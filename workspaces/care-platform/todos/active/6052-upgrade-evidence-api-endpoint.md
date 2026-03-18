# Task 6052: Create upgrade-evidence API Endpoint for PostureUpgradeWizard

**Milestone**: M42
**Priority**: High
**Effort**: Medium
**Status**: Active

## Description

The `PostureUpgradeWizard` in the frontend shows criteria for upgrading an agent's trust posture (e.g., from SUPERVISED to SHARED_PLANNING). It currently uses hardcoded placeholder data in the frontend. A backend API endpoint must provide the real evidence requirements and current evidence state for each posture transition.

Endpoint: `GET /api/v1/agents/{agent_id}/upgrade-evidence`

Response shape:

```json
{
  "agent_id": "...",
  "current_posture": "SUPERVISED",
  "target_posture": "SHARED_PLANNING",
  "criteria": [
    {
      "id": "audit_clean_30d",
      "description": "No BLOCKED actions in last 30 days",
      "satisfied": true,
      "evidence": "0 BLOCKED actions in audit chain"
    }
  ],
  "eligible_for_upgrade": false,
  "blocking_criteria": ["audit_clean_30d"]
}
```

## Acceptance Criteria

- [ ] `GET /api/v1/agents/{agent_id}/upgrade-evidence` endpoint added
- [ ] Endpoint reads from the AuditChain to determine whether each upgrade criterion is satisfied
- [ ] At minimum 3 criteria evaluated: clean audit history, posture duration threshold, human-approval rate
- [ ] `eligible_for_upgrade` field is accurate based on all criteria
- [ ] 404 returned for unknown agent_id
- [ ] Unit tests for the endpoint with agents at different posture levels
- [ ] OpenAPI spec updated to include the new endpoint

## Dependencies

- Task 6051 (AuditChain wired into PlatformAPI, providing the data source)
