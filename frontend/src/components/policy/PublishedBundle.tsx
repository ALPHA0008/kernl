"use client";

import { useMemo, useState } from "react";
import { PolicyCard } from "@/components/policy/PolicyCard";
import { Input } from "@/components/ui/Input";
import type { Policy } from "@/lib/types";

const KIND_DOT: Record<string, string> = {
  approve: "bg-approve",
  deny: "bg-deny",
  escalate: "bg-escalate",
  route: "bg-route",
};

/** The published bundle, presented as an inspectable constitution: policies
 *  grouped by workflow into collapsible sections, a live filter, and a summary
 *  strip. Turns a flat wall of 22 rows into a navigable hierarchy. */
export function PublishedBundle({
  policies,
  workflowCount,
}: {
  policies: Policy[];
  workflowCount: number;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return policies;
    return policies.filter(
      (p) =>
        p.id.toLowerCase().includes(q) ||
        p.workflow.toLowerCase().includes(q) ||
        p.effect.action.toLowerCase().includes(q) ||
        p.rationale.toLowerCase().includes(q),
    );
  }, [policies, query]);

  const groups = useMemo(() => {
    const map = new Map<string, Policy[]>();
    for (const p of filtered) {
      (map.get(p.workflow) ?? map.set(p.workflow, []).get(p.workflow)!).push(p);
    }
    return [...map.entries()]
      .map(([workflow, ps]) => ({
        workflow,
        policies: [...ps].sort((a, b) => b.priority - a.priority),
      }))
      .sort((a, b) => a.workflow.localeCompare(b.workflow));
  }, [filtered]);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-2 text-sm">
          <span className="text-ink">
            <span className="font-medium tabular-nums">{policies.length}</span> policies
          </span>
          <span className="text-hairline-strong">·</span>
          <span className="text-body">
            <span className="font-medium tabular-nums">{workflowCount}</span> workflows
          </span>
        </div>
        <div className="relative w-full max-w-xs">
          <svg width="14" height="14" viewBox="0 0 14 14" className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-mute">
            <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.3" fill="none" />
            <path d="M9 9l3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter policies…"
            className="!h-9 pl-8"
          />
        </div>
      </div>

      {groups.length === 0 ? (
        <p className="rounded-lg bg-canvas-soft px-5 py-8 text-center text-sm text-mute shadow-[var(--shadow-1)]">
          No policies match “{query}”.
        </p>
      ) : (
        <div className="space-y-6">
          {groups.map((g) => {
            const kinds = [...new Set(g.policies.map((p) => p.effect.kind))];
            return (
              <section key={g.workflow}>
                <div className="mb-2 flex items-center gap-2.5 px-1">
                  <h3 className="font-mono text-[13px] font-medium text-ink">{g.workflow}</h3>
                  <span className="rounded-full bg-canvas-soft px-2 py-0.5 text-[11px] tabular-nums text-body shadow-[var(--shadow-1)]">
                    {g.policies.length}
                  </span>
                  <span className="flex items-center gap-1">
                    {kinds.map((k) => (
                      <span key={k} className={`h-1.5 w-1.5 rounded-full ${KIND_DOT[k] ?? "bg-mute"}`} title={k} />
                    ))}
                  </span>
                </div>
                <div className="space-y-1.5">
                  {g.policies.map((p) => (
                    <PolicyCard key={p.id} policy={p} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
