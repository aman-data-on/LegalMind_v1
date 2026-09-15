/**
 * The CSS foundation's contract, asserted against the REAL compiled stylesheet.
 *
 * Every property checked here is silent when it breaks: the build stays green,
 * the types stay clean, and a screen renders slightly wrong somewhere nobody is
 * looking. Each `it` below corresponds to a trap that was actually hit while
 * building this (2026-09-15, DD-22) — none is hypothetical.
 */
import { describe, expect, it, beforeAll } from "vitest";
import { readFileSync, readdirSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";
import postcss from "postcss";
import tailwind from "@tailwindcss/postcss";

const GLOBALS = "src/app/globals.css";
const PROBE_DIR = "src/components/ui";
const PROBE = join(PROBE_DIR, "__css_foundation_probe.tsx");

async function compile(): Promise<postcss.Root> {
  const css = readFileSync(GLOBALS, "utf8");
  const result = await postcss([tailwind()]).process(css, { from: GLOBALS });
  return result.root;
}

/**
 * The layer a selector is emitted into — the whole cascade argument depends on
 * it. Walks the real AST rather than matching text: a first attempt counted
 * `@layer x {` openings in the string, never saw the closing braces, and
 * reported every later rule as still inside the last layer opened.
 */
function layerOf(root: postcss.Root, selector: string): string {
  let found = "(absent)";
  root.walk((node) => {
    const matches =
      (node.type === "rule" && node.selector === selector) ||
      (node.type === "decl" && `${node.prop}: ${node.value}` === selector) ||
      (node.type === "decl" && node.prop === selector);
    if (!matches || found !== "(absent)") return;
    // Only these three fields are needed, and postcss's own parent union
    // (`Document_ | Container_`) does not satisfy `exactOptionalPropertyTypes`.
    type Ancestor = { type: string; name?: string; params?: string; parent?: Ancestor };
    for (let p = node.parent as Ancestor | undefined; p; p = p.parent) {
      if (p.type === "atrule" && p.name === "layer") {
        found = p.params ?? "";
        return;
      }
    }
    found = "(unlayered)";
  });
  return found;
}

/** Every utility class name emitted, for the allow-list assertion. */
function utilityNames(root: postcss.Root): string[] {
  const names: string[] = [];
  root.walkAtRules("layer", (layer) => {
    if (layer.params !== "utilities") return;
    layer.walkRules((rule) => {
      names.push(rule.selector);
    });
  });
  return names;
}

describe("the compiled stylesheet", () => {
  let root: postcss.Root;
  let sources = ""; // the allow-listed directory, read while the probe still exists
  beforeAll(async () => {
    // A probe component gives the allow-list something to find, so the
    // "utilities are generated at all" and "only from the allow-list"
    // assertions test opposite failures rather than the same one.
    mkdirSync(PROBE_DIR, { recursive: true });
    writeFileSync(PROBE, 'export const P = () => <i className="flex border-border" />;\n');
    try {
      root = await compile();
      sources = readdirSync(PROBE_DIR)
        .map((f) => readFileSync(join(PROBE_DIR, f), "utf8"))
        .join("\n");
    } finally {
      rmSync(PROBE, { force: true });
    }
  }, 60_000);

  it("never imports preflight", () => {
    // Preflight would reset `ul, ol` (17 and 14 in this app, none re-styled
    // below) and `a` (38 links, 3 styled), moving the ws-admin baseline.
    //
    // Matched on selectors ONLY preflight emits. A first version asserted the
    // absence of `list-style: none` and failed on LegalMind's own `.evaluations`
    // — a declaration this app is entitled to use itself.
    const selectors = new Set<string>();
    root.walkRules((rule) => {
      selectors.add(rule.selector);
    });
    for (const fingerprint of ["abbr:where([title])", "ul, ol", "html, :host"]) {
      expect(selectors, `${fingerprint} is a preflight-only selector`).not.toContain(fingerprint);
    }
    expect(root.toString()).not.toContain("-webkit-text-size-adjust");
  });

  it("supplies the one preflight behaviour shadcn needs, with its width partner", () => {
    // `border-style: solid` WITHOUT `border-width: 0` gives every element on the
    // page the initial `medium` width — a 3px border around everything.
    const rule = root.toString().match(/\*, ::before, ::after \{[^}]*\}/)?.[0] ?? "";
    expect(rule).toContain("border-style: solid");
    expect(rule).toContain("border-width: 0");
  });

  it("puts the bare-element rules where utilities can beat them", () => {
    // This is the entire reason shadcn could not be styled here before.
    expect(layerOf(root, "button")).toBe("base");
    expect(layerOf(root, "input, select, textarea")).toBe("base");
    expect(layerOf(root, "label")).toBe("base");
  });

  it("keeps the design system unlayered, so it still outranks every utility", () => {
    // `.card`/`.btn`/`.field` must NOT become overridable by a stray utility.
    expect(layerOf(root, ".card")).toBe("(unlayered)");
    expect(layerOf(root, ".btn")).toBe("(unlayered)");
    expect(layerOf(root, ".field")).toBe("(unlayered)");
  });

  it("declares utilities last, so they win over @layer base", () => {
    // Tailwind emits `@layer properties;` of its own first, so take the
    // statement that actually orders ours rather than the first one seen.
    const statements = [...root.toString().matchAll(/@layer ([^;{]+);/g)]
      .map((m) => m[1] ?? "");
    const order = statements.find((o) => o.includes("utilities"))?.split(", ") ?? [];
    expect(order).toEqual(["theme", "base", "utilities"]);
  });

  it("generates utilities only from the @source allow-list", () => {
    // `source(none)` is load-bearing. Without it Tailwind's automatic detection
    // scans the whole project: measured at 30 utilities with an EMPTY allow-list,
    // `.flex` and `.collapse` among them, any of which could have claimed an
    // existing class name.
    const names = utilityNames(root);
    expect(names).toContain(".flex"); // the probe's, so generation works at all

    // The real property: nothing is emitted that the allow-listed directory does
    // not ask for. With `source(none)` removed this fails immediately — measured
    // at 30 utilities from an EMPTY directory, `.collapse` and `.static` among
    // them, scavenged out of unrelated markup.
    const strays = names.filter((selector) => {
      const candidate = (selector.match(/^\.((?:\\.|[^ :>~(\[])+)/)?.[1] ?? "")
        .replace(/\\/g, "");
      return candidate !== "" && !sources.includes(candidate);
    });
    expect(strays, "utilities emitted from outside the allow-list").toEqual([]);
  });

  it("lets LegalMind's values win the seven shared token names", () => {
    // Tailwind's theme layer declares --text-* and --radius-* too. LegalMind's
    // :root must stay UNLAYERED so its values win and shadcn primitives inherit
    // this product's type and radius scale. Wrap that :root in a layer and every
    // adopted primitive silently changes size.
    const source = readFileSync(GLOBALS, "utf8");
    for (const token of ["--text-xs", "--text-sm", "--text-base", "--text-lg",
                         "--radius-xs", "--radius-sm", "--radius-md"]) {
      expect(layerOf(root, token), `${token} is declared by Tailwind's theme layer`)
        .toBe("theme");
      expect(source, `${token} must stay in the unlayered :root`).toContain(`  ${token}: `);
    }
    expect(layerOf(root, "--radius-sm: 4px")).toBe("(unlayered)");
  });
});
