# Data Retention Policy — V1

**Status:** Policy of record for V1
**Date:** 2026-07-16
**Authority:** derived from `docs/Kernel_arc.md`'s constitutional rules (no mutation of history; no uncited norm) and `CLAUDE.md`
**Scope:** what Kernl retains, for how long, why, and what is honestly unsolved

---

## 1. The core tension, stated plainly

Kernl's product promise is a durable, tamper-evident decision ledger — "truth is a log" (`Product_summit.md`). The arc's constitutional rules make this literal, not aspirational: the ledger is append-only, bundles are content-addressed and immutable, and rollback moves a pointer rather than editing a row (`CLAUDE.md` rule 3). That is a *retention* commitment as much as an architectural one — a ledger you can quietly prune is not a ledger, it's a log file.

This creates a real tension with two things every production system eventually needs: the ability to purge genuinely disposable data (test tenants, abandoned drafts) and the ability to honor a data-subject deletion request against data that includes personal information. This document draws the line explicitly rather than leaving it implicit, and is honest about which side of that line V1 has actually built.

---

## 2. Retained indefinitely, by design (not a gap)

| Data | Where | Why indefinite |
|---|---|---|
| Ledger events (decisions, adjudications) | `decision_events` table / `PgLedgerStore` | This *is* the product. Every row is the hash-chained proof that a ruling happened, under what facts, against what bundle. Deleting one breaks the chain for everything after it. |
| Published bundles | `bundle` records, content-addressed by `bundle_hash` | Immutability is what makes "same content -> same hash" and replay-diff meaningful. A bundle that can disappear after publish undermines every trace that cites it. |
| Escalation resolutions / adjudications | Linked ledger events | Same reasoning as decisions — an adjudication is itself a ledgered ruling, not a scratch note. |
| Golden case corpus | Per-tenant case store | The corpus is the publish gate (`kernl-validation-and-qa`). Cases promoted from real adjudications are historical fact by construction. |

None of the above has (or should get) a delete/expire mechanism in the ordinary sense. If a decision was wrong, the correct action is a new adjudication event that supersedes it in the trace, not erasing the original — same principle as a corrected accounting entry, not a corrected accounting *system*.

---

## 3. Retained but genuinely disposable — currently NO cleanup mechanism (a real gap)

This is the honest part: as of 2026-07-16, **nothing in the codebase deletes any of the following.** Verified — `grep -rln "delete_tenant\|purge\|retention\|ttl\|expire" backend/` returns no hits outside test fixtures.

| Data | Where | Why it should be prunable | Current mechanism |
|---|---|---|---|
| Throwaway smoke/stress-test tenants (`smoke-<hex>`, `stress-<hex>`, `load-<hex>`) | Full tenant rows + their ledger/bundle/case data | Created by every run of `scripts/smoke_test.py` / `scripts/stress_test.py`. Purely diagnostic; this session alone created a dozen+ against live Supabase. Left unmanaged, they accumulate forever and pollute tenant listings. | None. `POST /v1/tenants` has no corresponding `DELETE`. |
| Abandoned draft bundles (never assembled/published) | `onboarding_drafts`, unassembled bundle records | A rejected or forgotten draft has no evidentiary value once superseded by a real published bundle. | None — drafts persist indefinitely regardless of status. |
| Source documents uploaded for grounding | `source_files` / `PgSourceStore` | May contain sensitive business text (refund policies, SOPs) uploaded during onboarding. Once a citation is grounded and the bundle published, the *citation* (source_id + span + excerpt) is what the ledger needs permanently — the full raw document is not. | None. |

**Direction for closing this gap** (not built in V1, scoped for whoever picks this up next):
1. A `DELETE /v1/tenants/{id}` endpoint gated the same way provisioning is (admin key), for full removal of non-production tenants. Straightforward — nothing about deleting an *entire* tenant's data violates the "no mutation of history" rule, because no partial/selective edit is happening; the whole append-only stream is being removed as a unit, the same way you can discard an entire logbook without it meaning you can tear out one page.
2. `scripts/smoke_test.py` / `scripts/stress_test.py` should self-clean on success (call the above endpoint at the end of a passing run) and print the tenant ID prominently on failure so a human can inspect before it's cleaned up manually.
3. A documented sweep (manual or scheduled) for `smoke-*`/`stress-*`/`load-*` tenants older than N days, once the delete endpoint exists.

---

## 4. Data-subject deletion requests (GDPR Art. 17 / CCPA) — unsolved, stated honestly

This is the one that doesn't have a comfortable answer yet, and V1 should not pretend otherwise.

If a decision event's `facts` payload contains personal data (e.g., a customer's purchase history used to evaluate a refund), and that person exercises a right to erasure, the constitutional "no mutation of history" rule is in direct tension with the legal requirement — you cannot edit a hash-chained ledger row without breaking the chain for every subsequent event, and you cannot delete it without leaving a gap the chain's `prev_event_hash` linkage will detect (correctly — that's the integrity guarantee working as designed).

**This is not solved in V1.** The honest options, for whoever scopes this next (this is a `kernl-change-control` decision, not something to resolve unilaterally in code):

- **Crypto-shredding**: encrypt PII fields within `facts`/`trace` at rest under a per-data-subject key; "deletion" destroys the key, not the row. The row (and hash chain) stays intact; its PII becomes permanently unrecoverable ciphertext. This preserves the chain's integrity guarantee while satisfying erasure — the standard pattern for exactly this conflict in append-only/immutable-ledger systems.
- **Minimize what's ledgered in the first place**: facts should ideally be the minimum typed fields a policy condition actually needs (`days_since_purchase`, not a full customer record) — the evaluator is already strict about only using declared fields (constitutional rule 1's strictness property, verified by `test_property_effective_facts_are_declared_fields_only`). Tightening what onboarding *allows* into a fact schema is a cheaper mitigation than building crypto-shredding, and should happen first.
- **What V1 does NOT do**: silently drop or redact ledger rows on request. That would violate the append-only guarantee for every other tenant's trust in the same mechanism, and would need to be a loud, audited, product-level decision — not a quiet support-ticket resolution.

Until one of the above is built, the operational answer to "we got an erasure request" is: minimize PII in facts at intake (the cheap mitigation above), and escalate anything already ledgered to `kernl-change-control` rather than improvising a fix.

---

## 5. API keys

Owner/approver/agent keys (`kk_...`) are stored only as hashes (`v1_api.py` — plaintext is shown once at provisioning, never again). There is currently no key rotation or revocation endpoint. Direction: a `POST /v1/tenants/{id}/keys` (issue) + `DELETE /v1/tenants/{id}/keys/{key_id}` (revoke) pair, following the same "keys, not the account, are revocable" pattern most API platforms use — out of scope to build speculatively here, noted so it's not forgotten.

---

## 6. Backups and infrastructure-level retention

Out of scope for this document — Postgres/Supabase backup retention is an infrastructure decision (point-in-time recovery window, backup encryption, backup access control), not an application-level policy. Whoever owns the Supabase project should set an explicit backup retention window and document it alongside this file; V1's application code makes no assumptions about backup existence or duration.

---

## Provenance

Written 2026-07-16 as part of closing Step 8's DoD ("retention policy documented," `docs/V1_EXECUTION_PLAN.md` build list). Re-verify the "no cleanup mechanism exists" claims in section 3 before trusting them if significant time has passed:

```bash
grep -rln "delete_tenant\|purge\|retention\|ttl\|expire" backend/*.py backend/*/*.py
grep -n "@router.delete" backend/v1_api.py
```
