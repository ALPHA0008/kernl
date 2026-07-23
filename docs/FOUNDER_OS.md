# Kernl Founder OS — The Weekly Operating System

**Prepared:** 2026-07-23 · Fifth and final doc in the series. Sources of truth: `MARKET_VALIDATION.md` (market), `FOUNDER_PLAYBOOK.md` (strategy/roadmap), `FOUNDER_BRAND_GTM.md` (brand/content), `DESIGN_PARTNER_PLAYBOOK.md` (sales motion). **This doc adds no new strategy — it is the rhythm that executes the other four.** Open it every Monday. If a conflict arises, the priority order is: partner commitments > sales floor > shipping > content > everything else.

---

## 1. The Ten Operating Principles (never violate)

1. **Calls before code.** Your demonstrated instinct is engineering; the company's constraint is commercial. When the calendar fights, the call wins.
2. **Five ICP conversations per week — the floor, not the target.** A week below floor is a red week no matter what shipped.
3. **Ship weekly, sell daily.** One user-visible improvement per week; outreach touches every working day.
4. **Learning velocity is the metric behind the metrics.** Every week must change at least one thing: the pitch, the product, or the plan. Log what changed (decision log). A week where nothing changed was wasted regardless of activity.
5. **The Friday scoreboard doesn't lie.** Real numbers, written down, every Friday, even (especially) when embarrassing.
6. **One niche, zero drift.** Agent accountability. Twelve months minimum (brand doc §3).
7. **Decisions get documented.** You run constitutional discipline in your codebase; run it in your company. One line per decision: date, what, why, revisit-when.
8. **Two 3-hour deep-work blocks are sacred.** Wednesday owns them. No calls, no Slack, no exceptions.
9. **Default to no.** The Ignore List (§9) is a commitment, not a suggestion.
10. **Health is infrastructure.** Solo founder = bus factor 1. Sleep ≥7h, 4 workouts/wk, one full day off. Burnout is the only competitor that beats you without shipping.

---

## 2. Time Allocation (design-partner stage, ~55h sustainable)

| Category | h/wk | % | Notes |
|---|---|---|---|
| Sales & partners (outreach, calls, demos, pilot ops, follow-ups) | 20 | 36% | The job. Protected first. |
| Product (connector, partner-driven work only) | 15 | 27% | Roadmap = `FOUNDER_PLAYBOOK` §8 Build-Now list, nothing else |
| Content & brand | 6 | 11% | Batch-produced Thursday (brand doc cadence: 3-4 posts, repurpose, essay progress) |
| Community & network | 4 | 7% | Daily 30-min engagement + 1-2 relationship calls |
| Metrics, planning, reviews, admin | 4 | 7% | Monday CEO hour + Friday close-out |
| Learning | 3 | 5% | Saturday block (§8) |
| Buffer (things break) | 3 | 5% | Unassigned on purpose |

**Reallocation gates:** first *paying* customer → product 18h / sales 18h. Raise mode (seed open) → fundraising takes 8-10h **from content and buffer, never from the sales floor or partner commitments**. Post-seed → hiring gets 6-8h from product (you're buying back build capacity).

---

## 3. The Week (the centerpiece — put this in your calendar today)

| Day | AM | PM | Evening* |
|---|---|---|---|
| **Mon** | **CEO Hour** (§6 dashboard, pick top-3, plan week) → outreach block: 20 new accounts sequenced | Follow-ups + CRM hygiene; prep tomorrow's calls | Call window (US buyers) |
| **Tue** | **Calls day.** Discovery + demos stacked back-to-back; light tasks between | More calls; partner Slack sweeps | Call window |
| **Wed** | **Deep build block 1 (3h, phone off)** | **Deep build block 2 (3h)** — ship target: connector/partner needs | Nothing scheduled |
| **Thu** | Build (finish + ship the week's improvement) | **Content batch (3h):** 3-4 posts written+scheduled, essay progress, repurpose to X | Community: 45 min genuine engagement |
| **Fri** | Partner updates (5-line template, every active partner) → feedback triage (30 min, scored per `DESIGN_PARTNER` §14) | **Scoreboard (20 min)** + **Weekly Review (30 min)** (§7) → loose ends, next-week call prep | Off |
| **Sat** | Learning block (2-3h max, §8) | Off | Off |
| **Sun** | Off | Off | **Sunday 30:** calendar next week, confirm top-3, clear head |

\* *Evening call windows apply if you're selling into US time zones from elsewhere; if US-based, compress calls into Tue/Thu afternoons and reclaim evenings. Either way: max 3 evenings/week with work in them.*

**The daily spine (every working day):** 90 min deep work *before* opening inbox/LinkedIn → comms batch #1 (30 min: replies, follow-ups due) → theme-day block → comms batch #2 (30 min, end of day) → **shutdown ritual (10 min):** log calls into CRM, write tomorrow's top-3, close the laptop. Workout 45 min at a fixed time you actually keep. Two comms batches only — notifications off between them.

---

## 4. The Five Sub-Systems (weekly checklists; numbers from the source docs)

**Product OS (Wed-Thu):** Ship 1 user-visible thing/wk · build only what's on the Build-Now list or scores ≥ threshold in the feedback system (`DESIGN_PARTNER` §14) · release = deploy + 1-line partner note + changelog line · quality bar: CI green, no known P0/P1, hook clean (the standing repo discipline) · kill rule: any feature not touched by a partner in 30 days of shipping gets flagged in the monthly review.
**Customer OS (Tue/Fri):** every active partner: 1 call/wk (M1) or biweekly (M2+), 5-line Friday update, <24h Slack SLA · every call ends with the feedback question + next step · day-30/60/90 gates per `DESIGN_PARTNER` §11 · case-study capture is a day-90 deliverable, not an afterthought.
**Sales OS (Mon-Tue daily follow-ups):** 20 new accounts/wk · 5 conversations/wk floor · every call logged same day · follow-ups due today done today (they decay in 48h) · pipeline reviewed Friday against 3× coverage · referral ask on every call, counted.
**Marketing OS (Thu):** 3-4 LinkedIn posts (pillar rotation, brand doc §5) · daily X repurposing (10 min from batch) · 2 essays/mo · 1 monthly state-of-the-build · every piece has one job: get an ICP reply or DM · attribution asked on every call ("how'd you find me").
**Networking OS (daily 30 min + Thu evening):** 5 substantive comments/day on the named-30 list · 1-2 relationship calls/wk (advisors, community, peers) · 1 community lightning-talk ask/mo · investor list: engage content only, no pitching until the trigger (`DESIGN_PARTNER` §16).

---

## 5. Metrics OS

**North Star (product):** decisions flowing through Kernl per week across all tenants. **North Star (company, this stage):** active design partners at ≥90% coverage. **Interim NSM until partners exist:** ICP conversations/week.
**Leading:** accounts touched, conversations held, demos earned, content-sourced replies, partner coverage %. **Lagging:** partners signed, paying customers, ARR, case studies. **Warning signals (act, don't watch):** conversations <3 two weeks running → outreach volume or messaging problem, fix Monday · reply rate <3% after 100 sends → rewrite angles · partner coverage stalled <60% at day 45 → data problem, escalate to champion · you skipped two Friday scoreboards → you're hiding; that's the tell.
**Vanity (never report to yourself):** follower totals, impressions, stars, hours worked.

---

## 6. The Monday CEO Dashboard (open every Monday, fill in 15 min)

```
WEEK OF ______            STAGE: [ ] partners  [ ] first-paying  [ ] raising
TOP 3 THIS WEEK: 1)              2)              3)
FLOOR CHECK: conversations booked so far: __ /5
PIPELINE: accounts touched __ | active convos __ | demos set __ | agreements out __ | partners active __ | paying __
PARTNER HEALTH: [name: coverage %, last call, next gate] ×N
REVENUE/ARR: $__        PIPELINE COVERAGE vs next gate: __×
CONTENT QUEUE: posts scheduled __ /3 | essay due? | launch upcoming?
PRODUCT: this week's ship: ______ | blocked on: ______
BOTTLENECK (the one thing limiting everything else): ______
FUNDRAISE: [ ] not yet (trigger: 3 partners + 1 paying + case study)  [ ] open: next step ______
HEALTH: sleep avg __ | workouts __ /4 | day fully off? Y/N
```

---

## 7. Review Cadence

**Daily (10 min, shutdown):** calls logged? floor pace? tomorrow's top-3 written.
**Weekly (Fri, 30 min):** scoreboard numbers → 3 questions: *What did I learn that changes something? What did I avoid? What's the bottleneck?* → one experiment for next week → decision-log entries.
**Monthly (90 min, last Friday):** month vs. `DESIGN_PARTNER` §17 plan · kill-list review (features, channels, accounts gone cold) · pricing/messaging learnings consolidated · next month's single theme · update the four playbooks *only if evidence demands it* (docs serve reality, not vice versa).
**Quarterly (half day):** OKR scoring (§11) · stage-gate check (§12) · pivot checkpoint if red thresholds hit (`DESIGN_PARTNER` §15) · rewrite quarterly OKRs · one honest public retrospective post (brand pillar 4).
**Annual:** the year-one retrospective essay (already planned, brand doc idea #49) + re-run the market validation assumptions register.

---

## 8. Learning OS (Saturday block + ambient)

**Reading order (one at a time, applied immediately):** 1. *The Mom Test* (before more discovery calls — this week) · 2. *Founding Sales* (during partner sprint) · 3. *Obviously Awesome* (when messaging stalls) · 4. *Sales Pitch* · 5. *Play Bigger* (pre-seed narrative) · 6. *Crossing the Chasm* (Y2 enterprise).
**Ambient (timeboxed, 30 min/day inside comms batches):** Lenny's, Tunguz, Latent.Space, Luiza's Newsletter, TLDR AI headlines.
**Competitor sweep:** 30 min/month (monthly review): Decagon/Sierra/Fin release notes, Taktile blog, agent-governance funding news. **Not weekly** — obsessing over competitors at this stage is procrastination with a business case.

---

## 9. The Ignore List (anti-distraction contract with yourself)

Vanity metrics · new features not on the Build-Now list · shiny agent frameworks and model releases (30-min monthly sweep only) · premature hiring (trigger: post-raise) · premature fundraising (trigger: 3+1+story) · conference *sponsoring* · Discord/community building of your own · Product Hunt (for now) · YouTube channel · redesigns (the console is done; the design system is documented) · refactors not blocking a partner · enterprise features nobody asked for · "partnership" calls with $10B+ companies · AGI discourse · building a 6th strategy doc. **Rule of thumb: if it doesn't touch a partner, a prospect, or this week's ship, it waits for the monthly review to argue its case.**

---

## 10. AI & Automation Blueprint (cheap, now)

| Task | Tool / method | When |
|---|---|---|
| Repo work, docs, analysis | Claude Code (already in use) | Ongoing |
| Outreach sequencing + email finding | Apollo (basic) | Now |
| Meeting notes + call summaries | Granola or Fathom (free tiers) → paste key quotes into CRM | Now — never take manual notes on discovery calls |
| CRM | A single sheet (`founder-os/crm.csv` spec below) until 25+ active accounts, then Attio/folk | Now → M3 |
| Content repurposing | Essay → 4 posts → 2 threads via a fixed prompt template; schedule via Buffer/Typefully | Thu batch |
| Competitor/market monitoring | Google Alerts (Decagon, Sierra, Taktile, "agent governance") + monthly sweep | Now |
| Lead research at scale | Clay | Only past ~150 accounts/mo (per `DESIGN_PARTNER` §6) |
| Investor CRM | Same sheet, second tab | When raise opens |
| Weekly scoreboard assembly | Ask Claude Code to generate it from the CRM sheet + calendar each Friday | Now |
| **Never automate** | First-touch personalization line, discovery calls, partner Slack replies, the weekly review | — |

---

## 11. Quarterly OKRs

**Q3-2026 (now → Sep 30) — "Partners or bust":** O1 Prove the exchange: 3-5 partners signed (KR: ≥3 active, ≥90% coverage at ≥2, 2 Leakage Reports delivered). O2 Keep the floor: ≥60 ICP conversations in the quarter. O3 Ship the machine: shadow connector live, first replay artifact at a partner. O4 Seed the brand: 30+ posts, 4 essays, HN launch, 1K in-ICP follower adds. *(Health KR: ≥45 workouts, zero all-nighters.)*
**Q4-2026 — "Convert":** first paying (1-3), $25K+ ARR, named case study, YC outcome absorbed, seed conversations open if green, founding-hire pipeline started.
**Q1-2027 — "Repeatable":** partner→paid ≥50%, $75K+ ARR, second domain shadow at best partner, raise closed or default-alive plan written.
*(Detailed month-by-month: `DESIGN_PARTNER` §17 + `FOUNDER_PLAYBOOK` §19 — this OS just enforces the rhythm against them.)*

---

## 12. Stage Evolution (what changes at each gate)

| Stage gate | Time shift | Metric shift | New rituals | Stop doing |
|---|---|---|---|---|
| → First paying | Product +3h, sales −2h | NSM adds ARR; NRR watch begins | Monthly customer-health review | Free-partner intake |
| → Raise open | Fundraising 8-10h from content/buffer | Pipeline coverage on *investors* (3× target checks) | Investor-update email (monthly, even pre-close) | New Tier-1 outbound pauses; floor drops to 3 (never 0) |
| → Post-seed | Hiring 6-8h; delegate CS gradually | Burn multiple ≤2 enters dashboard | Weekly 1:1s; hiring scorecards | Founder-does-all-encoding (train hire #1 on it) |
| → Series A track | Sales team owns floor; you own top-5 accounts + narrative | Rule of 40 watch; NRR ≥105% proof | Quarterly board-style review (even without a board) | Solo everything — the OS becomes a team OS |

---

## 13. Founder Command Center (repo-native spec)

Keep it where you already live — the repo, not a Notion you'll abandon:
```
founder-os/
  DASHBOARD.md        ← §6 template, updated Mondays (this quarter's OKRs pinned at top)
  crm.csv             ← account, tier, evidence-link, contact, stage, last-touch, next-step, source
  content-calendar.md ← 4-week rolling: date, pillar, hook, status, link
  decision-log.md     ← date, decision, why, revisit-when
  journal.md          ← Friday review answers, 5 lines/week
  ideas-backlog.md    ← everything the Ignore List deflects, argued monthly
  risk-register.md    ← top-5 live risks, reviewed monthly (seeded from playbook §18/§19)
  meetings/           ← one file per discovery/demo call (template from DESIGN_PARTNER §18)
```
*(Say the word and this scaffold gets created with all templates pre-filled.)*

---

## 14. Launch OS (compact; first use: the HN launch, ~day 60-90)

**Pre (T-14):** artifact ready (Show HN draft peer-reviewed by 2 technical friends), demo tenant polished, site CTA aligned, FAQ answers pre-written (self-attestation, Microsoft AGT, "why not OPA"), partners forewarned. **Day:** post early US-morning · reply to every comment for 6h (calls excepted — floor still wins) · LinkedIn/X companion posts · community shares where membership is genuine (no drive-by drops). **Post (T+3):** metrics honestly logged (traffic, signups, conversations started) · every warm commenter gets a personal follow-up · retro in the decision log · repurpose the best comment-thread arguments into next week's content. **Rule: a launch is a spike on top of the rhythm, never a replacement for it.**

---

## 15. The 365-Day Line of Sight

Q3-26: partners (this doc, §11). Q4-26: conversion + YC/pre-seed. Q1-27: repeatability + raise. Q2-27: founding hire onboard, domain #2, $150-300K ARR track (`FOUNDER_PLAYBOOK` §11 base case), NRR evidence. Day 365 (2027-07-23): the year-one honest retrospective essay, written from the journal you kept — 52 Friday entries, 12 monthly reviews, 4 quarterly resets. **The compounding asset of this whole OS is that file trail: it becomes your seed data room, your content archive, and your proof of learning velocity — the three things investors, customers, and future-you all want, produced as a byproduct of just running the week.**
