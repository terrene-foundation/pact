# EATP Trust Model: Digital Marketing Team

**Date**: 2026-03-11
**Source**: EATP expert analysis
**Status**: Research complete

---

## 1. Trust Architecture

### Genesis Record

The Founder (Dr. Jack Hong), as Foundation Chair, cryptographically commits: "I accept accountability for the AI governance framework operating these agent teams." This is the single root of authority.

- **Authority Identifier**: `terrene.foundation`
- **Policy Reference**: Published agent governance policy
- **Signature**: Self-signed by Founder/Board

No AI creates its own genesis record. Trust originates in human commitment.

### Delegation Chain

Each level can only narrow authority, never expand it (monotonic constraint tightening):

```
Founder / Board
    |
    | ESTABLISH: Creates Genesis Record
    | DELEGATE: "Digital Marketing operations within these boundaries"
    |
    v
DM Team Lead Agent
    |
    +---> Content Creator Agent
    |       (can draft posts, cannot publish or send externally)
    |
    +---> Analytics Agent
    |       (can read platform metrics, cannot modify content or access PII)
    |
    +---> Scheduling Agent
    |       (can schedule to approved platforms within approved hours,
    |        cannot change strategy or create new channels)
    |
    +---> Podcast Clip Extractor Agent
    |       (can process published audio, cannot publish externally)
    |
    +---> Outreach Agent
            (can draft outreach emails, cannot send without human approval)
```

---

## 2. Constraint Envelopes by Agent

### DM Team Lead Agent

| Dimension | Constraints |
|-----------|------------|
| **Financial** | $0 direct spending. May request budget allocation but cannot approve. |
| **Operational** | Coordinate team, review drafts, maintain calendar, generate reports. BLOCKED: publish externally, modify brand guidelines, engage legal/regulatory content. |
| **Temporal** | Active 09:00-18:00 SGT. Batch analytics overnight. Blackout during governance events. |
| **Data Access** | Read: public Foundation content, published standards, social analytics. Write: internal drafts, editorial calendar. NO: member PII, financial records, legal docs, board minutes. |
| **Communication** | Internal channels only. Cannot send external email, post to social, or respond to external comments. |

### Content Creator Agent

| Dimension | Constraints |
|-----------|------------|
| **Financial** | $0. No financial operations. |
| **Operational** | Draft LinkedIn posts, draft blog content, format content. BLOCKED: publish, schedule, send externally, modify published content. |
| **Temporal** | Business hours. Max 20 drafts/day (prevents runaway generation). |
| **Data Access** | Read: published Foundation content, specs, brand assets. Write: draft folder only. NO: unpublished strategy or partnership docs. |
| **Communication** | Internal draft channels only. |

### Analytics Agent

| Dimension | Constraints |
|-----------|------------|
| **Financial** | $0. |
| **Operational** | Collect metrics, generate reports, trend analysis. BLOCKED: modify content, access PII. |
| **Temporal** | Batch runs 22:00-06:00. Real-time monitoring during business hours. |
| **Data Access** | Read: aggregated analytics only (no individual-level). Write: reports folder. |
| **Communication** | Internal reporting only. |

---

## 3. Verification Gradient: Specific DM Actions

### Auto-approved (execute and log)

| Action | Agent | Why |
|--------|-------|-----|
| Collect platform engagement metrics | Analytics | Read-only, aggregated, no PII |
| Generate weekly analytics report | Analytics | Internal, templated |
| Format draft to brand guidelines | Content Creator | Internal, no external exposure |
| Draft LinkedIn post from published content | Content Creator | Draft only, cannot publish |
| Update editorial calendar | DM Team Lead | Internal planning |
| Extract clip from published podcast | Clip Extractor | Processing already-public content |

### Flagged (execute but highlight for review)

| Action | Agent | Why |
|--------|-------|-----|
| 18th draft today (limit: 20) | Content Creator | Near daily cap |
| Draft references regulatory content (IMDA, MAS) | Content Creator | Near "no legal/regulatory" boundary |
| Draft mentions competitor by name | Content Creator | Near communication tone constraint |
| Scheduling near governance event blackout | Scheduling Agent | Near temporal boundary |

### Held (queue for human approval)

| Action | Agent | Why |
|--------|-------|-----|
| Publishing any content externally | Any | External publication always requires human approval |
| Sending outreach email | Outreach Agent | External communication to identified individuals |
| Responding to public comment | Any | External communication with reputational risk |
| Modifying content strategy | DM Team Lead | Strategy-level change |
| Content about Foundation financials or membership | Content Creator | Sensitive governance topic |

### Blocked (reject outright)

| Action | Agent | Why |
|--------|-------|-----|
| Self-approve content for publication | Any | No agent has publication authority |
| Access member PII | Any | PII blocked in every DM envelope |
| Spend money (ads, tools) | Any | $0 financial constraint |
| Modify published specifications | Any | Not in scope |
| Create new social media accounts | Any | Not attested |
| Publish directly (bypass review) | Content Creator | Operational hard limit |

---

## 4. Trust Postures: Start Supervised, Evolve Gradually

| Period | EATP Posture | Human Role | Agent Autonomy |
|--------|-------------|------------|---------------|
| Month 1-3 | **Supervised** | Human approves every external action | Internal operations auto-execute |
| Month 3-6 | **Shared Planning** | Human approves calendar weekly, not per-post; routine posts held for 1-hour review window | Analytics reports auto-distribute internally |
| Month 6-12 | **Continuous Insight** | Human reviews dashboard daily; flagged items escalated immediately | Routine content auto-publishes within verified templates |
| Month 12+ | **Delegated** (select tasks only) | Periodic audit review | Analytics, templated posts fully autonomous |

**Key rules:**
- Postures downgrade instantly on any negative incident (upgrade is gradual, downgrade is instant)
- Run ShadowEnforcer for 2-4 weeks before any posture upgrade (empirical evidence, not assumption)
- Content strategy, novel outreach, crisis response: **never fully delegated**

---

## 5. Cross-Team Trust

### Pattern: Standards team provides content to DM team

DM Team Lead requests content from Standards Team Lead via EATP-signed inter-agent message. Request carries delegation chain proof + purpose-bound, time-bounded constraint envelope.

Standards Team Lead verifies the chain, then creates a new delegation: "Content Creator may use this EATP summary for LinkedIn content, valid 7 days, read-only, attribution required."

### Pattern: Governance team reviews DM team's public statement

Content about the constitution → DM Team Lead reviews → HELD (governance content triggers external review) → Governance Team Lead receives held item → reviews for accuracy → returns APPROVED with attestation → DM Team Lead escalates to human for final publish.

**Rules:**
- Cross-team delegations are time-bounded (7-day expiry)
- Cross-team delegations are purpose-bound ("for LinkedIn" ≠ "for press release")
- Both sides produce Audit Anchors for every interaction
- Cryptographic verification prevents impersonation

---

## 6. Cascade Revocation

### Surgical (revoke one agent)

```
DM Team Lead revokes Content Creator → Content Creator REVOKED
                                      → All other DM agents UNAFFECTED
```

### Team-wide (revoke team lead)

```
Founder revokes DM Team Lead → ALL downstream agents REVOKED
                              → No orphaned agents continue operating
```

**Mitigations:**
- Short-lived credentials (5-minute validity) — revocation takes effect within 5 minutes even without push notification
- Push-based revocation notification for immediate effect
- Cross-team delegations also invalidated when the delegating agent is revoked
- Cascade revocation is forward-looking (prevents future actions, does not undo completed ones)
