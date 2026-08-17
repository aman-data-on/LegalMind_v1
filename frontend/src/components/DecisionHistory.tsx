"use client";

/**
 * The append-only decision chain for one Evaluation — locked Step 31 r14/r20,
 * 49.7, 52.5.
 *
 * Locked 52.5: "Decision history is viewable per Evaluation, with the current
 * version distinguished from superseded ones."
 *
 * Superseded versions are shown, never hidden and never struck through into
 * illegibility: the chain is the record of who decided what and when, and a
 * superseded decision was a real act by a real person. The server marks the
 * current one (`is_current`, derived from the highest `version_number`), so this
 * component never works it out for itself.
 */

import { useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import type { Decision } from "@/lib/types";

export function DecisionHistory({ evaluationId }: { evaluationId: string }) {
  const [chain, setChain] = useState<Decision[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .decisions(evaluationId)
      .then((decisions) => {
        if (active) setChain(decisions);
      })
      .catch((cause: unknown) => {
        if (active) setError(describeError(cause));
      });
    return () => {
      active = false;
    };
  }, [evaluationId]);

  if (error) return <p className="error">{error}</p>;
  if (chain === null) return <p className="hint">Loading decision history…</p>;
  if (chain.length === 0) return <p className="hint">No decisions recorded.</p>;

  return (
    <ol className="decision-history">
      {chain.map((decision) => (
        <li
          key={decision.id}
          className={decision.is_current ? "decision-history--current" : "decision-history--superseded"}
        >
          <p>
            <strong>v{decision.version_number}</strong> · {decision.decision_type}
            {decision.is_current ? (
              <span className="tag tag--current"> current</span>
            ) : (
              <span className="tag tag--superseded"> superseded</span>
            )}
          </p>
          <p className="decision-history__meta">
            {decision.created_at ?? "date not recorded"} · decided by{" "}
            {decision.decided_by}
          </p>
          {/* Step 31 r11 — the reason is part of the record, so it is shown. */}
          <blockquote>{decision.justification}</blockquote>
        </li>
      ))}
    </ol>
  );
}
