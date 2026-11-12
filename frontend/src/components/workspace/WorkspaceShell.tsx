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
import { loginPath, useSession } from "@/lib/session";

import { IconChevronDown, IconMenu, IconSparkle } from "./icons";
import { activeNavHref, navItemsFor } from "./model";
import { BellToggle, NotificationPanel, useNotifications } from "./Notifications";
import { LoadingState } from "@/components/Feedback";

/** The floating Ask button steps aside while the reader scrolls down a list and comes back
 *  on the way up or at the top (the standard FAB behaviour) — so it never sits over the
 *  row being read. Capture catches whichever element scrolls; rAF keeps it to one read a
 *  frame. Hidden is presentation only: the link stays in the tab order and shows on focus. */
function useHiddenOnScrollDown(): boolean {
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    // a scroller seen for the first time is taken to start at its top
    let last = 0, frame = 0, source: EventTarget | null = null;
    const read = () => {
      frame = 0;
      const el = source instanceof Element ? source : document.scrollingElement;
      const y = el?.scrollTop ?? 0;
      if (y <= 24) setHidden(false);
      else if (Math.abs(y - last) > 4) setHidden(y > last);
      else return; // a slow drag adds up until it passes the threshold
      last = y;
    };
    const onScroll = (e: Event) => {
      if (source !== e.target) { source = e.target; last = 0; }
      if (!frame) frame = requestAnimationFrame(read);
    };
    document.addEventListener("scroll", onScroll, { capture: true, passive: true });
    return () => {
      document.removeEventListener("scroll", onScroll, { capture: true });
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);
  return hidden;
}

const FIRST_SCREEN_FACES = [
  '400 1em "IBM Plex Sans"', '500 1em "IBM Plex Sans"', '600 1em "IBM Plex Sans"',
  '400 1em "Source Serif 4"', '700 1em "Source Serif 4"', 'italic 400 1em "Source Serif 4"',
  '400 1em "IBM Plex Mono"',
];

/** The account's circle: the sign-in provider's profile photo when there is one, the
 *  first letter of the name otherwise — and again if the photo cannot be loaded. */
export function Avatar({ name, picture }: { name: string; picture?: string | null | undefined }) {
  const [broken, setBroken] = useState(false);
  return (
    <span className="ws-shell__avatar" aria-hidden="true">
      {picture && !broken ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={picture} alt="" referrerPolicy="no-referrer" onError={() => setBroken(true)} />
      ) : (
        name.charAt(0).toUpperCase()
      )}
    </span>
  );
}

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const { identity, loading, can, signOut } = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const items = navItemsFor(can);
  // One popover open at a time: the bell's panel or the account menu.
  const [open, setOpen] = useState<"bell" | "user" | null>(null);
  /** page 2 — on a phone the sections are a menu, not a strip clipped at "Asi" */
  const [navOpen, setNavOpen] = useState(false);
  const notes = useNotifications(open === "bell", !loading && !!identity);
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
  const askAway = useHiddenOnScrollDown();
  // Start every face the first screen draws while the page's data is still loading: a
  // face fetched only when the document first uses it swapped in after the text was laid
  // out and reflowed it (phone CLS, 2026-11-06). The fallback stays if one fails.
  useEffect(() => {
    for (const face of FIRST_SCREEN_FACES) void document.fonts?.load(face).catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!loading && !identity) router.replace(loginPath());
  }, [loading, identity, router]);

  // Mirrors the legacy shell's own guard: `can()` defaults to false before the
  // session resolves, so rendering `children` early would flash "Access
  // restricted" for an authenticated user on every hard navigation. The
  // signed-out state renders the same quiet placeholder while the redirect
  // above lands — never a restricted flash, never an empty shell.
  // Round 2: the shell itself, with the wordmark and a skeleton, never a blank page — the
  // nav waits (it is permission-shaped), the page announces "Loading…" once.
  if (loading || !identity) {
    return (
      <div className="ws">
        <header className="ws-shell">
          <span className="ws-shell__word"><span className="ws-shell__word-a">Legal</span><span className="ws-shell__word-b">Mind</span></span>
        </header>
        <main id="ws-main" className="ws-main"><div className="lm-page"><LoadingState rows={5} /></div></main>
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
        <button type="button" className="ws-shell__navtoggle" aria-expanded={navOpen}
                aria-controls="ws-shell-nav" aria-label="Menu"
                onClick={() => setNavOpen((o) => !o)}
                onKeyDown={(e) => { if (e.key === "Escape") setNavOpen(false); }}>
          <IconMenu size={20} />
        </button>
        <nav id="ws-shell-nav" className="ws-shell__nav" aria-label="Primary"
             data-open={navOpen ? "" : undefined}
             onKeyDown={(e) => { if (e.key === "Escape") setNavOpen(false); }}>
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={activeNavHref(pathname, items) === item.href ? "page" : undefined}
              onClick={() => setNavOpen(false)}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <span className="ws-shell__spacer" />
        <div className="ws-shell__bar" ref={barRef} onKeyDown={onBarKey}>
          {/* B3 p2: on a phone Ask lives here, in the app bar — a floating button there
              covered list rows (WCAG 2.4.11); above 760px this is not drawn */}
          {can(P.ASSIST_ASK) ? (
            <Link className="ws-shell__ask" href="/dashboard/ask" aria-label="Ask">
              <IconSparkle size={18} />
            </Link>
          ) : null}
          {/* AM-273 m3 (AB-150): the caller's own notices, a fixed sentence and a link. */}
          <div className="ws-shell__bell">
            <BellToggle unread={notes.list.unread} open={open === "bell"}
                        onClick={() => setOpen(open === "bell" ? null : "bell")} />
            {open === "bell" ? (
              <NotificationPanel list={notes.list} reload={notes.reload}
                                 onClose={() => setOpen(null)} />
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
            <Avatar name={identity.name} picture={identity.picture} />
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
        <Link className="ws-askglobal" href="/dashboard/ask" data-away={askAway || undefined}>
          <IconSparkle size={17} />
          <span>Ask</span>
        </Link>
      ) : null}
    </div>
  );
}
