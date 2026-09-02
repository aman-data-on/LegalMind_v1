import type { Metadata } from "next";

import { Chrome } from "@/components/Chrome";
import { SessionProvider } from "@/lib/session";

import "./globals.css";

export const metadata: Metadata = {
  title: "LegalMind",
  description: "Contract review against Company Standards",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      {/* suppressHydrationWarning covers exactly one attribute mismatch depth
          (React's own scope for this prop): browser extensions (password
          managers, grammar/translation tools) commonly inject attributes onto
          <html> before hydration — e.g. data-qb-installed — which is not
          something this app ever sets. It does not hide a real app-state
          mismatch; those still surface normally. */}
      <body>
        <SessionProvider>
          <Chrome>{children}</Chrome>
        </SessionProvider>
      </body>
    </html>
  );
}
