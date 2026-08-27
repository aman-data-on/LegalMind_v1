/**
 * Loading skeletons — Phase 4 hardening (2026-08-27).
 *
 * Three rules govern this component, the first two from DESIGN.md:
 *
 * 1. **A skeleton must match the final layout's shape** so content arriving does
 *    not shift the page (the ui-ux-pro-max "Content Jumping" guideline: reserve
 *    space, keep async states in a stable container). Every composed shape below
 *    mirrors the real component it stands in for, including its container class.
 *
 * 2. **Shimmer must never contradict a valid empty state.** DESIGN.md's
 *    anti-pattern list warns that skeletons "can imply content that then
 *    contradicts a valid empty/absent state" — so shapes are few (3 rows, not a
 *    page of phantom data), and every use replaces an existing `Loading` state
 *    whose empty case is already handled separately by the caller.
 *
 * 3. **The announcement is text; the shimmer is decoration.** Assistive
 *    technology hears exactly what it heard before (`role="status"`,
 *    `aria-live="polite"` — the Phase 1 pattern); the visual shapes are
 *    `aria-hidden`. Under `prefers-reduced-motion` the shimmer stops and the
 *    blocks render static (see globals.css).
 */

export function Skeleton({
  width,
  height = "0.9rem",
  className = "",
}: {
  width?: string;
  height?: string;
  className?: string;
}) {
  return (
    <span
      className={`skeleton ${className}`.trim()}
      style={{ ...(width ? { width } : {}), height }}
      aria-hidden="true"
    />
  );
}

/** The announcement + shapes pairing every skeleton view uses. */
export function SkeletonStatus({ what }: { what: string }) {
  return (
    <p className="visually-hidden" role="status" aria-live="polite">
      Loading {what}…
    </p>
  );
}

/** Stands in for a `TableCard` list (reviews, contracts) while it loads. */
export function SkeletonTable({ what, columns }: { what: string; columns: number }) {
  return (
    <div className="table-card skeleton-table" data-skeleton={what}>
      <SkeletonStatus what={what} />
      <div aria-hidden="true">
        {[0, 1, 2].map((row) => (
          <div key={row} className="skeleton-table__row">
            {Array.from({ length: columns }, (_, column) => (
              <Skeleton key={column} width={column === 0 ? "8rem" : "6rem"} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Stands in for `FindingCard`s while findings load — same `.finding` container,
 * so the cards arriving replace equal-height blocks instead of pushing the page. */
export function SkeletonFindings() {
  return (
    <div data-skeleton="findings">
      <SkeletonStatus what="findings" />
      <div aria-hidden="true">
        {[0, 1].map((card) => (
          <article key={card} className="finding skeleton-finding">
            <Skeleton width="18rem" height="1.1rem" />
            <Skeleton width="10rem" />
            <Skeleton width="100%" height="3.2rem" />
          </article>
        ))}
      </div>
    </div>
  );
}

/** Stands in for an assist answer while retrieval and citation checks run.
 * One shape serves both outcomes (an answer and a refusal render on the same
 * surface), so the skeleton cannot promise content a refusal would contradict. */
export function SkeletonAnswer() {
  return (
    <div className="ask-answer skeleton-answer" data-skeleton="answer">
      <p className="hint" role="status" aria-live="polite">
        Searching the document and checking citations…
      </p>
      <div aria-hidden="true">
        <Skeleton width="90%" />
        <Skeleton width="70%" />
      </div>
    </div>
  );
}
