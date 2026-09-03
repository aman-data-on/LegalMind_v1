/**
 * Refuses an in-place `next build` while a live service is serving `.next`.
 *
 * WHY. On 2026-09-01 a `next build` run in this working tree failed partway on a
 * type error in an unrelated route. `next build` deletes and rewrites its output
 * directory in place, so the failure left the LIVE site with no `BUILD_ID` and
 * half a chunk set. nginx kept returning 200 and every scripted check passed;
 * the only symptom was every page hanging on "Loading…" in a real browser.
 *
 * Documentation does not prevent that — a hook does. This runs as `prebuild`, so
 * it fires on `npm run build` no matter who or what invokes it.
 *
 * ⚠️ It does NOT fire on a bare `npx next build`, which is how the Playwright
 * web server rebuilt the live `.next` on 2026-09-02. The load-bearing layer is
 * therefore the phase guard inside `next.config.ts`, which every `next build`
 * invocation must pass through before `distDir` is even known. This hook stays
 * as the friendlier, earlier message on the `npm run build` path.
 *
 * Escape hatches, both explicit:
 *   LEGALMIND_NEXT_DIST=<dir>   build somewhere else (what the deploy script does)
 *   LEGALMIND_ALLOW_INPLACE=1   "I know, do it anyway"
 */

import { execSync } from "node:child_process";

const SERVICE = "legalmind-frontend";
const dist = process.env.LEGALMIND_NEXT_DIST ?? ".next";

// Building to a staging directory can never disturb what is being served.
if (dist !== ".next") process.exit(0);
if (process.env.LEGALMIND_ALLOW_INPLACE === "1") process.exit(0);

let serving = false;
try {
  serving = execSync(`systemctl is-active ${SERVICE} 2>/dev/null || true`, {
    encoding: "utf8",
  }).trim() === "active";
} catch {
  // No systemd, or no permission to ask it. Not a deployment host; nothing to guard.
  process.exit(0);
}

if (!serving) process.exit(0);

console.error(`
✖ Refusing to run an in-place \`next build\`.

  ${SERVICE} is ACTIVE and serving ${process.cwd()}/.next.
  \`next build\` rewrites that directory in place, so a build that fails partway
  takes the live site down in a way HTTP checks do not catch — it answers 200 and
  hangs on "Loading…" forever. That happened on 2026-09-01.

  Deploy instead (builds to staging, verifies, swaps atomically, rolls back):

      bash scripts/deploy-frontend.sh

  Or build without touching what is served:

      LEGALMIND_NEXT_DIST=.next-staging npx next build

  If you genuinely mean to overwrite the live output:

      LEGALMIND_ALLOW_INPLACE=1 npm run build
`);
process.exit(1);
