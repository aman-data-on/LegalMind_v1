"use client";

/** Research — the disclosed placeholder (see ResearchPlaceholder). The page
 *  only adds the shell context line; the content is the static component so a
 *  unit test can pin its no-interactivity property. */

import { ResearchPlaceholder } from "@/components/workspace/ResearchPlaceholder";

export default function ResearchPage() {
  return (
    <>
      <div className="ws-context">
        <h1>Research</h1>
      </div>
      <ResearchPlaceholder />
    </>
  );
}
