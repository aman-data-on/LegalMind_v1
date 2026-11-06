"use client";

/**
 * The final contract (`AM-307`, design 11 §8 U3–U5): our template's body exactly as we
 * sent it, with every agreed change as one entry of Special Conditions (Annexure A).
 *
 *   PackageBar              Changes tab — the dry run: what Annexure A would list, or what
 *                           stops it; the header's "Prepare final contract" opens the confirm
 *   PackageCard             Document tab, on the final contract — its files, sent or not
 *   SpecialConditionsTrace  inside the card — who agreed each entry, when and why
 *
 * Everything that decides is the server's: the dry run, its blockers, the gate on the
 * files and the trace (an internal note arrives only for a reader allowed it — absent,
 * never shown empty, SEC-07). A control the reader may not use is absent (52.4).
 */

import { useCallback, useEffect, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { ApiError, api, describeError } from "@/lib/api";
import { runStep, useStep } from "@/lib/nextStep";
import {
  blockerText, clauseName, entryAction, packageApplies,
  type PackageBlocker, type PackageEntry, type PackagePlan, type SpecialConditions,
} from "@/lib/package";
import type { Answer } from "@/lib/changes";
import type { DocumentVersion } from "@/lib/types";

import { ForUs, ReplyDownloads } from "./ChangesPane";
import { IconLock } from "./icons";
import { formatDate } from "@/lib/dates";


/** The dry run, fetched again whenever `key` changes (an answer was recorded). */
export function usePackagePlan(contractId: string, enabled: boolean, key: unknown) {
  const [plan, setPlan] = useState<PackagePlan | null>(null);
  const [seq, setSeq] = useState(0);
  const reload = useCallback(() => setSeq((n) => n + 1), []);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    // best effort: no dry run leaves "Prepare our reply" as the step
    api.packagePlan(contractId).then((got) => { if (!cancelled) setPlan(got); },
                                     () => { if (!cancelled) setPlan(null); });
    return () => { cancelled = true; };
  }, [contractId, enabled, key, seq]);
  return { plan: enabled && packageApplies(plan) ? plan : null, reload };
}

/** A prepared final contract's entries, each with the change it came from (`row_key`
 *  from its record) — for the Changes tab's "In the final contract" line. */
export function usePreparedEntries(version: DocumentVersion | null): PackageEntry[] | null {
  const id = version?.package ? version.id : null;
  const [entries, setEntries] = useState<PackageEntry[] | null>(null);
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    api.specialConditions(id).then(
      (sc) => {
        if (cancelled) return;
        setEntries(sc.entries.map((e) => {
          const t = sc.trace.find((x) => x.n === e.n);
          return { ...e, row_key: t?.row_key ?? "", ...(t?.answer ? { answer: t.answer as Answer } : {}) };
        }));
      },
      () => { if (!cancelled) setEntries(null); });
    return () => { cancelled = true; };
  }, [id]);
  return id ? entries : null;
}

/** The entries, in Annexure A's own order — the numbers are its numbering. */
function EntryList({ entries, showText = false }: { entries: PackageEntry[]; showText?: boolean }) {
  return (
    <ol className="lm-pkg__entries">
      {entries.map((e) => (
        <li key={e.n}>
          <span className="lm-pkg__n" aria-hidden="true">{e.n}</span>
          <span className="lm-pkg__what">
            <strong>{clauseName(e.target, e.new_number)}</strong>
            <span>{entryAction(e)}</span>
          </span>
          {e.effect ? <ForUs effect={e.effect} /> : null}
          {showText && e.text ? (
            <details className="lm-pkg__text">
              <summary>Wording</summary>
              <blockquote>{e.text}</blockquote>
            </details>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

function Blockers({ blockers, onPick }: { blockers: PackageBlocker[]; onPick?: (rowKey: string) => void }) {
  return (
    <ul className="lm-pkg__blockers">
      {blockers.map((b, i) => (
        <li key={`${b.code}-${b.row_key ?? i}`}>
          <span>{blockerText(b)}</span>
          {b.row_key && onPick ? (
            <button type="button" className="ws-escalate__link" onClick={() => onPick(b.row_key!)}>
              Open the change
            </button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

/** "Prepare final contract" (Changes tab): the dry run, said before it is asked. The
 *  header's primary opens the confirm here (`useStep("preparePackage")`); a refusal
 *  lists its reasons, a stale preview reloads the list for a second look. */
/** `AM-310`: shown with the secondary action, in these words (owner, 2026-11-05) */
export const RESTATE_WARNING = "Restating the whole contract can be read as a new contract and may need fresh "
  + "stamp duty. Use only on Legal’s advice.";

export function PackageBar({ contractId, plan: changesOnly, canPrepare, canRestate = false, nextVersion, onReload,
                             onPrepared, onPick }: {
  contractId: string; plan: PackagePlan; canPrepare: boolean;
  /** presentation only: holds `legal.approve_customization` (the server refuses anyone else) */
  canRestate?: boolean;
  /** the number the final contract will take */
  nextVersion: number;
  onReload: () => void; onPrepared: () => void; onPick: (rowKey: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<{ message: string; blockers: PackageBlocker[]; final: boolean } | null>(null);
  // AM-310: an amendment is the changes-only instrument; the restated dry run only on Legal's choice
  const [restated, setRestated] = useState<PackagePlan | null>(null);
  const [effective, setEffective] = useState("");
  const amendment = changesOnly.form !== undefined;
  const plan = restated ?? changesOnly;
  const instrument = amendment && !restated;
  useStep("preparePackage", useCallback(() => { if (changesOnly.available) setOpen(true); }, [changesOnly.available]));

  function close() { setOpen(false); setRestated(null); setRefused(null); }

  async function chooseRestated() {
    setRefused(null);
    try {
      setRestated(await api.packagePlan(contractId, "restated"));
      setOpen(true);
    } catch (cause) {
      setRefused({ message: describeError(cause), blockers: [], final: false });
    }
  }

  async function prepare() {
    if (!plan.entries_sha256) return;
    setBusy(true);
    setRefused(null);
    try {
      await api.preparePackage(contractId, plan.entries_sha256, amendment
        ? { form: restated ? "restated" : "changes_only", ...(instrument ? { effective_date: effective } : {}) }
        : undefined);
      close();
      onPrepared();
    } catch (cause) {
      const stale = cause instanceof ApiError && cause.code === "STALE_PREVIEW";
      setRefused({
        message: stale ? "The answers changed since this list was made. It has been read again — check it and prepare again."
          : cause instanceof ApiError && cause.code === "NO_AMENDMENT_TEMPLATE" ? blockerText({ code: cause.code })
          : cause instanceof ApiError && cause.status === 403 ? "Only Legal can restate the whole contract."
          : describeError(cause),
        blockers: cause instanceof ApiError ? cause.blockers ?? [] : [],
        // not ready: asking again fails the same way, so the way forward is the change
        final: cause instanceof ApiError && (cause.code === "PACKAGE_NOT_READY" || cause.code === "NO_AMENDMENT_TEMPLATE"
          || cause.code === "AMENDMENT_TEMPLATE_INCOMPLETE" || cause.status === 403),
      });
      onReload();
    } finally {
      setBusy(false);
    }
  }

  const count = changesOnly.entries.length;
  const precedence = changesOnly.precedence?.number;
  const changes = count === 1 ? "the 1 agreed change" : `the ${count} agreed changes`;
  const reasons = changesOnly.restatement ?? [];
  const action = restated ? "Restate the whole contract" : amendment ? "Prepare amendment" : "Prepare final contract";
  return (
    <section className="lm-pkg" aria-labelledby="lm-pkg-title" data-state={changesOnly.available ? "ready" : "blocked"}>
      <h2 id="lm-pkg-title" className="lm-pkg__title">{amendment ? "Amendment" : "Final contract"}</h2>
      {changesOnly.available ? (
        <>
          <p className="lm-pkg__lead">
            {amendment ? <>
              A short amendment listing only {changes}, in the amendment template&rsquo;s own words, with its
              no-other-change, precedence and counterparts clauses. The signed contract stays the operative document.
            </> : <>
              Our contract as we sent it, with {changes} in Special Conditions (Annexure A).
              {" "}{precedence ? `Clause ${precedence}` : "The order-of-precedence clause"} says Annexure A wins where
              the two differ.
            </>}
          </p>
          <EntryList entries={changesOnly.entries} />
          {amendment && canPrepare && canRestate ? (
            <div className="lm-pkg__restate">
              {reasons.length ? (
                <p>Legal may prefer to restate the whole contract here. That is Legal&rsquo;s call: {reasons.join(" ")}</p>
              ) : null}
              <p>
                <button type="button" className="ws-escalate__link" onClick={() => void chooseRestated()}>
                  Restate the whole contract instead
                </button>
              </p>
              <p className="lm-pkg__warn">{RESTATE_WARNING}</p>
              {!open && refused ? <p role="alert"><strong>{refused.message}</strong></p> : null}
            </div>
          ) : null}
          {canPrepare ? (
            <p className="lm-pkg__alt">
              <button type="button" className="ws-escalate__link" onClick={() => runStep("prepareReply")}>
                Prepare a reply with tracked changes instead
              </button>
            </p>
          ) : null}
        </>
      ) : (
        <>
          <p className="lm-pkg__lead">It can be prepared once {plan.blockers.length === 1 ? "this is" : "these are"} sorted:</p>
          <Blockers blockers={changesOnly.blockers} onPick={onPick} />
          {changesOnly.blockers.some((b) => b.code.startsWith("SC_")) ? (
            <p className="lm-pkg__lead">Legal sets up Special Conditions on the template, on the Templates page.</p>
          ) : null}
        </>
      )}
      {open ? (
        <Dialog onClose={() => { if (!busy) close(); }} titleId="lm-pkg-dialog-title">
          <h2 id="lm-pkg-dialog-title">{action}</h2>
          <p className="lm-pkg__body">
            {instrument ? <>This makes version {nextVersion}: an amendment naming the signed contract, with{" "}
              {plan.entries.length === 1 ? "this change" : `these ${plan.entries.length} changes`} and the template&rsquo;s
              own clauses and signature blocks.</>
              : <>This makes version {nextVersion}: our contract{restated ? ", restated in full" : " as we sent it"}, plus
              Special Conditions (Annexure A) with {plan.entries.length === 1 ? "this entry"
                : `these ${plan.entries.length} entries`}.</>}
            {" "}It is reviewed like any upload. Nothing goes to the client until you send it.
          </p>
          {restated ? <p className="lm-pkg__warn" role="note">{RESTATE_WARNING}</p> : null}
          <EntryList entries={plan.entries} showText />
          {instrument ? (
            <label className="lm-pkg__date">
              <span>Takes effect on</span>
              <input type="date" required value={effective} onChange={(e) => setEffective(e.target.value)} />
            </label>
          ) : null}
          {refused ? (
            <div className="cx-blocked" role="alert">
              <p className="cx-blocked__title">{refused.message}</p>
              {refused.blockers.length ? (
                <Blockers blockers={refused.blockers} onPick={(key) => { setOpen(false); onPick(key); }} />
              ) : null}
            </div>
          ) : null}
          <div className="cx-dialog__foot">
            <button type="button" className="ws-btn" disabled={busy} onClick={close}>Cancel</button>
            {canPrepare && !refused?.final ? (
              <button type="button" className="ws-btn ws-btn--primary" disabled={busy || (instrument && !effective)}
                      aria-busy={busy} onClick={() => void prepare()}>
                {busy ? "Preparing…" : action}
              </button>
            ) : null}
          </div>
          {busy ? <p className="ws-visually-hidden" role="status">Preparing…</p> : null}
        </Dialog>
      ) : null}
    </section>
  );
}

/** The final contract on the Document tab: what it is, its files once nothing in it is
 *  open, and Annexure A's record. "Send for signature" is the header's primary. */
export function PackageCard({ version, versions, filesOpen }: {
  version: DocumentVersion; versions: DocumentVersion[];
  /** the stage lets the files out (`AM-293`: nothing undecided is offered as sendable) */
  filesOpen: boolean;
}) {
  const pkg = version.package;
  if (!pkg) return null;
  const theirs = versions.find((v) => v.id === pkg.of_version_id);
  const n = pkg.special_conditions;
  const instrument = pkg.form === "changes_only";        // AM-310
  return (
    <section className="ws-replynote lm-pkgcard" aria-label="Final contract" data-sent={version.sent_at ? "" : undefined}>
      <div className="ws-replynote__text">
        <h2 className="ws-replynote__title">
          Version {version.version_number} is the {instrument ? "amendment" : "final contract"}
        </h2>
        <p className="ws-replynote__sub">
          {instrument ? `An amendment listing ${n === 1 ? "1 change" : `${n} changes`} to the signed contract`
            : `Our contract as we sent it, with ${n === 1 ? "1 Special Condition" : `${n} Special Conditions`} (Annexure A)`}
          {theirs ? `, answering the client’s version ${theirs.version_number}` : ""}.{" "}
          {version.sent_at ? <strong>Sent for signature on {formatDate(version.sent_at)}.</strong>
            : filesOpen ? "Not sent yet."
            : "Its review still has a point open, so the files are held until it is decided."}
        </p>
      </div>
      {filesOpen || version.sent_at ? (
        <div className="ws-replynote__acts"><ReplyDownloads version={version} pdf="pdf" /></div>
      ) : null}
      <SpecialConditionsTrace versionId={version.id} count={n} instrument={instrument} />
    </section>
  );
}

type TraceLoad = { kind: "idle" } | { kind: "loading" } | { kind: "ready"; sc: SpecialConditions } | { kind: "error"; message: string };

/** Annexure A's record, read when opened: each entry, who agreed it, when, why, and the
 *  notes the server sends this reader. */
export function SpecialConditionsTrace({ versionId, count, instrument = false }: {
  versionId: string; count: number; instrument?: boolean;
}) {
  const [load, setLoad] = useState<TraceLoad>({ kind: "idle" });
  function read() {
    setLoad({ kind: "loading" });
    api.specialConditions(versionId).then((sc) => setLoad({ kind: "ready", sc }),
                                          (cause: unknown) => setLoad({ kind: "error", message: describeError(cause) }));
  }
  return (
    <details className="lm-pkgtrace" onToggle={(event) => { if ((event.target as HTMLDetailsElement).open && load.kind === "idle") read(); }}>
      <summary>{instrument ? `What the amendment changes (${count})` : `What is in Annexure A (${count})`}</summary>
      {load.kind === "loading" ? <p className="ws-pane__note" role="status">Reading…</p> : null}
      {load.kind === "error" ? (
        <p className="cx-error" role="alert">{load.message}{" "}
          <button type="button" className="ws-escalate__link" onClick={read}>Try again</button>
        </p>
      ) : null}
      {load.kind === "ready" ? <TraceList sc={load.sc} /> : null}
    </details>
  );
}

/** Annexure A's entries with their record — exported for the test. */
export function TraceList({ sc }: { sc: SpecialConditions }) {
  return (
    <ol className="lm-pkgtrace__list">
      {sc.entries.map((e) => {
        const t = sc.trace.find((x) => x.n === e.n);
        return (
          <li key={e.n}>
            <p className="lm-pkgtrace__head">
              <span className="lm-pkg__n" aria-hidden="true">{e.n}</span>
              <strong>{clauseName(e.target, e.new_number)}</strong>
              {t?.effect ? <ForUs effect={t.effect} /> : null}
            </p>
            <p className="lm-pkgtrace__line">
              {entryAction(t?.answer ? { ...e, answer: t.answer as Answer } : e)}
              {t?.decided_by ? <>, answered by {t.decided_by}</> : null}
              {t?.decided_at ? <> on {formatDate(t.decided_at)}</> : null}.
              {t?.decision_ids.length ? <> Agreed by {t.decision_ids.length === 1 ? "a Legal Decision" : `${t.decision_ids.length} Legal Decisions`}.</> : null}
            </p>
            {t?.reason ? <p className="lm-pkgtrace__note"><span>Reason, kept in LegalMind</span>{t.reason}</p> : null}
            {t?.client_note ? (
              <p className="cx-note-read cx-note-read--client"><span>Sent to the client</span>{t.client_note}</p>
            ) : null}
            {t?.internal_note ? (
              <p className="cx-note-read cx-note-read--internal"><span><IconLock size={12} /> Internal note, never sent to the client</span>{t.internal_note}</p>
            ) : null}
            {e.text ? (
              <details className="lm-pkg__text"><summary>Wording</summary><blockquote>{e.text}</blockquote></details>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
