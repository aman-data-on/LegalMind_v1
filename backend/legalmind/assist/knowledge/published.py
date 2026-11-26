"""The company's published policies as a retrievable source — `AM-130` (AB-74).

Owner ruling, 2026-10-09: for the Privacy Policy, Terms of Service, SLA and Acceptable
Usage Policy of both brands, the LIVE WEBSITE is authoritative, and Ask must answer from
what the website says today. The Constitution (§7, §8, Appendix C) already names these
eight pages as Level 3 "official, current company documents"; until now Ask could not
read them at all.

`refresh` fetches each page (the second permitted egress, `AM-130` amending `AM-30`
t10: GET only, HTTPS only, these two hosts only — a redirect anywhere else is refused
BEFORE it is followed — nothing sent but the request), keeps the policy text and
nothing of the site around it, and compares it with the CURRENT version by SHA-256 of
that text. Unchanged → nothing is written. Changed → a new `knowledge_sources` row
becomes CURRENT, the old one SUPERSEDED as of today with its items kept as history,
the page is saved under the source-material directory, and an audit event records old
and new hash. A page that cannot be fetched, is larger than MAX_BYTES, yields too
little text, or shrank sharply against the CURRENT version changes nothing (fail
closed: the last good version keeps answering, and the run reports the error).

Searched by `constitution.search` beside the Constitution, labelled
APPROVED_COMPANY_DOCUMENT. Records are indexed under a short crumb (brand · document ·
heading path); the reader's citation adds the URL (`citation`) — never the
Constitution.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from html.parser import HTMLParser

from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from legalmind import config


@dataclasses.dataclass(frozen=True)
class Policy:
    key: str            # also the saved file's stem, as in legal-docs/
    brand: str
    title: str
    url: str

    @property
    def source_type(self) -> str:
        return f"PUBLISHED_{self.key.replace('-', '_').upper()}"

    @property
    def name(self) -> str:
        return f"{self.brand} {self.title}"


POLICIES = (
    Policy("SLA-leapswitch", "Leapswitch", "Service Level Agreement",
           "https://www.leapswitch.com/service-level-agreement"),
    Policy("TOS-leapswitch", "Leapswitch", "Terms of Service",
           "https://www.leapswitch.com/terms-of-service"),
    Policy("AUP-leapswitch", "Leapswitch", "Acceptable Usage Policy",
           "https://www.leapswitch.com/acceptable-usage-policy"),
    Policy("PRIVACY-leapswitch", "Leapswitch", "Privacy Policy",
           "https://www.leapswitch.com/privacy-policy"),
    Policy("SLA-cloudpe", "CloudPe", "Service Level Agreement",
           "https://www.cloudpe.com/sla/"),
    Policy("TOS-cloudpe", "CloudPe", "Terms of Service", "https://www.cloudpe.com/terms/"),
    Policy("AUP-cloudpe", "CloudPe", "Acceptable Usage Policy",
           "https://www.cloudpe.com/aup/"),
    Policy("PRIVACY-cloudpe", "CloudPe", "Privacy Policy",
           "https://www.cloudpe.com/privacy/"),
)
SOURCE_TYPES = tuple(p.source_type for p in POLICIES)
BY_SOURCE_TYPE = {p.source_type: p for p in POLICIES}

#: Each brand as documents write it ("CloudPe", "Cloud Pe", "LeapSwitch") — the
#: Constitution's applicability chain starts at the brand (§4, §5.2; C-19), and Ask must
#: never answer a CloudPe document with a Leapswitch policy, or the reverse.
BRAND_NAMES = {"CloudPe": re.compile(r"cloud\s?pe", re.I),
               "Leapswitch": re.compile(r"leap\s?switch", re.I)}
#: A text is a brand's when it names that brand at least BRAND_MIN_MENTIONS times and at
#: least BRAND_DOMINANCE times as often as the other. Measured 2026-10-16 on the 13
#: approved PDFs: a CloudPe document names CloudPe 28-62 times and Leapswitch 3-6 (as its
#: operator, "CloudPe by Leapswitch"); a Leapswitch document or customer contract names
#: Leapswitch 2-242 times and CloudPe 0-4 — 7x apart at the closest. A text naming
#: neither, or both alike, is no brand's: both brands' policies stay, each labelled.
BRAND_MIN_MENTIONS = 2
BRAND_DOMINANCE = 3


def source_types(brand: str | None = None) -> tuple[str, ...]:
    """The published policies' source types — one brand's, or every brand's (None)."""
    return tuple(p.source_type for p in POLICIES if brand in (None, p.brand))


def brand_of(counts: dict[str, int]) -> str | None:
    """The brand ``counts`` (mentions per brand) make dominant, or None."""
    (top, n), (_, other) = sorted(counts.items(), key=lambda kv: -kv[1])[:2]
    return top if n >= BRAND_MIN_MENTIONS and n >= BRAND_DOMINANCE * other else None


def named_brand(text: str) -> str | None:
    """The one brand a question names ("the CloudPe SLA"), or None — none, or both."""
    named = [b for b, pattern in BRAND_NAMES.items() if pattern.search(text or "")]
    return named[0] if len(named) == 1 else None


#: "LeapSwitch" is also the COMPANY — Leapswitch Networks, which operates both brands —
#: so in a reader's words it names the Leapswitch brand only beside a product or policy
#: word ("the leapswitch sla", "a leapswitch customer"). "LeapSwitch to confirm …" in a
#: client's email about a CloudPe proposal named the company fourteen times and scoped
#: the answer to Leapswitch's policies (production, 2026-10-22). CloudPe is only a brand.
_LEAPSWITCH_AS_BRAND = re.compile(
    r"leap\s?switch(?:'s)?\s+(?:\w+\s+){0,2}?(?:sla\b|service level|terms|tos\b|aup\b|"
    r"acceptable us|privacy|polic|dedicated|servers?\b|bare.?metal|colocation|"
    r"customers?\b|clients?\b|plans?\b|products?\b|website)", re.I)


#: A product names its brand (`AM-202`). Each list is the products that brand's own
#: published SLA covers: Leapswitch's is the dedicated-server SLA; CloudPe's lists
#: Virtual Machines and GPU Compute. Only names one brand's SLA uses and the other's
#: does not — "private network" and "object storage" are left out.
PRODUCTS = {"Leapswitch": re.compile(r"\bdedicated\s+servers?\b|\bbare.?metal\b|"
                                     r"\bcolocation\b", re.I),
            "CloudPe": re.compile(r"\bvirtual\s+machines?\b|\bcloud\s+vms?\b|"
                                  r"\bgpu\s+(?:compute|instances?)\b", re.I)}


#: The company acting in a sentence — "LeapSwitch to confirm", "LeapSwitch remains
#: responsible", "caused by LeapSwitch" — is never the brand.
_LEAPSWITCH_AS_COMPANY = re.compile(
    r"leap\s?switch\s+(?:to|remains?|shall|will|may|must|is|has|networks|pvt|private|"
    r"ltd|limited)\b|\b(?:by|from|with|against)\s+leap\s?switch\b", re.I)
#: A short question naming Leapswitch means the brand: "what is the late fee for
#: leapswitch?" was asked which brand on all three models (P2 run, 2026-10-22).
SHORT_QUESTION_WORDS = 25


def reader_brands(text: str) -> set[str]:
    """The brands a reader's own words mean (`AM-201`): CloudPe wherever it is named,
    Leapswitch only as a brand (never as the company), and a product's brand
    (`PRODUCTS`). Two is a comparison."""
    out = set()
    if BRAND_NAMES["CloudPe"].search(text or ""):
        out.add("CloudPe")
    if _LEAPSWITCH_AS_BRAND.search(text or "") or (
            BRAND_NAMES["Leapswitch"].search(text or "")
            and len((text or "").split()) <= SHORT_QUESTION_WORDS
            and not _LEAPSWITCH_AS_COMPANY.search(text or "")):
        out.add("Leapswitch")
    out |= {brand for brand, pattern in PRODUCTS.items() if pattern.search(text or "")}
    return out


def brand_of_label(label: str | None) -> str | None:
    """The brand of a published policy's record, from its label ("CloudPe Service Level
    Agreement · …"), else None — the Constitution and every other source are no
    brand's."""
    low = (label or "").lower()
    return next((p.brand for p in POLICIES if low.startswith(p.name.lower())), None)


def document_brand(db: DBSession, document_version_id) -> str | None:
    """The brand a document version is, read from its own words (its chunks), or None.
    Deterministic and recomputed each time: nothing is stored, so no brand is ever
    recorded against a contract (the evaluator's side of C-19 is a schema decision)."""
    if document_version_id is None:
        return None
    contents = db.execute(text(
        f'SELECT content FROM "{config.assist_schema()}".chunks '
        "WHERE document_version_id = :v"), {"v": document_version_id}).scalars().all()
    return brand_of({b: sum(len(pattern.findall(c)) for c in contents)
                     for b, pattern in BRAND_NAMES.items()})
AUTHORITY = "APPROVED_COMPANY_DOCUMENT"
HOSTS = frozenset({"www.leapswitch.com", "www.cloudpe.com"})
MAX_BYTES = 2_000_000
TIMEOUT_S = 30
#: Fewer words than this is a broken or blocked page, never a policy (the shortest,
#: CloudPe's SLA, is ~700 words).
MIN_WORDS = 300
#: A new version shorter than this share of the CURRENT one is refused: a page cut
#: short by a template change must not silently replace the whole policy.
MIN_SHARE_OF_CURRENT = 0.7
#: ...and one that GREW past this multiple, in words or in headings, is refused too:
#: after a site redesign the footer or a promo is extracted with the policy, every
#: other check passes, and the broken page became CURRENT (review, 2026-10-14).
MAX_GROWTH_OF_CURRENT = 1.5


def citation(source_type: str, crumb: str) -> str:
    """What a reader is shown: the record's crumb and where the policy is published."""
    return f"{crumb} (published at {BY_SOURCE_TYPE[source_type].url})"


# ------------------------------------------------------------------------ egress
def _allowed(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and parts.hostname in HOSTS


class _Redirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to an allowed URL — checked BEFORE the request is made."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed(newurl):
            raise urllib.error.HTTPError(newurl, code, "redirect off the allowed hosts",
                                         headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_Redirects)


#: who we are, said honestly first; a WAF that refuses bots gets one re-probe as a
#: browser before a page is called dead (source integrity B1, critique M6)
HONEST_UA = "LegalMind-policy-refresh/1 (+https://leapswitch.com)"
BROWSER_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36")
#: the final statuses that mean the page is gone — every other failure is transient
GONE = (404, 410)


@dataclasses.dataclass(frozen=True)
class Page:
    html: str
    final_url: str
    status: int


class PageGone(Exception):
    """The FINAL response after redirects was 404/410, as ourselves and as a browser."""

    def __init__(self, url: str, status: int) -> None:
        super().__init__(f"HTTP {status} at {url} (after redirects, twice)")
        self.url, self.status = url, status


def _get(url: str, agent: str) -> Page:
    req = urllib.request.Request(url, headers={"User-Agent": agent})
    with _OPENER.open(req, timeout=TIMEOUT_S) as r:
        if not _allowed(r.geturl()):
            raise ValueError(f"ended off the allowed hosts: {r.geturl()}")
        raw = r.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError(f"page larger than {MAX_BYTES} bytes — refused")
        return Page(raw.decode(r.headers.get_content_charset() or "utf-8", "replace"),
                    r.geturl(), r.status)


def fetch(policy: Policy) -> Page:
    """The page, by GET over HTTPS from an allowed host, redirects followed (only to the
    allowed hosts). A 403/404/410 is re-probed once as a browser; a FINAL 404/410 both
    times raises `PageGone` — a 302 chain that ends 200 is a live page."""
    if not _allowed(policy.url):
        raise ValueError(f"not an allowed policy URL: {policy.url}")
    try:
        return _get(policy.url, HONEST_UA)
    except urllib.error.HTTPError as exc:
        if exc.code not in (403, *GONE):
            raise
    try:
        return _get(policy.url, BROWSER_UA)
    except urllib.error.HTTPError as exc:
        if exc.code in GONE:
            raise PageGone(exc.geturl() or policy.url, exc.code) from exc
        raise


#: the page's own "Last updated" line — "17 August 2026", "February 5, 2026"
_UPDATED = re.compile(r"last\s+updated\s*:?\s*(\d{1,2}\s+[a-z]+\.?\s+\d{4}"
                      r"|[a-z]+\.?\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})", re.I)


def page_updated_on(blocks: list[tuple[str, str]]) -> datetime.date | None:
    """The date the page says it was last updated (decision 5: shown to clients), or
    None when it gives none that parses — never a guess."""
    for _, t in blocks[:12]:
        m = _UPDATED.search(t)
        if not m:
            continue
        found = re.sub(r"[.,]", "", m[1])
        for fmt in ("%d %B %Y", "%B %d %Y", "%d %b %Y", "%b %d %Y", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(found, fmt).date()
            except ValueError:
                continue
    return None


# ------------------------------------------------------------------- extraction
_BLOCKS = {"p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt", "blockquote"}
_SKIP = {"script", "style", "noscript", "svg", "nav", "header", "form", "button"}
#: The site footer: a <footer>, or an element whose class/id token IS "footer" or
#: starts "footer_"/"footer-" (Leapswitch: id="footer", class="footer_bottom") —
#: never a "card-footer" or "table-footer" inside the policy.
_FOOTER = re.compile(r"(?:^|\s)footer(?:[_-]\w*)?(?=\s|$)")
#: Page chrome between the <h1> and the policy (Leapswitch's 2026-10-31 site): the
#: hero's one-line summary (class "lead") and the "On this page" contents (class
#: "legal-toc") — marketing and navigation, never policy text a reader may be cited.
#: Only BEFORE the policy's first section heading: a "lead" paragraph inside the policy
#: is policy text (review, 2026-11-02).
_CHROME = re.compile(r"(?:^|\s)(?:lead|legal-toc|toc)(?=\s|$)")


class _Extract(HTMLParser):
    """Text blocks from the page's first <h1> to the end of the policy: the end of
    <main> (CloudPe) or the site footer (Leapswitch) — the two templates the sites use
    (2026-10-09). Tables keep one row per block, cells joined by " | "."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []     # (tag, text)
        self.started = self.done = False
        self.skip = 0
        self.chrome: str | None = None      # the tag of the chrome element we are in
        self.chrome_depth = 0
        self.in_body = False                # chrome is read only before the first section
        self.main_depth = 0
        self.in_main_at_start = False
        self.tag: str | None = None
        self.buf: list[str] = []

    def _flush(self) -> None:
        t = re.sub(r"\s+", " ", "".join(self.buf)).strip(" |")
        if self.started and t and self.tag:
            self.blocks.append((self.tag, t))
        self.buf, self.tag = [], None

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        a = dict(attrs)
        mark = f'{a.get("class") or ""} {a.get("id") or ""}'.lower()
        if tag == "main":
            self.main_depth += 1
        if self.started and (tag == "footer" or _FOOTER.search(mark)):
            self._flush()
            self.done = True
            return
        if tag in _SKIP:
            self.skip += 1
        if tag in ("h2", "h3") and self.started:
            self.in_body = True             # the policy's own sections have begun
        if (self.chrome is None and self.started and not self.in_body
                and _CHROME.search(a.get("class") or "")):
            self.chrome = tag
        if tag == self.chrome:
            self.chrome_depth += 1
        if tag == "h1" and not self.started:
            self.started, self.in_main_at_start = True, self.main_depth > 0
        if tag in _BLOCKS:
            self._flush()
            self.tag = tag
        elif tag in ("td", "th") and self.buf:
            self.buf.append(" | ")
        elif tag == "br":
            self.buf.append(" ")

    def handle_endtag(self, tag):
        if self.done:
            return
        if tag in _SKIP and self.skip:
            self.skip -= 1
        if tag == self.chrome:
            self.chrome_depth -= 1
            if not self.chrome_depth:
                self.chrome = None
        if tag == "main":
            self.main_depth -= 1
            if self.started and self.in_main_at_start:
                self._flush()
                self.done = True
                return
        if tag in _BLOCKS:
            self._flush()

    def handle_data(self, data):
        if self.started and not self.done and not self.skip and self.chrome is None:
            if self.tag is None:
                self.tag = "p"
            self.buf.append(data)


@dataclasses.dataclass
class Item:
    ordinal: int
    parent: int | None
    kind: str
    clause: str | None
    content: str
    breadcrumb: str = ""
    level: int = 0


def extract(html: str) -> list[tuple[str, str]]:
    p = _Extract()
    p.feed(html)
    p.close()
    p._flush()
    return p.blocks


def policy_text(blocks: list[tuple[str, str]]) -> str:
    """The text the version hash is taken over: what a reader of the policy sees."""
    return "\n".join(t for _, t in blocks)


def items(policy: Policy, blocks: list[tuple[str, str]]) -> list[Item]:
    """DOCUMENT → SECTIONs nested by heading level → PARAGRAPH per block. The page's
    <h1> is a SECTION named for the policy, so its opening terms have an anchor too.
    A record's crumb is the policy's name and its heading path — "Leapswitch Terms of
    Service · 16. Termination · Effect of Termination" — short, so it is what is
    indexed and embedded (the URL goes in the citation, not the index)."""
    out = [Item(0, None, "DOCUMENT", policy.name, "", policy.name, 0)]
    stack = [0]
    for tag, t in blocks:
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            while len(stack) > 1 and out[stack[-1]].level >= level:
                stack.pop()
            parent = out[stack[-1]]
            crumb = policy.name if tag == "h1" else f"{parent.breadcrumb} · {t}"
            out.append(Item(len(out), parent.ordinal, "SECTION", t, t, crumb, level))
            stack.append(len(out) - 1)
            continue
        if len(stack) == 1:            # text before any heading: anchor it to the policy
            out.append(Item(len(out), 0, "SECTION", policy.name, policy.name,
                            policy.name, 1))
            stack.append(len(out) - 1)
        head = out[stack[-1]]
        out.append(Item(len(out), head.ordinal, "PARAGRAPH", None, t, head.breadcrumb,
                        head.level + 1))
    return out


# ------------------------------------------------------------------- ingestion
def _size(kinds_and_text) -> tuple[int, int]:
    """(paragraph words, headings) — one count for the stored version and the page
    read now, so the two are compared like for like."""
    words = heads = 0
    for kind, content in kinds_and_text:
        words += len(content.split()) if kind == "PARAGRAPH" else 0
        heads += kind == "SECTION"
    return words, heads


def _stored_size(db: DBSession, schema: str, source_id) -> tuple[int, int]:
    return _size(db.execute(text(
        f'SELECT kind, content FROM "{schema}".knowledge_items WHERE source_id = :s'),
        {"s": source_id}).tuples())


def _embed(db: DBSession, rows: list[tuple]) -> int:
    from legalmind.assist.knowledge import store
    return store.embed_into(db, table="knowledge_item_embeddings", fk="knowledge_item_id",
                            rows=rows)


def ingest(db: DBSession, policy: Policy, html: str, *,
           read_on: datetime.date | None = None) -> dict:
    """Make `html` the CURRENT version of `policy` unless its policy text is unchanged.
    Raises ValueError, writing nothing, when the page yields too little text, shrank
    below MIN_SHARE_OF_CURRENT of the CURRENT version or grew past
    MAX_GROWTH_OF_CURRENT of it."""
    read_on = read_on or datetime.date.today()
    blocks = extract(html)
    body = policy_text(blocks)
    words = len(body.split())
    if words < MIN_WORDS:
        raise ValueError(f"{policy.key}: {words} words extracted — not a policy page; "
                         "the current version is kept")
    sha = hashlib.sha256(body.encode()).hexdigest()
    schema = config.assist_schema()
    current = db.execute(text(
        f'SELECT id, version, file_sha256 FROM "{schema}".knowledge_sources '
        "WHERE source_type = :t AND status = 'CURRENT'"),
        {"t": policy.source_type}).first()
    if current and current.file_sha256 == sha:
        return {"policy": policy.key, "changed": False, "version": current.version,
                "embedded": _backfill(db, schema, current.id)}
    rows = items(policy, blocks)
    if current:
        (before, before_heads) = _stored_size(db, schema, current.id)
        (now, heads) = _size((i.kind, i.content) for i in rows)
        if now < MIN_SHARE_OF_CURRENT * before:
            raise ValueError(f"{policy.key}: {now} words against {before} in "
                             f"{current.version} — refused as a cut-short page; the "
                             "current version is kept")
        if now > MAX_GROWTH_OF_CURRENT * before or (
                heads > MAX_GROWTH_OF_CURRENT * before_heads):
            raise ValueError(f"{policy.key}: {now} words and {heads} headings against "
                             f"{before} and {before_heads} in {current.version} — "
                             "refused as a page that suddenly grew; the current "
                             "version is kept")
    # The same text seen before (A → B → A): that version becomes CURRENT again
    # rather than a duplicate — its records and embeddings are still there.
    earlier = db.execute(text(
        f'SELECT id, version FROM "{schema}".knowledge_sources '
        "WHERE source_type = :t AND file_sha256 = :h"),
        {"t": policy.source_type, "h": sha}).first()
    if current:
        db.execute(text(
            f'UPDATE "{schema}".knowledge_sources SET status = \'SUPERSEDED\', '
            "effective_to = :d WHERE id = :i"), {"d": read_on, "i": current.id})
    count = None
    if earlier:
        db.execute(text(
            f'UPDATE "{schema}".knowledge_sources SET status = \'CURRENT\', '
            "effective_to = NULL WHERE id = :i"), {"i": earlier.id})
        source_id, version = earlier.id, earlier.version
    else:
        version = f"{read_on.isoformat()}-{sha[:8]}"
        source_id = uuid.uuid4()
        db.execute(text(f"""
            INSERT INTO "{schema}".knowledge_sources
              (id, source_type, title, version, status, authority, jurisdiction,
               effective_from, supersedes_id, source_file, file_sha256)
            VALUES (:id, :t, :ti, :v, 'CURRENT', :a, 'IN', :ef, :sup, :f, :sha)"""),
            {"id": source_id, "t": policy.source_type, "ti": policy.name, "v": version,
             "a": AUTHORITY, "ef": read_on, "sup": current.id if current else None,
             "f": f"{policy.url} (read {read_on.isoformat()})", "sha": sha})
        count = len(rows)
        ids = [uuid.uuid4() for _ in rows]
        for it in rows:
            db.execute(text(f"""
                INSERT INTO "{schema}".knowledge_items
                  (id, source_id, parent_id, ordinal, kind, section_path, clause,
                   content, authority, status, cross_references, line_start, line_end,
                   breadcrumb)
                VALUES (:id, :s, :p, :o, :k, NULL, :c, :ct, :a, 'CURRENT', '{{}}', :o,
                        :o, :b)"""),
                {"id": ids[it.ordinal], "s": source_id,
                 "p": ids[it.parent] if it.parent is not None else None,
                 "o": it.ordinal, "k": it.kind, "c": it.clause, "ct": it.content,
                 "a": AUTHORITY, "b": it.breadcrumb})
        _embed(db, [(ids[i.ordinal], f"{i.breadcrumb}\n{i.content}") for i in rows
                    if i.kind == "PARAGRAPH"])
    _save(policy, html, read_on)
    from legalmind.security import audit
    audit.record(db, action=audit.PUBLISHED_POLICY_UPDATED,
                 entity_type="knowledge_source", entity_id=source_id,
                 before={"version": current.version, "sha256": current.file_sha256}
                 if current else None,
                 after={"policy": policy.key, "url": policy.url, "version": version,
                        "sha256": sha})
    return {"policy": policy.key, "changed": True, "version": version, "items": count}


def _backfill(db: DBSession, schema: str, source_id) -> int:
    """A version ingested while no embedding model was present gets its vectors the
    next time it is seen unchanged — otherwise it would stay lexical-only for good."""
    missing = db.execute(text(f"""
        SELECT i.id, i.breadcrumb, i.content FROM "{schema}".knowledge_items i
         WHERE i.source_id = :s AND i.kind = 'PARAGRAPH' AND NOT EXISTS (
               SELECT 1 FROM "{schema}".knowledge_item_embeddings e
                WHERE e.knowledge_item_id = i.id)"""), {"s": source_id}).all()
    return _embed(db, [(r.id, f"{r.breadcrumb}\n{r.content}") for r in missing]) \
        if missing else 0


def _save(policy: Policy, html: str, read_on: datetime.date) -> None:
    """The page as read, beside the other source material (gitignored, 54.6)."""
    folder = (pathlib.Path(config.source_material_dir()) / "published"
              / read_on.isoformat())
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{policy.key}.html").write_text(html)


def refresh(db: DBSession, *, fetcher=fetch,
            read_on: datetime.date | None = None) -> list[dict]:
    """Every policy, each in its own transaction: one site down never blocks the
    other's update. ``fetcher`` returns a `Page` (or the bare HTML of a saved copy).

    On success the CURRENT version records the check (`last_checked_ok_at`, final URL,
    status, the page's own date). On failure nothing is replaced and the version keeps
    its last good check, so the send gate says "not re-checked" after `source_check.
    RECHECK_HOURS`; a page the size guards refused, or one gone (final 404/410) on two
    runs in a row, is an operational failure the alerts timer reports."""
    out = []
    for policy in POLICIES:
        try:
            got = fetcher(policy)
            page = got if isinstance(got, Page) else None     # None: a saved copy
            result = ingest(db, policy, page.html if page else got, read_on=read_on)
            _checked(db, policy, page, got)
            db.commit()
            out.append(result)
        except Exception as exc:  # reported; the last good version stands
            db.rollback()
            out.append({"policy": policy.key, "changed": False,
                        "error": f"{type(exc).__name__}: {exc}"[:300]})
            _failed(db, policy, exc)
    return out


def _checked(db: DBSession, policy: Policy, page: Page | None, html: str | Page) -> None:
    """The page's own date always; the live check only for a page read live — a saved
    copy (``page`` None) proves nothing about the website today."""
    live = page is not None
    db.execute(text(f"""
        UPDATE "{config.assist_schema()}".knowledge_sources
           SET page_updated_on = :d,
               last_checked_ok_at = CASE WHEN :live THEN now()
                                         ELSE last_checked_ok_at END,
               final_url = coalesce(:u, final_url),
               http_status = coalesce(:s, http_status)
         WHERE source_type = :t AND status = 'CURRENT'"""),
        {"live": live, "u": page.final_url[:512] if page else None,
         "s": page.status if page else None,
         "d": page_updated_on(extract(page.html if page else str(html))),
         "t": policy.source_type})


def _failed(db: DBSession, policy: Policy, exc: Exception) -> None:
    from legalmind.observability import log_event
    schema = config.assist_schema()
    if isinstance(exc, PageGone):
        before = db.execute(text(
            f'SELECT http_status FROM "{schema}".knowledge_sources '
            "WHERE source_type = :t AND status = 'CURRENT'"),
            {"t": policy.source_type}).scalar()
        db.execute(text(
            f'UPDATE "{schema}".knowledge_sources SET http_status = :s, final_url = :u '
            "WHERE source_type = :t AND status = 'CURRENT'"),
            {"s": exc.status, "u": exc.url[:512], "t": policy.source_type})
        db.commit()
        if before in GONE:          # the final page gone on two runs: ours moved or died
            log_event("published_policy.page_gone", kind=policy.key, status=exc.status,
                      operational_failure=True)
    elif "refused" in str(exc) or "not a policy page" in str(exc):
        log_event("published_policy.refused", kind=policy.key,
                  error=type(exc).__name__, operational_failure=True)
