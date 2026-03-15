# 1202: Workspace Discovery from Disk

**Priority**: Critical
**Effort**: Medium
**Source**: RT3 Theme C
**Dependencies**: M1 (workspace model)

## Problem

The WorkspaceManager creates workspaces programmatically but cannot discover existing workspace structures on disk. The Foundation's 7+ directories at ~/repos/terrene/terrene/ cannot be loaded.

## Implementation

Create `care_platform/workspace/discovery.py`:

- Scan a directory and identify workspace boundaries
- Map directory structure to workspace definitions
- Support manifest files (workspace.yaml) for explicit configuration
- Auto-detect workspace type from content (docs, code, config)
- Return WorkspaceConfig objects for each discovered workspace

## Acceptance Criteria

- [ ] Can discover workspaces from a directory tree
- [ ] Supports explicit workspace.yaml manifests
- [ ] Auto-detects workspace type from directory contents
- [ ] Tests verify discovery against mock directory structures
