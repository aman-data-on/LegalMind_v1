"use client";

import Link from "next/link";
import { Fragment, type ReactNode, useId, useState } from "react";

import { Dialog } from "@/components/Dialog";
import type { AskSource, ConversationTurn } from "@/lib/types";

/**
 * The answer, as paragraphs and bullets — owner request, 2026-09-11 ("proper
 * paragraph spacing, bullets when useful").
 *
 * A small, closed subset of markdown — never a general renderer: the generator's
 * output is prose over retrieved passages, and a parser that invented links, images or
 * emphasis from stray punctuation would be putting formatting into a legal answer that
 * nobody wrote. Blank lines separate paragraphs; a line opening with a bullet becomes a
 * list item, one opening with a number an item of a numbered list (its number kept); a
 * block of pipe rows becomes a table (`PipeTable`); a block that is exactly one of the
 * server's own section labels (`SECTION_LABELS`) becomes a heading; `**…**` is bold.
 *
 * Owner request, 2026-10-06 (`AM-116`, amending DD-19 r6 again): `#` headings,
 * `` `code` `` and ``` fenced blocks render too. Each is guarded against legal prose:
 * a heading needs a word after its hashes (`# 17.2 applies` is a clause reference and
 * stays text), code needs both backticks on one line, and an unclosed fence stays
 * text. Single `*` and `_` are never emphasis. Every character of the text survives.
 *
 * ── Emphasis (owner request, 2026-10-06, amending DD-19 r6) ─────────────────────
 * "See how ChatGPT bolds that sentence." The answer's author marks the words that
 * carry a point; the agent's verifier checks the plain words and the server puts the
 * marks back only where the checked phrase still stands (`agent_verify.render`), so
 * this is emphasis somebody wrote, not one parsed from stray punctuation. A real
 * `<strong>` also travels with a copy into an e-mail or a document. A lone `**`
 * stays literal.
 *
 * Extracted from `TranscriptTurn` (2026-09-15) so the live dock can use it too. It
 * rendered `result.text` in a single flat `<p>`, so the SAME answer was laid out one
 * way while being read and another way on reload — paragraphs collapsed into a wall.
 * `TranscriptTurn` already imports from `AskDock`, so the dock could not import back
 * without a cycle; a module both can depend on is the smaller fix.
 *
 * ── Citation markers (Ask target architecture Phase 3, 2026-09-17) ──────────────
 * The generator cites its evidence as `[n]`, and `n` indexes the source list rendered
 * under the answer — the server renumbers prose and list into one sequence AFTER
 * verification (`service._renumber_markers`, PR #68). Until now both halves were
 * inert text, so a reader on the fourth point of an answer had to count list items to
 * find source 4. Given `citeCount` and `citeTargetId`, a marker in range becomes a
 * reference that moves focus to its own source; everything else — an out-of-range
 * number, a bracketed aside the model wrote, a bare `[`, the whole of a turn rendered
 * without the two props — stays exactly the literal text it is today.
 *
 * It is a NAVIGATION aid and nothing more. It does not restate, score or qualify the
 * evidence: no count, no strength, no "primary source", nothing that could read as
 * confidence in the claim (rule 12, DESIGN.md). The marker says where to look.
 */

/** `[1]`, `[12]` — one or more digits, nothing else. A marker the model wrote around
 *  anything but digits (`[see §7]`) is not a citation and is left alone. Split keeps
 *  the captured group, so every character of the original survives the round trip. */
const MARKER = /(\[\d+\])/g;
/** The Ask agent's ledger keys, `[C1]` or `[P8, P5]` (`agent_verify.render`): one
 *  letter for the kind of source and its number, never anything the model wrote. */
const KEYS = /(\[[CHPSDU]\d+(?:,\s*[CHPSDU]\d+)*\])/g;
/** A line of the agent's Sources legend: `- C37: §12.3 …`, its key first. */
const SOURCE_LINE = /^- ([CHPSDU]\d+): /gm;

/** What a marker in this answer can point at: its numbered sources, and the entries of
 *  its own Sources legend by key. */
interface Refs {
  count: number;
  target?: ((n: number) => string) | undefined;
  key: (key: string) => string | undefined;
  /** Where a key's clause can be shown in the document open beside the answer. */
  show: (key: string) => (() => void) | undefined;
}

/** How the surface that renders an answer shows a cited clause in its own open
 *  document: the action for a source it can highlight, undefined for any other. */
export type ShowInDocument = (source: AskSource) => (() => void) | undefined;

/** The section labels the SERVER writes between the parts of a verified answer
 *  (`service.LAYER_LABELS` and the Sources legend, `AM-107`): the direct answer
 *  first, then these, each on its own. Only a block that IS one of these exact
 *  strings becomes a heading — model prose never does, so nothing is interpreted
 *  that the server did not deliberately emit. Keep in step with `service.py`. */
export const SECTION_LABELS: ReadonlySet<string> = new Set([
  "Also relevant",
  "Historical context — past negotiated deals, not current policy",
  "Legal background",
  "Sources",
  // The Ask agent's four parts of a whole-situation answer (`agent_verify.PARTS`,
  // 2026-10-06): what is established is never read as what is only likely.
  "What we know",
  "What is likely",
  "What we don't know yet",
  "What needs legal review",
  "Next steps",
]);

/** The position reading aid (`AM-67`) cites its spans `[1]..[n]` in the order the
 *  company-standard cards are shown and has no Sources legend; a verified answer
 *  always carries its own. Only the former numbers the cards. */
export function citesPositions(text: string, citations: number, positions: number): boolean {
  return citations === 0 && positions > 0 && /\[\d+\]/.test(text)
    && !/(^|\n)Sources(\n|$)/.test(text);
}

/** The answer has no reading of its own — no document source, no marker: the fixed
 *  "quoted below" sentence of `AM-76` r4, where the paraphrase did not verify. The
 *  quote IS the answer then, so it opens, on reload too. */
export function quotesAreTheAnswer(text: string, citations: number): boolean {
  return citations === 0 && !/\[\d+\]/.test(text);
}

/** One line of a structured comparison (`AM-122`'s AMENDMENT A to `AM-90`): the server
 *  writes "Agreement (cl. 14.3): …", "Standard (MSA agreements only): …", "Delta: …". */
// lazy up to "): ", so a clause number such as "7.2(b)" keeps its own parenthesis
const COMPARE_ROW = /^(Agreement|Standard|Delta)(?: \((.+?)\))?: (.*)$/;

/** The three lines as a diff — label, then the words — with each source's marker on its
 *  own line, and any commentary after, as the plain sentence it is. */
function Comparison({ lines, rich }: { lines: string[]; rich: (line: string) => ReactNode }) {
  const rows = lines.map((line) => COMPARE_ROW.exec(line));
  const notes = lines.filter((_, i) => !rows[i]);
  return (
    <>
      <dl className="ws-ask__compare">
        {rows.map((m, i) => m ? (
          <div key={i} className={m[1] === "Delta" ? "ws-ask__compare-row ws-ask__compare-row--delta"
                                                  : "ws-ask__compare-row"}>
            <dt>
              {m[1]}
              {m[2] ? <span className="ws-ask__compare-qual"> ({m[2]})</span> : null}
            </dt>
            <dd>{rich(m[3]!)}</dd>
          </div>
        ) : null)}
      </dl>
      {notes.length ? <p className="ws-ask__text">{rich(notes.join(" "))}</p> : null}
    </>
  );
}

/** ``` … ``` on lines of their own: kept verbatim, blank lines and all. Split keeps
 *  the captured body, so odd parts are code. An unclosed fence matches nothing. */
const FENCE = /^```[^\n`]*\n([\s\S]*?)\n```[ \t]*$/gm;
/** `## Heading` — a word must follow the hashes, so `# 17.2 applies` stays a sentence. */
const HEADING = /^(#{1,4})\s+(?![\d§(])(.+?)\s*#*$/;
/** `- item`, `* item`, `• item`, `1. item`, `2) item` — three digits at most, so a
 *  year that happens to open a line ("2026. The Act…") is not a list. */
const ITEM = /^(?:([-*•])|(\d{1,3})[.)])\s+(.*)$/;

type Part =
  | { kind: "heading"; level: number; text: string }
  | { kind: "list"; ordered: boolean; start: number; items: string[] }
  | { kind: "text"; lines: string[] };

/** One block's lines as headings, lists and paragraphs, in order. A list item is one
 *  line; any other line after it starts a paragraph rather than joining the item. */
function parts(lines: string[]): Part[] {
  const out: Part[] = [];
  for (const line of lines) {
    const last = out[out.length - 1];
    const heading = HEADING.exec(line);
    const item = heading ? null : ITEM.exec(line);
    if (heading) {
      out.push({ kind: "heading", level: heading[1]!.length, text: heading[2]! });
    } else if (item) {
      const ordered = item[2] !== undefined;
      if (last?.kind === "list" && last.ordered === ordered) last.items.push(item[3]!);
      else out.push({ kind: "list", ordered, start: ordered ? Number(item[2]) : 1, items: [item[3]!] });
    } else if (last?.kind === "text") {
      last.lines.push(line);
    } else {
      out.push({ kind: "text", lines: [line] });
    }
  }
  return out;
}

export function AnswerProse({
  text,
  citeCount = 0,
  citeTargetId,
  sources,
  contractId,
  showInDocument,
}: {
  text: string;
  /** How many sources the answer actually carries. A marker above this is left as
   *  text: it points at nothing, and a reference that goes nowhere is worse than a
   *  number. */
  citeCount?: number;
  /** Builds the DOM id of source `n` — the same function the source list uses, so
   *  the two cannot drift. Absent (a turn with no source list, a refusal, the
   *  transcript before it opts in) means markers stay literal. */
  citeTargetId?: ((n: number) => string) | undefined;
  /** The records behind the Sources legend's keys: each entry with one opens it. */
  sources?: AskSource[] | undefined;
  /** The conversation's contract, so a clause can be opened in its document. */
  contractId?: string | null | undefined;
  /** The dock beside the document: a document key's marker shows its clause there. */
  showInDocument?: ShowInDocument | undefined;
}) {
  const uid = useId();
  const byKey = new Map((sources ?? []).map((source) => [source.key, source]));
  // the record open in the dialog, and the entry that opened it — focus goes back
  // there on close (the dialog unmounts, so Radix has nothing to return focus to)
  const [open, setOpen] = useState<
    { source: AskSource; where: string; from: HTMLElement } | null>(null);
  const legend = new Set([...text.matchAll(SOURCE_LINE)].map((m) => m[1]!));
  const refs: Refs = {
    count: citeCount,
    target: citeTargetId,
    key: (k) => (legend.has(k) ? `${uid}-source-${k}` : undefined),
    show: (k) => {
      const source = byKey.get(k);
      return source && showInDocument ? showInDocument(source) : undefined;
    },
  };
  const rich = (line: string) => inline(line, refs);
  let inSources = false;
  return (
    <>
      {text.split(FENCE).map((segment, s) => (s % 2 ? (
        <pre key={s} className="ws-ask__pre"><code>{segment}</code></pre>
      ) : segment.split(/\n{2,}/).filter((block) => block.trim().length > 0).map((block, index) => {
        const key = `${s}-${index}`;
        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        const label = lines.length === 1 ? lines[0] : undefined;
        if (label !== undefined && SECTION_LABELS.has(label)) {
          inSources = label === "Sources";
          return (
            <h3 key={key} className="ws-ask__section">
              {label}
            </h3>
          );
        }
        if (lines.length > 1 && lines.every((line) => /^\|.*\|$/.test(line))) {
          return <PipeTable key={key} lines={lines} refs={refs} />;
        }
        if (lines.length >= 3 && lines[0]!.startsWith("Agreement")
            && COMPARE_ROW.test(lines[0]!) && /^Standard\b/.test(lines[1]!)) {
          return <Comparison key={key} lines={lines} rich={rich} />;
        }
        return (
          <Fragment key={key}>
            {parts(lines).map((part, i) => {
              if (part.kind === "heading") {
                const Heading = part.level <= 2 ? "h3" : "h4";
                return <Heading key={i} className="ws-ask__heading">{rich(part.text)}</Heading>;
              }
              if (part.kind === "list") {
                const items = part.items.map((item, n) => {
                  // A legend entry is where its key's markers land: its own id, focusable
                  // by script only, the key set apart from the location it names.
                  const entry = inSources ? /^([CHPSDU]\d+): (.*)$/.exec(item) : null;
                  const id = entry ? refs.key(entry[1]!) : undefined;
                  const source = entry ? byKey.get(entry[1]!) : undefined;
                  // A key with its record behind it opens that record: the marker in
                  // the prose lands on this button, and Enter shows where it came from.
                  if (entry && id && source) {
                    return (
                      <li key={n}>
                        <button id={id} type="button" className="ws-ask__srcbtn"
                                aria-haspopup="dialog"
                                onClick={(event) => setOpen({
                                  source, where: entry[2]!, from: event.currentTarget })}>
                          <span className="ws-ask__srckey ws-mono">{entry[1]} </span>
                          <span>
                            {/* plain text: a control inside this button would be invalid */}
                            <span className="ws-ask__srckind">{sourceKind(source)}</span>{" "}
                            {entry[2]}
                          </span>
                        </button>
                      </li>
                    );
                  }
                  return entry && id ? (
                    <li key={n} id={id} tabIndex={-1}>
                      {/* the space inside the key keeps a copied legend readable */}
                      <span className="ws-ask__srckey ws-mono">{entry[1]} </span>
                      <span>{rich(entry[2]!)}</span>
                    </li>
                  ) : <li key={n}>{rich(item)}</li>;
                });
                const legendList = inSources && !part.ordered;
                return part.ordered ? (
                  <ol key={i} className="ws-ask__bullets" start={part.start === 1 ? undefined : part.start}>
                    {items}
                  </ol>
                ) : (
                  <ul key={i} className={legendList ? "ws-ask__bullets ws-ask__legend" : "ws-ask__bullets"}>
                    {items}
                  </ul>
                );
              }
              return <p key={i} className="ws-ask__text">{rich(part.lines.join(" "))}</p>;
            })}
          </Fragment>
        );
      })))}
      {open ? (
        <SourceDialog source={open.source} where={open.where} contractId={contractId ?? null}
                      show={refs.show(open.source.key)}
                      onClose={(refocus = true) => {
          const from = open.from;
          setOpen(null);
          // Shown in the document, focus belongs on the lit passage, not back here.
          if (refocus) requestAnimationFrame(() => from.focus());
        }} />
      ) : null}
    </>
  );
}

/** Who answered and how long it took (owner, 2026-10-07), from the answer row — the
 *  same line live and on reload. Three honest cases (`AM-122`): a model wrote it; a
 *  model ran but its draft was not used (the reply itself says why); or no model ran
 *  at all — a fixed reply, which carries no time because nothing was timed. A time,
 *  never a score: nothing here reads as confidence (rule 12). */
export function AnswerMeta({ turn }: {
  turn: Pick<ConversationTurn, "answered_by" | "latency_ms">;
}) {
  const ms = turn.latency_ms;
  if (ms == null && !turn.answered_by) {
    return <p className="ws-ask__meta">Instant reply · no model used</p>;
  }
  const who = turn.answered_by
    ? `Answered by ${turn.answered_by.label}` +
      (turn.answered_by.model !== turn.answered_by.label ? ` (${turn.answered_by.model})` : "")
    : "Model draft not used";
  const time = ms == null ? "" : ms < 1000 ? ` · ${ms} ms` : ` · ${(ms / 1000).toFixed(1)} s`;
  return <p className="ws-ask__meta">{who}{time}</p>;
}

/** What kind of source a key names, in the reader's words. */
export function sourceKind(source: AskSource): string {
  if (source.kind === "document") {
    return source.scope === undefined || source.scope === "the selected document"
      ? "This agreement" : "Another document";
  }
  return { position: "Company standard", constitution: "Legal Constitution",
           statute: "Statute", material: "Your material" }[source.kind];
}

/** One cited record, opened from the Sources list: what it is, where it sits, and its
 *  own words — the text the answer was checked against, never a summary of it. */
function SourceDialog({ source, where, contractId, show, onClose }: {
  source: AskSource;
  /** The legend's own words for it ("§9, MSA agreements only") — the same live and on
   *  reload, where the record's scope is not carried. */
  where: string;
  /** Absent where the document is already open (the dock): the link would go nowhere. */
  contractId: string | null;
  /** Shows the clause in the document already open beside the answer (the dock). */
  show?: (() => void) | undefined;
  onClose: (refocus?: boolean) => void;
}) {
  const titleId = useId();
  const href = contractId && source.kind === "document" &&
    sourceKind(source) === "This agreement" && source.evidence_id && source.document_version_id
    ? `/dashboard?id=${contractId}&version=${source.document_version_id}` +
      `&evidence=${source.evidence_id}`
    : null;
  return (
    <Dialog onClose={onClose} titleId={titleId}>
      <h2 id={titleId}>{sourceKind(source)}</h2>
      <p className="ws-modal__body">{where}</p>
      {source.state === "stale" ? (
        <p className="ws-modal__body">
          This source has changed since the answer was written. Its current text is shown.
        </p>
      ) : null}
      <blockquote className="ws-ask__excerpt ws-ask__srctext">{source.text}</blockquote>
      <div className="ws-modal__acts">
        {href ? <Link className="ws-btn" href={href}>Open in the document</Link> : null}
        {!href && show ? (
          <button type="button" className="ws-btn" onClick={() => { onClose(false); show(); }}>
            Show in the document
          </button>
        ) : null}
        <button type="button" className="ws-btn ws-btn--primary" onClick={() => onClose()}>
          Close
        </button>
      </div>
    </Dialog>
  );
}

/** A table the SERVER emitted (`AM-108`: every line of the block is a pipe row, which
 *  model prose never is — a table reaches here only when the reader asked for one and
 *  every row passed verification). The first row is the header; a `|---|` rule line is
 *  skipped; cells keep their markers as references. */
function PipeTable({ lines, refs }: { lines: string[]; refs: Refs }) {
  const rows = lines
    .filter((line) => !/^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$/.test(line))
    .map((line) => line.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim()));
  const head = rows[0];
  const body = rows.slice(1);
  if (head === undefined || body.length === 0) {
    return <p className="ws-ask__text">{lines.join(" ")}</p>;
  }
  return (
    <div className="ws-ask__tablewrap">
      <table className="ws-ask__table">
        <thead>
          <tr>{head.map((cell, i) => <th key={i} scope="col">{cell}</th>)}</tr>
        </thead>
        <tbody>
          {body.map((cells, r) => (
            <tr key={r}>
              {cells.map((cell, c) => (c === 0
                ? <th key={c} scope="row">{inline(cell, refs)}</th>
                : <td key={c}>{inline(cell, refs)}</td>))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** `**phrase**` — opening and closing next to a word, one line, no `*` inside.
 *  Split keeps the captured group, so the odd parts are the emphasised ones. */
const EMPHASIS = /\*\*(?=\S)([^*\n]*?\S)\*\*/g;
/** `` `code` `` — both backticks on one line; its text is shown exactly, unformatted. */
const CODE = /`([^`\n]+)`/g;
/** A code span held out of the line while its emphasis is read (private-use marks). */
const HELD = /\uE000(\d+)\uE001/;

/** One paragraph, bullet, heading or cell. Code spans are held out first, so nothing
 *  inside one is read and bold may wrap one (`**within `6 hours`**`); then `**…**` is
 *  bold; then markers become references. */
function inline(line: string, refs: Refs): ReactNode {
  const codes: string[] = [];
  const held = line.includes("`")
    ? line.replace(CODE, (_, code: string) => `\uE000${codes.push(code) - 1}\uE001`)
    : line;
  const leaf = (span: string): ReactNode => {
    if (!codes.length) return withMarkers(span, refs);
    const pieces = span.split(HELD);
    return pieces.map((piece, index) => (index % 2
      ? <code key={index} className="ws-ask__code">{codes[Number(piece)]}</code>
      : <Fragment key={index}>{withMarkers(piece, refs)}</Fragment>));
  };
  const parts = held.includes("**") ? held.split(EMPHASIS) : [held];
  if (parts.length === 1) return leaf(held);
  return parts.map((part, index) => (index % 2
    ? <strong key={index}>{leaf(part)}</strong>
    : <Fragment key={index}>{leaf(part)}</Fragment>));
}

/** The prose of one paragraph or bullet, its markers as references: an in-range `[n]`,
 *  and a ledger key `[C1, P2]` set quietly apart, each key linked to its legend entry.
 *  Returns the plain string when there is nothing to mark, so the common case
 *  allocates nothing and renders exactly as it did before this existed. */
function withMarkers(line: string, refs: Refs): ReactNode {
  if (!line.includes("[")) return line;
  const numbered = refs.target && refs.count > 0;
  const parts = line.split(numbered ? new RegExp(`${MARKER.source}|${KEYS.source}`) : KEYS);
  if (parts.length === 1) return line;
  const isKeys = (part: string | undefined) =>
    part !== undefined && /^\[[CHPSDU]\d/.test(part);
  return parts.map((part, index) => {
    if (part === undefined || part === "") return null;
    // A key group keeps to the word before it, so it never wraps onto a line alone.
    if (!isKeys(part) && isKeys(parts.slice(index + 1).find((x) => x))) {
      part = part.replace(/\s+$/, "\u00A0");
    }
    const keys = /^\[([CHPSDU]\d+(?:,\s*[CHPSDU]\d+)*)\]$/.exec(part);
    if (keys) {
      const list = keys[1]!.split(/,\s*/);
      return (
        <span key={index} className="ws-ask__keys ws-mono">
          [{list.map((k, i) => {
            const id = refs.key(k);
            const show = refs.show(k);
            return (
              <Fragment key={k}>
                {i ? ", " : ""}
                {id ? <CiteRef label={k} targetId={id} show={show}
                               name={show ? `Show source ${k} in the document` : `Go to source ${k}`} />
                    : k}
              </Fragment>
            );
          })}]
        </span>
      );
    }
    const match = /^\[(\d+)\]$/.exec(part);
    const n = match ? Number(match[1]) : 0;
    if (!refs.target || n < 1 || n > refs.count) return part;
    return <CiteRef key={index} label={`[${n}]`} name={`Go to source ${n}`}
                    targetId={refs.target(n)} className="ws-ask__ref" />;
  });
}

/** Script-driven scrolling follows the reader's motion setting, as CSS scrolling does
 *  on its own: `behavior: "smooth"` in a script ignores `prefers-reduced-motion`. */
export function scrollMotion(): ScrollBehavior {
  return typeof window !== "undefined"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

/** One marker, as a reference to its source.
 *
 *  A button rather than an `<a href="#…">`: the anchor form would push a hash onto a
 *  URL that already carries the workspace's document, version and evidence state, and
 *  a back button that undid a footnote jump instead of the document you opened is the
 *  wrong behaviour. Focus moves to the source (not just the scroll position), so the
 *  jump works for a keyboard and a screen reader and not only for a mouse — the
 *  source list item is focusable for exactly this reason.
 *
 *  Inline in a sentence, so WCAG 2.2 Target Size (Minimum) applies its in-text
 *  exception; the padding is for comfort, and deliberately not enough to break the
 *  line rhythm of a paragraph of legal prose. "Source 4", not "Citation 4": the list it
 *  points at is headed "Sources", and one word for one thing across the interface.
 */
function CiteRef({ label, name, targetId, show, className = "ws-ask__key" }: {
  label: string;
  name: string;
  targetId: string;
  /** A clause of the open document: the marker shows it there instead (the dock). */
  show?: (() => void) | undefined;
  className?: string;
}) {
  return (
    <button
      type="button"
      className={`${className} ws-mono`}
      aria-label={name}
      onClick={() => {
        if (show) return show();
        const target = typeof document === "undefined" ? null : document.getElementById(targetId);
        if (!target) return;
        target.scrollIntoView({ block: "nearest", behavior: scrollMotion() });
        /* The item carries tabIndex={-1}; focusing it is what announces the source
           to a screen reader and gives the eye somewhere to land. `preventScroll`
           leaves the smooth scroll above in charge of the movement. */
        target.focus({ preventScroll: true });
      }}
    >
      {label}
    </button>
  );
}
