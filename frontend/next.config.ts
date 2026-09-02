import type { NextConfig } from "next";

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
};

export default nextConfig;
