import Link from "next/link";

/** Explicit "return" affordance for detail screens — no dead ends. */
export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="mb-4 inline-flex items-center gap-1.5 text-sm text-body transition-colors hover:text-ink"
    >
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden>
        <path d="M8.5 3L4.5 7L8.5 11" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {label}
    </Link>
  );
}
