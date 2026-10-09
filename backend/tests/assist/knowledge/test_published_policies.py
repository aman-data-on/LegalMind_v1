"""`AM-130` (AB-74): the published Privacy Policy, TOS, SLA and AUP of both brands, read
from the website and searched by Ask beside the Constitution — never as it.

The HTML below is synthetic, shaped like the two sites' templates (2026-10-09); the
real pages stay out of the repository (54.6) and are checked only where present."""
import datetime
import io
import pathlib
import urllib.error

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from legalmind import config
from legalmind.assist.knowledge import constitution, published
from legalmind.assist.retrieval import evidence, retrieval
from legalmind.assist.synthesis import answer

FILLER = " ".join(["The customer accepts these terms of service in full."] * 80)
# Leapswitch's template: content in div.container, then a footer by id.
LEAPSWITCH = f"""<html><head><title>x</title><script>var a=1;</script></head><body>
<div class="menu"><ul><li>VPS</li><li>Login 24x7 Support</li></ul></div>
<div class="container"><h1>Leapswitch Service Level Agreement</h1>
<p>{FILLER}</p>
<h2>16. Service Credits</h2>
<h4>Issuance of Service Credits</h4>
<table><tr><td>Less than 99.9% but equal to or greater than 99.0%</td><td>15%</td></tr>
<tr><td>Less than 95.0%</td><td>100%</td></tr></table>
<div class="card-footer"><p>To apply for a Service Credit, you must submit a support
request within sixty (60) calendar days following the incident.</p></div></div>
<div id="footer"><h2>Contact Us</h2><ul><li>Open Tickets</li></ul></div></body></html>"""
# CloudPe's template: content inside <main>, site chrome after it.
CLOUDPE = f"""<html><body><nav>Products Pricing</nav><main><div><h1>CloudPe by Leapswitch
Service Level Agreement (SLA)</h1><section><p>{FILLER}</p><h2>Issuance of Service
Credits</h2><p>Less than 99.9% but &ge; 99.0% 5%</p></section></div></main>
<div><p>Products Services Use Cases Careers</p></div></body></html>"""
SLA_LS = next(p for p in published.POLICIES if p.key == "SLA-leapswitch")
SLA_CP = next(p for p in published.POLICIES if p.key == "SLA-cloudpe")
PERMS = frozenset({"assist.ask", "legal_position.view"})
DAY = datetime.date(2026, 10, 9)
LATER = datetime.date(2026, 11, 1)


def test_the_policy_text_is_kept_and_the_site_around_it_is_not():
    ls = published.policy_text(published.extract(LEAPSWITCH))
    assert ls.startswith("Leapswitch Service Level Agreement")
    assert "15%" in ls and "99.9% but equal" in ls
    assert "sixty (60)" in ls, "a card-footer inside the policy is not the site footer"
    for chrome in ("Login 24x7", "Open Tickets", "Contact Us", "var a"):
        assert chrome not in ls, chrome
    cp = published.policy_text(published.extract(CLOUDPE))
    assert "≥ 99.0% 5%" in cp and "Products Pricing" not in cp and "Careers" not in cp


def test_a_table_row_stays_one_block_with_its_cells_in_order():
    rows = [t for tag, t in published.extract(LEAPSWITCH) if tag == "tr"]
    assert rows == ["Less than 99.9% but equal to or greater than 99.0% | 15%",
                    "Less than 95.0% | 100%"]


def test_headings_nest_and_every_record_names_its_policy_and_place():
    rows = published.items(SLA_LS, published.extract(LEAPSWITCH))
    paras = [i for i in rows if i.kind == "PARAGRAPH"]
    assert all(i.breadcrumb.startswith("Leapswitch Service Level Agreement") for i in paras)
    assert paras[0].breadcrumb == "Leapswitch Service Level Agreement"   # opening terms
    assert any(i.breadcrumb == "Leapswitch Service Level Agreement · 16. Service Credits"
               " · Issuance of Service Credits" for i in paras)
    assert not any("Constitution" in i.breadcrumb or "http" in i.breadcrumb for i in rows)
    assert all(rows[i.parent].kind != "DOCUMENT" for i in paras), "every paragraph anchored"
    assert published.citation(SLA_LS.source_type, paras[0].breadcrumb).endswith(
        "(published at https://leapswitch.com/service-level-agreement.php)")


def test_only_the_two_sites_over_https_may_be_fetched_or_redirected_to():
    assert {p.url.split("/")[2] for p in published.POLICIES} == published.HOSTS
    assert all(p.url.startswith("https://") for p in published.POLICIES)
    with pytest.raises(ValueError):
        published.fetch(published.Policy("X", "L", "T", "https://evil.example/terms"))
    with pytest.raises(ValueError):
        published.fetch(published.Policy("X", "L", "T", "http://leapswitch.com/x"))
    handler = published._Redirects()
    req = published.urllib.request.Request(SLA_LS.url)
    for target in ("https://evil.example/x", "http://leapswitch.com/x"):
        with pytest.raises(urllib.error.HTTPError):           # refused before it is made
            handler.redirect_request(req, io.BytesIO(), 302, "Found", {}, target)
    assert handler.redirect_request(req, io.BytesIO(), 301, "Moved", {},
                                    "https://www.cloudpe.com/sla/") is not None


@pytest.fixture
def material(tmp_path, monkeypatch):
    monkeypatch.setenv("LEGALMIND_SOURCE_MATERIAL_DIR", str(tmp_path))
    return tmp_path


def _sources(db, policy):
    return db.execute(text(
        f'SELECT version, status, file_sha256 FROM "{config.assist_schema()}".'
        "knowledge_sources WHERE source_type = :t ORDER BY effective_from, status"),
        {"t": policy.source_type}).all()


def test_an_unchanged_page_writes_nothing_and_a_changed_one_supersedes(db, material):
    first = published.ingest(db, SLA_LS, LEAPSWITCH, read_on=DAY)
    assert first["changed"] and first["items"]
    assert (material / "published/2026-10-09/SLA-leapswitch.html").exists()
    assert published.ingest(db, SLA_LS, LEAPSWITCH, read_on=DAY)["changed"] is False
    edited = LEAPSWITCH.replace("sixty (60)", "thirty (30)")
    assert published.ingest(db, SLA_LS, edited, read_on=LATER)["changed"]
    rows = _sources(db, SLA_LS)
    assert [r.status for r in rows].count("CURRENT") == 1
    assert {r.status for r in rows} == {"CURRENT", "SUPERSEDED"}
    audit = db.execute(text(
        "SELECT before_state, after_state FROM audit_events WHERE action = :a "
        "ORDER BY after_state->>'version'"), {"a": "assist.published_policy_updated"}).all()
    assert len(audit) == 2 and audit[0].before_state is None
    assert audit[1].before_state["sha256"] in {r.file_sha256 for r in rows}
    assert "thirty" not in str(audit[1].after_state)            # hashes, never text


def test_a_page_changed_back_the_same_day_restores_that_version(db, material):
    published.ingest(db, SLA_LS, LEAPSWITCH, read_on=DAY)
    published.ingest(db, SLA_LS, LEAPSWITCH.replace("sixty (60)", "thirty (30)"),
                     read_on=DAY)
    back = published.ingest(db, SLA_LS, LEAPSWITCH, read_on=DAY)
    assert back["changed"]
    rows = _sources(db, SLA_LS)
    assert len(rows) == 2 and [r.status for r in rows].count("CURRENT") == 1


def test_a_broken_or_cut_short_page_changes_nothing(db, material):
    published.ingest(db, SLA_LS, LEAPSWITCH, read_on=DAY)
    with pytest.raises(ValueError):
        published.ingest(db, SLA_LS, "<html><h1>Maintenance</h1><p>Back soon</p></html>",
                         read_on=LATER)
    half = LEAPSWITCH.replace(FILLER, " ".join(["Short."] * 320))   # > MIN_WORDS, < 70%
    with pytest.raises(ValueError, match="cut-short"):
        published.ingest(db, SLA_LS, half, read_on=LATER)
    assert [r.status for r in _sources(db, SLA_LS)] == ["CURRENT"]


def test_refresh_keeps_one_sites_update_when_the_other_fails(engine, material):
    """Each policy commits on its own (savepoints stand in for transactions here)."""
    conn = engine.connect()
    outer = conn.begin()
    db = sessionmaker(bind=conn, join_transaction_mode="create_savepoint")()
    try:
        def fetcher(p):
            if p.brand == "CloudPe":
                raise OSError("unreachable")
            return LEAPSWITCH
        results = {r["policy"]: r for r in published.refresh(db, fetcher=fetcher,
                                                               read_on=DAY)}
        assert results["SLA-leapswitch"]["changed"] and "error" in results["SLA-cloudpe"]
        assert [r.status for r in _sources(db, SLA_LS)] == ["CURRENT"]
        assert _sources(db, SLA_CP) == []
    finally:
        db.close()
        outer.rollback()
        conn.close()


def test_ask_finds_the_published_text_labelled_as_itself(db, material):
    constitution.ingest(db)
    published.ingest(db, SLA_LS, LEAPSWITCH, read_on=DAY)
    published.ingest(db, SLA_CP, CLOUDPE, read_on=DAY)
    hits = constitution.search(db, query="service credit support request sixty days",
                               permissions=PERMS, embed_query=lambda q: None)
    pub = [h for h in hits if h.source_type == SLA_LS.source_type]
    assert pub and pub[0].authority == "APPROVED_COMPANY_DOCUMENT"
    # LEGAL-02: the same permission as the Constitution
    assert constitution.search(db, query="service credit", permissions=frozenset(
        {"assist.ask"}), embed_query=lambda q: None) == []
    cands = retrieval._search(db, retrieval.CONSTITUTION,
                              "service credit support request sixty days",
                              permissions=PERMS, route=None, document_version_id=None,
                              embed_query=lambda q: None)
    c = next(c for c in cands if c.ref.startswith(f"PUB:{SLA_LS.source_type}:"))
    src = evidence.Source("COMPANY_POSITION", c, "", None, True, None)
    assert answer.citation(src).startswith("Leapswitch Service Level Agreement")
    assert "(published at https://leapswitch.com/" in answer.citation(src)
    context = constitution.expand(db, c.item_id)
    assert context.startswith("Leapswitch Service Level Agreement")
    assert "Legal Constitution" not in context


LIVE = pathlib.Path(config.source_material_dir()) / "published"


@pytest.mark.skipif(not LIVE.exists(), reason="source material not present (54.6)")
def test_the_saved_live_pages_extract_as_whole_policies():
    folder = max(p for p in LIVE.iterdir() if p.is_dir())
    for policy in published.POLICIES:
        blocks = published.extract((folder / f"{policy.key}.html").read_text())
        body = published.policy_text(blocks)
        assert len(body.split()) >= published.MIN_WORDS, policy.key
        assert "Open Tickets" not in body and "Knowledge Base" not in body, policy.key
        rows = published.items(policy, blocks)
        assert all(rows[i.parent].kind != "DOCUMENT" for i in rows if i.kind == "PARAGRAPH")
