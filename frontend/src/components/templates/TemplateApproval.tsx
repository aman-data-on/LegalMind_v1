"use client";

/**
 * Template approval (S4, `AM-282`/`AM-283`): the corporate lawyer turns an imported
 * reference template (DRAFT, "Reference text — not approved by Legal") into a published
 * one, clause by clause. Left: the clauses, the ones the gate will refuse first. Centre:
 * the clause as contract text, our wording as it will be numbered, "Before publishing"
 * or "Changes since the published version". Right: what our standards say of it, the
 * three actions and the clause's history. Everything shown comes from the server — the
 * clause text, the approvals, the numbering (`…/replace` dry run) and the publish gate's
 * own check (`GET /templates/{id}/check`); nothing here judges a clause. A reader without
 * `legal.approve_customization` never reaches this component (the page renders "not
 * found" for them).
 */

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import { blockerText } from "@/lib/package";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import {
  actionProblem, approved, approvedLine, blockers, canPublish, changedSincePublished, clauseLine, clauseNumbers, displayTitle,
  failingOn, fieldLabel, flagWords, fromEditor, groupClauses, listOrder, outlineDiff, placed, plainText,
  problemLines, shortWhy, topicWords, statusWords, stopCount, structureChanges, templateName, toEditor, unchecked, within,
  blankPath, reviewCopyPath,
  type CheckStandard, type ClauseVersionRow, type OutlineLine, type TemplateCheck, type TemplateClause,
  type SpecialConditionsReadiness, type TemplateDetail,
  cardName,
} from "@/lib/templates";

import { shortDate } from "@/components/workspace/model";

import { PageHeader } from "@/components/page/PageHeader";

import { ClauseSheet, Runs } from "./TemplateClause";
import { CheckStatus } from "./TemplateList";
import { PreviewButton } from "@/components/PreviewPanel";
import "./templates.css";
import { formatDate } from "@/lib/dates";

type View = { kind: "clause"; key: string } | { kind: "publish" } | { kind: "changes" };
type Mode = "none" | "replace" | "no-position";

function useTemplate(id: string) {
  const [detail, setDetail] = useState<TemplateDetail | null>(null);
  const [check, setCheck] = useState<TemplateCheck | null>(null);
  const [checking, setChecking] = useState(true);
  const [failed, setFailed] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // HIGH 4: the check always FINISHES — the result, or failed (an error or past
  // `within`'s limit) with "Run again"; only the newest run may write its result
  const seq = useRef(0);
  const fetchCheck = useCallback(() => {
    const mine = ++seq.current;
    return within(api.checkTemplate(id))
      .then((c) => { if (mine === seq.current) { setCheck(c); setFailed(false); } })
      .catch(() => { if (mine === seq.current) setFailed(true); })
      .finally(() => { if (mine === seq.current) setChecking(false); });
  }, [id]);
  const reload = useCallback(() => api.template(id).then(setDetail).catch(setError), [id]);
  useEffect(() => { void reload(); void fetchCheck(); }, [reload, fetchCheck]);
  /** after a clause action, or "Run again": the gate's check reads the new text */
  const runCheck = useCallback(() => { setChecking(true); setFailed(false); void fetchCheck(); }, [fetchCheck]);
  return { detail, check, checking, failed, error, reload, runCheck };
}

/** How the server will number ``text`` (a dry run, debounced). While a newer text is
 *  being numbered the last answer stays (its ``text`` says which); null before the first. */
function useOutline(id: string, key: string | null, text: string | null) {
  const [got, setGot] = useState<{ key: string; text: string; outline: OutlineLine[] | null; error: string | null } | null>(null);
  useEffect(() => {
    if (!key || text === null || !text.trim()) return;
    let live = true;
    const t = setTimeout(() => {
      api.previewClause(id, key, text).then((r) => live && setGot({ key, text, outline: r.outline, error: null }))
        .catch((e) => live && setGot({ key, text, outline: null, error: describeError(e) }));
    }, 400);
    return () => { live = false; clearTimeout(t); };
  }, [id, key, text]);
  return key && text !== null && got?.key === key ? got : null;
}

export function TemplateApproval({ id }: { id: string }) {
  const { can } = useSession();
  const { detail, check, checking, failed, error, reload, runCheck } = useTemplate(id);
  const checkState = checking ? "checking" : failed || !check ? "failed" : "done";
  const [chosen, setView] = useState<View | null>(null);
  const [onPhoneDetail, setOnPhoneDetail] = useState(false);
  const [said, setSaid] = useState("");
  const [mode, setMode] = useState<Mode>("none");
  const [text, setText] = useState("");
  const [baseText, setBaseText] = useState<string | null>(null);
  const positions = can(P.LEGAL_POSITION_VIEW);

  const groups = useMemo(() => detail ? groupClauses(detail.clauses, check) : [], [detail, check]);
  const order = useMemo(() => listOrder(groups), [groups]);
  const numbers = useMemo(() => clauseNumbers(detail?.clauses ?? []), [detail]);

  // until one is chosen: the first clause in list order (a failing one when there is one),
  // once the check has said which those are — so the list does not reorder under the reader
  const view: View | null = useMemo(() => chosen ?? (!detail ? null
    : !order.length ? { kind: "publish" }
    : check || !checking ? { kind: "clause", key: order[0]!.clause_key } : null),
  [chosen, detail, order, check, checking]);
  const clause = view?.kind === "clause" ? detail?.clauses.find((c) => c.clause_key === view.key) : undefined;

  const editing = mode === "replace" && clause ? clause.clause_key : null;
  const base = useOutline(id, editing, editing ? baseText : null);
  const sent = editing ? fromEditor(text, numbers) : null;
  const now = useOutline(id, editing, sent);

  const select = useCallback((next: View, replace?: TemplateClause) => {
    setView(next);
    setOnPhoneDetail(true);
    if (replace) {
      const start = toEditor(replace.wording ?? plainText(replace.body), numbers);
      setText(start); setBaseText(fromEditor(start, numbers)); setMode("replace");
    } else setMode("none");
  }, [numbers]);

  // j / k — next / previous clause in the list's order
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (e.metaKey || e.ctrlKey || e.altKey || t?.closest("input, textarea, select, [contenteditable]")) return;
      if (e.key !== "j" && e.key !== "k") return;
      const at = view?.kind === "clause" ? order.findIndex((c) => c.clause_key === view.key) : -1;
      const next = order[Math.min(order.length - 1, Math.max(0, at + (e.key === "j" ? 1 : -1)))];
      if (next) { e.preventDefault(); select({ kind: "clause", key: next.clause_key }); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [order, view, select]);

  if (error) {
    return <div className="ws-docs tpl"><p className="tpl-error" role="alert">{describeError(error)}</p></div>;
  }
  if (!detail) return <div className="ws-docs tpl"><p className="tpl-quiet" role="status">Loading the template…</p></div>;

  const draft = detail.status === "DRAFT";
  const remaining = detail.clauses_total - detail.clauses_approved;
  const stops = stopCount(check);
  const changed = detail.published ? changedSincePublished(detail.clauses) : [];
  const openReplace = (key: string) => {
    const c = detail.clauses.find((x) => x.clause_key === key);
    if (c) select({ kind: "clause", key }, draft ? c : undefined);
  };

  async function afterAction(done: TemplateClause, what: string) {
    await reload();
    runCheck();
    setMode("none");
    // on to the next clause still to approve, in the list's order
    const at = order.findIndex((c) => c.clause_key === done.clause_key);
    const next = [...order.slice(at + 1), ...order.slice(0, at)].find((c) => !approved(c));
    setSaid(`${what}: ${displayTitle(done.title)}.${next ? ` Next: ${displayTitle(next.title)}.` : " Every clause is approved."}`);
    if (next) setView({ kind: "clause", key: next.clause_key });
    else setView({ kind: "publish" });
  }

  const preview = editing && now?.outline && base?.outline ? {
    outline: now.outline, diff: outlineDiff(base.outline, now.outline),
    structure: structureChanges(base.outline, now.outline),
  } : null;

  return (
    <div className="tpl" data-detail={onPhoneDetail || undefined} data-editing={editing ? true : undefined}>
      <PageHeader wide title={templateName(detail)} back={{ href: "/templates", label: "Templates" }}
        meta={<>
          <strong>{statusWords(detail, check)}</strong>
          {draft && checkState !== "done" ? <CheckStatus state={checkState} onRetry={runCheck} />
            : <span>{(draft ? blockers(detail, check) : null) ?? detail.progress}</span>}
        </>}
        secondary={<>
          {draft || detail.status === "APPROVED" ? (
            <PreviewButton path={reviewCopyPath(detail)} text="Preview review copy" title={`Review copy: ${cardName(detail)}, version ${detail.version}`} />
          ) : detail.status === "PUBLISHED" ? (
            <PreviewButton path={blankPath(detail)} text="Preview blank" title={`Blank template: ${cardName(detail)}, version ${detail.version}`} />
          ) : null}
          {draft && !canPublish(detail, check) && stops ? (
            <button type="button" className="ws-btn ws-btn--sm" aria-pressed={view?.kind === "publish"}
                    onClick={() => select({ kind: "publish" })}>
              {stops === 1 ? "See the 1 problem" : `See the ${stops} problems`}
            </button>
          ) : null}
        </>}
        primary={draft && canPublish(detail, check) ? (
          <button type="button" className="ws-btn ws-btn--sm ws-btn--primary" onClick={() => select({ kind: "publish" })}>
            Publish
          </button>
        ) : null} />
      <p className="ws-visually-hidden" role="status" aria-live="polite">{said}</p>

      <div className="tpl-grid" data-wide={(view && (view.kind !== "clause" || !clause)) || undefined}>
        <nav className="tpl-list" aria-label="Clauses" aria-keyshortcuts="j k">
          <button type="button" className="tpl-row tpl-row--publish" aria-current={view?.kind === "publish" || undefined}
                  onClick={() => select({ kind: "publish" })}>
            <span className="tpl-row__l1">{draft ? "Before publishing" : "Publishing"}</span>
            <span className="tpl-row__l2">
              {checkState !== "done" && draft ? <CheckStatus state={checkState} onRetry={runCheck} /> : !draft ? statusWords(detail, check)
                : canPublish(detail, check) ? "Ready to publish"
                : [remaining ? `${remaining} ${remaining === 1 ? "clause" : "clauses"} to approve` : "",
                   stops ? `${stops} ${stops === 1 ? "problem stops" : "problems stop"} publishing` : ""]
                  .filter(Boolean).join(". ")}
            </span>
          </button>
          {detail.published ? (
            <button type="button" className="tpl-row tpl-row--publish" aria-current={view?.kind === "changes" || undefined}
                    onClick={() => select({ kind: "changes" })}>
              <span className="tpl-row__l1">Changes since version {detail.published.version}</span>
              <span className="tpl-row__l2">{changed.length
                ? `${changed.length} ${changed.length === 1 ? "clause" : "clauses"} changed` : "No clause has changed"}</span>
            </button>
          ) : null}
          {groups.map((g) => (
            <section key={g.id} className="tpl-group" aria-labelledby={`tpl-g-${g.id}`}>
              <h2 id={`tpl-g-${g.id}`} className="tpl-group__title">{g.title} <span>{g.clauses.length}</span></h2>
              {g.why ? <p className="tpl-group__why">{g.why}</p> : null}
              <ul>
                {g.clauses.map((c) => (
                  <li key={c.clause_key}>
                    <button type="button" className="tpl-row" data-fails={g.id === "differs" || undefined}
                            data-done={approved(c) || undefined}
                            aria-current={view?.kind === "clause" && view.key === c.clause_key || undefined}
                            onClick={() => select({ kind: "clause", key: c.clause_key })}>
                      <span className="tpl-row__l1"><span className="tpl-row__n">{numbers.get(c.clause_key)}</span>
                        <span className="tpl-row__t">{displayTitle(c.title)}</span></span>
                      <span className="tpl-row__l2">{clauseLine(c, check)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
          <p className="tpl-keys"><kbd>j</kbd> next clause, <kbd>k</kbd> previous</p>
        </nav>

        <button type="button" className="ws-btn tpl-phoneback" onClick={() => setOnPhoneDetail(false)}>
          Back to the clauses
        </button>
        <div className="tpl-centre">
          {!view ? (checkState === "failed" ? <p className="tpl-quiet"><CheckStatus state="failed" onRetry={runCheck} /></p>
            : <CheckingSheet clauses={detail.clauses.length} />)
            : view.kind === "changes" && detail.published ? (
              <ChangesView detail={detail} changed={changed} numbers={numbers}
                           onSelect={(key) => select({ kind: "clause", key })} />
            ) : view.kind !== "clause" || !clause ? (
              <PublishView detail={detail} check={check} checking={checking} positions={positions} onRetry={runCheck}
                           onSelect={(key) => select({ kind: "clause", key })} onReplace={openReplace}
                           onPublished={async () => { await reload(); setSaid("Published."); }} />
            ) : editing ? (
              <PreviewSheet clause={clause} number={numbers.get(clause.clause_key) ?? ""} numbers={numbers}
                            outline={preview?.outline ?? null} changed={preview?.diff.changed ?? null}
                            removed={preview?.diff.removed ?? []} error={now?.error ?? null} />
            ) : (
              <ClauseSheet clause={clause} number={numbers.get(clause.clause_key) ?? ""} numbers={numbers}
                           label={detail.label ?? "Reference text — not approved by Legal"} />
            )}
        </div>

        {!view && checkState !== "failed" ? (
          <aside className="tpl-side" aria-hidden="true">
            <section className="tpl-panel"><span className="ws-skel ws-skel--line ws-skel--w64" />
              <span className="ws-skel ws-skel--line" /><span className="ws-skel ws-skel--line ws-skel--w88" /></section>
          </aside>
        ) : null}
        {view?.kind === "clause" && clause ? (
          <aside className="tpl-side" aria-label="Our standard and your approval">
            <StandardsFor clause={clause} check={check} checking={checking} positions={positions} onRetry={runCheck} />
            {draft ? (
              <ClauseActions key={clause.clause_key} templateId={detail.id} clause={clause}
                             fails={failingOn(clause.clause_key, check)}
                             fields={detail.variables.map((v) => v.key)} mode={mode}
                             onMode={(m) => m === "replace" ? select({ kind: "clause", key: clause.clause_key }, clause) : setMode(m)}
                             text={text} onText={setText} sent={sent}
                             preview={editing ? { pending: !now || now.text !== sent, error: now?.error ?? null,
                                                  structure: preview?.structure ?? null,
                                                  changed: preview?.diff.changed.size ?? 0,
                                                  removed: preview?.diff.removed.length ?? 0 } : null}
                             onDone={afterAction} />
            ) : null}
            <History key={`h-${clause.clause_key}-${clause.version}`} templateId={detail.id} clause={clause} />
          </aside>
        ) : null}
      </div>
    </div>
  );
}

/** The clause view at its final size while the check runs (it takes seconds): the sheet and
 *  the side panel as skeletons, and one line saying what is being checked. */
function CheckingSheet({ clauses }: { clauses: number }) {
  const widths = ["", "ws-skel--w88", "", "ws-skel--w64", "", "ws-skel--w88", "ws-skel--w64"];
  return (
    <article className="tpl-sheet" aria-busy="true">
      <p className="tpl-quiet tpl-sheet__checking" role="status">
        Checking {clauses === 1 ? "the clause" : `all ${clauses} clauses`} against our standards. The first
        clause that differs opens here when the check finishes.
      </p>
      <div aria-hidden="true">
        <span className="ws-skel ws-skel--line ws-skel--w64 tpl-skel__title" />
        {widths.map((w, i) => <span key={i} className={`ws-skel ws-skel--line ${w}`} />)}
      </div>
    </article>
  );
}

function StandardsFor({ clause, check, checking, positions, onRetry }: {
  clause: TemplateClause; check: TemplateCheck | null; checking: boolean; positions: boolean; onRetry: () => void;
}) {
  const fails = failingOn(clause.clause_key, check);
  const differs = fails.filter((s) => !unchecked(s));
  const reads = fails.filter(unchecked);
  const item = (s: CheckStandard) => (
    <li key={s.code}>
      <p className="tpl-standards__what">{s.description ?? s.code}</p>
      <p className="tpl-standards__said">{shortWhy(s)}</p>
      {positions && s.position ? (
        <p className="tpl-standards__pos"><span>Our position</span>{s.position}</p>
      ) : null}
    </li>
  );
  return (
    <section className="tpl-panel" aria-labelledby="tpl-std">
      <h2 id="tpl-std" className="tpl-panel__title">
        {differs.length ? "Differs from our standard" : reads.length ? "Couldn’t be checked" : "Our standards"}
      </h2>
      {checking && !check ? <p className="tpl-quiet"><CheckStatus state="checking" onRetry={onRetry} /></p>
        : !check ? <p className="tpl-quiet"><CheckStatus state="failed" onRetry={onRetry} /></p>
        : fails.length ? (
          <>
            {differs.length ? <ul className="tpl-standards">{differs.map(item)}</ul> : null}
            {reads.length ? (
              <div className="tpl-standards__group">
                {differs.length ? <h3>Couldn&rsquo;t be checked</h3> : null}
                <p className="tpl-help">The check found this clause but could not measure it against the standard
                  below. Read it yourself before you approve it.</p>
                <ul className="tpl-standards tpl-standards--read">{reads.map(item)}</ul>
              </div>
            ) : null}
          </>
        ) : <p className="tpl-quiet">The check found nothing in this clause that differs from our standards.</p>}
      {clause.flags?.length ? (
        <div className="tpl-flags">
          <h3>Check this clause</h3>
          <ul>{clause.flags.map((f) => <li key={f}>{flagWords(f)}</li>)}</ul>
        </div>
      ) : null}
    </section>
  );
}

function ClauseActions({ templateId, clause, fails, fields, mode, onMode, text, onText, sent, preview, onDone }: {
  templateId: string; clause: TemplateClause; fails: CheckStandard[]; fields: string[];
  mode: Mode; onMode: (m: Mode) => void; text: string; onText: (t: string) => void; sent: string | null;
  preview: { pending: boolean; error: string | null; structure: string[] | null; changed: number; removed: number } | null;
  onDone: (clause: TemplateClause, what: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tried, setTried] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const reasonRef = useRef<HTMLTextAreaElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const isApproved = approved(clause);
  const fails0 = fails.find((s) => !unchecked(s)) ?? fails[0];

  useEffect(() => { if (confirming) confirmRef.current?.focus(); }, [confirming]);

  async function run(what: string, call: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await call(); await onDone(clause, what); }
    catch (e) { setError(e instanceof ApiError && e.status === 409 ? e.message : describeError(e)); }
    finally { setBusy(false); }
  }
  const approve = () => void run("Approved", () => api.approveClause(templateId, clause.clause_key));
  const problem = mode === "none" ? null : actionProblem(mode, text, reason);
  function submit(e: React.FormEvent) {
    e.preventDefault();
    setTried(true);
    if (problem) { reasonRef.current?.focus(); return; }
    if (mode === "replace") void run("Our wording approved", () => api.replaceClause(templateId, clause.clause_key, sent ?? text, reason.trim()));
    else void run("No position approved", () => api.noPosition(templateId, clause.clause_key, reason.trim()));
  }
  const replaceButton = (primary: boolean) => (
    <button type="button" className={`ws-btn${primary ? " ws-btn--primary" : ""}`} disabled={busy} onClick={() => onMode("replace")}>
      Replace with our wording
    </button>
  );

  return (
    <section className="tpl-panel tpl-actions" aria-labelledby="tpl-act" data-mode={mode}>
      <h2 id="tpl-act" className="tpl-panel__title">{isApproved ? "Change this clause" : "Your approval"}</h2>
      {mode === "none" ? (
        <>
          {/* phone: the action bar sits far below the standard, so it says which one, and links to it */}
          {fails0 ? <a className="tpl-actions__why" href="#tpl-std">{shortWhy(fails0)}{fails.length > 1 ? `, and ${fails.length - 1} more` : ""}</a> : null}
          {isApproved ? <p className="tpl-quiet">An approved clause is kept as it is. Replacing it records a new version.</p> : null}
          {confirming && fails0 ? (
            <div className="tpl-confirm" role="group" aria-labelledby="tpl-confirm-q">
              <p id="tpl-confirm-q"><strong>Approve anyway?</strong> This clause {whyInSentence(fails0)}. The
                template can&rsquo;t be published until the clause is replaced.</p>
              <div className="tpl-actions__row">
                <button ref={confirmRef} type="button" className="ws-btn" disabled={busy} onClick={approve}>Approve anyway</button>
                <button type="button" className="ws-btn tpl-btn-quiet" disabled={busy} onClick={() => setConfirming(false)}>Cancel</button>
              </div>
            </div>
          ) : (
            <div className="tpl-actions__row">
              {fails0 && !unchecked(fails0) ? replaceButton(true) : null}
              {!isApproved ? (
                <button type="button" className={`ws-btn${fails0 && !unchecked(fails0) ? "" : " ws-btn--primary"}`} disabled={busy}
                        onClick={() => fails0 ? setConfirming(true) : approve()}>
                  Approve as it stands
                </button>
              ) : null}
              {!(fails0 && !unchecked(fails0)) ? replaceButton(false) : null}
              <button type="button" className="ws-btn" disabled={busy} onClick={() => onMode("no-position")}>
                No position
              </button>
            </div>
          )}
        </>
      ) : (
        <form className="tpl-form" onSubmit={submit} noValidate>
          {mode === "replace" ? (
            <>
              <label htmlFor="tpl-text" className="tpl-label">Our wording</label>
              <p id="tpl-text-help" className="tpl-help">Start a line with 4.1 or (a) for a sub-clause or a list item.
                Write a cross-reference as <code>{"{clause 4.2}"}</code>
                {fields.length ? <> and a fill-in field as <code>{`{${fields[0]}}`}</code> ({fieldLabel(fields[0]!)})</> : null}.</p>
              <textarea id="tpl-text" className="tpl-editor" value={text} rows={14} spellCheck
                        aria-describedby="tpl-text-help tpl-structure" onChange={(e) => onText(e.target.value)} />
            </>
          ) : (
            <p className="tpl-help">The clause keeps its text and is recorded as stating no company position.</p>
          )}
          <label htmlFor="tpl-reason" className="tpl-label">Reason (required)</label>
          <textarea id="tpl-reason" ref={reasonRef} className="tpl-reason" rows={2} value={reason}
                    aria-invalid={tried && !!problem || undefined}
                    aria-describedby={tried && problem ? "tpl-reason-err" : undefined}
                    onChange={(e) => setReason(e.target.value)} />
          {tried && problem ? <p id="tpl-reason-err" className="tpl-error">{problem}</p> : null}
          {/* Pinned to the foot of the side column (polish batch): what recording will do to the
              clause's numbering stays in sight beside the button that records it. */}
          <div className="tpl-form__foot">
            {mode === "replace" ? <div id="tpl-structure" className="tpl-structure" aria-live="polite">
              {!text.trim() ? null : preview?.error ? <p className="tpl-error">{preview.error}</p>
                : !preview?.structure ? <p className="tpl-quiet">Numbering it…</p> : (
                  <>
                    <p className="tpl-structure__head">{preview.changed || preview.removed
                      ? `${preview.changed} ${preview.changed === 1 ? "line" : "lines"} new or changed, ${preview.removed} removed`
                      : "Same words as the reference text"}{preview.pending ? " (updating…)" : ""}</p>
                    {preview.structure.length ? (
                      <ul className="tpl-structure__form">{preview.structure.map((s) => <li key={s}>{s}</li>)}</ul>
                    ) : <p className="tpl-quiet">Its numbering and form stay as they are.</p>}
                  </>
                )}
            </div> : null}
            <div className="tpl-actions__row">
              <button type="submit" className="ws-btn ws-btn--primary" disabled={busy || (mode === "replace" && !!preview?.error)}>
                {mode === "replace" ? "Record our wording" : "Record no position"}
              </button>
              <button type="button" className="ws-btn" disabled={busy} onClick={() => { onMode("none"); setTried(false); }}>
                Back
              </button>
            </div>
          </div>
        </form>
      )}
      {error ? <p className="tpl-error" role="alert">{error}</p> : null}
    </section>
  );
}

/** Our wording as the renderer will number it, beside the editor — new or changed lines
 *  marked against the reference text. Nothing here is recorded. */
function PreviewSheet({ clause, number, numbers, outline, changed, removed, error }: {
  clause: TemplateClause; number: string; numbers: Map<string, string>; outline: OutlineLine[] | null;
  changed: Set<number> | null; removed: string[]; error: string | null;
}) {
  return (
    <article className="tpl-sheet tpl-sheet--preview" aria-labelledby="tpl-sheet-title">
      <div className="tpl-sheet__note">
        <p>Our wording, numbered as it will be. New or changed lines are marked.</p>
      </div>
      <h2 id="tpl-sheet-title" className="tpl-sheet__title"><span className="tpl-num">{number}</span>{clause.title}</h2>
      <div className="tpl-sheet__body">
        {error ? <p className="tpl-error">{error}</p> : !outline ? <p className="tpl-quiet">Numbering it…</p>
          : outline.map((l, i) => (
            <p key={i} className="tpl-para" data-changed={changed?.has(i) || undefined}
               style={{ marginLeft: `${Math.max(0, l.level - 2) * 2.6}em` }}>
              {l.number ? <span className="tpl-num">{l.number}</span> : null}
              {l.kind === "definition" ? <strong>{l.text.split("”")[0]}&rdquo;</strong> : null}
              <Runs text={l.kind === "definition" ? l.text.split("”").slice(1).join("”") : l.text} numbers={numbers} />
            </p>
          ))}
        {removed.length ? (
          <details className="tpl-removed">
            <summary>{removed.length} {removed.length === 1 ? "line" : "lines"} of the reference text not in our wording</summary>
            <ul>{removed.map((t, i) => <li key={i}><Runs text={t} numbers={numbers} /></li>)}</ul>
          </details>
        ) : null}
      </div>
      <p className="tpl-sign">Not recorded yet</p>
    </article>
  );
}

/** "differs from our standard on liability" — the standard, mid-sentence. */
function whyInSentence(s: CheckStandard): string {
  const on = topicWords(s).toLowerCase();
  return s.classification === "CONFLICT" ? `says the same thing twice, differently, on ${on}`
    : unchecked(s) ? `couldn\u2019t be checked against our standard on ${on}` : `differs from our standard on ${on}`;
}

const DECISION_WORDS: Record<string, string> = {
  APPROVE: "approved as it stood", REPLACE: "our wording", NO_POSITION: "no position",
};

/** The clause's governance trail: every recorded version, who approved it, how and why. */
function History({ templateId, clause }: { templateId: string; clause: TemplateClause }) {
  const [rows, setRows] = useState<ClauseVersionRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <details className="tpl-panel tpl-history" onToggle={(e) => {
      if ((e.currentTarget as HTMLDetailsElement).open && !rows) {
        api.clauseVersions(templateId, clause.clause_key).then(setRows).catch((x) => setError(describeError(x)));
      }
    }}>
      <summary className="tpl-panel__title">History of this clause</summary>
      {error ? <p className="tpl-error">{error}</p> : !rows ? <p className="tpl-quiet" role="status">Loading…</p> : (
        <ol className="tpl-history__list">
          {rows.map((r) => (
            <li key={r.version}>
              <p className="tpl-history__what">Version {r.version}: {r.decision ? DECISION_WORDS[r.decision] : "imported reference text"}
                {r.in_this_template ? <span className="tpl-tag">In this template</span> : null}
                {r.published ? <span className="tpl-tag">Published</span> : null}</p>
              <p className="tpl-history__who">{r.approved_by_name ? `Approved by ${r.approved_by_name}${r.approved_at ? `, ${shortDate(r.approved_at)}` : ""}`
                : `Not approved${r.created_at ? `, added ${shortDate(r.created_at)}` : ""}`}</p>
              {r.reason ? <p className="tpl-history__why">&ldquo;{r.reason}&rdquo;</p> : null}
            </li>
          ))}
        </ol>
      )}
    </details>
  );
}

/** Each clause whose version differs from the published template's, and why it changed. */
function ChangesView({ detail, changed, numbers, onSelect }: {
  detail: TemplateDetail; changed: TemplateClause[]; numbers: Map<string, string>; onSelect: (key: string) => void;
}) {
  const v = detail.published!.version;
  return (
    <section className="tpl-sheet tpl-publish" aria-labelledby="tpl-chg">
      <h2 id="tpl-chg" className="tpl-publish__title">Changes since version {v}</h2>
      <p className="tpl-quiet">Version {v} is the one new contracts are drafted from today. This draft becomes
        version {detail.version} when it is published.</p>
      {!changed.length ? <p className="tpl-ok">No clause has changed since version {v}.</p> : (
        <div className="tpl-pubgroup"><h3>Changed <span>{changed.length}</span></h3>
          <ul>{changed.map((c) => (
            <li key={c.clause_key}>
              <span className="tpl-pubrow__what">{numbers.get(c.clause_key)} {displayTitle(c.title)}</span>
              <span className="tpl-pubrow__said">{c.published_version == null ? "New in this version" : approved(c)
                ? approvedLine(c.approval) : "Changed, not approved yet"}
                {c.approval?.reason ? <>. Reason: &ldquo;{c.approval.reason}&rdquo;</> : null}</span>
              <span className="tpl-pubrow__where">
                <button type="button" className="tpl-link" onClick={() => onSelect(c.clause_key)}>Open {displayTitle(c.title)}</button>
              </span>
            </li>
          ))}</ul></div>
      )}
    </section>
  );
}

function PublishView({ detail, check, checking, positions, onRetry, onSelect, onReplace, onPublished }: {
  detail: TemplateDetail; check: TemplateCheck | null; checking: boolean; positions: boolean; onRetry: () => void;
  onSelect: (key: string) => void; onReplace: (key: string) => void; onPublished: () => Promise<void>;
}) {
  const [refused, setRefused] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reference, setReference] = useState("");
  const title = (key: string) => displayTitle(detail.clauses.find((c) => c.clause_key === key)?.title ?? key);
  const standards = check?.standards ?? [];
  const inClauses = standards.filter((s) => placed(s) && !unchecked(s));
  const toRead = standards.filter((s) => placed(s) && unchecked(s));
  const missing = standards.filter((s) => !s.clause_keys.length && s.classification === "MISSING");
  const across = standards.filter((s) => !placed(s) && !missing.includes(s));
  const lines = problemLines(check?.problems ?? [], detail.clauses, check);
  const unapproved = detail.clauses.filter((c) => !approved(c));
  const ready = canPublish(detail, check);
  const stops = stopCount(check);

  if (detail.status !== "DRAFT") {
    return (
      <section className="tpl-sheet tpl-publish" aria-labelledby="tpl-pub">
        <h2 id="tpl-pub" className="tpl-publish__title">{statusWords(detail, check)}</h2>
        <p className="tpl-quiet">Published {formatDate(detail.published_at)}. New contracts are drafted from it; its clauses are fixed.</p>
        {detail.approval_reference ? (
          <p className="tpl-quiet">Approved outside LegalMind: {detail.approval_reference}</p>
        ) : null}
        <SpecialConditionsSetup readiness={detail.special_conditions} />
      </section>
    );
  }

  async function publish() {
    setBusy(true); setRefused(null); setError(null);
    try { await api.publishTemplate(detail.id, reference.trim()); await onPublished(); }
    catch (e) {
      if (e instanceof ApiError && e.problems?.length) setRefused(e.problems);
      else setError(describeError(e));
    } finally { setBusy(false); }
  }

  const std = (s: CheckStandard) => (
    <li key={s.code}>
      <span className="tpl-pubrow__what">{s.description ?? s.code}</span>
      <span className="tpl-pubrow__said">{shortWhy(s)}
        {positions && s.position ? <>. Our position: {s.position}</> : null}</span>
      {placed(s) ? (
        <span className="tpl-pubrow__where">{s.clause_keys.map((k) => (
          <button key={k} type="button" className="tpl-link"
                  onClick={() => unchecked(s) ? onSelect(k) : onReplace(k)}>
            {unchecked(s) ? `Read ${title(k)}` : `Replace in ${title(k)}`}
          </button>
        ))}</span>
      ) : s.clause_keys.length ? (
        <span className="tpl-pubrow__where">Read in {s.clause_keys.length} clauses</span>
      ) : null}
    </li>
  );

  return (
    <section className="tpl-sheet tpl-publish" aria-labelledby="tpl-pub">
      <h2 id="tpl-pub" className="tpl-publish__title">Before publishing {templateName(detail)}</h2>
      {checking && !check ? <p className="tpl-quiet"><CheckStatus state="checking" onRetry={onRetry} /></p> : null}
      {!checking && !check ? <p className="tpl-error"><CheckStatus state="failed" onRetry={onRetry} /></p> : null}
      {ready ? <p className="tpl-ok">Every clause is approved and the check finds nothing. It can be published.</p>
        : check ? <p className="tpl-publish__sum"><strong>{stops} {stops === 1 ? "problem stops" : "problems stop"} publishing</strong>
            {unapproved.length ? `, and ${unapproved.length} ${unapproved.length === 1 ? "clause is" : "clauses are"} not approved yet` : ""}.
            {" "}The check reads the text as it stands, as if every clause were approved.</p> : null}

      {inClauses.length ? (
        <div className="tpl-pubgroup"><h3>Differs from our standard <span>{inClauses.length}</span></h3>
          <ul>{inClauses.map(std)}</ul></div>
      ) : null}
      {toRead.length ? (
        <div className="tpl-pubgroup"><h3>Couldn&rsquo;t be checked, read it yourself <span>{toRead.length}</span></h3>
          <p className="tpl-help">The check found the clause but could not measure it against the standard.</p>
          <ul>{toRead.map(std)}</ul></div>
      ) : null}
      {across.length ? (
        <div className="tpl-pubgroup"><h3>Across the whole template <span>{across.length}</span></h3>
          <p className="tpl-help">The check reads these in many clauses at once, so they are not pinned to one.</p>
          <ul>{across.map(std)}</ul></div>
      ) : null}
      {missing.length ? (
        <div className="tpl-pubgroup"><h3>Not in this template <span>{missing.length}</span></h3>
          <p className="tpl-help">No clause says this yet. Our wording for it goes into the clause it belongs to.</p>
          <ul>{missing.map(std)}</ul></div>
      ) : null}
      {lines.length ? (
        <div className="tpl-pubgroup"><h3>Problems in the file <span>{lines.length}</span></h3>
          <ul>{lines.map((w) => (
            <li key={w.text}><span className="tpl-pubrow__what">{w.text}</span>
              {w.clauseKey ? <span className="tpl-pubrow__where"><button type="button" className="tpl-link"
                onClick={() => onReplace(w.clauseKey!)}>Replace in {title(w.clauseKey)}</button></span> : null}</li>
          ))}</ul></div>
      ) : null}
      {unapproved.length ? (
        <div className="tpl-pubgroup"><h3>Clauses not approved yet <span>{unapproved.length}</span></h3>
          <ul className="tpl-pubinline">{unapproved.map((c) => (
            <li key={c.clause_key}><button type="button" className="tpl-link" onClick={() => onSelect(c.clause_key)}>{displayTitle(c.title)}</button></li>
          ))}</ul></div>
      ) : null}
      <SpecialConditionsSetup readiness={detail.special_conditions} />
      {detail.flags?.length ? (
        <div className="tpl-pubgroup"><h3>Notes from the import <span>{detail.flags.length}</span></h3>
          <p className="tpl-help">About the front of the agreement (parties and recitals). They do not stop publishing. Read them before you do.</p>
          <ul>{detail.flags.map((f) => <li key={f}><span className="tpl-pubrow__what">{flagWords(f)}</span></li>)}</ul></div>
      ) : null}

      {ready || refused ? (
        <div className="tpl-publish__act">
          {ready ? (
            <div className="tpl-form tpl-approval-ref">
              <label htmlFor="tpl-approval-ref" className="tpl-label">Approval reference (optional)</label>
              <input id="tpl-approval-ref" className="tpl-reason" type="text" maxLength={300} value={reference}
                     aria-describedby="tpl-approval-ref-help" onChange={(e) => setReference(e.target.value)} />
              <p id="tpl-approval-ref-help" className="tpl-help">Who approved this text outside LegalMind, for example &ldquo;Management approval, email of 5 Nov 2026&rdquo;. It is kept with the publish record.</p>
            </div>
          ) : null}
          {ready ? <button type="button" className="ws-btn ws-btn--primary" disabled={busy} onClick={() => void publish()}>
            {busy ? "Publishing…" : "Publish"}</button> : null}
          {refused ? (
            <div className="tpl-refused" role="alert">
              <p><strong>Not published.</strong> The server refused it for {refused.length === 1 ? "this reason" : `these ${refused.length} reasons`}:</p>
              <ul>{problemLines(refused, detail.clauses, check).map((w) => {
                return <li key={w.text}>{w.clauseKey ? <button type="button" className="tpl-link" onClick={() => onSelect(w.clauseKey!)}>{w.text}</button> : w.text}</li>;
              })}</ul>
            </div>
          ) : null}
        </div>
      ) : null}
      {error ? <p className="tpl-error" role="alert">{error}</p> : null}
    </section>
  );
}

/** U1 (`AM-307`): whether agreed changes to a contract made from this template can go out
 *  as Special Conditions (Annexure A) — the server's readiness, in words. It never stops
 *  publishing; without it a deal goes back as a reply with tracked changes. */
export function SpecialConditionsSetup({ readiness }: { readiness?: SpecialConditionsReadiness | undefined }) {
  if (!readiness) return null;
  return (
    <div className="tpl-pubgroup" data-sc={readiness.ready ? "ready" : "not-set-up"}>
      <h3>Special Conditions (Annexure A)</h3>
      {readiness.ready ? (
        <p className="tpl-help"><strong>Set up.</strong> When a client&rsquo;s changes are agreed, a contract made from
          this template goes out as a final contract: this text unchanged, with each agreed change in Annexure A, and a
          clause saying Annexure A wins.</p>
      ) : (
        <>
          <p className="tpl-help"><strong>Not set up.</strong> Agreed changes go back to the client as tracked changes
            instead of a final contract. It does not stop publishing. An administrator sets it up when the template is
            imported; it cannot be set up from this page yet.</p>
          {readiness.missing.some((m) => m.code !== "NOT_CONFIGURED") ? (
            <ul>{readiness.missing.map((m) => (
              <li key={m.code}><span className="tpl-pubrow__what">{blockerText({ code: `SC_${m.code}`, detail: m.detail })}</span></li>
            ))}</ul>
          ) : null}
        </>
      )}
    </div>
  );
}
