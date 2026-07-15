/** Empty state — a calm, centered panel with a comfortable text measure and an
 *  optional next action. The inner block is width-constrained (not flex-starved)
 *  so copy reads as sentences, never a one-word-per-line ribbon. */
export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="rounded-lg bg-canvas-soft px-6 py-16 shadow-[var(--shadow-1)]">
      <div className="mx-auto max-w-sm text-center">
        <p className="t-body-md font-medium text-ink">{title}</p>
        {hint ? <p className="mt-2 text-sm leading-relaxed text-body">{hint}</p> : null}
        {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
      </div>
    </div>
  );
}
