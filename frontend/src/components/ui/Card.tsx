/** Vercel card chrome: white surface, 8px radius, stacked-shadow elevation
 *  ladder + inset hairline (never a single heavy drop). */

type Elevation = 1 | 2 | 3 | 4;

const SHADOW: Record<Elevation, string> = {
  1: "shadow-[var(--shadow-1)]",
  2: "shadow-[var(--shadow-2)]",
  3: "shadow-[var(--shadow-3)]",
  4: "shadow-[var(--shadow-4)]",
};

export function Card({
  elevation = 1,
  className = "",
  children,
  ...rest
}: React.HTMLAttributes<HTMLDivElement> & { elevation?: Elevation }) {
  return (
    <div
      className={`rounded-lg bg-canvas ${SHADOW[elevation]} ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  title,
  eyebrow,
  action,
}: {
  title?: React.ReactNode;
  eyebrow?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-hairline px-5 py-3.5">
      <div className="min-w-0">
        {eyebrow ? <div className="t-eyebrow mb-0.5">{eyebrow}</div> : null}
        {title ? <div className="t-body-sm font-medium text-ink">{title}</div> : null}
      </div>
      {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
    </div>
  );
}

export function CardBody({
  className = "",
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return <div className={`px-5 py-4 ${className}`}>{children}</div>;
}
