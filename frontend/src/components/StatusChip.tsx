/**
 * The ONE point-status chip (UX Batch 2). A status is word + icon + colour, the same on
 * every screen: Matches green, Change needed orange, Missing orange (its own icon, never
 * red), Needs a decision indigo, In our favour teal. "Decided" is a second line under the
 * chip, never a replacement for it (RESOLVED ≠ MATCH, rule 14).
 *
 * Presentation only: the status comes from the server (`user_status`, `in_our_favour`),
 * never from this file (rule 18). Not interactive (a status is not a filter). This is not
 * `StatePill` — the five state axes keep their own namespaces there.
 */

import { STATUS_CHIP_WORDS } from "@/lib/labels";
import type { UserStatus } from "@/components/workspace/findingLanguage";
import {
  IconBetter, IconCheck, IconCheckCircle, IconFilePlus, IconPencilLine, IconScale,
} from "@/components/workspace/icons";

export type ChipStatus = "MATCHES" | "CHANGE_NEEDED" | "MISSING" | "NEEDS_DECISION" | "IN_OUR_FAVOUR";

const LOOK: Record<ChipStatus, { tone: string; Icon: typeof IconCheck }> = {
  MATCHES: { tone: "match", Icon: IconCheckCircle },
  CHANGE_NEEDED: { tone: "change", Icon: IconPencilLine },
  MISSING: { tone: "missing", Icon: IconFilePlus },
  NEEDS_DECISION: { tone: "decision", Icon: IconScale },
  IN_OUR_FAVOUR: { tone: "favour", Icon: IconBetter },
};

const FROM_USER_STATUS: Record<UserStatus, ChipStatus> = {
  ACCEPTABLE: "MATCHES",
  REQUIRES_MODIFICATION: "CHANGE_NEEDED",
  MISSING: "MISSING",
  NEEDS_DECISION: "NEEDS_DECISION",
};

/** The server's reader word, as the chip's key. `inOurFavour` is the server's own flag;
 *  it never comes from comparing values here. */
export function chipStatus(status: UserStatus, inOurFavour = false): ChipStatus {
  return inOurFavour ? "IN_OUR_FAVOUR" : FROM_USER_STATUS[status];
}

export function StatusChip({ status, decided, title }: {
  status: ChipStatus;
  /** an extra word for a lawyer (the engine's own term); never the only carrier */
  title?: string | undefined;
  /** the decision in words ("We accepted their wording"); `true` says only "Decided" */
  decided?: string | true | null;
}) {
  const { tone, Icon } = LOOK[status];
  const chip = (
    <span className={`lm-chip lm-chip--${tone}`} data-status={status} title={title}>
      <Icon size={14} />
      {STATUS_CHIP_WORDS[status]}
    </span>
  );
  if (!decided) return chip;
  return (
    <span className="lm-chipstack">
      {chip}
      <span className="lm-chip__decided">
        <IconCheck size={14} />
        {decided === true ? STATUS_CHIP_WORDS.decided : `${STATUS_CHIP_WORDS.decided}: ${decided}`}
      </span>
    </span>
  );
}
