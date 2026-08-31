"use client";

/**
 * The new application's shell — the ONE dark surface in the product
 * (UI_UX_MASTER_PROMPT §3/§4.5). Navigation is derived from permissions by
 * absence (52.3): a section the caller cannot use is not rendered. The permission
 * array is a rendering hint; every route it hides is authorized server-side.
 *
 * Skip link first (ui-ux-pro-max: nav-heavy pages need one), sticky bar that
 * never obscures focus (content gets scroll-margin), landmarks for assistive tech.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useSession } from "@/lib/session";

import { activeNavHref, navItemsFor } from "./model";

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const { identity, loading, can, signOut } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const items = navItemsFor(can);

  // A signed-out visitor goes to /login — owner ruling, 2026-08-31: "the correct
  // process: I log in, and then I land on the page based on RBAC." Before this,
  // a signed-out visit to any /workspace route rendered the shell with an empty
  // nav and the page's own "Access restricted" note — which reads as an RBAC
  // denial when the visitor simply isn't signed in. The permission gates on the
  // pages themselves are untouched: they remain the correct treatment for an
  // AUTHENTICATED account that genuinely lacks a permission.
  //
  // Declared above every early return (the React #310 lesson), and client-side
  // via router.replace — the same pattern `/` uses, since a Server-Component
  // redirect() does not complete through this app's provider tree (Next 16.3.1,
  // measured 2026-08-30).
  useEffect(() => {
    if (!loading && !identity) router.replace("/login");
  }, [loading, identity, router]);

  // Mirrors the legacy shell's own guard: `can()` defaults to false before the
  // session resolves, so rendering `children` early would flash "Access
  // restricted" for an authenticated user on every hard navigation. The
  // signed-out state renders the same quiet placeholder while the redirect
  // above lands — never a restricted flash, never an empty shell.
  if (loading || !identity) {
    return (
      <div className="ws">
        <p className="ws-visually-hidden" role="status" aria-live="polite">
          Loading…
        </p>
      </div>
    );
  }

  return (
    <div className="ws">
      <a className="ws-skip" href="#ws-main">
        Skip to content
      </a>
      <header className="ws-shell">
        <Link className="ws-shell__word" href="/workspace">
          LegalMind
        </Link>
        <nav className="ws-shell__nav" aria-label="Primary">
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={activeNavHref(pathname, items) === item.href ? "page" : undefined}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <span className="ws-shell__spacer" />
        <div className="ws-shell__user">
          <span className="ws-shell__avatar" aria-hidden="true">
            {(identity?.name ?? "?").charAt(0).toUpperCase()}
          </span>
          <span>{identity?.name}</span>
          <button type="button" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </header>
      <main id="ws-main" className="ws-main" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}
