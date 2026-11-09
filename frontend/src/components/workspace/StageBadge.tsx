/**
 * Where a deal stands — `AM-260`/`AM-261` (CLM R7). One word for the negotiation, derived
 * by the server (`legalmind/domain/deal_stage.py`); this only renders it.
 *
 * Its OWN vocabulary and its own look: never `StatePill`/`AXIS_CLASS` (the five legal state
 * axes), never the review-stage line, never a verdict tone. Only "Client returned" and
 * "Ready to send" are marked, by weight and a rule: the two stages that mean "our turn".
 */

import { changesWords, pointsWords, reviewStatusLabel, stageLine, stageWords, type StageViewer } from "@/lib/labels";
import type { Contract, DealCounts, NegotiationStage, NegotiationStageCode } from "@/lib/types";

import { documentStatusBucket, relativeTime, shortDate, UNFINISHED_REVIEW_STATUSES } from "./model";

/** Display order: the deal's path, start to finish, then the pause. */
export const STAGE_ORDER: readonly NegotiationStageCode[] = [
  "DRAFTING", "INTERNAL_REVIEW", "WITH_CLIENT", "CLIENT_RETURNED",
  "READY_TO_SEND", "READY_TO_SIGN", "FINAL", "SIGNED", "ON_HOLD",
];

/** The words live in the one label map (`stageWords`); kept as a record for the list's
 *  stage filter, which reads as the deal owner does. */
export const STAGE_LABEL = Object.fromEntries(
  STAGE_ORDER.map((code) => [code, stageWords(code)])) as Record<NegotiationStageCode, string>;

export function StageBadge({ stage, counts, showDays = true, viewer = "owner", final = false }: {
  stage: NegotiationStage | undefined | null;
  /** the server's `counts` (`AM-291`): the chip names the real next step from them */
  counts?: DealCounts | undefined;
  showDays?: boolean;
  /** Who is reading: the lawyer holding a review reads "Your review" (S1). */
  viewer?: StageViewer;
  /** `AM-318`: the latest version is the final contract (the stage chip names its wait) */
  final?: boolean;
}) {
  if (!stage) return <span className="ws-dealstage ws-dealstage--none">—</span>;
  if (stage.stage === "FINAL") {
    // the end of the deal: "Final · 9 Nov 2026", a date rather than an age
    return <span className="ws-dealstage ws-dealstage--final">{`Final · ${shortDate(stage.since)}`}</span>;
  }
  const label = stageLine(stage.stage, counts, viewer, final);
  const ourTurn = stage.stage === "CLIENT_RETURNED" || stage.stage === "READY_TO_SEND";
  return (
    <span
      className={`ws-dealstage${ourTurn ? " ws-dealstage--turn" : ""}`}
      title={`${label} since ${shortDate(stage.since)}`}
    >
      <span>{label}</span>
      {ourTurn ? <span className="ws-visually-hidden">, our turn</span> : null}
      {showDays ? (
        <span className="ws-dealstage__days">
          <span className="ws-visually-hidden">, since </span>{relativeTime(stage.since)}
        </span>
      ) : null}
    </span>
  );
}

/** The two nouns on a row (`AM-291`), from the server's `counts` only: the client's
 *  changes in the open round, and the points still open. Before an analysis has
 *  finished the review's own word stands in for the points. A signed deal shows only
 *  "Signed" — nothing is left to count. */
export function CountsCell({ contract, viewer }: { contract: Contract; viewer: StageViewer }) {
  // a signed deal has nothing left to count: its stage is the whole story
  if (contract.negotiation_stage?.stage === "SIGNED") {
    return <span className="ws-home__counts"><span>{stageWords("SIGNED")}</span></span>;
  }
  if (contract.negotiation_stage?.stage === "FINAL") {         // AM-318
    return <span className="ws-home__counts"><span>Final copy ready</span></span>;
  }
  const review = contract.latest_analysis?.review_status;
  const changes = changesWords(contract.counts, viewer);
  let points: React.ReactNode = pointsWords(contract.counts, viewer);
  if (review && UNFINISHED_REVIEW_STATUSES.has(review)) points = reviewStatusLabel(review);
  else if (documentStatusBucket(contract) === "analyzing") points = <span className="ws-home__quiet">Being read</span>;
  else if (points === null) points = <span className="ws-home__quiet">Not checked yet</span>;
  return (
    <span className="ws-home__counts">
      {changes ? <span>{changes}</span> : null}
      <span>{points}</span>
    </span>
  );
}
