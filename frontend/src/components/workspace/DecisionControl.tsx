"use client";

/**
 * The Legal Decision control for one Evaluation — the Authority register's one
 * control that changes the legal record (locked Step 31, AB-1, 49.7, 52.5, 52.7).
 * Ported from the legacy `DecisionPanel` with its safety properties intact, not
 * reinvented: no optimistic UI (52.7 — the decision shown is the decision the
 * server confirmed), and a `409` FREEZES the form until an explicit refresh
 * rather than auto-refetching (2026-08-27 hardening — the ground must not shift
 * under a decision-maker mid-read).
 */

import { useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import { DECISION_TYPES, submittableDecisionTypes } from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Decision, Evaluation } from "@/lib/types";

type Outcome =
  | { kind: "idle" }
  | { kind: "submitting" }
  | { kind: "recorded"; decision: Decision; isEffective: boolean }
  | { kind: "conflict"; message: string; requestId: string }
  | { kind: "error"; message: string };

export function DecisionControl({
  evaluation,
  onRecorded,
}: {
  evaluation: Evaluation;
  onRecorded: () => void;
}) {
  const { identity } = useSession();
  const available = submittableDecisionTypes(identity?.permissions ?? []);
  const [decisionType, setDecisionType] = useState<string>(available[0] ?? DECISION_TYPES[0]);
  const [justification, setJustification] = useState("");
  const [outcome, setOutcome] = useState<Outcome>({ kind: "idle" });

  const [refreshing, setRefreshing] = useState(false);

  // 52.1 r3 / 52.3 — hides the form; the endpoint refuses a caller without
  // legal.decision regardless of whether this branch ran (SEC-02).
  if (available.length === 0) return null;
  const frozen = outcome.kind === "conflict";

  async function refreshAfterConflict() {
    setRefreshing(true);
    try {
      // Pull the server's version of events — `evaluation.current_decision`
      // re-renders from the parent's re-fetch, never from local state.
      onRecorded();
      setOutcome({ kind: "idle" });
    } finally {
      setRefreshing(false);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (frozen) return;
    setOutcome({ kind: "submitting" });
    try {
      const result = await api.recordDecision(evaluation.id, {
        decision_type: decisionType,
        justification,
        expected_version: evaluation.current_decision?.version_number ?? 0,
      });
      setOutcome({ kind: "recorded", decision: result.decision, isEffective: result.is_effective });
      setJustification("");
      onRecorded();
    } catch (error) {
      if (error instanceof ApiError && error.isConflict) {
        setOutcome({ kind: "conflict", message: error.message, requestId: error.requestId });
        return;
      }
      setOutcome({ kind: "error", message: describeError(error) });
    }
  }

  return (
    <div className="ws-decision">
      <p className="ws-decision__label">Legal decision</p>
      {evaluation.current_decision ? (
        <p className="ws-pane__note">
          Current: <strong>{evaluation.current_decision.decision_type}</strong> (version{" "}
          {evaluation.current_decision.version_number})
        </p>
      ) : null}

      <form className="ws-decision__form" onSubmit={submit}>
        <label>
          Decision
          <select value={decisionType} onChange={(event) => setDecisionType(event.target.value)}>
            {available.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label>
          Justification (required)
          <textarea
            required
            rows={3}
            value={justification}
            onChange={(event) => setJustification(event.target.value)}
          />
        </label>
        <button type="submit" className="ws-btn ws-btn--primary" disabled={outcome.kind === "submitting" || frozen}>
          {outcome.kind === "submitting" ? "Recording…" : "Record decision"}
        </button>
      </form>

      {outcome.kind === "recorded" ? (
        <p className="ws-pane__note">
          Recorded as version {outcome.decision.version_number}.
          {!outcome.isEffective ? " Not yet effective — awaits clarification or a second approval." : ""}
        </p>
      ) : null}

      {outcome.kind === "conflict" ? (
        <div className="ws-decision__conflict" role="alert">
          <p>
            <strong>Not recorded.</strong> This Evaluation was already updated by another user.
            The form is paused until you load the latest state.
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
