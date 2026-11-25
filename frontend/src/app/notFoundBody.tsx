"use client";

import Link from "@/components/AppLink";

import { EmptyState } from "@/components/Feedback";
import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";
// outside the dashboard layout, so the 404 brings the shell's sheet itself (W2-1)
import "./dashboard/workspace.css";

/** Every unknown address (the legacy routes redirect before they get here). Round 2 of UX
 *  Batch 2: inside the app header like every page, one h1, and the way back is the nav's
 *  own word — Contracts. A signed-out visitor is sent to sign in by the shell. */
export default function NotFoundBody() {
  return (
    <div className="ws-fonts">
      <WorkspaceShell>
        <div className="lm-page">
          <EmptyState heading="h1" title="Page not found" body="This address doesn’t exist, or the page has moved."
                      action={<Link className="ws-btn ws-btn--primary" href="/contracts">Go to Contracts</Link>} />
        </div>
      </WorkspaceShell>
    </div>
  );
}
