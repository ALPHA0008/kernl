export function JsonView({ value, maxHeight }: { value: unknown; maxHeight?: string }) {
  return (
    <pre
      className="overflow-auto rounded-md border border-hairline bg-canvas-soft px-3.5 py-3 font-mono text-[13px] leading-relaxed text-body"
      style={maxHeight ? { maxHeight } : undefined}
    >
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
