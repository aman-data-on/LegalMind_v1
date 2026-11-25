import type { Metadata } from "next";

import { NotFoundBody } from "./lazyNotFound";

export const metadata: Metadata = {
  title: "Page not found",
  description: "This LegalMind address does not exist.",
};

export default function NotFound() {
  return <NotFoundBody />;
}
