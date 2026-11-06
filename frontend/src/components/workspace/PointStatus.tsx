/**
 * Where a point stands — ONE set of four (cross-page pass, `AM-291` r5): the document's
 * marks and legend, the Points filters and the Changes rows all use these words, icons
 * and tones. Each has its own icon, so colour never carries the meaning alone (WCAG 1.4.1).
 *
 * Its own vocabulary, beside the three reader words on each card (never instead of them,
 * never `StatePill`/`AXIS_CLASS`): RESOLVED is "Decided", never "Matches" (rule 14).
 */

import type { StatusBucket } from "./model";
import { IconAlertCircle, IconCheck, IconCheckCircle, IconFileMinus } from "./icons";

export const POINT_STATUS_ORDER: readonly StatusBucket[] = ["match", "review", "decided", "missing"];

export const POINT_STATUS: Record<StatusBucket, string> = {
  match: "Matches our standard",
  review: "Open point",
  decided: "Decided",
  missing: "Missing",
};

/** The same four as one-word filter chips, so the Points filters fit one row; the full
 *  word stays the chip's accessible name. */
export const POINT_CHIP: Record<StatusBucket, string> = {
  match: "Matches",
  review: "Open",
  decided: "Decided",
  missing: "Missing",
};

export function PointStatusIcon({ bucket, size = 16, label = true }: {
  bucket: StatusBucket; size?: number;
  /** false where the word is printed beside it (the icon is then decorative) */
  label?: boolean;
}) {
  const Icon = bucket === "match" ? IconCheckCircle : bucket === "decided" ? IconCheck
    : bucket === "review" ? IconAlertCircle : IconFileMinus;
  return (
    <span className={`ws-status ws-status--${bucket}`}
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

/** The key, in the one order. */
export function PointStatusLegend() {
  return (
    <ul className="lm-legend" aria-label="What the marks mean">
      {POINT_STATUS_ORDER.map((bucket) => <li key={bucket}><PointStatusMark bucket={bucket} /></li>)}
    </ul>
  );
}
