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
import urllib.request

from legalmind.assist.onnx_backend import MANIFEST, MODEL_FILES, model_root


def provision(repo: str, revision: str = "main") -> pathlib.Path:
    target = model_root() / repo.replace("/", "__") / revision
    target.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}

    for name in MODEL_FILES:
        url = f"https://huggingface.co/{repo}/resolve/{revision}/{name}"
        request = urllib.request.Request(url, headers={"User-Agent": "legalmind"})
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = response.read()
        out = target / pathlib.Path(name).name
        out.write_bytes(payload)
        manifest[pathlib.Path(name).name] = hashlib.sha256(payload).hexdigest()

    manifest["repo"] = repo
    manifest["revision"] = revision
    (target / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--revision", default="main")
    args = ap.parse_args()
    target = provision(args.repo, args.revision)
    manifest = json.loads((target / MANIFEST).read_text())
    print(f"provisioned {args.repo}@{args.revision} -> {target}")
    for key in sorted(k for k in manifest if k.endswith(".onnx") or k.endswith(".json")):
        print(f"  {key:20s} sha256={manifest[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
