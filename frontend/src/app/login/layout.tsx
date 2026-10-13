import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to LegalMind with your LeapSwitch account.",
};

/** The sign-in page owns its full-viewport composition (DD-3). */
export default function LoginLayout({ children }: { children: React.ReactNode }) {
  return <main className="shell shell--login">{children}</main>;
}
