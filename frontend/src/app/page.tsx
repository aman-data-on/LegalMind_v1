"use client";

/**
 * A client-side redirect, deliberately not the Server-Component `redirect()`.
 *
 * Measured in this Next.js version (16.3.1 — see frontend/AGENTS.md's warning
 * that this is not the Next.js prior training data describes): a Server
 * Component page whose body is only `redirect()` encodes the target in the RSC
 * flight stream rather than a plain HTTP 307 (confirmed with `curl -I`: 200, no
 * `Location` header, no `<meta refresh>`), and in a full page load through this
 * app's `RootLayout > SessionProvider > Chrome` tree that flight-based redirect
 * did not complete — the browser stayed on `/` rendering `Chrome`'s own
 * signed-out fallback instead of ever reaching `/workspace`.
 *
 * `useRouter().replace()` is the same mechanism `login/page.tsx` already uses
 * for its own post-login navigation, and it works there — so this follows the
 * pattern already proven in this codebase rather than the one that measurably
 * did not.
 */

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/workspace");
  }, [router]);
  return null;
}
