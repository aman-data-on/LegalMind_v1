#!/usr/bin/env node
/**
 * No confidence scores in the UI — rule 12 / AI-03 item 16, as a build gate.
 *
 * DESIGN.md forbids "confidence percentages, risk scores, or traffic-light
 * rollups not backed by a real field", and the readiness R&D named the concrete
 * enforcement: a CI check that fails the build when a forbidden term enters
 * frontend source. This is that check.
 *
 * What it scans: every .ts/.tsx under src/, excluding test files (a test may
 * assert the ABSENCE of these words, which requires writing them).
 *
 * How it scans: comments are stripped first. A comment saying "never render a
 * confidence figure" is the rule being enforced, not a violation of it — the
 * danger is the word reaching a user, which means string literals, JSX text and
 * identifiers, all of which survive comment-stripping.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = join(import.meta.dirname, "..", "src");
const FORBIDDEN = ["confidence", "risk_score", "ai_confidence", "probability", "likelihood"];

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) {
      if (name === "__tests__") continue; // tests may assert absence
      yield* walk(path);
    } else if (/\.(ts|tsx)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name)) {
      yield path;
    }
  }
}

function stripComments(source) {
  // Good enough for a gate: removes /* */ and // comments. A forbidden word
  // inside a string literal survives, which is exactly the case that matters.
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

const violations = [];
for (const path of walk(ROOT)) {
  const code = stripComments(readFileSync(path, "utf8"));
  const lines = code.split("\n");
  lines.forEach((line, index) => {
    const lower = line.toLowerCase();
    for (const term of FORBIDDEN) {
      if (lower.includes(term)) {
        violations.push(`${relative(process.cwd(), path)}:${index + 1}  [${term}]  ${line.trim()}`);
      }
    }
  });
}

if (violations.length > 0) {
  console.error("Forbidden terms found in frontend source (rule 12 / AI-03 item 16):\n");
  for (const violation of violations) console.error("  " + violation);
  console.error(
    "\nA retrieval score is the sanctioned label; no confidence, risk-score,",
    "probability or likelihood figure may reach the UI.",
  );
  process.exit(1);
}
console.log(`check-forbidden-terms: clean (${FORBIDDEN.join(", ")})`);
