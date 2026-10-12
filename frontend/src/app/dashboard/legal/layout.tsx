import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Legal",
  description: "Findings that need a legal decision.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
