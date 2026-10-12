import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Diff-Talk",
  description: "Compare our document with a client contract, clause by clause, with changed wording marked.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
