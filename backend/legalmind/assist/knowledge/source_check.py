"""Source integrity B1 — is the policy text that leaves LegalMind still what the website
says? (`AM-130` extension; `AM-273`/`AB-150` send gate.) Deterministic: no model, no
embedding, no fuzzy match (rule 15) — exact substrings of the stored versions of the
published policies (`published.py`), after one shared normaliser.

Three facts, each about STORED TEXT, never about the answer (rule 12) and never a legal
judgement (rule 7):

* a cited policy record's passage — ``in_force`` (its own version is the one in force),
  ``wording_same`` (a newer version holds it verbatim), ``changed`` (a newer version does
  not), ``unverifiable`` (no version can be read). These names are a citation's own and
  share none with `knowledge_sources.status` or the answer state (`AM-29`).
* a policy FIGURE (%, duration, ₹) in a sentence naming a policy term — found in the
  version in force (fine), only in an older version (``OLD_FIGURE``, blocks), or in none
  (``NO_SOURCE``, a warning: it cannot be shown to be a policy figure at all).
* a QUOTED passage attributed to a policy — found in force, only in an older version, or
  in no stored version (blocks: "could not match the pasted quote").

A policy not confirmed against the live page in `RECHECK_HOURS` is ``NOT_RECHECKED``:
we cannot rule out "changed since" (owner, 2026-11-26), so it blocks too.
"""
from __future__ import annotations

import dataclasses
import datetime
import re
import unicodedata
from collections.abc import Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist.knowledge import published

IN_FORCE, WORDING_SAME, CHANGED, UNVERIFIABLE = (
    "in_force", "wording_same", "changed", "unverifiable")
RECHECK_HOURS = 26

# ------------------------------------------------------------------ normaliser
_ZERO_WIDTH = dict.fromkeys([0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD])
#: curly and prime quotes to straight ones; every dash, hyphen and minus to "-"
_QUOTES = str.maketrans({**dict.fromkeys(map(chr, (0x2018, 0x2019, 0x201A, 0x201B,
                                                   0x2032)), "'"),
                         **dict.fromkeys(map(chr, (0x201C, 0x201D, 0x201E, 0x201F,
                                                   0x2033)), '"'),
                         **dict.fromkeys(map(chr, (0x2010, 0x2011, 0x2012, 0x2013,
                                                   0x2014, 0x2015, 0x2212)), "-")})
#: a bullet or a clause number opening a line: "•", "-", "*", "(a)", "(iv)", "4.2",
#: "4.2.1.", "12)", "a." — never a figure ("99.9% uptime" keeps its digits)
_PREFIX = re.compile(r"^(?:[•▪◦·*-]|\((?:[a-z]{1,3}|\d{1,3})\)|\d{1,3}(?:\.\d{1,3})+\.?"
                     r"|\d{1,3}[.)]|[a-z][.)])\s+", re.I)


def normalise(s: str) -> str:
    """The one comparison form, for stored and pasted text alike (`M7`): NFKC, no
    zero-width or soft hyphen, straight quotes, every dash a hyphen, bullets and clause
    numbers off each line's start, whitespace collapsed. Case and digits are kept."""
    s = unicodedata.normalize("NFKC", s or "").translate(_ZERO_WIDTH).translate(_QUOTES)
    lines = (_PREFIX.sub("", line.strip(), count=1) for line in s.splitlines())
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def holds(haystack: str, quote: str) -> bool:
    """``quote`` appears verbatim in ``haystack`` after normalising both. Exact only."""
    q = normalise(quote)
    return bool(q) and q in normalise(haystack)


# ------------------------------------------------------------- stored versions
@dataclasses.dataclass(frozen=True)
class Version:
    id: str
    source_type: str
    title: str
    effective_from: datetime.date | None
    page_updated_on: datetime.date | None
    last_checked_ok_at: datetime.datetime | None
    sha256: str
    items: tuple[tuple[str, str, str], ...]     # (item id, breadcrumb, content)

    @property
    def brand(self) -> str:
        return published.BY_SOURCE_TYPE[self.source_type].brand

    @property
    def text(self) -> str:
        return "\n".join(c for _, _, c in self.items)

    def dated(self) -> str:
        """The version's date for a LegalMind reader: the page's own date when it gives
        one, else the day LegalMind first read it — labelled which (N3)."""
        if self.page_updated_on:
            return f"updated {self.page_updated_on:%d %b %Y}"
        return f"as read on {self.effective_from:%d %b %Y}" if self.effective_from \
            else "date unknown"


def load(db: DBSession) -> list[Version]:
    """Every stored version of the eight published policies, items in page order."""
    s = config.assist_schema()
    rows = db.execute(text(f"""
        SELECT ks.id::text AS sid, ks.source_type, ks.title, ks.effective_from,
               ks.page_updated_on, ks.last_checked_ok_at, ks.file_sha256,
               k.id::text AS iid,
               k.breadcrumb, k.content
          FROM "{s}".knowledge_sources ks
          JOIN "{s}".knowledge_items k ON k.source_id = ks.id AND k.kind = 'PARAGRAPH'
         WHERE ks.source_type = ANY(:t) ORDER BY ks.effective_from, ks.id, k.ordinal"""),
        {"t": list(published.SOURCE_TYPES)}).all()
    out: dict[str, Version] = {}
    for r in rows:
        v = out.get(r.sid) or Version(r.sid, r.source_type, r.title, r.effective_from,
                                      r.page_updated_on, r.last_checked_ok_at,
                                      r.file_sha256 or "",
                                      ())
        out[r.sid] = dataclasses.replace(
            v, items=(*v.items, (r.iid, r.breadcrumb or "", r.content or "")))
    return list(out.values())


def in_force(db: DBSession, versions: list[Version], source_type: str,
             on: datetime.date) -> Version | None:
    """The stored version of one policy in force on ``on``.

    TODO(lawyer-p1): `published.version_on` (the A→B→A-safe periods table, `AM-477`)
    owns this; until that branch merges this falls back to the CURRENT row, which is
    the same answer for ``on`` = today — the only date Batch 1 asks about."""
    version_on = getattr(published, "version_on", None)
    if version_on is not None:
        pinned = version_on(db, source_type, on)["pinned"]
        wanted = str(pinned["source_id"]) if pinned else None
    else:
        wanted = db.execute(text(
            f'SELECT id::text FROM "{config.assist_schema()}".knowledge_sources '
            "WHERE source_type = :t AND status = 'CURRENT'"), {"t": source_type}).scalar()
    return next((v for v in versions if v.id == wanted), None)


def not_rechecked(v: Version, now: datetime.datetime) -> bool:
    return v.last_checked_ok_at is None or (
        now - v.last_checked_ok_at > datetime.timedelta(hours=RECHECK_HOURS))


def _rechecked_words(v: Version) -> str:
    if v.last_checked_ok_at is None:
        return f"The live {v.title} has not been checked yet. Ask Legal before sending."
    return (f"The live {v.title} has not been re-checked since "
            f"{v.last_checked_ok_at:%d %b %Y %H:%M} UTC.")


# --------------------------------------------------------- passage status (ledger)
def passage_status(db: DBSession, knowledge_item_id, *,
                   now: datetime.datetime | None = None,
                   versions: list[Version] | None = None) -> dict | None:
    """A cited record's passage against the version in force today, or None when the
    record is not a published policy's (the Constitution has its own status)."""
    now = now or datetime.datetime.now(datetime.UTC)
    versions = load(db) if versions is None else versions
    pinned = next(((v, b, c) for v in versions for i, b, c in v.items
                   if i == str(knowledge_item_id)), None)
    if pinned is None:
        return None
    own, crumb, content = pinned
    current = in_force(db, versions, own.source_type, now.date())
    if current is None:
        return {"status": UNVERIFIABLE, "policy": own.title}
    out: dict[str, str | None] = {"policy": own.title, "version": current.dated()}
    if not_rechecked(current, now):
        out["not_rechecked_since"] = (current.last_checked_ok_at.date().isoformat()
                                      if current.last_checked_ok_at else None)
    if current.id == own.id:
        return {**out, "status": IN_FORCE}
    if holds(current.text, content):
        return {**out, "status": WORDING_SAME}
    return {**out, "status": CHANGED, "since": own.dated(),
            "current_wording": _same_place(current, crumb, content)}


def _same_place(v: Version, crumb: str, like: str | None = None) -> str | None:
    """The version's passage at the same heading path — the one reading like ``like``
    but for its figures, else the first sharing one of its specific terms, else None
    (never a neighbour guessed) — shown as "the current text says", never compared."""
    at = [c for _, b, c in v.items if b == crumb]
    if like:
        def shape(x: str) -> str:
            return re.sub(r"[\d.,%₹]+", "#", normalise(x))
        at = ([c for c in at if shape(c) == shape(like)]
              or [c for c in at if _terms(c) & _terms(like) & set(_SPECIFIC)])
    return at[0] if at else None


# ------------------------------------------------------------------ figures
#: the policy terms a sentence must name for its figures to be checked (critique M5);
#: "specific" ones must be shared, so an uptime figure of one product never vouches
#: for another's (Object Storage 99.95% is not Power 99.95%)
_SPECIFIC = {"power": r"power", "network": r"network",
             "response time": r"response\s+time",
             "notice": r"notice", "refund": r"refund\w*", "termination": r"terminat\w*",
             "service credit": r"service\s+credits?"}
_GENERIC = {"uptime": r"uptime", "availability": r"availab\w*",
            "sla": r"sla|service\s+level"}
_TERM = re.compile("|".join(f"(?P<{k.replace(' ', '_')}>\\b(?:{v})\\b)"
                            for k, v in {**_SPECIFIC, **_GENERIC}.items()), re.I)
_FIGURE = re.compile(
    r"(?P<pct>\d+(?:\.\d+)?)\s?(?:%|per\s?cent\b)"
    r"|\(?(?P<n>\d+)\)?\s*(?:calendar\s+|business\s+|working\s+|clear\s+)?"
    r"(?P<unit>hours?|hrs?|days?|minutes?|mins?|weeks?|months?|years?)\b"
    r"|(?:₹|\bINR|\bRs\.?)\s?(?P<inr>\d[\d,]*(?:\.\d+)?)", re.I)
_UNIT = {"hr": "hour", "hrs": "hour", "min": "minute", "mins": "minute"}
_SENTENCE = re.compile(r"(?<=[.!?;])\s+|\n+")


def _terms(s: str) -> set[str]:
    return {k.replace("_", " ") for m in _TERM.finditer(s or "")
            for k, v in m.groupdict().items() if v}


def figures(s: str) -> list[str]:
    """Each figure of the closed grammar, in one canonical form: "99.95%", "30 day",
    "₹5000". A bare number (a price without ₹, a date, a clause number) is none."""
    out = []
    for m in _FIGURE.finditer(s or ""):
        if m["pct"]:
            out.append(f"{float(m['pct']):g}%")
        elif m["n"]:
            unit = m["unit"].lower()
            unit = _UNIT.get(unit, unit.rstrip("s") if unit != "hrs" else "hour")
            out.append(f"{int(m['n'])} {unit}")
        else:
            out.append(f"₹{float(m['inr'].replace(',', '')):g}")
    return out


def policy_figures(body: str) -> list[str]:
    """The figures the check reads: those in a sentence naming a policy term."""
    return sorted({f for s in map(normalise, sentences(body)) if _terms(s)
                   for f in figures(s)})


def sentences(s: str) -> list[str]:
    return [x.strip() for x in _SENTENCE.split(s or "") if x.strip()]


def _shares(wanted: set[str], have: set[str]) -> bool:
    specific = wanted & set(_SPECIFIC)
    return bool(specific & have) if specific else bool(wanted & have)


# ------------------------------------------------------------------- quotes
_QUOTED = re.compile(r'"([^"]{20,})"')
_POLICY_NAMED = re.compile(r"\b(?:terms\s+of\s+service|tos|terms\s+and\s+conditions|"
                           r"sla|service\s+level|acceptable\s+us\w*|aup|privacy\s+policy)"
                           r"\b", re.I)


# ------------------------------------------------------------------- the check
def check_text(db: DBSession, body: str, *, now: datetime.datetime | None = None,
               versions: list[Version] | None = None) -> list[dict]:
    """Every problem with the policy figures and quoted policy passages in ``body``, in
    the order they appear. Same inputs → same list. Each problem: ``code``, ``blocks``,
    ``message`` and, where known, ``policy``, ``figure``/``quote`` and
    ``current_wording``."""
    now = now or datetime.datetime.now(datetime.UTC)
    versions = load(db) if versions is None else versions
    brands = published.reader_brands(body) or {p.brand for p in published.POLICIES}
    mine = [v for v in versions if v.brand in brands]
    force = {t: in_force(db, versions, t, now.date())
             for t in {v.source_type for v in mine}}
    current = [v for v in force.values() if v is not None]
    older = [v for v in mine if v not in current]
    out: list[dict] = []
    stale_named: set[str] = set()
    said: set[str] = set()

    def touched(v: Version) -> None:
        if not_rechecked(v, now) and v.id not in stale_named:
            stale_named.add(v.id)
            out.append({"code": "NOT_RECHECKED", "blocks": True, "policy": v.title,
                        "message": _rechecked_words(v)})

    for sentence in map(normalise, sentences(body)):
        wanted = _terms(sentence)
        if not wanted:
            continue
        for fig in dict.fromkeys(figures(sentence)):
            if fig in said:             # one problem per figure per text
                continue
            said.add(fig)
            hit = next((v for v in current if _has(v, fig, wanted)), None)
            if hit is not None:
                touched(hit)
                continue
            old = next((v for v in reversed(older) if _has(v, fig, wanted)), None)
            if old is None:
                out.append({"code": "NO_SOURCE", "blocks": False, "figure": fig,
                            "message": f"No source attached: {fig} is not in any stored "
                                       "version of our published policies. Check it "
                                       "before sending."})
                continue
            now_v = force.get(old.source_type)
            crumb, was = next((b, c) for _, b, c in old.items if fig in figures(c)
                              and _shares(wanted, _terms(f"{b} {c}")))
            says = _same_place(now_v, crumb, was) if now_v else None
            out.append({"code": "OLD_FIGURE", "blocks": True, "figure": fig,
                        "policy": old.title, "current_wording": says,
                        "message": f"Old figure: {fig} is from the {old.title} "
                                   f"{old.dated()}; the current text "
                                   + (f"says: “{says}”." if says else
                                      "no longer has it.")})
    norm = normalise(body)
    for m in _QUOTED.finditer(norm):
        quote = m[1]
        if not _POLICY_NAMED.search(norm[max(0, m.start() - 200):m.start()]
                                    + norm[m.end():m.end() + 100]):
            continue
        if any(holds(v.text, quote) for v in current):
            for v in current:
                if holds(v.text, quote):
                    touched(v)
            continue
        old = next((v for v in reversed(older) if holds(v.text, quote)), None)
        short = quote if len(quote) <= 90 else quote[:87] + "…"
        if old is None:
            out.append({"code": "QUOTE_NOT_MATCHED", "blocks": True, "quote": short,
                        "message": f"Could not match the pasted quote “{short}” to any "
                                   "stored version of our published policies. Quote "
                                   "the current text instead."})
            continue
        now_v = force.get(old.source_type)
        crumb, was = next(((b, c) for _, b, c in old.items if holds(c, quote[:60])),
                          ("", quote))
        says = _same_place(now_v, crumb, was) if now_v else None
        out.append({"code": "QUOTE_CHANGED", "blocks": True, "quote": short,
                    "policy": old.title, "current_wording": says,
                    "message": f"Changed: “{short}” is from the {old.title} "
                               f"{old.dated()}; the current text "
                               + (f"says: “{says}”." if says else "no longer has it.")})
    return out


def _has(v: Version, fig: str, wanted: set[str]) -> bool:
    return any(fig in figures(c) and _shares(wanted, _terms(f"{b} {c}"))
               for _, b, c in v.items)


def cited_problems(db: DBSession, fetched: Iterable, *, client: bool,
                   now: datetime.datetime | None = None,
                   versions: list[Version] | None = None) -> list[dict]:
    """Problems with an answer's cited records (`ledger.Fetched`, each with its
    ``passage`` status): a changed or unverifiable policy passage, a policy not
    re-checked, and — on a copy meant for the client (``client``) — any internal
    record (Constitution, house view, company position: LEGAL-02)."""
    out = []
    for f in fetched:
        cls = f.key[:1]
        p = getattr(f, "passage", None)
        if client and (cls in "HP" or (cls == "C" and p is None)):
            out.append({"code": "INTERNAL_SOURCE", "blocks": True, "key": f.key,
                        "message": "This answer draws on internal company guidance, "
                                   "which never goes to a client. Re-draft from the "
                                   "published policies or the contract only."})
            continue
        if p is None:
            continue
        if p["status"] in (CHANGED, UNVERIFIABLE):
            out.append({"code": p["status"].upper(), "blocks": True, "key": f.key,
                        "policy": p["policy"],
                        "current_wording": p.get("current_wording"),
                        "message": (f"Changed: the cited {p['policy']} passage "
                                    f"({p.get('since')}) is not in the current "
                                    "text." if p["status"] == CHANGED else
                                    f"The cited {p['policy']} passage could not be "
                                    "found in any stored version.")})
        if "not_rechecked_since" in p:
            out.append({"code": "NOT_RECHECKED", "blocks": True, "key": f.key,
                        "policy": p["policy"],
                        "message": f"The live {p['policy']} has not been re-checked "
                                   + (f"since {p['not_rechecked_since']}."
                                      if p["not_rechecked_since"] else "yet.")})
    return out


#: what never leaves in a client copy (S6, LEGAL-02): a SHA-256, a UUID, a ledger key
_INTERNAL_ID = re.compile(r"\b[0-9a-f]{64}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
                          r"[0-9a-f]{4}-[0-9a-f]{12}\b|\[(?:[CHPSDU]\d+|\d+)\]", re.I)


def leak_problems(body: str) -> list[dict]:
    found = sorted({m[0] for m in _INTERNAL_ID.finditer(body or "")})
    return [{"code": "INTERNAL_ID", "blocks": True,
             "message": "Internal references (source markers, record ids or hashes) are "
                        f"in the text: {', '.join(found[:5])}. Remove them before "
                        "sending."}] if found else []


def in_force_hashes(db: DBSession, versions: list[Version],
                    now: datetime.datetime | None = None) -> dict[str, str]:
    """Each policy's version in force now, by SHA-256 — what an audit row pins."""
    today = (now or datetime.datetime.now(datetime.UTC)).date()
    out = {}
    for t in published.SOURCE_TYPES:
        v = in_force(db, versions, t, today)
        if v is not None:
            out[t] = v.sha256
    return out
