"use client";

/** Research — statute questions without a document (2026-09-08, `AM-47`).
 *
 *  The same Ask surface as the workspace, with no contract attached: the router
 *  answers from the approved statute corpus (Act + section citations) and the
 *  organization's approved positions, and refuses — naming the corpus's actual
 *  holdings — when the law asked about was never supplied (NI Act, Evidence Act;
 *  C-16). There is still no source selector: the question decides. */

import { AskDock } from "@/components/workspace/AskDock";
import { HighlightProvider } from "@/components/workspace/highlight";

export default function ResearchPage() {
  return (
    <>
      <div className="ws-context">
        <h1>Research</h1>
      </div>
      <div className="ws-docs">
        <div className="ws-state" role="note">
          <h2>Ask about the law itself.</h2>
          <p>
            Questions here are answered from the approved statute corpus, cited by Act and
            section, and from the organization&rsquo;s approved positions. A statute that has
            not been supplied to the system is not guessed at &mdash; the answer says what the
            corpus holds.
          </p>
        </div>
        <HighlightProvider>
          <AskDock contractId={null} documentVersionId={null} versionNumber={null} isLatest />
        </HighlightProvider>
      </div>
    </>
  );
}
