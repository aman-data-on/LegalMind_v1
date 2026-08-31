"use client";

/**
 * The decision queue — needs-decision first, all-findings one click away
 * (locked 52.5, DD-1's own recommendation, finalized by DD-7 §3): a Finding
 * shows its derived `classification` AND every scoped Evaluation, never a
 * single collapsed verdict (49.7 r1). Decision controls attach to the
 * Evaluation, never the Finding (AB-1).
 *
 * A Review is resolved for the CURRENT document version via
 * `GET /reviews?contract_id=` (2026-08-30 addition to the frontend client only
 * — the backend already allow-lists this filter, 49.6) — the workspace has no
 * Review of its own to hand down from `WorkspacePage`. Creating a Review needs
 * a published configuration snapshot, a distinct capability this slice
 * deliberately does not build (excluded, stated plainly): the pane says so
 * rather than offering a raw id-pasting form or a link back into the legacy
 * app.
 *
 * Evidence links reuse the highlight mechanism from slice 1 — a citation and a
 * verdict now point at the document through the exact same gesture.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ErrorBanner } from "@/components/Feedback";
import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { DocumentVersion, Evaluation, Finding, Review } from "@/lib/types";

import { DecisionControl } from "./DecisionControl";
import { EscalateControl } from "./EscalateControl";
import { useHighlight } from "./highlight";

type Load =
  | { kind: "loading" }
  | { kind: "no-review" }
  | { kind: "ready"; review: Review; findings: Finding[] }
  | { kind: "error"; error: unknown };

const ATTENTION_OUTCOMES = new Set(["APPROVAL_REQUIRED", "UNACCEPTABLE"]);
const CALM_CLASSIFICATIONS = new Set(["MATCH"]);
const CALM_OUTCOMES = new Set(["ACCEPTABLE", "NOT_APPLICABLE"]);

export function FindingsPane({ contractId, version }: { contractId: string; version: DocumentVersion }) {
  const { can } = useSession();
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [view, setView] = useState<"attention" | "all">("attention");

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const { items: reviews } = await api.reviews({ contract_id: contractId, page_size: 100 });
      const review = reviews.find((r) => r.document_version_id === version.id);
      if (!review) {
        setState({ kind: "no-review" });
        return;
      }
      const { items: findings } = await api.findings(review.id, { page_size: 100 });
      setState({ kind: "ready", review, findings });
    } catch (error) {
      setState({ kind: "error", error });
    }
  }, [contractId, version.id]);

  useEffect(() => {
    void load();
  }, [load]);

  // `?finding=` — the Legal queue's deep link. One-shot per target: scroll to
  // the card and move focus to it (the same gesture the document pane gives
  // `?evidence=`). A target hidden by the attention view widens the view first.
  const pointedDone = useRef<string | null>(null);
  useEffect(() => {
    if (state.kind !== "ready") return;
    const pointed = new URLSearchParams(window.location.search).get("finding");
    if (!pointed || pointedDone.current === pointed) return;
    const card = document.querySelector<HTMLElement>(`article[data-finding-id="${pointed}"]`);
    if (!card) {
      if (view === "attention") setView("all");
      return;
    }
    pointedDone.current = pointed;
    card.scrollIntoView({ block: "center" });
    card.focus({ preventScroll: true });
  }, [state, view]);

  if (!can(P.FINDING_VIEW)) {
    return (
      <div className="ws-pane__head">
        <h2 className="ws-pane__title">Findings</h2>
        <div className="ws-state" role="note">
          <p>Your account does not include findings access.</p>
        </div>
      </div>
    );
  }

  if (state.kind === "loading") {
    return (
      <>
        <div className="ws-pane__head">
          <h2 className="ws-pane__title">Findings</h2>
        </div>
        <div className="ws-state" aria-busy="true">
          <p className="ws-visually-hidden" role="status" aria-live="polite">
            Loading findings…
          </p>
          <span className="ws-skel ws-skel--line" style={{ width: "70%" }} aria-hidden="true" />
          <span className="ws-skel ws-skel--line" style={{ width: "55%" }} aria-hidden="true" />
        </div>
      </>
    );
  }

  if (state.kind === "no-review") {
    return (
      <>
        <div className="ws-pane__head">
          <h2 className="ws-pane__title">Findings</h2>
        </div>
        <div className="ws-state">
          <h3>This document version hasn&rsquo;t been analysed yet.</h3>
          <p>
            Findings appear once a Review runs this document against a published
            configuration snapshot. Starting a Review isn&rsquo;t built into this
            screen yet.
          </p>
        </div>
      </>
    );
  }

  if (state.kind === "error") {
    return (
      <>
        <div className="ws-pane__head">
          <h2 className="ws-pane__title">Findings</h2>
        </div>
        <div className="ws-state ws-state--error" role="alert">
          <p>{describeError(state.error)}</p>
        </div>
      </>
    );
  }

  const { findings } = state;
  const attention = findings.filter((f) => f.requires_decision);
  const effectiveView = attention.length > 0 ? view : "all";
  const shown = effectiveView === "attention" ? attention : findings;

  return (
    <>
      <div className="ws-pane__head">
        <h2 className="ws-pane__title">Findings</h2>
        <span className="ws-pane__note ws-mono">{findings.length} total</span>
      </div>
      <div className="ws-pane__body" style={{ padding: "16px" }}>
        {findings.length === 0 ? (
          <p>This Review has no Findings yet.</p>
        ) : (
          <>
            {attention.length > 0 ? (
              <div className="ws-filter">
                <button type="button" aria-pressed={effectiveView === "attention"} onClick={() => setView("attention")}>
                  Needs decision ({attention.length})
                </button>
                <button type="button" aria-pressed={effectiveView === "all"} onClick={() => setView("all")}>
                  All findings ({findings.length})
                </button>
              </div>
            ) : null}
            {shown.length === 0 ? (
              <p>No Findings on this page need a decision.</p>
            ) : (
              shown.map((finding) => (
                <FindingCard key={finding.id} finding={finding} onChanged={() => void load()} />
              ))
            )}
          </>
        )}
      </div>
    </>
  );
}

function FindingCard({ finding, onChanged }: { finding: Finding; onChanged: () => void }) {
  const calm = CALM_CLASSIFICATIONS.has(finding.classification);
  return (
    <article className={`ws-finding${finding.requires_decision ? " ws-finding--attention" : ""}`} data-finding-id={finding.id} tabIndex={-1}>
      <header className="ws-finding__head">
        <h3 className="ws-finding__title">
          {finding.requirement.code ?? "Requirement"}
          {finding.requirement.name ? ` — ${finding.requirement.name}` : ""}
        </h3>
        <span className={`ws-chip${calm ? "" : " ws-chip--fill ws-chip--classify-fill"}`} title="Derived summary of the Evaluations below">
          {finding.classification}
        </span>
        <span className="ws-chip">{finding.status}</span>
        {finding.escalated ? <span className="ws-chip--flag">Escalated</span> : null}
      </header>
      <p className="ws-finding__note">
        Classification is a derived summary — the Evaluations below are the authoritative results.
      </p>
      {finding.evaluations.map((evaluation) => (
        <EvaluationCard key={evaluation.id} evaluation={evaluation} onChanged={onChanged} />
      ))}
      <EscalateControl finding={finding} onChanged={onChanged} />
    </article>
  );
}

function EvaluationCard({ evaluation, onChanged }: { evaluation: Evaluation; onChanged: () => void }) {
  const { point, target } = useHighlight();
  const attention =
    ("rule_outcome" in evaluation && evaluation.rule_outcome !== undefined
      ? ATTENTION_OUTCOMES.has(evaluation.rule_outcome)
      : false) || evaluation.requires_decision;
  const showDecision = evaluation.requires_decision || evaluation.current_decision !== null;

  return (
    <div className="ws-evaluation" data-scope={evaluation.scope_key}>
      <div className="ws-evaluation__head">
        <span className="ws-evaluation__scope">
          {evaluation.scope_key}
          {evaluation.scope_label ? ` · ${evaluation.scope_label}` : ""}
        </span>
        {/* Presence-tested, not permission-tested (52.4) — an omitted field renders nothing. */}
        {evaluation.rule_outcome !== undefined ? (
          <span className={`ws-chip${CALM_OUTCOMES.has(evaluation.rule_outcome) ? "" : " ws-chip--fill ws-chip--outcome-fill"}`}>
            {evaluation.rule_outcome}
          </span>
        ) : null}
        {evaluation.current_decision ? (
          <span className="ws-chip--fill ws-chip--decision-fill">{evaluation.current_decision.decision_type}</span>
        ) : attention ? (
          <span className="ws-chip--flag">Decision required</span>
        ) : null}
      </div>

      <dl className="ws-facts">
        <dt>Found in contract</dt>
        <dd>{renderValue(evaluation.actual_value)}</dd>
        {evaluation.expected_value !== undefined ? (
          <>
            <dt>Company Standard</dt>
            <dd>{renderValue(evaluation.expected_value)}</dd>
          </>
        ) : null}
      </dl>

      {evaluation.evidence_refs.length > 0 ? (
        <div className="ws-evidence-refs">
          {evaluation.evidence_refs.map((evidenceId, index) => (
            <button
              key={evidenceId}
              type="button"
              aria-current={target === evidenceId ? "true" : undefined}
              onClick={() => point(evidenceId, "the cited")}
            >
              Evidence {index + 1}
            </button>
          ))}
        </div>
      ) : (
        <p className="ws-pane__note">No supporting text was found in the document for this Requirement.</p>
      )}

      {showDecision ? <DecisionControl evaluation={evaluation} onRecorded={onChanged} /> : null}
    </div>
  );
}

function scalar(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

/** Values verbatim — presentation only, no interpretation (rule 12: the server's
 *  keys and values, exactly; just never a clipped one-line JSON blob). */
function renderValue(value: unknown): React.ReactNode {
  if (value === null || value === undefined) return "Not recorded";
  if (typeof value === "object" && !Array.isArray(value)) {
    return (
      <span className="ws-facts__pairs">
        {Object.entries(value as Record<string, unknown>).map(([key, entry]) => (
          <span key={key} className="ws-facts__pair">
            <span className="ws-facts__k">{key}</span>{" "}
            <span className="ws-mono">{scalar(entry)}</span>
          </span>
        ))}
      </span>
    );
  }
  return scalar(value);
}
