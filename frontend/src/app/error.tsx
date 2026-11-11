"use client";

/** Anything that fails to render outside the workspace shell (sign-in, a bare route):
 *  the same error block as inside the shell (GP-24), in the product's own surface. */
import Link from "next/link";

import { ErrorState } from "@/components/Feedback";

export default function AppError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="ws ws-fonts notfound">
      <p className="notfound__brand">LegalMind</p>
      <ErrorState heading="h1" title="This page could not be shown"
                  fix="Nothing you saved is affected." onRetry={reset}>
        <p className="lm-state__body"><Link href="/contracts">Go to Contracts</Link></p>
      </ErrorState>
    </main>
  );
}
