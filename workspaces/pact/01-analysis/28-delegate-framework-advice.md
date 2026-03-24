# Framework Selection Analysis: PACT Work Management Layer

**Date**: 2026-03-23
**Context**: Delegate integration brief calls for ~15 DataFlow models, ~10 API routers, ~10 services
**Inputs**: Existing governance stores (direct SQLite), existing FastAPI server, DataFlow/Nexus capabilities

---

## Executive Summary

Use DataFlow for the work management layer. Keep direct SQLite for governance stores. Extend the existing FastAPI server rather than replacing with Nexus. Add PostgreSQL via DataFlow's native support.

---

## 1. DataFlow vs Direct SQL

### Recommendation: DataFlow for work management. Keep direct SQLite for governance.

The governance stores are **trust-critical infrastructure** — parameterized queries, `_validate_id()` on every input, `_write_lock` on every mutation, bounded collections, hash-chained audit logs. They have 968 tests and 10+ red team rounds. Rewriting to DataFlow would lose Protocol-based dependency injection and recreate security invariants.

The work management layer needs: 11+ models with varied schemas, complex query patterns, bulk operations, upsert patterns, pagination. DataFlow gives 11 nodes per model = 121 auto-generated nodes from ~200 lines of model definitions. Writing that as direct SQLite would mean ~3,000 lines of hand-rolled SQL.

**Coexistence pattern:**

```
GovernanceEngine (Layer 1)
  -> SqliteOrgStore, SqliteEnvelopeStore, etc. (direct SQLite, protocol-based)
  -> Trust-critical, red-team validated

WorkManagementService (Layer 3)
  -> DataFlow models: AgenticObjective, AgenticRequest, etc.
  -> Operational data, not trust-critical
  -> Auto-generated CRUD nodes, bulk ops, pagination
```

They share a process but not a database connection.

---

## 2. Nexus vs Existing FastAPI

### Recommendation: Extend existing FastAPI now. Add Nexus later.

The existing server has production-hardened middleware (auth, rate limiting, security headers, body size limits, CORS, WebSocket with auth, graceful shutdown, Prometheus). Nexus doesn't replicate this. The `PactAPI` class already follows a framework-agnostic pattern.

Add Nexus when PACT needs MCP tool exposure of work management operations (Priority 4+).

---

## 3. Model Design (11 models)

### 3.1 AgenticObjective

Top-level unit of work. Fields: id, org_id, title, description, submitted_by, status (draft|active|completed|cancelled), priority, deadline, timestamps, metadata.

### 3.2 AgenticRequest

Decomposed task. Fields: id, objective_id, org_id, title, description, assigned_to, assigned_type, claimed_by, status (pending|claimed|in_progress|review|completed|blocked|cancelled), priority, sequence_order, depends_on (JSON), envelope_id, deadline, timestamps, metadata.

### 3.3 AgenticWorkSession

Active work period with cost tracking. Fields: id, request_id, worker_address, status, timestamps, input_tokens, output_tokens, cost_usd, provider, model_name, tool_calls, verification_verdicts (JSON), metadata.

### 3.4 AgenticArtifact

Produced deliverable. Fields: id, request_id, session_id, artifact_type, title, content_ref, content_hash, version, parent_artifact_id, created_by, status, timestamps, metadata.

### 3.5 AgenticDecision

Human judgment point. Fields: id, request_id, objective_id, decision_type, title, description, options (JSON), decided_by, decision, reason, status (pending|decided|expired), deadline, timestamps, metadata.

### 3.6 AgenticReviewDecision

Review outcome. Fields: id, request_id, reviewer_address, verdict (approved|revision_required|rejected), summary, timestamps, metadata.

### 3.7 AgenticFinding

Issue found during review. Fields: id, review_id, request_id, severity, category, description, location, suggestion, status (open|acknowledged|resolved|wont_fix), resolved_by, resolved_at, timestamps, metadata.

### 3.8 AgenticPool

Agent/human group. Fields: id, org_id, name, description, pool_type (agent|human|mixed), routing_strategy, max_concurrent, active, timestamps, metadata.

### 3.9 AgenticPoolMembership

Pool member link. Fields: id, pool_id, member_address, member_type, capabilities (JSON), max_concurrent, active, joined_at, metadata.

### 3.10 Run

Execution record. Fields: id, session_id, request_id, agent_address, run_type, status, timestamps, duration_ms, input_tokens, output_tokens, cost_usd, verification_level, error_message, metadata.

### 3.11 ExecutionMetric

Performance metric per run. Fields: id, run_id, metric_name, metric_value, unit, recorded_at, metadata.

**Total**: 11 models x 11 nodes = 121 auto-generated DataFlow workflow nodes.

---

## 4. Integration Pattern

**DataFlow handles operational data. Governance stores handle trust data. They interact through GovernanceEngine, not shared storage.**

Key integration points:

- Request creation → `GovernanceEngine.get_effective_envelope()` → envelope_id stored on request
- Work session execution → `GovernanceEngine.verify_action()` → verdict recorded on Run
- HELD verdicts → create AgenticDecision in DataFlow
- Cost tracking → backed by DataFlow queries against WorkSession and Run
- Audit bridge → emit lightweight anchor to governance audit chain

**What changes in existing code:**

- `ApprovalQueue` (in-memory) → backed by AgenticDecision queries
- `CostTracker` (in-memory) → backed by DataFlow cost aggregations
- `AgentRegistry` (in-memory) → optionally backed by AgenticPoolMembership
- `PactSession` (no persistence) → backed by AgenticWorkSession

**None of these changes touch the governance stores.**

---

## 5. PostgreSQL Path

DataFlow supports PostgreSQL natively. Same model definitions, zero code changes:

- Development: `DataFlow()` → SQLite
- Production: `DataFlow("postgresql://...")` → PostgreSQL

Both governance and DataFlow can share the same PostgreSQL instance (different tables). Connection pool math: governance 2-5 connections + DataFlow 10-25 = 12-30 total, well within `t2.micro` limits.

---

## Summary

| Decision                    | Recommendation                 |
| --------------------------- | ------------------------------ |
| Storage for work management | DataFlow (11 models)           |
| Storage for governance      | Keep direct SQLite (unchanged) |
| API framework               | Extend existing FastAPI        |
| Multi-channel (Nexus)       | Add later (Priority 4+)        |
| PostgreSQL                  | Via DataFlow native support    |
| Model count                 | 11 (reduced from ~15)          |
