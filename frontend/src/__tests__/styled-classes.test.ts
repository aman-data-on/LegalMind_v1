/**
 * Every class name in the markup has a CSS rule behind it.
 *
 * WHY THIS EXISTS. `.ws-filter-bar` was written into Administration's markup and
 * its rule was never written anywhere. Nothing failed: the build was green, the
 * types were clean, and five filter controls stacked at full width on production
 * for a day until someone opened the page. A class with no rule is invisible to
 * every other check this project runs.
 *
 * Scanning the whole app turned up sixteen of them. This test is the floor: the
 * list below may SHRINK, never grow. A new unstyled class fails the build.
 *
 * `src/components/ui/` is excluded — those are shadcn primitives whose classes are
 * Tailwind utilities, generated at build time rather than authored in a stylesheet.
 */
import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const STYLESHEETS = ["src/app/globals.css", "src/app/dashboard/workspace.css"];
const EXCLUDED = "src/components/ui";

/**
 * Known unstyled classes, each a real element rendering with no rule of its own.
 * They are listed rather than fixed because writing the missing rules is a visual
 * judgement on the Ask, Findings and Evidence surfaces — it moves baselines and
 * belongs to a pass that can look at those screens, not to the test that found them.
 *
 * Do not add to this list. Fix the class or delete it.
 */
const KNOWN_UNSTYLED = [
  // `DecisionHistory.tsx` is imported by nothing; left in place rather than
  // deleted, because removing someone's component is their call, not this test's.
  "decision-history__meta",
  "tag--current",
  // `.evidence--none`, `.evidence__location` and `.evidence__text` all exist —
  // these four were added to the markup later and their rules never followed.
  "evidence",
  "evidence__item",
  "evidence__ocr",
  "evidence__relationship",
  // Same shape: the `.evaluation__*` family is otherwise complete.
  "evaluation__diagnostics",
  // The `.ws-ask__*` and `.ws-dock__*` families are otherwise complete too.
  "ws-ask__statutes",
  "ws-ask__turn",
  "ws-dock__launcher-text",
  // `.ws-evidence__group`, `__how`, `__loc` and `__more` exist; `__item` does not.
  "ws-evidence__item",
  // `.ws-turn--user` exists and `.ws-turn` does not — the modifier without its base.
  "ws-turn",
];

function tsxFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (path.startsWith(EXCLUDED)) continue;
    if (statSync(path).isDirectory()) tsxFiles(path, out);
    else if (path.endsWith(".tsx")) out.push(path);
  }
  return out;
}

function definedClasses(): Set<string> {
  const css = STYLESHEETS.map((f) => readFileSync(f, "utf8")).join("\n");
  return new Set([...css.matchAll(/\.([a-zA-Z][\w-]*)/g)].map((m) => m[1]!));
}

/** class name -> the files that use it, for every class with no rule. */
function unstyled(): Map<string, string[]> {
  const defined = definedClasses();
  const found = new Map<string, string[]>();
  for (const file of tsxFiles("src")) {
    const source = readFileSync(file, "utf8");
    // Only literal className strings: an interpolated one cannot be read here,
    // and guessing at template expressions would produce noise, not findings.
    for (const match of source.matchAll(/className="([^"{}]+)"/g)) {
      for (const cls of match[1]!.split(/\s+/).filter(Boolean)) {
        if (defined.has(cls)) continue;
        found.set(cls, [...(found.get(cls) ?? []), file]);
      }
    }
  }
  return found;
}

describe("every class in the markup has a rule", () => {
  it("introduces no new unstyled class", () => {
    const surprises = [...unstyled().entries()]
      .filter(([cls]) => !KNOWN_UNSTYLED.includes(cls))
      .map(([cls, files]) => `${cls} (${[...new Set(files)].join(", ")})`);
    expect(surprises, "class names with no CSS rule anywhere").toEqual([]);
  });

  it("keeps the known list honest — a fixed class must leave it", () => {
    // Otherwise the list rots into a permanent excuse and stops meaning anything.
    const still = new Set(unstyled().keys());
    const fixed = KNOWN_UNSTYLED.filter((cls) => !still.has(cls));
    expect(fixed, "no longer unstyled — remove from KNOWN_UNSTYLED").toEqual([]);
  });

  it("can actually see the stylesheets it checks against", () => {
    // A typo in a path would make every class look defined and the test vacuous.
    const defined = definedClasses();
    expect(defined.size).toBeGreaterThan(500);
    for (const anchor of ["ws-filter-bar", "ws-link", "card", "btn"]) {
      expect(defined, `${anchor} should be a known rule`).toContain(anchor);
    }
  });
});
