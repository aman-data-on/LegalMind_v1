/**
 * The three locked boundary rules — 52.1, 38.22, 38.23, 43.31, 52.7.
 *
 * These are source-level assertions. That is unusual for a test suite and it is the
 * point: the rules they defend are about what the frontend *is not allowed to
 * contain*, and no behavioural test can prove the absence of a database client or a
 * classification rule. Locked C-EXT-1 rejected exactly this failure in the external
 * reference — pages that called data-access functions directly — so the check is
 * for the pattern, not for a symptom of it.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(process.cwd(), "src");

function sourceFiles(dir = SRC): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(ts|tsx)$/.test(entry) ? [path] : [];
  });
}

const files = sourceFiles();
const application = files.filter((path) => !path.includes("__tests__"));

function read(path: string): string {
  return readFileSync(path, "utf8");
}

describe("38.22 / 52.1 r1 — the frontend never touches the database", () => {
  it("declares no database dependency", () => {
    const manifest = JSON.parse(read(join(process.cwd(), "package.json"))) as {
      dependencies: Record<string, string>;
      devDependencies: Record<string, string>;
    };
    const declared = Object.keys({ ...manifest.dependencies, ...manifest.devDependencies });
    for (const forbidden of [
      "pg",
      "postgres",
      "mysql",
      "mysql2",
      "prisma",
      "@prisma/client",
      "drizzle-orm",
      "knex",
      "sequelize",
      "typeorm",
      "mongodb",
    ]) {
      expect(declared).not.toContain(forbidden);
    }
  });

  it("contains no SQL and no connection string", () => {
    for (const path of application) {
      const source = read(path);
      expect(source, path).not.toMatch(/\bSELECT\s+.+\s+FROM\b/i);
      expect(source, path).not.toMatch(/\bINSERT\s+INTO\b/i);
      expect(source, path).not.toMatch(/postgres(ql)?:\/\//);
      expect(source, path).not.toMatch(/DATABASE_URL/);
    }
  });

  it("routes every request through the single API client", () => {
    // `fetch` is permitted in exactly one module. Anywhere else it would be a
    // second data path, which is how the boundary erodes in practice.
    const callers = application.filter(
      (path) => /\bfetch\s*\(/.test(read(path)) && !path.endsWith(join("lib", "api.ts")),
    );
    expect(callers).toEqual([]);
  });

  it("addresses only the locked /api/v1 base path", () => {
    const api = read(join(SRC, "lib", "api.ts"));
    expect(api).toContain('export const API_BASE = "/api/v1"');
  });
});

describe("38.23 / 52.1 r2 — the frontend never implements legal logic", () => {
  it("derives no classification, roll-up or decision requirement", () => {
    // Locked 52.7: "No derived legal value is computed client-side —
    // classification, roll-up, `requires_decision` and rule outcomes arrive from
    // the API." A local computation would be a second implementation of the Tier-1
    // / Tier-2 roll-up, free to disagree with the engine.
    const forbidden: [RegExp, string][] = [
      [/\brequires_decision\s*[:=]\s*(?!\s*(?:boolean|evaluation|false\b))/, "computing requires_decision"],
      [/\bTIER_1\b|\bROLLUP\b|\brollUp\b|\brollup\(/, "roll-up logic"],
      [/UNABLE_TO_EVALUATE\s*[>&|]/, "classification precedence"],
      [/\bclassify\s*\(/, "a classification function"],
      [/\bevaluateRule\b|\bapplyLegalRule\b|\bcomputeOutcome\b/, "rule evaluation"],
    ];
    for (const path of application) {
      const source = read(path);
      for (const [pattern, description] of forbidden) {
        expect(pattern.test(source), `${path} contains ${description}`).toBe(false);
      }
    }
  });

  it("never assigns a rule outcome", () => {
    for (const path of application) {
      // Reading and displaying `rule_outcome` is required (52.5); assigning one
      // would be deciding it.
      expect(read(path), path).not.toMatch(/rule_outcome\s*=\s*["']/);
    }
  });
});

describe("52.5 / AB-1 — no Finding-level decision or resolve control", () => {
  it("the Finding component accepts no decision or resolution props", () => {
    const source = read(join(SRC, "components", "FindingCard.tsx"));
    // A decision resolves exactly one Evaluation (AB-1.1). A Finding-level control
    // would implicitly dispose of every Evaluation under it.
    expect(source).not.toMatch(/onDecide|onResolve|recordDecision|resolveFinding/);
  });

  it("the API client exposes no Finding-level decision call and no resolve call", () => {
    const api = read(join(SRC, "lib", "api.ts"));
    expect(api).not.toMatch(/findings\/\$\{[^}]+\}\/decisions/);
    expect(api).not.toMatch(/\/resolve\b/);
    // Supersession is a create (Step 31 r14): there is no update path.
    expect(api).not.toMatch(/decisions\/\$\{[^}]+\}["'`]\s*,\s*\{\s*method:\s*["']PATCH/);
  });

  it("nothing sets a Review or Finding status", () => {
    // Step 30 r3 — users cannot arbitrarily set Review status; D-3.6 — resolution
    // is derived, never asserted.
    for (const path of application) {
      const source = read(path);
      expect(source, path).not.toMatch(/\/reviews\/\$\{[^}]+\}\/status/);
      expect(source, path).not.toMatch(/status:\s*["']RESOLVED["']/);
    }
  });
});

describe("52.7 — no optimistic UI for Legal Decisions", () => {
  it("the decision panel re-fetches rather than patching local state", () => {
    const source = read(join(SRC, "components", "DecisionPanel.tsx"));
    // A 409 is a real outcome, so the recorded decision must come from the server.
    expect(source).toContain("isConflict");
    expect(source).toContain("onRecorded");
    // It must never fabricate a current decision locally.
    expect(source).not.toMatch(/setEvaluation|evaluation\.current_decision\s*=/);
  });

  it("sends expected_version so a collision is detectable", () => {
    const source = read(join(SRC, "components", "DecisionPanel.tsx"));
    expect(source).toContain("expected_version");
  });
});

describe("rule 21 — no legal content is authored in the UI", () => {
  it("ships no threshold, tolerance or example Company Standard as a default", () => {
    // Locked rule 21: real Company Standards and Legal Rules must be supplied by
    // the organization, never manufactured. A prefilled "6 months" in a form would
    // become the organization's position by accident.
    for (const path of application) {
      const source = read(path);
      expect(source, path).not.toMatch(/defaultValue=["'][^"']*\d+\s*month/i);
      expect(source, path).not.toMatch(/placeholder=["'][^"']*\b\d+\s*(month|year|%)/i);
    }
  });

  it("offers exactly the two locked evaluator types", () => {
    const source = read(join(SRC, "app", "configuration", "page.tsx"));
    // Scoped to the evaluator_type control. `PRESENCE` is deliberately also a
    // locked RuleType value (THRESHOLD / ALLOWED_VALUES / PRESENCE), so an
    // unscoped scan sees it twice and proves nothing about either vocabulary.
    const select = source.slice(
      source.indexOf('name="evaluator_type"'),
      source.indexOf("</select>", source.indexOf('name="evaluator_type"')),
    );
    const options = [...select.matchAll(/<option value="([A-Z_]+)">/g)].map((m) => m[1]);
    expect(options.sort()).toEqual(["NUMERIC_COMPARISON", "PRESENCE"]);
    // AM-16 fixes the vocabulary at two. Anything else would be inventing an
    // evaluator (N-30 removed TEXT_PATTERN for exactly this reason).
    expect(source).not.toContain("TEXT_PATTERN");
    expect(source).not.toContain("SEMANTIC");
  });
});
