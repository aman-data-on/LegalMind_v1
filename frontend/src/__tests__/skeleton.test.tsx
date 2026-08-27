/**
 * Loading skeletons — Phase 4 hardening.
 *
 * The properties worth pinning: the visual shapes are hidden from assistive
 * technology while a text status is announced (the Phase 1 aria-live pattern,
 * unchanged); the answer skeleton carries one honest status line, not a staged
 * theater; and nothing on the loading surface says "confidence" (rule 12).
 * Static render assertions — motion and reduced-motion belong to CSS.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  Skeleton,
  SkeletonAnswer,
  SkeletonFindings,
  SkeletonTable,
} from "@/components/Skeleton";

describe("Skeleton", () => {
  it("hides the shape from assistive technology", () => {
    const html = renderToStaticMarkup(<Skeleton width="4rem" />);
    expect(html).toContain('aria-hidden="true"');
    expect(html).toContain("skeleton");
  });

  it("a table skeleton announces loading as text and keeps the table container", () => {
    const html = renderToStaticMarkup(<SkeletonTable what="reviews" columns={4} />);
    expect(html).toContain("Loading reviews…");
    expect(html).toContain('role="status"');
    expect(html).toContain("visually-hidden");
    // Same container class as the loaded state, so arrival causes no layout shift.
    expect(html).toContain("table-card");
  });

  it("the findings skeleton uses the real finding container class", () => {
    const html = renderToStaticMarkup(<SkeletonFindings />);
    expect(html).toContain("Loading findings…");
    expect(html).toContain('class="finding skeleton-finding"');
  });

  it("the answer skeleton states what is happening, once, honestly", () => {
    const html = renderToStaticMarkup(<SkeletonAnswer />);
    expect(html).toContain("Searching the document and checking citations…");
    // One shape serves answer and refusal alike; no invented progress stages.
    // (Text content only — the skeleton's width style legitimately uses "%".)
    expect(html).not.toMatch(/>\s*\d+\s*%/);
    expect(html.toLowerCase()).not.toContain("confidence");
  });
});
