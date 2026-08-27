/**
 * A deliberately-unavailable surface, rendered as the calm, labelled state it is.
 *
 * The workspace plan (docs/design/WORKSPACE_UI_PLAN.md) draws a line between two
 * kinds of not-here:
 *
 *  - a *disclosed placeholder* — a surface whose existence is public product
 *    direction (positions search, statute search) but whose enabling decision or
 *    material has not arrived. This component renders those.
 *  - an *absent capability* (SSO, export) — those render NOTHING, ever; 52.4's
 *    absence discipline forbids an affordance that discloses an unbuilt capability.
 *    Do not reach for this component there.
 *
 * Blocked is a legitimate state (CLAUDE.md), so the rendering is factual and quiet:
 * no lock icon, no "coming soon" marketing tone, no urgency, no spinner implying
 * something is on its way. It reuses the settled `.empty` treatment — a bounded,
 * bordered fact — because "not available, deliberately" is closer to a settled empty
 * state than to an error.
 */

export function DomainPlaceholder({
  title,
  reason,
  alternative,
}: {
  /** What this surface will be, named plainly — e.g. "Statute search". */
  title: string;
  /** Why it is not available, stated factually in the interface's voice. */
  reason: string;
  /** Where the reader can go today for the nearest capability, if anywhere. */
  alternative?: string;
}) {
  return (
    <section className="empty" role="note" aria-label={`${title} — not available`}>
      <h3>{title}</h3>
      <p>{reason}</p>
      {alternative ? <p className="hint">{alternative}</p> : null}
    </section>
  );
}

/**
 * The two gated retrieval domains, with their copy fixed in one place so every
 * screen renders the identical factual sentence and a wording change is one diff.
 * The generated-answer surface has NO placeholder — the live refusal state is
 * production behavior and the Ask panel already renders it (`AM-29` r4).
 */
export function PositionsSearchPlaceholder() {
  return (
    <DomainPlaceholder
      title="Approved positions search"
      reason="Search across approved positions isn't available yet."
      alternative="Approved positions can be browsed under Configuration."
    />
  );
}

export function StatuteSearchPlaceholder() {
  return (
    <DomainPlaceholder
      title="Statute search"
      reason="Statute search isn't available yet — the statute texts haven't been supplied."
    />
  );
}
