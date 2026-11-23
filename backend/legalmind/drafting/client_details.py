"""Client details before drafting (batch 7, AB-220) — Legal's ten-point list for sales.

Before an MSA or NDA is generated, Legal asks sales to collect from the client: 1 the
agreement date · 2 the company's registered email (as on the GST certificate) · 3 its
registered address (as on the GST certificate) · 4 its CIN (Indian companies only) · 5 its
nature of business · 6 the signatory's name · 7 designation · 8 official email · 9 the GST
number · 10 the GST certificate.

**One record (spec §5).** Items 2–10 are facts about the client, typed or confirmed ONCE
on the client record; item 1 is this deal's answer. On a gated template the contract's
client fields are read from the record at the time of asking (`effective_answers`), never
from a copy in the deal's answers, so the profile and the contract cannot disagree.

`checklist` says which items are present, runs the free checks and reports the tick;
`require_ready` is the server gate generation calls; `read_certificate` reads a GST
certificate's own labelled lines (text layer, else the existing OCR path) for a person to
confirm — nothing read is ever saved without a person.

Nothing here is a legal rule or a company fact (rules 7, 21): every value was typed or
uploaded by a person, the checks compare those values with each other and with public code
tables, and a check that only informs (state, Act wording, legal name) never blocks.

**India rule (spec §1):** the CIN, GSTIN and certificate — and the tick, which is about
the GST certificate — are required when the client's country is India or not set (fail
closed); a country set to anything else makes them "not needed".
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from legalmind.api.errors import Conflict
from legalmind.api.schemas import _LEGAL_ID_SHAPES
from legalmind.db import models as M
from legalmind.drafting import model as model_

#: the templates the gate holds (spec §2: the MSA and any future NDA)
GATED_DOC_TYPES = frozenset({"MSA", "NDA"})
#: the record's fields the tick attests — a change to any of them (or the file) clears it
VERIFIED_FIELDS = ("registered_email", "registered_office", "cin_or_llpin", "gstin",
                   "legal_name")            # the tick's own words name the legal name too
#: a variable's role → the record field(s) it is read from on a gated template. The
#: business question is found by `business_var` (Legal's fill-in label), not by role.
RECORD_ROLES = {"counterparty_name": ("legal_name", "name"),
                "counterparty_registered_office": ("registered_office",),
                "counterparty_cin": ("cin_or_llpin",),
                "counterparty_gstin": ("gstin",),
                "counterparty_pan": ("pan",),
                "counterparty_signatory_name": ("signatory_name",),
                "counterparty_signatory_designation": ("signatory_designation",),
                "counterparty_signatory_email": ("signatory_email",),
                # round 2 (lead polish 4): their authority to sign is a client fact
                "counterparty_authority": ("authority_reference",)}

_CODES_FILE = Path(__file__).resolve().parents[2] / "config" / "gst_state_codes.json"
#: GST state code → the state names an address may carry (`config/gst_state_codes.json`)
STATE_CODES: dict[str, list[str]] = json.loads(
    _CODES_FILE.read_text(encoding="utf-8"))["codes"]
_CONFIG = Path(__file__).resolve().parents[2] / "config"
_COUNTRIES_FILE = _CONFIG / "iso3166_non_india.json"
#: every ISO 3166-1 country other than India, by its names and codes, normalised
#: (`config/iso3166_non_india.json`, its source recorded there)
ABROAD: dict[str, str] = {}
for _c in json.loads(_COUNTRIES_FILE.read_text(encoding="utf-8"))["countries"]:
    for _w in (*_c["names"], _c["alpha_2"], _c["alpha_3"]):
        ABROAD[" ".join(re.sub(r"[^0-9a-z]+", " ", _w.casefold()).split())] = \
            _c["names"][0]
#: "NA" is far more often "not applicable" than Namibia's code: fail closed (by name only)
del ABROAD["na"]
_BUSINESS = re.compile(r"\b(?:customer|client)(?:['\u2019]s)?\b.*\bbusiness\b", re.I)


class ClientDetailsIncomplete(Conflict):
    code = "CLIENT_DETAILS_INCOMPLETE"

    def __init__(self, missing: list[dict[str, Any]], unverified: bool) -> None:
        super().__init__("The contract cannot be made yet: the client's details are not "
                         "complete and checked.")
        self.extra = {"missing": missing, "unverified": unverified}


def _norm(text: Any) -> str:
    return " ".join(re.sub(r"[^0-9a-z]+", " ", str(text or "").casefold()).split())


def gated(tv: M.TemplateVersion) -> bool:
    return tv.doc_type in GATED_DOC_TYPES


def country_abroad(country: str | None) -> str | None:
    """The country a Country field names when it is clearly NOT India — exactly one ISO
    3166-1 name or code and no mention of India — else None (D2: fail closed; blank, a
    typo, a city, "N/A" or anything naming India keeps the India rules)."""
    text = _norm(country)
    if not text or re.search(r"\b(?:india|bharat)\b", text):
        return None
    return ABROAD.get(text)


def is_india(client: M.Counterparty | None) -> bool:
    return client is None or country_abroad(client.country) is None


def _var(variables: list[Mapping[str, Any]], role: str) -> Mapping[str, Any] | None:
    return next((v for v in variables if model_.role(v) == role), None)


def business_var(variables: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """The "Customer's line of business" question: its role, else Legal's label for the
    recital B blank (the live MSA's fill-in field)."""
    return _var(variables, "counterparty_business") or next(
        (v for v in variables if _BUSINESS.search(model_.label(v))), None)


def record_keys(tv: M.TemplateVersion) -> dict[str, tuple[str, ...]]:
    """This template's question keys that are client facts on a gated template → the
    record field(s) each is read from. Empty on any other template."""
    if not gated(tv):
        return {}
    out = {v["key"]: RECORD_ROLES[model_.role(v)] for v in tv.variables or []
           if model_.role(v) in RECORD_ROLES and "locked_value" not in v}
    if (b := business_var(tv.variables or [])) is not None:
        out[b["key"]] = ("line_of_business",)
    return out


def effective_answers(tv: M.TemplateVersion, answers: Mapping[str, Any],
                      client: M.Counterparty | None) -> dict[str, Any]:
    """The answers the contract is made from: on a gated template every client fact is the
    record's current value (absent when the record has none, so it is asked, never kept
    from an older copy); any other template, the answers as given."""
    keys = record_keys(tv)
    out = {k: v for k, v in answers.items() if k not in keys}
    for key, fields in keys.items():
        value = next(filter(None, ((getattr(client, f, None) or "").strip()
                                   for f in fields)), None) if client else None
        if value:
            out[key] = value
    return out


def state_codes(address: str) -> set[str]:
    """The GST codes of the state an address names — the LAST state named, as an Indian
    address ends with its state ("…, Delhi Road, Pune, Maharashtra" is Maharashtra)."""
    text = _norm(address.replace("&", " and "))
    found: list[tuple[int, str]] = []
    for code, names in STATE_CODES.items():
        for name in names:
            for m in re.finditer(rf"\b{re.escape(_norm(name))}\b", text):
                found.append((m.end(), code))
    if not found:
        return set()
    last = max(end for end, _ in found)
    return {code for end, code in found if end == last}


def state_name(code: str) -> str | None:
    names = STATE_CODES.get(code)
    return names[0] if names else None


def _shape_ok(field: str, value: str) -> bool:
    return bool(_LEGAL_ID_SHAPES[field][0].fullmatch(value))


def _record_items(client: M.Counterparty | None) -> list[dict[str, Any]]:
    """Items 2–10, from the record."""
    india = is_india(client)

    def rec(field: str) -> str:
        return (getattr(client, field, None) or "").strip() if client else ""

    def item(n: int, key: str, field: str, value: str, needed: bool = True,
             problem: str | None = None) -> dict[str, Any]:
        status = ("not_needed" if not needed else "missing" if not value
                  else "fix" if problem else "done")
        return {"n": n, "key": key, "status": status, "source": "profile",
                "profile_field": field, **({"value": value} if value and needed else {}),
                **({"problem": problem} if status == "fix" else {})}

    cin, gstin = rec("cin_or_llpin").upper(), rec("gstin").upper()
    pan = rec("pan").upper()
    gst_problem = ("bad_format" if gstin and not _shape_ok("gstin", gstin)
                   else "pan_bad_format" if pan and not _shape_ok("pan", pan)
                   else "pan_mismatch" if pan and gstin[2:12] != pan else None)
    certificate = (client.gst_certificate or {}) if client else {}
    return [
        item(2, "registered_email", "registered_email", rec("registered_email")),
        item(3, "registered_office", "registered_office", rec("registered_office")),
        item(4, "cin", "cin_or_llpin", cin, india,
             "bad_format" if cin and not _shape_ok("cin_or_llpin", cin) else None),
        item(5, "business", "line_of_business", rec("line_of_business")),
        item(6, "signatory_name", "signatory_name", rec("signatory_name")),
        item(7, "signatory_designation", "signatory_designation",
             rec("signatory_designation")),
        item(8, "signatory_email", "signatory_email", rec("signatory_email")),
        item(9, "gstin", "gstin", gstin, india, gst_problem),
        item(10, "gst_certificate", "gst_certificate", certificate.get("filename", ""),
             india),
    ]


def missing_count(client: M.Counterparty) -> int:
    """Items 2–10 still to add or fix — the client list's "3 details to add"."""
    return sum(i["status"] in ("missing", "fix") for i in _record_items(client))


#: what a certificate's read value fills on the record (the PAN is derived from the GSTIN)
READ_FIELDS = ("gstin", "pan", "legal_name", "registered_office")


def reads(client: M.Counterparty | None) -> list[dict[str, str]]:
    """Each value read from the current certificate against the record: ``fill`` (the
    record has none — shown pre-filled until a person confirms), ``differs`` (the record
    says something else — "Certificate says X"), ``same``."""
    read = ((client.gst_certificate or {}).get("read") or {}) if client else {}
    out = []
    for field in READ_FIELDS:
        if not read.get(field) or client is None:
            continue
        have = (getattr(client, field, None) or "").strip()
        state = ("fill" if not have else "same" if _norm(have) == _norm(read[field])
                 else "differs")
        out.append({"field": field, "value": read[field], "state": state})
    return out


def confirm_reads(client: M.Counterparty) -> dict[str, str]:
    """The tick confirms what is still shown as read and unconfirmed (review change 2):
    each ``fill`` value is written to the record; the fields AND values go to the audit
    (D7), the PAN included."""
    shown = [r for r in reads(client) if r["state"] == "fill"]
    for r in shown:
        setattr(client, r["field"], r["value"])
    return {r["field"]: r["value"] for r in shown}


def record_gaps(client: M.Counterparty) -> list[int]:
    """The items the tick attests (2, 3, 4, 9, 10) still missing or to fix — and 0 for a
    legal name not recorded (D5: the tick's words name the legal name)."""
    gaps = [i["n"] for i in _record_items(client)
            if i["n"] in (2, 3, 4, 9, 10) and i["status"] in ("missing", "fix")]
    return gaps if (client.legal_name or "").strip() else [0, *gaps]


def checklist(tv: M.TemplateVersion, answers: Mapping[str, Any],
              client: M.Counterparty | None,
              verified_by_name: str | None = None) -> dict[str, Any]:
    """The ten items, each ``done`` / ``missing`` / ``not_needed`` / ``fix`` with where it
    comes from (``deal`` — the question's key — or ``profile`` — the record's field),
    the warnings, the tick and ``ready`` (what the gate asks)."""
    if not gated(tv):
        return {"applies": False, "ready": True, "items": [], "warnings": []}
    date = _var(tv.variables or [], "effective_date")
    value = str(answers.get(date["key"]) or "").strip() if date else ""
    items = [{"n": 1, "key": "agreement_date", "status": "done" if value else "missing",
              "source": "deal", **({"question": date["key"]} if date else {}),
              **({"value": value} if value else {})}, *_record_items(client)]
    india = is_india(client)
    rec = {i["key"]: i.get("value", "") for i in items}
    certificate = (client.gst_certificate or {}) if client else {}
    read = certificate.get("read") or {}

    warnings: list[dict[str, Any]] = []
    gst_item = next(i for i in items if i["key"] == "gstin")
    office, gstin, cin = rec["registered_office"], rec["gstin"], rec["cin"]
    if india and gstin and gst_item["status"] == "done" and office:
        codes = state_codes(office)
        if not codes:
            warnings.append({"code": "state_unreadable", "item": 9})
        elif gstin[:2] not in codes:
            warnings.append({"code": "state_differs", "item": 9,
                             "gstin_state": state_name(gstin[:2]),
                             "office_state": state_name(sorted(codes)[0])})
    if india and cin and len(cin) == 21 and _shape_ok("cin_or_llpin", cin) \
            and int(cin[8:12]) < ACT_2013_YEAR and _says_2013_act(tv):
        warnings.append({"code": "act_wording", "item": 4, "year": int(cin[8:12])})
    on_record = (client.legal_name or client.name or "").strip() if client else ""
    # a recorded legal name unlike the certificate's (the display name is not a legal
    # name: a client with none recorded is not warned — its field shows the read value)
    if read.get("legal_name") and client and client.legal_name \
            and _norm(read["legal_name"]) != _norm(client.legal_name):
        warnings.append({"code": "name_differs", "certificate_name": read["legal_name"],
                         "profile_name": client.legal_name})

    verified = client is not None and client.details_verified_at is not None
    ok = [i["status"] in ("done", "not_needed") for i in items]
    checked = verified or not india
    needed = [i for i in items[1:] if i["status"] != "not_needed"]
    return {"applies": True, "india": india, "items": items, "warnings": warnings,
            "questions": sorted(record_keys(tv)), "reads": reads(client),
            "trade_name": read.get("trade_name"),
            "legal_name": on_record or None, "verify_needed": india,
            # R2-5: the tick needs a recorded legal name — its state, for the field's mark
            "legal_name_recorded": bool(client and (client.legal_name or "").strip()),
            "verified": {"at": client.details_verified_at.isoformat(),
                         "by": verified_by_name}
            if verified and client and client.details_verified_at else None,
            # review change 5: the client's details are nine items and the check
            "counts": {"done": sum(i["status"] == "done" for i in needed),
                       "needed": len(needed)},
            "client_ready": all(ok[1:]) and checked,
            "draft_values": draft_values(tv, answers, client),
            # how the Country field was read (D2): the named country, or India rules
            "country_abroad": country_abroad(client.country) if client else None,
            # what the tick attests is all there (review finding 17: the server says so)
            "tick_ready": client is not None and not record_gaps(client),
            "ready": all(ok) and checked}


#: the Companies Act, 2013's incorporation provisions began on 1 April 2014; a CIN carries
#: only the year, so a year before 2014 warns (the lead's ruling, round 2) — never blocks
ACT_2013_YEAR = 2014


def draft_values(tv: M.TemplateVersion, answers: Mapping[str, Any],
                 client: M.Counterparty | None) -> dict[str, str]:
    """D8: a draft started before client facts lived on the record still holds the typed
    answer. Where the record's field is empty, that answer is offered in the card ("from
    this draft — check"), never saved without a person."""
    out: dict[str, str] = {}
    for key, fields in record_keys(tv).items():
        typed = str(answers.get(key) or "").strip()
        field = fields[0]
        empty = client is not None and not (getattr(client, field, None) or "").strip()
        if typed and empty:
            out[field] = typed
    return out


def _says_2013_act(tv: M.TemplateVersion) -> bool:
    """The client's party paragraph in the template says "Companies Act, 2013"."""
    parties = (tv.layout or {}).get("parties") or []
    return any("{our_" not in json.dumps(p) and "Companies Act, 2013" in json.dumps(p)
               for p in parties)


def require_ready(tv: M.TemplateVersion, answers: Mapping[str, Any],
                  client: M.Counterparty | None) -> None:
    """The gate (spec §2): 409 with every item still open, else nothing."""
    found = checklist(tv, answers, client)
    if found["ready"]:
        return
    raise ClientDetailsIncomplete(
        [{k: i[k] for k in ("n", "key", "status", "problem") if k in i}
         for i in found["items"] if i["status"] in ("missing", "fix")],
        unverified=bool(found["verify_needed"] and found["verified"] is None))


def gate_problems(tv: M.TemplateVersion, answers: Mapping[str, Any],
                  client: M.Counterparty | None) -> str | None:
    """The gate's refusal as one sentence, for a caller that lists blockers."""
    try:
        require_ready(tv, answers, client)
    except ClientDetailsIncomplete as exc:
        return str(exc)
    return None


# ---------------------------------------------------------------- the certificate
#: D1: what the reader will look at — the certificate is one or two pages; anything larger
#: than this many pixels is not drawn at all; the whole OCR has this many seconds
READ_PAGES = 2
MAX_PIXELS = 25_000_000
OCR_SECONDS = 20
#: the size a certificate may be (D8: said in MB)
MAX_CERTIFICATE_MB = 25

_GSTIN = r"\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]"
#: Form GST REG-06's own block, in order: "Registration Number : <GSTIN>" and then, with
#: no other registration line between, "1. Legal Name". A value is the text between its
#: numbered label and the next numbered one, read from that block only (D7: the labelled
#: value nearest the registration line, never the first match anywhere on the page).
_BLOCK = re.compile(rf"Registration Number\s*:?\s*({_GSTIN})\b"
                    r"(?:(?!Registration Number).){0,200}?(?=1\.\s*Legal Name)")
_LABELLED = (("legal_name", r"1\.\s*Legal Name", r"2\.\s*Trade Name"),
             ("trade_name", r"2\.\s*Trade Name,?\s*(?:if any)?",
              r"3\.\s*Constitution of Business"),
             ("registered_office", r"4\.\s*Address of Principal Place of\s*Business",
              r"5\.\s*Date of Liability"))
#: how much of a certificate's text is read: its first block is near the top (R2-1)
_READ_CHARS = 20_000
_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin_valid(gstin: str) -> bool:
    """The GSTIN's 15th character is the check character of the first 14 (GSTN's base-36
    weighted sum: odd positions x1, even x2, each product's quotient and remainder by 36
    added; the check is 36 minus the sum mod 36)."""
    if not re.fullmatch(_GSTIN, gstin):
        return False
    total = 0
    for i, ch in enumerate(gstin[:14]):
        product = _B36.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _B36[(36 - total % 36) % 36] == gstin[14]


def _image_pixels(data: bytes) -> int | None:
    """Width x height from a PNG or JPEG header, before anything is decoded."""
    import struct
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return int(w) * int(h)
    i = 2
    while data.startswith(b"\xff\xd8") and i + 9 < len(data):
        if data[i] != 0xFF:
            return None
        marker, size = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return int(w) * int(h)
        i += 2 + size
    return None


def _ocr(pix, deadline: float) -> str:
    """One read of ``pix`` by the parser's own tesseract call, within what is left of the
    budget (a timeout or an error is caught by the caller: nothing read)."""
    import time

    from legalmind.ingestion.parsing import _tesseract
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError
    return _tesseract(pix, timeout=left)[0]


def certificate_text(data: bytes, mime_type: str) -> str:
    """The certificate's text, bounded (D1): a PDF's text layer on its first two pages,
    else those pages drawn for OCR (each refused unread past 25 MP); an image read at its
    own resolution after its header shows it is under 25 MP; at most 20 s of OCR in all.
    Anything unreadable, too large or too slow is the empty string: nothing is guessed."""
    import time

    import fitz  # the parser's PDF library

    from legalmind.ingestion.parsing import OCR_RENDER_DPI, ocr_available
    deadline = time.monotonic() + OCR_SECONDS
    try:
        if mime_type in ("image/png", "image/jpeg"):
            pixels = _image_pixels(data)
            if pixels is None or pixels > MAX_PIXELS or not ocr_available():
                return ""
            return _ocr(fitz.Pixmap(data), deadline)
        if mime_type != "application/pdf":
            return ""
        with fitz.open(stream=data, filetype="pdf") as doc:
            pages = [doc[i] for i in range(min(READ_PAGES, doc.page_count))]
            text = "\n".join(page.get_text() for page in pages)
            if text.strip() or not ocr_available():
                return text
            scale = OCR_RENDER_DPI / 72
            out = []
            for page in pages:
                if page.rect.width * scale * page.rect.height * scale > MAX_PIXELS:
                    return ""
                out.append(_ocr(page.get_pixmap(dpi=OCR_RENDER_DPI), deadline))
            return "\n".join(out)
    except Exception:              # damaged, unexpected, too slow: reads as nothing
        return ""


def read_certificate(text: str) -> dict[str, str]:
    """What the certificate's own block says: GSTIN (only when its check character is
    right — else ``gstin_unreadable``), legal name, trade name and the principal place of
    business; the PAN is the GSTIN's characters 3–12 and the state its first two digits'
    name. Only what was found — each for a person to confirm. No block, nothing read."""
    # bounded (R2-1): the form's own block sits on its first page — never scan more
    flat = " ".join(text.split())[:_READ_CHARS]
    block = _BLOCK.search(flat)
    if block is None:
        return {}
    out: dict[str, str] = {}
    gstin = block.group(1)
    if gstin_valid(gstin):
        out["gstin"], out["pan"] = gstin, gstin[2:12]
        if name := state_name(gstin[:2]):
            out["state"] = name
    else:
        out["gstin_unreadable"] = "true"
    rest = flat[block.end():]
    for key, start, end in _LABELLED:
        # linear (R2-1): the label once, then its end label within one value's reach
        s = re.search(start, rest, re.I)
        e = re.search(end, rest[s.end():s.end() + 600], re.I) if s else None
        value = rest[s.end():s.end() + e.start()].strip(" :,-") if s and e else ""
        if value and len(value) <= 500 and value.casefold() not in ("na", "n/a", "-"):
            out[key] = value
    return out
