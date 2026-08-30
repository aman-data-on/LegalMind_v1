/**
 * The disclosed-placeholder rules (docs/design/WORKSPACE_UI_PLAN.md):
 *   a gated domain renders as a calm, labelled, factual state — never an error,
 *   never a lock, never urgency, never a promise dressed as marketing;
 *   and the copy is fixed in one place so every screen says the identical thing.
 *
 * Static render assertions, the house idiom.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  DomainPlaceholder,
  PositionsSearchPlaceholder,
  StatuteSearchPlaceholder,
} from "@/components/DomainPlaceholder";

describe("DomainPlaceholder", () => {
  it("renders the settled empty treatment, not an error", () => {
    const html = renderToStaticMarkup(
      <DomainPlaceholder title="Statute search" reason="Not available." />,
    );
    expect(html).toContain('class="empty"');
    expect(html).not.toContain("error");
    expect(html).not.toContain("banner");
  });

  it("is announced as a note with an accessible name", () => {
    const html = renderToStaticMarkup(
      <DomainPlaceholder title="Statute search" reason="Not available." />,
    );
    expect(html).toContain('role="note"');
    expect(html).toContain('aria-label="Statute search — not available"');
  });

  it("omits the alternative line entirely when there is nowhere to point", () => {
    const html = renderToStaticMarkup(
      <DomainPlaceholder title="X" reason="Y." />,
    );
    expect(html).not.toContain("hint");
  });

  it("never renders urgency, lock, or marketing vocabulary", () => {
    for (const surface of [
      <PositionsSearchPlaceholder key="a" />,
      <StatuteSearchPlaceholder key="b" />,
    ]) {
      const html = renderToStaticMarkup(surface).toLowerCase();
      for (const forbidden of ["coming soon", "lock", "🔒", "upgrade", "soon!",
                               "stay tuned", "confidence"]) {
        expect(html).not.toContain(forbidden);
      }
    }
  });

  it("positions placeholder points at the browsable alternative that exists today", () => {
    const html = renderToStaticMarkup(<PositionsSearchPlaceholder />);
    expect(html).toContain("browsed under Configuration");
  });

  it("statute placeholder states the factual cause: material not supplied", () => {
    const html = renderToStaticMarkup(<StatuteSearchPlaceholder />);
    // renderToStaticMarkup escapes apostrophes, so assert around them
    expect(html).toContain("the statute texts haven");
    expect(html).toContain("been supplied");
  });
});
