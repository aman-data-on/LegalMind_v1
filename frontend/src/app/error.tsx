"use client";

/** Anything that fails to render outside the workspace shell (sign-in, a bare route):
 *  the same error block as inside the shell (GP-24), in the product's own surface. */
import { ErrorState } from "@/components/Feedback";
import dynamic from "next/dynamic";

/** W2-1: the root error boundary is part of every page's tree; its sheet is a dynamic import
 *  so it loads only when this error renders, not on every page (/login included). */
const WorkspaceSheet = dynamic(() => import("./workspaceSheetBody"));

export default function AppError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <WorkspaceSheet>
      <main className="ws ws-fonts notfound">
        <p className="notfound__brand">LegalMind</p>
        <ErrorState heading="h1" title="This page could not be shown"
                    fix="Nothing you saved is affected." onRetry={reset}
                    back={{ href: "/contracts", label: "Go to Contracts" }} />
      </main>
    </WorkspaceSheet>
  );
}
