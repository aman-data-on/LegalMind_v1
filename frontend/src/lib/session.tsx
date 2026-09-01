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

import { ApiError, api } from "./api";
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
export function useSeesLegalPosition(): boolean {
  const { can } = useSession();
  return can("legal_position.view");
}

/**
 * Wrap API calls to handle session expiry (401 errors) globally. If a 401 occurs,
 * attempt to refresh the session. If that fails, redirect to login. This ensures
 * expired sessions are caught immediately and users are prompted to sign in again.
 *
 * Usage: `const result = await useApiError(() => api.someEndpoint())`
 */
export function useApiError(): <T,>(fn: () => Promise<T>) => Promise<T> {
  const { refresh } = useSession();
  const router = useRouter();

  return useCallback(
    async <T,>(fn: () => Promise<T>): Promise<T> => {
      try {
        return await fn();
      } catch (error) {
        // If it's a 401 (session expired), try to refresh and redirect to login
        if (error instanceof ApiError && error.isUnauthenticated) {
          try {
            await refresh();
            // If refresh succeeds, the session is restored - retry the operation
            return await fn();
          } catch {
            // Refresh failed - redirect to login page
            router.replace("/login");
            throw error;
          }
        }
        // For all other errors, re-throw to let the caller handle
        throw error;
      }
    },
    [refresh, router],
  );
}
