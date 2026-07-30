import { Hero } from "@/components/landing/Hero";
import { LandingNav } from "@/components/landing/LandingNav";
import { LandingFooter } from "@/components/landing/LandingFooter";
import { SectionShell } from "@/components/landing/SectionShell";
import { FlowDiagram } from "@/components/landing/FlowDiagram";
import { PolicyCard } from "@/components/landing/PolicyCard";
import { Terminal } from "@/components/landing/Terminal";
import { ReplayArtifact } from "@/components/landing/ReplayArtifact";
import { ChainVisual } from "@/components/landing/ChainVisual";
import { Faq, FAQ_ITEMS } from "@/components/landing/Faq";
import { CTA_DEMO, CTA_PARTNER } from "@/components/landing/cta";
import { SITE_URL } from "@/lib/site";

/* ── local section helpers (the story lives in one file; artifacts are imported) ── */

function SectionHead({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="max-w-[46ch]">
      {eyebrow ? <p className="t-eyebrow mb-4">{eyebrow}</p> : null}
      <h2 className="t-display-section text-ink text-balance">{title}</h2>
      {children ? <p className="mt-5 max-w-[62ch] text-[18px] leading-relaxed text-body">{children}</p> : null}
    </div>
  );
}

const Content = ({ children }: { children: React.ReactNode }) => (
  <div className="mx-auto w-full max-w-[1200px] px-6 sm:px-8 lg:pl-20 lg:pr-10">{children}</div>
);

export default function LandingPage() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": `${SITE_URL}/#org`,
        name: "Kernl",
        url: SITE_URL,
        description: "The decision ledger for enterprise AI.",
      },
      {
        "@type": "WebSite",
        "@id": `${SITE_URL}/#website`,
        url: SITE_URL,
        name: "Kernl",
        inLanguage: "en-US",
        publisher: { "@id": `${SITE_URL}/#org` },
      },
      {
        "@type": "SoftwareApplication",
        // Anchored into the same graph as Organization/WebSite: without an @id
        // and a publisher edge this node floats free and search engines cannot
        // tell it describes the same entity as the rest of the page.
        "@id": `${SITE_URL}/#software`,
        url: SITE_URL,
        name: "Kernl",
        applicationCategory: "BusinessApplication",
        operatingSystem: "Web",
        publisher: { "@id": `${SITE_URL}/#org` },
        description:
          "Kernl turns operating policy into deterministic, versioned code and records every decision as a signed, append-only, replay-tested ledger entry for humans and AI agents.",
        offers: { "@type": "Offer", price: "0", priceCurrency: "USD", description: "Design partner program" },
      },
      {
        "@type": "FAQPage",
        mainEntity: FAQ_ITEMS.map((f) => ({
          "@type": "Question",
          name: f.q,
          acceptedAnswer: { "@type": "Answer", text: f.a },
        })),
      },
    ],
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[60] focus:rounded-md focus:bg-ink focus:px-3 focus:py-2 focus:text-sm focus:text-on-primary"
      >
        Skip to content
      </a>

      <LandingNav />

      <main id="main">
        <Hero />

        {/* the ledger spine runs down the narrative (each section draws its segment) */}
        <div className="relative">
          {/* 2 · Problem */}
          <SectionShell id="problem">
            <Content>
              <SectionHead title="An AI agent just refunded $4,000. Which policy authorized it?">
                For most companies the honest answer is nobody knows. Policy lives in macros,
                spreadsheets, and someone&rsquo;s memory. Agents act in milliseconds.
              </SectionHead>
              <dl className="mt-12 max-w-3xl divide-y divide-hairline border-y border-hairline">
                {[
                  ["AGENTS ACT", "AI agents already resolve most support conversations at leading companies. Refunds included."],
                  ["ADOPTION COMPOUNDS", "Gartner expects 40% of enterprise apps to embed task-specific agents by the end of 2026."],
                  ["THE LAW ARRIVED", "EU AI Act high-risk enforcement began August 2, 2026. Regulators now ask for decision trails, not intentions."],
                ].map(([k, v]) => (
                  <div key={k} className="grid grid-cols-1 gap-1.5 py-5 sm:grid-cols-[200px_1fr] sm:gap-6">
                    <dt className="font-mono text-[12px] uppercase tracking-wide text-ink">{k}</dt>
                    <dd className="max-w-[56ch] text-[14px] leading-relaxed text-body">{v}</dd>
                  </div>
                ))}
              </dl>
            </Content>
          </SectionShell>

          {/* 3 · Why current answers fail */}
          <SectionShell id="why">
            <Content>
              <SectionHead title="Logs tell you what happened. Not what was allowed." />
              <ol className="group/list mt-12 max-w-3xl divide-y divide-hairline border-y border-hairline">
                {[
                  ["Vendor self-attestation.", "Your agent platform grades its own homework. A trail signed by the party being audited is testimony, not evidence."],
                  ["Prompts as policy.", "A system prompt cannot be versioned, diffed, tested, or cited when finance asks why."],
                  ["Logs without lineage.", "A log line records an outcome. It cannot prove which rule, which version, which authority produced it."],
                ].map(([t, b], i) => (
                  <li key={t} className="flex gap-5 py-6">
                    <span className="mt-0.5 font-mono text-[13px] text-mute">{String(i + 1).padStart(2, "0")}</span>
                    <div>
                      <h3 className="text-[18px] font-medium text-ink">{t}</h3>
                      <p className="mt-1.5 max-w-[58ch] text-[14px] leading-relaxed text-body">{b}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </Content>
          </SectionShell>

          {/* 4 · Introducing Kernl — centered diagram */}
          <SectionShell id="how" reveal={false}>
            <Content>
              <div className="reveal mx-auto max-w-[56ch] text-center">
                <h2 className="t-display-section text-ink text-balance">Kernl is the system of record for decisions.</h2>
                <p className="mx-auto mt-5 max-w-[60ch] text-[18px] leading-relaxed text-body">
                  Policy becomes code: typed, versioned, cited to its source. Decisions become ledger
                  entries: signed and append-only. Changes become replays: tested against history first.
                </p>
              </div>
              <div className="mt-12">
                <FlowDiagram />
              </div>
            </Content>
          </SectionShell>

          {/* 5 · How it works — three-primitive overview + the policy artifact */}
          <SectionShell reveal={false}>
            <Content>
              <div className="reveal">
                <SectionHead title="Three primitives. No magic.">
                  Everything downstream is a view of these three. Determinism, replay, and the audit
                  trail all fall out of getting them right.
                </SectionHead>
              </div>
              <div className="reveal mt-12 grid grid-cols-1 gap-x-12 gap-y-10 border-t border-hairline pt-10 sm:grid-cols-3">
                {[
                  ["01", "Policy as code", "Typed conditions, priorities, and override rules. Every rule cites its source document, byte for byte. No citation, no publish."],
                  ["02", "Deterministic decision", "Same facts, same policy, same answer. Zero LLM calls on the decision path. Ambiguity escalates to a human instead of guessing."],
                  ["03", "Append-only ledger", "Every decision becomes a signed, hash-chained entry. Change one byte and every hash after it breaks."],
                ].map(([n, t, b]) => (
                  <div key={n}>
                    <span className="font-mono text-[13px] text-mute">{n}</span>
                    <h3 className="mt-2 text-[18px] font-medium tracking-[-0.01em] text-ink">{t}</h3>
                    <p className="mt-2 text-[14px] leading-relaxed text-body">{b}</p>
                  </div>
                ))}
              </div>
              {/* the first primitive, made concrete */}
              <div className="reveal mt-14 max-w-md">
                <p className="mb-4 font-mono text-[12px] uppercase tracking-wide text-mute">A policy, in full</p>
                <PolicyCard />
              </div>
            </Content>
          </SectionShell>

          {/* 6 · Determinism — split text/terminal */}
          <SectionShell reveal={false}>
            <Content>
              <div className="grid grid-cols-1 items-center gap-10 lg:grid-cols-2 lg:gap-14">
                <div className="reveal">
                  <SectionHead title="Same facts. Same policy. Same answer.">
                    Probabilistic systems are impressive and unaccountable. Kernl keeps the model where it
                    belongs: proposing drafts and explaining outcomes. Never deciding.
                  </SectionHead>
                  <p className="mt-6 max-w-[52ch] text-[14px] leading-relaxed text-mute">
                    The evaluator is differential-tested against an independent Rust implementation.
                    Determinism here is not a promise. It is a test suite.
                  </p>
                </div>
                <div className="reveal">
                  <Terminal />
                </div>
              </div>
            </Content>
          </SectionShell>

          {/* 7 · Replay — centered artifact */}
          <SectionShell id="replay" reveal={false}>
            <Content>
              <div className="reveal mx-auto max-w-[52ch] text-center">
                <h2 className="t-display-section text-ink text-balance">Ship policy like you ship code.</h2>
                <p className="mx-auto mt-5 max-w-[58ch] text-[18px] leading-relaxed text-body">
                  Every change replays against your golden cases and decision history before it can
                  publish. See which past decisions flip. Acknowledge the blast radius, or don&rsquo;t ship.
                </p>
              </div>
              <div className="reveal mx-auto mt-12 max-w-3xl">
                <ReplayArtifact />
              </div>
            </Content>
          </SectionShell>

          {/* 8 · The ledger — stacked */}
          <SectionShell id="ledger" reveal={false}>
            <Content>
              <div className="reveal max-w-[52ch]">
                <SectionHead title="Append-only. Hash-chained. Signed.">
                  Append-only is enforced by the database, not by promise. Bundles are Ed25519-signed at
                  publish. Anyone can verify the chain without trusting us. That is the point.
                </SectionHead>
              </div>
              <div className="reveal mt-12 max-w-3xl">
                <ChainVisual />
              </div>
            </Content>
          </SectionShell>

          {/* 9 · Enterprise readiness — spec grid */}
          <SectionShell reveal={false}>
            <Content>
              <div className="reveal">
                <SectionHead eyebrow="INFRASTRUCTURE" title="Built like infrastructure, because it is." />
              </div>
              <dl className="reveal mt-12 grid grid-cols-1 gap-x-14 gap-y-0 sm:grid-cols-2">
                {[
                  ["Deterministic core", "Zero LLM calls on the decision path."],
                  ["Append-only ledger", "Enforced by a database trigger, not convention."],
                  ["Ed25519 signatures", "Verify any bundle independently of Kernl."],
                  ["Replay-gated publishing", "No policy change ships untested."],
                  ["Evidence-cited policy", "Every rule traces to its source document."],
                  ["API-first", "REST, tenant-isolated, role-scoped keys."],
                ].map(([t, b]) => (
                  <div key={t} className="flex items-baseline gap-4 border-b border-hairline py-5">
                    <dt className="w-44 shrink-0 font-mono text-[13px] text-ink">{t}</dt>
                    <dd className="text-[14px] leading-relaxed text-body">{b}</dd>
                  </div>
                ))}
              </dl>
            </Content>
          </SectionShell>

          {/* 10 · Design partner program */}
          <SectionShell id="program" reveal={false}>
            <Content>
              <div className="reveal max-w-[52ch]">
                <SectionHead eyebrow="DESIGN PARTNER PROGRAM" title="Five partners. Ninety days. Zero workflow change.">
                  We shadow your existing refund and credit decisions, read-only. We encode your policies
                  for you. You get the Leakage Report: what inconsistent decisions actually cost.
                </SectionHead>
              </div>
              <div className="reveal mt-12 grid grid-cols-1 gap-px overflow-hidden rounded-xl bg-hairline shadow-[var(--shadow-1)] sm:grid-cols-2">
                {[
                  {
                    h: "You get",
                    items: [
                      "Your policies encoded as cited, versioned code",
                      "The Leakage Report on your own decision history",
                      "A replay run on a real policy change",
                      "An audit-trail pack your finance team can hold",
                    ],
                  },
                  {
                    h: "We need",
                    items: [
                      "A read-only export from your help desk",
                      "One 45-minute call a week",
                      "Honest feedback",
                    ],
                  },
                ].map((col) => (
                  <div key={col.h} className="bg-canvas p-6 sm:p-8">
                    <h3 className="t-eyebrow mb-4">{col.h}</h3>
                    <ul className="space-y-3">
                      {col.items.map((it) => (
                        <li key={it} className="flex gap-2.5 text-[14px] leading-relaxed text-body">
                          <svg width="16" height="16" viewBox="0 0 16 16" className="mt-1 shrink-0 text-approve" aria-hidden>
                            <path d="M3.5 8.5l3 3 6-6" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                          {it}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
              <p className="reveal mt-6 max-w-[62ch] text-[14px] leading-relaxed text-mute">
                Free for the ninety days. If the report doesn&rsquo;t find more than the year-one price,
                we&rsquo;ll tell you so ourselves.
              </p>
              <div className="reveal mt-8">
                <a
                  href={CTA_PARTNER}
                  className="inline-flex h-11 items-center justify-center rounded-[7px] bg-ink px-5 text-[16px] font-medium text-on-primary shadow-[0_1px_2px_rgba(0,0,0,0.14)] transition-colors hover:bg-[color:var(--color-ink-hover)]"
                >
                  Become a design partner
                </a>
              </div>
            </Content>
          </SectionShell>

          {/* 11 · FAQ */}
          <SectionShell>
            <Content>
              <SectionHead title="Questions a careful buyer asks." />
              <Faq />
            </Content>
          </SectionShell>
        </div>

        {/* 12 · Close */}
        <section className="border-t border-hairline">
          <div className="mx-auto max-w-[1200px] px-6 py-28 text-center sm:px-8 lg:py-36">
            <h2 className="t-display-hero mx-auto max-w-[18ch] text-ink text-balance">
              The ledger starts when you do.
            </h2>
            <p className="mx-auto mt-6 max-w-[54ch] text-[18px] leading-relaxed text-body">
              Every decision before Kernl is unprovable history. Every decision after is on the record.
            </p>
            <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
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
          </div>
        </section>
      </main>

      <LandingFooter />
    </>
  );
}
