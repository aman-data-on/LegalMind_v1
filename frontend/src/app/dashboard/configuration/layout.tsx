import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Standards",
  description: "The Company Standards every review measures against.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
