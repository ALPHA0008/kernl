"use client";

import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";

export default function NavBar() {
  const { user, logout, loading } = useAuth();
  const router = useRouter();

  return (
    <nav className="border-b border-gray-800 bg-surface/80 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
        <button
          onClick={() => router.push("/")}
          className="text-lg font-bold text-primary tracking-tight"
        >
          Kernl
        </button>
        <div className="flex items-center gap-4 text-sm">
          {!loading && user ? (
            <>
              <span className="text-text-secondary">{user.email}</span>
              <button
                onClick={() => { logout(); router.push("/login"); }}
                className="text-text-secondary hover:text-foreground"
              >
                Sign Out
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => router.push("/login")}
                className="text-text-secondary hover:text-foreground"
              >
                Sign In
              </button>
              <button
                onClick={() => router.push("/register")}
                className="bg-primary text-background font-bold px-4 py-1.5 text-xs hover:opacity-90"
              >
                Sign Up
              </button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
