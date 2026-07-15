/** Compact inline control bar for list screens — filters left, actions right.
 *  Replaces the full-width stacked selects that made Ledger feel unfinished. */
export function Toolbar({
  children,
  actions,
}: {
  children?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      {children}
      {actions ? <div className="ml-auto flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/** A table wrapped in the standard elevated surface with horizontal scroll. */
export function TableSurface({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-lg bg-canvas shadow-[var(--shadow-1)]">
      {children}
    </div>
  );
}
