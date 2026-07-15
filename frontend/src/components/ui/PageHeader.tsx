/** Page header — the anchor of every screen.
 *  Vercel/Linear pattern: eyebrow → title → description as a full-width stack,
 *  actions pinned to the title's baseline, a hairline rule closing the band.
 *  The title row and description each get the FULL content width (the previous
 *  flex layout starved the description column, wrapping it one word per line). */
export function PageHeader({
  title,
  subtitle,
  eyebrow,
  children,
}: {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="mb-7 border-b border-hairline pb-5">
      {eyebrow ? <div className="t-eyebrow mb-1.5">{eyebrow}</div> : null}
      <div className="flex items-start justify-between gap-6">
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em] text-ink">
          {title}
        </h1>
        {children ? (
          <div className="flex shrink-0 items-center gap-2 pt-0.5">{children}</div>
        ) : null}
      </div>
      {subtitle ? (
        <p className="mt-2.5 max-w-2xl text-[15px] leading-relaxed text-body">{subtitle}</p>
      ) : null}
    </header>
  );
}
