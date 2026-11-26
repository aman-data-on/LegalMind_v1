"""Source integrity B1: the normaliser, the exact passage matcher, the per-passage status,
the policy-figure check and the refresh hardening (`AM-130` extension).

Synthetic pages are shaped like the two sites' templates; the real stored snapshots
(`legal-docs/published/`, gitignored, 54.6) are read only where present. The quotes and
figures in the drafts below are TEST INPUTS about stored text — never a policy position."""
import datetime
import io
import pathlib
import urllib.error

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from legalmind import config
from legalmind.assist.knowledge import published
from legalmind.assist.knowledge import source_check as sc

SLA_LS = next(p for p in published.POLICIES if p.key == "SLA-leapswitch")
TOS_LS = next(p for p in published.POLICIES if p.key == "TOS-leapswitch")
FILLER = " ".join(["The customer accepts this service level agreement in full."] * 80)


def sla(dual: str, private: str) -> str:
    return f"""<html><body><div class="container"><h1>Leapswitch Service Level Agreement</h1>
<p>Last Updated: 26 February 2026</p><p>{FILLER}</p>
<h2>Commitment to Service Availability</h2><h3>Service Minimum Uptime</h3>
<table><tr><td>Dedicated Servers</td><td>99.9%</td></tr>
<tr><td>Power (Dual Power Servers)</td><td>{dual}</td></tr>
<tr><td>Private Network</td><td>{private}</td></tr></table>
<h2>Service Credits</h2><p>Credit requests must be raised within sixty (60) days.</p>
</div><div id="footer">Contact</div></body></html>"""


OLD, NEW = sla("99.95%", "99.95%"), sla("99.9%", "99.9%")
DAY, LATER = datetime.date(2026, 10, 9), datetime.date(2026, 11, 2)
NOW = datetime.datetime(2026, 11, 26, 12, tzinfo=datetime.UTC)
LIVE = pathlib.Path(config.source_material_dir()) / "published"


@pytest.fixture
def material(tmp_path, monkeypatch):
    monkeypatch.setenv("LEGALMIND_SOURCE_MATERIAL_DIR", str(tmp_path))
    return tmp_path


def _checked(db, hours_ago: float) -> None:
    db.execute(text(f'UPDATE "{config.assist_schema()}".knowledge_sources SET '
                    "last_checked_ok_at = :t WHERE status = 'CURRENT'"),
               {"t": NOW - datetime.timedelta(hours=hours_ago)})


def _two_slas(db) -> None:
    published.ingest(db, SLA_LS, OLD, read_on=DAY)
    published.ingest(db, SLA_LS, NEW, read_on=LATER)
    _checked(db, 1)


# ------------------------------------------------------------------ normaliser
def test_the_normaliser_folds_quotes_dashes_spaces_and_numbering_only():
    assert sc.normalise("All content \u2014 including \u201cX\u201d\u00a0and\u200b it") \
        == 'All content - including "X" and it'
    assert sc.normalise("4.2 Termination\n(a) by notice\n\u2022 bullet") \
        == "Termination by notice bullet"
    assert sc.normalise("30 days notice\n99.9% uptime") == "30 days notice 99.9% uptime"
    assert sc.normalise("Case Kept") != sc.normalise("case kept")


def test_the_matcher_is_exact_never_fuzzy():
    assert sc.holds("Fees are due \u2014 in advance.", "fees are due - in advance") is False
    assert sc.holds("Fees are due \u2014 in advance.", "Fees are due - in advance")
    assert not sc.holds("Fees are due in advance.", "Fees are due in advance!")
    assert not sc.holds("anything", "")


@pytest.mark.skipif(not (LIVE / "2026-11-02").exists(),
                    reason="source material not present (54.6)")
def test_the_real_tos_snapshots_differ_only_in_dashes_so_every_passage_is_the_same():
    """2026-10-09 vs 2026-11-02 (the 2026-10-31 template change): 169 of 171 blocks are
    byte-identical; the other two changed "—" to " - ". Normalised, every 10-09 passage
    is still in the 11-02 text — `wording_same`, never a false `changed`."""
    def blocks(day):
        return [t for _, t in published.extract((LIVE / day / "TOS-leapswitch.html")
                                                .read_text())]
    before, after = blocks("2026-10-09"), blocks("2026-11-02")
    assert len(set(before) - set(after)) == 2
    whole = "\n".join(after)
    assert all(sc.holds(whole, b) for b in before)


# --------------------------------------------------------------------- figures
def test_figures_are_a_closed_grammar_and_bare_numbers_are_not_figures():
    assert sc.figures("99.95% uptime, 5 per cent, thirty (30) calendar days, 24 hrs, "
                      "₹5,000 and INR 1,200.50") == [
        "99.95%", "5%", "30 day", "24 hour", "₹5000", "₹1200.5"]
    assert sc.figures("clause 4.2, 17 August 2026, invoice 10023, 3 servers") == []


#: prices, dates, clause numbers and plain business figures — none may block
NEGATIVE = [
    "The dedicated server is priced at ₹4,999 per month.",
    "Please sign by 30 November 2026.",
    "See clause 14.3 of the MSA for the limitation of liability.",
    "We can deliver 3 servers within 2 weeks.",
    "Our quote of ₹1,20,000 is valid until 15 December.",
    "Payment terms are net 30 days from invoice.",
    "The contract term is 36 months.",
    "Our 24x7 support desk answers within minutes.",
    "The order form lists 128 GB RAM and 2 x 960 GB SSD.",
    "Kindly refer to section 7 and Annexure 2.",
    "Version 3 of the draft is attached.",
    "We offer a 10% discount on an annual commitment.",
    "Rack space of 42U is reserved for you.",
    "Bandwidth is 1 Gbps unmetered.",
    "Invoices are raised on the 1st of each month.",
    "The setup fee is INR 5,000, one time.",
    "GST at 18% applies on all invoices.",
    "Your account manager will call within 2 days.",
    "Migration takes about 4 hours.",
    "The proposal is valid for 15 days.",
    "We have 12 data centres across India.",
    "Clause 9.1(b) is accepted as drafted.",
    "Please return the signed copy by 5 December.",
    "The pilot runs for 1 month at no charge.",
    "Our tier III facility in Mumbai hosts the servers.",
    "Rs. 2,500 is charged for each extra IP block.",
    "The renewal is due on 01/04/2027.",
    "We reviewed pages 4 to 9 of your paper.",
    "The PO number is 4500012345.",
    "Your 2 TB backup plan is included.",
    "Delivery within 7 working days of the PO.",
    "Our offices are closed on 25 December.",
    "The MSA dated 12 March 2025 continues.",
    "The 2nd annexure lists the hardware.",
    "We accept 50% advance and 50% on delivery.",
    "Prices exclude 18% GST.",
    "The server has 64 cores.",
    "Your quote reference is Q-2026-118.",
    "A 5% early-payment discount applies.",
    "We will share the draft in 3 days.",
    "Our team of 40 engineers supports you.",
    "The deposit is ₹25,000, refundable on exit as per the order form.",
    "Section 12 covers confidentiality.",
    "Call us on +91 22 1234 5678.",
    "The licence covers 25 users.",
    "Hardware warranty is 3 years from delivery.",
    "Clause 4.2 and clause 4.3 are unchanged.",
    "Two copies are attached for signature.",
    "The meeting is at 3 pm on 2 December.",
    "We need the signed PO within 10 days to hold the price.",
]


def test_a_negative_set_of_fifty_business_messages_never_blocks(db, material):
    _two_slas(db)
    assert len(NEGATIVE) == 50
    for message in NEGATIVE:
        found = sc.check_text(db, message, now=NOW)
        assert not any(p["blocks"] for p in found), (message, found)


# ------------------------------------------------------------ the incident replay
INCIDENT = ('As per our SLA, power uptime is 99.95% for dual-power servers. '
            'Our SLA says "*99.95% for Power (Dual-powered servers) and Private Network".')
REDRAFT = ('As per our SLA, power uptime is 99.9% for dual-power servers. '
           'Our SLA lists "Power (Dual Power Servers) | 99.9%".')


def test_the_old_power_figure_blocks_and_names_the_current_text(db, material):
    _two_slas(db)
    found = sc.check_text(db, "Leapswitch power uptime is 99.95% on dual-power servers.",
                          now=NOW)
    assert [p["code"] for p in found] == ["OLD_FIGURE"]
    assert found[0]["blocks"] and found[0]["figure"] == "99.95%"
    assert found[0]["current_wording"] == "Power (Dual Power Servers) | 99.9%"
    assert "Leapswitch Service Level Agreement as read on 09 Oct 2026" in found[0][
        "message"]                    # ingest alone never sets the page's own date


@pytest.mark.skipif(not (LIVE / "2026-11-02").exists(),
                    reason="source material not present (54.6)")
def test_incident_replay_on_the_real_stored_slas(db, material):
    """The real 2026-10-09 and 2026-11-02 Leapswitch SLA pages: the old dual-power
    figure and a quote from the old page both block, each named with the current
    wording; the same draft redrafted against the current text passes."""
    for day in ("2026-10-09", "2026-11-02"):
        published.ingest(db, SLA_LS, (LIVE / day / "SLA-leapswitch.html").read_text(),
                         read_on=datetime.date.fromisoformat(day))
    _checked(db, 1)
    found = sc.check_text(db, INCIDENT, now=NOW)
    assert [p["code"] for p in found] == ["OLD_FIGURE", "QUOTE_CHANGED"], found
    assert all(p["blocks"] for p in found)
    assert found[0]["current_wording"] == "Power (Dual Power Servers) | 99.9%"
    assert sc.check_text(db, REDRAFT, now=NOW) == []
    assert sc.check_text(db, INCIDENT, now=NOW) == found        # same inputs, same list


def test_a_quote_no_stored_version_holds_blocks_as_could_not_match(db, material):
    _two_slas(db)
    altered = 'Our SLA says "credit requests must be raised within ninety days of it".'
    found = sc.check_text(db, altered, now=NOW)
    assert [p["code"] for p in found] == ["QUOTE_NOT_MATCHED"] and found[0]["blocks"]
    assert "pasted quote" in found[0]["message"]


def test_a_figure_in_no_version_only_warns(db, material):
    _two_slas(db)
    found = sc.check_text(db, "Our network response time is 15 minutes.", now=NOW)
    assert [(p["code"], p["blocks"]) for p in found] == [("NO_SOURCE", False)]


def test_a_policy_not_rechecked_for_27_hours_blocks(db, material):
    _two_slas(db)
    fine = "Leapswitch power uptime is 99.9% on dual-power servers."
    assert sc.check_text(db, fine, now=NOW) == []
    _checked(db, 27)
    found = sc.check_text(db, fine, now=NOW)
    assert [p["code"] for p in found] == ["NOT_RECHECKED"] and found[0]["blocks"]


# --------------------------------------------------------- per-passage status
def _item(db, version_prefix: str, content: str):
    return db.execute(text(f"""
        SELECT k.id FROM "{config.assist_schema()}".knowledge_items k
          JOIN "{config.assist_schema()}".knowledge_sources s ON s.id = k.source_id
         WHERE s.version LIKE :v AND k.content = :c"""),
        {"v": f"{version_prefix}%", "c": content}).scalar_one()


def test_passage_status_in_force_wording_same_changed_and_unverifiable(db, material):
    _two_slas(db)
    old_power = _item(db, "2026-10-09", "Power (Dual Power Servers) | 99.95%")
    old_dedicated = _item(db, "2026-10-09", "Dedicated Servers | 99.9%")
    new_power = _item(db, "2026-11-02", "Power (Dual Power Servers) | 99.9%")
    status = {k: sc.passage_status(db, i, now=NOW)["status"]
              for k, i in (("new", new_power), ("same", old_dedicated),
                           ("changed", old_power))}
    assert status == {"new": sc.IN_FORCE, "same": sc.WORDING_SAME,
                      "changed": sc.CHANGED}
    changed = sc.passage_status(db, old_power, now=NOW)
    assert changed["current_wording"] == "Power (Dual Power Servers) | 99.9%"
    assert sc.passage_status(db, "00000000-0000-0000-0000-000000000000", now=NOW) is None
    # the names are the citation's own, never `knowledge_sources.status` words (AM-29)
    assert not {sc.IN_FORCE, sc.WORDING_SAME, sc.CHANGED, sc.UNVERIFIABLE} & {
        "CURRENT", "SUPERSEDED", "current", "stale", "unavailable"}


# ------------------------------------------------------------- refresh hardening
class _Resp(io.BytesIO):
    def __init__(self, body: bytes, url: str, status: int = 200):
        super().__init__(body)
        self.url, self.status = url, status
        self.headers = type("H", (), {"get_content_charset": lambda s: "utf-8"})()

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_a_php_302_chain_that_ends_200_is_live(monkeypatch):
    """`.php` → 302 → www → clean URL → 200: urllib follows it; the final page counts."""
    final = "https://www.leapswitch.com/terms-of-service"
    monkeypatch.setattr(published._OPENER, "open",
                        lambda req, timeout: _Resp(b"<h1>x</h1>", final))
    page = published.fetch(TOS_LS)
    assert (page.final_url, page.status) == (final, 200)


def test_a_dead_page_is_a_final_404_twice_with_a_browser_reprobe(monkeypatch):
    agents = []

    def opener(req, timeout):
        agents.append(req.get_header("User-agent"))
        raise urllib.error.HTTPError(TOS_LS.url, 404, "Not Found", {}, None)
    monkeypatch.setattr(published._OPENER, "open", opener)
    with pytest.raises(published.PageGone) as gone:
        published.fetch(TOS_LS)
    assert gone.value.status == 404
    assert agents == [published.HONEST_UA, published.BROWSER_UA]

    def blocked_then_ok(req, timeout):
        if req.get_header("User-agent") == published.HONEST_UA:
            raise urllib.error.HTTPError(TOS_LS.url, 403, "Forbidden", {}, None)
        return _Resp(b"<h1>x</h1>", TOS_LS.url)
    monkeypatch.setattr(published._OPENER, "open", blocked_then_ok)
    assert published.fetch(TOS_LS).status == 200           # a WAF, not a dead page

    def flaky(req, timeout):
        raise urllib.error.HTTPError(TOS_LS.url, 503, "Unavailable", {}, None)
    monkeypatch.setattr(published._OPENER, "open", flaky)
    with pytest.raises(urllib.error.HTTPError):             # transient, never "gone"
        published.fetch(TOS_LS)


def test_the_page_date_parses_or_is_none():
    assert published.page_updated_on([("p", "Last Updated: 17 August 2026")]) \
        == datetime.date(2026, 8, 17)
    assert published.page_updated_on([("p", "Last updated: February 5, 2026")]) \
        == datetime.date(2026, 2, 5)
    assert published.page_updated_on([("p", "Last Updated:")]) is None


@pytest.fixture
def sdb(engine):
    """Savepoints stand in for the refresh's own per-policy transactions."""
    conn = engine.connect()
    outer = conn.begin()
    s = sessionmaker(bind=conn, join_transaction_mode="create_savepoint")()
    yield s
    s.close()
    outer.rollback()
    conn.close()


def test_refresh_records_the_check_and_a_refused_page_alerts(sdb, material, monkeypatch):
    db = sdb
    events = []
    monkeypatch.setattr("legalmind.observability.log_event",
                        lambda name, **kw: events.append((name, kw)))

    def live(p):
        if p is not SLA_LS:
            raise OSError("not in this test")
        return published.Page(OLD, "https://www.leapswitch.com/service-level-agreement",
                              200)
    published.refresh(db, fetcher=live, read_on=DAY)
    row = db.execute(text(
        f'SELECT page_updated_on, last_checked_ok_at, final_url, http_status FROM '
        f'"{config.assist_schema()}".knowledge_sources WHERE source_type = :t'),
        {"t": SLA_LS.source_type}).one()
    assert row.page_updated_on == datetime.date(2026, 2, 26)
    assert row.last_checked_ok_at is not None and row.http_status == 200
    cut = OLD.replace(FILLER, " ".join(["Short."] * 320))

    def refused(p):
        if p is not SLA_LS:
            raise OSError("not in this test")
        return published.Page(cut, SLA_LS.url, 200)
    out = {r["policy"]: r for r in published.refresh(db, fetcher=refused, read_on=LATER)}
    assert "error" in out["SLA-leapswitch"]
    assert ("published_policy.refused", {"kind": "SLA-leapswitch",
                                         "error": "ValueError",
                                         "operational_failure": True}) in events
    again = db.execute(text(
        f'SELECT last_checked_ok_at FROM "{config.assist_schema()}".knowledge_sources '
        "WHERE source_type = :t AND status = 'CURRENT'"),
        {"t": SLA_LS.source_type}).scalar()
    assert again == row.last_checked_ok_at       # a refused page is no successful check
