import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Clients",
  description: "Every document LegalMind holds for a client, in one place.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
