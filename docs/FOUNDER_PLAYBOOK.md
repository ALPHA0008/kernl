# Kernl — Founder Strategy & Execution Playbook

**Prepared:** 2026-07-23 · **Analyst artifact, not plan-of-record** (binding strategy: `Kernel_arc.md` + `Product_summit.md`; market model: `MARKET_VALIDATION.md`, same date, which this playbook builds on rather than repeats).
**Standard:** board-level; every external statistic cited; internal numbers labeled **[fact] / [assumption] / [estimate] / [opinion]**.

---

## 1. Executive Summary

Kernl has shipped a genuinely differentiated V1 — a deterministic, replay-gated, cryptographically signed Decision Ledger — into a market whose timing is nearly perfect (EU AI Act high-risk enforcement lands 2026-08-02; Gartner projects 40% of enterprise apps embedding agents by end-2026). What it does not have: a customer, a price, a team, or proof that anyone pays for *neutral* decision governance. The next 90 days therefore have exactly one job: **convert companies currently deploying AI support agents into 3–5 shadow-mode design partners and extract one quantified ROI number.** Everything in this playbook — product priorities, outreach lists, metrics, fundraising sequencing — is subordinated to that job.

**Operating verdict:** Execute the design-partner sprint before any fundraise; apply to YC in parallel (the profile fits); do not build anything new except what removes friction from shadow-mode adoption.

---

## 2. Startup Overview (Phase 1)

| Dimension | Status | Label |
|---|---|---|
| Vision | "Institutional Computing" — the policy plane of the agentic economy; warrants as the authority primitive | [fact] (Product_summit.md) |
| Product today | V1 Decision Ledger: policy IR, deterministic evaluator, hash-chained ledger, escalation→adjudication→precedent, replay-gated publish, Ed25519 signing, console; deployed Railway+Vercel, production-verified 2026-07-22 | [fact] |
| Core tech / AI posture | Zero LLM on the enforce path (deterministic, differential-tested vs Rust port); LLM only proposes drafts | [fact] |
| Target user / buyer | Support/RevOps ops lead (user); VP CX / VP RevOps / CFO (economic buyer) | [fact ICP] / [assumption buyer] |
| Traction | 0 customers, 0 revenue, 0 of 3 design partners | [fact] |
| Team | Solo founder (P. Abhijith), technical | [fact] |
| Funding | Bootstrapped; infra on trial tiers | [fact] |
| Pricing | None defined | [fact — gap] |
| Geography | English-first, US/EU target | [assumption] |

**Missing info that binds this plan:** founder runway and full-time status; willingness to do 20+ sales conversations/month; visa/relocation constraints for YC. Flagged where relevant.

---

## 3. Market Validation (Phase 2 — summary; full model in MARKET_VALIDATION.md)

- **Wedge TAM (bottom-up):** ~28K global ICP companies × $25K ACV ≈ **$700M** (range $430–960M); cross-validated within 30% of a top-down 8–12% slice of decision management ($6.7–8.1B 2025 → $17.2–17.9B 2030, 16.6–20.7% CAGR — [Mordor](https://www.mordorintelligence.com/industry-reports/management-decision-market), [TBRC](https://www.thebusinessresearchcompany.com/report/decision-management-global-market-report)).
- **Expansion TAM:** $3–6B (multi-domain policy plane + enterprise), inheriting AI-governance CAGR of 36–51% ([MarketsandMarkets](https://www.marketsandmarkets.com/Market-Reports/ai-governance-market-176187291.html), [NextMSC](https://www.nextmsc.com/report/ai-governance-market-3562)).
- **SAM:** ~6,200 companies ≈ **$156M** after language/vendor-trust/ops-owner filters.
- **SOM:** Y1 $25–100K · Y3 $0.9–3.2M · Y5 $7–30M ARR (conservative→base).
- **Value-theory check** [estimate]: a 600-person B2B company processing ~2,000 refund/credit/discount decisions/yr with 3–5% inconsistency leakage on a $150 mean decision loses $9–15K/yr directly, plus audit-prep labor (~$10–20K) plus agent-rollout risk. A $18–30K price captures <50% of created value — defensible, but must be *proven* at a design partner.

**Next steps:** validate ACV and leakage math at partners №1–3; revisit SAM filters after 20 discovery calls.

---

## 4. Customer & ICP Analysis (Phase 3)

**Primary ICP (land):** B2B SaaS / subscription / B2B e-commerce, 200–2,000 employees, $20M–$400M revenue, US/EU, Zendesk or Intercom stack, **actively piloting an AI support agent (Decagon, Intercom Fin, Sierra, Forethought)**, support org 10–100 seats, has a named Support-Ops or RevOps owner. Budget authority: $15–50K at VP level. Buying maturity: mid — used to buying ops tooling, never bought "decision governance."

**Secondary ICP:** fintech-adjacent mid-market (billing disputes, credit terms, collections) — smaller population, *direct* EU AI Act pull, higher compliance budget.

**Expansion ICP (Y2+):** 2,000+ employee enterprises entering agent deployment with internal-audit mandates; agent-platform vendors themselves (OEM/partner).

### Buying committee & personas

| Role | Title | Cares about | Objection to expect | Win them with |
|---|---|---|---|---|
| Champion / user | Support Ops Manager, RevOps Manager | Consistency, fewer escalation fights, policy change without breakage | "I don't have time to write policies" | Extraction-assisted authoring; <5 min/policy; shadow mode = zero workflow change |
| Decision maker | VP Support / VP CX | Team efficiency, agent-rollout safety, CSAT | "Is this another dashboard nobody opens?" | Replay report on *their* history; leakage number |
| Economic buyer | CFO / VP Finance | Refund leakage, audit cost, control evidence | "Why isn't this a Zendesk feature?" | Neutral ledger ≠ vendor self-attestation; quarterly-close artifact |
| Technical buyer | Eng lead / IT | Integration surface, security, data residency | "Another vendor with our data?" | API-first, deterministic, no LLM on decisions, SOC2 roadmap |
| Procurement | (only >$30K) | Terms, vendor risk | Pre-seed vendor risk | Land under $30K to stay below procurement gravity [opinion] |

**Jobs-to-be-done:** Functional — decide consistently, prove what policy authorized what, change policy safely, bound agent authority. Emotional — stop being blamed for "wrong" refunds; confidence during audits. Social — look like the operator who made AI adoption safe.

**Customer journey friction points:** Evaluation (no live sandbox with *their* data → fix with shadow connector); Onboarding (policy authoring → extraction + grounding UX exists, measure the 5-min DoD); Activation (define as ≥90% of one domain in shadow within 30 days); Expansion (second domain = the NRR engine).

**Next steps:** write the one-page design-partner offer; instrument activation timing from day one.

---

## 5–6. Industry Research (Phase 4 — delta since MARKET_VALIDATION.md)

All macro findings carry over (agent adoption, EU AI Act 2026-08-02, Colorado June 2026, OWASP Agentic Top 10, Microsoft Agent Governance Toolkit). One addition for GTM: the buyer communities are organized and reachable — [RevOps Co-op](https://www.revopscoop.com/) (15K+ Slack members), [CX Accelerator](https://www.cxaccelerator.com/community) (virtual CX practitioner Slack), [ElevateCX](https://www.elevatecx.co) (CX-leadership Slack + conferences), plus Support Driven (the long-running support-ops community and its Expo events) **[established knowledge — verify current size before budgeting]**. White space confirmed: no player owns "neutral, replayable decision ledger for agent-era ops."

---

## 7. Competitive Landscape (Phase 5 — carried from MARKET_VALIDATION.md §10)

Squeeze structure: execution-plane vendors bundling self-attested governance above (Sierra $15B/$150M ARR, Decagon $4.5B — [CMSWire](https://www.cmswire.com/customer-experience/sierra-raises-950m-at-15b-valuation-eyes-transformation-beyond-customer-support/), [Bloomberg](https://www.bloomberg.com/news/articles/2026-01-28/ai-customer-support-startup-decagon-valued-at-4-5-billion)); free enforcement below ([Microsoft AGT, MIT-licensed](https://opensource.microsoft.com/blog/2026/04/02/introducing-the-agent-governance-toolkit-open-source-runtime-security-for-ai-agents/)); Taktile ($79M raised — [Taktile](https://taktile.com/articles/taktile-raises-54m-series-b)) validating the "decision platform for experts" pattern in FS; the *real* incumbent is macros + spreadsheets + memory.

**Positioning sentence to use everywhere:** *"Sierra and Decagon are the agents doing the work. Kernl is the neutral system of record proving what policy authorized it — the audit layer no agent vendor can credibly provide for itself."*

**Gap analysis → exploit:** (1) neutrality (structural conflict for agent vendors); (2) replay-CI ergonomics (nobody has "blast radius before publish" for ops policy); (3) mid-market price point (BRMS incumbents can't go there); (4) evidence-grounded citations (unique constitutional discipline).

---

## 8. Product Strategy (Phase 6)

### Build Immediately (unblocks design partners; ~next 60 days)
1. **Zendesk/Intercom shadow connector** — ingest real historical + live decisions without asking teams to change behavior. *This is the single highest-leverage build:* shadow mode is the arc's own adoption plan, and today the only inflow is API/console. **Priority P0.** [opinion, high confidence]
2. **ROI/leakage report** — from shadowed history: inconsistency rate, estimated leakage $, policy-conflict count. This is the artifact that converts WTP from theory to number. **P0.**
3. **Agent-webhook gateway (thin)** — accept decision requests from Decagon/Fin-style webhooks so an AI agent's refund flows through Kernl *before* execution. Rides the wave; small surface. **P1.**
4. **Design-partner packaging** — pricing page (even "design partner program — $500/mo, 6-mo lock, white-glove"), security one-pager, DPA template. **P1.**

### Build Later (post-partners / post-seed)
- Ledger-range replay (already planned-deferred in V1) — when partners have history worth replaying
- Credit-terms/collections domain pack — Y2, rides direct EU AI Act Annex III pull
- SOC2 Type I → II, SSO/SAML — when first enterprise conversation demands it
- Slack notifications for escalations; approvals-in-Slack — activation polish
- `<details>` motion polish and remaining design plans (frontend/plans/) — cosmetic

### Never Build (reaffirming the arc + new)
- Workflow/execution engine (Kernl authorizes, never executes — constitutional)
- Chat-as-product; blockchain; universal ontology; autonomous policy self-modification
- A general BRMS to chase IBM/FICO upmarket; an authZ engine to chase Oso/Cerbos — different buyer, commodity layer
- Model-risk/AI-bias tooling (Credo's lane; different buyer and motion)

**PMF indicators to instrument now:** shadow-activation ≤30 days; ≥1 policy change decided via replay per partner per quarter; weekly active adjudicators; % decisions escalated (should fall as precedent accrues); time-to-author-policy (<5 min DoD).

---

## 9. Moat Analysis (Phase 7)

| Moat | Today | At scale | Investor weight | How to strengthen |
|---|---|---|---|---|
| **Data (corpus)** | None | **Strongest** — outcome-linked decision history is unreplicable without the years (arc's own thesis) | High | Every design partner = corpus seed; never lose a ledger |
| **Switching costs** | Low | **Strong** — leaving = abandoning audit history + precedent ("constitutional switching costs") | High | Make the ledger the audit artifact of record ASAP |
| Workflow | Weak | Medium — replay-gated publishing becomes the team's change-management ritual | Medium | Ship the Slack surface; make replay reports shareable |
| Distribution / ecosystem | None | Medium — agent-vendor partnerships; later the IR/protocol standard | High if protocol lands | Partner with №2–5 agent vendors who *need* a neutral audit story |
| Network effects | None | Late-game (kernel-to-kernel protocol, V6+) | Discount for now | Don't pitch it as near-term |
| Brand / community | None | Medium ("CI for your policy" category language) | Medium | Own the phrase through content |
| Regulatory | Indirect | Medium — grows if Annex III domains ship | Rising | Credit-domain pack in Y2 |
| AI moat | Deliberately none | None (determinism IS the differentiation) | Neutral | Keep the enforce path LLM-free; it's the trust story |

**Honest read:** today's only moat is execution quality; the durable moats (corpus, switching costs) are **earned per-customer**, which is precisely why the design-partner sprint is existential. Investors will value corpus + switching costs + timing; they will discount protocol/network talk until Series A+. [opinion]

---

## 10. Business Model Review (Phase 8)

**Recommended pricing architecture** [assumption, to be tested]:
- **Design Partner** (now): $0–500/mo, 6-month term, case-study rights, roadmap input. Goal = proof, not revenue.
- **Team** (post-proof): **$1,500/mo (~$18K ACV)** — 1 domain, 3 seats, ledger + replay + escalations.
- **Growth**: **$2,900/mo (~$35K ACV)** — 3 domains, 10 seats, agent gateway, exports/API.
- **Enterprise** (Y2): $75K+ — SSO, SOC2, private region, custom retention, signed-bundle verification endpoint.
- Meter on **domains + seats**, not per-decision (wedge volumes too low to meter; per-decision pricing punishes adoption). [opinion]

**Unit economics targets vs benchmarks:** Gross margin ~85% (no LLM inference on decisions — structural COGS edge). Mid-market CAC payback benchmark is **14–18 months** ([CalcMastery](https://www.calcmastery.com/benchmarks/cac-payback-benchmarks-saas/)); founder-led motion should beat it (target ≤12). NRR: median B2B SaaS is ~82–101% depending on cut ([Rockingweb 2025](https://www.rockingweb.com.au/saas-metrics-benchmark-report-2025/), [SaaS Mag](https://www.saasmag.com/saas-capital-efficiency-metrics/)) — target **105% Y1 → 115% at scale** via second-domain expansion; treat 115% as upper-decile ambition, not a default. Churn target <10% logo (ledger lock-in should deliver this or the thesis is wrong).

---

## 11. Financial Model (Phase 9)

**Cost anchors** [estimate]: infra <$200/mo through Y1 (deterministic serving is cheap — real advantage); founding engineer $60–90K (remote/India) or $160–200K (US); founder living cost = the actual runway constraint (unknown — flag).

| Scenario | Funding | Team by mid-2027 | End-2027 ARR | End-2028 ARR | Burn multiple |
|---|---|---|---|---|---|
| Conservative (bootstrap) | $0 | 1 | $40–80K | $150–300K | n/a (near-zero burn) |
| **Base** | $500K–1.5M pre-seed/seed H2-2026 (post-partners or YC) | 3 (founder + eng + fractional GTM) | $150–300K | $0.8–1.5M | ≤2.0 |
| Aggressive | $2M seed + YC | 5 | $400–600K | $2.5M+ | ≤1.5 |

Seed-stage capital-efficiency benchmark: 2.5–3.4× ([SaaS Mag](https://www.saasmag.com/saas-capital-efficiency-metrics/)). Runway rule: raise for 24 months; assume the first $1M ARR takes ~2× longer than planned. [opinion]

---

## 12. GTM Strategy (Phase 10)

**Sequence (do not parallelize prematurely):**
1. **Founder-led design-partner sales (now → Q4-26).** Only motion that works at 0→1 for trust products. Target: companies *visibly deploying AI support agents*.
2. **Lighthouse audit story (Q1-27).** One partner's finance team relies on the ledger in a close/SOC2 cycle → the WTP artifact.
3. **Agent-vendor partnerships (Q1–Q3-27).** Mid-tier vendors (Forethought, Ada, smaller Decagon rivals) need neutral audit to win compliance-sensitive deals; Kernl = their governance answer. OEM/referral. *Do not pitch Sierra — they'll bundle.* [opinion]
4. **Content/community flywheel (start now, cheap).** Own "CI for your refund policy" + "who authorized that refund?" in the support-ops communities.
5. **PLG free tier (post-seed only).** Free shadow-ledger for <500 decisions/mo — an instrumented top-of-funnel, not a business model yet.
- **Not now:** enterprise outbound, paid acquisition, marketplaces, open-sourcing the evaluator (Microsoft AGT already commoditized enforcement; open-sourcing yours adds nothing and arms copycats [opinion]).

---

## 13. Customer Acquisition Blueprint (Phase 11)

| Channel | Why | Cost | Difficulty | ROI expectation |
|---|---|---|---|---|
| **Decagon/Fin/Sierra public case studies + job posts mentioning those tools** → prospect list | Companies already past the "should agents act?" decision — your exact trigger event | $0 + scraping time | Low | **Highest** — this is the list; build it today |
| [RevOps Co-op](https://www.revopscoop.com/) (15K+ Slack) | RevOps buyers discuss tooling openly; AMA/office-hours culture | Free | Low | High for discovery calls |
| Support Driven + [CX Accelerator](https://www.cxaccelerator.com/community) + [ElevateCX](https://www.elevatecx.co) Slacks | Support-ops champions live here; ElevateCX runs leadership conferences | Free–$ | Low | High (champion-building) |
| LinkedIn (founder posts + DM) | VP Support/RevOps are active; "agent just refunded $X with no trail" content lands | Time | Medium | Medium-High |
| Conferences: ElevateCX events, Support Driven Expo, SaaStr (RevOps track), Zendesk Relate | Concentrated ICP; sponsor only after seed | $500–5K attend | Medium | Medium (relationship seeding) |
| Podcasts/newsletters in CX-ops niche | Cheap authority; hosts want the "AI agents + governance" angle now | Time | Low | Medium, compounding |
| Reddit r/CustomerSuccess, r/ecommerce (ops threads) | Occasional high-intent threads | Free | Low | Low-Medium |
| Cold email (Apollo/Clay-built list off the case-study scrape) | Scalable once messaging is proven in communities | ~$100–300/mo tools | Medium | Medium until proof, then High |

---

## 14. Outreach Strategy (Phase 12)

**Who:** (1) Director/Head of Support Operations; (2) VP Customer Experience/Support; (3) VP RevOps; (4) CFO only *after* champion exists. Seniority sweet spot: Director/VP at 200–2,000-person B2B — has the pain, can sign <$30K.

**Trigger-based cold email (the only cold motion to run):**

> **Subject:** your Decagon rollout — who signs off on the refunds?
> Hi {Name} — saw {Company} is using {agent vendor} for support. Quick question the auditors will eventually ask: when the agent issues a refund, what's the record of *which policy authorized it*?
> We built Kernl — a decision ledger that shadows your existing refund/discount decisions (no workflow change), shows you where policy is inconsistent, and gives every agent action a signed, replayable audit trail.
> We're taking 5 design partners this quarter — free, white-glove, you keep the leakage report either way. Worth 20 minutes?

Sequence: Day 0 email → Day 3 LinkedIn connect w/ note → Day 7 value follow-up (1-pager or 90-sec demo video) → Day 14 breakup email ("closing the design-partner cohort — should I keep a seat?"). 4 touches, stop.

**Warm paths:** ElevateCX/RevOps Co-op relationships → intro requests; YC network if accepted (single biggest warm-intro unlock for this profile); agent-vendor CSMs (they need their customers to pass audits).

---

## 15. Distribution Strategy (Phase 13)

**Loops to build (ranked):** (1) *Replay-report loop* — every partner's policy change produces a shareable blast-radius report; finance forwards it; recipients ask what produced it. Product-native, start now. (2) *Content loop* — weekly artifact from real (anonymized) decision-governance findings → LinkedIn + communities → discovery calls. (3) *Audit loop* — auditors/fractional CFOs who see the ledger once start recommending it (Y2 channel). (4) *AI-SEO* — publish the definitional pages ("decision ledger", "AI agent audit trail", "replay testing for policy") now; LLM answer-engines are the new front door and the category has no incumbent content. Paid: none until seed + proven message.

---

## 16. KPI Dashboard (Phase 14)

| Metric | Formula | Benchmark | Kernl target (12 mo) | Cadence |
|---|---|---|---|---|
| Design partners active | count | n/a | **3–5 by Oct-26** | Weekly |
| Shadow activation | days from signup → ≥90% of one domain shadowed | n/a | ≤30 days | Per partner |
| Replay-decided changes | changes gated by replay report | n/a | ≥1/partner/quarter | Monthly |
| Policy authoring time | median min/policy | n/a (arc DoD) | <5 min | Per cohort |
| Paying customers | count | n/a | 1–3 by Q1-27 | Monthly |
| ARR / MRR | Σ contracts | n/a | $25–100K by mid-27 | Monthly |
| ACV | ARR / customers | mid-market $15–100K band | $18–30K | Quarterly |
| CAC payback | CAC / (ACV × GM) | 14–18 mo mid-market ([CalcMastery](https://www.calcmastery.com/benchmarks/cac-payback-benchmarks-saas/)) | ≤12 mo | Quarterly |
| NRR | (start ARR + expansion − churn) / start | ~82–101% B2B medians ([Rockingweb](https://www.rockingweb.com.au/saas-metrics-benchmark-report-2025/)) | ≥105% Y1 | Quarterly |
| Logo churn | churned / total | <10% good mid-market | <10% | Quarterly |
| Gross margin | (rev − COGS)/rev | 75–85% SaaS | ≥85% | Quarterly |
| Burn multiple | net burn / net new ARR | ≤2 good seed ([SaaS Mag](https://www.saasmag.com/saas-capital-efficiency-metrics/)) | ≤2 post-raise | Monthly |
| Win rate (quals→closed) | closed / qualified | ~20–30% typical | ≥25% design-partner phase | Monthly |
| Weekly active adjudicators | users resolving/reviewing per week | n/a | 100% of partner ops leads | Weekly |
| Rule of 40 | growth% + FCF% | ≥40 at scale | n/a until >$1M ARR | — |

---

## 17. Fundraising Readiness (Phase 15)

**Today:** not seed-ready (no traction, solo). **YC-ready: yes** — technical solo founder, shipped product of unusual quality, category-defining vision, perfect timing narrative; this is the archetype YC funds. **Apply to the next batch immediately** (applications are rolling; batches ~quarterly). [opinion, high confidence]

**Best profile:** pre-seed/seed infra- and agent-thesis funds and angels (dev-tools/fintech-infra operators, support-tech founders, compliance/audit executives). Avoid growth-stage tourists.

**Raise sequencing:** design partners first → raise **$750K–1.5M pre-seed** on 3–5 partners + activation data (Q4-26/Q1-27) → seed ($2.5–4M) after $250K+ ARR with NRR evidence.

**Milestones before institutional pitch:** 3–5 partners, ≥1 paying, one replay-decided policy change *by a customer*, quantified leakage number, founding hire identified.

**The story that raises:** "Agents are executing money decisions today. Sierra attests to itself. Auditors won't accept that forever — Aug 2, 2026 starts the clock. We're the neutral ledger, we're live, and here's a customer's audit artifact." Every element exists except the last — which is the point of the next 90 days.

---

## 18. Risk Register (Phase 16)

| Risk | P | I | Mitigation |
|---|---|---|---|
| WTP never materializes (governance stays a feature, not a line item) | Med | Critical | Leakage-ROI framing; CFO artifact; pivot lever = agent-vendor OEM |
| Bundled vendor governance accepted by auditors | Med | High | Land the neutrality story with finance/audit *now*; partner with mid-tier vendors |
| Agent-project churn (Gartner: 40% canceled by 2027) | High | Med | Anchor value on *human* decision governance too (works without agents) |
| Solo-founder stall / burnout | Med | Critical | YC/peer structure; founding hire post-raise; ruthless scope discipline (already demonstrated) |
| Authoring friction kills activation | Med | High | Measure 5-min DoD; invest in extraction UX before any new surface |
| Microsoft/hyperscaler expands from enforcement into lifecycle | Low-Med | High | Speed + corpus + neutrality; don't compete on engine |
| Security incident (a *governance* vendor breach is fatal) | Low | Critical | SOC2 path early; minimal data ingestion in shadow mode; pen test pre-enterprise |
| Regulatory wedge mismatch (refunds ≠ Annex III) | Certain | Med | Credit-domain pack Y2; sell EU AI Act as adjacent pull, never claim compliance magic |
| Platform dependence (Zendesk/Intercom API terms) | Low | Med | Multi-connector roadmap; API-first core |

---

## 19. Execution Roadmap (Phase 17)

### Today
- [ ] Commit pending repo work; tag v1.0. *(P0, founder, → clean baseline)*
- [ ] Start the target list: scrape Decagon/Intercom-Fin/Sierra case studies + job posts → 25 named companies w/ Support-Ops contacts. *(P0 → the pipeline)*

### Next 7 Days
- [ ] Design-partner one-pager + 90-sec demo video (seeded rivanly tenant). *(P0)*
- [ ] Join RevOps Co-op, CX Accelerator, ElevateCX, Support Driven; contribute (no pitching) daily 20 min. *(P0)*
- [ ] Send first 20 trigger-based sequences. *(P0, KPI: ≥5 replies, ≥3 calls)*
- [ ] Draft YC application + 1-min video. *(P1)*
- [ ] Publish "Who authorized that refund?" essay (LinkedIn + communities). *(P1)*

### Next 30 Days
- [ ] 10+ discovery calls; iterate pitch weekly. *(KPI: 2 signed shadow partners)*
- [ ] **Ship Zendesk shadow connector MVP.** *(P0 — the activation unlock)*
- [ ] Ship leakage/ROI report v0. *(P0)*
- [ ] Submit YC. *(P1)*

### Next 90 Days
- [ ] 3–5 partners; ≥1 domain at ≥90% shadow (arc criterion). 
- [ ] First replay-decided policy change by a customer; capture the artifact.
- [ ] First leakage number → pricing test ($1.5K/mo) on partner №4–5.
- [ ] Agent-webhook gateway if ≥1 partner runs an AI agent.
- [ ] Begin pre-seed conversations with the evidence pack.

### Next 6 Months
- [ ] 1–3 paying; $25–75K ARR; lighthouse audit story documented.
- [ ] Close pre-seed ($750K–1.5M) or YC batch; founding engineer hired.
- [ ] SOC2 Type I started; security one-pager shipped.

### Next 12 Months
- [ ] 10–20 customers; $250–500K ARR; NRR ≥105%; churn <10%.
- [ ] Second domain shipped (credit-terms/collections — Annex III adjacency).
- [ ] 1 agent-vendor partnership LOI; seed round open with Taktile-comp narrative.

---

## 20. Founder Playbook (Phase 18)

- **Don't build:** anything on the Never list; a second product surface before 3 partners; open-source theater; conference sponsorships; SOC2 Type II prematurely. The codebase is *done enough* — the constraint is now entirely commercial. [opinion, high confidence]
- **Founders waste time on:** polishing product for imaginary users (you are past this — stop), fundraising before evidence, "partnership" calls with giants (Sierra will take the meeting and learn your roadmap), building community before having anything to say weekly.
- **Blind spots:** (1) engineering excellence can become avoidance of sales — your calendar, not your repo, is the metric now; (2) the buyer cares about *blame and audits*, not determinism — sell outcomes, keep the architecture as proof; (3) solo-founder pitch discount is real — a founding hire narrative matters almost as much as traction.
- **Biggest leverage points:** the Decagon-customer prospect list (trigger-perfect); the Aug-2 EU date as an outreach hook (10 days away — use it this week); YC application (network unlock); the replay report as a self-distributing artifact.
- **Fastest path to first revenue:** design partner №4–5 converting at $1.5K/mo after seeing their own leakage number — Q4-2026 is realistic.
- **Fastest path to 100 customers / $1M ARR:** doesn't exist through founder-led alone — it runs through the agent-vendor OEM channel + seed-funded 2-AE team, 2027-2028. Plan for it; don't force it early.

---

## 21. Investment Committee Verdict (Phase 19)

**Would Sequoia invest today?** No — seed bar requires traction + team. **After 5 partners, 1 paying, audit lighthouse?** Credible pre-seed/seed conversation, especially with agent-thesis partners. **Would YC fund this?** **Plausibly yes, now** — the profile (technical solo founder, shipped exceptional product, huge timely vision) is their sweet spot; the interview risk is the solo-GTM question. 

**$10M ARR?** Achievable in the wedge + early expansion by ~2030 with funding. **$100M ARR?** Only via the multi-domain policy plane + enterprise + partner channel (~1,300 × $75K); real but unproven path. **Unicorn?** Requires the agent-economy bet paying off AND the neutral-ledger position winning vs. bundled governance — possible, not probable from today. **IPO?** Too speculative to price. **Acquisition target?** Strong — natural buyers: agent platforms needing neutrality (ironically), ServiceNow/Salesforce/Zendesk, audit/GRC majors (Workiva/Diligent), or Microsoft post-AGT. A $50–300M outcome is a *modal* success scenario; the fund-returner is the protocol path. [opinion]

| Dimension | /10 | One-line why |
|---|---|---|
| Market | 8 | Wedge modest, expansion huge, timing exceptional |
| Team | 4 | Solo; elite technical execution, zero commercial evidence |
| Product | 8 | Production-verified, differentiated, constitutionally disciplined — far above stage |
| Timing | 9 | Agent wave + Aug-2 enforcement + category legitimization, simultaneously |
| GTM | 4 | Correct plan, entirely unexecuted |
| Moat | 6 | Earned-per-customer (corpus/switching); thin at entry |
| Financial potential | 7 | 85%+ GM, structural COGS edge, credible $10M path |
| Defensibility | 6 | Neutrality is structural; everything else must be built |
| Execution difficulty | 8 | Trust-selling + authoring adoption + solo = hard mode |
| VC attractiveness | 6 | Pre-seed: yes profile; seed: not yet |
| **Overall opportunity** | **7** | **Right product, right moment, one unproven motion between here and fundable** |

---

## 22. Key Assumptions Register

1. 28K ICP / $25K ACV / $700M wedge TAM (MARKET_VALIDATION.md §4) — moderate confidence
2. Shadow-mode removes adoption friction enough for 30-day activation — untested
3. Leakage 3–5% of decision value at ICP scale — untested, partner №1 must measure
4. Neutral audit becomes a requirement (not vendor self-attestation) — supported by financial-controls precedent, unproven for agents
5. Agent-economy macro bet (arc's own load-bearing assumption) — currently supported by all signals
6. Founder can run 20+ commercial conversations/month alongside product — unknown, the personal constraint
7. NRR 105–115% via domain expansion — modeled, not observed (B2B medians are 82–101%)

## 23. Sources

Carried from MARKET_VALIDATION.md §18 (market sizes, competitors, regulation, Gartner, mid-market counts, Zendesk ACV), plus: [CalcMastery — CAC payback benchmarks](https://www.calcmastery.com/benchmarks/cac-payback-benchmarks-saas/) · [Rockingweb — SaaS Metrics Benchmarks 2025](https://www.rockingweb.com.au/saas-metrics-benchmark-report-2025/) · [SaaS Mag — capital efficiency](https://www.saasmag.com/saas-capital-efficiency-metrics/) · [Pavilion — B2B benchmarks](https://www.joinpavilion.com/resource/b2b-saas-performance-benchmarks) · [RevOps Co-op](https://www.revopscoop.com/) · [CX Accelerator](https://www.cxaccelerator.com/community) · [ElevateCX](https://www.elevatecx.co).

## 24. Appendix — The One-Slide Version

> **Kernl** — the neutral decision ledger for the agent economy.
> AI agents are already issuing refunds (Sierra: $150M ARR; Decagon: 70–75% autonomous). Nobody can prove which policy authorized them. EU enforcement starts Aug 2, 2026.
> Kernl shadows your existing decisions, shows the leakage, and gives every decision — human or agent — a signed, replayable audit trail. Policy changes ship like code: replay-tested, versioned, reversible.
> Live in production. Taking 5 design partners this quarter.
