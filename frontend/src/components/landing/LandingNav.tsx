import Link from "next/link";
import { Logo } from "@/components/ui/Logo";
import { CTA_PARTNER } from "./cta";

const ANCHORS = [
  { href: "#how", label: "How it works" },
  { href: "#replay", label: "Replay" },
  { href: "#ledger", label: "The ledger" },
  { href: "#program", label: "Partner program" },
];

/** Sticky landing nav. Wordmark + anchors + Sign in + the persistent primary
 *  CTA. On mobile the anchors drop (the page is one story; scrolling is the nav)
 *  and only wordmark + CTA remain. */
export function LandingNav() {
  return (
    <header className="sticky top-0 z-50 border-b border-hairline bg-[color:var(--color-canvas)]/80 backdrop-blur">
      <nav
        aria-label="Primary"
        className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-6 sm:px-8 lg:px-10"
      >
        <Link href="/" className="flex items-center gap-2.5" aria-label="Kernl home">
          <span className="flex h-7 w-7 items-center justify-center rounded-[7px] bg-ink">
            <Logo size={17} className="text-on-primary" />
          </span>
          <span className="text-[16px] font-semibold tracking-tight text-ink">Kernl</span>
        </Link>

        <div className="hidden items-center gap-7 md:flex">
          {ANCHORS.map((a) => (
            <a
              key={a.href}
              href={a.href}
              className="text-[13px] text-body transition-colors hover:text-ink"
            >
              {a.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-3 sm:gap-5">
          <Link
            href="/login"
            className="hidden text-[13px] text-body transition-colors hover:text-ink sm:block"
          >
            Sign in
          </Link>
          <a
            href={CTA_PARTNER}
            className="inline-flex h-9 items-center justify-center rounded-[6px] bg-ink px-3.5 text-[13px] font-medium leading-none text-on-primary shadow-[0_1px_2px_rgba(0,0,0,0.12)] transition-colors hover:bg-[color:var(--color-ink-hover)]"
          >
            Become a design partner
          </a>
        </div>
      </nav>
    </header>
  );
}
