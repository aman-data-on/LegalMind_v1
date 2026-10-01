"""Delete expired Ask attachment material — A4-2 retention (30 days by default).

    python3 -m tools.purge_attachments

Run daily by `ops/production/legalmind-attachment-purge.timer`. Idempotent; prints a
count only — never a filename or any text.
"""
from __future__ import annotations

from legalmind.assist import attachments
from legalmind.db.session import new_session


def main() -> int:
    db = new_session()
    try:
        n = attachments.purge_expired(db)
        db.commit()
    finally:
        db.close()
    print(f"purged {n} expired attachment(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
