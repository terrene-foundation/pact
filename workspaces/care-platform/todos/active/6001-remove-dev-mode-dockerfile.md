# Task 6001: Remove CARE_DEV_MODE=true from root Dockerfile

**Milestone**: M0b
**Priority**: Critical
**Effort**: Tiny
**Status**: Active

## Description

The root `Dockerfile` has `CARE_DEV_MODE=true` hardcoded as an environment variable. This flag bypasses trust enforcement and governance checks. Shipping a production image with this flag enabled means no governance runs in production — directly violating the platform's core guarantee.

## Acceptance Criteria

- [ ] `CARE_DEV_MODE=true` line removed from root Dockerfile
- [ ] `CARE_DEV_MODE` is not set anywhere in Docker build args
- [ ] If dev-mode toggle is needed, it must come from the runtime environment (docker-compose.override.yml or host env), not baked into the image
- [ ] Docker image builds cleanly after the change
- [ ] Existing CI Docker build test passes

## Dependencies

- None. No other task blocks this.

## Notes

If any test suite relies on `CARE_DEV_MODE=true` in the Docker context, those tests must be fixed to either set the flag via environment override or not rely on it at all. The image itself must be governance-enforcing by default.
