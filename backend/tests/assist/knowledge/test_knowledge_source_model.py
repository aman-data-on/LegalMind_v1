"""Roadmap PHASE 1 / `AM-79`: the Constitution as a canonical source with a structured
representation beside it. The first group needs no database."""
import json
import re

from sqlalchemy import text

from legalmind import config
from legalmind.assist.knowledge import authority, constitution
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
    assert rows == {"L1.11": "L1.10", "L1.10": "L1.5", "L1.5": None}
    found = constitution.item_for_section(
        db, "14", permissions=frozenset({"assist.ask", "legal_position.view"}))
    assert found and found[1].startswith("14. Fixed-Term Commitments")
    # LEGAL-02: without the positions permission it returns nothing (`AM-104`).
    assert constitution.item_for_section(db, "14",
                                         permissions=frozenset({"assist.ask"})) is None


# --- PHASE 3 / AM-82: child retrieval records, breadcrumbs, parent expansion -------

def test_every_child_carries_a_breadcrumb_naming_its_place_and_nature():
    position = next(p for p in _items("31.2", "PARAGRAPH")
                    if p.content.startswith("Established Company Position"))
    history = next(p for p in _items("31.2", "PARAGRAPH")
                   if p.content.startswith("Historical exceptions"))
    assert position.breadcrumb.startswith("Legal Constitution L1.11 · 31.")
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


def test_a_position_expands_to_its_whole_section_with_law_and_history_labelled(db):
    """PHASE 8: the parent is the NUMBERED section — §14's position arrives with its
    own legal-basis caveat, labelled as the company's reading of the law; §31.2's
    position with its historical exceptions, labelled as history."""
    constitution.ingest(db)
    schema = config.assist_schema()
    def item(section, starts):
        return db.execute(text(
            f'SELECT id FROM "{schema}".knowledge_items WHERE section_path = :s '
            "AND kind = 'PARAGRAPH' AND content LIKE :c"),
            {"s": section, "c": starts + "%"}).scalar()
    s14 = constitution.expand(db, item("14", "No early exit"))
    assert "Applicable Law / Legal Basis:" in s14
    assert "[the company's reading of the law] Sections 73 and 74" in s14
    s312 = constitution.expand(db, item("31.2", "Established Company Position"))
    assert "[historical evidence, not current policy] Historical exceptions" in s312
    assert len(s14) <= 4000 + 200


# --- C-25 / AM-115: L1.11, the IT Act penalties as amended in 2023 --------------------

def _row(field: str, entry: str) -> str:
    """One field of one §28.3 entry, as the current file states it."""
    start = BODY.index(f"### **Entry: {entry}")
    return next(line for line in BODY[start:].splitlines()
                if line.startswith(f"| {field} |"))


def test_l1_11_states_the_it_act_penalties_as_amended():
    certin = _row("Legal Consequence / Penalty", "Reportable Cyber Security Incident")
    assert "fine which may extend to ₹1 crore" in certin and "one year" in certin
    assert "Jan Vishwas (Amendment of Provisions) Act, 2023" in certin
    assert "30 November 2023" in certin
    disclosure = _row("Legal Consequence / Penalty", "Unauthorized Disclosure")
    assert disclosure.startswith("| Legal Consequence / Penalty | Liability to a penalty "
                                 "which may extend to ₹25 lakh — a civil")
    # the 2023 amendment is recorded, and the old criminal penalty only as history
    assert "Before 30 November 2023" in disclosure


def test_l1_11_leaves_43a_open_for_counsel_and_invents_no_date():
    status = _row("Current Legal Status", "Compensation for Negligent Handling")
    assert '"section 43A shall be omitted"' in status
    assert "NOT established by the sources currently held" in status
    assert "REQUIRES COUNSEL CONFIRMATION" in status
    assert "2027" not in status and "2026" not in status       # no commencement invented


def test_l1_10_is_kept_as_history_and_superseded_after_ingest(db):
    """Production holds L1.10 as the CURRENT source when L1.11 arrives: ingest demotes
    it (its rows stay, as history) rather than leaving two current Constitutions."""
    schema = config.assist_schema()
    l15 = constitution._source(db, schema, "L1.5", "SUPERSEDED",
                               constitution.SUPERSEDED_FILES["L1.5"], None)
    constitution._source(db, schema, "L1.10", "CURRENT",
                         constitution.SUPERSEDED_FILES["L1.10"], "0" * 64, supersedes=l15)
    constitution.ingest(db)
    rows = dict(db.execute(text(
        f'SELECT version, status FROM "{schema}".knowledge_sources')).all())
    assert rows == {"L1.11": "CURRENT", "L1.10": "SUPERSEDED", "L1.5": "SUPERSEDED"}
    assert constitution.SUPERSEDED_FILES["L1.10"].read_text().count("₹1 lakh") >= 1
