"use client";

/** API-key auth held client-side. The key lives in sessionStorage (gone when
 *  the tab closes); the server enforces roles on every endpoint regardless —
 *  the principal here only gates what the UI offers. */

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getMe } from "./api";
import type { Principal } from "./types";

const STORAGE_KEY = "kernl.api_key";

interface AuthState {
  apiKey: string | null;
  principal: Principal | null;
  /** true until sessionStorage has been consulted (avoids redirect flicker) */
  ready: boolean;
  login: (key: string) => Promise<Principal>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [principal, setPrincipal] = useState<Principal | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (!stored) {
      // defer to a microtask so the setState is not synchronous in the effect
      queueMicrotask(() => {
        if (!cancelled) setReady(true);
      });
      return () => {
        cancelled = true;
      };
    }
    getMe(stored)
      .then((me) => {
        if (cancelled) return;
        setApiKey(stored);
        setPrincipal(me);
      })
      .catch(() => sessionStorage.removeItem(STORAGE_KEY))
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (key: string) => {
    const me = await getMe(key); // throws ApiError(401) on a bad key
    sessionStorage.setItem(STORAGE_KEY, key);
    setApiKey(key);
    setPrincipal(me);
    return me;
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY);
    setApiKey(null);
    setPrincipal(null);
  }, []);

  return (
    <AuthContext.Provider value={{ apiKey, principal, ready, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Convenience for authenticated screens: non-null key + principal.
 *  Only call under the console layout guard. */
export function useSession(): { apiKey: string; principal: Principal } {
  const { apiKey, principal } = useAuth();
  if (!apiKey || !principal) throw new Error("useSession outside authenticated area");
  return { apiKey, principal };
}
