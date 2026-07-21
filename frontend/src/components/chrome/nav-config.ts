/** Single source of truth for navigation: section groups, labels, and the
 *  breadcrumb/label lookup used by the shell. Keeping it here means the
 *  sidebar, breadcrumbs, and page titles never drift apart. */

import type { IconName } from "@/components/ui/Icon";

export interface NavItem {
  href: string;
  label: string;
  icon: IconName;
  ownerOnly?: boolean;
  /** short description shown in the sidebar tooltip / command sense */
  hint?: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Operate",
    items: [
      { href: "/evaluate", label: "Evaluate", icon: "evaluate", hint: "Run a decision" },
      { href: "/ledger", label: "Ledger", icon: "ledger", hint: "Decision history" },
      { href: "/escalations", label: "Escalations", icon: "escalations", hint: "Adjudicate ambiguity" },
    ],
  },
  {
    label: "Govern",
    items: [
      { href: "/policies", label: "Policies", icon: "policies", hint: "The published bundle" },
      { href: "/replays", label: "Replay", icon: "replay", hint: "Blast radius before publish" },
    ],
  },
  {
    label: "Build",
    items: [
      { href: "/onboarding", label: "Onboarding", icon: "onboarding", ownerOnly: true, hint: "Docs → dashboard" },
      { href: "/sources", label: "Sources", icon: "sources", hint: "Uploaded documents" },
      { href: "/settings", label: "Settings", icon: "settings", hint: "Tenant & session" },
    ],
  },
];

const ALL_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

/** Human label for a top-level section path. */
export function sectionLabel(path: string): string {
  const seg = "/" + (path.split("/")[1] ?? "");
  return ALL_ITEMS.find((i) => i.href === seg)?.label ?? seg.replace("/", "");
}

/** Breadcrumb trail for a route. Detail routes append a short id crumb. */
export interface Crumb {
  label: string;
  href?: string;
}

/** Detail routes whose section is not itself a sidebar item map to a parent. */
const DETAIL_PARENT: Record<string, { href: string; label: string; kind: string }> = {
  decisions: { href: "/ledger", label: "Ledger", kind: "Decision" },
  escalations: { href: "/escalations", label: "Escalations", kind: "Escalation" },
  replays: { href: "/replays", label: "Replay", kind: "Run" },
  onboarding: { href: "/onboarding", label: "Onboarding", kind: "Draft" },
};

export function breadcrumbs(pathname: string): Crumb[] {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 0) return [];
  const section = "/" + parts[0];
  const isDetail = parts.length > 1;

  if (!isDetail) {
    const item = ALL_ITEMS.find((i) => i.href === section);
    return [{ label: item?.label ?? parts[0], href: section }];
  }

  const parent = DETAIL_PARENT[parts[0]] ?? {
    href: section,
    label: ALL_ITEMS.find((i) => i.href === section)?.label ?? parts[0],
    kind: "Detail",
  };
  const last = parts[parts.length - 1];
  const shortId = last.length > 10 ? `${last.slice(0, 8)}…` : last;
  return [
    { label: parent.label, href: parent.href },
    { label: `${parent.kind} ${shortId}` },
  ];
}

export { ALL_ITEMS };
