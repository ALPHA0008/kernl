"use client";

import { usePathname, useRouter } from "next/navigation";

const NAV_ITEMS = [
  {
    id: "home",
    label: "Dashboard",
    path: "/",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="2" y="2" width="7" height="8" rx="1.5" />
        <rect x="11" y="2" width="7" height="5" rx="1.5" />
        <rect x="2" y="12" width="7" height="6" rx="1.5" />
        <rect x="11" y="9" width="7" height="9" rx="1.5" />
      </svg>
    ),
  },
  {
    id: "onboarding",
    label: "Onboarding",
    path: "/onboarding",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M10 2v16M2 10h16" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "skills",
    label: "Skills",
    path: "/skills",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M3 4h14M3 8h10M3 12h12M3 16h8" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "demo",
    label: "Query",
    path: "/demo",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="10" cy="10" r="7" />
        <path d="M10 6v4l3 2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const isActive = (path: string) => {
    if (path === "/") return pathname === "/";
    return pathname.startsWith(path);
  };

  return (
    <aside
      className="fixed left-0 top-0 bottom-0 z-40 flex flex-col items-center py-5 border-r"
      style={{
        width: "var(--sidebar-width)",
        background: "var(--bg-surface)",
        borderColor: "var(--border)",
      }}
    >
      {/* Logo */}
      <button
        onClick={() => router.push("/")}
        className="mb-8 flex items-center justify-center w-9 h-9 rounded-lg transition-all hover:scale-105"
        style={{
          background: "var(--primary-ghost)",
          color: "var(--primary)",
        }}
        title="Kernl"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path
            d="M3 2h3v14H3V2zm5 0h2l5 7-5 7H8l5-7-5-7z"
            fill="currentColor"
          />
        </svg>
      </button>

      {/* Nav Items */}
      <nav className="flex-1 flex flex-col gap-1 w-full px-2">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.path);
          return (
            <button
              key={item.id}
              onClick={() => router.push(item.path)}
              title={item.label}
              className="relative flex items-center justify-center w-10 h-10 mx-auto rounded-lg transition-all duration-200 group"
              style={{
                color: active ? "var(--primary)" : "var(--text-muted)",
                background: active ? "var(--primary-ghost)" : "transparent",
              }}
            >
              {/* Active indicator */}
              {active && (
                <span
                  className="absolute left-0 top-2 bottom-2 w-[2px] rounded-full"
                  style={{ background: "var(--primary)" }}
                />
              )}
              {item.icon}

              {/* Tooltip */}
              <span
                className="absolute left-full ml-3 px-2 py-1 rounded text-xs font-medium whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity"
                style={{
                  background: "var(--bg-elevated)",
                  color: "var(--text-primary)",
                  border: "1px solid var(--border-hover)",
                }}
              >
                {item.label}
              </span>
            </button>
          );
        })}
      </nav>

      {/* Bottom accent dot */}
      <div
        className="w-2 h-2 rounded-full"
        style={{ background: "var(--primary-dim)", opacity: 0.5 }}
      />
    </aside>
  );
}
