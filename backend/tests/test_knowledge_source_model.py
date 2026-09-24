"""Roadmap PHASE 1 / `AM-79`: the Constitution as a canonical source with a structured
representation beside it. The first group needs no database."""
import json
import re

from sqlalchemy import text

from legalmind import config
from legalmind.assist import authority, constitution
from tools import rag_benchmark

BODY = constitution.CURRENT_FILE.read_text()
ITEMS = constitution.parse(BODY)


def _items(path, kind=None):
    return [i for i in ITEMS if i.section_path == path and (kind is None or i.kind == kind)]


def test_every_line_of_the_constitution_lands_in_exactly_one_item():
    owned: dict[int, int] = {}
    for item in ITEMS[1:]:
        for n in range(item.line_start, item.line_end + 1):
            assert n not in owned, f"line {n} in items {owned[n]} and {item.ordinal}"
            owned[n] = item.ordinal
    first = min(owned)
    lost = [n for n, line in enumerate(BODY.split("\n"), 1)
            if n >= first and line.strip() and n not in owned]
    assert not lost, f"content lost at lines {lost[:5]}"


def test_no_section_number_is_invented():
    headings = [line for line in BODY.split("\n") if line.startswith("#")]
    for item in ITEMS:
        if item.kind != "PARAGRAPH" and item.section_path and item.clause:
            assert any(item.section_path in h for h in headings), item.section_path


def test_historical_exceptions_are_separated_from_current_policy():
    paras = _items("31.2", "PARAGRAPH")
    position = next(p for p in paras if p.content.startswith("Established Company Position"))
    history = next(p for p in paras if p.content.startswith("Historical exceptions"))
    assert (position.authority, position.status) == ("COMPANY_CONSTITUTION", "CURRENT")
    assert (history.authority, history.status) == ("HISTORICAL_EXCEPTION", "HISTORICAL")
    # §15.5 names the reference NDA's counterparty placeholder in CURRENT guidance.
    assert all(p.status == "CURRENT" for p in _items("15.5", "PARAGRAPH"))


def test_the_law_as_the_company_reads_it_is_not_company_policy():
    law = [p for p in _items("14", "PARAGRAPH") if "Sections 73 and 74" in p.content]
    assert law and all(p.authority == "SECONDARY_REFERENCE" for p in law)


def test_the_one_unratified_section_is_marked_so():
    assert _items("31.6a") and all(i.status == "UNRATIFIED" for i in _items("31.6a"))
    assert not any(i.status == "UNRATIFIED" for i in ITEMS if i.section_path != "31.6a")


def test_every_standard_and_benchmark_ref_resolves_to_a_constitution_item():
    paths = {i.section_path for i in ITEMS}
    for f in sorted(constitution.REPO_ROOT.glob("backend/config/company_standards/*.json")):
        section = (json.loads(f.read_text()).get("configuration", {})
                   .get("constitution") or {}).get("section")
        assert section is None or str(section) in paths, (f.name, section)
    cases = json.loads(rag_benchmark.DATASET.read_text())["cases"]
    for ref in {r for c in cases for slot in c["gold"] for r in slot if r.startswith("CONST:")}:
        assert ref.removeprefix("CONST:") in paths, ref


def test_the_authority_vocabulary_is_one_list():
    def vocab(path):
        return re.search(r"AUTHORITIES = \(([^)]*)\)", path.read_text()).group(1).split()
    migration = next(constitution.REPO_ROOT.glob("backend/alembic/versions/f4c1e8a2b7d9_*.py"))
    assert vocab(migration) == vocab(constitution.pathlib.Path(authority.__file__))
    assert authority.of_document("FINAL_SIGNED") == "EXECUTED_DOCUMENT"
    assert authority.of_document(None) is None                 # unknown is never "executed"
    assert authority.of_statute("The Companies Act, 1956 (REPEALED — x)") == ("PRIMARY_LAW", "REPEALED")
    assert authority.of_standard("Legal Constitution, Lawyer Review Version L1.10") == "COMPANY_CONSTITUTION"


def test_ingest_writes_the_version_chain_and_is_idempotent(db):
    first = constitution.ingest(db)
    assert first["changed"] and first["items"] == len(ITEMS)
    assert constitution.ingest(db)["changed"] is False
    schema = config.assist_schema()
    rows = dict(db.execute(text(
        f'SELECT s.version, o.version FROM "{schema}".knowledge_sources s '
        f'LEFT JOIN "{schema}".knowledge_sources o ON o.id = s.supersedes_id')).all())
    assert rows == {"L1.10": "L1.5", "L1.5": None}
    found = constitution.item_for_section(db, "14")
    assert found and found[1].startswith("14. Fixed-Term Commitments")


# --- PHASE 3 / AM-82: child retrieval records, breadcrumbs, parent expansion -------

def test_every_child_carries_a_breadcrumb_naming_its_place_and_nature():
    position = next(p for p in _items("31.2", "PARAGRAPH")
                    if p.content.startswith("Established Company Position"))
    history = next(p for p in _items("31.2", "PARAGRAPH")
                   if p.content.startswith("Historical exceptions"))
    assert position.breadcrumb.startswith("Legal Constitution L1.10 · 31.")
    assert "31.2 Early Termination" in position.breadcrumb
    assert history.breadcrumb.endswith("historical evidence, not current policy")
    assert all(i.breadcrumb for i in ITEMS if i.kind == "PARAGRAPH")


def test_constitution_search_finds_the_position_one_child_per_parent(db):
    constitution.ingest(db)
    perms = frozenset({"assist.ask", "legal_position.view"})
    hits = constitution.search(db, query="early exit fixed-term commitment committed-term "
                               "value payable", permissions=perms, embed_query=lambda q: None)
    assert hits and hits[0].section_path in ("14", "31.2")
    assert len({h.parent_id for h in hits}) == len(hits), "two children of one parent"
    assert not any(h.status == "UNRATIFIED" for h in hits)
    assert constitution.search(db, query="early exit", permissions=frozenset({"assist.ask"}),
                               embed_query=lambda q: None) == []       # LEGAL-02


def test_expansion_restores_the_provision_and_labels_history(db):
    constitution.ingest(db)
    perms = frozenset({"assist.ask", "legal_position.view"})
    hit = next(h for h in constitution.search(
        db, query="historical exceptions signed MSAs 30-day no-penalty exit",
        permissions=perms, embed_query=lambda q: None) if h.section_path == "31.2")
    context = constitution.expand(db, hit.item_id)
    assert "Established Company Position" in context
    assert "[historical evidence, not current policy] Historical exceptions" in context
