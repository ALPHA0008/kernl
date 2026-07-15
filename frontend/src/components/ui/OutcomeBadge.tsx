const STYLES: Record<string, string> = {
  approve: "bg-approve-bg text-approve",
  deny: "bg-deny-bg text-deny",
  escalate: "bg-escalate-bg text-escalate",
  route: "bg-route-bg text-route",
};

const DOT: Record<string, string> = {
  approve: "bg-approve",
  deny: "bg-deny",
  escalate: "bg-escalate",
  route: "bg-route",
};

export function OutcomeBadge({ kind, size = "md" }: { kind: string; size?: "md" | "lg" }) {
  const cls = STYLES[kind] ?? "bg-canvas-soft text-body";
  const pad = size === "lg" ? "px-2.5 py-1 text-[13px]" : "px-2 py-0.5 text-xs";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${pad} ${cls}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[kind] ?? "bg-mute"}`} />
      {kind}
    </span>
  );
}
