import type { Metadata } from "next";

import WorkspaceRootLayout from "../dashboard/layout";

/** `/templates` (cross-page pass): a top-level section like `/contracts` and `/todo`, in the
 *  same shell; `/dashboard/templates…` redirects here (next.config.ts). */
export const metadata: Metadata = {
  title: "Templates",
  description: "Approve our contract templates clause by clause, then publish them.",
};

export default WorkspaceRootLayout;
