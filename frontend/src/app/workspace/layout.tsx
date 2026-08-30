/**
 * The new application's route group. Server layout; the shell is the one client
 * component (ui-ux-pro-max/nextjs: client components as leaves). Imports the new
 * foundation stylesheet — scoped under `.ws`, so the legacy stylesheet loaded at
 * the root never collides with it.
 */

import { WorkspaceShell } from "@/components/workspace/WorkspaceShell";

import "./workspace.css";

export default function WorkspaceRootLayout({ children }: { children: React.ReactNode }) {
  return <WorkspaceShell>{children}</WorkspaceShell>;
}
