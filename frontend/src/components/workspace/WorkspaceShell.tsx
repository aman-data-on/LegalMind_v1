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
import { usePathname } from "next/navigation";

import { useSession } from "@/lib/session";

import { navItemsFor } from "./model";

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const { identity, loading, can, signOut } = useSession();
  const pathname = usePathname();
  const items = navItemsFor(can);

  // Mirrors the legacy shell's own guard: `can()` defaults to false before the
  // session resolves, so rendering `children` early would flash "Access
  // restricted" for an authenticated user on every hard navigation.
  if (loading) {
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
              aria-current={pathname.startsWith(item.href) ? "page" : undefined}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <span className="ws-shell__spacer" />
        <div className="ws-shell__user">
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
