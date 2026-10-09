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
           "https://leapswitch.com/service-level-agreement.php"),
    Policy("TOS-leapswitch", "Leapswitch", "Terms of Service",
           "https://leapswitch.com/terms-of-service.php"),
    Policy("AUP-leapswitch", "Leapswitch", "Acceptable Usage Policy",
           "https://leapswitch.com/acceptable-usage-policy.php"),
    Policy("PRIVACY-leapswitch", "Leapswitch", "Privacy Policy",
           "https://leapswitch.com/privacy-policy.php"),
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
AUTHORITY = "APPROVED_COMPANY_DOCUMENT"
HOSTS = frozenset({"leapswitch.com", "www.cloudpe.com"})
MAX_BYTES = 2_000_000
TIMEOUT_S = 30
#: Fewer words than this is a broken or blocked page, never a policy (the shortest,
#: CloudPe's SLA, is ~700 words).
MIN_WORDS = 300
#: A new version shorter than this share of the CURRENT one is refused: a page cut
#: short by a template change must not silently replace the whole policy.
MIN_SHARE_OF_CURRENT = 0.7


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


def fetch(policy: Policy) -> str:
    """The page, by GET over HTTPS from an allowed host — the only request made."""
    if not _allowed(policy.url):
        raise ValueError(f"not an allowed policy URL: {policy.url}")
    req = urllib.request.Request(policy.url, headers={
        "User-Agent": "LegalMind-policy-refresh/1 (+https://leapswitch.com)"})
    with _OPENER.open(req, timeout=TIMEOUT_S) as r:
        if not _allowed(r.geturl()):
            raise ValueError(f"ended off the allowed hosts: {r.geturl()}")
        raw = r.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError(f"{policy.key}: page larger than {MAX_BYTES} bytes")
        return raw.decode(r.headers.get_content_charset() or "utf-8", "replace")


# ------------------------------------------------------------------- extraction
_BLOCKS = {"p", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "dd", "dt", "blockquote"}
_SKIP = {"script", "style", "noscript", "svg", "nav", "header", "form", "button"}
#: The site footer: a <footer>, or an element whose class/id token IS "footer" or
#: starts "footer_"/"footer-" (Leapswitch: id="footer", class="footer_bottom") —
#: never a "card-footer" or "table-footer" inside the policy.
_FOOTER = re.compile(r"(?:^|\s)footer(?:[_-]\w*)?(?=\s|$)")


class _Extract(HTMLParser):
    """Text blocks from the page's first <h1> to the end of the policy: the end of
    <main> (CloudPe) or the site footer (Leapswitch) — the two templates the sites use
    (2026-10-09). Tables keep one row per block, cells joined by " | "."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []     # (tag, text)
        self.started = self.done = False
        self.skip = 0
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
        if tag == "main":
            self.main_depth -= 1
            if self.started and self.in_main_at_start:
                self._flush()
                self.done = True
                return
        if tag in _BLOCKS:
            self._flush()

    def handle_data(self, data):
        if self.started and not self.done and not self.skip:
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
def _words(db: DBSession, schema: str, source_id) -> int:
    rows = db.execute(text(
        f'SELECT content FROM "{schema}".knowledge_items WHERE source_id = :s '
        "AND kind = 'PARAGRAPH'"), {"s": source_id}).scalars()
    return sum(len(c.split()) for c in rows)


def _embed(db: DBSession, rows: list[tuple]) -> int:
    from legalmind.assist.knowledge import store
    return store.embed_into(db, table="knowledge_item_embeddings", fk="knowledge_item_id",
                            rows=rows)


def ingest(db: DBSession, policy: Policy, html: str, *,
           read_on: datetime.date | None = None) -> dict:
    """Make `html` the CURRENT version of `policy` unless its policy text is unchanged.
    Raises ValueError, writing nothing, when the page yields too little text or shrank
    below MIN_SHARE_OF_CURRENT of the CURRENT version."""
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
    if current:
        before = _words(db, schema, current.id)
        if words < MIN_SHARE_OF_CURRENT * before:
            raise ValueError(f"{policy.key}: {words} words against {before} in "
                             f"{current.version} — refused as a cut-short page; the "
                             "current version is kept")
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
        rows = items(policy, blocks)
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
    other's update."""
    out = []
    for policy in POLICIES:
        try:
            out.append(ingest(db, policy, fetcher(policy), read_on=read_on))
            db.commit()
        except Exception as exc:  # reported; the last good version stands
            db.rollback()
            out.append({"policy": policy.key, "changed": False,
                        "error": f"{type(exc).__name__}: {exc}"[:300]})
    return out
