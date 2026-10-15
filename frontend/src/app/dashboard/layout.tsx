/**
 * The new application's route group. Server layout; the shell is the one client
 * component (ui-ux-pro-max/nextjs: client components as leaves). Imports the new
 * foundation stylesheet — scoped under `.ws`, so the legacy stylesheet loaded at
 * the root never collides with it.
 *
 * Typefaces (DD-8, owner approval 2026-08-31): the master prompt §4.3 faces,
 * self-hosted in `./fonts.css` and served from our own origin, so no page load
 * ever reaches a third-party font host (the DD-4 concern that ruled out the
 * runtime CDN) and no build does either (the font host failed CI builds,
 * 2026-10-15). Each face exposes a CSS variable on `.ws-fonts` that the
 * stylesheet's role tokens (--ws-sans/--ws-mono/--ws-serif) consume, with the
 * previous system stacks kept as fallbacks. Weights match what the stylesheet
 * actually uses (400/500/600); no face beyond the three roles (§4.3: "No other
 * face anywhere").
 */

import type { Metadata } from "next";

import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

import "./fonts.css";
import "./workspace.css";

export const metadata: Metadata = {
  // `absolute` for the Dashboard itself; `template` so every section below it
  // still reads "Diff-Talk · LegalMind" (a plain string here would cut it off).
  title: { absolute: "Dashboard · LegalMind", template: "%s · LegalMind" },
  description: "Your contracts, their review status, and what needs attention.",
};

export default function WorkspaceRootLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="ws-fonts">
      <WorkspaceShell>{children}</WorkspaceShell>
    </div>
  );
}
