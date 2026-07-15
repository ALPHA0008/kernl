"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { breadcrumbs } from "./nav-config";

/** Sticky top bar: breadcrumb trail (the back-navigation spine) on the left,
 *  tenant + role menu on the right. Every screen gets a path home. */
export function TopBar() {
  const pathname = usePathname();
  const { principal, logout } = useAuth();
  const router = useRouter();
  const crumbs = breadcrumbs(pathname);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-hairline bg-[color:var(--color-canvas)]/80 px-6 backdrop-blur">
      {/* Context trail: tenant → section → [detail]. The tenant root is real
          context (not a repeat of the page H1), so a top-level page reads
          "rivanly-inc / Evaluate" here while the page owns the big title. */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-[13px]">
        {principal ? (
          <>
            <span className="font-mono text-body">{principal.company_id}</span>
            <span className="text-hairline-strong">/</span>
          </>
        ) : null}
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1;
          return (
            <span key={i} className="flex items-center gap-1.5">
              {c.href && !last ? (
                <Link href={c.href} className="text-body transition-colors hover:text-ink">
                  {c.label}
                </Link>
              ) : (
                <span className={last ? "font-medium text-ink" : "text-body"}>{c.label}</span>
              )}
              {!last ? <span className="text-hairline-strong">/</span> : null}
            </span>
          );
        })}
      </nav>

      {/* tenant menu */}
      {principal ? (
        <div ref={menuRef} className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="flex items-center gap-2 rounded-[6px] px-2 py-1.5 transition-colors hover:bg-canvas-soft"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ink text-[11px] font-semibold uppercase text-on-primary">
              {principal.company_id.slice(0, 2)}
            </span>
            <span className="hidden text-sm text-ink sm:block">{principal.company_id}</span>
            <svg width="12" height="12" viewBox="0 0 12 12" className="text-mute">
              <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.2" fill="none" />
            </svg>
          </button>

          {menuOpen ? (
            <div className="page-enter absolute right-0 top-11 w-56 rounded-lg bg-canvas p-1.5 shadow-[var(--shadow-5)]">
              <div className="px-3 py-2">
                <div className="font-mono text-xs text-ink">{principal.company_id}</div>
                <div className="mt-0.5 text-xs text-mute">
                  role: <span className="text-body">{principal.role}</span>
                </div>
              </div>
              <div className="my-1 h-px bg-hairline" />
              <Link
                href="/settings"
                onClick={() => setMenuOpen(false)}
                className="block rounded-[6px] px-3 py-1.5 text-sm text-body transition-colors hover:bg-canvas-soft hover:text-ink"
              >
                Settings
              </Link>
              <button
                type="button"
                onClick={() => {
                  logout();
                  router.replace("/login");
                }}
                className="block w-full rounded-[6px] px-3 py-1.5 text-left text-sm text-body transition-colors hover:bg-error-soft hover:text-error-deep"
              >
                Sign out
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </header>
  );
}
