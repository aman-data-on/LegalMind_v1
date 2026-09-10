/**
 * Key obligations — the count and the rendered rows reconcile (owner,
 * 2026-09-10: a group headed "6" showed five and a "+1" nothing could open).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HighlightProvider } from "@/components/workspace/highlight";
import { OBLIGATIONS_SHOWN, ObligationCategoryRow } from "@/components/workspace/ObligationsPanel";
import type { ObligationItem } from "@/lib/types";

const items = Array.from({ length: 6 }, (_, i) => ({
  id: `o${i}`, obligation_text: `Obligation ${i + 1}`, evidence_id: null, section_ref: null,
})) as unknown as ObligationItem[];

describe("ObligationCategoryRow", () => {
  it("shows five, says exactly how many more there are, and the header count is the whole list", () => {
    const html = renderToStaticMarkup(
      <HighlightProvider>
        <ObligationCategoryRow title="Distributor must" items={items} open onToggle={() => {}} />
      </HighlightProvider>,
    );
    expect(OBLIGATIONS_SHOWN).toBe(5);
    expect(html.match(/ws-obligations__item/g)).toHaveLength(5);
    expect(html).toContain('class="ws-obligations__count">6<');
    expect(html).toContain(">Show 1 more<");
    expect(html).toContain('aria-expanded="false"');
    expect(html).not.toContain("+1 more");
  });

  it("offers no control when everything already shows", () => {
    const html = renderToStaticMarkup(
      <HighlightProvider>
        <ObligationCategoryRow title="Both sides must" items={items.slice(0, 3)} open onToggle={() => {}} />
      </HighlightProvider>,
    );
    expect(html.match(/ws-obligations__item/g)).toHaveLength(3);
    expect(html).not.toContain("Show ");
  });
});
