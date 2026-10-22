"use client";

/**
 * The Legal Decision control for one Evaluation — the Authority register's one
 * control that changes the legal record (locked Step 31, AB-1, 49.7, 52.5, 52.7).
 * Ported from the legacy `DecisionPanel` with its safety properties intact, not
 * reinvented: no optimistic UI (52.7 — the decision shown is the decision the
 * server confirmed), and a `409` FREEZES the form until an explicit refresh
 * rather than auto-refetching (2026-08-27 hardening — the ground must not shift
 * under a decision-maker mid-read).
 *
 * AB-103 (owner, 2026-10-22): everyone who can see the card sees what was decided, by
 * whom and why — only the Decide button is for deciders; each choice says what it does
 * before it is recorded; and a point measured against several standards is decided in
 * one step, the other items named before confirming (AM-179).
 */

import { useEffect, useRef, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import { DECISION_EFFECTS, decidedWords, decisionLabel } from "@/lib/labels";
import { DECISION_TYPES, submittableDecisionTypes } from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Decision, Evaluation } from "@/lib/types";

type Outcome =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "recorded"; decision: Decision | null; isEffective: boolean; count: number }
  | { kind: "conflict"; message: string; requestId: string; mine: boolean }
  | { kind: "error"; message: string };

/** Another requirement measured on the same clause (AM-179) — decided with this one. */
export interface GroupItem {
  evaluation: Evaluation;
  title: string;
}

export function DecisionControl({
  evaluation,
  onRecorded,
  prepared,
  reviewId,
  group = [],
}: {
  evaluation: Evaluation;
  onRecorded: () => void;
  /** A keyboard request to PREPARE a decision — preselect the type and focus the
   *  justification. Carries a `seq` so pressing the same key twice re-applies.
   *  Never submits: recording stays an explicit act (Step 31 r11). */
  prepared?: { decisionType: (typeof DECISION_TYPES)[number]; seq: number } | null;
  reviewId?: string;
  group?: GroupItem[];
}) {
  const { identity } = useSession();
  const available = submittableDecisionTypes(identity?.permissions ?? []);
  const [decisionType, setDecisionType] = useState<string>(available[0] ?? DECISION_TYPES[0]);
  const [justification, setJustification] = useState("");
  const justificationRef = useRef<HTMLTextAreaElement | null>(null);
  const [outcome, setOutcome] = useState<Outcome>({ kind: "idle" });
  // One small "Decide" per open point (owner, 2026-10-21); the form opens on press, or
  // when a keyboard shortcut prepares it — never fourteen forms stacked open.
  const [open, setOpen] = useState(false);
  // focus the justification once the form has rendered — a shortcut or "Decide" asks for
  // it before the textarea exists (CI's keyboard test, 2026-10-21)
  const [focusSeq, setFocusSeq] = useState(0);
  useEffect(() => {
    if (open && focusSeq) justificationRef.current?.focus();
  }, [open, focusSeq]);
  const [refreshing, setRefreshing] = useState(false);

  /*
   * A keyboard PREPARE request (the `a` / `r` shortcuts). It sets this form's
   * own React state and moves focus — it never submits, which is the whole
   * point of calling it "prepare": Step 31 r11 keeps recording an explicit act,
   * and 52.7's no-optimistic-UI posture applies to input as much as output.
   *
   * Keyed on `seq` rather than the type, so pressing the same key twice
   * re-applies instead of silently doing nothing.
   */
  useEffect(() => {
    if (!prepared) return;
    if (!available.includes(prepared.decisionType)) return;
    setOpen(true);
    setDecisionType(prepared.decisionType);
    setFocusSeq((n) => n + 1);
    // Keyed on `seq` ALONE, deliberately: `available` is rebuilt every render, so
    // including it re-ran this effect continuously and stole focus back into the
    // justification on every keystroke elsewhere on the page.
  }, [prepared?.seq]);  // eslint-disable-line react-hooks/exhaustive-deps

  const current = evaluation.current_decision;
  // 52.1 r3 / 52.3 — a reader without legal.decision sees the decision and no control;
  // the endpoint refuses such a caller regardless of what rendered (SEC-02). Returned
  // after every hook, so the hook order never changes between renders.
  const canDecide = available.length > 0;
  if (!canDecide && !current) return null;
  const frozen = outcome.kind === "conflict";
  // the other items of this point a decision would cover — those still undecided
  const pending = group.filter(({ evaluation: e }) =>
    !e.current_decision || e.current_decision.decision_type === "REQUEST_CLARIFICATION");
  const alreadyDecided = group.length - pending.length;

  async function refreshAfterConflict() {
    setRefreshing(true);
    try {
      // Pull the server's version of events — `evaluation.current_decision`
      // re-renders from the parent's re-fetch, never from local state.
      onRecorded();
      setOutcome({ kind: "idle" });
      setOpen(false);         // what won is shown; a further change starts from the button
    } finally {
      setRefreshing(false);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (frozen || outcome.kind === "submitting") return;     // never twice in flight
    setOutcome({ kind: "submitting" });
    try {
      if (pending.length > 0 && reviewId) {
        const items = [evaluation, ...pending.map((g) => g.evaluation)];
        const result = await api.groupDecision(reviewId, {
          evaluation_ids: items.map((e) => e.id),
          decision_type: decisionType,
          justification,
          expected_versions: Object.fromEntries(items.map((e) => [
            e.id, e.current_decision?.version_number ?? 0])),
        });
        setOutcome({ kind: "recorded", decision: result.decided[0] ?? null,
                     isEffective: true, count: result.decided.length });
      } else {
        const result = await api.recordDecision(evaluation.id, {
          decision_type: decisionType,
          justification,
          expected_version: current?.version_number ?? 0,
        });
        setOutcome({ kind: "recorded", decision: result.decision,
                     isEffective: result.is_effective, count: 1 });
      }
      setJustification("");
      setOpen(false);
      onRecorded();
    } catch (error) {
      if (error instanceof ApiError && error.isConflict) {
        // a lost response retried, or another reviewer first? Ask the record (O7)
        const chain = await api.decisions(evaluation.id).catch(() => [] as Decision[]);
        const latest = chain.at(-1);
        const mine = !!latest && latest.decided_by === identity?.user_id
          && latest.decision_type === decisionType;
        setOutcome({ kind: "conflict", message: error.message, requestId: error.requestId,
                     mine });
        return;
      }
      setOutcome({ kind: "error", message: describeError(error) });
    }
  }

  return (
    <div className="ws-decision">
      <p className="ws-decision__label">Legal decision</p>
      {current ? (
        <p className="ws-decision__done">
          <strong>{decidedWords(current.decision_type)}</strong>
          {current.decided_by_name ? ` — ${current.decided_by_name}` : ""}
          {current.created_at
            ? `, ${new Date(current.created_at).toLocaleDateString("en-IN", {
                day: "numeric", month: "short", year: "numeric" })}` : ""}
          {current.justification ? `: “${current.justification}”` : ""}
          {current.version_number > 1 ? ` (version ${current.version_number})` : ""}
        </p>
      ) : null}

      {!canDecide ? null : !open && !frozen ? (
        <button type="button" className="ws-btn ws-btn--primary ws-decision__open"
                onClick={() => {
                  setOpen(true);
                  setFocusSeq((n) => n + 1);
                }}>
          {current ? "Change the decision" : "Decide"}
        </button>
      ) : (
      <form className="ws-decision__form" onSubmit={submit}>
        <label>
          Decision
          <select value={decisionType} onChange={(event) => setDecisionType(event.target.value)}>
            {available.map((type) => (
              <option key={type} value={type}>
                {decisionLabel(type)}
              </option>
            ))}
          </select>
        </label>
        {DECISION_EFFECTS[decisionType] ? (
          <p className="ws-decision__effect">{DECISION_EFFECTS[decisionType]}</p>
        ) : null}
        {pending.length > 0 ? (
          <div className="ws-decision__covers">
            <p>This decision also covers the same clause measured against:</p>
            <ul>
              {pending.map(({ evaluation: e, title }) => <li key={e.id}>{title}</li>)}
            </ul>
            {alreadyDecided > 0 ? (
              <p className="ws-pane__note">
                {alreadyDecided === 1
                  ? "1 already decided is left as it is."
                  : `${alreadyDecided} already decided are left as they are.`}
              </p>
            ) : null}
          </div>
        ) : null}
        <label>
          Justification (required)
          <textarea
            ref={justificationRef}
            required
            rows={3}
            value={justification}
            onChange={(event) => setJustification(event.target.value)}
          />
        </label>
        <button type="submit" className="ws-btn ws-btn--primary" disabled={outcome.kind === "submitting" || frozen}>
          {outcome.kind === "submitting" ? "Recording…"
            : pending.length > 0 ? `Record for all ${pending.length + 1}` : "Record decision"}
        </button>
        {!frozen ? (
          <button type="button" className="ws-btn" onClick={() => setOpen(false)}
                  disabled={outcome.kind === "submitting"}>
            Cancel
          </button>
        ) : null}
      </form>
      )}

      {outcome.kind === "recorded" ? (
        <p className="ws-pane__note" role="status">
          {outcome.count > 1 ? `Recorded for ${outcome.count} items.`
            : outcome.decision ? `Recorded as version ${outcome.decision.version_number}.`
            : "Recorded."}
          {!outcome.isEffective ? " Not yet effective — awaits clarification or a second approval." : ""}
        </p>
      ) : null}

      {outcome.kind === "conflict" ? (
        <div className="ws-decision__conflict" role="alert">
          <p>
            <strong>Not recorded.</strong>{" "}
            {outcome.mine
              ? <>Your same decision is already on record — an earlier attempt reached the
                  server, or you decided in another window. Nothing was recorded twice.</>
              : <>This Evaluation was already updated by another user. The form is paused
                  until you load the latest state.</>}
          </p>
          <button type="button" className="ws-btn" onClick={() => void refreshAfterConflict()} disabled={refreshing}>
            {refreshing ? "Refreshing…" : "Refresh to see the latest decision"}
          </button>
          <p className="ws-pane__note">Reference {outcome.requestId}</p>
        </div>
      ) : null}

      {outcome.kind === "error" ? (
        <p className="ws-pane__note" role="alert">
          {outcome.message}
        </p>
      ) : null}
    </div>
  );
}
