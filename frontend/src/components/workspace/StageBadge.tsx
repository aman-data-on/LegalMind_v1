/**
 * Where a deal stands — `AM-260`/`AM-261` (CLM R7). One word for the negotiation, derived
 * by the server (`legalmind/domain/deal_stage.py`); this only renders it.
 *
 * Its OWN vocabulary and its own look: never `StatePill`/`AXIS_CLASS` (the five legal state
 * axes), never the review-stage line, never a verdict tone. Only "Client returned" and
 * "Ready to send" are marked, by weight and a rule: the two stages that mean "our turn".
 */

import { stageLine, stageWords, type StageViewer } from "@/lib/labels";
import type { DealCounts, NegotiationStage, NegotiationStageCode } from "@/lib/types";

import { relativeTime, shortDate } from "./model";

/** Display order: the deal's path, start to finish, then the pause. */
export const STAGE_ORDER: readonly NegotiationStageCode[] = [
  "DRAFTING", "INTERNAL_REVIEW", "WITH_CLIENT", "CLIENT_RETURNED",
  "READY_TO_SEND", "READY_TO_SIGN", "SIGNED", "ON_HOLD",
];

/** The words live in the one label map (`stageWords`); kept as a record for the list's
 *  stage filter, which reads as the deal owner does. */
export const STAGE_LABEL = Object.fromEntries(
  STAGE_ORDER.map((code) => [code, stageWords(code)])) as Record<NegotiationStageCode, string>;

export function StageBadge({ stage, counts, showDays = true, viewer = "owner" }: {
  stage: NegotiationStage | undefined | null;
  /** the server's `counts` (`AM-291`): the chip names the real next step from them */
  counts?: DealCounts | undefined;
  showDays?: boolean;
  /** Who is reading: the lawyer holding a review reads "Your review" (S1). */
  viewer?: StageViewer;
}) {
  if (!stage) return <span className="ws-dealstage ws-dealstage--none">—</span>;
  const label = stageLine(stage.stage, counts, viewer);
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
