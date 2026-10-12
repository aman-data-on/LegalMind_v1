import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Page not found",
  description: "This LegalMind address does not exist.",
};

/** Every address outside /login and /dashboard lands here (the legacy routes
 *  redirect in next.config.ts), so it offers the way back, nothing else. */
export default function NotFound() {
  return (
    <main className="notfound">
      <p className="notfound__brand">LegalMind</p>
      <h1>Page not found</h1>
      <p>This address doesn&rsquo;t exist, or the page has moved.</p>
      <Link className="notfound__home" href="/dashboard">Go to the Dashboard</Link>
    </main>
  );
}
