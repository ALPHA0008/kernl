import Link from "next/link";
import { Logo } from "@/components/ui/Logo";
import { CONTACT_EMAIL } from "./cta";

export function LandingFooter() {
  return (
    <footer className="border-t border-hairline">
      <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-6 py-12 sm:flex-row sm:items-center sm:justify-between sm:px-8 lg:px-10">
        <div className="flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-[6px] bg-ink">
            <Logo size={14} className="text-on-primary" />
          </span>
          <span className="text-sm text-body">
            <span className="font-medium text-ink">Kernl</span> · The decision ledger for enterprise AI.
          </span>
        </div>
        <div className="flex items-center gap-6 text-[13px] text-body">
          <Link href="/login" className="transition-colors hover:text-ink">
            Sign in
          </Link>
          <a href={`mailto:${CONTACT_EMAIL}`} className="transition-colors hover:text-ink">
            Contact
          </a>
          <span className="text-mute">© 2026 Kernl</span>
        </div>
      </div>
    </footer>
  );
}
