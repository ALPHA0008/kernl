"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Sidebar } from "@/components/chrome/Sidebar";
import { TopBar } from "@/components/chrome/TopBar";
import { Loading } from "@/components/ui/Loading";
import { useAuth } from "@/lib/auth";

/** Auth guard + Vercel-style app shell: persistent sidebar + top bar with
 *  breadcrumbs, and a keyed content region that fades on route change so
 *  navigation always feels intentional.
 *
 *  Responsive: at md+ the sidebar is a fixed rail. Below md it becomes an
 *  off-canvas drawer the layout owns (opened by the TopBar hamburger, closed
 *  on route change, scrim click, or Escape) so the console is usable on a
 *  phone instead of clipping content behind a permanent rail. */
export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const { apiKey, principal, ready } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    if (ready && !apiKey) router.replace("/login");
  }, [ready, apiKey, router]);

  // Escape closes the drawer; lock body scroll while it's open.
  useEffect(() => {
    if (!mobileNavOpen) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMobileNavOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [mobileNavOpen]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loading label="Checking session…" />
      </div>
    );
  }
  if (!apiKey || !principal) return null;

  return (
    <div className="flex min-h-screen bg-canvas-soft">
      <Sidebar mobileOpen={mobileNavOpen} onMobileClose={() => setMobileNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onMenuClick={() => setMobileNavOpen(true)} />
        <main className="mx-auto w-full max-w-[1240px] flex-1 px-5 py-6 sm:px-8 lg:px-10 lg:py-9">
          <div key={pathname} className="page-enter">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
