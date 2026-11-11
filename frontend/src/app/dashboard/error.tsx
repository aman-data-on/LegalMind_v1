"use client";

import Link from "next/link";

import { ErrorState } from "@/components/Feedback";

/** A section that fails to render inside the shell: the navigation stays, and the
 *  section says what happened and offers to try again (GP-24: the same block as the
 *  root boundary; here the error IS the page, so its heading is the h1). */
export default function SectionError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="lm-page">
      <ErrorState heading="h1" title="This page could not be shown"
                  fix="Nothing you saved is affected. Try again, or go back to Contracts." onRetry={reset}>
        <p className="lm-state__body"><Link href="/contracts">Go to Contracts</Link></p>
      </ErrorState>
    </div>
  );
}
