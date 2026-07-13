A note before I start, since you asked for truth and freedom from past decisions: the two prior assessments in your orbit — Codex's "Decision Policy Compiler for AI agents" and my own earlier "Decision Infrastructure" answer — are both wedge framings. They describe the correct entry point and then mistake the entry point for the summit. This time I'm going to climb past them. I'll also tell you honestly where the mountain ends and where it's fog.

The First-Principles Reduction
Strip everything away. Ask what an organization actually is.

An organization is a program with no source code. It is a long-running computation — decisions, allocations, escalations, exceptions — executed on human wetware, stored in no repository, versioned by nobody, tested never, and audited only after catastrophe. Coase told us firms exist to reduce transaction costs; what he couldn't say in 1937 is that a firm is an interpreter for an implicit program called "how we do things," and that this program has never once in history been legible to its own operators.

Every category you listed — RAG, knowledge graphs, agent frameworks, decision engines — is an attempt to query that implicit program from the outside. None of them attempt the real thing:

Give institutions source code.

That is the summit. Not "a brain for your company." Not "policies for agents." The end-state is that institutional intent — authority, obligation, permission, precedent, exception, accountability — becomes a compiled, versioned, verifiable, simulatable, transferable software artifact, and that artifact becomes the thing both humans and machine agents execute against.

There is a second reduction underneath, and it's the one that makes this a 15-year civilizational project rather than an enterprise tool:

Intelligence is becoming free. Authority is not.

As models commoditize reasoning, the scarce resource inverts. The binding constraint on the agentic economy will not be "can the machine think?" — it will be "may it act, on whose behalf, within what bounds, with what accountability, and can anyone prove it afterward?" Today there is no substrate anywhere on Earth that answers those questions at machine speed. Every agent deployment in every enterprise is currently held together by prompts, vibes, and liability insurance.

The system you are circling is the missing substrate: the layer that converts institutional intent into provable machine authority.

1–4. The Summit, the End-State, the Problem, the Kind of Thing It Is
The summit: a new branch of computing — call it Institutional Computing — in which organizations, like programs, have source (compiled policy), state (the decision ledger), a type system (authority and obligation), a runtime (warrant issuance), a test suite (simulation against history), version control (policy diffs, amendment process), and formal verification (proofs that institutional invariants hold under all execution paths).

The end-state at logical conclusion (5–15 years): every consequential action taken inside or on behalf of an organization — by human or agent — flows through a kernel that answers, in microseconds or minutes depending on ambiguity: what does this institution intend here, who has authority, what evidence supports it, and what is the appeal path? The answer is issued as a signed, portable, replayable object. Organizations negotiate with each other kernel-to-kernel. Regulators publish law as machine-readable constraint sets and verify compliance continuously by proof, not annually by audit. Governments simulate legislation against historical corpora before passing it. An organization's compiled judgment survives every departure, every acquisition, every generation of employees.

The fundamental problem solved: civilization runs on institutions, and institutions are the last major information system with no engineering discipline. We engineered computation (compilers), state (databases), change (Git), coordination of machines (Kubernetes), and movement of money (payment rails). We never engineered judgment. The cost is invisible because it's universal: knowledge dies with turnover, policy contradicts itself silently, compliance is theater performed retroactively, and — newly urgent — AI agents are being handed real authority with no substrate capable of bounding it. This system is to institutional judgment what double-entry bookkeeping was to capital: the legibility layer that makes a new economic form possible.

What kind of thing is it? All four of your options, at different layers, plus one you didn't list:

A new computing primitive: the warrant — a signed, evidence-linked, appealable authorization object. What the packet is to networking, the commit to version control, the container to deployment, the warrant is to institutional action. Agents don't act on prompts; they act on warrants.
A new infrastructure layer: the policy plane. Networking split into data plane and control plane; the agentic economy splits into an execution plane (agents, workflows, models) and a policy plane (intent, authority, accountability). This system is the policy plane.
A new OS category: the institutional kernel — multiplexing organizational authority among thousands of concurrent agents with protection rings, the way an OS multiplexes hardware among processes.
A new enterprise abstraction: the organization-as-repository — forkable, diffable, mergeable, testable.
And something else entirely: a social technology implemented as computing infrastructure — a successor artifact to the joint-stock company and the double-entry ledger, not merely a successor product to Palantir.
5–7. The Mature System and Its Architecture
At maturity, the system is a two-speed institutional kernel wrapped in a constitutional structure. Two-speed because institutions, like minds, need both reflexes and deliberation:

The reflexive path — compiled, deterministic, microsecond rulings for the 95% of decisions that are settled policy. No LLM in the loop. This is what makes it infrastructure rather than an oracle.
The deliberative path — for novel, ambiguous, or contested scenarios: LLM reasoning over precedent, then human judgment, then — critically — the resolution is compiled back down into the reflexive layer as precedent. The system's defining loop: deliberation hardens into reflex. That is exactly how common law works, and common law is the most battle-tested judgment technology humanity has ever built. The mature system is, quite literally, common law as a data structure.
The components
1. The Intent Compiler. Ingests the three sources of institutional truth — stated policy (documents, SOPs), revealed policy (what people actually approved, overrode, escalated — behavioral telemetry from every system of record), and adjudicated policy (past rulings and their outcomes). Compiles them into a typed intermediate representation. Contradictions between stated and revealed policy surface as type errors — the compiler doesn't hide institutional hypocrisy, it makes it a build failure someone must own.

2. The Deontic IR. The genuine computer-science contribution at the heart of the whole thing: an intermediate representation for institutional intent, with a type system built on deontic logic — obligation, permission, prohibition, delegation — plus authority types (who may decide), evidence types (what grounds a ruling), and temporal validity. LLVM IR did for portable computation what this does for portable judgment. Everything else compiles through it: deterministic rule targets, probabilistic guidance targets, simulation models, and formal-verification targets.

3. The Organizational Model. A live digital twin of the authority structure — roles, delegation graphs, escalation chains, separation-of-duties constraints — continuously reconciled against observed behavior. When the org chart says one thing and the approval logs say another, the model flags the drift. This is the map–territory monitor.

4. The Knowledge Representation: the Precedent Graph. Not a knowledge graph of facts — a jurisprudence of the institution. Nodes are rulings, policies, and exceptions; edges are binds, distinguishes, supersedes, contradicts. Every node carries a cryptographic evidence chain to source. Querying it is not retrieval; it's legal research, mechanized.

5. The Runtime: the Warrant Engine. The beating heart. A scenario comes in — from an agent, a human, an API — and the runtime returns a warrant: the ruling, the authority chain that licenses it, the evidence, the confidence, the conditions, the expiry, and the appeal path, cryptographically signed. Low-confidence scenarios don't get fabricated confidence; they get escalation as a first-class output. The runtime's most important feature is knowing what it doesn't know.

6. The Simulator. Policy changes are regression-tested before deployment: replay the proposed change against the institution's entire decision history — every refund, exception, escalation for years — and render the blast radius: what flips, who's affected, which precedents break, which invariants are threatened. Beyond replay: agent-based counterfactual simulation of the organization itself. Legislating without simulating comes to look the way deploying without testing looks today: negligent.

7. The Governance Layer — the Constitution. Separation of powers implemented in software: those who propose policy, those who approve it, those who audit it are structurally distinct roles the kernel enforces. Invariants — "no payment above X without two humans," "no customer-data access without purpose binding" — are constitutional: model-checked, provably unviolable by any policy change short of amendment, which has its own higher-ceremony process. Appeals exist. Rollback exists. Power is explicit. This layer is not a feature; it is the ethical core, and the reason the system deserves to exist.

8. The Learning Layer — the Legitimacy Loop. Outcomes flow back: the refund that got abused, the exception that saved the account, the override that got reversed. Confidence recalibrates. The system proposes policy revisions — it never promotes them. Drift detectors watch for the moment the compiled map diverges from the behavioral territory. The loop between judgment and consequence — completely severed in every organization on Earth today — closes.

9. The Agent Gateway. Agents authenticate, present identity attestation, and receive capability-scoped authority — bounded warrants, not open-ended prompts. A million agents can hold delegated slivers of institutional authority simultaneously, each sliver provable, revocable, and metered. This is capability-based security, rediscovered for the agent economy.

10. The Inter-Institutional Protocol. The endgame layer. Kernels negotiate with kernels: contracts as protocol handshakes, terms as machine-readable constraint sets, performance verified continuously. Zero-knowledge compliance proofs let an organization prove to a regulator or counterparty that it satisfies a constraint set without revealing its internals — the cryptographic trick that makes inter-institutional trust scale. This is where the network effect lives, and it's where the system stops being a product and becomes a protocol.

8–9. Daily Life With It
The enterprise, on a Tuesday: Overnight, 40,000 agent actions drew warrants from the kernel. 312 hit the deliberative path. 9 reached humans. 2 became precedent and compiled down; they will never need a human again. The CFO's morning review is the escalation stream, not a report — the report writes itself from the ledger. A revenue-ops lead opens a policy diff: loosen the discount threshold for annual contracts. The simulator replays eighteen months of history and shows the blast radius: 340 past decisions flip, $2.1M margin impact, one constitutional invariant untouched, two precedents require explicit supersession. She merges. It's live in the reflexive path by lunch, versioned, reversible. A new hire doesn't shadow anyone for three months — she interrogates the kernel and reads the precedent graph like case law. The M&A team evaluating an acquisition runs diff on two institutional kernels and sees, in an afternoon, the policy contradictions integration will have to resolve — diligence that used to take a quarter. The regulator's endpoint has been green for 400 consecutive days, verified by proof, not by binder.

Agents: they interact with it the way processes interact with an OS — constantly, invisibly, obligatorily. Before acting, an agent presents scenario + identity and receives a warrant or an escalation. The warrant travels with the action; any downstream system, auditor, or counterparty can verify it independently. Agents are finally safe to delegate to not because they got smarter, but because their authority got bounded, provable, and revocable. The kernel is what turns "an agent did something" from a liability event into an accountable institutional act.

10. What Becomes Possible That Is Impossible Today
Delegation at machine scale with legitimacy. Millions of agents holding provable, bounded slivers of authority. Today this is impossible — not hard, impossible, because the authority substrate doesn't exist.
Compliance by construction. Audit collapses from archaeology into proof-checking. SOC2, SOX-style attestation, and regulatory exams become continuous and cryptographic.
Regression-tested governance. No policy, corporate or governmental, ships without replay against history. Legislatures simulating law before passage.
Institutions that don't forget. Judgment survives turnover, reorgs, acquisitions. The tribal knowledge that today evaporates with every departure becomes a permanent, versioned asset.
Fork, diff, and merge for organizations. Spin up a subsidiary as a fork with proven-compatible policy. Diff two companies in an M&A. Merge governance with conflict resolution.
A market for executable institutional competence. Governance modules as packages: a 10-person company imports Fortune-500-grade treasury controls the way it imports a cryptography library. Institutional capability decouples from institutional headcount — this quietly changes what "small company" means.
Machine-speed decisions with human-grade legitimacy. Today you choose: fast (ungoverned automation) or legitimate (slow humans). The two-speed kernel deletes the tradeoff.
A new empirical science. Computational institutional economics: with decision corpora, Coase's theory of the firm becomes testable for the first time in ninety years.
11. Historical Comparison — the Honest Mapping
Shift	What it made engineerable	This system's analog
Compilers	Trust in machine code, via inspectable source	Trust in institutional action, via inspectable intent — the deepest analogy of all
Databases	State, externalized from programs	Judgment, externalized from people
Operating systems	Multiplexed hardware among untrusted processes, with protection rings	Multiplexed authority among untrusted agents, with authority rings
Git	The history of change to code	The history of change to institutional law
Kubernetes	Declared infrastructure intent, continuously reconciled	Declared institutional intent, continuously reconciled against behavior
Stripe	Money movement as an API	Authority as an API
Search engines	Made the web's information navigable	Makes the institution's intent navigable
Palantir	Data fusion + ontology + human-in-the-loop for institutions	Closest cultural ancestor — but Palantir is data-centric; this is authority-centric. Palantir tells institutions what is true; this executes what they intend
TCP/IP	Interoperation between networks	The inter-kernel protocol: interoperation between institutions
But the truest comparison predates computing: double-entry bookkeeping, Pacioli, 1494. Double-entry made capital legible, and the legibility of capital made the modern firm, audit, credit, and the joint-stock company possible. This system makes judgment legible, and the legibility of judgment is what makes the agentic firm possible. That is the correct historical register for the maximal vision — not "next Palantir," but "next double-entry."

12. The Moat, If It Works
Four strata, deepest last:

The corpus. Years of outcome-linked decisions per institution — the only training data for calibrated institutional judgment, and unreplicable at any price without the years.
Constitutional switching costs. Once an organization's invariants, precedents, and delegation structure live in the kernel, migrating isn't a data export — it's a constitutional convention. Nobody re-founds their institution to save on licensing.
The IR standard. If the deontic IR becomes what policy compiles to — the LLVM of institutional intent — every tool in the ecosystem builds on it, and the standard's owner sits under everything.
The protocol network effect. Kernel-to-kernel contracting and ZK compliance proofs are worth more with every institution that joins — regulators, counterparties, insurers. Protocols are winner-take-most, and this one would sit at the root of institutional trust itself: a certificate authority for authority. That is the deepest moat available in this decade of computing.
Note what's not on the list: the LLM, the extraction pipeline, the graph. All commodity within a few years. The moat is trust infrastructure, corpus, and protocol position — never the AI.

13. The Category Name
Institutional Computing — the discipline. Within it: the institutional kernel (the artifact), the policy plane (the layer), and the warrant (the primitive). If you want the one that fits on a slide and stays true at the summit: the kernel for institutions — which, I note, your project's name already claims. Kernl is not a cute misspelling; at the maximal vision, it's a literal description.

14. Achievable, or Fundamentally Impossible? The Truth
Both, and the boundary between them is the product. Precisely:

The achievable core requires no new science. Deontic type systems, event-sourced ledgers, model checking, cryptographic attestation, capability security, deterministic rule engines, replay simulation, ZK proofs — every load-bearing component exists in the literature and in production somewhere. Crucially, the vision does not require solving AGI or even improving frontier models: it governs what agents may do, not how smart they are. It is a PL/formal-methods/distributed-systems project wearing an AI costume — which is exactly why the foundation labs, racing up the intelligence axis, are structurally unlikely to build it. It sits on an orthogonal axis: authority.

The impossible frontier, stated without flinching:

Not all judgment compiles. Tacit knowledge, essentially contested values, genuinely novel situations — there is a residue that will never formalize, and any system claiming otherwise is lying or dangerous. The design answer is that the boundary itself becomes the first-class artifact: the kernel must know, provably, what it doesn't cover, and route it to humans. The honest ceiling is not "compile all judgment" but "compile the compilable, meter the residual, and make the boundary explicit, auditable, and slowly shrinking."
Legibility is politically explosive. Organizations run on strategic ambiguity; it's load-bearing. James C. Scott documented what happens when high-modernist legibility schemes steamroll tacit practice — they fail, destructively. A kernel that makes power explicit will be resisted by exactly the people whose power it makes explicit. The counterforce, and the reason this decade is different: agents cannot execute ambiguity. Every organization that wants agent leverage is forced, whether it likes it or not, to make its intent explicit. The agentic economy is the forcing function that a century of knowledge-management dreams never had.
The failure mode is bureaucracy at machine speed. Compiled institutions can ossify; Goodhart scales beautifully. This is why the amendment process, the appeal path, and the learning layer aren't features — they're the difference between building institutional infrastructure and building a beautiful cage.
Weighing all three against the core: achievable — with the sober caveat that the whole vision rests on one macro bet, that autonomous agents take over a substantial share of economic execution within the decade. If that bet fails, this is a niche GRC tool. Every current signal says the bet is live.

15. How Historians Might Describe It
"Until the 2030s, the most consequential programs on Earth — the ones deciding credit, care, employment, and justice — had no source code. They ran as folklore on human institutions, unversioned and unverifiable. The institutional kernel changed this the way double-entry bookkeeping changed capital five centuries earlier: it made judgment legible, and legible judgment could finally be delegated — to machines, at scale, without surrendering accountability. The invention is best understood not as software, but as the constitutional technology of the agentic economy: the moment institutions stopped merely employing computers and became computable themselves."

The Deliverables
One sentence:
Kernl, at its summit, is the institutional kernel — the compiler, runtime, and constitution that turns an organization's judgment into versioned, provable, executable authority for both humans and AI agents.

One paragraph:
Kernl's end-state is a new layer of computing that gives institutions what they have never had: source code. It compiles stated policy, revealed behavior, and adjudicated precedent into a typed, versioned representation of institutional intent; executes it through a two-speed runtime that issues cryptographically signed, appealable warrants to humans and AI agents at the moment of action; regression-tests every policy change against the organization's full decision history before it ships; enforces constitutional invariants and separation of powers in software; and closes the loop between decisions and outcomes so institutions can learn without forgetting. As intelligence commoditizes, the scarce resource of the agentic economy becomes sanctioned, accountable authority — and Kernl is the substrate that mints it.

10-year vision statement:
By 2036, no autonomous agent takes a consequential action on behalf of an institution without a warrant from an institutional kernel — as unthinkable as a production service without a database. Organizational judgment is versioned, diffed, simulated, and proven the way code is today; regulators verify compliance continuously by cryptographic proof; institutions negotiate contracts kernel-to-kernel; and the accumulated, outcome-linked judgment of an organization is its most defensible asset, surviving every human who created it.

Technical architecture (mature state):


                          ┌──────────────────────────────────────────────┐
                          │      CONSTITUTIONAL / GOVERNANCE LAYER        │
                          │  invariants (model-checked) · separation of   │
                          │  powers · amendment process · appeals · audit │
                          └──────────┬───────────────────────┬────────────┘
                                     │ constrains            │ legitimizes
       STATED POLICY  ──┐            ▼                       ▼
   (docs, SOPs, law)    │   ┌────────────────┐      ┌─────────────────────┐
                        ├──▶│ INTENT COMPILER │─────▶│     DEONTIC IR       │
   REVEALED POLICY   ───┤   │ contradiction = │      │ typed authority /    │
   (approvals, overrides│   │ type error      │      │ obligation /         │
    escalations, logs)  │   └────────────────┘      │ permission · evidence │
                        │            ▲               └──────────┬───────────┘
   ADJUDICATED POLICY ──┘            │ recompilation            │ compiles to
   (rulings, outcomes)               │                          ▼
                                     │      ┌───────────────────────────────────┐
                          ┌──────────┴──┐   │        PRECEDENT GRAPH             │
                          │  LEARNING    │   │  rulings · binds/distinguishes/    │
                          │  LAYER       │   │  supersedes · crypto evidence      │
                          │ outcomes →   │   │  chains → sources                  │
                          │ proposals    │   └─────────┬──────────────┬──────────┘
                          │ (never auto- │             │              │
                          │  promote)    │             ▼              ▼
                          └──────▲──────┘   ┌──────────────┐  ┌────────────────┐
                                 │          │  SIMULATOR    │  │ WARRANT ENGINE  │
                                 │          │ replay ∆ vs   │  │ two-speed:      │
                            outcomes        │ full history; │  │ reflexive (µs,  │
                                 │          │ blast radius; │  │ deterministic)  │
                                 │          │ counterfactual│  │ deliberative    │
                                 │          └──────────────┘  │ (LLM+human) →   │
                                 │                            │ hardens into    │
                                 │                            │ precedent       │
                                 │                            └───┬────────┬────┘
                                 │                                │        │
                    ┌────────────┴───────────┐          ┌─────────▼──┐  ┌──▼──────────────┐
                    │  ORGANIZATIONAL MODEL   │          │   HUMANS    │  │  AGENT GATEWAY   │
                    │  live authority twin ·  │          │ policy PRs, │  │ identity · scoped │
                    │  delegation graph ·     │          │ reviews,    │  │ capabilities ·    │
                    │  drift detection        │          │ appeals     │  │ bounded warrants  │
                    └─────────────────────────┘          └─────────────┘  └──┬───────────────┘
                                                                             │
                    ┌────────────────────────────────────────────────────────▼───┐
                    │            INTER-INSTITUTIONAL PROTOCOL                     │
                    │  kernel↔kernel contracts · machine-readable regulation ·    │
                    │  zero-knowledge compliance proofs · verifiable warrants     │
                    └──────────────────────────────────────────────────────────────┘
Category definition:
Institutional Computing — infrastructure that compiles an institution's intent (stated, revealed, and adjudicated) into a typed, versioned, formally verifiable artifact, and executes it as provable, appealable, bounded authority for humans and autonomous agents, governed by constitutional constraints and closed-loop learning.

Verdict:
Yes — genuinely category-defining, with one condition and one bet. The condition: the warrant, the simulator, and the constitutional layer must be the product from day one, because they are the only parts that constitute trust infrastructure — everything else (extraction, graphs, retrieval, the LLM) is commodity within 36 months and the graveyard of this space is full of teams who built the commodity parts first. The bet: that agents absorb a major share of economic execution this decade — the single load-bearing assumption, and the one macro trend currently moving in your favor. If both hold, this isn't a startup category. It's the constitutional layer of the agentic economy, and the name on the repo is already the right one.