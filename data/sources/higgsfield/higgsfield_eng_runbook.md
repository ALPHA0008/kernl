# Higgsfield AI — Engineering Operations Runbook
**Last updated:** February 2026 | **Owner:** Head of Engineering

---

## 1. Incident Classification & Response

### 1.1 Severity Definitions

**P0 — Critical (System Down)**
- Video generation pipeline completely unavailable
- API returning 5xx for >10% of requests over 5-minute window
- Authentication system failure affecting all users
- Data loss or data corruption confirmed

**P1 — High (Significant Degradation)**
- Generation latency exceeds 3x baseline for >20% of requests
- API error rate between 2–10% over 15-minute window
- Enterprise customer-specific outage
- Billing system not processing payments

**P2 — Medium (Partial Degradation)**
- Specific model or style unavailable
- Dashboard loading slowly (>5s for any page)
- Webhook delivery failures
- Single-region performance degradation

**P3 — Low (Minor Issue)**
- Non-critical UI bugs
- Documentation errors
- Single-customer edge case with workaround available

### 1.2 Response SLAs

| Severity | Acknowledge | First Update | Resolution Target |
|---|---|---|---|
| P0 | 5 minutes | 15 minutes | 2 hours |
| P1 | 15 minutes | 30 minutes | 4 hours |
| P2 | 1 hour | 2 hours | 24 hours |
| P3 | 8 hours | Next sprint | Best effort |

**SLA clock starts when incident is detected, not when it is reported.**

### 1.3 On-Call Escalation Path

```
Tier 1: On-call engineer (PagerDuty rotation, always assigned)
Tier 2: Engineering Lead (escalate if no response in 10 mins for P0, 20 mins for P1)
Tier 3: Head of Engineering (escalate if P0 not resolved in 45 minutes)
Tier 4: CTO (P0 incidents affecting >50% of enterprise customers, or any data loss)
```

**P0 rule:** On-call engineer MUST post in #incidents within 5 minutes of alert. If no post in 5 minutes, Engineering Lead gets automatically paged by PagerDuty. Do not wait.

**P1 enterprise rule:** When a P1 affects a named enterprise customer, the AE for that customer must be notified within 15 minutes — even outside business hours. Use the AE emergency contact list in Notion.

### 1.4 Incident Communication

**Internal (always required for P0/P1):**
- Open incident thread in #incidents channel immediately
- Update every 15 minutes for P0, every 30 minutes for P1
- Post all updates in the incident thread, not in general channels

**External (customer-facing):**
- P0: Update status page within 10 minutes of incident declaration
- P1 affecting enterprise: direct email to affected enterprise customers within 30 minutes
- P2: Status page update if expected resolution >4 hours
- NEVER tell a customer a resolution time you are not 80% confident in

---

## 2. Deployment Process

### 2.1 Standard Deployment

All deployments follow this process:
1. PR must have ≥2 approvals (at least 1 from a senior engineer)
2. All CI checks green (no bypassing for "quick fixes")
3. Deploy to staging, run smoke tests
4. Hold for 10 minutes in staging — watch error rates
5. Deploy to production during deployment window only

**Deployment windows:**
- Standard: Tuesday and Thursday, 10 AM – 2 PM PT
- Emergency (P0 hotfix only): any time, but requires Head of Engineering approval
- NEVER deploy on Friday after 2 PM PT or on weekends without explicit CEO sign-off

### 2.2 Rollback Criteria

Trigger immediate rollback if any of the following occur within 15 minutes of deployment:
- Error rate increases by >1% absolute
- P95 latency increases by >500ms
- Any P0 alert fires
- Generation success rate drops below 95%

Rollback is NOT optional — if criteria are met, roll back first, investigate after.

### 2.3 Feature Flags

All major features must be behind feature flags before production deployment:
- Flag naming: `ff_{team}_{feature_name}` (e.g., `ff_gen_turbo_mode`)
- New flags default to OFF in production
- Enterprise-only features: enabled per-account in the admin panel
- Do not enable a flag for >10% of production traffic without a monitoring period of at least 24 hours

---

## 3. Bug Triage Process

### 3.1 Bug Intake

All bugs reported via:
- Customer support tickets (auto-creates Jira via Zendesk integration)
- Internal Slack (#bugs channel)
- PagerDuty alerts (auto-P0/P1)

### 3.2 Triage Rules

**Auto-escalate to P0 if any bug report mentions:**
- "All videos failing" or "generation broken"
- "Can't log in" or "authentication error"
- "Charged twice" or "billing error" from enterprise customer

**P1 criteria:**
- Enterprise customer reports a reproducible bug affecting their workflow
- Same bug reported by 3+ distinct users within 24 hours
- Any bug affecting the API that has a documented workaround but the workaround is non-trivial

**Assignment rules:**
- P0 and P1 bugs: assigned to on-call engineer immediately, regardless of their sprint commitments
- P2 bugs: triaged in next daily standup, assigned to appropriate team
- P3 bugs: added to backlog, reviewed in sprint planning

### 3.3 Customer-Reported Bug Workflow

1. Support creates Jira ticket with full repro steps
2. Engineering triages within SLA window
3. If fix requires >4 hours work for a P1: customer gets interim workaround communication
4. On fix deployment: support notified via Jira comment automatically
5. Support closes customer ticket with resolution note

**Do not tell a customer a bug is "fixed" until the fix is in production, not just deployed to staging.**

---

## 4. Database Operations

### 4.1 Production Database Rules

- No direct writes to production DB without a migration file reviewed by Head of Engineering
- All schema changes require downtime window if they involve column removal or type changes
- Read replicas available for analytics queries — NEVER run heavy analytics on primary

### 4.2 Data Deletion Policy

- Customer data deletion requests (GDPR/CCPA): must be completed within 30 days
- Soft-delete first, hard-delete after 14-day hold period
- Deletion of enterprise customer data: requires written confirmation from their legal contact
- DO NOT delete any data while a legal hold is active — check legal-holds list in Notion before any bulk deletion

### 4.3 Backup & Recovery

- Automated backups every 6 hours, retained for 30 days
- Point-in-time recovery available for last 7 days
- RTO (Recovery Time Objective): 2 hours for P0 data recovery scenario
- Test restoration process quarterly — log results in #engineering-ops

---

## 5. Security Incident Response

### 5.1 Security Incident Classification

**Critical:**
- Confirmed unauthorized access to customer data
- API keys or secrets exposed in public repository
- Active exploitation of a vulnerability

**High:**
- Suspected unauthorized access (unconfirmed)
- Internal credentials phishing attempt that succeeded
- Third-party dependency with confirmed CVE being actively exploited

### 5.2 Security Response

For any Critical security incident:
1. Isolate affected system immediately (even if it causes downtime)
2. Notify CTO + Head of Engineering within 10 minutes — do NOT post in public Slack channels
3. Engage security counsel if customer data is involved
4. Customers affected by data breach: notify within 72 hours per GDPR requirements

**NEVER disclose a security incident on public channels, social media, or to customers before CTO approval of messaging.**
