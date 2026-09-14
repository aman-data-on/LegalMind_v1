#!/usr/bin/env python3
"""Move one object to and from the off-server backup bucket.

WHY THIS EXISTS. Backups lived only on the machine they protect, which is not a
backup against losing the machine. This is the smallest thing that fixes that:
`put`, `get`, `list`, `delete` against an S3-compatible endpoint, driven by
`backup.sh`. No framework, no abstraction over boto3 — boto3 IS the abstraction.

`python3-boto3` is an apt package already installed system-wide, so this adds no
project dependency and raises no rule-19 question.

CONFIGURATION comes from the environment, normally `/root/.legalmind-backup.env`
(mode 600, root-only). Nothing here ever prints a key, a secret or a URL that
carries one — `_config()` reports only which variable names are MISSING.

    LEGALMIND_S3_ENDPOINT           https://<region-endpoint>
    LEGALMIND_S3_BUCKET             legalmind-production-backups
    LEGALMIND_S3_REGION             S3-INWEST2
    LEGALMIND_S3_ACCESS_KEY_ID      <secret>
    LEGALMIND_S3_SECRET_ACCESS_KEY  <secret>

Usage:
    python3 s3_object.py check
    python3 s3_object.py put <local-file> <key>
    python3 s3_object.py get <key> <local-file>
    python3 s3_object.py list [prefix]
    python3 s3_object.py delete <key>
"""

from __future__ import annotations

import hashlib
import os
import sys

REQUIRED = (
    "LEGALMIND_S3_ENDPOINT",
    "LEGALMIND_S3_BUCKET",
    "LEGALMIND_S3_REGION",
    "LEGALMIND_S3_ACCESS_KEY_ID",
    "LEGALMIND_S3_SECRET_ACCESS_KEY",
)


def _config() -> dict[str, str]:
    """Return the settings, or exit naming ONLY the missing variable names.

    Never echoes a value. A missing-credential message that quotes the value it
    did find is how secrets reach logs.
    """
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        print("off-server storage is not configured; missing: " + ", ".join(missing),
              file=sys.stderr)
        raise SystemExit(2)
    return {name: os.environ[name] for name in REQUIRED}


def _client(cfg: dict[str, str]):
    import boto3  # apt: python3-boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=cfg["LEGALMIND_S3_ENDPOINT"],
        region_name=cfg["LEGALMIND_S3_REGION"],
        aws_access_key_id=cfg["LEGALMIND_S3_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["LEGALMIND_S3_SECRET_ACCESS_KEY"],
        # Path style: an S3-compatible provider rarely has per-bucket DNS, and a
        # virtual-host request against one fails as a name-resolution error,
        # which reads like a network fault rather than a configuration choice.
        config=Config(s3={"addressing_style": "path"},
                      retries={"max_attempts": 3, "mode": "standard"}),
    )


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stale_keys(objects, keep_days, now=None):
    """Return (keys to delete, refusal reason). A reason means delete nothing.

    Pure, because this is the DELETION path and the one part of this file that
    can destroy a backup. Age arithmetic lives here rather than in the shell,
    where parsing an ISO timestamp is a bug waiting for a timezone.

    The refusal matters more than the selection: if EVERY object looks stale,
    the clock or the prefix is wrong far more often than the whole archive
    genuinely expired on the same night — and emptying the bucket is not the
    recovery from either.
    """
    import datetime as dt
    now = now or dt.datetime.now(dt.UTC)
    cutoff = now - dt.timedelta(days=keep_days)
    stale = [o["Key"] for o in objects if o["LastModified"] < cutoff]
    if stale and len(stale) == len(objects):
        return [], (f"all {len(objects)} object(s) are older than {keep_days}d "
                    "— check the clock or the prefix")
    return stale, None


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    command = argv[1]

    # `check` proves the credentials work and the bucket is reachable WITHOUT
    # writing anything — the probe backup.sh runs before it bothers encrypting.
    if command == "check":
        cfg = _config()
        _client(cfg).head_bucket(Bucket=cfg["LEGALMIND_S3_BUCKET"])
        print(f"bucket reachable: {cfg['LEGALMIND_S3_BUCKET']} "
              f"({cfg['LEGALMIND_S3_REGION']})")
        return 0

    cfg = _config()
    client = _client(cfg)
    bucket = cfg["LEGALMIND_S3_BUCKET"]

    if command == "put":
        local, key = argv[2], argv[3]
        digest = sha256(local)
        with open(local, "rb") as fh:
            # The digest travels WITH the object. Verifying a download against a
            # checksum kept only on the machine that made it proves nothing once
            # that machine is the thing you lost.
            client.put_object(Bucket=bucket, Key=key, Body=fh,
                              Metadata={"sha256": digest},
                              ContentType="application/octet-stream")
        head = client.head_object(Bucket=bucket, Key=key)
        stored = head.get("Metadata", {}).get("sha256")
        if stored != digest:
            print(f"UPLOAD VERIFY FAILED: stored sha256 {stored} != local {digest}",
                  file=sys.stderr)
            return 1
        print(f"uploaded {key} ({head['ContentLength']} bytes) sha256={digest}")
        return 0

    if command == "get":
        key, local = argv[2], argv[3]
        client.download_file(bucket, key, local)
        head = client.head_object(Bucket=bucket, Key=key)
        stored = head.get("Metadata", {}).get("sha256")
        local_digest = sha256(local)
        if stored and stored != local_digest:
            print(f"DOWNLOAD VERIFY FAILED: {key} sha256 {local_digest} != {stored}",
                  file=sys.stderr)
            return 1
        print(f"downloaded {key} sha256={local_digest}")
        return 0

    if command == "list":
        prefix = argv[2] if len(argv) > 2 else ""
        pages = client.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix=prefix)
        for page in pages:
            for obj in page.get("Contents", []):
                print(f"{obj['LastModified'].isoformat()}\t{obj['Size']}\t{obj['Key']}")
        return 0

    if command == "delete":
        client.delete_object(Bucket=bucket, Key=argv[2])
        print(f"deleted {argv[2]}")
        return 0

    if command == "prune":
        prefix, keep_days = argv[2], int(argv[3])
        objects = [o for page in client.get_paginator("list_objects_v2")
                   .paginate(Bucket=bucket, Prefix=prefix)
                   for o in page.get("Contents", [])]
        stale, problem = stale_keys(objects, keep_days)
        if problem:
            print(f"REFUSING to prune {prefix!r}: {problem}", file=sys.stderr)
            return 1
        for key in stale:
            client.delete_object(Bucket=bucket, Key=key)
            print(f"pruned {key}")
        print(f"retention: {len(stale)} removed, {len(objects) - len(stale)} "
              f"retained (> {keep_days}d under {prefix!r})")
        return 0

    print(f"unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
