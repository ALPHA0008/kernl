export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2.5 py-8 text-sm text-mute">
      <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-[1.5px] border-hairline-strong border-t-transparent" />
      {label}
    </div>
  );
}
