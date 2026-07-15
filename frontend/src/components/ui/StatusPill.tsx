const STYLES: Record<string, string> = {
  // bundle lifecycle
  draft: "bg-canvas-soft text-body",
  published: "bg-approve-bg text-approve",
  superseded: "bg-canvas-soft text-mute",
  retired: "bg-canvas-soft text-mute",
  // escalations
  open: "bg-escalate-bg text-escalate",
  resolved: "bg-approve-bg text-approve",
  // misc
  active: "bg-ink text-on-primary",
};

export function StatusPill({ status }: { status: string }) {
  const cls = STYLES[status] ?? "bg-canvas-soft text-body";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}
