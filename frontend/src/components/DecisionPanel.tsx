"use client";

/**
 * Legal Decision controls, attached to **one Evaluation** — locked Step 31, AB-1,
 * 49.7, 52.5, 52.7.
 *
 * Locked 52.7: "Optimistic UI is **not** used for Legal Decisions. A decision is
 * displayed only after the server confirms it, because a `409` (version collision)
 * is a real and meaningful outcome."
 *
 * So this component holds no local copy of "the decision I just made". It shows
 * what the server returned and nothing else, and a 409 is surfaced as its own
 * explicit state — someone else decided first, and this user must re-read before
 * deciding again. Showing their submission as accepted and reconciling later would
 * be a UI that lies about a legal act.
 *
 * **The conflict state freezes the form** (Phase 4, 2026-08-27): after a 409 the
 * submit control is disabled until the user explicitly reloads the latest state.
 * An earlier draft re-fetched automatically, which was well-meaning but wrong —
 * the decision-maker must *see and acknowledge* what was actually recorded before
 * the form will take another submission, not have the ground shift under a form
 * they may already be re-reading.
 *
 * **Keyboard shortcuts prepare, never record** (Phase 4): with `shortcutsActive`,
 * `d` jumps to the form, `a`/`r` preselect a decision type and focus the mandatory
 * justification. No key submits — a single keystroke must not complete a legal
 * act, and the server-mandatory justification (Step 31 r11) makes that structural
 * rather than polite.
 *
 * `REQUEST_CLARIFICATION` is never treated as a disposition (Step 31 r10); the
 * server reports `is_effective: false` and that is displayed as-is.
 *
 * There is no update or delete control: supersession is a create (Step 31 r14).
 */

import { useEffect, useRef, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import { DECISION_TYPES, submittableDecisionTypes } from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { shortcutKey } from "@/lib/shortcuts";
import type { Decision, Evaluation } from "@/lib/types";

import { DecisionHistory } from "./DecisionHistory";

type Outcome =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "recorded"; decision: Decision; findingStatus: string; isEffective: boolean }
  | { kind: "conflict"; message: string; requestId: string }
  | { kind: "error"; message: string };

/** Exported for the static test suite, like `AnswerView`. */
export function ConflictNotice({
  requestId,
  refreshing,
  onRefresh,
}: {
  requestId: string;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="decision__conflict" role="alert">
      <p className="error">
        <strong>Not recorded.</strong> This Evaluation was already updated by another
        user while this page was open. The form is paused until you load the latest
        state.
      </p>
      <button
        type="button"
        className="btn btn--secondary"
        onClick={onRefresh}
        disabled={refreshing}
      >
        {refreshing ? "Refreshing…" : "Refresh to see the latest decision"}
      </button>
      <p className="hint">Reference {requestId}</p>
    </div>
  );
}

export function DecisionPanel({
  evaluation,
  onRecorded,
  shortcutsActive = false,
}: {
  evaluation: Evaluation;
  /** Lets the Review screen re-fetch from the server rather than patch state. */
  onRecorded: () => void;
  /** True only on the panel keyboard navigation currently points at. */
  shortcutsActive?: boolean;
}) {
  const { identity } = useSession();
  const permissions = identity?.permissions ?? [];
  const available = submittableDecisionTypes(permissions);

  const [decisionType, setDecisionType] = useState<string>(available[0] ?? DECISION_TYPES[0]);
  const [justification, setJustification] = useState("");
  const [outcome, setOutcome] = useState<Outcome>({ kind: "idle" });
  const [historyOpen, setHistoryOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const typeRef = useRef<HTMLSelectElement | null>(null);
  const justificationRef = useRef<HTMLTextAreaElement | null>(null);

  /*
   * 52.1 r3 / 52.3 — a control the user cannot invoke is not rendered. This hides
   * the form; it does not protect the endpoint. A caller who reaches
   * POST /evaluations/{id}/decisions without `legal.decision` is refused with a
   * 403 whether or not this branch ran (SEC-02: no bypass reaches legal authority).
   */
  const canDecide = available.length > 0;
  const frozen = outcome.kind === "conflict";

  useEffect(() => {
    if (!shortcutsActive || !canDecide) return;
    function onKey(event: KeyboardEvent) {
      const key = shortcutKey(event);
      if (key === "d") {
        typeRef.current?.focus();
        typeRef.current?.scrollIntoView({ block: "center" });
      } else if (key === "a" && available.includes("ACCEPT_DEVIATION")) {
        setDecisionType("ACCEPT_DEVIATION");
        justificationRef.current?.focus();
      } else if (key === "r" && available.includes("REJECT")) {
        setDecisionType("REJECT");
        justificationRef.current?.focus();
      } else {
        return;
      }
      event.preventDefault();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [shortcutsActive, canDecide, available]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (frozen) return;
    setOutcome({ kind: "submitting" });
    try {
      const result = await api.recordDecision(evaluation.id, {
        decision_type: decisionType,
        justification,
        // 49.7 / N-1 Option C — the whole concurrency mechanism. The version the
        // client last saw; the server writes expected_version + 1 and a collision
        // is a 409 rather than a silent overwrite.
        ...(evaluation.current_decision
          ? { expected_version: evaluation.current_decision.version_number }
          : { expected_version: 0 }),
      });
      setOutcome({
        kind: "recorded",
        decision: result.decision,
        findingStatus: result.finding_status,
        isEffective: result.is_effective,
      });
      setJustification("");
      onRecorded();
    } catch (error) {
      if (error instanceof ApiError && error.isConflict) {
        // Deliberately NO automatic re-fetch here: the user must load the latest
        // state themselves, so what they read next is what they asked to read.
        setOutcome({
          kind: "conflict",
          message: error.message,
          requestId: error.requestId,
        });
        return;
      }
      setOutcome({ kind: "error", message: describeError(error) });
    }
  }

  async function refreshAfterConflict() {
    setRefreshing(true);
    try {
      // Pull the server's version of events; the evaluation prop re-renders with
      // the decision that actually won, and expected_version follows from it.
      onRecorded();
      setOutcome({ kind: "idle" });
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="decision">
      {/* Authority marker (DD-5 / audit finding #8): the one control on the page
          that changes the legal record announces itself as such. */}
      <p className="decision__label">Legal decision</p>
      {/*
        The current decision as the SERVER reports it, on the Evaluation payload.
        Not local state, so it cannot drift from what was actually recorded.
      */}
      {evaluation.current_decision ? (
        <p className="decision__current">
          Current decision: <strong>{evaluation.current_decision.decision_type}</strong>{" "}
          (version {evaluation.current_decision.version_number})
        </p>
      ) : evaluation.requires_decision ? (
        <p className="decision__pending">No decision recorded yet.</p>
      ) : null}

      <button
        type="button"
        className="link"
        onClick={() => setHistoryOpen((open) => !open)}
      >
        {historyOpen ? "Hide decision history" : "Decision history"}
      </button>
      {historyOpen ? <DecisionHistory evaluationId={evaluation.id} /> : null}

      {canDecide ? (
        <form className="decision__form" onSubmit={submit}>
          <label>
            Decision
            <select
              ref={typeRef}
              value={decisionType}
              onChange={(event) => setDecisionType(event.target.value)}
            >
              {available.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </label>

          <label>
            {/* Step 31 r11 / AM-15 — mandatory, and the server rejects whitespace. */}
            Justification (required)
            <textarea
              ref={justificationRef}
              required
              rows={3}
              value={justification}
              onChange={(event) => setJustification(event.target.value)}
            />
          </label>

          <button
            type="submit"
            className="btn btn--primary"
            disabled={outcome.kind === "submitting" || frozen}
          >
            {outcome.kind === "submitting" ? "Recording…" : "Record decision"}
          </button>
        </form>
      ) : null}

      {outcome.kind === "recorded" ? (
        <div className="decision__result">
          <p>
            Recorded as version {outcome.decision.version_number}. Finding status is
            now <strong>{outcome.findingStatus}</strong>.
          </p>
          {!outcome.isEffective ? (
            /*
             * Step 31 r10 and r15 — the decision exists in the append-only chain
             * but does not dispose of the Evaluation yet. Said plainly, because a
             * decision-maker who believes they have finished when they have not is
             * the failure this wording prevents.
             */
            <p className="warning">
              This decision is recorded but is <strong>not yet effective</strong> — it
              either requests clarification or awaits an independent second approval
              by a different authorized user.
            </p>
          ) : null}
        </div>
      ) : null}

      {outcome.kind === "conflict" ? (
        <ConflictNotice
          requestId={outcome.requestId}
          refreshing={refreshing}
          onRefresh={() => void refreshAfterConflict()}
        />
      ) : null}

      {outcome.kind === "error" ? <p className="error">{outcome.message}</p> : null}
    </div>
  );
}
