# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Knowledge policy enforcement — workspace-level data access controls.

M17-1702: KnowledgePolicyEnforcer checks data access against workspace knowledge
policies. Each workspace has a KnowledgePolicy that defines:
- Which data classifications are allowed/blocked for read and write access.
- Which data types are blocked (e.g., credentials, PII).
- Maximum data sensitivity level.

Bridge access that violates a workspace policy is denied with clear violation
details. Access that complies is allowed.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class PolicyViolation(BaseModel):
    """A single violation found during policy check."""

    reason: str = Field(description="Human-readable description of the violation")
    policy_workspace_id: str = Field(description="Workspace whose policy was violated")
    dimension: str = Field(
        description="Which dimension was violated (classification, data_type, etc.)"
    )


class PolicyDecision(BaseModel):
    """Result of a knowledge policy check."""

    allowed: bool = Field(description="Whether the access is allowed")
    violations: list[PolicyViolation] = Field(
        default_factory=list,
        description="List of violations (empty if allowed)",
    )


class KnowledgePolicy(BaseModel):
    """Workspace-level knowledge policy defining data access rules.

    Each workspace has one KnowledgePolicy that governs what data
    classifications and types are accessible through that workspace.
    """

    workspace_id: str = Field(description="ID of the workspace this policy governs")
    allowed_read_classifications: list[str] = Field(
        default_factory=list,
        description="Data classifications allowed for read access",
    )
    blocked_read_classifications: list[str] = Field(
        default_factory=list,
        description="Data classifications explicitly blocked for read access",
    )
    allowed_write_classifications: list[str] = Field(
        default_factory=list,
        description="Data classifications allowed for write access",
    )
    blocked_write_classifications: list[str] = Field(
        default_factory=list,
        description="Data classifications explicitly blocked for write access",
    )
    max_data_sensitivity: str = Field(
        default="internal",
        description="Maximum allowed data sensitivity level",
    )
    allowed_data_types: list[str] = Field(
        default_factory=list,
        description="Data types explicitly allowed (empty = no restriction beyond blocks)",
    )
    blocked_data_types: list[str] = Field(
        default_factory=list,
        description="Data types explicitly blocked (e.g., credentials, pii)",
    )

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "workspace_id must not be empty. "
                "Every knowledge policy must be associated with a workspace."
            )
        return v


# ---------------------------------------------------------------------------
# KnowledgePolicyEnforcer
# ---------------------------------------------------------------------------


class KnowledgePolicyEnforcer:
    """Enforces workspace knowledge policies on data access requests.

    Maintains a registry of workspace policies and checks each access
    request against the appropriate workspace's policy.

    Usage:
        enforcer = KnowledgePolicyEnforcer(policies=[eng_policy, hr_policy])
        decision = enforcer.check_access(
            workspace_id="ws-engineering",
            path="docs/arch.md",
            access_type="read",
            data_classification="internal",
        )
        if not decision.allowed:
            for v in decision.violations:
                print(f"DENIED: {v.reason}")
    """

    def __init__(self, policies: list[KnowledgePolicy] | None = None) -> None:
        """Initialize with a list of workspace policies.

        Args:
            policies: Initial list of knowledge policies. Each policy
                is indexed by workspace_id.
        """
        self._policies: dict[str, KnowledgePolicy] = {}
        for policy in policies or []:
            self._policies[policy.workspace_id] = policy

    def add_policy(self, policy: KnowledgePolicy) -> None:
        """Register a workspace knowledge policy.

        Args:
            policy: The knowledge policy to add. Overwrites any existing
                policy for the same workspace_id.
        """
        self._policies[policy.workspace_id] = policy
        logger.info(
            "Knowledge policy registered for workspace '%s'",
            policy.workspace_id,
        )

    def get_policy(self, workspace_id: str) -> KnowledgePolicy | None:
        """Get the knowledge policy for a workspace.

        Args:
            workspace_id: The workspace to look up.

        Returns:
            The KnowledgePolicy if found, None otherwise.
        """
        return self._policies.get(workspace_id)

    def check_access(
        self,
        workspace_id: str,
        path: str,
        access_type: str,
        data_classification: str,
        data_type: str | None = None,
    ) -> PolicyDecision:
        """Check whether a data access request complies with the workspace policy.

        Args:
            workspace_id: The workspace being accessed.
            path: The data path being accessed.
            access_type: Either 'read' or 'write'.
            data_classification: Classification of the data (e.g., 'public', 'internal').
            data_type: Optional data type (e.g., 'credentials', 'documentation').

        Returns:
            PolicyDecision with allowed status and any violations.
        """
        policy = self._policies.get(workspace_id)
        if policy is None:
            violation = PolicyViolation(
                reason=(
                    f"No policy found for workspace '{workspace_id}'. "
                    f"Access denied by default — every workspace must have "
                    f"a registered knowledge policy."
                ),
                policy_workspace_id=workspace_id,
                dimension="policy_lookup",
            )
            logger.warning(
                "Knowledge policy check DENIED: no policy for workspace '%s', "
                "path='%s', access_type='%s'",
                workspace_id,
                path,
                access_type,
            )
            return PolicyDecision(allowed=False, violations=[violation])

        violations: list[PolicyViolation] = []

        # Check classification
        self._check_classification(
            policy=policy,
            access_type=access_type,
            data_classification=data_classification,
            violations=violations,
        )

        # Check data type
        if data_type is not None:
            self._check_data_type(
                policy=policy,
                data_type=data_type,
                violations=violations,
            )

        if violations:
            logger.info(
                "Knowledge policy check DENIED: workspace='%s', path='%s', "
                "access_type='%s', classification='%s', data_type='%s' — "
                "%d violation(s)",
                workspace_id,
                path,
                access_type,
                data_classification,
                data_type,
                len(violations),
            )
        else:
            logger.debug(
                "Knowledge policy check ALLOWED: workspace='%s', path='%s', "
                "access_type='%s', classification='%s'",
                workspace_id,
                path,
                access_type,
                data_classification,
            )

        return PolicyDecision(
            allowed=len(violations) == 0,
            violations=violations,
        )

    def _check_classification(
        self,
        policy: KnowledgePolicy,
        access_type: str,
        data_classification: str,
        violations: list[PolicyViolation],
    ) -> None:
        """Check data classification against the policy.

        Args:
            policy: The workspace policy.
            access_type: 'read' or 'write'.
            data_classification: The classification to check.
            violations: Accumulator for violations found.
        """
        if access_type == "read":
            allowed = policy.allowed_read_classifications
            blocked = policy.blocked_read_classifications
        elif access_type == "write":
            allowed = policy.allowed_write_classifications
            blocked = policy.blocked_write_classifications
        else:
            violations.append(
                PolicyViolation(
                    reason=f"Unknown access type '{access_type}' — only 'read' and 'write' are supported",
                    policy_workspace_id=policy.workspace_id,
                    dimension="access_type",
                )
            )
            return

        # Blocked classifications always take precedence
        if data_classification in blocked:
            violations.append(
                PolicyViolation(
                    reason=(
                        f"Classification '{data_classification}' is explicitly blocked "
                        f"for {access_type} access in workspace '{policy.workspace_id}'"
                    ),
                    policy_workspace_id=policy.workspace_id,
                    dimension="classification",
                )
            )
            return

        # If allowed list is defined, classification must be in it
        if allowed and data_classification not in allowed:
            violations.append(
                PolicyViolation(
                    reason=(
                        f"Classification '{data_classification}' is not in the allowed "
                        f"{access_type} classifications for workspace '{policy.workspace_id}'. "
                        f"Allowed: {allowed}"
                    ),
                    policy_workspace_id=policy.workspace_id,
                    dimension="classification",
                )
            )

    def _check_data_type(
        self,
        policy: KnowledgePolicy,
        data_type: str,
        violations: list[PolicyViolation],
    ) -> None:
        """Check data type against the policy.

        Args:
            policy: The workspace policy.
            data_type: The data type to check.
            violations: Accumulator for violations found.
        """
        if data_type in policy.blocked_data_types:
            violations.append(
                PolicyViolation(
                    reason=(
                        f"Data type '{data_type}' is blocked by the knowledge policy "
                        f"for workspace '{policy.workspace_id}'. "
                        f"Blocked types: {policy.blocked_data_types}"
                    ),
                    policy_workspace_id=policy.workspace_id,
                    dimension="data_type",
                )
            )
