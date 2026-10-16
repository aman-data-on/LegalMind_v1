"""The uploaded documents are backed up, off the server, and provably intact.

Until 2026-10-16 the nightly backup dumped only the database. The original files
live in LEGALMIND_STORAGE_ROOT, outside it, so a restore brought back rows that
point at files no backup held. These tests pin the documents stage (C1/C2) the
way `test_backup_credentials.py` pins the parser: each block of `backup.sh` is
run on its own, so they need no root, no database and no network. The S3 helper
is a stand-in that copies files into a directory; gpg is real.
"""
from __future__ import annotations

import hashlib
import re
import stat
import subprocess
from pathlib import Path

BACKUP_SH = Path(__file__).resolve().parents[2] / "ops" / "production" / "backup.sh"


def _block(name: str) -> str:
    script = BACKUP_SH.read_text()
    found = re.search(rf"^# >>> {name}$.*?^# <<< {name}$", script, re.S | re.M)
    assert found, f"the {name} block moved — update this test"
    return found.group(0)


def _store(root: Path, files: dict[str, bytes]) -> Path:
    """A content-addressed store as `legalmind.ingestion.storage` writes it."""
    docs = root / "documents"
    for suffix, data in files.items():
        digest = hashlib.sha256(data).hexdigest()
        path = docs / digest[:2] / f"{digest}-{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return docs


def _archive(tmp_path: Path, docs: Path) -> subprocess.CompletedProcess:
    runner = tmp_path / "archive.sh"
    runner.write_text(f'set -euo pipefail\n{_block("documents-archive")}\n'
                      f'documents_archive "{docs}" "{tmp_path / "out.tar"}"\n')
    return subprocess.run(["bash", str(runner)], capture_output=True, text=True)


def test_an_intact_store_is_archived_whole_and_private(tmp_path):
    docs = _store(tmp_path, {"a1b2c3d4.pdf": b"%PDF one", "e5f6a7b8.docx": b"PK two"})
    done = _archive(tmp_path, docs)
    assert done.returncode == 0, done.stderr
    assert "documents ok:" in done.stdout and "(2 files," in done.stdout
    out = tmp_path / "out.tar"
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    listing = subprocess.run(["tar", "-tf", str(out)], capture_output=True, text=True)
    assert len([n for n in listing.stdout.split() if not n.endswith("/")]) == 2


def test_a_file_that_does_not_hash_to_its_name_fails_the_stage(tmp_path):
    docs = _store(tmp_path, {"a1b2c3d4.pdf": b"%PDF one"})
    victim = next(p for p in docs.rglob("*") if p.is_file())
    victim.write_bytes(b"%PDF changed on disk")
    done = _archive(tmp_path, docs)
    assert done.returncode != 0
    assert "does not hash to its own name" in done.stderr
    assert not (tmp_path / "out.tar").exists()


def test_a_missing_store_fails_loudly(tmp_path):
    done = _archive(tmp_path, tmp_path / "absent")
    assert done.returncode != 0 and "does not exist" in done.stderr


def test_a_file_not_named_by_its_hash_is_archived_unchecked(tmp_path):
    docs = tmp_path / "documents"
    (docs / "xx").mkdir(parents=True)
    (docs / "xx" / "legacy-name.pdf").write_bytes(b"%PDF legacy")
    done = _archive(tmp_path, docs)
    assert done.returncode == 0, done.stderr


def test_a_disk_without_room_refuses_the_archive(tmp_path):
    """Fourteen archives live on the root disk the database runs on: a store that
    outgrew it must fail the stage loudly, never fill the disk."""
    docs = _store(tmp_path, {"a1b2c3d4.pdf": b"%PDF one"})
    fake = tmp_path / "bin"
    fake.mkdir()
    (fake / "df").write_text("#!/bin/sh\necho Avail\necho 1024\n")
    (fake / "df").chmod(0o755)
    runner = tmp_path / "archive.sh"
    runner.write_text(f'set -euo pipefail\nexport PATH="{fake}:$PATH"\n'
                      f'{_block("documents-archive")}\n'
                      f'documents_archive "{docs}" "{tmp_path / "out.tar"}"\n')
    done = subprocess.run(["bash", str(runner)], capture_output=True, text=True)
    assert done.returncode != 0 and "bytes free" in done.stderr
    assert not (tmp_path / "out.tar").exists()


FAKE_HELPER = """import shutil, sys
from pathlib import Path
bucket = Path(sys.argv[0]).parent / "bucket"
cmd = sys.argv[1]
if cmd == "put":
    (bucket / sys.argv[3]).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(sys.argv[2], bucket / sys.argv[3])
elif cmd == "get":
    data = (bucket / sys.argv[2]).read_bytes()
    Path(sys.argv[3]).write_bytes(data + (b"x" if (bucket / "TAMPER").exists() else b""))
elif cmd == "prune":
    print("prune", sys.argv[2], sys.argv[3])
if (bucket / "FAIL_PUT").exists() and cmd == "put":
    sys.exit(1)
"""


def _offsite(tmp_path: Path, src: Path, prefix: str, tamper: bool = False,
             fail_put: bool = False):
    helper = tmp_path / "helper" / "s3_object.py"
    helper.parent.mkdir()
    helper.write_text(FAKE_HELPER)
    (helper.parent / "bucket").mkdir()
    if tamper:
        (helper.parent / "bucket" / "TAMPER").write_text("")
    if fail_put:
        (helper.parent / "bucket" / "FAIL_PUT").write_text("")
    passphrase = tmp_path / "pass"
    passphrase.write_text("test-passphrase-not-a-secret\n")
    home = tmp_path / "gnupg"
    home.mkdir(mode=0o700)
    runner = tmp_path / "offsite.sh"
    runner.write_text(
        f'set -euo pipefail\nexport GNUPGHOME="{home}"\nHELPER="{helper}"\n'
        f'LEGALMIND_BACKUP_PASSPHRASE_FILE="{passphrase}"\nREMOTE_KEEP_DAYS=90\n'
        f'WORK="$(mktemp -d)"\n{_block("offsite")}\n'
        f'offsite "{src}" "{prefix}" same_listing || exit 3\n')
    return subprocess.run(["bash", str(runner)], capture_output=True, text=True), \
        helper.parent / "bucket"


def test_the_documents_archive_goes_off_server_encrypted_and_read_back(tmp_path):
    docs = _store(tmp_path, {"a1b2c3d4.pdf": b"%PDF one"})
    assert _archive(tmp_path, docs).returncode == 0
    done, bucket = _offsite(tmp_path, tmp_path / "out.tar", "validation/documents/")
    assert done.returncode == 0, done.stderr
    assert "off-server ok: validation/documents/out.tar.gpg" in done.stdout
    assert "prune validation/documents/ 90" in done.stdout
    stored = (bucket / "validation" / "documents" / "out.tar.gpg").read_bytes()
    assert b"%PDF one" not in stored                   # encrypted before it left


def test_a_read_back_that_differs_from_the_upload_fails(tmp_path):
    docs = _store(tmp_path, {"a1b2c3d4.pdf": b"%PDF one"})
    assert _archive(tmp_path, docs).returncode == 0
    done, _ = _offsite(tmp_path, tmp_path / "out.tar", "documents/", tamper=True)
    assert done.returncode != 0
    assert "read-back of documents/ differs" in done.stderr


def test_a_failed_upload_stops_the_documents_stage_even_without_set_e(tmp_path):
    """Called as `offsite … || DOCS_STATUS=1`, bash suspends `set -e` inside the
    function: a failed upload must still stop it, not run on to a read-back."""
    docs = _store(tmp_path, {"a1b2c3d4.pdf": b"%PDF one"})
    assert _archive(tmp_path, docs).returncode == 0
    done, _ = _offsite(tmp_path, tmp_path / "out.tar", "documents/", fail_put=True)
    assert done.returncode == 3
    assert "upload to documents/ failed" in done.stderr
    assert "read-back" not in done.stderr


def test_the_database_keys_and_the_stage_order_are_unchanged():
    """Production keys stay `legalmind_v1_dev/<file>.gpg`; the documents get their
    own prefix; a validation root prefixes both; the overrides are read before the
    credential file is parsed; and a documents failure never skips the database's
    off-server copy, while a skipped upload still reports it."""
    script = BACKUP_SH.read_text()
    assert 'offsite "$F" "$REMOTE_ROOT$DB/"' in script
    assert 'offsite "$D" "${REMOTE_ROOT}documents/" same_listing || DOCS_STATUS=1' in script
    assert script.index('offsite "$F"') < script.index('offsite "$D"')
    assert script.index('REMOTE_ROOT="${LEGALMIND_BACKUP_REMOTE_ROOT:-}"') < \
        script.index("while IFS= read -r _line")
    assert script.count('exit "${DOCS_STATUS:-0}"') == 2
    assert script.rstrip().endswith('exit "$DOCS_STATUS"')
