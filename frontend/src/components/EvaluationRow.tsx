/**
 * One scoped Evaluation — the authoritative layer (AB-1, 45B re-lock, 52.5).
 *
 * **This is the most confidentiality-sensitive component in the application.**
 *
 * Locked 52.4: "The UI must render an omitted field as simply absent — no
 * placeholder, no 'hidden', no greyed-out row, no lock icon. A visible marker
 * would disclose that an internal legal position exists, which is exactly what
 * LEGAL-02 prevents. The normal-user and authorized-legal views are structurally
 * different views, not the same view with fields masked."
 *
 * So every legal-position field below is rendered by testing whether the property
 * is **present in the response**, never by asking what the caller may see. Those
 * are different questions and only the first one is safe: a permission check would
 * let the component know a value was withheld, and anything it then rendered —
 * even whitespace, even a differently sized row — would be the marker 52.4
 * forbids.
 *
 * Nothing here is computed. `classification`, `rule_outcome` and
 * `requires_decision` are rendered exactly as received (38.23, 52.1 r2, 52.7).
 */

import type { Evaluation } from "@/lib/types";

/**
 * 52.5 — an Evaluation whose rule outcome is `APPROVAL_REQUIRED` or
 * `UNACCEPTABLE` is visually distinct.
 *
 * Note this can only fire for a caller who receives `rule_outcome` at all. For
 * everyone else the row is styled by `requires_decision`, which is not a legal
 * position and which the API returns to every caller (49.7's own example).
 */
const ATTENTION_OUTCOMES = new Set(["APPROVAL_REQUIRED", "UNACCEPTABLE"]);

export function evaluationNeedsAttention(evaluation: Evaluation): boolean {
  if ("rule_outcome" in evaluation && evaluation.rule_outcome !== undefined) {
    if (ATTENTION_OUTCOMES.has(evaluation.rule_outcome)) return true;
  }
  return evaluation.requires_decision;
}

export function EvaluationRow({
  evaluation,
  children,
}: {
  evaluation: Evaluation;
  /** Decision controls and history, supplied by the Review screen. */
  children?: React.ReactNode;
}) {
  const attention = evaluationNeedsAttention(evaluation);

  return (
    <li
      className={`evaluation${attention ? " evaluation--attention" : ""}`}
      data-scope={evaluation.scope_key}
      data-evaluation-id={evaluation.id}
    >
      <div className="evaluation__head">
        <span className="evaluation__scope">
          {evaluation.scope_key}
          {evaluation.scope_label ? <em> · {evaluation.scope_label}</em> : null}
        </span>
        <span className="evaluation__kind">{evaluation.evaluation_kind}</span>
        <span className={`badge badge--${evaluation.classification.toLowerCase()}`}>
          {evaluation.classification}
        </span>

        {/*
          Presence-tested, not permission-tested. When the server omitted it there
          is no element at all — not an empty span, not a placeholder (52.4).
        */}
        {evaluation.rule_outcome !== undefined ? (
          <span className={`outcome outcome--${evaluation.rule_outcome.toLowerCase()}`}>
            {evaluation.rule_outcome}
          </span>
        ) : null}

        {evaluation.requires_decision ? (
          <span className="evaluation__flag">Decision required</span>
        ) : null}
      </div>

      <dl className="evaluation__facts">
        {/* The counterparty's own contract value — not an internal position. */}
        <dt>Found in contract</dt>
        <dd>{renderValue(evaluation.actual_value)}</dd>

        {evaluation.expected_value !== undefined ? (
          <>
            <dt>Company Standard</dt>
            <dd>{renderValue(evaluation.expected_value)}</dd>
          </>
        ) : null}

        {evaluation.operator !== undefined && evaluation.operator !== null ? (
          <>
            <dt>Comparison</dt>
            <dd>{evaluation.operator}</dd>
          </>
        ) : null}
      </dl>

      {/*
        Rule 12's explainability chain: Evidence → Fact → Standard → Rule →
        Result. It contains the standard and the rule, so the API gates it behind
        `legal_position.view` and it is likewise presence-tested here.
      */}
      {evaluation.explanation !== undefined && evaluation.explanation.length > 0 ? (
        <ol className="evaluation__explanation">
          {evaluation.explanation.map((step, index) => (
            <li key={index}>{step}</li>
          ))}
        </ol>
      ) : null}

      <p className="evaluation__provenance">
        {/* 45B.10 / AM-19 — which evaluator version produced this result. */}
        Evaluator {evaluation.evaluator_type} · {evaluation.evaluator_version} ·{" "}
        {evaluation.evidence_refs.length} evidence reference
        {evaluation.evidence_refs.length === 1 ? "" : "s"}
      </p>

      {/*
        REC-07 — diagnostics are persisted with the Evaluation for auditability.
        Diagnostic metadata only: they cannot produce or alter a legal finding, and
        are labelled so they are never read as one.
      */}
      {evaluation.diagnostics.length > 0 ? (
        <details className="evaluation__diagnostics">
          <summary>Extraction diagnostics ({evaluation.diagnostics.length})</summary>
          <p className="hint">
            Diagnostic information about reading the document. Not a legal
            conclusion.
          </p>
          <ul>
            {evaluation.diagnostics.map((note, index) => (
              <li key={index}>{note}</li>
            ))}
          </ul>
        </details>
      ) : null}

      {children}
    </li>
  );
}

/** Values arrive as arbitrary JSON; nothing is interpreted, only displayed. */
function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "Not recorded";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}
