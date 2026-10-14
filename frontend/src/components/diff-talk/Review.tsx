"use client";

/**
 * Diff-Talk's REVIEW mode (design plan: docs/architecture/diff-talk/DESIGN_PLAN.md).
 *
 * One pinned bar (the two documents, decided count, ↑ ↓, Copy for Legal), the list of
 * differences beside the comparison — a panel on a tablet, a sheet on a phone — and
 * one flat block per difference: its choice beside its heading, the changed sentences
 * first, a decided block folded to one line.
 *
 * WORDING ONLY. Red marks our words, green the client's — a key, never a verdict: the
 * chrome stays neutral and no screen says whether a difference is acceptable (33.16).
 */

import dynamic from "next/dynamic";
import {
  type ReactNode, useCallback, useEffect, useEffectEvent, useMemo, useRef, useState,
} from "react";
import type { DiffMethod } from "react-diff-viewer-continued";

import { shortDate } from "@/components/clients/model";
import {
  IconArrowDown, IconArrowUp, IconCheck, IconCopy, IconExternal, IconFileMinus,
  IconFilePlus, IconList, IconReplace, IconX,
} from "@/components/workspace/icons";
import { useMinWidth } from "@/components/workspace/WorkspaceLayout";
import { api, describeError } from "@/lib/api";
import type { ComparedDocument, DocumentComparison } from "@/lib/types";
import {
  CHOICE_WORDS, type Choice, type Filter, type Row, changedSentences, choicesForLegal,
  clauseName, isDecidable, isDifference, isRewritten, rowKey, sentences,
} from "./text";
import { useChoices } from "./useChoices";
import { useReviewNavigation } from "./useReviewNavigation";

/** The viewer loads only when a comparison renders — fetched beside the data. */
const loadViewer = () => import("react-diff-viewer-continued");
const ReactDiffViewer = dynamic(loadViewer, {
  ssr: false,
  loading: () => <p className="ws-dt__text">Loading the comparison…</p>,
});
/** `DiffMethod.WORDS` without importing the enum eagerly. It must be the library's
 *  own method name: given a function, the viewer turns word marks off (2026-10-12). */
const WORDS = "diffWords" as unknown as DiffMethod;

/** Each kind of difference as the reader names it — text and icon, never colour. */
const KIND: Record<Row["status"], { label: string; short: string;
  Icon: (p: { size?: number }) => React.ReactElement }> = {
  UNCHANGED: { label: "Same wording", short: "Same", Icon: IconCheck },
  CHANGED: { label: "Wording changed", short: "Changed", Icon: IconReplace },
  ADDED: { label: "Added by the client", short: "Added", Icon: IconFilePlus },
  REMOVED: { label: "Missing from the client's contract", short: "Missing", Icon: IconFileMinus },
};

type Load =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; comparison: DocumentComparison };

/** Where a choice came from: a click or a 1/2 key folds the block and moves on; an
 *  arrow key on the radios keeps it open — the reader is still deciding. */
type How = "move" | "stay";
/** Changes only (the differences) or Full documents (every clause, both sides). */
type View = "changes" | "full";

export function Review({ left, right, onChange }: {
  left: string;
  right: string;
  onChange: (side: "left" | "right") => void;
}) {
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [view, setView] = useState<View>("changes");
  const full = view === "full";
  const [filter, setFilter] = useState<Filter>("ALL");
  const { choices, byKey, canChoose, loaded: choicesLoaded, error: choiceError,
          choose: saveChoice } = useChoices(left, right);
  /** The copy's outcome; on failure, the list itself, to select and copy by hand. */
  const [copied, setCopied] = useState<{ ok: boolean; text: string; list?: string } | null>(null);
  /** Decided blocks the reader reopened, and the one whose choice gets focus. */
  const [reopened, setReopened] = useState<ReadonlySet<string>>(new Set());
  const [focusKey, setFocusKey] = useState<string | null>(null);
  const wide = useMinWidth(1180) !== false;   // the list as a column
  const split = useMinWidth(768) !== false;   // ours | client side by side
  const headRef = useRef<HTMLElement>(null);
  const rootRef = useRef<HTMLElement>(null);
  const sheetRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    let cancelled = false;
    void loadViewer();
    api.compareDocuments(left, right)
      .then((comparison) => { if (!cancelled) setState({ kind: "ready", comparison }); })
      .catch((e: unknown) => {
        if (!cancelled) setState({ kind: "error", message: describeError(e) });
      });
    return () => { cancelled = true; };
  }, [left, right]);

  // The pinned bar's height as a CSS variable: the list, the column headings and
  // every block's scroll stop sit below it. Ready only once BOTH loads are in: the
  // skeleton shows until then, and an effect that ran on it never re-ran (review,
  // 2026-10-14 — the offsets fell back to 64px and the list stopped following).
  const ready = state.kind === "ready" && choicesLoaded;
  useEffect(() => {
    const head = headRef.current, root = rootRef.current;
    if (!head || !root) return;
    const set = () => root.style.setProperty("--dt-head", `${head.offsetHeight}px`);
    set();
    const ro = new ResizeObserver(set);
    ro.observe(head);
    return () => ro.disconnect();
  }, [ready, split]);

  const rows = useMemo(() => (state.kind === "ready" ? state.comparison.clauses : []), [state]);
  const diffs = useMemo(() => rows.flatMap((r, i) => (isDifference(r) ? [i] : [])), [rows]);
  const shown = useMemo(() => diffs.filter((i) => filter === "ALL" || rows[i]?.status === filter),
                        [diffs, filter, rows]);
  const decidable = diffs.filter((i) => rows[i] && isDecidable(rows[i]));
  const decided = decidable.filter((i) => rows[i] && choices[rowKey(rows[i])]);

  const label = useCallback((i: number) => clauseName(rows[i]?.right ?? rows[i]?.left ?? null),
                            [rows]);
  const nav = useReviewNavigation({ order: shown, ready, label, watch: [filter, view] });

  function choose(index: number, choice: Choice, how: How) {
    const row = rows[index];
    if (!canChoose || !row || !isDecidable(row)) return;
    const key = rowKey(row);
    const next = { ...choices, [key]: choice };
    saveChoice(key, choice);
    setCopied(null);
    setFocusKey(null);
    setReopened((open) => {
      const out = new Set(open);
      if (how === "stay") out.add(key); else out.delete(key);
      return out;
    });
    const done = decidable.filter((i) => rows[i] && next[rowKey(rows[i])]).length;
    nav.setAnnouncement(`${CHOICE_WORDS[row.status][choice]}. ${done} of ${decidable.length} decided.`);
    if (how === "stay") return;
    const after = [...decidable.filter((i) => i > index), ...decidable.filter((i) => i < index)]
      .find((i) => rows[i] && !next[rowKey(rows[i])]);
    if (after !== undefined) nav.show(after);
  }

  function reopen(key: string) {
    setReopened((open) => new Set(open).add(key));
    setFocusKey(key);
  }

  // 1 / 2 choose for the current difference, beside J / K — never while typing.
  const onKey = useEffectEvent((e: KeyboardEvent) => {
    const t = e.target as HTMLElement;
    if (e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName)
        || t.isContentEditable || t.closest("dialog") || (e.key !== "1" && e.key !== "2")) return;
    choose(nav.current, e.key === "1" ? "ours" : "theirs", "move");
  });
  useEffect(() => {
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function copyForLegal() {
    if (state.kind !== "ready") return;
    const { left: l, right: r } = state.comparison;
    const list = choicesForLegal(l.title, r.title, rows, choices);
    // No clipboard API at all (a plain-http address) throws before any promise —
    // so it runs inside one, and every failure shows the list to copy by hand.
    Promise.resolve().then(() => navigator.clipboard.writeText(list))
      .then(() => setCopied({ ok: true, text: "Copied — paste it into an email or chat to Legal." }))
      .catch(() => setCopied({ ok: false, list,
        text: "This browser blocked copying. The list is selected below — press Ctrl+C (⌘C on a Mac)." }));
  }

  if (state.kind === "loading" || !choicesLoaded) return <Skeleton split={split} />;
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

  const { comparison } = state;
  const same = rows.length - diffs.length;
  const allDone = decidable.length > 0 && decided.length === decidable.length;
  const at = shown.indexOf(nav.current);
  const position = at === -1 ? `${shown.length} difference${shown.length === 1 ? "" : "s"}`
    : `${at + 1} of ${shown.length}`;
  const progress = allDone ? `All ${decidable.length} decided`
    : `${decided.length} of ${decidable.length} decided`;
  const pick = (i: number) => {
    sheetRef.current?.close();
    nav.show(i);
  };
  const list = (
    <ChangesList rows={rows} diffs={diffs} shown={shown} same={same} current={nav.current}
                 filter={filter} onFilter={setFilter} full={full} onFull={() => { setView("full"); setFilter("ALL"); }}
                 choices={choices} onPick={pick} />
  );
  const viewSwitch = (
    <div className="ws-dt__view" role="group" aria-label="Show">
      {([["changes", "Changes only"], ["full", "Full documents"]] as const).map(([v, name]) => (
        <button key={v} type="button" aria-pressed={view === v}
                className={view === v ? "is-on" : undefined}
                onClick={() => { setView(v); if (v === "full") setFilter("ALL"); }}>
          {name}
        </button>
      ))}
    </div>
  );
  const copyButton = (iconOnly: boolean) => (
    <button type="button" className={`ws-dt__copy${allDone ? " is-ready" : ""}`}
            onClick={copyForLegal} aria-label={iconOnly ? "Copy for Legal" : undefined}
            title="Copy your choices as a list for Legal">
      <IconCopy size={16} />{iconOnly ? null : " Copy for Legal"}
    </button>
  );

  return (
    <section className={`ws-dt ws-dt--review${split ? "" : " is-phone"}`} ref={rootRef}
             aria-label="Comparison of our document with the client contract">
      {/* What a screen reader hears: moves and choices only, never plain scrolling. */}
      <p className="ws-visually-hidden" role="status" aria-live="polite">{nav.announcement}</p>

      <header className="ws-dt__head" ref={headRef}>
        <div className="ws-dt__docs">
          <DocChip side="ours" doc={comparison.left} onChange={() => onChange("left")} />
          <DocChip side="client" doc={comparison.right} onChange={() => onChange("right")} />
        </div>
        {split ? null : viewSwitch}
        {split ? (
          <div className="ws-dt__bar">
            {viewSwitch}
            {wide ? null : (
              <button type="button" className="ws-dt__listbtn"
                      onClick={() => sheetRef.current?.showModal()}>
                <IconList size={16} /> {diffs.length} change{diffs.length === 1 ? "" : "s"}
              </button>
            )}
            {decidable.length ? (
              <div className="ws-dt__progress">
                <progress max={decidable.length} value={decided.length} aria-label="Differences decided" />
                <span>{progress}</span>
              </div>
            ) : null}
            {shown.length ? (
              <div className="ws-dt__step">
                <button type="button" className="ws-dt__iconbtn" onClick={() => nav.go(-1)}
                        aria-label="Previous difference" title="Previous difference (K)">
                  <IconArrowUp size={16} />
                </button>
                <span className="ws-dt__pos">
                  {at === -1 ? position : <><span className="ws-visually-hidden">Difference </span>{position}</>}
                </span>
                <button type="button" className="ws-dt__iconbtn" onClick={() => nav.go(1)}
                        aria-label="Next difference" title="Next difference (J)">
                  <IconArrowDown size={16} />
                </button>
              </div>
            ) : null}
            {decidable.length ? copyButton(!wide && !allDone) : null}
          </div>
        ) : null}
      </header>

      {choiceError ? <p className="ws-dt__msg ws-dt__notice is-error" role="alert">{choiceError}</p> : null}
      {!canChoose && decidable.length && !choiceError ? (
        <p className="ws-dt__notice">
          You can read the choices made on these two documents. Only their owner can change them.
        </p>
      ) : null}
      {copied ? (
        <div className={`ws-dt__msg ws-dt__toast ${copied.ok ? "is-ok" : "is-error"}`} role="status">
          <p>{copied.text}</p>
          <button type="button" className="ws-dt__dismiss" aria-label="Dismiss" onClick={() => setCopied(null)}>
            <IconX size={14} />
          </button>
          {copied.list ? (
            <textarea className="ws-dt__copytext" readOnly value={copied.list} aria-label="Your choices for Legal"
                      rows={Math.min(8, copied.list.split("\n").length)} autoFocus
                      onFocus={(e) => e.currentTarget.select()} />
          ) : null}
        </div>
      ) : null}

      {([["Our document", comparison.left], ["The client contract", comparison.right]] as const)
        .map(([who, doc]) => doc.kind === "DOCUMENT" && doc.unread_pages.length ? (
          <p key={who} className="ws-dt__notice">
            {who}: {doc.unread_pages.length === 1 ? `page ${doc.unread_pages[0]} has` : `pages ${doc.unread_pages.join(", ")} have`}{" "}
            no readable text and {doc.unread_pages.length === 1 ? "is" : "are"} not compared —
            often a blank page; if it holds a scan or picture, check it in the file.
          </p>
        ) : null)}

      <div className="ws-dt__body">
        {wide ? <aside className="ws-dt__rail">{list}</aside> : (
          <dialog className="ws-dt__sheet" ref={sheetRef} aria-label="Changes"
                  // A click on the backdrop (the dialog element itself) closes it.
                  onClick={(e) => { if (e.target === e.currentTarget) e.currentTarget.close(); }}>
            <div className="ws-dt__sheethead">
              <span>Changes</span>
              <button type="button" className="ws-dt__iconbtn" aria-label="Close"
                      onClick={() => sheetRef.current?.close()}>
                <IconX size={16} />
              </button>
            </div>
            {list}
          </dialog>
        )}

        <div className="ws-dt__main">
          {split && diffs.length ? (
            <div className="ws-dt__colhead" aria-hidden="true">
              <span><i className="ws-dt__swatch is-ours" />Ours</span>
              <span><i className="ws-dt__swatch is-client" />Client</span>
            </div>
          ) : null}
          {!split && diffs.length ? (
            <p className="ws-dt__key">
              <span><i className="ws-dt__swatch is-ours" />− Ours</span>
              <span><i className="ws-dt__swatch is-client" />+ Client</span>
              <span>Marked words differ</span>
            </p>
          ) : null}
          {diffs.length === 0 ? (
            <div className="ws-dt__empty">
              <IconCheck size={20} />
              <p>{same ? "These two read the same, clause by clause." : "Neither document has text to compare."}</p>
              {same && !full ? (
                <button type="button" onClick={() => { setView("full"); setFilter("ALL"); }}>See the full documents</button>
              ) : null}
            </div>
          ) : null}
          <ol className="ws-dt__cards">
            {rows.map((row, i) => {
              // Full documents: every clause, in the client's reading order.
              if (!full && !shown.includes(i)) return null;
              const key = rowKey(row);
              return (
                <DiffBlock key={key} row={row} index={i} number={shown.indexOf(i)} split={split}
                           current={i === nav.current} pick={choices[key]}
                           full={full}
                           folded={!full && Boolean(choices[key]) && !reopened.has(key)}
                           focusChoice={focusKey === key}
                           canChoose={canChoose}
                           by={byKey[key] && !byKey[key].decided_by_me ? byKey[key].decided_by : null}
                           onChoose={choose} onReopen={() => reopen(key)}
                           cardRef={nav.registerCard(i)} />
              );
            })}
          </ol>
          {decidable.length ? (
            <p className="ws-dt__footnote">
              Your choices are about wording only — Legal still decides in the review.
              {wide ? <> Keys: <kbd>J</kbd> / <kbd>K</kbd> next and previous, <kbd>1</kbd> / <kbd>2</kbd> choose.</> : null}
            </p>
          ) : null}
        </div>
      </div>

      {split ? null : (
        // Phone: everything the reader does with a thumb, at the bottom.
        <div className="ws-dt__dock" role="toolbar" aria-label="Review">
          <button type="button" className="ws-dt__iconbtn" onClick={() => nav.go(-1)}
                  aria-label="Previous difference" disabled={!shown.length}>
            <IconArrowUp size={18} />
          </button>
          <button type="button" className="ws-dt__dockmid" onClick={() => sheetRef.current?.showModal()}
                  aria-label={`Changes — ${position}${decidable.length ? `, ${progress}` : ""}`}>
            <span className="ws-dt__pos"><IconList size={15} /> {position}</span>
            {decidable.length ? <span className="ws-dt__dockprogress">{progress}</span> : null}
          </button>
          {decidable.length ? copyButton(true) : null}
          <button type="button" className="ws-dt__iconbtn" onClick={() => nav.go(1)}
                  aria-label="Next difference" disabled={!shown.length}>
            <IconArrowDown size={18} />
          </button>
        </div>
      )}
    </section>
  );
}

/** The comparison's own shape while it loads — never a spinner on a blank page. */
function Skeleton({ split }: { split: boolean }) {
  return (
    <section className="ws-dt ws-dt--review" aria-busy="true">
      <p className="ws-visually-hidden" role="status">Lining up the clauses…</p>
      <div className="ws-dt__skel" aria-hidden="true">
        <span className="ws-dt__skelbar" />
        {[0, 1, 2].map((n) => (
          <div key={n} className="ws-dt__skelblock">
            <span className="ws-dt__skeltitle" />
            <div className={split ? "ws-dt__skelcols" : "ws-dt__skelrows"}>
              <span /><span />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/** A compared document in the bar — both sides drawn alike, each one a link. */
function DocChip({ side, doc, onChange }: {
  side: "ours" | "client";
  doc: ComparedDocument;
  onChange: () => void;
}) {
  const href = doc.kind === "WEBSITE" ? doc.url : `/dashboard?id=${doc.contract_id}`;
  return (
    <div className={`ws-dt__doc is-${side}`}>
      <span className="ws-dt__side"><i className={`ws-dt__swatch is-${side}`} />{side === "ours" ? "Ours" : "Client"}</span>
      <div className="ws-dt__docname">
        <a href={href} target="_blank" rel="noreferrer" title={`${doc.title} — opens in a new tab`}>
          <span>{doc.title}</span><IconExternal size={12} />
        </a>
        <span className="ws-dt__meta">
          {doc.kind === "WEBSITE"
            ? `Website · as of ${shortDate(doc.effective_from)}`
            : `${doc.filename} · version ${doc.version_number}`}
        </span>
      </div>
      <button type="button" className="ws-dt__change" onClick={onChange}
              aria-label={side === "ours" ? "Change our document" : "Change the client contract"}>
        Change
      </button>
    </div>
  );
}

function ChangesList({ rows, diffs, shown, same, current, filter, onFilter, full, onFull,
                       choices, onPick }: {
  rows: Row[];
  diffs: number[];
  shown: number[];
  same: number;
  current: number;
  filter: Filter;
  onFilter: (f: Filter) => void;
  full: boolean;
  onFull: () => void;
  choices: Record<string, Choice>;
  onPick: (row: number) => void;
}) {
  const count = (f: Filter) => diffs.filter((i) => rows[i]?.status === f).length;
  const filters = ([["ALL", "All", diffs.length], ["CHANGED", "Changed", count("CHANGED")],
    ["ADDED", "Added", count("ADDED")], ["REMOVED", "Missing", count("REMOVED")]] as const)
    .filter(([f, , n]) => f === "ALL" || n > 0);
  return (
    <nav className="ws-dt__changes" aria-label="Changes">
      {filters.length > 2 && !full ? (
        <div className="ws-dt__filters" role="group" aria-label="Show">
          {filters.map(([f, name, n]) => (
            <button key={f} type="button" aria-pressed={filter === f}
                    className={filter === f ? "is-on" : undefined} onClick={() => onFilter(f)}>
              {name} <span>{n}</span>
            </button>
          ))}
        </div>
      ) : null}
      <ol>
        {shown.map((i, n) => {
          const row = rows[i];
          if (!row) return null;
          const kind = KIND[row.status];
          const pick = choices[rowKey(row)];
          return (
            <li key={rowKey(row)}>
              <button type="button" aria-current={i === current ? "true" : undefined}
                      className={`ws-dt__change-item${i === current ? " is-current" : ""}${pick ? " is-decided" : ""}`}
                      onClick={() => onPick(i)}>
                <span className="ws-dt__num">{n + 1}</span>
                <span className="ws-dt__itemtext">
                  <span className="ws-dt__itemname">{clauseName(row.right ?? row.left)}</span>
                  <span className="ws-dt__itemmeta">
                    <kind.Icon size={12} />
                    {row.moved && row.status === "UNCHANGED" ? "Moved" : kind.short}
                    {isDecidable(row) && pick ? <em> · {CHOICE_WORDS[row.status][pick]}</em> : null}
                  </span>
                </span>
                {isDecidable(row) ? (
                  <span className="ws-dt__state">
                    {pick ? <IconCheck size={14} /> : <i className="ws-dt__dot" />}
                    <span className="ws-visually-hidden">{pick ? ", decided" : ", not decided"}</span>
                  </span>
                ) : null}
              </button>
            </li>
          );
        })}
      </ol>
      {same > 0 ? (
        <p className="ws-dt__same">
          {same} clause{same === 1 ? " reads" : "s read"} the same.
          {full ? null : <> <button type="button" onClick={onFull}>See the full documents</button></>}
        </p>
      ) : null}
    </nav>
  );
}

function DiffBlock({ row, index, number, split, full, current, pick, folded, focusChoice,
                     canChoose, by, onChoose,
                     onReopen, cardRef }: {
  row: Row;
  index: number;
  /** Position among the shown differences, or -1 for an identical clause. */
  number: number;
  split: boolean;
  /** Full documents: every text in full, nothing folded or cut. */
  full: boolean;
  current: boolean;
  pick: Choice | undefined;
  folded: boolean;
  focusChoice: boolean;
  /** False: this reader sees the choice and cannot change it (AB-81 r4). */
  canChoose: boolean;
  /** Who made the choice, when it was not this reader. */
  by: string | null;
  onChoose: (index: number, choice: Choice, how: How) => void;
  onReopen: () => void;
  cardRef: (el: HTMLLIElement | null) => void;
}) {
  const name = clauseName(row.right ?? row.left);
  const titleId = `dt-card-${index}`;
  const classes = `ws-dt__card is-${row.status.toLowerCase()}${current ? " is-current" : ""}`;

  if (folded && pick && isDecidable(row)) {
    return (
      <li ref={cardRef} tabIndex={-1} data-row={index} aria-labelledby={titleId}
          className={`${classes} is-folded`}>
        <div className="ws-dt__foldrow">
          {number >= 0 ? <span className="ws-dt__num">{number + 1}</span> : null}
          <h2 id={titleId}>{name}</h2>
          <span className="ws-dt__pickword">
            <IconCheck size={14} /> {CHOICE_WORDS[row.status][pick]}
            {by ? <span className="ws-dt__by"> · {by}</span> : null}
          </span>
          <button type="button" className="ws-dt__change" onClick={onReopen}
                  aria-label={canChoose ? `Change the choice for ${name}` : `Show ${name}`}>
            {canChoose ? "Change" : "Show"}
          </button>
        </div>
      </li>
    );
  }

  const kind = KIND[row.status];
  const rewritten = row.status === "CHANGED" && row.left && row.right
    && isRewritten(row.left, row.right);
  const renamed = row.left && row.right
    && clauseName(row.left).toLowerCase() !== clauseName(row.right).toLowerCase();
  const pages = [row.left?.page ? `ours p. ${row.left.page}` : null,
                 row.right?.page ? `client p. ${row.right.page}` : null].filter(Boolean);
  return (
    <li ref={cardRef} tabIndex={-1} data-row={index} aria-labelledby={titleId} className={classes}>
      <div className="ws-dt__cardhead">
        {number >= 0 ? <span className="ws-dt__num">{number + 1}</span> : null}
        <div className="ws-dt__cardtitle">
          <h2 id={titleId}>
            {renamed ? <span className="ws-dt__was">{clauseName(row.left)} → </span> : null}
            {name}
          </h2>
          <p className="ws-dt__cardmeta">
            <span className="ws-dt__kind">
              <kind.Icon size={13} /> {rewritten ? "Rewritten — read both" : kind.label}
            </span>
            {row.status === "CHANGED" && row.left && row.right && !rewritten
              ? <span>{changedSentences(row.left, row.right)} differ</span> : null}
            {row.moved ? <span>In a different place</span> : null}
            {pages.length ? <span>{pages.join(" · ")}</span> : null}
          </p>
        </div>
      </div>
      {isDecidable(row) ? (
        <fieldset className="ws-dt__choice" disabled={!canChoose}>
          <legend className="ws-visually-hidden">Your choice for {name}</legend>
          {(["ours", "theirs"] as const).map((c) => (
            <label key={c} className={`ws-dt__opt${pick === c ? " is-on" : ""}`}>
              <input type="radio" name={`dt-choice-${index}`} value={c} checked={pick === c}
                     autoFocus={focusChoice && (pick ?? "ours") === c}
                     // A radio changes on a click event either way; detail > 0 is a
                     // pointer, 0 an arrow key (the reader is still deciding).
                     onChange={(e) => onChoose(index, c,
                       (e.nativeEvent as MouseEvent).detail > 0 ? "move" : "stay")}
                     // Clicking the option already chosen fires no change: confirm it.
                     onClick={(e) => { if (e.detail > 0 && pick === c) onChoose(index, c, "move"); }} />
              {CHOICE_WORDS[row.status][c]}
            </label>
          ))}
        </fieldset>
      ) : null}
      <div className="ws-dt__cardbody">
        <ClauseBody row={row} split={split} full={full} rewritten={Boolean(rewritten)} />
      </div>
    </li>
  );
}

/** One side's text, labelled on a phone (side by side, the pinned headings say it). */
function Side({ who, split, children }: { who: "ours" | "client"; split: boolean; children: ReactNode }) {
  return (
    <div className={`ws-dt__sidetext is-${who}`}>
      {split ? null : (
        <span className="ws-dt__label"><i className={`ws-dt__swatch is-${who}`} />{who === "ours" ? "Ours" : "Client"}</span>
      )}
      {children}
    </div>
  );
}

function ClauseBody({ row, split, full, rewritten }: {
  row: Row; split: boolean; full: boolean; rewritten: boolean;
}) {
  const text = (t: string | undefined) => <p className="ws-dt__text">{sentences(t ?? "")}</p>;
  // Same wording: once when stacked (it is labelled so); on both sides when side by
  // side — one column there read as the client having none.
  if (row.status === "UNCHANGED" && !split) return text((row.right ?? row.left)?.text);
  if (row.status === "UNCHANGED" || rewritten || !row.left || !row.right) {
    // Side by side, the two are cut together; stacked (phone), each on its own —
    // or a long text of ours would hide the client's behind the same cut.
    const side = (who: "ours" | "client", c: Row["left"]) => (
      <Side who={who} split={split}>
        {c ? (split || full ? text(c.text) : <Clamp>{text(c.text)}</Clamp>) : (
          <p className="ws-dt__absent">{who === "ours" ? "Not in our document" : "Not in the client's contract"}</p>
        )}
      </Side>
    );
    const pair = <div className="ws-dt__pair">{side("ours", row.left)}{side("client", row.right)}</div>;
    return split && !full ? <Clamp>{pair}</Clamp> : pair;
  }
  return (
    <div className={split ? undefined : "ws-dt__unified"}>
      <ReactDiffViewer
        oldValue={sentences(row.left.text)}
        newValue={sentences(row.right.text)}
        splitView={split}
        compareMethod={WORDS}
        hideLineNumbers
        hideSummary
        disableWorker
        // The changed sentences, one either side for context; the rest fold behind
        // a plain-words line (the library's default is a code "@@" header).
        showDiffOnly={!full}
        extraLinesSurroundingDiff={1}
        codeFoldMessageRenderer={(n) => (
          <span className="ws-dt__fold">Show {n} matching sentence{n === 1 ? "" : "s"}</span>
        )}
        styles={viewerStyles(split)}
      />
    </div>
  );
}

/** Long text stops at about twelve lines, with the way to the rest in plain view. */
function Clamp({ children }: { children: ReactNode }) {
  const body = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [over, setOver] = useState(false);
  useEffect(() => {
    const el = body.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setOver(el.scrollHeight > el.clientHeight + 4));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div className={`ws-dt__clamp${open ? " is-open" : ""}${over && !open ? " is-over" : ""}`}>
      <div ref={body} className="ws-dt__clampbody">{children}</div>
      {over || open ? (
        <button type="button" className="ws-dt__more" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Show less" : "Show the full clause"}
        </button>
      ) : null}
    </div>
  );
}

/** The viewer in the page's tokens: ours marked red, the client's green — a light
 *  tint on a changed sentence, a stronger one and a rule under the changed words. */
const viewerStyles = (split: boolean) => ({
  variables: {
    light: {
      diffViewerBackground: "var(--ws-surface)",
      diffViewerColor: "var(--ws-ink-900)",
      removedBackground: "var(--ws-diff-ours-line)",
      addedBackground: "var(--ws-diff-client-line)",
      wordRemovedBackground: "var(--ws-diff-ours-word)",
      wordAddedBackground: "var(--ws-diff-client-word)",
      removedGutterBackground: "var(--ws-diff-ours-line)",
      addedGutterBackground: "var(--ws-diff-client-line)",
      removedColor: "var(--ws-ink-900)",
      addedColor: "var(--ws-ink-900)",
      emptyLineBackground: "var(--ws-surface)",
      gutterBackground: "var(--ws-surface)",
      codeFoldBackground: "var(--ws-surface)",
      codeFoldGutterBackground: "var(--ws-surface)",
    },
  },
  contentText: {
    fontFamily: "var(--ws-serif)", fontSize: "var(--ws-text-base)", lineHeight: 1.65,
    // The viewer's code default `line-break: anywhere` splits words ("a greement").
    whiteSpace: "pre-wrap" as const, lineBreak: "auto" as const,
    overflowWrap: "break-word" as const,
  },
  line: { padding: "1px 0" },
  // The library's table has `min-width: 1000px`: it clipped the client column.
  diffContainer: { minWidth: 0 },
  wordDiff: { padding: "1px 1px", borderRadius: 0 },
  wordRemoved: { boxShadow: "inset 0 -2px 0 var(--ws-diff-ours-rule)" },
  wordAdded: { boxShadow: "inset 0 -2px 0 var(--ws-diff-client-rule)" },
  // Hidden, not removed: the marker is a table cell; dropping it shifts the text.
  marker: split ? { width: 0, minWidth: 0, padding: 0, visibility: "hidden" as const }
    : { width: "20px", padding: "0 4px", color: "var(--ws-ink-500)" },
});
