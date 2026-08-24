"use client";

/**
 * Review detail — **the load-bearing surface** (locked 52.5).
 *
 * Locked Step 31 r16, as amended by AM-6, requires that before deciding, Legal is
 * shown the evidence, Requirement, Company Standard, applicable Legal Rule and
 * Finding — *including every scoped Evaluation with its own applicable Legal Rule*.
 * Everything below follows from that.
 *
 * The five properties this screen exists to guarantee:
 *
 * 1. **Every Finding shows its Evaluations.** `FindingCard` cannot render without
 *    them, so a Finding is never presented as a single verdict (52.5, 49.7 r1).
 * 2. **Decision controls attach to the Evaluation.** `renderEvaluationActions` is
 *    passed per Evaluation; there is no Finding-level decision control anywhere
 *    (AB-1, 52.5).
 * 3. **A Finding cannot be resolved from here.** There is no resolve control and no
 *    endpoint for one — resolution is derived server-side (D-3.6, Step 30 r3/r16).
 *    That is what makes the "hidden carve-out" failure structurally impossible: a
 *    conforming aggregate cap cannot be used to close a Finding whose exception
 *    still needs a decision, because nothing here closes Findings at all.
 * 4. **No optimistic UI.** After a decision the screen re-fetches from the server
 *    (52.7); it never patches its own copy.
 * 5. **Escalation is Finding-level and is not approval** (Steps 4, 22, F-3, AM-23).
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AccessRestricted, PermissionGate } from "@/components/AccessRestricted";
import { DecisionPanel } from "@/components/DecisionPanel";
import { EmptyState, ErrorBanner, Loading, Pager } from "@/components/Feedback";
import { FindingCard } from "@/components/FindingCard";
import {
  QUEUE_POLL_MS,
  isAnalysable,
  shouldPollForAnalysis,
} from "@/lib/analysis";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type {
  AnalysisSubmission,
  Evaluation,
  Finding,
  Pagination,
  Review,
} from "@/lib/types";

export default function ReviewPage({
  params,
}: {
  params: Promise<{ reviewId: string }>;
}) {
  const { can } = useSession();
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [classification, setClassification] = useState("");
  const [error, setError] = useState<unknown>(null);
  /*
   * DD-1 (direction C): the primary entry point for a decision-maker is the set
   * of Findings that still need one. This is a DISPLAY filter over what the API
   * returned for this page, keyed on the server-provided `requires_decision`
   * field — nothing is derived client-side (52.7), and the full list is one
   * click away, never hidden (DD-1's non-negotiable).
   */
  const [view, setView] = useState<"attention" | "all">("attention");

  useEffect(() => {
    void params.then((resolved) => setReviewId(resolved.reviewId));
  }, [params]);

  const load = useCallback(async () => {
    if (!reviewId) return;
    setError(null);
    try {
      setReview(await api.review(reviewId));
      const result = await api.findings(reviewId, {
        page,
        ...(classification ? { classification } : {}),
      });
      setFindings(result.items);
      setPagination(result.pagination);
    } catch (cause) {
      setError(cause);
    }
  }, [reviewId, page, classification]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.REVIEW_VIEW)) return <AccessRestricted what="reviews" />;
  if (!reviewId) return <Loading what="review" />;

  const attention = (findings ?? []).filter((finding) => finding.requires_decision);
  /* The queue view falls back to the full list when nothing needs a decision —
     an empty default view would misread as "no Findings" (rule: absence is
     information, and this absence belongs to the queue, not the Review). */
  const effectiveView = view === "attention" && attention.length > 0 ? "attention" : "all";
  const shown = effectiveView === "attention" ? attention : (findings ?? []);

  return (
    <>
      <Link className="page-back" href="/reviews">
        ← Reviews
      </Link>
      <h1>Review {reviewId.slice(0, 8)}</h1>
      {review ? (
        <p className="page-meta">
          {/*
            Step 30 — the Review lifecycle is the single source of progress (52.7).
            There is no separate progress indicator that could disagree with it, and
            no control that sets it (r3).
          */}
          <span className={`status status--${review.status.toLowerCase()}`}>
            {review.status}
          </span>
          <span>snapshot {review.configuration_snapshot_id.slice(0, 8)}</span>
          <Link href={`/reviews/${reviewId}/report`}>View report</Link>
        </p>
      ) : null}

      <ErrorBanner error={error} />

      <form className="card form-row" onSubmit={(event) => event.preventDefault()}>
        {findings !== null && findings.length > 0 ? (
          <div className="field">
            <span className="field__label">View</span>
            <span className="seg">
              <button
                type="button"
                aria-pressed={effectiveView === "attention"}
                disabled={attention.length === 0}
                onClick={() => setView("attention")}
              >
                Needs decision ({attention.length})
              </button>
              <button
                type="button"
                aria-pressed={effectiveView === "all"}
                onClick={() => setView("all")}
              >
                All findings ({findings.length})
              </button>
            </span>
          </div>
        ) : null}
        <div className="field">
          <label className="field__label" htmlFor="classification-filter">
            Filter by classification
          </label>
          <select
            id="classification-filter"
            value={classification}
            onChange={(event) => {
              setPage(1);
              setClassification(event.target.value);
            }}
          >
            <option value="">All</option>
            {/* Locked Step 36 / REC-01 — the canonical seven. Nothing added. */}
            {[
              "MATCH",
              "DEVIATION",
              "MISSING",
              "CONFLICT",
              "AMBIGUOUS",
              "UNRESOLVED",
              "UNABLE_TO_EVALUATE",
            ].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </form>

      {!can(P.FINDING_VIEW) ? (
        <AccessRestricted what="findings" />
      ) : findings === null ? (
        /* A failed load already shows its ErrorBanner above; rendering a
           perpetual "Loading…" beside it would misstate the page's state. */
        error ? null : <Loading what="findings" />
      ) : findings.length === 0 ? (
        <>
          <EmptyState>
            This Review has no Findings yet. Findings appear once the document has been
            analysed against the configuration snapshot the Review is pinned to.
          </EmptyState>
          <AnalyseControl
            reviewId={reviewId}
            reviewStatus={review?.status ?? null}
            onAnalysed={() => void load()}
          />
        </>
      ) : (
        <>
          {shown.map((finding) => (
            <FindingCard
              key={finding.id}
              finding={finding}
              renderEvaluationActions={(evaluation: Evaluation) =>
                /*
                 * Rendered per Evaluation — never per Finding (AB-1, 52.5). Shown
                 * when the Evaluation needs a decision or already has one, so the
                 * record stays visible after the fact.
                 */
                evaluation.requires_decision || evaluation.current_decision ? (
                  <DecisionPanel evaluation={evaluation} onRecorded={() => void load()} />
                ) : null
              }
            >
              <EscalationControls finding={finding} onChanged={() => void load()} />
            </FindingCard>
          ))}
          {effectiveView === "attention" && attention.length < findings.length ? (
            <p className="hint">
              Showing the {attention.length} Finding{attention.length === 1 ? "" : "s"}{" "}
              that need a decision on this page. &ldquo;All findings&rdquo; shows the
              rest.
            </p>
          ) : null}
          {pagination ? (
            <Pager
              page={pagination.page}
              pageSize={pagination.page_size}
              total={pagination.total}
              onPage={setPage}
            />
          ) : null}
        </>
      )}
    </>
  );
}

/**
 * Run the analysis — locked 44.2/44.40, 49.8, 55.1, Step 30, 52.3, 52.7.
 *
 * Locked 52.7: "the Review lifecycle state (Step 30) is the single source of
 * progress." So this component keeps no progress state of its own beyond "a request
 * is in flight": what happened is read back from the Review, and there is no spinner
 * or percentage that could disagree with the lifecycle.
 *
 * Locked 55.1 makes analysis a worker job, so a submission may return `202 accepted`
 * before any Finding exists. The component then **re-reads the Review** on a bounded
 * interval — it does not invent a `QUEUED` state, because Step 30 has none and a
 * client-side one would be the second source of progress 52.7 forbids. If the
 * lifecycle has not moved after `QUEUE_POLL_ATTEMPTS` looks, it says so plainly
 * rather than animating indefinitely.
 *
 * Nothing here is interpreted. Counts, mapping states and the skipped-as-optional
 * figure are rendered as the server reported them (38.23), and a per-Requirement
 * `failure` is labelled as a configuration problem — never as a legal conclusion.
 */
function AnalyseControl({
  reviewId,
  reviewStatus,
  onAnalysed,
}: {
  reviewId: string;
  reviewStatus: string | null;
  onAnalysed: () => void;
}) {
  const { can } = useSession();
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AnalysisSubmission | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [error, setError] = useState<unknown>(null);

  const waiting = shouldPollForAnalysis({
    mode: result?.mode,
    reviewStatus,
    attempts,
  });

  // Every hook runs before the early returns below — a conditional return placed
  // above a hook would change the hook order between renders.
  useEffect(() => {
    if (!waiting) return;
    const timer = setTimeout(() => {
      setAttempts((n) => n + 1);
      onAnalysed();
    }, QUEUE_POLL_MS);
    return () => clearTimeout(timer);
  }, [waiting, attempts, onAnalysed]);

  // 52.3 — a control the user cannot invoke is not rendered. Hiding it is a
  // usability affordance; the server refuses the call regardless.
  if (!can(P.REVIEW_CREATE)) return null;

  // Step 30 — analysis belongs to the pre-review part of the lifecycle. A terminal
  // Review is not re-analysable, and offering the control would be misleading.
  if (!isAnalysable(reviewStatus)) {
    return (
      <p className="hint">
        This Review is {reviewStatus} and is not awaiting analysis.
      </p>
    );
  }

  async function analyse() {
    setBusy(true);
    setError(null);
    setAttempts(0);
    try {
      setResult(await api.analyzeReview(reviewId));
      onAnalysed();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card">
      <h2>Analyse this Review</h2>
      <p className="hint">
        The document is compared against the Requirements in the Review&rsquo;s
        configuration snapshot. The result is deterministic: the same document and the
        same snapshot always produce the same Findings.
      </p>
      <ErrorBanner error={error} />
      <button
        type="button"
        className="btn btn--primary"
        onClick={() => void analyse()}
        disabled={busy || waiting}
      >
        {busy || waiting ? "Analysing…" : "Run analysis"}
      </button>

      {result ? (
        <div className="analysis-result">
          {result.already_analysed ? (
            <p className="hint">
              This Review had already been analysed. Nothing was re-run, so no Finding
              was duplicated.
            </p>
          ) : result.mode === "queued" ? (
            /*
             * 55.1 — queued, so nothing has been evaluated yet. No count is shown:
             * "0 Findings" would be a statement about the contract, and the only true
             * statement available here is about the Review's lifecycle state.
             */
            waiting ? (
              <p className="hint">
                Submitted for analysis. Status is <strong>{reviewStatus}</strong> —
                this page re-reads the Review until the lifecycle moves.
              </p>
            ) : (
              <p className="warning">
                Submitted for analysis, but the Review is still {reviewStatus} and has
                not been picked up. The work is not lost — it stays queued — but a
                worker may not be running.
              </p>
            )
          ) : (
            <>
              <p>
                {result.findings_created ?? 0} Finding
                {result.findings_created === 1 ? "" : "s"} from{" "}
                {result.requirements_in_snapshot ?? 0} Requirement
                {result.requirements_in_snapshot === 1 ? "" : "s"}. Review status is
                now <strong>{result.review_status}</strong>.
              </p>
              {result.skipped_as_optional ? (
                <p className="hint">
                  {result.skipped_as_optional} optional Requirement
                  {result.skipped_as_optional === 1 ? "" : "s"} had no matching
                  provision, so no Finding was produced for
                  {result.skipped_as_optional === 1 ? " it" : " them"} — nothing was
                  required and nothing was found.
                </p>
              ) : null}
              {(result.requirements ?? [])
                .filter((item) => item.failure)
                .map((item) => (
                  <p key={item.requirement_code} className="warning">
                    <strong>{item.requirement_code}</strong> could not be analysed:{" "}
                    {item.failure}. This is a configuration problem, not a finding
                    about the contract.
                  </p>
                ))}
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}

/**
 * Escalation — locked Steps 4 and 22, `ROLE-04`, F-3, AM-23.
 *
 * Locked Step 4: an escalation means "This requires authorized review." It does
 * **not** mean "I approve this deviation." The wording here is deliberate for that
 * reason, and the control is gated on `review.view` rather than `legal.decision`
 * (49.3), because an ordinary User escalating is the whole point of `ROLE-03`.
 */
function EscalationControls({
  finding,
  onChanged,
}: {
  finding: Finding;
  onChanged: () => void;
}) {
  const { can } = useSession();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  if (!can(P.REVIEW_VIEW)) return null;

  async function escalate(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.escalate(finding.id, reason);
      setReason("");
      onChanged();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  async function withdraw() {
    setBusy(true);
    setError(null);
    try {
      await api.withdrawEscalation(finding.id);
      onChanged();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="escalation">
      <ErrorBanner error={error} />
      {finding.escalated ? (
        <>
          <p className="hint">
            Escalated for authorized review. This is a request for review, not an
            approval, and it records no decision.
          </p>
          <button
            type="button"
            className="btn btn--secondary btn--sm"
            onClick={() => void withdraw()}
            disabled={busy}
          >
            Withdraw escalation
          </button>
        </>
      ) : (
        <form className="form-row" onSubmit={escalate}>
          <div className="field field--grow">
            <label className="field__label" htmlFor={`escalate-${finding.id}`}>
              Escalate for authorized review — reason
            </label>
            <input
              id={`escalate-${finding.id}`}
              required
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="Why does this need authorized review?"
            />
          </div>
          <button type="submit" className="btn btn--secondary" disabled={busy}>
            Escalate
          </button>
        </form>
      )}
    </div>
  );
}
