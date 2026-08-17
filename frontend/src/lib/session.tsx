"use client";

/**
 * Session context — locked 49.2, 52.3, S-1.
 *
 * The permission array is fetched with the session and never cached across
 * sessions (52.3). It carries no authority: authority is resolved server-side on
 * every request (S-1), so this array can only ever be a rendering hint.
 */

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
    try {
      await api.logout();
    } finally {
      setIdentity(null);
    }
  }, []);

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
