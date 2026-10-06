"""Fetch embedding-model weights once — `AM-26` r5, and an operator action.

    python3 -m tools.provision_model <repo> [--revision REV]

Deliberately a tool rather than a function in `legalmind/assist/`. Every module under
`legalmind/` is asserted by `tests/test_import_boundaries.py` to import no network
client at all, and that invariant is worth more than the convenience of putting a
downloader next to its consumer. The first draft did put it there, and the boundary test
refused it — so `AM-26` r5's *"weights are obtained once … and never fetched at
runtime"* is now structural rather than a promise: the application package has no code
capable of fetching them.

Downloading public model weights is not an egress of our data. Nothing about a document,
a chunk, an embedding input, a prompt or an answer leaves, so `AM-30` t1 is untouched —
the one permitted egress remains the generation call.

`--revision` should be a commit sha for anything but exploration: `AM-30` t7's reasoning
that a floating alias is not a pin applies to weights exactly as it does to a hosted
model version.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys
import urllib.error
import urllib.request

from legalmind.assist.ingestion.onnx_backend import MANIFEST, MODEL_FILES, model_root


def _download(url: str, path: pathlib.Path, attempts: int = 8) -> None:
    """Stream to disk, RESUMING with an HTTP Range request when the connection drops —
    a 2.3 GB weights file was reset mid-transfer on the first try (2026-09-24). The
    checksum is taken from the finished file, never from a partial one."""
    import time
    for attempt in range(attempts):
        have = path.stat().st_size if path.exists() else 0
        headers = {"User-Agent": "legalmind", **({"Range": f"bytes={have}-"} if have else {})}
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers),
                                        timeout=300) as response:
                if have and response.status != 206:        # server ignored the Range
                    have = 0
                with path.open("ab" if have else "wb") as out:
                    while block := response.read(1 << 20):
                        out.write(block)
            return
        except urllib.error.HTTPError as exc:
            if exc.code == 416:                           # already complete
                return
            raise
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))


def _sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def provision(repo: str, revision: str = "main", *, onnx: str = "onnx/model.onnx",
              extra: tuple[str, ...] = ()) -> pathlib.Path:
    """Download the model files, streamed to disk and hashed as they arrive (a 2.3 GB
    external-data file must not be held in memory). `onnx` picks the graph file for
    repos that ship several; `extra` names further files the graph needs — an ONNX
    model over 2 GB keeps its weights in `<name>.onnx_data`, beside the graph. Every
    file lands in the manifest and is verified at load (`AM-26` r5)."""
    target = model_root() / repo.replace("/", "__") / revision
    target.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    files = [onnx if n == "onnx/model.onnx" else n for n in MODEL_FILES]
    for name in (*files, *extra):
        url = f"https://huggingface.co/{repo}/resolve/{revision}/{name}"
        local = "model.onnx" if name == onnx else pathlib.Path(name).name
        _download(url, target / local)
        manifest[local] = _sha256_file(target / local)
    manifest["repo"] = repo
    manifest["revision"] = revision
    (target / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--revision", default="main")
    ap.add_argument("--onnx", default="onnx/model.onnx")
    ap.add_argument("--extra", nargs="*", default=[])
    args = ap.parse_args()
    target = provision(args.repo, args.revision, onnx=args.onnx, extra=tuple(args.extra))
    manifest = json.loads((target / MANIFEST).read_text())
    print(f"provisioned {args.repo}@{args.revision} -> {target}")
    for key in sorted(k for k in manifest if k not in ("repo", "revision")):
        print(f"  {key:20s} sha256={manifest[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
