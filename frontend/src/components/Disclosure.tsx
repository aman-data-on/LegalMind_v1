import type { ReactNode } from "react";

import { IconChevronRight } from "@/components/workspace/icons";

/** One disclosure (U2 r4, critic 15): a native `<details>` with a Lucide chevron in place of
 *  the browser's ▶ marker, turned when open (`globals.css` `.lm-disc`). Keyboard and screen
 *  readers get the native element's own behaviour. */
export function Disclosure({ summary, className, children }: {
  summary: ReactNode; className?: string | undefined; children: ReactNode;
}) {
  return (
    <details className={className ? `lm-disc ${className}` : "lm-disc"}>
      <summary><span className="lm-disc__chev"><IconChevronRight size={14} /></span>{summary}</summary>
      {children}
    </details>
  );
}
