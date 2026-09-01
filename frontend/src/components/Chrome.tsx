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
import {
  FileText,
  CheckCircle,
  Settings,
  LogOut,
  LogIn,
  Users,
  BarChart3,
} from "lucide-react";

import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

interface NavItem {
  href: string;
  label: string;
  permission: string;
  icon: React.ReactNode;
}

/** One row per locked 52.6 screen, each carrying its 49.3 permission. */
const NAV: NavItem[] = [
  { href: "/contracts", label: "Contracts", permission: P.CONTRACT_VIEW, icon: <FileText size={18} /> },
  { href: "/reviews", label: "Reviews", permission: P.REVIEW_VIEW, icon: <CheckCircle size={18} /> },
  { href: "/configuration", label: "Legal configuration", permission: P.CONFIGURATION_VIEW, icon: <Settings size={18} /> },
  { href: "/audit", label: "Audit", permission: P.AUDIT_VIEW, icon: <BarChart3 size={18} /> },
  { href: "/admin", label: "Users & roles", permission: P.USER_MANAGE, icon: <Users size={18} /> },
];

export function Chrome({ children }: { children: React.ReactNode }) {
  const { identity, loading, can, signOut } = useSession();
  const pathname = usePathname();

  // DD-3 — /login owns its full-viewport composition; other bare states keep the narrow column.
  if (pathname === "/login") return <main className="shell shell--login">{children}</main>;

  // The new application (PRODUCT_UX_ROADMAP.md) brings its own shell and its own
  // loading/signed-out states under /documents (WorkspaceShell) — checked BEFORE
  // the legacy loading/signed-out fallbacks below, which would otherwise render
  // first and put legacy markup on a new-UI route (found in browser testing,
  // 2026-08-30: a signed-out visit to /documents showed the bare "You are signed
  // out" shell before ever reaching the new one). This legacy chrome guarantees
  // nothing for /documents; the two never render together either way.
  //
  // `/` is included too, and for a sharper reason than styling: the loading and
  // signed-out branches below return their OWN JSX and never render `{children}`
  // at all — so `/`'s own page component (whose only job is a client-side
  // `router.replace("/documents")` in a `useEffect`) would never even MOUNT while
  // signed out, and the redirect would silently never fire. Measured, not
  // assumed: this is what a signed-out visit to `/` actually did before this
  // line included it.
  if (pathname === "/" || pathname.startsWith("/documents")) return <>{children}</>;

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
              title={item.label}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="topbar__identity">
          <span>{identity.name}</span>
          <button type="button" className="link" onClick={() => void signOut()} title="Sign out">
            <LogOut size={18} />
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
