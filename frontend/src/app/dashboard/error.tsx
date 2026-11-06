"use client";

/** A section that fails to render inside the shell: the navigation stays, and the
 *  section says what happened and offers to try again. */
export default function SectionError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="ws-state" role="alert">
      <h2>This page could not be shown.</h2>
      <p>Something went wrong while showing it. Nothing you saved is affected.</p>
      <button type="button" className="ws-btn ws-btn--sm" onClick={reset}>Try again</button>
    </div>
  );
}
