"use client";

import { ErrorState } from "@/components/Feedback";

/** A section that fails to render inside the shell: the navigation stays, and the
 *  section says what happened and offers to try again (GP-24: the same block as the
 *  root boundary; here the error IS the page, so its heading is the h1). */
export default function SectionError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="lm-page">
      <ErrorState heading="h1" title="This page could not be shown"
                  fix="Nothing you saved is affected." onRetry={reset}
                  back={{ href: "/contracts", label: "Go to Contracts" }} />
    </div>
  );
}
