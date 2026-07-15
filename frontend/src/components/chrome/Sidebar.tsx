"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/ui/Icon";
import { Logo } from "@/components/ui/Logo";
import { useAuth } from "@/lib/auth";
import { NAV_GROUPS } from "./nav-config";

export function Sidebar() {
  const pathname = usePathname();
  const { principal } = useAuth();
  const isOwner = principal?.role === "owner";

  return (
    <aside className="sticky top-0 flex h-screen w-[248px] shrink-0 flex-col border-r border-hairline bg-canvas">
      {/* wordmark — h-14 to align its bottom rule with the top bar's */}
      <div className="flex h-14 items-center border-b border-hairline px-5">
        <Link href="/evaluate" className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-[7px] bg-ink">
            <Logo size={17} className="text-on-primary" />
          </span>
          <span className="text-[16px] font-semibold tracking-tight text-ink">Kernl</span>
        </Link>
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
  );
}
