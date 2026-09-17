/**
 * The comparison must fit its column whatever the basis token is, asserted
 * against the REAL stylesheet.
 *
 * Reported twice. The first fix scoped the three-column rule to the
 * document-CLOSED state so the ~324px rail stacks instead of laying out three
 * 150px tracks — and that was right, but incomplete, and the second report
 * measured exactly why: the stacked rule said `grid-template-columns: 1fr`.
 *
 * `1fr` is `minmax(auto, 1fr)`, and that `auto` minimum is the item's MIN-CONTENT
 * width. `CONFIDENTIALITY_SURVIVAL_POST_TERMINATION_OR_RELATIONSHIP_END` — the
 * longest basis in the ratified config at 61 characters, with no space or hyphen
 * to break at — has a min-content width of 439px. So the single column measured
 * 439px inside a 324px container, and "Next step", the one column that tells the
 * reviewer what to do, went back behind a hidden horizontal scrollbar. Measured
 * before the fix: `grid-template-columns: 439.281px`, `scrollWidth` 455 vs
 * `clientWidth` 324.
 *
 * Two changes are needed together and neither works alone:
 *
 *   minmax(0, 1fr)            releases the TRACK's intrinsic floor
 *   overflow-wrap: anywhere   releases the TOKEN's min-content width
 *
 * `overflow-wrap: break-word` — which is what this had — breaks a long word
 * visually but does NOT reduce min-content, so the track floor stayed. That
 * distinction is the whole defect, and it is why a shorter basis never triggered
 * it and the layout change looked like a fix.
 */

import { readFileSync } from "node:fs";

import postcss from "postcss";
import { describe, expect, it } from "vitest";

const WORKSPACE_CSS = "src/app/dashboard/workspace.css";

function rules(selectorIncludes: string, property: string): string[] {
  const root = postcss.parse(readFileSync(WORKSPACE_CSS, "utf8"), { from: WORKSPACE_CSS });
  const found: string[] = [];
  root.walkRules((rule) => {
    if (!rule.selector.includes(selectorIncludes)) return;
    rule.walkDecls(property, (decl) => {
      found.push(decl.value);
    });
  });
  return found;
}

describe("the comparison grid cannot be widened by its own content", () => {
  it("declares no track that can take an intrinsic minimum", () => {
    /* Every `grid-template-columns` on this grid is either `none` (the
       auto-flow: column form) or carries an explicit `minmax(0, …)` for its
       flexible track. A bare `1fr` hands the layout's floor to the longest
       unbroken token in the ratified config. */
    for (const value of rules(".ws-facts--compare", "grid-template-columns")) {
      if (value === "none") continue;
      // A `1fr` track is only safe written as `minmax(0, 1fr)`. `max-content` on
      // the LABEL track is fine — those are three short controlled strings — so
      // the rule is about bare flexible tracks, not about max-content.
      const bareFr = value.replace(/minmax\([^)]*\)/g, "").includes("fr");
      expect(bareFr, `grid-template-columns: ${value} has a bare fr track`).toBe(false);
      expect(value, `grid-template-columns: ${value}`).toMatch(/minmax\(\s*0\s*,/);
    }
  });

  it("gives the auto-placed columns a zero floor too", () => {
    for (const value of rules(".ws-facts--compare", "grid-auto-columns")) {
      // The doc-CLOSED rule keeps a 150px floor deliberately — it only applies
      // where the panel is the whole workspace and three columns genuinely fit.
      expect(value).toMatch(/minmax\(\s*(0|150px)\s*,/);
    }
  });

  it("lets the basis token break, with the one property that shrinks min-content", () => {
    const wraps = rules(".ws-side__detail", "overflow-wrap");
    expect(wraps.length).toBeGreaterThan(0);
    // `break-word` here is the bug, not a weaker version of the fix.
    expect(wraps).toContain("anywhere");
    expect(wraps).not.toContain("break-word");
  });

  it("releases the grid items' own automatic minimum size", () => {
    /* Tracks and items are two separate floors. `minmax(0, 1fr)` on the track
       is undone one level down if the item keeps its own `auto` minimum. */
    const mins = rules(".ws-facts--compare", "min-width");
    expect(mins).toContain("0");
  });
});
