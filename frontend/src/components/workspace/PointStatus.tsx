/**
 * Where a point stands, as a MARK (round 2 of UX Batch 2): the document's Contents marks,
 * its legend, the Points filters and the Changes rows. ONE vocabulary with StatusChip — the
 * same words, icons and hues (`LOOK`, `STATUS_CHIP_WORDS`) — so "Needs a decision" is the
 * indigo scale everywhere, never an orange "Open point". "Decided" is the one workflow
 * mark beside them (ink check), and never "Matches": RESOLVED ≠ MATCH (rule 14).
 * The bucket comes from the server's reader word (`model.readerBucket`), never derived here.
 */

import type { StatusBucket } from "./model";
import { LOOK, type ChipStatus } from "@/components/StatusChip";
import { STATUS_CHIP_WORDS } from "@/lib/labels";
import { IconCheck } from "./icons";

export const POINT_STATUS_ORDER: readonly StatusBucket[] = ["match", "favour", "change", "missing", "decision", "decided"];

const CHIP_OF: Record<Exclude<StatusBucket, "decided">, ChipStatus> = {
  match: "MATCHES", favour: "IN_OUR_FAVOUR", change: "CHANGE_NEEDED", missing: "MISSING", decision: "NEEDS_DECISION",
};

/** The mark's word — StatusChip's word, or "Decided". */
export const POINT_STATUS: Record<StatusBucket, string> = {
  match: STATUS_CHIP_WORDS.MATCHES,
  favour: STATUS_CHIP_WORDS.IN_OUR_FAVOUR,
  change: STATUS_CHIP_WORDS.CHANGE_NEEDED,
  missing: STATUS_CHIP_WORDS.MISSING,
  decision: STATUS_CHIP_WORDS.NEEDS_DECISION,
  decided: STATUS_CHIP_WORDS.decided,
};

/** The filter word: the same word (one vocabulary; the filter control never clips). */
export const POINT_CHIP: Record<StatusBucket, string> = POINT_STATUS;

export function PointStatusIcon({ bucket, size = 16, label = true }: {
  bucket: StatusBucket; size?: number;
  /** false where the word is printed beside it (the icon is then decorative) */
  label?: boolean;
}) {
  const look = bucket === "decided" ? { tone: "decided", Icon: IconCheck } : LOOK[CHIP_OF[bucket]];
  const Icon = look.Icon;
  return (
    <span className={`ws-status lm-mark--${look.tone}`}
          {...(label ? { title: POINT_STATUS[bucket], "aria-label": POINT_STATUS[bucket], role: "img" } : {})}>
      <Icon size={size} />
    </span>
  );
}

/** The icon and the word. */
export function PointStatusMark({ bucket, children }: { bucket: StatusBucket; children?: React.ReactNode }) {
  return (
    <span className="lm-mark">
      <PointStatusIcon bucket={bucket} label={false} /> {children ?? POINT_STATUS[bucket]}
    </span>
  );
}

/** The key, in the one order — folded behind one disclosure (round 3), so the Contents rail
 *  keeps its rows; the Points pane has its own "What the statuses mean". */
export function PointStatusLegend() {
  return (
    <details className="lm-legendbox">
      <summary>What the marks mean</summary>
      <ul className="lm-legend" aria-label="What the marks mean">
        {POINT_STATUS_ORDER.map((bucket) => <li key={bucket}><PointStatusMark bucket={bucket} /></li>)}
      </ul>
    </details>
  );
}
