"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { useRouter } from "next/navigation";
import { API_BASE } from "@/lib/api";

type AuthConfig = {
  supabase_url: string;
  supabase_anon_key: string;
};

type AuthUser = {
  id: string;
  email: string;
};

type AuthContextType = {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

let cachedConfig: AuthConfig | null = null;

async function getAuthConfig(): Promise<AuthConfig> {
  if (cachedConfig) return cachedConfig;
  const res = await fetch(`${API_BASE}/auth/config`);
  cachedConfig = await res.json();
  return cachedConfig!;
}

export async function loginWithSupabase(email: string, password: string) {
  const config = await getAuthConfig();
  const res = await fetch(`${config.supabase_url}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: config.supabase_anon_key,
    },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error((await res.json()).error_description || "Login failed");
  const data = await res.json();
  sessionStorage.setItem("kernl_token", data.access_token);
  sessionStorage.setItem("kernl_user", JSON.stringify({ id: data.user.id, email: data.user.email }));
  return data;
}

export async function registerWithSupabase(email: string, password: string) {
  const config = await getAuthConfig();
  const res = await fetch(`${config.supabase_url}/auth/v1/signup`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: config.supabase_anon_key,
    },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error((await res.json()).msg || "Registration failed");
  return res.json();
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const savedToken = sessionStorage.getItem("kernl_token");
    const savedUser = sessionStorage.getItem("kernl_user");
    if (savedToken && savedUser) {
      setToken(savedToken);
      setUser(JSON.parse(savedUser));
    }
    setLoading(false);
  }, []);

  const login = async (email: string, password: string) => {
    const data = await loginWithSupabase(email, password);
    setToken(data.access_token);
    setUser({ id: data.user.id, email: data.user.email });
  };

  const register = async (email: string, password: string) => {
    await registerWithSupabase(email, password);
  };

  const logout = () => {
    sessionStorage.removeItem("kernl_token");
    sessionStorage.removeItem("kernl_user");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function useProtectedAuth() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!auth.loading && !auth.user) {
      router.push("/login");
    }
  }, [auth.loading, auth.user, router]);

  return auth;
}
