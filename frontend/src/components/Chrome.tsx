"use client";

/**
 * Application shell and navigation — locked 52.3, 52.6.
 *
 * Navigation is permission-driven: "A control the user cannot invoke is not
 * rendered" (52.3). A Super Admin therefore sees Audit and Administration but no
 * Contracts or Reviews, which is not a UI quirk — locked Step 23 gives Super Admin
 * no contract or Legal content access, and Step 24 r8 says so explicitly. The
 * navigation reflecting that is the point.
 *
 * The permission array comes from `GET /auth/session` and drives presentation only
 * (43.31, 47.6 r3). Every route it hides is still authorized server-side.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

interface NavItem {
  href: string;
  label: string;
  permission: string;
}

/** One row per locked 52.6 screen, each carrying its 49.3 permission. */
const NAV: NavItem[] = [
  { href: "/contracts", label: "Contracts", permission: P.CONTRACT_VIEW },
  { href: "/reviews", label: "Reviews", permission: P.REVIEW_VIEW },
  { href: "/configuration", label: "Legal configuration", permission: P.CONFIGURATION_VIEW },
  { href: "/audit", label: "Audit", permission: P.AUDIT_VIEW },
  { href: "/admin", label: "Users & roles", permission: P.USER_MANAGE },
];

export function Chrome({ children }: { children: React.ReactNode }) {
  const { identity, loading, can, signOut } = useSession();
  const pathname = usePathname();

  // DD-3 — /login owns its full-viewport composition; other bare states keep the narrow column.
  if (pathname === "/login") return <main className="shell shell--login">{children}</main>;

  if (loading) {
    return (
      <main className="shell shell--bare">
        {/* Phase 1 accessibility fix (docs/design/UX_AUDIT.md §2) — same as Feedback's Loading. */}
        <p className="hint" role="status" aria-live="polite">
          Loading…
        </p>
      </main>
    );
  }

  if (!identity) {
    return (
      <main className="shell shell--bare">
        <h1>LegalMind</h1>
        <p>
          You are signed out. <Link href="/login">Sign in</Link>.
        </p>
      </main>
    );
  }

  return (
    <div className="shell">
      <header className="topbar">
        <span className="topbar__brand">LegalMind</span>
        <nav className="topbar__nav">
          {NAV.filter((item) => can(item.permission)).map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={pathname.startsWith(item.href) ? "active" : undefined}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="topbar__identity">
          <span>{identity.name}</span>
          <button type="button" className="link" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </header>
      <main className="content">{children}</main>
      <footer className="footer">
        <p className="hint">
          Findings are produced by a deterministic engine and are not legal advice. A
          Legal Decision is recorded only by an authorized person.
        </p>
      </footer>
    </div>
  );
}
