/**
 * The new application's route group. Server layout; the shell is the one client
 * component (ui-ux-pro-max/nextjs: client components as leaves). Imports the new
 * foundation stylesheet — scoped under `.ws`, so the legacy stylesheet loaded at
 * the root never collides with it.
 *
 * Typefaces (DD-8, owner approval 2026-08-31): the master prompt §4.3 faces,
 * bundled via `next/font` — downloaded at BUILD time and served from our own
 * origin, so no page load ever reaches a third-party font host (the DD-4
 * concern that ruled out the runtime CDN). Each face exposes a CSS variable the
 * stylesheet's role tokens (--ws-sans/--ws-mono/--ws-serif) consume, with the
 * previous system stacks kept as fallbacks. Weights match what the stylesheet
 * actually uses (400/500/600); no face beyond the three roles (§4.3: "No other
 * face anywhere").
 */

import { IBM_Plex_Mono, IBM_Plex_Sans, Source_Serif_4 } from "next/font/google";

import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

import "./workspace.css";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-plex-sans",
});
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-plex-mono",
});
const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  style: ["normal", "italic"],
  display: "swap",
  variable: "--font-source-serif",
});

export default function WorkspaceRootLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className={`ws-fonts ${plexSans.variable} ${plexMono.variable} ${sourceSerif.variable}`}
    >
      <WorkspaceShell>{children}</WorkspaceShell>
    </div>
  );
}
