import { execSync } from "node:child_process";

import type { NextConfig } from "next";
import { PHASE_PRODUCTION_BUILD } from "next/constants";

/**
 * The dev-time API proxy exists for one reason: the session cookie is
 * `Secure; SameSite=Strict; HttpOnly` (locked S-3), so a browser will not send it
 * cross-origin. In production the frontend and the API sit behind one origin
 * (Step 55); in development the rewrite below reproduces that, so the browser
 * only ever makes same-origin requests and no locked cookie attribute has to be
 * weakened to make development work.
 *
 * This is a request proxy, not a data path: it forwards HTTP to `/api/v1/` and
 * nothing here reaches a repository or the database (38.22, 52.2).
 */
const apiOrigin = process.env.LEGALMIND_API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  /**
   * Build output directory. Defaults to `.next` so nothing changes for a local
   * build or for CI.
   *
   * It is overridable for one reason, learned the hard way on 2026-09-01: the
   * production systemd unit serves `.next` straight out of this working tree, and
   * `next build` **deletes and rewrites that directory in place**. A build that
   * then fails partway leaves the live site with no `BUILD_ID` and half its
   * chunks — which is exactly what happened, and the symptom was every page stuck
   * on "Loading…" forever while HTTP still answered 200.
   *
   * `scripts/deploy-frontend.sh` therefore builds into a staging directory and
   * only swaps it into place once the build has actually succeeded. Never run a
   * bare `next build` against a tree a live service is serving.
   */
  distDir: process.env.LEGALMIND_NEXT_DIST ?? ".next",
  // Dev-only: lets a browser on the LAN reach the dev server's own static
  // chunks when the page is opened via the machine's IP (Next blocks
  // cross-origin dev assets by default). Production serves built assets and
  // never consults this. NOTE the locked S-3 cookie is `Secure`, so signing in
  // still requires a secure context — use an SSH tunnel to localhost.
  allowedDevOrigins: ["202.66.172.110"],
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${apiOrigin}/api/v1/:path*` }];
  },
  /**
   * Deploys must be visible on an ORDINARY reload (2026-09-02). Next's static
   * prerender ships page HTML with `s-maxage=31536000` and no private-cache
   * directive, so a browser was free to keep yesterday's HTML — which
   * references yesterday's hashed chunk URLs, deleted by the deploy swap. The
   * owner loaded the workspace right after a deploy and saw none of it.
   *
   * `no-cache` (NOT `no-store`) is deliberate: the browser may keep a copy but
   * must revalidate before using it — a cheap 304 on the unchanged case, the
   * fresh page the moment a deploy lands. Hashed assets under `/_next/static/`
   * keep their immutable year-long caching; this header applies to page HTML
   * only (everything except Next's own asset paths).
   */
  async headers() {
    return [
      {
        source: "/((?!_next/static|_next/image).*)",
        headers: [{ key: "Cache-Control", value: "no-cache" }],
      },
    ];
  },
};

/**
 * The build guard, at the one layer no entry point can walk around (2026-09-02).
 *
 * `scripts/guard-build-target.mjs` refuses an in-place build — but it is an npm
 * `prebuild` hook, so it fires only on `npm run build`. `npx next build` walks
 * straight past it, and on 2026-09-02 exactly that happened: the Playwright
 * web-server command rebuilt `.next` in place, the running `legalmind-frontend`
 * service kept serving HTML that named the OLD chunk hashes, and every live page
 * lost its stylesheet while nginx answered 200 throughout.
 *
 * Exporting a phase function puts the same refusal inside config resolution,
 * which EVERY invocation of `next build` performs — npm script, npx, a test
 * runner's web server, CI. The ordering guarantee is causal, not incidental:
 * `distDir` is a value of this config, so Next cannot clean or write the build
 * directory before this function has returned. A throw here therefore always
 * precedes the first byte written.
 *
 * The npm prebuild hook stays as a second layer with a friendlier message.
 */
function refuseInPlaceBuildWhileServing(): void {
  const dist = process.env.LEGALMIND_NEXT_DIST ?? ".next";
  // A staging or harness directory can never disturb what is being served.
  if (dist !== ".next") return;
  if (process.env.LEGALMIND_ALLOW_INPLACE === "1") return;
  let serving = false;
  try {
    serving =
      execSync("systemctl is-active legalmind-frontend 2>/dev/null || true", {
        encoding: "utf8",
      }).trim() === "active";
  } catch {
    return; // no systemd or no permission to ask — not a deployment host
  }
  if (!serving) return;
  throw new Error(
    "Refusing to build into .next: the legalmind-frontend service is ACTIVE and " +
      "serves that directory from this working tree, and `next build` rewrites it " +
      "in place. Deploy with `bash scripts/deploy-frontend.sh` (staging build, " +
      "atomic swap, rollback), or build elsewhere with " +
      "LEGALMIND_NEXT_DIST=<dir>, or — only if you truly mean to overwrite the " +
      "live output — set LEGALMIND_ALLOW_INPLACE=1.",
  );
}

export default function config(phase: string): NextConfig {
  if (phase === PHASE_PRODUCTION_BUILD) refuseInPlaceBuildWhileServing();
  return nextConfig;
}
