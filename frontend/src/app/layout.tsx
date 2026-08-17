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
    <html lang="en">
      <body>
        <SessionProvider>
          <Chrome>{children}</Chrome>
        </SessionProvider>
      </body>
    </html>
  );
}
