"""The canonical Constitution is redacted (`AM-59`: L1.10, counterparty names redacted),
and since the multi-source Ask path (`AM-94`) shows Constitution text to readers, a
missed redaction is a leak — found live on 2026-09-26 in a §31.2 emphasis line whose own
paragraph already called the same entity "[Customer A]". The names never enter this
file: each is pinned by the SHA-256 of its lower-cased form, checked against every word
of the canonical file and of every ingested record (the text every answer is built
from)."""
import hashlib
import re

from sqlalchemy import text as sql

from legalmind import config
from legalmind.assist import constitution

#: sha256(name.lower()) of every counterparty name the redaction pass must never miss.
REDACTED = {
    "d3f965d3bf1bf388de88e2b23d580e782cd23648d4a7898f07e705abf2cf1658",
}
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9&.'-]*")


def _leaks(text: str) -> set[str]:
    return {w for w in _WORD.findall(text)
            if hashlib.sha256(w.lower().strip(".'-").encode()).hexdigest() in REDACTED}


def test_the_canonical_constitution_carries_no_redacted_name():
    assert _leaks(constitution.CURRENT_FILE.read_text()) == set()


def test_no_ingested_constitution_record_carries_a_redacted_name(db):
    constitution.ingest(db)
    rows = db.execute(sql(f'SELECT clause, content, breadcrumb FROM '
                          f'"{config.assist_schema()}".knowledge_items')).all()
    assert rows
    assert not any(_leaks(" ".join(x or "" for x in r)) for r in rows)


def test_a_placeholder_never_reads_as_a_leak():
    assert _leaks("The [Customer A] MSA, Clause 5.1") == set()
