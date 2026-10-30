"use client";

/**
 * Session context — locked 49.2, 52.3, S-1.
 *
 * The permission array is fetched with the session and never cached across
 * sessions (52.3). It carries no authority: authority is resolved server-side on
 * every request (S-1), so this array can only ever be a rendering hint.
 */

import { useRouter } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError, SESSION_ENDED, api } from "./api";
import type { SessionIdentity } from "./types";

interface SessionState {
  identity: SessionIdentity | null;
  loading: boolean;
  /** Presentation-only permission check (52.1 r3). */
  can: (permission: string) => boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [identity, setIdentity] = useState<SessionIdentity | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setIdentity(await api.session());
    } catch (error) {
      // A 401 is the normal signed-out state, not an error worth showing
      // (47.1.1 r2: a revoked or expired session is indistinguishable from
      // being signed out).
      if (!(error instanceof ApiError && error.isUnauthenticated)) throw error;
      setIdentity(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // QA-027: a session that ends mid-work goes to sign-in, and comes back to this page
  useEffect(() => {
    if (!identity) return;
    const ended = () => {
      setIdentity(null);
      router.replace(loginPath());
    };
    window.addEventListener(SESSION_ENDED, ended);
    return () => window.removeEventListener(SESSION_ENDED, ended);
  }, [identity, router]);

  const signOut = useCallback(async () => {
    /*
     * Signing out ALWAYS lands on /login — added 2026-09-01 (owner).
     *
     * It used to only clear the identity. `WorkspaceShell` has its own
     * signed-out guard, so /dashboard redirected and looked correct; the older
     * Chrome-based pages (/reviews, /contracts, /admin, /audit,
     * /configuration) simply stayed put and rendered "You are signed out",
     * which reads as a broken page rather than a completed action. Verified
     * with a browser: /dashboard → /login, /reviews → /reviews.
     *
     * The redirect lives HERE rather than in a second shell guard because
     * signing out is one act with one outcome, and duplicating the rule per
     * shell is how the two diverged in the first place.
     *
     * `replace`, not `push`: Back must not return to a page that is now
     * signed out. And it runs in `finally` — a logout whose request failed has
     * still discarded the local session, so leaving the user on an
     * authenticated-looking page would be the worse outcome. The server-side
     * session is revoked by the endpoint; the cookie is cleared by its
     * response (including the AM-36 token, which cannot be revoked any other
     * way).
     */
    try {
      await api.logout();
    } finally {
      setIdentity(null);
      router.replace("/login");
    }
  }, [router]);

  const value = useMemo<SessionState>(
    () => ({
      identity,
      loading,
      can: (permission: string) => identity?.permissions.includes(permission) ?? false,
      refresh,
      signOut,
    }),
    [identity, loading, refresh, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside SessionProvider");
  return context;
}

/**
 * Whether this caller is permitted to see internal legal position.
 *
 * Used only to decide whether to render a *section heading* for it. Never used to
 * decide whether a field is present — that is determined by the field's presence
 * in the response, because the server omits rather than nulls (49.7 r4, 52.4).
 * Asking this question instead of checking presence would reintroduce exactly the
 * placeholder Step 52.4 forbids.
 */
/** Sign-in, returning to where the reader was. */
export function loginPath(): string {
  const here = window.location.pathname + window.location.search;
  return here.startsWith("/login") ? "/login" : `/login?next=${encodeURIComponent(here)}`;
}

/** Where to go after sign-in: only a path on this site, never another origin. */
export function safeNext(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") && !raw.startsWith("/\\")
    ? raw : "/dashboard";
}

export function useSeesLegalPosition(): boolean {
  const { can } = useSession();
  return can("legal_position.view");
}
