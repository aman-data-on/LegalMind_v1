import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Ask",
  description: "Ask questions about contracts, company positions and Indian law, answered with citations.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
