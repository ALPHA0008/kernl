"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/ui/Icon";
import { Logo } from "@/components/ui/Logo";
import { useAuth } from "@/lib/auth";
import { NAV_GROUPS } from "./nav-config";

export function Sidebar({
  mobileOpen = false,
  onMobileClose,
}: {
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}) {
  const pathname = usePathname();
  const { principal } = useAuth();
  const isOwner = principal?.role === "owner";

  return (
    <>
      {/* Scrim: only below md, only when the drawer is open. Tapping it closes. */}
      <div
        className={`fixed inset-0 z-40 bg-ink/30 backdrop-blur-[1px] transition-opacity duration-200 md:hidden ${
          mobileOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        aria-hidden
        onClick={onMobileClose}
      />
      <aside
        className={`flex h-screen w-[248px] shrink-0 flex-col border-r border-hairline bg-canvas
          max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-50 max-md:transition-transform max-md:duration-200 max-md:ease-out
          md:sticky md:top-0 ${
            mobileOpen ? "max-md:translate-x-0 max-md:shadow-[var(--shadow-5)]" : "max-md:-translate-x-full"
          }`}
      >
      {/* wordmark — h-14 to align its bottom rule with the top bar's */}
      <div className="flex h-14 items-center justify-between border-b border-hairline px-5">
        <Link href="/evaluate" className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-[7px] bg-ink">
            <Logo size={17} className="text-on-primary" />
          </span>
          <span className="text-[16px] font-semibold tracking-tight text-ink">Kernl</span>
        </Link>
        {/* close affordance, drawer only */}
        <button
          type="button"
          onClick={onMobileClose}
          className="-mr-1.5 flex h-8 w-8 items-center justify-center rounded-md text-mute transition-colors hover:bg-canvas-soft hover:text-ink md:hidden"
          aria-label="Close navigation"
        >
          <svg width="16" height="16" viewBox="0 0 16 16"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg>
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-4 pt-2" aria-label="Console">
        {NAV_GROUPS.map((group) => {
          const items = group.items.filter((i) => !i.ownerOnly || isOwner);
          if (items.length === 0) return null;
          return (
            <div key={group.label} className="mb-6 last:mb-0">
              <div className="t-eyebrow px-3 pb-2">{group.label}</div>
              <div className="space-y-0.5">
                {items.map((item) => {
                  const active =
                    pathname === item.href || pathname.startsWith(`${item.href}/`);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onMobileClose}
                      className={`group relative flex items-center gap-2.5 rounded-md px-3 py-[7px] text-[13px] transition-colors ${
                        active
                          ? "bg-canvas-soft font-medium text-ink"
                          : "text-body hover:bg-canvas-soft hover:text-ink"
                      }`}
                    >
                      {active ? (
                        <span className="absolute left-0 top-1/2 h-[14px] w-[2px] -translate-y-1/2 rounded-full bg-ink" />
                      ) : null}
                      <Icon
                        name={item.icon}
                        size={15}
                        className={active ? "text-ink" : "text-mute group-hover:text-ink"}
                      />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      <div className="mt-auto flex items-center gap-2 border-t border-hairline px-5 py-3.5">
        <span className="h-1.5 w-1.5 rounded-full bg-[color:var(--color-approve)]" />
        <span className="font-mono text-[11px] text-mute">kernl-evaluator/1.0.0</span>
      </div>
      </aside>
    </>
  );
}
