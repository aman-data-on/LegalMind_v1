"""Render a Review's analysis as a portable file — PDF or DOCX.

Owner directive 2026-08-31 ("Export Report … PDF, DOCX") closes 49.12's open
formats question. Two properties are structural here:

* **One content model, two renderers.** ``build_export_model`` assembles the
  document once, from payloads already serialized under the caller's own
  permissions (``serialize_finding`` with the caller's ``legal_position`` flag,
  ``report_payload``). A field the API would omit for this caller — an internal
  legal position above all (LEGAL-02) — is therefore absent from the file too,
  and neither renderer can reintroduce it.
* **Counts, never a grade.** The model carries the same deliberate absences as
  the report endpoint: no risk score, no verdict, no percentage presented as a
  conclusion (36.10, F-8, F-9), and the F-9 sentence travels with the numbers.

Both renderers use libraries already in the ingestion stack (pymupdf,
python-docx) — no new dependency (rule 19).
"""

from __future__ import annotations

import html
import io
import re
from dataclasses import dataclass
from string import capwords
from typing import Any

# Fixed rendering order for classification counts — attention first. A rendering
# order, not a severity model: Tier-1 states are legally equivalent (DESIGN.md).
_COUNT_ORDER = (
    "DEVIATION", "MISSING", "CONFLICT", "UNABLE_TO_EVALUATE",
    "AMBIGUOUS", "UNRESOLVED", "MATCH",
)

# The reader's words — the same the workspace shows (frontend `lib/labels.ts`), so the
# file and the screen never disagree (owner, 2026-10-22: "well structured, as a user").
_STAGE = {
    "SUPERSEDED": "Superseded — a newer version has been reviewed",
    "ANALYSING": "Being analysed",
    "ANALYSIS_FAILED": "The analysis could not be completed",
    "WAITING_FOR_CLARIFICATION": "Waiting for the client's clarification",
    "REOPENED": "Reopened — points need a decision again",
    "WITH_LEGAL": "With Legal",
    "NOT_SENT": "Not yet sent for review",
    "CONTRACT_DECISION_PENDING":
        "Every point is decided — the decision on the contract is next",
    "COMPLETE": "Review complete",
    "NO_ISSUES": "No point needs a decision",
}
_DECIDED = {
    "ACCEPT_DEVIATION": "Accepted as an exception",
    "REQUIRE_COMPANY_STANDARD": "Change requested — our wording to send",
    "APPROVE_CUSTOMIZATION": "Customised clause approved",
    "REJECT": "Must change — not acceptable as written",
    "REQUEST_CLARIFICATION": "Awaiting the client's clarification",
    "NOT_APPLICABLE_TO_CONTRACT": "Not applicable to this contract",
}
_OUTCOME = {
    "SIGN_AS_IS": "Sign as is",
    "SIGN_WITH_CHANGES": "Sign after our changes",
    "DO_NOT_SIGN": "Do not sign",
    "ON_HOLD": "On hold — waiting for the client",
}
_ANALYSIS = {"ACCEPTABLE": "Matches our standard",
             "REQUIRES_MODIFICATION": "Change needed",
             "MISSING": "Missing",
             "NEEDS_DECISION": "Needs a decision"}
_TO_SEND = {"REQUIRE_COMPANY_STANDARD", "REJECT"}
#: A document type in words (the same labels the screens use, `documentTypes.ts`).
_TYPE_WORDS = {"MSA": "Master Services Agreement", "NDA": "Non-Disclosure Agreement",
               "TOS": "Terms of Service", "SLA": "Service Level Agreement",
               "DPA": "Data Processing Agreement", "AUP": "Acceptable Use Policy",
               "PRIVACY_POLICY": "Privacy Policy",
               "ORDER_FORM": "Purchase order / order form",
               "AMENDMENT": "Amendment / Addendum",
               "PARTNER_AGREEMENT": "Partner Agreement",
               "VENDOR_AGREEMENT": "Vendor Agreement",
               "DISTRIBUTION_AGREEMENT": "Distribution Agreement",
               "OTHER": "Other agreement"}


#: the report's key (owner, 2026-10-27), in the order the points are listed
_KEY = (
    ("NEEDS_DECISION", "Legal rules on it before anything is sent — the contract is "
                       "unclear or conflicting here, or touches a position we do not "
                       "negotiate."),
    ("REQUIRES_MODIFICATION", "The contract differs from our standard; we ask the "
                              "client to change it."),
    ("MISSING", "A clause our standard expects is not in the contract; we ask for it "
                "to be added."),
)


@dataclass(frozen=True)
class Block:
    """One content block. ``kind``: h1 | h2 | h3 | p | kv | quote | note | bullet |
    table (``rows``: the header first) | change (one tracked change: ``text`` is the
    printed line, ``rows[0]`` = clause, kind, removed, added, "read" or "")."""
    kind: str
    text: str
    label: str = ""
    rows: tuple[tuple[str, ...], ...] = ()


def _value_text(value: Any) -> str:
    """A stored JSON value as plain text — the server's keys and values verbatim,
    never interpreted (rule 12). Used where no plain statement was built."""
    if value is None:
        return "Not recorded"
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_value_text(v)}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(_value_text(v) for v in value)
    return str(value)


_PRESENCE = {"PRESENT": "Required in the contract", "ABSENT": "Not in the contract",
             "WAIVED": "Waived by the contract"}
_UNITS = {"DAYS": "days", "MONTHS": "months", "YEARS": "years", "WEEKS": "weeks",
          "PERCENT": "percent", "HOURS": "hours"}


def _plain(value: Any, *, standard: bool = False) -> str:
    """A stored value said in words for the shapes the evaluators write — presence,
    allowed values, an amount and its unit; anything else stays verbatim (rule 12:
    nothing interpreted beyond naming what is stored)."""
    if isinstance(value, dict):
        if set(value) <= {"presence"} and value.get("presence") in _PRESENCE:
            word = _PRESENCE[value["presence"]]
            return "Required" if standard and value["presence"] == "PRESENT" else word
        if isinstance(value.get("allowed_values"), list) and value["allowed_values"]:
            names = [str(v).replace("_", " ").title() for v in value["allowed_values"]]
            return " or ".join(names)
        amount = value.get("cap_value", value.get("preferred"))
        unit = value.get("cap_unit", value.get("unit"))
        if amount is not None and unit:
            return f"{amount} {_UNITS.get(str(unit), str(unit).lower())}"
    return _value_text(value)


_FAMILY = re.compile(r"§31\.\d+ ([A-Z_]+) position")


def _why_not(row: dict[str, Any]) -> str:
    """Why a standard was not measured, in a reader's words — the run's own reason
    (AM-61) mapped by its recorded shape, never re-decided; anything else verbatim."""
    reason, outcome = str(row.get("reason") or ""), row.get("outcome")
    if outcome in ("SAME_POSITION", "SAME_TOPIC"):
        return "Measured once, through another standard on the same point"
    family = _FAMILY.search(reason)
    if family:
        kind = family.group(1).replace("_", " ").lower()
        return f"Written for {kind}s — not this type of contract"
    if "not_applicable_to" in reason:
        return "Our standards exclude this type of contract"
    if reason.startswith("not confirmed in the document"):
        return "Not in this contract, and not expected for its type"
    other = re.match(r"another document type's (?:position|standard) \(([A-Z_]+)\)",
                     reason)
    if other:
        kind = _TYPE_WORDS.get(other.group(1), other.group(1).title())
        return f"Belongs to a {kind} — not raised on this type of contract"
    if "fixed-term commitment" in reason and "states no committed term" in reason:
        return "Applies only to a fixed-term commitment; this contract states none"
    if "non-fixed-term" in reason:
        return "Applies only where no fixed term is committed; this contract commits one"
    # never an internal reference in a reader's reason: "(AM-152)", rule codes
    return _short(re.sub(r"\s*\((?:AM|AB)-[^)]*\)", "", reason), 110)


def _heading_like(title: Any) -> bool:
    """A real heading — "Facility provider", "LIMITATION OF LIABILITY" — never a sentence
    the parser kept as a title ("Unavailability caused by misuse of the service by the
    Customer;", "50 Mbps dedicated bandwidth is included …")."""
    text = str(title or "").strip()
    return (0 < len(text.split()) <= 7 and text[-1:] not in ",;:"
            and not re.match(r"\d", text))


def _position(finding: dict[str, Any], said: str) -> str:
    """Our standard in words: a presence position ("Required") is said as the position
    itself — the standard's own description after its heading ("Changes / cancellation —
    should follow …" → "Should follow …") — so a reader sees WHAT we require."""
    if said != "Required":
        return said
    text = str((finding.get("requirement") or {}).get("description") or "").strip()
    text = text.split(" — ", 1)[-1].strip() if " — " in text else text
    return _short(text[:1].upper() + text[1:], 220) if text else said


def _evidence_location(e: dict[str, Any]) -> str:
    parts: list[str] = []
    if e.get("section_number"):
        parts.append(f"§{e['section_number']}")
    if e.get("section_title"):
        parts.append(str(e["section_title"]))
    if e.get("page_number") is not None:
        parts.append(f"p.{e['page_number']}")
    return " · ".join(parts) if parts else "location not recorded"


def _clause(e: dict[str, Any] | None) -> str:
    """Clause and page only — the short form a table cell can carry."""
    if not e:
        return "Not in the contract"
    parts = [f"§{e['section_number']}"] if e.get("section_number") else []
    if e.get("page_number") is not None:
        parts.append(f"p.{e['page_number']}")
    return " · ".join(parts) or "location not recorded"


def _day(iso: str | None) -> str:
    if not iso:
        return ""
    from datetime import datetime
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y")
    except ValueError:
        return iso[:10]


#: "(§25.1)", "(Constitution §24.4, §25.1)": our rulebook's section numbers mean nothing
#: to a reader from another department (owner, 2026-10-27: "layman terms"); the audit
#: record and the Findings screen keep them
_REFS = re.compile(r"\s*\((?:Legal\s+)?(?:Constitution\s*)?§[^)]*\)")


def _no_refs(text: str) -> str:
    return _REFS.sub("", text)


def _short(text: str, n: int) -> str:
    """Cut at a word, never mid-word, and say so with an ellipsis."""
    text = " ".join((text or "").split())
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0] + " …"


def _title(finding: dict[str, Any]) -> str:
    from legalmind.domain.document_types import DOCUMENT_TYPES
    from legalmind.evaluation.user_status import _requirement_title
    requirement = finding.get("requirement") or {}
    return _requirement_title(requirement.get("code"), requirement.get("name"),
                              {t.upper() for t in DOCUMENT_TYPES})


def _next_steps(stage: str | None, outcome: str | None, progress: dict[str, Any],
                owner: str, reviewer: str, to_send: int) -> list[str]:
    """What happens next and who does it — derived from where the review stands, never
    a legal judgement of its own (rule 13)."""
    open_points = progress.get("to_decide", 0)
    asked = progress.get("clarification", 0)
    if stage == "COMPLETE" and outcome == "SIGN_WITH_CHANGES":
        return [f"{owner} sends the {to_send} change{'s' * (to_send != 1)} listed below "
                "to the client.",
                "When the client returns a revised version, upload it to LegalMind — it "
                "is reviewed as a new version, point by point."]
    if stage == "COMPLETE" and outcome == "SIGN_AS_IS":
        return [f"{owner} may take the contract to signature; the reviewer found nothing "
                "that must change."]
    if stage == "COMPLETE" and outcome == "DO_NOT_SIGN":
        return [f"{owner} informs the client that the contract cannot be signed as "
                "drafted; the reasons are below."]
    if stage == "CONTRACT_DECISION_PENDING" and outcome == "ON_HOLD":
        return [f"Waiting for the client; {reviewer} records the decision on the "
                "contract when they reply."]
    if stage == "CONTRACT_DECISION_PENDING":
        return [f"{reviewer} records the decision on the contract — every point is "
                "decided."]
    if stage == "WAITING_FOR_CLARIFICATION":
        return [f"{owner} obtains the client's answer on {asked} point"
                f"{'s' * (asked != 1)}.", f"{reviewer} then decides."]
    if stage in ("WITH_LEGAL", "REOPENED"):
        steps = [f"{reviewer} decides the {open_points} open point"
                 f"{'s' * (open_points != 1)}."]
        if asked:
            steps.append(f"{owner} obtains the client's answer on {asked} point"
                         f"{'s' * (asked != 1)}.")
        return steps
    if stage == "NOT_SENT":
        return [f"{owner} sends the contract to a reviewer — {open_points} point"
                f"{'s' * (open_points != 1)} need{'s' * (open_points == 1)} a decision."]
    if stage == "SUPERSEDED":
        return ["Nothing — a newer version of this contract has been reviewed."]
    return []


def build_export_model(*, contract: dict[str, Any], version: dict[str, Any],
                       review: dict[str, Any], report: dict[str, Any],
                       findings: list[dict[str, Any]],
                       exported_at: str,
                       angles: dict[str, Any] | None = None) -> list[Block]:
    """The review as a reader needs it (owner, 2026-10-22; second research round): a
    short summary and the decision, what happens next and who does it, the money, the
    changes to send in order of importance, what is still open, what was accepted and
    why, the detail of what still needs action, then the appendices and the audit record.
    Every field comes from payloads serialized under the caller's own permissions, so
    what the API omits for this caller (LEGAL-02) is absent here too — never blanked."""
    progress = report.get("progress") or {}
    outcome = report.get("contract_outcome") or {}
    current = (outcome.get("history") or [None])[-1]
    decisions = {d["finding_id"]: d for d in report.get("decisions") or []}
    cases = {i["finding_id"]: i.get("case") or {} for i in
             ((angles or {}).get("legal") or {}).get("items") or []}
    stage = progress.get("stage")
    owner = contract.get("owner_name") or "The contract's owner"
    reviewer = ((progress.get("assignee") or {}).get("name")
                or (current or {}).get("decided_by_name") or "A Legal reviewer")

    # one row per point the reader sees — the fold the screens use (AM-179)
    seen: set[str] = set()
    points = []
    for f in findings:
        group = f.get("group_id") or f["id"]
        if group not in seen:
            seen.add(group)
            points.append(f)

    def decided(f):
        return decisions.get(f["id"])

    def first_evidence(f):
        return (f.get("evidence") or [None])[0]

    def clause_of(f):
        return _clause(first_evidence(f)) if first_evidence(f) else "—"

    matches = [f for f in points
               if f.get("user_status") == "ACCEPTABLE" and not decided(f)]
    # worst first — a person decides, then what must change, then what is missing —
    # and one number per point across every table and the detail
    severity = {"NEEDS_DECISION": 0, "REQUIRES_MODIFICATION": 1, "MISSING": 2}
    numbered = {f["id"]: n for n, f in enumerate(sorted(
        (f for f in points if f not in matches),
        key=lambda f: severity.get(str(f.get("user_status")), 3)), start=1)}

    def name(f):
        return f"{numbered[f['id']]}. {_title(f)}" if f["id"] in numbered else _title(f)

    # the changes to send, most important first: what must change, then what we ask
    to_send = sorted(
        (f for f in points if decided(f) and decided(f)["decision_type"] in _TO_SEND),
        key=lambda f: (decided(f)["decision_type"] != "REJECT", numbered.get(f["id"], 0)))
    pending = sorted((f for f in points if f.get("status") in
                      ("DECISION_REQUIRED", "AWAITING_CLARIFICATION")),
                     key=lambda f: numbered.get(f["id"], 0))
    closed = [f for f in points if decided(f)
              and decided(f)["decision_type"] not in _TO_SEND | {"REQUEST_CLARIFICATION"}]

    # ---- the cover: what this is about -------------------------------------------
    blocks: list[Block] = [Block("h1", contract.get("name") or "Review report")]
    if contract.get("client_name"):
        blocks.append(Block("kv", contract["client_name"], label="Client"))
    blocks.append(Block("kv", f"v{version.get('version_number')}"
                              f" — {version.get('original_filename') or ''}".rstrip(" —"),
                        label="Document"))
    declared, analysed = contract.get("contract_type"), report.get("analysed_as")
    words = _TYPE_WORDS.get
    kind = (words(declared, declared) if declared
            else f"{words(analysed, analysed)} (read from its "
                 f"{'content' if report.get('analysed_from') == 'content' else 'title'})"
            if analysed
            else "not declared")
    blocks.append(Block("kv", kind, label="Document type"))
    if contract.get("owner_name"):
        blocks.append(Block("kv", contract["owner_name"], label="Contract owner"))
    if progress.get("assignee"):
        blocks.append(Block("kv", progress["assignee"]["name"], label="Reviewer"))
    analysed = _day(review.get("completed_at") or review.get("created_at"))
    prepared = _day(exported_at)
    blocks.append(Block("kv", f"analysed {analysed} · report prepared {prepared}",
                        label="Dates"))

    # ---- 1. summary: three sentences, all from the record ----------------------------
    blocks.append(Block("h2", "Summary"))
    # the reader's first question — can we sign? — answered first, in AM-160's own line
    advice = _no_refs(str((angles or {}).get("recommendation") or ""))
    if advice:
        blocks.append(Block("kv", advice.removeprefix("Recommendation: "),
                            label="Recommendation"))
    marked = (angles or {}).get("client_changes")
    changed_clauses = {c["clause"] for g in (marked or {}).get("sections", ())
                       for c in g["changes"] if c["clause"]}
    if marked and marked["changes"]:
        blocks.append(Block("p", f"This copy carries the client's tracked changes: "
                                 f"{marked['changes']} changes to {marked['clauses']} "
                                 f"clauses. {marked['unmeasured']} of those clauses "
                                 "are not checked by any of our standard terms — read "
                                 "them under “The client's changes”."))
    counts = report.get("user_status_counts") or {}
    total = sum(counts.values())
    if total:
        # one sentence a reader can act on: what matches, and what needs action, worst
        # first (owner, 2026-10-27: "a lot of information that is not needed")
        act = total - counts.get("ACCEPTABLE", 0)
        said = ", ".join(f"{_ANALYSIS[w].lower()} ({counts[w]})" for w in
                         ("NEEDS_DECISION", "REQUIRES_MODIFICATION", "MISSING")
                         if counts.get(w))   # the chips' own words, so nothing disagrees
        whose = f"{contract['owner_name']}'s contract" if contract.get("owner_name") \
            else "The contract"
        match = counts.get("ACCEPTABLE", 0)
        parts = ([f"{match} match"] if match else []) + (
            [f"{act} need{'s' * (act == 1)} action: {said}"] if act else [])
        blocks.append(Block("p", f"{whose} was checked against our standard terms "
                                 f"on {total} point{'s' * (total != 1)}: "
                                 + "; ".join(parts) + "."))
    by_type = progress.get("decided_by_type") or {}
    if progress.get("required") and any(by_type.values()):
        said = ", ".join(f"{n} {_DECIDED.get(t, t).lower()}"
                         for t, n in by_type.items() if n)
        open_ = progress.get("to_decide", 0) + progress.get("clarification", 0)
        blocks.append(Block("p", f"{progress['required']} point"
                                 f"{'s' * (progress['required'] != 1)} needed a decision"
                                 + (f": {said}" if said else "")
                                 + (f"; {open_} still open" if open_ else "") + "."))
    decision_shown = current and stage in ("COMPLETE", "CONTRACT_DECISION_PENDING")
    steps = _next_steps(stage, (current or {}).get("outcome"), progress, owner, reviewer,
                        len(to_send))
    if stage and not decision_shown and not steps:   # the next step already says it
        blocks.append(Block("p", _STAGE.get(stage, stage) + "."))
    if decision_shown:
        said = _OUTCOME.get(current["outcome"], current["outcome"])
        who = current.get("decided_by_name") or "a reviewer"
        blocks.append(Block(
            "kv", f"{said} — {who}, {_day(current.get('decided_at'))}: "
                  f"“{current.get('justification')}”", label="Decision on this contract"))
    if stage == "COMPLETE":
        blocks.append(Block("note", "A complete review is not approval to sign: it "
                                    "records what the reviewer decided."))

    # ---- 2. next steps -----------------------------------------------------------------
    if steps:
        blocks.append(Block("h2", "Next steps"))
        for n, step in enumerate(steps, start=1):
            blocks.append(Block("p", f"{n}. {step}"))

    # ---- 3. key commercial terms (evidence-backed figures only, AM-156) -----------
    commercial = (angles or {}).get("commercial") or {}
    money = [p for p in (angles or {}).get("business") or [] if p.get("money")]
    if commercial.get("fee_text") or commercial.get("term_text") or money:
        blocks.append(Block("h2", "Key commercial terms"))
        several = "more than one" in str(commercial.get("missing") or "")
        if several:
            blocks.append(Block("kv", "Several charges — see the price schedule",
                                label="Fees"))
        elif commercial.get("fee_text"):
            blocks.append(Block("kv", _short(commercial["fee_text"], 160), label="Fee"))
        if commercial.get("term_text"):
            blocks.append(Block("kv", _short(commercial["term_text"], 160), label="Term"))
        if commercial.get("committed_value_text"):
            gst = ", excluding GST" if commercial.get("excludes_gst") else ""
            blocks.append(Block("kv", f"{commercial['committed_value_text']}{gst}",
                                label="Committed value"))
        elif commercial.get("missing"):
            blocks.append(Block("kv", f"Not shown — {commercial['missing']}",
                                label="Committed value"))
        for p in money:
            blocks.append(Block("bullet", f"{p.get('headline')}: {p['money']}"))

    # ---- 4. at a glance ------------------------------------------------------------
    rows: list[tuple[str, ...]] = [("What was decided", "Points")]
    rows += [(_DECIDED.get(t, t), str(n)) for t, n in by_type.items() if n]
    if progress.get("to_decide"):
        rows.append(("Still to decide", str(progress["to_decide"])))
    if progress.get("clarification"):
        rows.append(("Awaiting the client's clarification",
                     str(progress["clarification"])))
    if any(by_type.values()):           # "Still to decide 12" alone repeats the summary
        blocks.append(Block("h2", "At a glance"))
        blocks.append(Block("table", "", rows=tuple(rows)))

    # ---- 5. changes to send, most important first ---------------------------------
    if to_send:
        blocks.append(Block("h2", f"Changes to send to the client ({len(to_send)})"))
        rows = [("Point", "Change", "Clause", "The contract says", "Our standard", "Why")]
        for f in to_send:
            case = cases.get(f["id"], {})
            standard = case.get("standard") or {}
            ours = standard.get("value") or (
                _plain(f["evaluations"][0]["expected_value"], standard=True)
                if f.get("evaluations") and "expected_value" in f["evaluations"][0]
                else "")
            if (standard.get("source") or {}).get("quote"):
                quote = _short(standard["source"]["quote"], 220)
                ours = f"{ours} — “{quote}”".lstrip(" —")
            evidence = first_evidence(f)
            says = ((case.get("contract") or {}).get("quote")
                    or (evidence or {}).get("content"))
            must = decided(f)["decision_type"] == "REJECT"
            rows.append((name(f), "Must change" if must else "Requested",
                         _clause(evidence) if evidence else "—",
                         _short(says, 240) if says else "Missing — to be added",
                         _position(f, ours) if ours else "—",
                         decided(f).get("justification") or ""))
        blocks.append(Block("table", "", rows=tuple(rows)))

    # ---- 6. still to decide ----------------------------------------------------------
    if pending:
        blocks.append(Block("h2", f"Still to decide ({len(pending)})"))
        # the key, once: what each word means and who acts (owner, 2026-10-27: a reader
        # understands the report in two minutes)
        shown = {str(f.get("user_status")) for f in pending}
        for status, meaning in _KEY:
            if status in shown:
                blocks.append(Block("kv", meaning, label=_ANALYSIS[status]))
        from legalmind.api.angles import LEGAL_REVIEW_WORDS  # the step most points carry
        blocks.append(Block("note", "A reviewer decides every point below before the "
                                    "contract is signed; unless a point says otherwise, "
                                    "the step is to " + LEGAL_REVIEW_WORDS.lower() + "."))
        # the step for each point is in the detail below; here, what and where
        rows = [("Point", "Status", "Clause", "What the contract says")]
        for f in pending:
            case = cases.get(f["id"], {})
            asking = f.get("status") == "AWAITING_CLARIFICATION"
            rows.append((name(f), "Awaiting the client's answer" if asking
                         else _ANALYSIS.get(str(f.get("user_status")), ""),
                         clause_of(f), case.get("gap") or ""))
        blocks.append(Block("table", "", rows=tuple(rows)))

    # ---- 7. accepted / not applicable ------------------------------------------------
    if closed:
        blocks.append(Block("h2", "Accepted as exceptions or not applicable "
                                  f"({len(closed)})"))
        rows = [("Point", "Clause", "Decision", "By, on", "Reason")]
        for f in closed:
            d = decided(f)
            rows.append((name(f), clause_of(f),
                         _DECIDED.get(d["decision_type"], d["decision_type"]),
                         f"{d.get('decided_by_name') or ''}, {_day(d.get('decided_at'))}",
                         d.get("justification") or ""))
        blocks.append(Block("table", "", rows=tuple(rows)))

    # ---- 7b. what the client changed (owner, 2026-10-27) ----------------------------
    # every tracked change of a marked-up contract, by section, beside the standard that
    # measured its clause — or said plainly that none covers it and a person reads it
    if marked:
        changed = marked["clauses"]
        plural = "s" * (changed != 1)
        blocks.append(Block("h2", f"The client's changes ({changed} clause{plural})"))
        noted = marked.get("notes") or 0
        blocks.append(Block("p", f"The client's lawyers made {marked['changes']} "
                                 f"changes to {changed} clauses"
                                 + (f" and left {noted} note{'s' * (noted != 1)}"
                                    if noted else "") + ". Our standard terms "
                                 f"checked {marked['measured']} of those clauses (the "
                                 f"points above). The other {marked['unmeasured']} "
                                 "changed in ways none of our standard terms check — "
                                 "please read them."))
        for group in marked["sections"]:
            title = f" {group['title'].capitalize()}" if group["title"] else ""
            head = (f"§{group['section']}{title}" if group["section"]
                    else "Unnumbered text")
            many = len(group["changes"])
            unread = sum(not c["measured_by"] for c in group["changes"])
            said = (f"{many} change{'s' * (many != 1)}" if many
                    else "No wording changed") + (
                f", {unread} to read" if unread else "") + "." + (
                " Checked against our terms on: " + ", ".join(group["measured_by"]) + "."
                if group["measured_by"] else "")
            if group["notes"]:
                said += f" {len(group['notes'])} note{'s' * (len(group['notes']) != 1)}" \
                        " from the client."
            blocks.append(Block("h3", head))
            blocks.append(Block("kv", said, label="The difference"))
            for note in group["notes"]:      # their words, beside the clause they are on
                blocks.append(Block("quote", note["text"],
                                    label=f"Their note on {note['clause'] or 'this part'}"
                                          + (f" ({note['author']})" if note["author"]
                                             else "")))
            for c in group["changes"]:
                removed, added = _short(c["removed"], 260), _short(c["added"], 260)
                quoted = (f"“{removed}” → “{added}”" if c["kind"] == "Changed"
                          else f"“{added or removed}”")
                where = c["clause"] or "—"
                # the file prints the line; the screen draws it as a redline (rows)
                blocks.append(Block(
                    "change", f"{where} · {c['kind']}: {quoted}"
                              + ("" if c["measured_by"] else " (please read)"),
                    # "read" tags a change only where it tells changes apart: in a
                    # section where some were checked and some were not
                    rows=((where, c["kind"], removed, added,
                           "read" if not c["measured_by"] and unread < many else ""),)))

    # ---- 8. matches ------------------------------------------------------------------
    if matches:
        blocks.append(Block("h2", f"Matches our standards ({len(matches)})"))
        for f in matches:
            where = _clause(first_evidence(f)) if first_evidence(f) else ""
            blocks.append(Block("bullet", f"{_title(f)} — {where}".rstrip(" —")))

    # ---- 9. detail of what still needs action ----------------------------------------
    detail = to_send + [f for f in pending if f not in to_send]
    if not findings:
        blocks.append(Block("p", "This Review produced no Findings."))
    if detail:
        blocks.append(Block("h2", "The points that need action, in detail"))
    for f in detail:
        case = cases.get(f["id"], {})
        d = decided(f)
        blocks.append(Block("h3", name(f)))
        analysis = _ANALYSIS.get(str(f.get("user_status")), str(f.get("user_status")))
        state = _DECIDED.get(d["decision_type"], d["decision_type"]) if d else analysis
        blocks.append(Block("kv", state, label="Status"))
        gap = case.get("gap")
        if gap:
            blocks.append(Block("kv", gap, label="The difference"))
        evaluations = f.get("evaluations") or []
        lead = evaluations[0] if evaluations else {}
        standard = case.get("standard") or {}
        ours = standard.get("value") or (_plain(lead["expected_value"], standard=True)
                                         if "expected_value" in lead else "")
        if ours and not (gap and ours in gap):          # never said twice
            blocks.append(Block("kv", _position(f, ours), label="Our standard"))
        if (standard.get("source") or {}).get("quote"):
            blocks.append(Block("quote", standard["source"]["quote"],
                                label=standard["source"].get("label", "")))
        theirs = sorted({str(e.get("section_number")) for e in f.get("evidence") or []
                         if str(e.get("section_number")) in changed_clauses})
        if theirs:          # the client's change is why this point reads as it does
            blocks.append(Block("kv", "the client changed " + ", ".join(theirs)
                                      + " — see “The client's changes”",
                                label="Changed by the client"))
        if case.get("recommendation") and not d:
            blocks.append(Block("kv", _no_refs(case["recommendation"]),
                                label="Recommended"))
        if d:
            again = (f" (version {d['version_number']})"
                     if d.get("version_number", 1) > 1 else "")
            blocks.append(Block("kv", f"{d.get('decided_by_name') or 'a reviewer'}, "
                                      f"{_day(d.get('decided_at'))}: "
                                      f"“{d.get('justification')}”{again}",
                                label="Decided by"))
        # the contract's own words where there is a clause; else the value it states,
        # unless it only says "absent" — the difference already does
        evidence = f.get("evidence") or []
        for e in evidence[:2]:
            blocks.append(Block("quote", _short(str(e.get("content") or ""), 400),
                                label=_evidence_location(e)))
        actual = lead.get("actual_value") or {}
        absent = "ABSENT" in (actual.get("presence"), actual.get("cap_status"))
        if not evidence and actual and not absent:
            blocks.append(Block("kv", _plain(actual), label="Found in the contract"))
        elif not evidence and not gap:
            blocks.append(Block("p", "The contract has no clause on this point."))

    # ---- appendices ------------------------------------------------------------------
    unmatched = report.get("unmatched_provisions_detail") or []
    if unmatched:
        blocks.append(Block("h2", "Appendix — clauses no standard covers "
                                  f"({len(unmatched)})"))
        blocks.append(Block("note",
                            "Not a problem by themselves: no company standard covers "
                            "these clauses, so there is nothing to compare them with. "
                            "Listed for a person to read."))
        # one line per contract section — a person sees where they are without
        # reading every clause here (each stays readable in the workspace)
        # in document order, a new group each time the section changes — an annexure
        # that restarts its numbering is its own group, never merged with the order's
        runs: list[tuple[str, dict[str, Any]]] = []
        for item in unmatched:
            number = str(item.get("section_number") or "")
            top = number.split(".")[0] if number else "—"
            if not runs or runs[-1][0] != top:
                runs.append((top, {"n": 0, "title": "", "pages": set()}))
            group = runs[-1][1]
            group["n"] += 1
            if number == top and _heading_like(item.get("section_title")):
                group["title"] = str(item["section_title"])
            if item.get("page_number") is not None:
                group["pages"].add(item["page_number"])
        # untitled single items side by side (a schedule's numbered list) are one line:
        # fourteen "§2 — 1 clause" rows tell a reader nothing
        merged: list[tuple[str, dict[str, Any]]] = []
        for top, group in runs:
            loose = not group["title"] and group["n"] == 1
            if loose and merged and merged[-1][0] == "list":
                merged[-1][1]["n"] += 1
                merged[-1][1]["pages"] |= group["pages"]
            elif loose and top != "—":
                merged.append(("list", {**group, "pages": set(group["pages"]),
                                        "first": top}))
            else:
                merged.append((top, group))
        for top, group in merged:
            if top == "list" and group["n"] == 1:
                top = group["first"]               # one item keeps its own number
            pages = sorted(group["pages"])
            where = (f"p.{pages[0]}" if len(pages) == 1
                     else f"p.{pages[0]}-{pages[-1]}" if pages else "")
            head = ("Numbered items without headings" if top == "list"
                    else f"§{top}" if top != "—" else "Unnumbered text")
            title = f" {capwords(group['title'].lower())}" if group["title"] else ""
            count = f"{group['n']} clause{'s' * (group['n'] != 1)}"
            blocks.append(Block("bullet", f"{head}{title} — {count}"
                                          + (f", {where}" if where else "")))

    # what was measured and what was not, with the run's own reason (AM-61)
    applicability = (report.get("coverage") or {}).get("applicability") or []
    skipped = [r for r in applicability if r.get("outcome") != "APPLIED"]
    if skipped:
        from legalmind.domain.document_types import DOCUMENT_TYPES
        from legalmind.evaluation.user_status import _requirement_title
        types = {t.upper() for t in DOCUMENT_TYPES}
        blocks.append(Block("h2", "Appendix — standards not measured on this contract "
                                  f"({len(skipped)})"))
        # grouped by reason, each standard named once — a 54-row table repeating "Written
        # for vendor agreements" is read by nobody
        by_reason: dict[str, list[str]] = {}
        for r in skipped:
            title = _requirement_title(r.get("code"), None, types)
            names = by_reason.setdefault(_why_not(r), [])
            if title not in names:
                names.append(title)
        measured = [("Why not measured", "Standards")] + [
            (f"{why} ({len(names)})", ", ".join(names))
            for why, names in sorted(by_reason.items(), key=lambda kv: -len(kv[1]))]
        blocks.append(Block("table", "", rows=tuple(measured)))

    blocks.append(Block("h2", "Appendix — audit record"))
    blocks.append(Block("kv", str(review.get("status") or ""), label="Review lifecycle"))
    blocks.append(Block("kv", str(review.get("configuration_snapshot_id") or ""),
                        label="Configuration snapshot"))
    coverage = report.get("coverage") or {}
    blocks.append(Block("kv", f"{coverage.get('requirements_with_findings', 0)} of "
                              f"{coverage.get('requirements_in_snapshot', 0)} "
                              "requirements produced findings", label="Coverage"))
    engine = report.get("classification_counts") or {}
    order = [c for c in _COUNT_ORDER if engine.get(c)] + sorted(
        c for c in engine if c not in _COUNT_ORDER and engine[c])
    if order:
        blocks.append(Block("kv", ", ".join(f"{c} {engine[c]}" for c in order),
                            label="Engine classifications"))
    blocks.append(Block("kv", exported_at[:16].replace("T", " ") + " UTC",
                        label="Exported"))
    blocks.append(Block(
        "note", "Generated by LegalMind. This report never grades the document: whether "
                "a difference is acceptable is a Legal Decision made by an authorised "
                "person. Contents reflect what the exporting account is authorized to "
                "see; fields withheld from that account are absent from this file."))
    return blocks


#: the frame every page carries — what the file is, that it is confidential, where
#: the reader is (a report is forwarded and printed; owner, 2026-10-22)
_CONFIDENTIAL = "Confidential · internal legal review"   # the PDF font has no em dash


def _title_of(blocks: list[Block]) -> str:
    """Every page's header: the contract, whose it is, what this is (owner, 2026-10-23:
    "mention the contract owner name, easy to review")."""
    name = next((b.text for b in blocks if b.kind == "h1"), "")
    owner = next((b.text for b in blocks if b.kind == "kv"
                  and b.label == "Contract owner"), "")
    head = f"{name} · owner {owner}" if name and owner else name
    return f"{head} · contract review report" if head else "Contract review report"


# --------------------------------------------------------------------------
# DOCX
# --------------------------------------------------------------------------
def render_docx(blocks: list[Block]) -> bytes:
    from docx import Document

    doc = Document()
    section = doc.sections[0]
    section.header.paragraphs[0].text = _title_of(blocks)
    footer = section.footer.paragraphs[0]
    footer.add_run(f"{_CONFIDENTIAL} · Page ")
    _field(footer, "PAGE")
    footer.add_run(" of ")
    _field(footer, "NUMPAGES")
    for block in blocks:
        if block.kind == "h1":
            doc.add_heading(block.text, level=0)
        elif block.kind == "h2":
            doc.add_heading(block.text, level=1)
        elif block.kind == "h3":
            doc.add_heading(block.text, level=2)
        elif block.kind == "kv":
            paragraph = doc.add_paragraph()
            paragraph.add_run(f"{block.label}: ").bold = True
            paragraph.add_run(block.text)
        elif block.kind == "quote":
            if block.label:
                doc.add_paragraph(block.label).runs[0].italic = True
            doc.add_paragraph(block.text, style="Intense Quote")
        elif block.kind == "note":
            doc.add_paragraph(block.text).runs[0].italic = True
        elif block.kind == "bullet":
            doc.add_paragraph(block.text, style="List Bullet")
        elif block.kind == "table" and block.rows:
            table = doc.add_table(rows=len(block.rows), cols=len(block.rows[0]))
            table.style = "Table Grid"
            for r, row in enumerate(block.rows):
                for c, value in enumerate(row):
                    cell = table.rows[r].cells[c]
                    cell.text = value
                    if r == 0:                      # the header row reads as one
                        for run in cell.paragraphs[0].runs:
                            run.bold = True
            doc.add_paragraph()
        else:
            doc.add_paragraph(block.text)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _field(paragraph: Any, code: str) -> None:
    """A Word field (PAGE, NUMPAGES) — Word fills in the number when it lays out."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), code)
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "1"
    run.append(text)
    field.append(run)
    paragraph._p.append(field)


# --------------------------------------------------------------------------
# PDF — pymupdf Story: HTML assembled from escaped text only.
# --------------------------------------------------------------------------
_PDF_CSS = """
body { font-family: sans-serif; font-size: 10pt; color: #111; }
h1 { font-size: 18pt; margin: 0 0 6pt; }
h2 { font-size: 13pt; margin: 14pt 0 4pt; }
h3 { font-size: 11pt; margin: 10pt 0 3pt; }
p { margin: 2pt 0; }
blockquote { margin: 2pt 0 6pt 12pt; font-style: italic; color: #333; }
.note { font-style: italic; color: #444; margin: 6pt 0; }
.loc { color: #555; font-size: 8.5pt; margin: 4pt 0 0; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 8pt; }
th, td { border: 0.5pt solid #999; padding: 3pt 4pt; font-size: 8.5pt;
  vertical-align: top; text-align: left; }
th { border-bottom: 1.2pt solid #555; }   /* no fill: the PDF engine repeats fills */
.bullet { margin: 1pt 0 1pt 10pt; }
"""


def _blocks_to_html(blocks: list[Block]) -> str:
    parts: list[str] = []
    for block in blocks:
        text = html.escape(block.text)
        label = html.escape(block.label)
        if block.kind in ("h1", "h2", "h3"):
            parts.append(f"<{block.kind}>{text}</{block.kind}>")
        elif block.kind == "kv":
            parts.append(f"<p><b>{label}:</b> {text}</p>")
        elif block.kind == "quote":
            if label:
                parts.append(f'<p class="loc">{label}</p>')
            parts.append(f"<blockquote>{text}</blockquote>")
        elif block.kind == "note":
            parts.append(f'<p class="note">{text}</p>')
        elif block.kind == "bullet":
            parts.append(f'<p class="bullet">• {text}</p>')
        elif block.kind == "table" and block.rows:
            head, *body = block.rows
            parts.append("<table><tr>" + "".join(
                f"<th>{html.escape(h)}</th>" for h in head) + "</tr>" + "".join(
                "<tr>" + "".join(f"<td>{html.escape(v)}</td>" for v in row) + "</tr>"
                for row in body) + "</table>")
        else:
            parts.append(f"<p>{text}</p>")
    return "<body>" + "".join(parts) + "</body>"


def render_pdf(blocks: list[Block]) -> bytes:
    import pymupdf

    story = pymupdf.Story(html=_blocks_to_html(blocks), user_css=_PDF_CSS)
    buffer = io.BytesIO()
    writer = pymupdf.DocumentWriter(buffer)
    page_rect = pymupdf.paper_rect("a4")
    # Rect + tuple is pymupdf's inset arithmetic, not sequence concatenation.
    content_rect = page_rect + (36, 40, -36, -40)  # noqa: RUF005
    more = True
    while more:
        device = writer.begin_page(page_rect)
        more, _ = story.place(content_rect)
        story.draw(device)
        writer.end_page()
    writer.close()
    # the frame, stamped once the page count is known
    pdf = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")
    title, total = _title_of(blocks), pdf.page_count
    for index in range(total):
        number, page = index + 1, pdf[index]
        width, height = page.rect.width, page.rect.height
        page.insert_text((36, 24), title, fontsize=7.5, color=(0.35, 0.35, 0.35))
        page.insert_text((36, height - 18), f"{_CONFIDENTIAL} · Page {number} of {total}",
                         fontsize=7.5, color=(0.35, 0.35, 0.35))
        page.draw_line((36, 30), (width - 36, 30), color=(0.8, 0.8, 0.8), width=0.5)
    out = pdf.tobytes()
    pdf.close()
    return out


RENDERERS = {"pdf": render_pdf, "docx": render_docx}
MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": ("application/vnd.openxmlformats-officedocument"
             ".wordprocessingml.document"),
}
