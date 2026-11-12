import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Legal",
  description: "Points that need a Legal decision.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
