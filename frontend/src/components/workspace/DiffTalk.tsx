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
import { useEffect, useMemo, useRef, useState } from "react";
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
import { IconFileDiff } from "./icons";
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
  loading: () => <p className="ws-diff__text">Loading the comparison…</p>,
});
/** `DiffMethod.WORDS`, without importing the enum's module eagerly. It must be
 *  the library's own method name: given a function instead, the viewer turns
 *  word highlighting off altogether (`shouldHighlightWordDiff`, found 2026-10-12). */
const WORDS = "diffWords" as unknown as DiffMethod;

type Row = DocumentComparison["clauses"][number];
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
  if (c.ref && title) return `${c.ref}. ${title}`;
  return c.ref ? `Clause ${c.ref}` : title || "Opening text";
}

const STATUS: Record<Row["status"], { label: string; tone: "same" | "diff" }> = {
  UNCHANGED: { label: "Same wording", tone: "same" },
  CHANGED: { label: "Wording differs", tone: "diff" },
  ADDED: { label: "Only in the client contract", tone: "diff" },
  REMOVED: { label: "Missing from the client contract", tone: "diff" },
};

const isDifference = (r: Row) => r.status !== "UNCHANGED" || r.moved;

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
  wordDiff: { padding: "1px 0", borderRadius: "2px" },
  // Hidden, not removed: the marker is a table cell, and dropping it shifts the
  // text into the gutter column.
  marker: split ? { width: "8px", padding: 0, visibility: "hidden" as const }
    : { width: "22px", padding: "0 4px", color: "var(--ws-error)" },
});

/** The Diff-Talk page: a choice for each side, then the comparison. Both sides
 *  live in the URL, so a comparison can be linked and Back works. */
export function DiffTalkPage({ initialLeft, initialRight, onChange }: {
  initialLeft: string;
  initialRight: string;
  onChange: (left: string, right: string) => void;
}) {
  const [left, setLeft] = useState(initialLeft);
  const [right, setRight] = useState(initialRight);
  const [website, setWebsite] = useState<WebsiteDocument[]>([]);
  const [documents, setDocuments] = useState<Contract[]>([]);
  const [listError, setListError] = useState<string | null>(null);

  async function loadDocuments() {
    const page = await api.contracts(1, 100);
    setDocuments(page.items.filter((c) => c.latest_version?.id));
  }

  useEffect(() => {
    Promise.all([api.websiteDocuments().then(setWebsite), loadDocuments()])
      .catch((e: unknown) => setListError(describeError(e)));
  }, []);

  function choose(nextLeft: string, nextRight: string) {
    setLeft(nextLeft);
    setRight(nextRight);
    onChange(nextLeft, nextRight);
  }

  const option = (c: Contract) => {
    const chip = documentTypeChip(c.contract_type);
    return { value: c.latest_version!.id, label: chip ? `${c.name} (${chip})` : c.name };
  };
  const ours = documents.filter((c) => c.latest_version?.source === "ORGANIZATION");
  const theirs = documents.filter((c) => c.latest_version?.source !== "ORGANIZATION");

  return (
    <>
    <div className="ws-context">
      <span className="ws-context__icon" aria-hidden="true"><IconFileDiff size={18} /></span>
      <div className="ws-cl__titles">
        <h1>Diff-Talk</h1>
        <p className="ws-cl__subtitle">
          Compare our document with a client contract, clause by clause. Colours show
          wording only — whether a difference is acceptable is answered in Findings.
        </p>
      </div>
    </div>
    <section className="ws-diff" aria-label="Compare our document with a client contract">
      <div className="ws-diff__choose">
        <SidePicker
          label="Our document"
          placeholder="Choose our document…"
          value={left}
          source="ORGANIZATION"
          groups={[
            { label: "Website documents",
              options: website.map((w) => ({ value: w.key, label: w.title })) },
            { label: "Uploaded by us", options: ours.map(option) },
          ]}
          onChange={(ref) => choose(ref, right)}
          onUploaded={async (ref) => {
            await loadDocuments().catch(() => undefined);
            choose(ref, right);
          }}
        />
        <SidePicker
          label="Client contract"
          placeholder="Choose the client contract…"
          value={right}
          source="COUNTERPARTY"
          groups={[{ label: "Client documents in LegalMind", options: theirs.map(option) }]}
          onChange={(ref) => choose(left, ref)}
          onUploaded={async (ref) => {
            await loadDocuments().catch(() => undefined);
            choose(left, ref);
          }}
        />
      </div>
      {listError ? <p className="ws-diff__note ws-diff__note--error" role="alert">{listError}</p> : null}
      {left && right ? (
        <Comparison key={`${left}|${right}`} left={left} right={right} />
      ) : (
        <div className="ws-diff__empty">
          <IconFileDiff size={28} />
          <p>
            {left || right
              ? `Now choose ${left ? "the client contract" : "our document"}, or upload it.`
              : "Choose our document and the client contract, or upload either."}
          </p>
          <p className="ws-diff__meta">
            The two are lined up clause by clause, even when they number or order
            their clauses differently.
          </p>
        </div>
      )}
    </section>
    </>
  );
}

function SidePicker({ label, placeholder, value, source, groups, onChange, onUploaded }: {
  label: string;
  placeholder: string;
  value: string;
  /** Declared on an upload here, so it lands on its own side's list (Step 6). */
  source: "ORGANIZATION" | "COUNTERPARTY";
  groups: { label: string; options: { value: string; label: string }[] }[];
  onChange: (ref: string) => void;
  onUploaded: (ref: string) => Promise<void>;
}) {
  const { can } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const id = `diff-pick-${source.toLowerCase()}`;

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      // An ordinary LegalMind document — same storage, parsing, access and audit
      // as any upload; it appears on the Dashboard like one.
      const contract = await api.createContract(nameFromFilename(file.name));
      // Refused file: the shared helper archives the empty contract it would
      // otherwise leave on the Dashboard ("notes", found in the 2026-10-12 audit).
      const result = await uploadFirstDocument(contract.id, file);
      await api.declareVersion(result.document_version.id, { source });
      await onUploaded(result.document_version.id);
      setDone(result.evidence_count
        ? `Uploaded “${file.name}” and selected it.`
        : `Uploaded “${file.name}”, but no text could be read from it yet — scanned pages are still being read.`);
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ws-diff__pick">
      <label className="ws-diff__side" htmlFor={id}>{label}</label>
      <div className="ws-diff__pickrow">
        <select id={id} value={value}
                onChange={(e) => { setDone(null); setError(null); onChange(e.target.value); }}>
          <option value="">{placeholder}</option>
          {groups.filter((g) => g.options.length).map((g) => (
            <optgroup key={g.label} label={g.label}>
              {g.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </optgroup>
          ))}
        </select>
        {can(P.CONTRACT_CREATE) && can(P.DOCUMENT_UPLOAD) ? (
          <label className={`ws-diff__upload${busy ? " is-busy" : ""}`}>
            {busy ? "Uploading…" : "Upload"}
            <input type="file" accept=".pdf,.docx,.md,.txt" disabled={busy}
                   className="ws-visually-hidden"
                   onChange={(e) => {
                     const file = e.target.files?.[0];
                     e.target.value = "";
                     if (file) void upload(file);
                   }} />
          </label>
        ) : null}
      </div>
      {error ? <p className="ws-diff__note ws-diff__note--error" role="alert">{error}</p> : null}
      {done ? <p className="ws-diff__note ws-diff__note--ok" role="status">{done}</p> : null}
    </div>
  );
}

function docMeta(d: ComparedDocument): React.ReactNode {
  return d.kind === "WEBSITE" ? (
    <>
      <a href={d.url} target="_blank" rel="noreferrer">{d.title}</a>
      <span className="ws-diff__meta">website, as of {shortDate(d.effective_from)}</span>
    </>
  ) : (
    <>
      <strong>{d.title}</strong>
      <span className="ws-diff__meta">version {d.version_number} · {d.filename}</span>
      {d.unread_pages.length ? (
        <span className="ws-diff__warn">
          {d.unread_pages.length === 1 ? `Page ${d.unread_pages[0]} has` : `Pages ${d.unread_pages.join(", ")} have`}{" "}
          no readable text and {d.unread_pages.length === 1 ? "is" : "are"} not compared —
          often a blank page; if it holds a scan or picture, check it in the file.
        </span>
      ) : null}
    </>
  );
}

function Comparison({ left, right }: { left: string; right: string }) {
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [current, setCurrent] = useState(-1);
  const [showSame, setShowSame] = useState(false);
  const split = useMinWidth(900) !== false;
  const rowRefs = useRef<(HTMLElement | null)[]>([]);
  const navRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    void loadViewer();          // fetched beside the data, ready when the rows draw
    api.compareDocuments(left, right)
      .then((comparison) => { if (!cancelled) setState({ kind: "ready", comparison }); })
      .catch((e: unknown) => {
        if (!cancelled) setState({ kind: "error", message: describeError(e) });
      });
    return () => { cancelled = true; };
  }, [left, right]);

  const rows = state.kind === "ready" ? state.comparison.clauses : [];
  const diffs = useMemo(() => rows.flatMap((r, i) => (isDifference(r) ? [i] : [])), [rows]);

  function go(step: 1 | -1) {
    if (!diffs.length) return;
    const at = diffs.indexOf(current);
    const next = at === -1 ? (step === 1 ? 0 : diffs.length - 1)
      : (at + step + diffs.length) % diffs.length;
    const target = diffs[next] ?? 0;
    setCurrent(target);
    const el = rowRefs.current[target];
    // Stop clear of whatever is pinned above (the whole bar wide, the nav narrow).
    const pinned = navRef.current?.closest(".ws-diff")?.querySelector<HTMLElement>(
      split ? ".ws-diff__bar" : ".ws-diff__nav");
    const below = pinned
      ? (parseFloat(getComputedStyle(pinned).top) || 0) + pinned.offsetHeight : 0;
    if (el) el.style.scrollMarginTop = `${below + 12}px`;
    el?.scrollIntoView({ block: "start" });
    el?.focus({ preventScroll: true });
  }

  if (state.kind === "loading") {
    return <p className="ws-diff__note" role="status">Lining up the clauses…</p>;
  }
  if (state.kind === "error") {
    return <p className="ws-diff__note ws-diff__note--error" role="alert">{state.message}</p>;
  }

  const { summary } = state.comparison;
  const hiddenSame = rows.length - diffs.length;
  const position = diffs.indexOf(current);
  const counts = [
    summary.CHANGED && `${summary.CHANGED} worded differently`,
    summary.REMOVED && `${summary.REMOVED} missing from the client contract`,
    summary.ADDED && `${summary.ADDED} only in the client contract`,
    summary.MOVED && `${summary.MOVED} in a different place`,
  ].filter(Boolean);

  return (
    <>
      <div className="ws-diff__bar">
        <div className="ws-diff__docs">
          <p className="ws-diff__doc">{docMeta(state.comparison.left)}</p>
          <p className="ws-diff__doc">{docMeta(state.comparison.right)}</p>
        </div>
        <div className="ws-diff__summary">
          <p className="ws-diff__counts">
            {diffs.length === 0
              ? `Every clause has the same wording (${summary.UNCHANGED}).`
              : <><strong>{diffs.length} difference{diffs.length === 1 ? "" : "s"}</strong>{`: ${counts.join(", ")}. ${summary.UNCHANGED === 0 ? "No clause reads" : `${summary.UNCHANGED} clause${summary.UNCHANGED === 1 ? " reads" : "s read"}`} the same.`}</>}
          </p>
          <div className="ws-diff__nav" ref={navRef}>
            {diffs.length > 0 ? (
              <div className="ws-diff__step">
                <button type="button" className="ws-btn" onClick={() => go(-1)}>
                  Previous<span className="ws-diff__long"> difference</span>
                </button>
                <span role="status" aria-atomic="true" className="ws-diff__pos">
                  {position === -1 ? `${diffs.length} to review`
                    : `${position + 1} of ${diffs.length}`}
                </span>
                <button type="button" className="ws-btn" onClick={() => go(1)}>
                  Next<span className="ws-diff__long"> difference</span>
                </button>
              </div>
            ) : null}
            {summary.UNCHANGED > 0 ? (
              <label className="ws-diff__toggle">
                <input type="checkbox" checked={showSame}
                       onChange={(e) => setShowSame(e.target.checked)} />
                Show matching clauses
              </label>
            ) : null}
            {split ? null : (
              <p className="ws-diff__legend">
                <span>− our document</span> <span>+ client contract</span>
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Differences first (owner, 2026-10-12: "within a second check the diff"):
          matching clauses stay out of the way until asked for. */}
      {!showSame && hiddenSame > 0 ? (
        <p className="ws-diff__hidden">
          {hiddenSame} clause{hiddenSame === 1 ? " reads" : "s read"} the same in both
          documents and {hiddenSame === 1 ? "is" : "are"} hidden.{" "}
          <button type="button" className="ws-escalate__link" onClick={() => setShowSame(true)}>
            Show {hiddenSame === 1 ? "it" : "them"}
          </button>
        </p>
      ) : null}
      <ol className="ws-diff__list">
        {rows.map((row, i) => {
          if (!showSame && !isDifference(row)) return null;
          const status = STATUS[row.status];
          const open = row.status !== "UNCHANGED" || showSame;
          return (
            <li key={i} ref={(el) => { rowRefs.current[i] = el; }} tabIndex={-1}
                className={`ws-diff__row ws-diff__row--${status.tone}`
                  + (i === current ? " is-current" : "")}
                aria-labelledby={`diff-row-${i}`}
                onClick={() => isDifference(row) && setCurrent(i)}>
              <div className="ws-diff__head" id={`diff-row-${i}`}>
                <span className="ws-diff__status">{status.label}</span>
                {row.status === "CHANGED" ? (
                  <span className="ws-diff__moved">{changedSentences(row)}</span>
                ) : null}
                {row.moved ? <span className="ws-diff__moved">in a different place</span> : null}
                <span className="ws-diff__names">
                  {row.left && row.right && clauseName(row.left) !== clauseName(row.right) ? (
                    <>
                      <span>{clauseName(row.left)}</span>
                      <span className="ws-diff__vs" aria-label="compared with"> · </span>
                    </>
                  ) : null}
                  <span>{clauseName(row.right ?? row.left)}</span>
                  {row.right?.page ? <span className="ws-diff__meta"> page {row.right.page}</span> : null}
                </span>
              </div>
              {open && split ? (
                <div className="ws-diff__cols" aria-hidden="true">
                  <span>Our document</span><span>Client contract</span>
                </div>
              ) : null}
              {open ? <ClauseBody row={row} split={split} /> : null}
            </li>
          );
        })}
      </ol>
    </>
  );
}

function ClauseBody({ row, split }: { row: Row; split: boolean }) {
  if (row.status === "ADDED" || row.status === "REMOVED") {
    const present = (row.left ?? row.right)!;
    return (
      <div className={`ws-diff__single ws-diff__single--${row.status === "ADDED" ? "right" : "left"}`}>
        <p className="ws-diff__text">{sentences(present.text)}</p>
        <p className="ws-diff__absent">
          {row.status === "ADDED" ? "Not in our document" : "Not in the client contract"}
        </p>
      </div>
    );
  }
  return (
    <div className={split ? undefined : "ws-diff__unified"}>
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
        <span className="ws-diff__fold">Show {n} matching sentence{n === 1 ? "" : "s"}</span>
      )}
      styles={viewerStyles(split)}
    />
    </div>
  );
}
