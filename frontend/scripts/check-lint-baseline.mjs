// QA-080 (2026-10-30): the hooks lint gate covered Diff-Talk only, while the rest of src
// carried errors nobody counted. This runs ESLint over all of src and fails when any
// file has MORE errors than lint-baseline.json records — the count may only shrink.
// After fixing some, run with --update to lower the baseline.
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const BASELINE = new URL("../lint-baseline.json", import.meta.url);
let out;
try {
  out = execFileSync("npx", ["eslint", "src", "-f", "json"], { encoding: "utf8", maxBuffer: 1 << 26 });
} catch (failed) {
  out = failed.stdout;            // eslint exits 1 when it finds errors; the JSON is still there
}
const now = {};
for (const file of JSON.parse(out)) {
  if (file.errorCount) now[file.filePath.slice(file.filePath.indexOf("src/"))] = file.errorCount;
}
if (process.argv.includes("--update")) {
  writeFileSync(BASELINE, JSON.stringify(now, null, 2) + "\n");
  console.log(`lint baseline: ${Object.values(now).reduce((a, b) => a + b, 0)} errors recorded`);
  process.exit(0);
}
const baseline = JSON.parse(readFileSync(BASELINE, "utf8"));
const worse = Object.entries(now).filter(([f, n]) => n > (baseline[f] ?? 0));
for (const [f, n] of worse) console.error(`${f}: ${n} lint errors, baseline ${baseline[f] ?? 0}`);
if (worse.length) process.exit(1);
console.log(`lint baseline: no file got worse (${Object.values(now).reduce((a, b) => a + b, 0)} errors, all known)`);
