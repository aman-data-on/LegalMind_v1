import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Reviews",
  description: "The queue of document reviews awaiting legal attention.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
