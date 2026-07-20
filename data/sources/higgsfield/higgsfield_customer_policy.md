# Higgsfield AI — Customer Policy & Operations Handbook
**Last updated:** March 2026 | **Owner:** Head of Customer Success

---

## 1. Subscription & Refund Policy

### 1.1 Standard Refund Rules

Higgsfield operates on a credits-based subscription model. The following rules apply:

**Annual subscribers:**
- Full refund within 14 days of initial purchase, no questions asked
- After 14 days: prorated refund based on unused credits — calculated as `(unused_credits / total_credits) * annual_price`
- Customer must not have used more than 20% of their credit allocation
- If usage exceeds 20%, no refund is issued — offer a 2-month extension instead

**Monthly subscribers:**
- Refund only within 48 hours of billing cycle start
- After 48 hours: no monetary refund — issue account credit equal to 50% of monthly charge
- Account credit is valid for 60 days only

**Enterprise accounts:**
- NEVER deny a refund request outright without Account Executive (AE) sign-off
- All enterprise refund requests must be escalated to AE within 2 hours regardless of amount
- AE has authority to approve up to $10,000 in refunds independently
- Above $10,000: requires VP of Revenue + AE approval
- Enterprise SLA: refund decision communicated within 4 business hours

**API-only customers:**
- No refunds on consumed API credits under any circumstances
- Unused prepaid API credits: refundable within 30 days of purchase
- After 30 days: convert to account credit only, valid for 90 days

### 1.2 Credit Expiration Policy

- Free tier credits: expire after 30 days of account inactivity
- Paid tier credits: expire 90 days after end of subscription period
- Enterprise credits: do not expire as long as contract is active
- **Exception:** If a customer downgrades mid-cycle, their legacy credits expire at the original cycle end date, not extended

### 1.3 Refund Fraud Signals

Escalate to fraud review (do not process refund) if:
- Customer has requested refunds 2+ times in the past 6 months
- Account was created less than 7 days ago and the refund amount exceeds $200
- Credit card country does not match stated company country
- Usage pattern shows bulk generation followed immediately by refund request

---

## 2. Plan Changes & Downgrades

### 2.1 Upgrade Flow

- Upgrades take effect immediately
- Customer is charged the prorated difference for remaining days in billing cycle
- Credits from old plan are preserved and added to new plan allocation

### 2.2 Downgrade Flow

- Downgrades take effect at the START of next billing cycle — never mid-cycle
- Notify customer 3 days before downgrade takes effect
- If customer has excess credits beyond new plan limit: those credits are forfeited — DO NOT extend them
- **Exception:** Enterprise customers requesting downgrade — always loop in AE before confirming. AE may negotiate retention.

### 2.3 Plan Cancellation

- Customer can cancel at any time; access continues until end of billing period
- Do not offer a discount to retain unless the customer has been active for 6+ months AND their MRR is above $500
- For Enterprise: cancellation requires 30-day written notice per contract — forward all cancellation requests to AE immediately, even if customer says they just want to "pause"

---

## 3. Content & Generation Policy

### 3.1 Content Violations

**Tier 1 violations (warning issued, content removed):**
- Generating content that mimics a real public figure without watermark
- Explicit content generated on standard plan (explicit content is only available on Enterprise with content unlocking addendum)
- Generating content using competitor brand assets

**Tier 2 violations (account suspended 7 days + warning):**
- Second Tier 1 violation within 90 days
- Generating synthetic media intended to deceive (deepfakes for impersonation)
- API abuse: more than 3x the plan rate limit in any 1-hour window

**Tier 3 violations (permanent ban + legal referral):**
- Generating CSAM or content involving minors in any explicit context
- Using the platform for coordinated disinformation campaigns
- Attempting to reverse-engineer model weights via API probing

**Escalation path for violations:**
- Tier 1: Support agent handles, logs to #content-moderation Slack channel
- Tier 2: Support lead + Legal notified within 1 hour of detection
- Tier 3: Immediate account suspension (no warning), CEO + Legal notified within 30 minutes

### 3.2 Dispute Process

If a customer disputes a content violation:
- They have 72 hours to submit an appeal via email
- Appeals reviewed within 3 business days
- Tier 1 appeals: Support Lead reviews, can reverse the warning
- Tier 2 appeals: Head of Trust & Safety reviews — NOT overridable by support
- No appeals for Tier 3 violations

---

## 4. SLA & Support Response Times

| Customer Tier | First Response | Resolution Target |
|---|---|---|
| Free | 72 hours | Best effort |
| Pro (monthly) | 24 hours | 48 hours |
| Pro (annual) | 12 hours | 24 hours |
| Enterprise | 2 hours | 8 hours |
| Enterprise (P0 incident) | 15 minutes | 4 hours |

**SLA breach procedure:**
- If a Pro annual customer has not received a first response within 12 hours: automatically escalate to Support Lead
- If an Enterprise customer has not received a response within 2 hours: immediately page the on-call support engineer AND notify their AE
- SLA breach compensation for Enterprise: 10% credit on next invoice per breach, up to 30% in any single billing period

---

## 5. Churn & Retention

### 5.1 Churn Risk Signals

Classify an account as "at-risk" if ANY 3 of the following are present in a 30-day window:
- No logins in 14+ days
- Credit usage below 20% of allocation
- Open support ticket with no resolution
- Downgrade inquiry or cancellation mention
- NPS score below 6

**Response to at-risk account:**
- Pro tier: automated email sequence (3 emails over 7 days)
- Annual Pro: assign CSM touch within 48 hours
- Enterprise: AE call required within 24 hours, no automated emails

### 5.2 Win-Back Policy

For churned customers attempting to reactivate:
- Within 30 days of churn: restore previous credits at no charge, no questions asked
- 30–90 days: 50% credit on first month reactivation
- Beyond 90 days: standard pricing, no discount without VP approval
