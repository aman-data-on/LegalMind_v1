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
import { useEffect, useRef, useState } from "react";

import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

import { IconBell, IconChevronDown, IconSparkle } from "./icons";
import { activeNavHref, navItemsFor } from "./model";

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const { identity, loading, can, signOut } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const items = navItemsFor(can);
  // One popover open at a time: the bell's panel or the account menu.
  const [open, setOpen] = useState<"bell" | "user" | null>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const toggleOf = (which: "bell" | "user") =>
    barRef.current?.querySelector<HTMLElement>(`[data-toggle="${which}"]`);

  // Outside click closes; on open, focus moves into the popover.
  useEffect(() => {
    if (!open) return;
    barRef.current?.querySelector<HTMLElement>(`[data-pop="${open}"] [tabindex], [data-pop="${open}"] [role='menuitem']`)?.focus();
    const away = (e: MouseEvent) => {
      if (!barRef.current?.contains(e.target as Node)) setOpen(null);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  // Escape closes and hands focus back to the toggle; Tab leaves the account menu.
  function onBarKey(e: React.KeyboardEvent) {
    if (!open) return;
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(null);
      toggleOf(open)?.focus();
    } else if (e.key === "Tab" && open === "user") setOpen(null);
  }

  // A signed-out visitor goes to /login — owner ruling, 2026-08-31: "the correct
  // process: I log in, and then I land on the page based on RBAC." Before this,
  // a signed-out visit to any /dashboard route rendered the shell with an empty
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
        {/*
          Two-tone wordmark (owner, 2026-09-02): "Legal" white, "Mind" brand blue.
          The two spans carry NO whitespace or newline between them — JSX would
          render that as a text node and the mark would read "Legal Mind". The
          accessible name is unaffected either way: both spans are plain text
          inside one link, so it is announced as "LegalMind, link".
        */}
        <Link className="ws-shell__word" href="/dashboard">
          <span className="ws-shell__word-a">Legal</span><span className="ws-shell__word-b">Mind</span>
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
        <div className="ws-shell__bar" ref={barRef} onKeyDown={onBarKey}>
          {/* No notifications endpoint exists yet (OD-15), so the panel says so
              rather than showing a badge or items it cannot back. */}
          <div className="ws-shell__bell">
            <button
              type="button"
              className="ws-shell__belltoggle"
              data-toggle="bell"
              aria-haspopup="dialog"
              aria-expanded={open === "bell"}
              aria-label="Notifications"
              onClick={() => setOpen(open === "bell" ? null : "bell")}
            >
              <IconBell size={17} />
            </button>
            {open === "bell" ? (
              <div className="ws-menu__list ws-shell__menu ws-shell__notes" role="dialog" aria-label="Notifications" data-pop="bell">
                <strong tabIndex={-1}>Notifications</strong>
                <span>Nothing to show. LegalMind does not send notifications yet, so there are no unread items.</span>
              </div>
            ) : null}
          </div>
        <div className="ws-shell__user">
          <button
            type="button"
            className="ws-shell__usertoggle"
            data-toggle="user"
            aria-haspopup="menu"
            aria-expanded={open === "user"}
            aria-label={`Account menu for ${identity.name}`}
            onClick={() => setOpen(open === "user" ? null : "user")}
          >
            <span className="ws-shell__avatar" aria-hidden="true">
              {identity.name.charAt(0).toUpperCase()}
            </span>
            <span>{identity.name}</span>
            <IconChevronDown size={14} />
          </button>
          {open === "user" ? (
            <div className="ws-menu__list ws-shell__menu" role="menu" aria-label="Account" data-pop="user">
              <div className="ws-shell__who">
                <strong>{identity.name}</strong>
                <span>{identity.email}</span>
                {identity.department ? <span>{identity.department.name}</span> : null}
              </div>
              <button type="button" role="menuitem" className="ws-menu__item"
                      onClick={() => { setOpen(null); void signOut(); }}>
                Sign out
              </button>
            </div>
          ) : null}
        </div>
        </div>
      </header>
      <main id="ws-main" className="ws-main" tabIndex={-1}>
        {children}
      </main>
      {/* The global way in to Ask (owner, 2026-09-11): every screen keeps a
          persistent entry point, and it NAVIGATES to the Ask workspace rather
          than opening a second, smaller chat beside the real one.

          It hides itself on the two screens that already own the conversation —
          the document workspace and Research (their own dock, DD-15/DD-17 r4)
          and Ask itself — with `:has()` in the stylesheet rather than a
          pathname test here, so the rule is "this page already has Ask" rather
          than a list of routes that has to be kept in step with the router. */}
      {can(P.ASSIST_ASK) ? (
        <Link className="ws-askglobal" href="/dashboard/ask">
          <IconSparkle size={17} />
          <span>Ask</span>
        </Link>
      ) : null}
    </div>
  );
}
