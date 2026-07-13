KERNL: Technical Architecture for an Institutional Kernel
A note on method before Part 1: I will make decisions, not surveys. Where a technology question has a fashionable answer and a correct answer, I'll tell you which is which. And I'll flag the three or four places where this design contains genuine research risk rather than pretending it's all engineering.

PART 1 — THE COMPUTING MODEL
The candidates, eliminated in order
Policy objects — policies are code, not the primitive. They change, get superseded, conflict. Making them the primitive is like making "the program" the primitive of an OS instead of the process.
Decision graphs — a representation (an index), not a primitive. Graphs are derived views.
Event streams — the correct truth substrate, but "event" is too weak a primitive: it has no deontic content. An event says what happened; it cannot say what was authorized.
State machines / actors — implementation patterns, not the computing model.
Formal logic systems — the correct semantics, but logic alone gives you a prover, not a system. Provers don't have accountability.
Capability systems — hot. Half the answer.
The primitive: the Warrant
The core primitive is the Warrant: a signed, evidence-carrying, attenuable, appealable claim of authority.

Formally, a warrant is a tuple:


Warrant = ⟨
  subject,        // who is authorized (human, agent, role)
  action,         // typed action with effect classification
  scope,          // resource × conditions × limits (caveats)
  grounds,        // derivation: policy bundle version + evidence + precedents cited
  authority,      // the delegation chain that licenses issuance (chain of warrants)
  validity,       // temporal bounds, usage bounds
  obligations,    // what must accompany exercise (logging, notification, review)
  appeal,         // the contest path
  signature       // cryptographic binding of all of the above
⟩
Why this wins: the recursion
The decisive property is that every other concept in the system is a warrant:

Concept	As a warrant
A decision	A warrant to act, exercised once
An approval	A warrant granted by a human adjudicator
A delegation	A warrant to issue warrants (with attenuation bounds)
A precedent	A warrant whose grounds bind future issuance in its scenario class
A policy deployment	A warrant to change the warrant-issuing rules
A constitutional amendment	A warrant to change the rules for changing rules
Agent onboarding	A warrant chain rooted in a human authority
This recursion — authority to grant authority, governance as self-application — is what makes the system a kernel rather than a rules engine. It is the same move that made capabilities work in OS research (a capability to mint capabilities), the same move that makes Git elegant (a commit is a snapshot; a branch is a pointer; everything is content-addressed objects). One primitive, closed under its own operations. The governance layer isn't a separate subsystem bolted on top; it is warrants applied to the warrant machinery itself. The system eats its own dogfood constitutionally.

The full computing model, in one sentence each
Truth is an append-only log of warrants, their exercises, and their outcomes (event sourcing — the ledger is the system of record; everything else is a rebuildable view).
Policy is a compiled, versioned, content-addressed artifact (the bundle) — a pure function from scenario to warrant-or-escalation.
Evaluation is logic-programming with provenance: the reflexive path evaluates a decidable rule fragment (Datalog-class) whose derivation tree is the explanation — provenance is not logged after the fact; it falls out of evaluation (this is the provenance-semiring insight from database theory: the proof of the answer is computed with the answer).
Security is capability-based: warrants are attenuable (you can always narrow, never widen — Biscuit/Macaroon-style caveats), proof-of-possession bound, offline-verifiable, revocable by chain.
Everything ambiguous escalates: the primitive has a dual — the Escalation — and the system's honesty lives in refusing to mint warrants it cannot ground.
Prior art this consciously synthesizes: object-capability systems (KeyKOS/E/seL4), Biscuit tokens (Datalog caveats, offline attenuation), Zanzibar (relationship-based authorization at scale), event sourcing, provenance semirings (Green/Tannen), and Hohfeldian jurisprudence (Part 2). Nothing here requires new physics — the novelty is the synthesis and the institutional semantics.

PART 2 — THE INSTITUTIONAL IR ("KIR")
The trap to avoid first
Standard deontic logic (SDL) is a famous paradox factory (Ross's paradox, Chisholm's contrary-to-duty puzzles). Any IR built naively on "obligation/permission as modal operators" will be wrong in ways lawyers discover instantly. The engineering answer, validated by the only production-grade law-compiler in existence (Catala, which compiles French tax law with default-logic semantics and a formally verified compiler): institutional rules are defeasible rules with explicit priority structure — general rule, exceptions, meta-rules for who wins. That is how institutions actually write policy, and it has clean semantics (prioritized default logic).

Structure: MLIR, not LLVM
The right structural precedent is MLIR's dialect stack, not LLVM's single IR — because institutional intent needs progressive lowering:


KIR-Intent      (literate, source-mapped, human-reviewable — near-prose with holes)
    ↓ lowering
KIR-Norm        (defeasible deontic core: typed norms + priority lattice)
    ↓ lowering
KIR-Decision    (exhaustive decision tables / Datalog — decidable, verifiable)
    ↓ lowering
KIR-Exec        (warrant templates, escalation routes, obligation schedules)
Each lowering is checked; each level keeps source attribution (a norm without a citation to its source does not compile — this single rule is worth more than any extraction model).

Type system
The type algebra comes from Hohfeld's analytical jurisprudence (1913) — the only complete, battle-tested decomposition of institutional relations ever produced, and it maps onto a type system almost embarrassingly well:

Hohfeldian incident	KIR type	Meaning
Duty	Obligation<A, deadline, violation-handler>	must do A
Privilege	Permission<A, scope>	may do A
No-right / prohibition	Prohibition<A, scope>	must not do A
Power	Power<NormChange, bounds>	may change normative relations — the delegation/amendment type
Liability	dual of Power	subject to another's power
Immunity	Immunity<NormChange>	constitutional protection: no power may alter this
Disability	dual of Immunity	lacks the power
Powers and Immunities are the constitutional layer, in the type system. "No policy change may weaken the two-approver rule on payments > $50k" is not a runtime check — it's an Immunity that makes offending bundles fail to type-check.

The remaining type families:

Authority types: Actor, Role, Scope = Action × Resource × Condition. Delegation is bounded subtyping: a delegated scope must be a subtype (⊆) of the delegator's scope. Attenuation monotonicity is enforced by construction — scope-widening is a type error, not a runtime catch.
Temporal types: validity intervals, effective/sunset dates, deadline obligations with typed violation states (Obligation that expires unmet transitions to a Violation value that must be handled — like a checked exception for institutions). Fragment of metric temporal logic, deliberately restricted to decidable patterns (deadlines, windows, recurrence).
Evidence types: Evidence<Claim, Source, Method, Freshness> with a trust lattice (verified > attested > asserted > inferred). Norms declare the minimum evidence tier their conditions require. Evidence combines via semiring operations, so confidence propagates through derivations mechanically.
Risk/effect types: every action is classified Reversible | Compensable | Irreversible and Internal | External. This is the load-bearing safety feature: irreversible-external actions require strictly higher authority tiers and stricter failure semantics (Part 5), enforced in types, not in prose.
Deontic conflict resolution: three meta-rules from actual legal tradition, encoded as the IR's φ-node semantics: lex specialis (specific beats general), lex superior (higher authority beats lower), lex posterior (later beats earlier) — with explicit, compiler-checked priority when they disagree.
Syntax (a taste — textual form, s-expression-flavored)

(norm refund.annual.14d
  :source (doc "notion_refund_sop.md" §2.1 (hash "ab3f…"))
  :stance (Permission (refund :plan annual :window (days 14) :amount full))
  :actor  (Role support.agent)
  :evidence-min attested
  :effect (Compensable External)
  :except refund.abuse-flagged           ; defeasible: names its exception
  :priority (lex-specialis over refund.general))

(immunity payments.two-approver
  :protects (invariant (=> (> amount 50000usd)
                           (>= (distinct-approvers ruling) 2)))
  :amendable-by (Power board.governance :quorum 2/3))
The decisive language-design decision
The enforce-tier fragment of KIR is decidable by construction — Datalog with stratified negation, finite domains, restricted linear arithmetic. This is Cedar's design lesson (AWS's authorization language, formally modeled in Lean and analyzable because it's deliberately not Turing-complete): expressiveness is the enemy of analyzability, and analyzability is the entire value proposition. Anything that needs more expressiveness lives in advise-tier (can recommend, cannot authorize) or in the deliberative path (humans). This one decision makes Parts 9 (verification), 6 (simulation), and 5 (determinism guarantees) possible instead of aspirational.

Evolution & standardization
Versioned spec; dialects are the extension mechanism (a healthcare-consent dialect, a financial-controls dialect) so the core stays frozen and small. Standardization path is LLVM's, not OASIS's: a standard is a killer implementation that others conform to, not a committee document (LegalRuleML is the cautionary tale — a fine OASIS standard with no runtime anyone wants). Open the IR spec + verifier + reference evaluator around V6 (Part 16); keep the compiler proprietary. If KIR becomes what policy tooling compiles to, that's the deepest moat in the whole design (Part 15).

PART 3 — COMPILER ARCHITECTURE
Ten stages. The first is the least trustworthy and the design treats it accordingly.


  SOPs / policies / Slack / tickets / decision logs / org data / contracts
        │
  [1] FRONTENDS (per-source parsers → candidate norms, LLM-assisted)
        │   rule: every candidate carries char-offset citations; uncited ⇒ rejected
  [2] SEMANTIC NORMALIZATION (entities, units, thresholds → typed predicates)
  [3] ONTOLOGY BINDING (actions/resources/actors resolved against org ontology;
        │   unresolved terms become review items, never silent nodes)
  [4] AUTHORITY RESOLUTION (bind each norm to Hohfeldian positions via org model:
        │   who holds the Power backing this norm? unowned norm ⇒ compile error)
  [5] CONFLICT DETECTION (SMT: ∃ scenario where norms yield contradictory verdicts?
        │   → emit CONCRETE COUNTEREXAMPLE scenarios as compile errors)
  [6] PRIORITY SYNTHESIS (propose lex-specialis/superior/posterior orderings;
        │   ambiguous priorities ⇒ human review queue, never guessed silently)
  [7] VERIFICATION (constitutional invariants model-checked against the compiled set;
        │   exhaustiveness: every in-scope scenario reaches VERDICT or ESCALATE —
        │   explicit escalation is fine, silence is undefined behavior and rejected)
  [8] LOWERING (KIR-Norm → decision tables + Datalog rules + simulation model
        │   + regenerated PROSE — the compiler emits the employee handbook back out;
        │   round-tripping makes the bundle the single source of truth)
  [9] REPLAY CI (candidate bundle vs. full historical corpus → semantic diff:
        │   flips, new escalations, invariant stress, monetary delta — Part 6)
 [10] PACKAGING (content-addressed, signed bundle: norms + ontology snapshot +
            golden tests + verification certificates + provenance manifest;
            rollout: shadow → canary → enforce, each stage warrant-gated)
Three design commitments worth stating plainly:

Extraction proposes; it never disposes. Nothing an LLM extracts becomes enforce-tier without passing a human review gate. The compiler's job is to make review cheap (citations inline, conflicts pre-detected with counterexamples, diffs against current bundle) — not to eliminate it. The metric that matters is minutes-of-review-per-norm, and the whole frontend is engineered against it.
Conflict detection is the killer feature of the compiler. "Here is a concrete scenario where your refund SOP and your finance policy disagree, with citations to both" is worth more to a buyer than any chat interface ever shipped. It's also cheap: decision-table conflicts over finite domains are plain SAT/SMT.
Stage 9 runs on every compile. Policy changes get regression-tested against history by default, the way code gets CI. This converts the simulator from a product feature into a compiler stage — which is exactly how it stops being skippable.
The precedent loop closes the compiler: adjudicated escalations (Part 5) land as (a) golden test cases and (b) candidate norms with the adjudication as their cited source. Deliberation hardens into reflex on the next compile.

PART 4 — KNOWLEDGE REPRESENTATION & STORAGE
The principle that dissolves the database religious war
Truth is the ledger. Everything else is a derived, rebuildable view. Once you commit to event-sourcing the warrants/adjudications/ingestions, the "graph vs relational vs vector" question stops being theological: you use all of them, as indexes, and none of them as truth.

Subsystem	Storage	Why	Tradeoffs accepted
Ledger (warrants, exercises, outcomes, adjudications)	Postgres append-only, partitioned per org; segments archived to object storage; hash-chained with periodic Merkle checkpoints	Boring, transactional, auditable; single-writer-per-org makes linearizability trivial	Not infinitely scalable per-org — fine, orgs don't emit Google-scale decision volume (Part 11)
Policy bundles (compiled artifacts)	Content-addressed blobs in object storage (OCI-image-like), signed; metadata in Postgres	Immutable, cacheable anywhere, verifiable by hash; "docker pull for policy"	None meaningful
Precedent/norm graph	Relational + recursive CTEs (Postgres) for years; graph shape only in views	An org's norm graph is small — 10³–10⁵ nodes. Buying Neo4j for 50k nodes is architecture cosplay	Cross-org precedent networks at V7 scale may want a real graph engine — a view-rebuild away
Embeddings (precedent similarity, scenario routing)	pgvector year 1 → Qdrant only if scale forces	Embeddings are cache: rebuildable from ledger + models; never authoritative	Retrieval routes and ranks; it must never decide at enforce tier
Org model / digital twin	Bitemporal relational (valid-time × transaction-time)	The audit question is inherently bitemporal: "what did we believe on March 3rd about who held authority on Jan 15th?" Nothing but bitemporal answers it	Schema discipline is unforgiving; worth it
Simulation / analytics	DuckDB embedded over ledger extracts (Parquet)	10 yrs × 10k decisions/day ≈ 36M rows — a single node's lunch. Columnar replay is embarrassingly parallel	ClickHouse only when cross-tenant hot analytics genuinely demand it
Full-text	Postgres FTS → OpenSearch if/when	Sources are modest corpora, not the web	—
The storage trinity that must never be violated: event-sourced truth, bitemporal authority, content-addressed artifacts. Every future scale problem is solvable by re-materializing views; violations of the trinity are the only unrecoverable mistakes.

PART 5 — RUNTIME ARCHITECTURE
The two-speed kernel

            scenario (from human UI / agent gateway / API)
                        │
              ┌─────────▼──────────┐
              │  SCENARIO TYPING &  │  schema-validated, versioned scenario types
              │  ROUTING            │  (retrieval may ROUTE here, never decide)
              └───┬────────────┬────┘
      settled     │            │        novel / ambiguous / low-evidence
   ┌──────────────▼───┐   ┌────▼──────────────────────────┐
   │ REFLEXIVE PATH    │   │ DELIBERATIVE PATH              │
   │ compiled tables + │   │ precedent retrieval → LLM      │
   │ Datalog; pure fn  │   │ drafts RULING PROPOSAL w/      │
   │ of (scenario,     │   │ cited precedents → routed to   │
   │  bundle@hash,     │   │ human adjudicator w/ context   │
   │  org-model@time,  │   │ package → ADJUDICATION         │
   │  clock); P50<10ms │   │ (minutes–days; Temporal-class  │
   │ NO LLM. EVER.     │   │  durable workflow)             │
   └───────┬───────────┘   └────────┬───────────────────────┘
           │ warrant / denial       │ adjudication ⇒ precedent ⇒
           │ + derivation tree      │ golden test + candidate norm
           ▼                        ▼
   ┌────────────────────────────────────────────┐
   │ LEDGER (write-ahead: no ruling exists      │
   │ unless its ledger entry exists)            │
   └────────────────────────────────────────────┘
Guarantees (the contract, stated as invariants)
Determinism: a reflexive ruling is a pure function of (scenario, bundle hash, org-model snapshot, clock). Pin all four → bit-exact replay of any historical ruling, forever. This guarantee is the foundation of audit, simulation, and appeals; everything in the design defends it.
Explanation completeness: every ruling carries its derivation tree with citations — computed during evaluation (provenance semirings), not reconstructed after.
Write-ahead accountability: no warrant is released before its ledger append commits.
Honest refusal: enforce-tier never guesses. Below evidence/confidence thresholds → escalation, which is a first-class output, not an error.
Risk-typed failure semantics (the detail auditors will love): on infrastructure failure, actions fail closed if Irreversible|External, may fail open-with-logging if Reversible|Internal and policy permits. The effect types from Part 2 drive degraded-mode behavior — safety semantics aren't in a runbook, they're in the types.
Offline verifiability: any third party can verify a warrant (signature + chain + Merkle inclusion proof) without calling Kernl.
Interaction surfaces
Humans: the escalation inbox (adjudication with full context packages — this is the daily product surface); the policy PR workflow (propose → replay report → review → staged deploy); the appeal flow (every warrant names its appeal path; appeals produce adjudications; adjudications bind as precedent).
Agents: via the gateway (Part 8) — warrants:request, exercise-with-proof, revocation streams.
External systems: verifier SDKs/sidecars (OPA-style) that gate actions in their systems on warrant verification — Kernl authorizes; it never executes. That boundary is permanent and non-negotiable: the moment Kernl executes actions it becomes a workflow engine competing with Temporal/ServiceNow, and it dies.
API sketch: POST /rulings:evaluate · POST /warrants:request · POST /warrants/{id}:verify (also offline) · POST /appeals · GET /ledger?… (replay/audit) · POST /bundles:deploy (shadow|canary|enforce — itself warrant-gated) · streams: escalations, revocations, drift.

PART 6 — SIMULATION ENGINE
You said this is likely the moat. Half agree: the moat is the corpus + the determinism discipline that makes simulation valid — the algorithms are all standard. Nobody else can replay institutional history because nobody else has institutional decisions in replayable form. The simulator monetizes the ledger.

Five layers, in strict order of epistemic honesty:

Historical replay (deterministic, exact). Candidate bundle × full scenario corpus → semantic diff: which decisions flip, which newly escalate, invariant stress, monetary delta, affected-population breakdown. Because rulings are pure functions, this is trivially correct-by-construction; DuckDB-vectorized evaluation of decision tables makes it fast (millions of scenario-evaluations/second/node). This runs on every compile — it's policy CI, not a separate product.
Counterfactual replay (exact, bounded claim). "What if the threshold had been X since January." Same machinery, modified bundle/world. State the limit loudly and in the UI: replay shows what the system would have ruled, not how customers/employees would have behaved in response. Confusing these two is how you lose regulator trust permanently.
Forecast simulation (probabilistic, labeled as such). Fit arrival/mix models on the scenario stream (seasonality, drift) → Monte Carlo scenario generation → distributions of outcomes under a candidate bundle, with uncertainty bands. Never point estimates.
Operational/capacity simulation (the sleeper feature). Discrete-event simulation of the escalation topology under a candidate bundle: given arrival rates and adjudicator capacity, does this policy change flood the CFO's inbox? What's the P95 time-to-adjudication? Policy changes have queueing consequences; no product on earth models this today, and it's classic queueing theory + DES. For a Fortune 500 this alone justifies the simulator.
Adversarial simulation. Property-based fuzzing + SMT counterexample mining over the typed scenario space: find the scenario that extracts maximum value with minimum approvals; find paths around SoD. Red-team your policy bundle before an actual employee or agent finds the exploit.
Fortune 500, concretely: M&A dry-run (merge two bundles, replay both histories, get the integration conflict list in an afternoon); regulatory-change impact (encode the new rule as constraints, replay, get the compliance-cost delta); reorg rehearsal (candidate delegation graph → capacity sim → bottleneck report).
Governments: replay proposed rule changes against years of historical case files (visa criteria vs. 5 years of applications — see exactly which past cases flip); agency capacity planning before legislation mandates workloads.

Tech: DuckDB, Parquet, a Rust/Python Monte Carlo harness, Hypothesis-class PBT, Z3, a DES core. Nothing exotic. The moat is upstream.

PART 7 — THE ORGANIZATIONAL DIGITAL TWIN
The twin is not an org chart. It's the live authority graph, and its killer property is that it's reconciled, Kubernetes-style: desired authority vs. observed behavior, with drift as a first-class signal.

Model (bitemporal relational, per Part 4): Actors (humans, agents, service identities) · Roles (bundles of Hohfeldian positions) · Bindings (actor↔role over valid-time intervals) · Delegations (warrants — scoped, attenuated, expiring; the twin is largely a materialized view over delegation warrants, which keeps the whole system on one primitive) · Escalation routes (typed graph with capacity annotations — feeds the DES in Part 6) · SoD constraint sets (Immunity-typed: e.g., no actor may hold both propose-payment and approve-payment in the same scope) · Responsibilities (typed RACI: accountable-for ≠ authorized-to, and the type system knows the difference).

Updates: event-sourced from HRIS/IdP feeds (hires, departures, transfers) + explicit delegation warrants. Every mutation is a ledger event; the twin at time T is a deterministic fold — which means the twin itself is replayable, and "who could have authorized this on date X" is answerable with proof.

Drift detection — the reconciliation loop, three drift classes:

Shadow authority: observed approvals/actions by actors the model says lack the power. Either the model is stale (propose amendment) or a violation occurred (open incident). The system must not silently pick one — it routes to a human with the evidence.
Dormant authority: powers held but unexercised for N months. Pure attack surface; propose revocation (this is least-privilege hygiene, automated).
Path drift: escalations actually flowing along edges the design doesn't have ("everyone actually asks Priya"). The most valuable drift class — it's tribal knowledge surfacing as telemetry, and it becomes a proposed model amendment with evidence attached.
Weekly drift report; every item resolves to amend the model or flag the behavior — and both resolutions are warrants, so the reconciliation loop is itself audited.

PART 8 — AGENTIC EXECUTION
Capability-based security for the agent economy, concretely:

Identity & attestation. Agents get workload identity (SPIFFE-class), plus a signed agent manifest: model, prompt/config hash, tool set, operator-of-record. You cannot warrant what you cannot identify; an agent whose configuration changed is a different agent (new manifest hash, re-onboarding through its authority chain).

Authority acquisition. Agent presents identity + scenario → runtime evaluates → issues a warrant that is:

Scoped (action × resource × conditions) and caveated (Biscuit/Macaroon-style: ≤ $500, ≤ 10 exercises, expires in 4h, only for tickets tagged X);
Proof-of-possession bound to the agent's key — not pure bearer; theft without the key is useless;
Attenuable but never amplifiable (subtyping from Part 2, enforced in the token format itself);
Chain-rooted in a human: every agent warrant's authority chain terminates at an accountable human Power. No self-licensing agents, ever. This is the accountability invariant.
Execution. Downstream systems (ERP, payment rail, email, CRM) verify warrants via SDK/sidecar before acting — offline-verifiable (signature + chain + inclusion proof), so verification adds microseconds, not a network dependency on Kernl. Exercise events flow back to the ledger with outcomes.

Revocation. Layered: short TTLs (minutes–hours) as the baseline; streamed revocation lists to verifiers for the gap; chain revocation as kill switch — revoke one delegation warrant and every downstream warrant in its subtree fails verification instantly. Revoking an agent = revoking its root delegation. One operation, provably complete.

Stateful caveats (the honest hard part): cumulative budgets ("≤ $10k/week across all exercises") can't be verified offline. Resolution by risk type: per-warrant limits enforce locally; cumulative org-level budgets check synchronously for Irreversible actions, asynchronously-with-bounded-overshoot for Compensable ones. The types (Part 2) again drive the distributed-systems semantics.

Rings (protection model): Ring 0 constitution/amendment — humans, high ceremony · Ring 1 policy deploy — governance warrants · Ring 2 deliberative adjudication — senior humans, AI-assisted · Ring 3 reflexive routine — agents & humans under compiled policy · Advisory ring — unwarranted agents may draft and recommend, never act. Effect types gate ring access: Irreversible|External is never authorizable from Ring 3 alone.

PART 9 — FORMAL METHODS STRATEGY
Verify where properties are crisp and the payoff is trust; test everywhere else. Concretely, four tools with distinct jobs:

Tool	Job	When
KIR type system	Attenuation monotonicity, delegation bounds, effect/authority mismatches, obligation/permission confusion — caught at compile, always on, free	Day 1
SMT (Z3/CVC5)	Norm-conflict detection with concrete counterexample scenarios (Part 3, stage 5); constitutional invariants vs. compiled decision tables; SoD as reachability over the delegation graph	Day 1 (this is cheap: finite domains by design)
TLA+ / model checking	The protocols, not the policies: warrant issue/revoke/verify lifecycle, ledger append & checkpoint, bundle rollout state machine, revocation-vs-offline-verification race	Design phase of each protocol (the AWS usage pattern)
Alloy	Org-model structural exploration during schema design (SoD counterexamples, delegation-cycle detection) — a design tool, not CI	As needed
The strategy stands on the Part 2 decision: the enforce-tier fragment is decidable by construction (Cedar's lesson — Cedar ships a Lean-verified model and differential-tests production against it). Long-term (V6): a verified reference evaluator (Lean/F*) with continuous differential testing against the production Rust evaluator — CompCert-style assurance for the component where a bug means unauthorized authority.

What formal methods must never be asked to do here: prove LLM extraction correct (impossible — gate it with citations, review, and golden corpora instead); verify arbitrary temporal properties of unrestricted policies (undecidable swamp — the fragment restriction exists precisely to avoid this).

PART 10 — CRYPTOGRAPHY
Principle: crypto for verifiability, never for decentralization theater. Explicitly: no blockchain. A signed hash-chained log with published checkpoints delivers ~95% of the assurance at ~5% of the complexity, and the remaining 5% ("no single operator") is a federation problem for V7, not a consensus problem for V1.

Mechanism	Verdict	Where
Digital signatures (Ed25519)	Mandatory, day 1	Warrants, bundles, adjudications, checkpoints. Hierarchical keys: org root (HSM/KMS, ceremony-protected) → policy authority → rotating runtime issuers
Merkle trees / transparency log	Mandatory, staged	Year 1: hash-chained ledger + daily checkpoint anchored externally (object-lock storage / a second org / a public log). Year 3: full RFC-6962-style tree with inclusion proofs (sigstore/Trillian lineage) so any warrant holder can prove "this ruling is in the record"
Verifiable credentials	Deferred to V7	Cross-org actor/agent identity in the inter-institutional protocol
Zero-knowledge proofs	Deferred deliberately — research track only	The eventual prize is real (prove "our policy bundle satisfies regulation R" without revealing the bundle — SNARKs over decision-table properties), but shipping ZK before V7 is résumé-driven engineering. Nothing in V1–V5 needs it
MPC	Almost never	Only plausible for cross-org benchmarking without corpus sharing; aggregate-plus-DP is simpler and likely sufficient
Attestation	Yes, scoped	Agent manifests (signed config hashes) at V4; TEE runtime attestation only if regulated customers demand on-prem confidentiality guarantees
PART 11 — DISTRIBUTED SYSTEMS
Reality check first, because honest load math changes the architecture: "millions of decisions/day" ≈ 10M/day = ~115/sec sustained. That is small. The hard problems here are correctness, isolation, auditability, and replayability — not throughput. Designing for Google-scale would be malpractice; the throughput story is "embarrassingly shardable by tenant," full stop.

Tenancy = cells. An org is a hard isolation boundary. A cell = one full stack (Postgres, evaluators, ledger, streams) serving N small orgs; regulated/large orgs get dedicated cells or on-prem cells. No cross-org data plane, period. Global control plane only for billing, bundle registry (public policy modules), and protocol routing (V7).
Consistency. Per-org: single-writer ledger stream → linearizable appends trivially (it's one Postgres partition). Rulings = snapshot read + append. Cross-org: asynchronous protocol messages only; distributed transactions are banned forever — if a design seems to need one, the design is wrong.
The edge-evaluator pattern (the architecture's best trick): because bundles are immutable content-addressed artifacts and evaluation is a pure function, the reflexive evaluator ships as a stateless sidecar/binary that runs inside the customer's infrastructure — OPA's deployment model. Policy evaluates at the point of action in microseconds with zero Kernl-availability dependency; ledger writes buffer locally and reconcile asynchronously (with the risk-typed exception: Irreversible actions require synchronous ledger ack). This simultaneously solves latency, availability, and data-gravity trust objections.
Streaming: transactional outbox → NATS JetStream (Kafka only when an enterprise integration contractually demands it — at 115/sec, Kafka is a lifestyle choice, not a requirement).
Fault tolerance: evaluators are stateless replicas of immutable bundles (restart = re-fetch by hash); Postgres HA per cell (sync replica, RPO≈0); ledger segments continuously archived to cross-region object storage; degraded-mode semantics driven by effect types (Part 5, guarantee 5).
What survives 10 years: the four commitments — event-sourced truth, content-addressed bundles, stateless pure evaluators, cell-per-tenant isolation. Each org's history is an independent shard; there is no global hot spot by construction. Scale surprises get absorbed by re-materializing views, never by migrating truth.
PART 12 — TECHNOLOGY SELECTION
Languages. Rust for the kernel surface — evaluator, warrant engine, ledger writer, verifier SDK core (determinism, no-GC tail latencies, and the credible path to a verified-reference twin; also compiles to the edge-sidecar static binary and to WASM for embedded verifiers). Python for compiler frontends, LLM pipeline, simulation harness (ecosystem gravity; it's also what the repo already has). TypeScript/Next.js for surfaces (exists). Go: fine for SDKs; not needed in the core.

Concern	Year 1	Year 3	Year 10
Truth/ledger	Postgres (append-only, partitioned) + S3	+ Merkle transparency service (Trillian-class)	FoundationDB under the ledger only if multi-region serializable writes become real requirements
Policy artifacts	S3 content-addressed, signed	OCI-registry-style bundle registry	Federated registries (V7)
Evaluation	Rust evaluator service	+ edge sidecar (static binary / WASM)	+ Lean/F* verified reference, differential-tested
Events	Postgres outbox → NATS JetStream	NATS; Kafka where contracts demand	Protocol-grade streams cross-org
Workflow (escalations, appeals, reviews)	Postgres queues (boring, sufficient)	Temporal (durable human-in-loop workflows earn it by V3)	Temporal
Search/vectors	pgvector + PG FTS	Qdrant/OpenSearch if metrics force	commodity
Analytics/sim	DuckDB + Parquet	+ ClickHouse for multi-tenant hot dashboards	same shape
Verification	Z3 in compiler CI	+ TLA+ modeled protocols	+ verified evaluator
Identity/keys	Cloud KMS, Ed25519	SPIFFE fabric, HSM roots	+ VC/ZK research productized (V7)
LLM	current vLLM/Qwen for extraction; frontier APIs for deliberative drafts where data policy allows	task-tuned small extraction models (cost)	commodity; never the moat
Orchestration (pipeline)	LangGraph (exists in repo — acceptable as internal scaffolding)	replaced by owned pipeline runner (it's just a DAG of typed passes)	—
Explicitly rejected: Neo4j/TigerGraph as core (graph is a view; the norm graph is tiny), Kafka-as-system-of-record (transport ≠ truth), blockchain (Part 10), any agent framework as a dependency of the kernel (agents are clients), fine-tuning-as-moat, vector-DB-as-brain.

PART 13 — RESEARCH ROADMAP
(Compressed here; Part 16 carries the product-versioned view of the same timeline.)

Phase	Window	Deliverables	Breakthrough required	Dominant risk	Team
P1 Deterministic core	0–9 mo	Bundle format; pure evaluator; ledger; escalation inbox; replay CI on golden corpus	None — discipline	Building demos instead of the ledger	2 systems (Rust), 2 compiler/ML (Py), 1 product-design, founder
P2 Compiler	6–18 mo	Multi-source frontends; citation-gated extraction; SMT conflict detection w/ counterexamples; review UX; shadow deployments at design partners	Review efficiency: minutes-per-norm low enough that review beats authoring	Extraction quality plateau	+1 PL engineer, +1 forward-deployed
P3 Warrants	12–30 mo	Warrant format (Biscuit-derived); agent gateway; revocation; verifier SDKs; edge evaluator	Attenuation semantics that downstream vendors accept	Ecosystem chicken-and-egg on verifiers	+1 security engineer
P4 Twin + Simulator	24–48 mo	Bitemporal twin; drift reconciler; Monte Carlo + DES capacity sim; adversarial fuzzing	Drift precision (false-positive rate low enough to keep trust)	HRIS data quality	+1 data eng, +1 research eng
P5 Constitution	36–72 mo	Immunity types enforced end-to-end; amendment machinery; verified reference evaluator; KIR spec v1 published	Decidable fragment proven sufficient on real corpora (~80%+ coverage)	Fragment too weak → expressiveness pressure → analyzability collapse	+formal methods hires
P6 Protocol	60 mo+	Kernel↔kernel contracts; machine-readable regulation interface; transparency federation; ZK over bundle properties	ZK cost curve; standardization politics	Premature standardization	protocol + policy team
Research-vs-product rule, enforced ruthlessly: research artifacts merge only as compiler passes or evaluator features gated by the same golden-corpus CI as everything else — or they die in the lab. This is the single best defense against becoming a perpetual research project.

PART 14 — WHAT MUST BE TRUE
Ten assumptions the vision rests on:

Agents take on real execution (not drafting) in enterprises this decade — the macro bet.
Enterprises will accept a system of record for policy outside the documents-and-heads status quo.
Citation-gated extraction + review is cheaper than manual policy authoring (the review-efficiency threshold).
A decidable policy fragment covers ≥~80% of enforceable operational policy (Catala's experience with tax law says yes; must be proven per-domain).
Organizations tolerate the legibility (political will survives the first drift report that embarrasses someone senior).
Downstream systems will adopt warrant verification (SDK friction low enough; one flagship integration creates the pattern).
Determinism discipline survives contact with enterprise integration pressure ("just call the LLM here" is refused every time).
The ledger's compliance value monetizes before the agent economy fully arrives (bridge revenue).
Incumbents (ServiceNow, Pega, OPA/Styra, Palantir) stay incoherent on this synthesis long enough — each owns a fragment; none owns the primitive.
LLM costs keep falling so compilation economics keep improving.
Ten biggest technical risks: extraction hallucination reaching enforce tier (mitigated: citations + review gates + golden CI — this must be structurally impossible, not merely unlikely); scenario-schema sprawl breaking replay (versioned schemas with total upgrade functions — replayability across schema versions is a requirement, not a nice-to-have); ontology drift; org-data garbage-in; revocation-latency vs offline-verification tension (Part 8's TTL layering); stateful-caveat consistency; cell-fleet operational burden; deliberative-path quality (LLM-over-precedent must beat human-with-search or the inbox is noise); key-ceremony failure at a customer; eval ground-truth cost (labeled institutional decisions are expensive — the adjudication stream is the only sustainable source, which is another reason escalation UX is the product).

Ten hardest genuinely-unsolved problems (research, stated honestly): priority synthesis from messy sources at scale (defeasible-logic elicitation); counterfactual behavioral response (layer-3 simulation honesty); knowing-what-you-don't-know institutionally (tacit-boundary detection); precedent similarity that survives legal scrutiny (analogical reasoning with guarantees); semantic-stability under recompilation (a one-line source edit must not silently flip 500 rulings — needs semantic diffing + flip budgets); practical ZK over rich policy properties; NL↔formal round-tripping lawyers will sign; cross-org ontology alignment without a central authority; institutional Goodharting (the org gaming its own compiled metrics); open-world action ontology (authorizing genuinely novel action types).

PART 15 — FINAL VERDICT
1. Simplest path from today's repo to the Institutional Kernel. The repo already contains embryos of the right organs: engine/ is a proto-compiler-frontend, runtime/constraint_resolver.py + precedence.py + condition_eval.py is a proto-reflexive-evaluator, tests/eval_harness.py + golden JSONs is a proto-replay-CI. The path is reification, not rewrite: (1) reify the bundle — replace "skills file" with a content-addressed, signed, versioned artifact containing decision tables; (2) make the resolver a pure function and ledger every evaluation (write-ahead); (3) grow the 40-scenario eval corpus into the golden replay CI that gates every compile; (4) make escalation + adjudication first-class (the precedent loop — this is the missing organ, and it's product work, not research); (5) add conflict detection with counterexamples to the compiler; (6) then warrants. In that order.

2. Build next: the ledger + pure evaluator + escalation inbox (V1 in Part 16). 3. Never build: blockchain; a workflow/execution engine (authorize, never execute); autonomous policy self-modification (the learning layer proposes, humans dispose — permanent); a universal ontology upfront; chat-as-the-product (the product surfaces are the inbox, the policy PR, the replay report). 4. Hype to avoid: agent-framework churn (LangGraph is acceptable scaffolding, must never be load-bearing), GraphRAG-as-identity, vector-DB-as-brain, ZK-before-V7, fine-tuning-as-moat. 5. Foundational moats: the per-customer golden corpus + outcome-linked ledger (unreplicable without the years); the KIR decidable fragment; the warrant format + verifier network (protocol gravity); the adjudication stream (every escalation resolved = labeled ground truth nobody else has). 6. Most elegant architecture, one breath: everything is a warrant; truth is a log; policy is a compiled pure function; explanations are derivations; views are disposable; governance is the system applied to itself.

Scores. Architecture-as-designed: 9/10 (the missing point is honest — semantic stability under recompilation and deliberative-path quality are unproven research). Current repo against this target: ~3.5/10, which is normal and fine — the organs exist as embryos and nothing built so far is wasted if the reification path is followed.

System	The lesson to steal	The trap to avoid
Linux	Kernel/userspace split → policy plane vs execution plane; a stable "syscall ABI" (the warrant API) that outlives everything above it	Kernel sprawl — keep Ring 0 tiny
Kubernetes	Reconciliation loops (the drift detector is a controller); declarative desired state; admission control → warrant gates	YAML sprawl; extension-API chaos before the core is frozen
Git	Content-addressing; immutable history; cheap branching → shadow bundles & policy branches	UX hostility — Git won despite its porcelain, Kernl won't get that luck
LLVM	Typed IR with verifier passes; many frontends, many backends; the IR is the ecosystem	Letting the IR grow undecidable — Cedar beat this trap, follow it
Stripe	Absorb a regulatory swamp behind seven lines of integration (the verifier SDK is Kernl's seven lines)	Hiding too much — auditors must see everything, selectively
Palantir	Forward-deployed engineers make ontology real; institutions buy outcomes, not tools	Services gravity — FDE work must compile into the product (bundles, corpora), or you become a consultancy with a repo
PART 16 — VERSIONING STRATEGY & EXECUTION ROADMAP
The anti-research-project design rule: every version ships to real users, and every version's core artifact is permanent — later versions add organs, never transplant them. The three things frozen from V1 onward (get these right, everything else is replaceable): the ledger schema discipline, the bundle format, and the golden-corpus CI contract.

V0 — today's repository (lab, not product)
Honest status: research prototype; 15%-strict eval; graph emits unconditional approves. Disposition: keep as lab; extract three seeds — resolver → evaluator, eval harness → replay CI, skills JSON → bundle. Kill: graph-as-authority, demo theater as roadmap.

V1 — "The Decision Ledger" (first sellable product)
New primitive: the Ruling + the Bundle (signed, content-addressed, versioned).
Capability unlocked: one operational domain (refunds/discounts/credits) runs through deterministic policy with an escalation inbox, full audit trail, and replay-diff on every policy change — "CI for your refund policy."
Target user: Support/RevOps operations lead, 200–2,000-person B2B company.
Release criteria: 3 design partners; ≥90% of domain decisions flowing through (shadow counts); ≥5 real policy changes decided using the replay report; zero unexplained rulings.
Architecture introduced: append-only ledger (Postgres), pure Rust evaluator, bundle pipeline, escalation inbox, golden-corpus CI, Ed25519 signing, hash-chained log.
Deferred deliberately: warrants, agents, twin (a static role table suffices), simulation beyond replay, Temporal, transparency log proper.
Acceptable debt: manual ontology; Postgres queues; single-cell deployment; LangGraph internals.
Unacceptable debt: any non-deterministic enforce-path ruling; any uncited norm; any mutation of history; any ruling skipping the ledger. These four are constitutional from day one.
V2 — "The Policy Compiler"
Primitive: the typed Norm (KIR-Norm, internal).
Unlocked: multi-source compilation with conflict counterexamples ("your SOP and your finance policy disagree — here's the concrete scenario, with citations") and policy-as-PR review flow.
Why before V3: you cannot serve org-wide policy you cannot compile reliably; review efficiency is the gate.
Advance signal from V1: same customer demands a second domain; review-minutes-per-norm < authoring time.
V3 — "The Policy Plane"
Primitive: the Authority Binding (who may decide — org model v1, bitemporal).
Unlocked: org-wide multi-domain coverage; enforce-tier vs advise-tier split; edge evaluator sidecar in customer infra; drift report v1.
Deferred: full reconciler, capacity sim.
Advance signal: a customer connects an agent that wants to act, not draft — that pull, not internal ambition, triggers V4.
V4 — "The Warrant Runtime"
Primitive: the Warrant proper (attenuable, PoP-bound, revocable) + agent gateway + verifier SDKs + transparency log v1.
Unlocked: bounded, provable, revocable agent authority — the first system on which delegating real execution to agents is defensible to an auditor.
Unacceptable debt here: bearer-only tokens; revocation as best-effort; any warrant chain not rooted in a human.
V5 — "Twin & Simulator"
Primitive: the Counterfactual (simulation as first-class query).
Unlocked: drift reconciliation loop; Monte Carlo + escalation-capacity DES; M&A/reg-change dry-runs; adversarial policy fuzzing. (Sellable to the CFO/GC, not just ops.)
V6 — "The Institutional Kernel" (the name is earned here)
Primitive: the Immunity + the Power (constitution + amendment machinery, SMT-verified; verified reference evaluator; KIR spec v1 published, IR+verifier open-sourced).
V7 — "The Protocol"
Primitive: the cross-institutional warrant (kernel↔kernel contracts, machine-readable regulation interface, transparency federation, ZK where finally real).
Dependency graph & evolution

V1 Ledger ──▶ V2 Compiler ──▶ V3 Policy Plane ──▶ V4 Warrants ──▶ V6 Kernel ──▶ V7 Protocol
   │              │                │                   ▲               ▲
   │              └── conflict-CI ─┤                   │               │
   └── golden corpus ──────────────┴──▶ V5 Twin+Sim ───┴───────────────┘
        (grows monotonically; feeds every version; never resets)

PERMANENT from birth:  ledger schema · bundle format · golden-corpus contract ·
                       warrant format (V4) · KIR core (V2, frozen at V6)
REPLACEABLE by design: extraction models · vector index · LangGraph internals ·
                       UI framework · queue/workflow engine · storage engines behind views
Roadmaps. 1-year: V1 shipped + V2 in shadow at 3–5 design partners; corpus ≥ 2,000 golden scenarios; the four V1 constitutional rules never violated. 3-year: V3 live, V4 with first agent-executing customer + one flagship downstream verifier integration; edge evaluator in production; Temporal adopted; transparency log real. 5-year: V5 monetizing simulation to the C-suite; V6 constitution + published KIR; the corpus is the moat and everyone selling "agent governance" is either integrating your warrants or explaining why not.

Build vs buy by stage: Buy/adopt always: Postgres, NATS, S3, Z3, KMS/HSM, Temporal (V3+), SPIFFE (V4), frontier LLM APIs. Build always: KIR, evaluator, warrant format, bundle format, compiler passes, escalation/review surfaces, replay CI, drift reconciler. Never build: database, queue, chain, base model.

Research vs product tracks: product = everything on the V-path above; research (parallel, gated) = priority synthesis, semantic diffing/flip-budgets, precedent similarity, behavioral counterfactuals, ZK-over-bundles — each merges only by becoming a compiler pass or evaluator feature that passes the same golden CI, or it stays in the lab.

The diagrams
Complete system (mature):


                    ┌───────────────────────────────────────────────┐
                    │   CONSTITUTION (Immunities · Powers ·          │
                    │   amendment machinery · appeals) — Ring 0      │
                    └──────────────┬────────────────────────────────┘
 SOURCES                           │ constrains everything below
 stated (docs/SOPs) ─┐   ┌─────────▼─────────┐     ┌──────────────────────┐
 revealed (behavior) ─┼──▶│  COMPILER (P3)     │────▶│ BUNDLE REGISTRY      │
 adjudicated (rulings)┘   │ cite→type→conflict │     │ signed, content-     │
        ▲                 │ →verify→lower→CI   │     │ addressed, staged    │
        │                 └────────────────────┘     └──────────┬───────────┘
        │                                                       │ pull by hash
   ┌────┴─────────┐    ┌──────────────┐    ┌────────────────────▼──────────────┐
   │ LEARNING     │    │ SIMULATOR    │    │ RUNTIME  (two-speed)               │
   │ outcomes →   │    │ replay·MC·   │◀──▶│ reflexive (edge sidecars, pure) ·  │
   │ proposals    │    │ DES·fuzzing  │    │ deliberative (precedent+human)     │
   │ (never auto) │    └──────▲───────┘    └───────┬──────────────────┬────────┘
   └────▲─────────┘           │                    │ warrants         │ escalations
        │                     │            ┌───────▼───────┐   ┌──────▼────────┐
        │              ┌──────┴──────┐     │ AGENT GATEWAY  │   │ HUMAN SURFACES │
        └──────────────│   LEDGER     │◀────┤ identity·PoP·  │   │ inbox·policy-  │
             outcomes  │ append-only, │     │ attenuation·   │   │ PR·appeals     │
                       │ Merkle-      │     │ revocation     │   └────────────────┘
                       │ checkpointed │     └───────┬────────┘
                       └──────▲───────┘             │ verify offline
                              │              ┌──────▼──────────────┐
                       ┌──────┴───────┐      │ DOWNSTREAM SYSTEMS   │
                       │ ORG TWIN     │      │ (ERP/CRM/pay rails)  │
                       │ bitemporal · │      │ verifier SDKs — Kernl│
                       │ drift        │      │ authorizes, never    │
                       │ reconciler   │      │ executes             │
                       └──────────────┘      └──────────────────────┘
Compiler flow: sources → cite-gated extraction → normalize → ontology-bind → authority-bind → SMT conflict (counterexamples) → priority synthesis (human-gated) → verify invariants → lower (tables+Datalog+prose) → replay CI → signed bundle → shadow/canary/enforce.

Runtime flow: scenario → type+route → [reflexive: pure eval → warrant+derivation] | [deliberative: precedent retrieval → drafted ruling → human adjudication → precedent] → write-ahead ledger → exercise → outcome → learning.

Data flow: events in (sources, HRIS, exercises, outcomes) → ledger (truth) → materialized views (norm graph, twin, vectors, analytics) → bundles out (compiled) → warrants out (runtime) → checkpoints out (transparency).

Stack evolution: Y1: PG+S3+NATS+DuckDB+Rust-evaluator+Py-compiler → Y3: +Temporal+edge-sidecars+Merkle-log+SPIFFE+ClickHouse → Y10: +verified evaluator+KIR standard+protocol federation (+FDB only if forced).

Final word. The architecture's elegance test is that the whole thing reduces to one sentence with no hand-waving in it: a log of warrants, a compiler that turns cited institutional intent into pure functions, and a constitution enforced by types — everything else is views and surfaces. The current repo is roughly three disciplined quarters away from V1, and V1 is already a product someone can buy. The mountain is real, the path doesn't require rewrites, and the only way to lose is to ship demos instead of the ledger.