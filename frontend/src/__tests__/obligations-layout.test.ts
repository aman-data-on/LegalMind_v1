/**
 * Key Obligations must be readable in the side rail, asserted against the REAL
 * stylesheet.
 *
 * Reported from the live site, 2026-09-17: every obligation wrapped to one word per
 * line, ten to fifteen lines a sentence, so reading eleven of them meant scrolling
 * past a column of single words.
 *
 * The cause is the trap this codebase has now hit twice. `.ws-obligations` asked for
 * `repeat(3, minmax(0, 1fr))` with a `@media (max-width: 900px)` escape beneath it —
 * but the Summary lives in the ~380px side rail beside an open document, and the rail
 * is not the viewport. On any laptop the media query never fires, so three equal tracks
 * divide 380px into ~118px each, and the ONE group most documents produce ("Receiving
 * Party must") is squeezed into a third of a rail it could have had all of.
 *
 * Asserted here rather than in a snapshot because this is exactly the kind of break
 * that is silent: the build stays green, the types stay clean, and the layout is wrong
 * only where someone happens to look. The same reasoning as `css-foundation.test.ts`,
 * on the workspace stylesheet.
 */

import { readFileSync } from "node:fs";

import postcss from "postcss";
import { describe, expect, it } from "vitest";

const WORKSPACE_CSS = "src/app/dashboard/workspace.css";

/** Every declaration of one property for one selector, in source order. */
function declarations(selector: string, property: string): string[] {
  const root = postcss.parse(readFileSync(WORKSPACE_CSS, "utf8"), { from: WORKSPACE_CSS });
  const found: string[] = [];
  root.walkRules((rule) => {
    if (rule.selector !== selector) return;
    rule.walkDecls(property, (decl) => {
      found.push(decl.value);
    });
  });
  return found;
}

/** The at-rule conditions under which a selector is (re)declared. */
function atRulesFor(selector: string): string[] {
  const root = postcss.parse(readFileSync(WORKSPACE_CSS, "utf8"), { from: WORKSPACE_CSS });
  const conditions: string[] = [];
  root.walkRules((rule) => {
    if (rule.selector !== selector) return;
    const parent = rule.parent;
    if (parent && parent.type === "atrule") {
      conditions.push(`@${(parent as postcss.AtRule).name} ${(parent as postcss.AtRule).params}`);
    }
  });
  return conditions;
}

describe("the Key Obligations grid sizes itself by its own width", () => {
  it("has no fixed three-track column rule, which is what squeezed the rail", () => {
    const columns = declarations(".ws-obligations", "grid-template-columns");
    expect(columns).toHaveLength(1);
    // `repeat(3, …)` reserves three tracks whatever the width. One group then gets a
    // third of a 380px rail — ~118px — and every sentence wraps a word at a time.
    expect(columns[0]).not.toMatch(/repeat\(\s*3\s*,/);
    expect(columns[0]).toMatch(/auto-fit/);
  });

  it("gives a column a floor wide enough to read a sentence in", () => {
    const [columns] = declarations(".ws-obligations", "grid-template-columns");
    const floor = columns?.match(/minmax\(\s*(\d+)px/)?.[1];
    expect(floor, "the minmax floor is stated in px").toBeDefined();
    // Comfortably past the ~118px that caused the report, and wide enough that the
    // ~380px rail resolves to one column rather than two cramped ones.
    expect(Number(floor)).toBeGreaterThanOrEqual(260);
  });

  it("is not re-declared inside a viewport media query", () => {
    /* The rail's width and the viewport's are different numbers, and this section is
       laid out inside the rail. A `max-width` media query here is answering a question
       nobody asked — it was the reason three tracks survived on a wide screen showing a
       narrow panel. */
    expect(atRulesFor(".ws-obligations")).toEqual([]);
  });

  it("lets the open group take the whole row, which is what lets it be read", () => {
    const spans = declarations('.ws-obligations__group[data-open="true"]', "grid-column");
    expect(spans).toEqual(["1 / -1"]);
  });

  it("keeps the owner's three-across where three genuinely fit", () => {
    /* The 2026-09-09 reference is three cards side by side, and that decision stands —
       this changes WHEN it applies, not whether. With a 360px floor, the ~1200px
       document-hidden panel still resolves to three columns; only the rail collapses. */
    const [columns] = declarations(".ws-obligations", "grid-template-columns");
    const floor = Number(columns?.match(/minmax\(\s*(\d+)px/)?.[1]);
    expect(Math.floor(1200 / floor)).toBe(3);
    expect(Math.floor(380 / floor)).toBe(1);
  });
});
