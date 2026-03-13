---
name: implement
description: "Load phase 03 (implement) for the current workspace. Repeat until all todos complete."
---

## What This Phase Does (present to user)

Execute the work one task at a time from the approved roadmap. Each run of `/implement` completes one task — writing code, creating tests, configuring agents, defining constraint envelopes, or building platform components.

## Your Role (communicate to user)

Your role is to answer questions when decisions come up — these will always be about architecture choices, trust model design, or standards alignment. You can check progress anytime with `/ws`.

## Workspace Resolution

1. If `$ARGUMENTS` specifies a project name or todo, parse accordingly
2. Otherwise, use the most recently modified directory under `workspaces/` (excluding `instructions/`)
3. If no workspace exists, ask the user to create one first
4. Read all files in `workspaces/<project>/briefs/` for user context

## Phase Check

- Read files in `workspaces/<project>/todos/active/` to see what needs doing
- Read files in `workspaces/<project>/todos/completed/` to see what's done
- If `$ARGUMENTS` specifies a specific todo, focus on that one
- Otherwise, pick the next active todo
- Reference plans in `workspaces/<project>/02-plans/` for context

## Workflow

### NOTE: Run `/implement` repeatedly until all todos/active have been moved to todos/completed

### 1. Prepare todos

Use the todo-manager to create detailed todos for EVERY SINGLE TODO in `todos/000-master.md`.

### 2. Execute

Implement the next todo using the appropriate team of agents.

- Read relevant existing code and docs before writing new code
- Check standards alignment (CARE/EATP/CO) for governance features
- Consult framework specialists (dataflow, nexus, kaizen, mcp) before building from scratch
- Check analysis docs in `workspaces/care-platform/01-analysis/` for design decisions

### 3. Quality standards

Always involve intermediate-reviewer:

- Code review for quality and patterns
- Terrene naming conventions
- License accuracy (Apache 2.0 headers)
- EATP/CARE alignment for trust features
- Tests written and passing
- No placeholder content

### 4. Communicate progress and surface decisions

When reporting to the user:

- **Progress**: State what was accomplished in plain terms. "The verification gradient now evaluates all five constraint dimensions" not "Updated verify.py"
- **Decisions needed**: Present choices with impact. "Should constraint envelopes be evaluated synchronously or asynchronously? Sync is simpler but blocks; async scales but adds complexity."
- **Scope changes**: If work reveals something not in the plan, explain what and why.

### 5. Update and close todos

After completing each todo:

- Move it from `todos/active/` to `todos/completed/`
- Ensure every task is verified with evidence before closing

### 6. Completion evidence

Before closing ANY todo, you MUST provide concrete evidence:

**For code changes:**

- [ ] File path(s) where work is stored
- [ ] All tests pass (unit, integration, e2e as applicable)
- [ ] Code review (intermediate-reviewer has reviewed)
- [ ] Security review (security-reviewer has reviewed)
- [ ] No regressions introduced

**For standards/governance content:**

- [ ] File path(s) where work is stored
- [ ] Standards expert consulted (care-expert, eatp-expert, co-expert as applicable)
- [ ] Terminology matches canonical spec
- [ ] Cross-references verified

A todo is NOT complete until evidence is provided. "Verified with evidence" means specific file paths, test results, and review attestations — not a general statement.

### 7. Decision log

When the user makes a decision during implementation, capture it:

```yaml
decision: [What was decided]
rationale: [Why — the reasoning]
alternatives_rejected: [What other options were considered]
date: [When]
initiative: [Which initiative]
```

Store decisions in the workspace for `/codify` to capture later.

## Agent Teams

Deploy these agents as a team for each implementation cycle:

**Core team (always):**

- **intermediate-reviewer** — Document review after changes
- **gold-standards-validator** — Naming, terminology, license compliance
- **todo-manager** — Track progress, update todo status

**Standards experts (invoke when working on standards content):**

- **care-expert** — CARE governance framework
- **eatp-expert** — EATP trust protocol
- **co-expert** — CO methodology
- **coc-expert** — COC (CO for Codegen)

**Strategy (invoke for positioning and licensing work):**

- **open-source-strategist** — Licensing, community, competitive positioning

**Framework specialists (invoke for Kailash work):**

- **dataflow-specialist** — Database operations, DataFlow models
- **nexus-specialist** — API endpoints, multi-channel deployment
- **kaizen-specialist** — Agent framework, multi-agent coordination
- **mcp-specialist** — MCP integration

**Analysis (invoke for complex decisions):**

- **deep-analyst** — Risk analysis, failure points, cascading effects
- **requirements-analyst** — Requirements breakdown, decision records

**Quality gate (before closing each todo):**

- **security-reviewer** — Security audit before commit
