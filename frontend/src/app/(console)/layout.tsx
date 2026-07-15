"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Sidebar } from "@/components/chrome/Sidebar";
import { TopBar } from "@/components/chrome/TopBar";
import { Loading } from "@/components/ui/Loading";
import { useAuth } from "@/lib/auth";

/** Auth guard + Vercel-style app shell: persistent sidebar + top bar with
 *  breadcrumbs, and a keyed content region that fades on route change so
 *  navigation always feels intentional. */
export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const { apiKey, principal, ready } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (ready && !apiKey) router.replace("/login");
  }, [ready, apiKey, router]);

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
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="mx-auto w-full max-w-[1240px] flex-1 px-10 py-9">
          <div key={pathname} className="page-enter">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
