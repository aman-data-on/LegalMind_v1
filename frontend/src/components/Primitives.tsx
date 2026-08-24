/**
 * Shared presentation primitives — Phase 3 consolidation (DD-5).
 *
 * These exist because, with all nine screens on the design system, the same
 * three JSX shapes were hand-repeated across pages. They are presentation
 * only: no data fetching, no permission logic, no state derivation.
 *
 * `StatePill` keeps the five-axis separation ratified in DESIGN_SYSTEM.md —
 * each axis maps to its own CSS namespace and they are never merged into one
 * generic badge (RESOLVED ≠ MATCH depends on the two rendering as visibly
 * separate kinds of thing). The rendered markup is byte-identical to what the
 * pages previously wrote by hand, so test selectors are unaffected.
 */

/** CSS namespace per state axis. Adding an axis here requires a DESIGN_SYSTEM.md entry. */
const AXIS_CLASS = {
  classification: "badge",
  status: "status",
  outcome: "outcome",
  tag: "tag",
} as const;

export function StatePill({
  axis,
  value,
  title,
}: {
  axis: keyof typeof AXIS_CLASS;
  value: string;
  title?: string;
}) {
  const base = AXIS_CLASS[axis];
  return (
    <span className={`${base} ${base}--${value.toLowerCase()}`} title={title}>
      {value}
    </span>
  );
}

/** Labeled form field — one source for the label/control association pattern. */
export function Field({
  id,
  label,
  grow,
  children,
}: {
  id: string;
  label: React.ReactNode;
  grow?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={grow ? "field field--grow" : "field"}>
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      {children}
    </div>
  );
}

/** Bordered table surface that scrolls horizontally instead of clipping. */
export function TableCard({ children }: { children: React.ReactNode }) {
  return <div className="table-card table-wrap">{children}</div>;
}
