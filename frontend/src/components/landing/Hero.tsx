import { LedgerStrip } from "./LedgerStrip";
import { CTA_DEMO, CTA_PARTNER } from "./cta";

/** Bottom-weighted hero (the Ship lesson: the air above the headline is the
 *  drama). Top ~55% is quiet with a single restrained aurora wash — the one
 *  atmospheric moment the whole page is allowed. The bottom block carries the
 *  eyebrow, the thesis headline, a 20-word sub, both CTAs, and the live ledger
 *  strip. First-viewport memory test: "the system of record for AI decisions." */
export function Hero() {
  return (
    <section className="relative flex min-h-[100dvh] flex-col justify-end overflow-hidden">
      {/* the single atmospheric moment: brand aurora, heavily restrained, top-anchored */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 left-1/2 h-[560px] w-[1000px] -translate-x-1/2 opacity-[0.13] blur-3xl"
        style={{
          background:
            "conic-gradient(from 180deg at 50% 50%, #007cf0, #00dfd8, #7928ca, #ff0080, #ff4d4d, #f9cb28, #007cf0)",
        }}
      />
      {/* faint measure grid baseline under the strip, subject-appropriate (a ledger has ruled lines) */}
      <div className="relative mx-auto w-full max-w-[1200px] px-6 pb-16 pt-28 sm:px-8 sm:pb-20 lg:px-10">
        <p className="load-rise t-eyebrow" style={{ animationDelay: "40ms" }}>
          The decision ledger for enterprise AI
        </p>
        <h1 className="load-rise t-display-hero mt-5 max-w-[16ch] text-ink" style={{ animationDelay: "120ms" }}>
          Every decision, on the record.
        </h1>
        <p
          className="load-rise mt-6 max-w-[62ch] text-[18px] leading-relaxed text-body sm:text-lg"
          style={{ animationDelay: "200ms" }}
        >
          Kernl turns operating policy into deterministic code. Every decision a human or AI
          agent makes is authorized, signed, and replayable.
        </p>
        <div
          className="load-rise mt-8 flex flex-col gap-3 sm:flex-row sm:items-center"
          style={{ animationDelay: "280ms" }}
        >
          <a
            href={CTA_PARTNER}
            className="inline-flex h-11 items-center justify-center rounded-[7px] bg-ink px-5 text-[16px] font-medium text-on-primary shadow-[0_1px_2px_rgba(0,0,0,0.14)] transition-colors hover:bg-[color:var(--color-ink-hover)]"
          >
            Become a design partner
          </a>
          <a
            href={CTA_DEMO}
            className="inline-flex h-11 items-center justify-center rounded-[7px] bg-canvas px-5 text-[16px] font-medium text-ink shadow-[var(--shadow-1)] transition-colors hover:bg-canvas-soft"
          >
            Request a demo
          </a>
        </div>

        <div className="load-rise max-w-2xl" style={{ animationDelay: "380ms" }}>
          <LedgerStrip />
        </div>
      </div>
    </section>
  );
}
