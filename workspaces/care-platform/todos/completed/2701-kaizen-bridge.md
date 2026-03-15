# Todo 2701: Kaizen Agent Bridge — Real Execution Under Governance

**Milestone**: M27 — Agent Execution Runtime
**Priority**: High
**Effort**: Large
**Source**: Phase 3 requirement
**Dependencies**: 2501, 2502, 2503

## What

Wire the `kailash-kaizen` agent framework into the CARE execution runtime so that agents defined in workspace configuration files can execute real tasks via the registered LLM backends. Every step in the execution path must be governed: trust verification runs before any agent action is dispatched; constraint middleware evaluates the action before execution; the LLM backend generates the content; an audit anchor is created after execution. The bridge must translate between the Kaizen agent task interface and the CARE execution runtime without bypassing any governance layer. Agents not present in the trust store must be rejected before any LLM call is made.

## Where

- `src/care_platform/execution/kaizen_bridge.py`

## Evidence

- [ ] An agent defined in a workspace config file executes a real task and receives an LLM-generated response
- [ ] Trust verification is called before the LLM backend is invoked
- [ ] An agent absent from the trust store is rejected with a typed error before any LLM call
- [ ] Constraint middleware evaluates the action before execution and can HOLD or BLOCK it
- [ ] An audit anchor is created and persisted after each completed execution
- [ ] The audit anchor contains the agent ID, action, verification result, timestamp, and response hash
- [ ] Unit tests cover trust rejection, constraint blocking, and successful execution
- [ ] Integration tests cover the full bridge path with a real LLM backend
