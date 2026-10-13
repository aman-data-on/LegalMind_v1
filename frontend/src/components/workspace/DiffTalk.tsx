"use client";

/**
 * Diff-Talk (owner, 2026-10-12) — two documents side by side, clause by clause.
 *
 * TWO NAMED SIDES, NOT "LEFT" AND "RIGHT" (owner, 2026-10-12). **Our document** is a
 * company website document (TOS, SLA, AUP, Privacy — the current published copy,
 * so nobody uploads what the website already has) or our own upload (an MSA, NDA,
 * PO). **Client contract** is the other party's paper: a client document already in
 * LegalMind or an upload. Each list offers only its own side — our documents are
 * never offered as a client's — using Step 6's existing source axis: an upload is
 * declared ORGANIZATION or COUNTERPARTY as it lands. A plain comparison: no side is
 * labelled approved ("we do not say this approved or not").
 *
 * WORDING ONLY. Green means the same words, red means different words; neither
 * says whether the difference is acceptable. That answer is the Constitution-based
 * review in a document's Findings, so the view states the boundary once and
 * carries no Finding, status word or decision control (33.16; the server returns no
 * verdict to show).
 *
 * WHY ONE SENTENCE PER LINE. The diff viewer compares line by line, then word by
 * word inside a changed line. A PDF breaks its lines wherever the page ran out, so
 * line-for-line every clause would look rewritten. Both sides are re-set one
 * sentence per line first: the viewer then pairs sentences and marks the words
 * that differ inside them, which is how a lawyer reads a mark-up anyway.
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DiffMethod } from "react-diff-viewer-continued";

import { api, describeError, uploadFirstDocument } from "@/lib/api";
import { documentTypeChip, nameFromFilename } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type {
  ComparedClause,
  ComparedDocument,
  Contract,
  DocumentComparison,
  WebsiteDocument,
} from "@/lib/types";
import { shortDate } from "@/components/clients/model";
import {
  IconArrowDown, IconArrowUp, IconCheck, IconCopy, IconFileDiff, IconFileMinus,
  IconFilePlus, IconReplace, IconUploadCloud, IconX,
} from "./icons";
import { useMinWidth } from "./WorkspaceLayout";

/** A contract type's own website document, offered first when a contract opens
 *  Diff-Talk from its workspace. A default only — the reader can pick anything. */
export const WEBSITE_KEY_BY_TYPE: Record<string, string> = {
  TOS: "TOS-leapswitch", SLA: "SLA-leapswitch", AUP: "AUP-leapswitch",
  PRIVACY_POLICY: "PRIVACY-leapswitch",
};

/** The viewer and its 81 transitive packages load only when a comparison
 *  renders, not with the page (2026-10-12). */
const loadViewer = () => import("react-diff-viewer-continued");
const ReactDiffViewer = dynamic(loadViewer, {
  ssr: false,
  loading: () => <p className="ws-dt__text">Loading the comparison…</p>,
});
/** `DiffMethod.WORDS`, without importing the enum's module eagerly. It must be
 *  the library's own method name: given a function instead, the viewer turns
 *  word highlighting off altogether (`shouldHighlightWordDiff`, found 2026-10-12). */
const WORDS = "diffWords" as unknown as DiffMethod;

type Row = DocumentComparison["clauses"][number];
type Filter = "ALL" | "CHANGED" | "ADDED" | "REMOVED";
type Load =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; comparison: DocumentComparison };

/** Whitespace collapsed, one sentence per line. A list number ("1."), an
 *  initial or a company/legal abbreviation ("Pvt. Ltd.", "No.", "e.g.") never
 *  ends a sentence. */
export function sentences(text: string): string {
  // A word hyphenated across a PDF line ("quasi-↵governmental") is one word.
  return text.replace(/(\w)-[ \t]*\n\s*(?=\w)/g, "$1-").replace(/\s+/g, " ").trim()
    .split(/(?<=[^\s\d][.;!?])(?<!\b(?:[A-Z]|Pvt|Ltd|Co|No|Nos|Inc|Corp|Mr|Mrs|Ms|Dr|St|Rs|vs|viz|e\.g|i\.e|etc)\.)\s+(?=[("“'A-Z0-9])/u)
    .join("\n");
}

function clauseName(c: ComparedClause | null): string {
  if (!c) return "";
  const title = (c.title ?? "").replace(/^\W*\d+(\.\d+)*\.?\s*/, "");
  if (c.ref && title) return tidyTitle(`${c.ref}. ${title}`);
  return c.ref ? `Clause ${c.ref}` : tidyTitle(title) || "Opening text";
}

/** Each kind of row, as the reader names it — label, short label for the
 *  changes list, and an icon so the kind is never carried by colour alone. */
const KIND: Record<Row["status"], { label: string; short: string; tone: "same" | "diff";
  Icon: (p: { size?: number }) => React.ReactElement }> = {
  UNCHANGED: { label: "Same wording", short: "Same", tone: "same", Icon: IconCheck },
  CHANGED: { label: "Wording changed", short: "Changed", tone: "diff", Icon: IconReplace },
  ADDED: { label: "Added by the client", short: "Added", tone: "diff", Icon: IconFilePlus },
  REMOVED: { label: "Missing from the client contract", short: "Missing", tone: "diff",
             Icon: IconFileMinus },
};

/** ALL-CAPS clause headings ("1. DEFINITIONS") read as shouting in a list —
 *  shown in title case. Display only; the documents are untouched. */
// No single letters here: in a legal heading "A" is a label ("Schedule A"), not "a".
const SMALL = new Set(["an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"]);
export function tidyTitle(title: string): string {
  const letters = title.replace(/[^A-Za-z]/g, "");
  if (letters.length < 4 || title !== title.toUpperCase()) return title;
  return title.toLowerCase().replace(/[a-z][a-z’']*/g, (w, i: number) =>
    i > 0 && SMALL.has(w) ? w : w[0]!.toUpperCase() + w.slice(1));
}

const isDifference = (r: Row) => r.status !== "UNCHANGED" || r.moved;

/** The reader's drafting choice on one difference (owner, 2026-10-13). A choice
 *  about wording, never a Legal Decision: the final contract still goes through
 *  the review, where Legal decides (AB-12 r9, RESOLVED ≠ MATCH). */
type Choice = "ours" | "theirs";
/** What each choice does to the TEXT, in the words of that kind of difference. */
const CHOICE_WORDS: Record<Exclude<Row["status"], "UNCHANGED">, Record<Choice, string>> = {
  CHANGED: { ours: "Keep ours", theirs: "Accept theirs" },
  ADDED: { ours: "Leave it out", theirs: "Add it" },
  REMOVED: { ours: "Keep ours", theirs: "Remove it" },
};
/** Stable across reloads of the same pair, unlike a row's position. */
const rowKey = (r: Row) =>
  `${r.status}|${r.left?.text.slice(0, 80) ?? ""}|${r.right?.text.slice(0, 80) ?? ""}`;

/** "2 of 14 sentences" — how much of a changed clause to read, before reading it. */
function changedSentences(row: Row): string {
  const ours = new Set(sentences(row.left!.text).split("\n"));
  const theirs = sentences(row.right!.text).split("\n");
  const n = theirs.filter((t) => !ours.has(t)).length || 1;
  return `${n} of ${theirs.length} sentence${theirs.length === 1 ? "" : "s"}`;
}

/** The viewer in the workspace's own colours: a light red tint on a changed
 *  sentence, a stronger one on the words that changed — on both sides, since
 *  green is kept for "same wording" — and the contract serif. Two columns need
 *  no −/+ gutter (the columns say which side); one column keeps it, with a
 *  legend. No fold lines: every sentence of a clause is shown. */
const viewerStyles = (split: boolean) => ({
  variables: {
    light: {
      diffViewerBackground: "var(--ws-surface)",
      diffViewerColor: "var(--ws-ink-900)",
      removedBackground: "#fdf3f3",
      addedBackground: "#fdf3f3",
      wordRemovedBackground: "#f6c8c8",
      wordAddedBackground: "#f6c8c8",
      removedGutterBackground: "#fdf3f3",
      addedGutterBackground: "#fdf3f3",
      removedColor: "var(--ws-ink-900)",
      addedColor: "var(--ws-ink-900)",
      emptyLineBackground: "var(--ws-paper)",
      gutterBackground: "var(--ws-surface)",
    },
  },
  contentText: {
    fontFamily: "var(--ws-serif)", fontSize: "var(--ws-text-base)", lineHeight: 1.6,
    // The viewer's code default `line-break: anywhere` splits words ("a greement").
    whiteSpace: "pre-wrap" as const, lineBreak: "auto" as const,
    overflowWrap: "break-word" as const,
  },
  line: { padding: "2px 0" },
  // The library's table has `min-width: 1000px`: below that it spilled out of the
  // card and clipped the client column (1024px, 2026-10-13).
  diffContainer: { minWidth: 0 },
  wordDiff: { padding: "1px 0", borderRadius: "2px" },
  // Hidden, not removed: the marker is a table cell, and dropping it shifts the
  // text into the gutter column.
  marker: split ? { width: "8px", padding: 0, visibility: "hidden" as const }
    : { width: "22px", padding: "0 4px", color: "var(--ws-error)" },
});

/** The Diff-Talk page (owner, 2026-10-13, full design ownership): SETUP until
 *  both documents are chosen, then REVIEW — a changes list beside the compared
 *  clauses, one pinned header carrying the documents, progress and actions.
 *  Both sides live in the URL, so a comparison can be linked and Back works. */
export function DiffTalkPage({ left, right, onChange }: {
  /** The two sides, straight from the URL — the one source of truth, so Back
   *  undoes a step (QA 2026-10-13: Back after "Change" skipped the comparison). */
  left: string;
  right: string;
  onChange: (left: string, right: string) => void;
}) {
  const [website, setWebsite] = useState<WebsiteDocument[]>([]);
  const [documents, setDocuments] = useState<Contract[]>([]);
  const [listError, setListError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    const page = await api.contracts(1, 100);
    setDocuments(page.items.filter((c) => c.latest_version?.id));
  }, []);

  useEffect(() => {
    Promise.all([api.websiteDocuments().then(setWebsite), loadDocuments()])
      .catch((e: unknown) => setListError(describeError(e)));
  }, [loadDocuments]);

  const choose = onChange;

  const option = (c: Contract) => {
    const chip = documentTypeChip(c.contract_type);
    return { value: c.latest_version!.id, label: chip ? `${c.name} (${chip})` : c.name };
  };
  const ours = documents.filter((c) => c.latest_version?.source === "ORGANIZATION");
  const theirs = documents.filter((c) => c.latest_version?.source !== "ORGANIZATION");

  const title = (
    <header className="ws-context ws-dt__title">
      <span className="ws-context__icon" aria-hidden="true"><IconFileDiff size={18} /></span>
      <div className="ws-cl__titles">
        <h1>Diff-Talk</h1>
        <p className="ws-cl__subtitle">
          Compare our document with a client contract, clause by clause. Colours show
          wording only — whether a difference is acceptable is answered in Findings.
        </p>
      </div>
    </header>
  );

  if (left && right) {
    return (
      <>
        {title}
        <Review key={`${left}|${right}`} left={left} right={right}
                onChange={(side) => (side === "left" ? choose("", right) : choose(left, ""))} />
      </>
    );
  }

  return (
    <>
      {title}
      <section className="ws-dt ws-dt--setup" aria-label="Choose the two documents">
        {listError ? <p className="ws-dt__msg is-error" role="alert">{listError}</p> : null}
        <div className="ws-dt__slots">
          <Slot step={1} label="Our document" source="ORGANIZATION" value={left}
                hint="A website document is always today's version — no upload needed."
                placeholder="Choose our document…"
                groups={[
                  { label: "Website documents",
                    options: website.map((w) => ({ value: w.key, label: w.title })) },
                  { label: "Uploaded by us", options: ours.map(option) },
                ]}
                onChange={(ref) => choose(ref, right)}
                onUploaded={async (ref) => {
                  await loadDocuments().catch(() => undefined);
                  if (ref) choose(ref, right);
                }} />
          <Slot step={2} label="Client contract" source="COUNTERPARTY" value={right}
                hint="The client's paper — any type, any numbering."
                placeholder="Choose the client contract…"
                groups={[{ label: "Client documents in LegalMind", options: theirs.map(option) }]}
                onChange={(ref) => choose(left, ref)}
                onUploaded={async (ref) => {
                  await loadDocuments().catch(() => undefined);
                  if (ref) choose(left, ref);
                }} />
        </div>
        <p className="ws-dt__setupnote">
          The two are lined up clause by clause — even when the client numbers, orders or
          words them differently — and only the differences are shown.
        </p>
      </section>
    </>
  );
}

/** One document slot of the setup: choose from a list, or drop / browse a file. */
function Slot({ step, label, hint, placeholder, value, source, groups, onChange, onUploaded }: {
  step: 1 | 2;
  label: string;
  hint: string;
  placeholder: string;
  value: string;
  /** Declared on an upload here, so it lands on its own side's list (Step 6). */
  source: "ORGANIZATION" | "COUNTERPARTY";
  groups: { label: string; options: { value: string; label: string }[] }[];
  onChange: (ref: string) => void;
  /** null: uploaded, but nothing to select yet (no readable text). */
  onUploaded: (ref: string | null) => Promise<void>;
}) {
  const { can } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const id = `dt-pick-${step}`;
  const chosen = groups.flatMap((g) => g.options).find((o) => o.value === value);

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    try {
      // An ordinary LegalMind document — same storage, parsing, access and audit
      // as any upload. A refused file: the shared helper archives the empty
      // contract it would otherwise leave on the Dashboard.
      const contract = await api.createContract(nameFromFilename(file.name));
      const result = await uploadFirstDocument(contract.id, file);
      await api.declareVersion(result.document_version.id, { source });
      if (result.evidence_count === 0) {
        // Nothing readable to compare: selecting it would only land on an error
        // screen (QA 2026-10-13). Say why, and what to do; the file is kept.
        const status = result.document_version.processing_status;
        await onUploaded(null);
        setError(status === "PENDING" || status === "PROCESSING"
          ? `“${file.name}” is uploaded and its scanned pages are being read. Choose it from the list in a minute or two.`
          : `No text could be read from “${file.name}”. Upload a PDF with selectable text, or the Word (DOCX) file.`);
        return;
      }
      await onUploaded(result.document_version.id);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  const canUpload = can(P.CONTRACT_CREATE) && can(P.DOCUMENT_UPLOAD);
  return (
    <div className={`ws-dt__slot${chosen ? " is-filled" : ""}`}>
      <div className="ws-dt__slothead">
        <span className="ws-dt__stepno" aria-hidden="true">{chosen ? <IconCheck size={14} /> : step}</span>
        <div>
          <label className="ws-dt__slotlabel" htmlFor={id}>{label}</label>
          <p className="ws-dt__hint">{hint}</p>
        </div>
      </div>
      <select id={id} className="ws-dt__select" value={value}
              onChange={(e) => { setError(null); onChange(e.target.value); }}>
        <option value="">{placeholder}</option>
        {groups.filter((g) => g.options.length).map((g) => (
          <optgroup key={g.label} label={g.label}>
            {g.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </optgroup>
        ))}
      </select>
      {canUpload ? (
        <label className={`ws-dt__drop${over ? " is-over" : ""}${busy ? " is-busy" : ""}`}
               onDragOver={(e) => { e.preventDefault(); setOver(true); }}
               onDragLeave={() => setOver(false)}
               onDrop={(e) => {
                 e.preventDefault();
                 setOver(false);
                 const file = e.dataTransfer.files?.[0];
                 if (file && !busy) void upload(file);
               }}>
          <IconUploadCloud size={20} />
          <span>
            {busy ? "Uploading and reading the file…" : (
              <><strong>Upload a file</strong> — drop a PDF or DOCX here, or click to browse</>
            )}
          </span>
          <input type="file" accept=".pdf,.docx,.md,.txt" disabled={busy}
                 className="ws-visually-hidden"
                 onChange={(e) => {
                   const file = e.target.files?.[0];
                   e.target.value = "";
                   if (file) void upload(file);
                 }} />
        </label>
      ) : null}
      {error ? <p className="ws-dt__msg is-error" role="alert">{error}</p> : null}
    </div>
  );
}

/** A compared document, as the review header names it. */
function DocChip({ side, doc, onChange }: {
  side: "Ours" | "Client";
  doc: ComparedDocument;
  onChange: () => void;
}) {
  return (
    <div className="ws-dt__doc">
      <span className={`ws-dt__side is-${side.toLowerCase()}`}>{side}</span>
      <div className="ws-dt__docname">
        {doc.kind === "WEBSITE" ? (
          <a href={doc.url} target="_blank" rel="noreferrer">{doc.title}</a>
        ) : <strong title={doc.title}>{doc.title}</strong>}
        <span className="ws-dt__meta">
          {doc.kind === "WEBSITE"
            ? `Website · as of ${shortDate(doc.effective_from)}`
            : `${doc.filename} · version ${doc.version_number}`}
        </span>
      </div>
      <button type="button" className="ws-dt__change" onClick={onChange}>Change</button>
    </div>
  );
}

function Review({ left, right, onChange }: {
  left: string;
  right: string;
  onChange: (side: "left" | "right") => void;
}) {
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [current, setCurrent] = useState(-1);
  const [showSame, setShowSame] = useState(false);
  const [filter, setFilter] = useState<Filter>("ALL");
  const split = useMinWidth(900) !== false;
  const wide = useMinWidth(1180) !== false;
  const rowRefs = useRef<(HTMLElement | null)[]>([]);
  const headRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const jumpedUntil = useRef(0);
  const rootRef = useRef<HTMLElement>(null);
  // Remembered per pair in this browser, so a reload keeps the reader's place —
  // a convenience only; storage can be absent (private window) and must not break.
  const storeKey = `diff-talk:choices:${left}|${right}`;
  const [choices, setChoices] = useState<Record<string, Choice>>(() => {
    try { return JSON.parse(window.localStorage.getItem(storeKey) ?? "{}"); } catch { return {}; }
  });
  const [copied, setCopied] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => {
    try { window.localStorage.setItem(storeKey, JSON.stringify(choices)); } catch { /* none */ }
  }, [storeKey, choices]);

  useEffect(() => {
    let cancelled = false;
    void loadViewer();          // fetched beside the data, ready when the cards draw
    api.compareDocuments(left, right)
      .then((comparison) => { if (!cancelled) setState({ kind: "ready", comparison }); })
      .catch((e: unknown) => {
        if (!cancelled) setState({ kind: "error", message: describeError(e) });
      });
    return () => { cancelled = true; };
  }, [left, right]);

  // The pinned header's height, for the list's own pinning and for scroll stops.
  useEffect(() => {
    const head = headRef.current, root = rootRef.current;
    if (!head || !root) return;
    const set = () => root.style.setProperty("--dt-head", `${head.offsetHeight}px`);
    set();
    const ro = new ResizeObserver(set);
    ro.observe(head);
    return () => ro.disconnect();
  }, [state.kind]);

  const rows = state.kind === "ready" ? state.comparison.clauses : [];
  const diffs = useMemo(() => rows.flatMap((r, i) => (isDifference(r) ? [i] : [])), [rows]);
  const shown = diffs.filter((i) => filter === "ALL" || rows[i]!.status === filter);
  /** Rows that take a choice: a wording difference, not a clause that only moved. */
  const decidable = diffs.filter((i) => rows[i]!.status !== "UNCHANGED");
  const decided = decidable.filter((i) => choices[rowKey(rows[i]!)]);

  // The changes list follows the reading: the card nearest the top is current.
  useEffect(() => {
    if (state.kind !== "ready") return;
    const io = new IntersectionObserver((entries) => {
      // A jump the reader asked for wins: scroll reports from the jump itself
      // (or an earlier one, J pressed twice) must not move "current" back.
      if (Date.now() < jumpedUntil.current) return;
      const top = entries.filter((e) => e.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (top) setCurrent(Number((top.target as HTMLElement).dataset.row));
    }, { rootMargin: "-30% 0px -60% 0px" });
    rowRefs.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, [state.kind, filter, showSame]);

  function show(target: number) {
    jumpedUntil.current = Date.now() + 700;
    setCurrent(target);
    const el = rowRefs.current[target];
    // Stop clear of what is pinned: the whole header wide, only its bar on a phone
    // (where the header is `display: contents`).
    const head = headRef.current;
    const pinned = head && getComputedStyle(head).display === "contents" ? barRef.current : head;
    const below = pinned ? (parseFloat(getComputedStyle(pinned).top) || 0) + pinned.offsetHeight : 0;
    if (el) el.style.scrollMarginTop = `${below + 12}px`;
    el?.scrollIntoView({ block: "start" });
    el?.focus({ preventScroll: true });
  }

  function go(step: 1 | -1) {
    if (!shown.length) return;
    const at = shown.indexOf(current);
    const next = at === -1 ? (step === 1 ? 0 : shown.length - 1)
      : (at + step + shown.length) % shown.length;
    show(shown[next] ?? 0);
  }

  // J / K — next / previous, as in mail and code review; never while typing.
  const goRef = useRef(go);
  goRef.current = go;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName)
          || t.isContentEditable) return;
      if (e.key === "j") goRef.current(1);
      if (e.key === "k") goRef.current(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  /** A pointer choice moves on to the next undecided difference; a keyboard one
   *  stays put — arrow keys change a radio while the reader is still deciding. */
  function choose(index: number, choice: Choice, advance: boolean) {
    const next = { ...choices, [rowKey(rows[index]!)]: choice };
    setChoices(next);
    setCopied(null);
    if (!advance) return;
    const after = [...decidable.filter((i) => i > index), ...decidable.filter((i) => i < index)]
      .find((i) => !next[rowKey(rows[i]!)]);
    if (after !== undefined) show(after);
  }

  function copyForLegal() {
    if (state.kind !== "ready") return;
    const { left: l, right: r } = state.comparison;
    const text = [`Diff-Talk — ${l.title} (ours) vs ${r.title} (client)`, "",
      ...decidable.map((i) => {
        const row = rows[i]!;
        const pick = choices[rowKey(row)];
        return `• ${clauseName(row.right ?? row.left)} — ${pick
          ? CHOICE_WORDS[row.status as Exclude<Row["status"], "UNCHANGED">][pick]
          : "not decided yet"}`;
      })].join("\n");
    navigator.clipboard.writeText(text)
      .then(() => setCopied({ ok: true, text: "Copied — paste it into an email or chat to Legal." }))
      .catch(() => setCopied({ ok: false, text: "Could not copy here — select the list in Changes and copy it." }));
  }

  if (state.kind === "loading") {
    return (
      <section className="ws-dt" aria-busy="true">
        <p className="ws-dt__loading" role="status">Lining up the clauses…</p>
      </section>
    );
  }
  if (state.kind === "error") {
    return (
      <section className="ws-dt">
        <div className="ws-dt__fail" role="alert">
          <p>{state.message}</p>
          <div>
            <button type="button" className="ws-btn" onClick={() => onChange("left")}>Change our document</button>
            <button type="button" className="ws-btn" onClick={() => onChange("right")}>Change the client contract</button>
          </div>
        </div>
      </section>
    );
  }

  const { summary } = state.comparison;
  const same = rows.length - diffs.length;
  const position = shown.indexOf(current);
  const count = (f: Exclude<Filter, "ALL">) => diffs.filter((i) => rows[i]!.status === f).length;
  const filters: [Filter, string, number][] = ([["ALL", "All", diffs.length],
    ["CHANGED", "Changed", count("CHANGED")], ["ADDED", "Added", count("ADDED")],
    ["REMOVED", "Missing", count("REMOVED")]] as [Filter, string, number][])
    .filter(([f, , n]) => f === "ALL" || n > 0);

  const changesList = (
    <nav className="ws-dt__changes" aria-label="Changes">
      <div className="ws-dt__changeshead">
        <h2>Changes <span>{diffs.length}</span></h2>
        {filters.length > 2 ? (
          <div className="ws-dt__filters" role="group" aria-label="Show">
            {filters.map(([f, name, n]) => (
              <button key={f} type="button" aria-pressed={filter === f}
                      className={filter === f ? "is-on" : undefined}
                      onClick={() => setFilter(f)}>
                {name} <span>{n}</span>
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <ol>
        {shown.map((i, n) => {
          const row = rows[i]!;
          const kind = KIND[row.status];
          const pick = choices[rowKey(row)];
          const words = row.status === "UNCHANGED" ? null : CHOICE_WORDS[row.status];
          return (
            <li key={i}>
              <button type="button" aria-current={i === current ? "true" : undefined}
                      className={`ws-dt__change-item is-${kind.tone}${i === current ? " is-current" : ""}`}
                      onClick={() => show(i)}>
                <span className="ws-dt__num">{n + 1}</span>
                <span className="ws-dt__itemtext">
                  <span className="ws-dt__itemname">{clauseName(row.right ?? row.left)}</span>
                  <span className="ws-dt__itemmeta">
                    <kind.Icon size={12} /> {row.moved && row.status === "UNCHANGED" ? "Moved" : kind.short}
                    {words ? (pick
                      ? <em className="is-done"> · {words[pick]}</em>
                      : <em className="is-open"> · Not decided</em>) : null}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      {same > 0 ? (
        <label className="ws-dt__same">
          <input type="checkbox" checked={showSame} onChange={(e) => setShowSame(e.target.checked)} />
          <span><IconCheck size={13} /> {same} clause{same === 1 ? " reads" : "s read"} the same — show {same === 1 ? "it" : "them"}</span>
        </label>
      ) : null}
    </nav>
  );

  return (
    <section className="ws-dt ws-dt--review" ref={rootRef}
             aria-label="Comparison of our document with the client contract">
      <div className="ws-dt__head" ref={headRef}>
        <div className="ws-dt__docs">
          <DocChip side="Ours" doc={state.comparison.left} onChange={() => onChange("left")} />
          <span className="ws-dt__vs" aria-hidden="true">vs</span>
          <DocChip side="Client" doc={state.comparison.right} onChange={() => onChange("right")} />
        </div>
        <div className="ws-dt__bar" ref={barRef}>
          {decidable.length ? (
            <div className="ws-dt__progress">
              <progress max={decidable.length} value={decided.length} aria-label="Differences decided" />
              <span>{decided.length === decidable.length ? "All decided"
                : `${decided.length} of ${decidable.length} decided`}</span>
            </div>
          ) : (
            <p className="ws-dt__progress">
              <IconCheck size={16} /> {summary.UNCHANGED ? "Every clause reads the same." : "Nothing to compare."}
            </p>
          )}
          {shown.length ? (
            <div className="ws-dt__step">
              <button type="button" className="ws-dt__iconbtn" onClick={() => go(-1)}
                      aria-label="Previous difference" title="Previous difference (K)">
                <IconArrowUp size={16} />
              </button>
              <span role="status" aria-atomic="true">
                {position === -1 ? `${shown.length} difference${shown.length === 1 ? "" : "s"}`
                  : <><span className="ws-dt__long">Difference </span>{position + 1} of {shown.length}</>}
              </span>
              <button type="button" className="ws-dt__iconbtn" onClick={() => go(1)}
                      aria-label="Next difference" title="Next difference (J)">
                <IconArrowDown size={16} />
              </button>
            </div>
          ) : null}
          {decidable.length ? (
            <button type="button" className="ws-dt__copy" onClick={copyForLegal}>
              <IconCopy size={15} /> Copy for Legal
            </button>
          ) : null}
        </div>
        {copied ? (
          <p className={`ws-dt__msg ${copied.ok ? "is-ok" : "is-error"}`} role="status">
            {copied.text}
            <button type="button" className="ws-dt__dismiss" aria-label="Dismiss" onClick={() => setCopied(null)}>
              <IconX size={14} />
            </button>
          </p>
        ) : null}
      </div>

      {([["Our document", state.comparison.left], ["The client contract", state.comparison.right]] as const)
        .map(([who, doc]) => doc.kind === "DOCUMENT" && doc.unread_pages.length ? (
          // Said once, above the changes — not pinned on screen the whole review.
          <p key={who} className="ws-dt__notice">
            {who}: {doc.unread_pages.length === 1 ? `page ${doc.unread_pages[0]} has` : `pages ${doc.unread_pages.join(", ")} have`}{" "}
            no readable text and {doc.unread_pages.length === 1 ? "is" : "are"} not compared — often
            a blank page; if it holds a scan or picture, check it in the file.
          </p>
        ) : null)}

      <div className="ws-dt__body">
        {wide ? <aside className="ws-dt__rail">{changesList}</aside> : (
          <details className="ws-dt__drawer">
            <summary>Changes ({diffs.length}) — the list</summary>
            {changesList}
          </details>
        )}

        <div className="ws-dt__main">
          {split ? null : (
            <p className="ws-dt__legend"><span>− our document</span><span>+ client contract</span></p>
          )}
          <ol className="ws-dt__cards">
            {rows.map((row, i) => {
              const isDiff = isDifference(row);
              if (isDiff ? !shown.includes(i) : !showSame) return null;
              const kind = KIND[row.status];
              const words = row.status === "UNCHANGED" ? null : CHOICE_WORDS[row.status];
              const pick = choices[rowKey(row)];
              const n = shown.indexOf(i);
              return (
                <li key={i} ref={(el) => { rowRefs.current[i] = el; }} tabIndex={-1} data-row={i}
                    className={`ws-dt__card is-${kind.tone}${i === current ? " is-current" : ""}`}
                    aria-labelledby={`dt-card-${i}`}>
                  <div className="ws-dt__cardhead" id={`dt-card-${i}`}>
                    {n >= 0 ? <span className="ws-dt__num">{n + 1}</span> : null}
                    <div className="ws-dt__cardtitle">
                      <h3>
                        {row.left && row.right
                          && clauseName(row.left).toLowerCase() !== clauseName(row.right).toLowerCase()
                          ? <span className="ws-dt__was">{clauseName(row.left)} → </span> : null}
                        {clauseName(row.right ?? row.left)}
                      </h3>
                      <p className="ws-dt__cardmeta">
                        <span className={`ws-dt__kind is-${kind.tone}`}><kind.Icon size={13} /> {kind.label}</span>
                        {row.status === "CHANGED" ? <span>{changedSentences(row)} differ</span> : null}
                        {row.moved ? <span>In a different place</span> : null}
                        {row.right?.page ? <span>Client contract p. {row.right.page}</span> : null}
                      </p>
                    </div>
                  </div>
                  {split && row.status !== "UNCHANGED" ? (
                    <div className="ws-dt__cols" aria-hidden="true">
                      <span className={pick === "ours" ? "is-chosen" : undefined}>
                        Our document{pick === "ours" ? <IconCheck size={13} /> : null}
                      </span>
                      <span className={pick === "theirs" ? "is-chosen" : undefined}>
                        Client contract{pick === "theirs" ? <IconCheck size={13} /> : null}
                      </span>
                    </div>
                  ) : null}
                  {row.status === "UNCHANGED" && !row.moved ? (
                    <p className="ws-dt__sametext">{sentences((row.right ?? row.left)!.text)}</p>
                  ) : <ClauseBody row={row} split={split} />}
                  {words ? (
                    // The choice sits where the eye ends after reading the difference.
                    <fieldset className="ws-dt__choice">
                      <legend>Your choice</legend>
                      <span className="ws-dt__opts">
                        {(["ours", "theirs"] as const).map((c) => (
                          <label key={c} className={`ws-dt__opt${pick === c ? " is-on" : ""}`}>
                            <input type="radio" name={`dt-choice-${i}`} value={c} checked={pick === c}
                                   onChange={() => choose(i, c, false)}
                                   // detail > 0: a pointer click, not an arrow key.
                                   onClick={(e) => { if (e.detail > 0) choose(i, c, true); }} />
                            {words[c]}
                          </label>
                        ))}
                      </span>
                      {pick ? null : <span className="ws-dt__undecided">Not decided yet</span>}
                    </fieldset>
                  ) : null}
                </li>
              );
            })}
          </ol>
          {decidable.length ? (
            <p className="ws-dt__footnote">
              Your choices are about wording only. The final contract still goes through
              LegalMind&rsquo;s review, where Legal decides.
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function ClauseBody({ row, split }: { row: Row; split: boolean }) {
  if (row.status === "ADDED" || row.status === "REMOVED") {
    const present = (row.left ?? row.right)!;
    return (
      <div className={`ws-dt__single is-${row.status === "ADDED" ? "right" : "left"}`}>
        <p className="ws-dt__text">{sentences(present.text)}</p>
        <p className="ws-dt__absent">
          {row.status === "ADDED" ? "Not in our document" : "Not in the client contract"}
        </p>
      </div>
    );
  }
  return (
    <div className={split ? undefined : "ws-dt__unified"}>
      <ReactDiffViewer
        oldValue={sentences(row.left!.text)}
        newValue={sentences(row.right!.text)}
        splitView={split}
        compareMethod={WORDS}
        hideLineNumbers
        hideSummary
        disableWorker
        // The changed sentences first, one either side for context; the rest fold
        // behind a plain-words line (the library's default is a code "@@" header).
        showDiffOnly
        extraLinesSurroundingDiff={1}
        codeFoldMessageRenderer={(n) => (
          <span className="ws-dt__fold">Show {n} matching sentence{n === 1 ? "" : "s"}</span>
        )}
        styles={viewerStyles(split)}
      />
    </div>
  );
}
