/**
 * A region that is planned but not yet built in this phase — said plainly, with
 * a pointer to where the job is done today. Never a control that looks
 * operational (owner rule §20: placeholder UX is not fake functionality).
 *
 * Distinct from `DomainPlaceholder`, which is for capabilities the BACKEND does
 * not offer yet; this is for UI the roadmap sequences later.
 */

import Link from "next/link";

export function NextSlice({
  title,
  todayHref,
  todayLabel,
}: {
  title: string;
  todayHref: string;
  todayLabel: string;
}) {
  return (
    <>
      <div className="ws-pane__head">
        <h2 className="ws-pane__title">{title}</h2>
      </div>
      <div className="ws-state ws-state--next" role="note" aria-label={`${title} — not in this build yet`}>
        <p>This pane arrives in the next build slice.</p>
        <p>
          Until then, <Link href={todayHref}>{todayLabel}</Link>.
        </p>
      </div>
    </>
  );
}
