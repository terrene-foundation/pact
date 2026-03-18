# Task 6053: Wire PostureUpgradeWizard to Real upgrade-evidence API

**Milestone**: M42
**Priority**: High
**Effort**: Small
**Status**: Active

## Description

Once the `upgrade-evidence` API endpoint exists (task 6052), replace the hardcoded placeholder data in the `PostureUpgradeWizard` frontend component with real API calls. The wizard should fetch evidence for the selected agent and display accurate criteria status.

## Acceptance Criteria

- [ ] `PostureUpgradeWizard` fetches `GET /api/v1/agents/{agent_id}/upgrade-evidence` on mount and when agent selection changes
- [ ] Loading state shown while fetch is in progress
- [ ] Error state shown if the endpoint returns an error
- [ ] All hardcoded placeholder criteria removed from the frontend component
- [ ] `eligible_for_upgrade` from the API drives whether the "Upgrade" button is enabled
- [ ] Criteria list rendered from API response (not hardcoded)
- [ ] Manual test: select an agent in the dashboard, open upgrade wizard, verify real data appears

## Dependencies

- Task 6052 (upgrade-evidence API endpoint must exist before the frontend can call it)
