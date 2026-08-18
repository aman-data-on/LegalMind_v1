/**
 * When to keep watching a queued analysis — locked 52.7, 55.1, Step 30.
 *
 * Locked 55.1 makes analysis a worker job, so a submission returns `202 accepted`
 * before any Finding exists. Locked 52.7 then fixes how the UI may report progress:
 * "the Review lifecycle state (Step 30) is the single source of progress." So this
 * module holds no progress state of its own — it decides only *whether to look
 * again*, and the answer comes from the lifecycle value the server returned.
 *
 * Deliberately a pure function rather than logic inside the component: the rule is
 * what matters and it is testable on its own. Nothing here derives a legal value, and
 * nothing here invents a lifecycle state — locked Step 30 has no `QUEUED` state, and
 * a client-side one would be exactly the second source of progress 52.7 forbids.
 */

/** Step 30 states in which analysis has not yet produced a result. */
export const PRE_ANALYSIS_STATUSES = ["DRAFT", "UPLOADED", "PROCESSING"] as const;

export const QUEUE_POLL_MS = 2000;

/**
 * How many times to look again before saying so plainly. Sixty seconds is long
 * enough for a queued job to start and short enough that a stopped worker is
 * reported rather than displayed as an indefinite spinner — an honest "not picked up
 * yet" beats a hopeful animation.
 */
export const QUEUE_POLL_ATTEMPTS = 30;

export function isPreAnalysis(status: string | null): boolean {
  return status === null || (PRE_ANALYSIS_STATUSES as readonly string[]).includes(status);
}

/**
 * Whether the Review may be submitted for analysis at all.
 *
 * A terminal or in-review Review is not re-analysable (Step 30, 43.28), and offering
 * the control would promise something the server would refuse.
 */
export function isAnalysable(status: string | null): boolean {
  return isPreAnalysis(status);
}

/**
 * Keep polling only while all three hold: the job was queued, the lifecycle has not
 * moved, and we have not been waiting unreasonably long.
 */
export function shouldPollForAnalysis(args: {
  mode: string | undefined;
  reviewStatus: string | null;
  attempts: number;
}): boolean {
  return (
    args.mode === "queued" &&
    isPreAnalysis(args.reviewStatus) &&
    args.attempts < QUEUE_POLL_ATTEMPTS
  );
}
