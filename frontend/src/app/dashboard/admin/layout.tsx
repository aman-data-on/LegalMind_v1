import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Administration",
  description: "Users, roles, departments and the audit log.",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
