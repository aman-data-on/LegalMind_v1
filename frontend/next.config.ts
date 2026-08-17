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
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${apiOrigin}/api/v1/:path*` }];
  },
};

export default nextConfig;
