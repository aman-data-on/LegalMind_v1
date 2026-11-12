"use client";

/**
 * The filter row (UX Batch 3): on a wide screen every control shows in one wrapping row; on a
 * phone (≤ 640px) the `lead` (search) stays and the rest fold behind one "Filters" button, so
 * the list starts on the first screen (review §B3-P2). Presentation only.
 */

import { useState, type ReactNode } from "react";

export function FilterPanel({ lead, active = 0, children }: {
  /** stays visible at every width (the search field) */
  lead?: ReactNode;
  /** how many filters are set, said on the button */
  active?: number;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="ws-filter-bar lm-filters" data-open={open || undefined}>
      {lead}
      <button type="button" className="ws-btn lm-filters__toggle" aria-expanded={open}
              onClick={() => setOpen((o) => !o)}>
        {active ? `Filters (${active})` : "Filters"}
      </button>
      <div className="lm-filters__body">{children}</div>
    </div>
  );
}
