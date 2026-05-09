"use client";

import { useAuth } from "@/lib/auth";
import { useRouter, usePathname } from "next/navigation";

function getPageTitle(pathname: string): string {
  if (pathname === "/") return "Dashboard";
  if (pathname.startsWith("/onboarding")) return "Onboarding";
  if (pathname.startsWith("/skills")) return "Skills Explorer";
  if (pathname.startsWith("/demo")) return "Query Agent";
  if (pathname.startsWith("/compile")) return "Compile Pipeline";
  return "Kernl";
}

export default function TopBar() {
  const { user, logout, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const pageTitle = getPageTitle(pathname);

  return (
    <header
      className="sticky top-0 z-30 flex items-center justify-between h-14 px-6 border-b"
      style={{
        background: "rgba(10, 15, 20, 0.85)",
        backdropFilter: "blur(12px)",
        borderColor: "var(--border)",
      }}
    >
      {/* Left: Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <span style={{ color: "var(--text-muted)" }}>Kernl</span>
        <span style={{ color: "var(--text-muted)" }}>/</span>
        <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>
          {pageTitle}
        </span>
      </div>

      {/* Right: User */}
      <div className="flex items-center gap-4">
        {!loading && user ? (
          <>
            <span
              className="text-xs font-mono"
              style={{ color: "var(--text-muted)" }}
            >
              {user.email}
            </span>
            <button
              onClick={() => {
                logout();
                router.push("/login");
              }}
              className="text-xs font-medium px-3 py-1.5 rounded-md transition-colors"
              style={{
                color: "var(--text-secondary)",
                border: "1px solid var(--border)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--border-hover)";
                e.currentTarget.style.color = "var(--text-primary)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.color = "var(--text-secondary)";
              }}
            >
              Sign Out
            </button>
          </>
        ) : !loading ? (
          <div className="flex items-center gap-2">
            <button
              onClick={() => router.push("/login")}
              className="text-xs font-medium px-3 py-1.5 rounded-md transition-colors"
              style={{ color: "var(--text-secondary)" }}
            >
              Sign In
            </button>
            <button
              onClick={() => router.push("/register")}
              className="btn-primary"
              style={{ fontSize: "12px", padding: "6px 14px" }}
            >
              Sign Up
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
