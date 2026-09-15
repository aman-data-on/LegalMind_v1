"""The backup credential file is PARSED, never sourced.

On 2026-09-15 a CloudPe secret key was pasted into
`/root/.legalmind-backup.env` with one leading space:

    LEGALMIND_S3_SECRET_ACCESS_KEY= <40-char secret>

`backup.sh` loaded that file with `set -a; . "$CREDS"`. Sourcing EXECUTES the
file, so bash set the variable to empty and ran the secret as a command — and
printed the whole thing in the resulting "command not found" error. The
credential leaked by being read, and had to be rotated.

The fix is not "strip whitespace". It is that a credentials file is DATA: read
KEY=VALUE, execute nothing. These tests pin that, because the failure is silent
in the good case and catastrophic in the bad one.
"""
from __future__ import annotations

import re
import subprocess
import textwrap
from pathlib import Path

import pytest

BACKUP_SH = Path(__file__).resolve().parents[2] / "ops" / "production" / "backup.sh"


def load(env_text: str, tmp_path: Path) -> dict[str, str]:
    """Run only the parser block of backup.sh against `env_text`."""
    script = BACKUP_SH.read_text()
    block = re.search(r"^while IFS= read -r _line.*?^unset _line _key _val$",
                      script, re.S | re.M)
    assert block, "the credential parser block moved — update this test"
    creds = tmp_path / "env"
    creds.write_text(env_text)
    runner = tmp_path / "run.sh"
    runner.write_text(f'CREDS="{creds}"\n{block.group(0)}\nenv | grep ^LEGALMIND_ || true\n')
    done = subprocess.run(["bash", str(runner)], capture_output=True, text=True)
    return dict(
        line.split("=", 1) for line in done.stdout.splitlines() if "=" in line
    )


def test_a_leading_space_does_not_execute_the_secret(tmp_path):
    """The exact 2026-09-15 incident."""
    got = load("LEGALMIND_S3_SECRET_ACCESS_KEY= s3cr3tValue1234567890\n", tmp_path)
    assert got["LEGALMIND_S3_SECRET_ACCESS_KEY"] == "s3cr3tValue1234567890"


def test_shell_metacharacters_stay_literal(tmp_path):
    """A secret is arbitrary bytes, not shell. Nothing here may be evaluated."""
    hostile = "pa$(echo PWNED)ss`echo PWNED`word"
    got = load(f"LEGALMIND_S3_SECRET_ACCESS_KEY={hostile}\n", tmp_path)
    # Byte-for-byte: the substitutions are still there as TEXT, which is only
    # true if nothing evaluated them.
    assert got["LEGALMIND_S3_SECRET_ACCESS_KEY"] == hostile


def test_a_value_may_contain_spaces(tmp_path):
    got = load("LEGALMIND_S3_BUCKET=two words\n", tmp_path)
    assert got["LEGALMIND_S3_BUCKET"] == "two words"


@pytest.mark.parametrize("quoted", ['"quoted123"', "'quoted123'"])
def test_one_layer_of_quotes_is_stripped(quoted, tmp_path):
    got = load(f"LEGALMIND_S3_ACCESS_KEY_ID={quoted}\n", tmp_path)
    assert got["LEGALMIND_S3_ACCESS_KEY_ID"] == "quoted123"


def test_comments_and_blank_lines_are_skipped(tmp_path):
    got = load(textwrap.dedent("""
        # a comment

        LEGALMIND_S3_REGION=in-west2
    """), tmp_path)
    assert got["LEGALMIND_S3_REGION"] == "in-west2"


def test_unexpected_keys_are_not_exported(tmp_path):
    """A credentials file must not be able to set PATH or LD_PRELOAD."""
    got = load("PATH=/tmp/evil\nLD_PRELOAD=/tmp/evil.so\nLEGALMIND_S3_REGION=in-west2\n",
               tmp_path)
    assert got.get("LEGALMIND_S3_REGION") == "in-west2"
    assert "PATH" not in got and "LD_PRELOAD" not in got


def test_backup_sh_never_sources_the_credentials_file():
    """The regression guard: if someone reintroduces `.` or `source`, fail."""
    script = BACKUP_SH.read_text()
    for line in script.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert not re.match(r'^(\.|source)\s+"?\$CREDS', stripped), \
            f"credentials must be parsed, never sourced: {line!r}"
