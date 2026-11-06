"use client";

/** Anything that fails to render outside the workspace shell (sign-in, a bare route):
 *  say so plainly and offer the one useful act — try again — plus the way home. */
import Link from "next/link";

export default function AppError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="notfound" role="alert">
      <p className="notfound__brand">LegalMind</p>
      <h1>This page could not be shown</h1>
      <p>Something went wrong while showing it. Nothing you saved is affected.</p>
      <button type="button" className="notfound__home" onClick={reset}>Try again</button>
      <Link href="/dashboard">Go to the Dashboard</Link>
    </main>
  );
}
