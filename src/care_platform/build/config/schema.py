# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Platform configuration schema — Pydantic models for CARE Platform configuration.

Defines how organizations describe their structure, teams, agents, constraint
envelopes, and workspace layout in YAML configuration files.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

# ConfidentialityLevel is defined in care_platform.trust.reasoning but
# importing it eagerly creates a circular dependency:
#   config.schema -> trust.reasoning -> trust.__init__ -> trust.delegation
#   -> constraint.envelope -> constraint.__init__ -> constraint.cache -> config.schema
#
# To break the cycle, we duplicate the enum definition here. The canonical
# source in trust.reasoning re-exports from here via a TYPE_CHECKING guard.
from enum import Enum as _Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConfidentialityLevel(str, _Enum):
    """Confidentiality classification for reasoning traces (EATP-aligned).

    Ordered from least to most restrictive:
    PUBLIC < RESTRICTED < CONFIDENTIAL < SECRET < TOP_SECRET

    - PUBLIC (level 0): visible to anyone
    - RESTRICTED (level 1): visible to direct chain participants
    - CONFIDENTIAL (level 2): visible to named roles
    - SECRET (level 3): visible to named individuals
    - TOP_SECRET (level 4): encrypted, only hash disclosed
    """

    PUBLIC = "public"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"
    SECRET = "secret"
    TOP_SECRET = "top_secret"


# Numeric ordering for confidentiality comparisons.
# Lower index = less access required.
CONFIDENTIALITY_ORDER: dict[ConfidentialityLevel, int] = {
    ConfidentialityLevel.PUBLIC: 0,
    ConfidentialityLevel.RESTRICTED: 1,
    ConfidentialityLevel.CONFIDENTIAL: 2,
    ConfidentialityLevel.SECRET: 3,
    ConfidentialityLevel.TOP_SECRET: 4,
}

# Backward-compatible alias (was _CONFIDENTIALITY_ORDER in trust.reasoning)
_CONFIDENTIALITY_ORDER = CONFIDENTIALITY_ORDER


# --- Enums ---


class TrustPostureLevel(str, Enum):
    """EATP trust posture levels. Agents start at SUPERVISED and evolve."""

    PSEUDO_AGENT = "pseudo_agent"
    SUPERVISED = "supervised"
    SHARED_PLANNING = "shared_planning"
    CONTINUOUS_INSIGHT = "continuous_insight"
    DELEGATED = "delegated"


class VerificationLevel(str, Enum):
    """Verification gradient levels for agent actions."""

    AUTO_APPROVED = "AUTO_APPROVED"
    FLAGGED = "FLAGGED"
    HELD = "HELD"
    BLOCKED = "BLOCKED"


class ConstraintDimension(str, Enum):
    """The five CARE constraint dimensions."""

    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    TEMPORAL = "temporal"
    DATA_ACCESS = "data_access"
    COMMUNICATION = "communication"


# --- Constraint Envelope Config ---


class FinancialConstraintConfig(BaseModel):
    """Financial dimension of a constraint envelope."""

    model_config = ConfigDict(frozen=True)

    max_spend_usd: float = Field(default=0.0, ge=0, description="Maximum USD spend allowed")
    api_cost_budget_usd: float | None = Field(
        default=None, ge=0, description="LLM API cost budget (per billing period)"
    )
    requires_approval_above_usd: float | None = Field(
        default=None, ge=0, description="Threshold requiring human approval"
    )
    reasoning_required: bool = Field(
        default=False,
        description="When True, any action touching this dimension must include a reasoning trace",
    )


class OperationalConstraintConfig(BaseModel):
    """Operational dimension of a constraint envelope."""

    model_config = ConfigDict(frozen=True)

    allowed_actions: list[str] = Field(
        default_factory=list, description="Actions this agent may perform"
    )
    blocked_actions: list[str] = Field(
        default_factory=list, description="Actions explicitly blocked"
    )
    max_actions_per_day: int | None = Field(
        default=None, gt=0, description="Daily action rate limit"
    )
    max_actions_per_hour: int | None = Field(
        default=None, gt=0, description="Hourly action rate limit (per-agent sliding window)"
    )
    rate_limit_window_type: str = Field(
        default="fixed",
        description="Rate limit window type: 'fixed' (calendar-based) or 'rolling' (sliding window)",
    )
    reasoning_required: bool = Field(
        default=False,
        description="When True, any action touching this dimension must include a reasoning trace",
    )

    @field_validator("rate_limit_window_type")
    @classmethod
    def validate_rate_limit_window_type(cls, v: str) -> str:
        if v not in ("fixed", "rolling"):
            msg = f"rate_limit_window_type must be 'fixed' or 'rolling', got '{v}'"
            raise ValueError(msg)
        return v


class TemporalConstraintConfig(BaseModel):
    """Temporal dimension of a constraint envelope."""

    model_config = ConfigDict(frozen=True)

    active_hours_start: str | None = Field(
        default=None, description="Start of active window (HH:MM, 24h)"
    )
    active_hours_end: str | None = Field(
        default=None, description="End of active window (HH:MM, 24h)"
    )
    timezone: str = Field(default="UTC", description="Timezone for active hours")
    blackout_periods: list[str] = Field(
        default_factory=list, description="Periods when agent must not operate"
    )
    reasoning_required: bool = Field(
        default=False,
        description="When True, any action touching this dimension must include a reasoning trace",
    )

    @field_validator("active_hours_start", "active_hours_end")
    @classmethod
    def validate_time_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        parts = v.split(":")
        if len(parts) != 2:
            msg = f"Time must be HH:MM format, got '{v}'"
            raise ValueError(msg)
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            msg = f"Invalid time '{v}': hours 0-23, minutes 0-59"
            raise ValueError(msg)
        return v


class DataAccessConstraintConfig(BaseModel):
    """Data access dimension of a constraint envelope."""

    model_config = ConfigDict(frozen=True)

    read_paths: list[str] = Field(
        default_factory=list, description="Paths/resources agent may read"
    )
    write_paths: list[str] = Field(
        default_factory=list, description="Paths/resources agent may write"
    )
    blocked_data_types: list[str] = Field(
        default_factory=list,
        description="Data types agent must never access (e.g., 'pii', 'financial_records')",
    )
    reasoning_required: bool = Field(
        default=False,
        description="When True, any action touching this dimension must include a reasoning trace",
    )


class CommunicationConstraintConfig(BaseModel):
    """Communication dimension of a constraint envelope."""

    model_config = ConfigDict(frozen=True)

    internal_only: bool = Field(default=True, description="Agent restricted to internal channels")
    allowed_channels: list[str] = Field(
        default_factory=list, description="Channels agent may communicate through"
    )
    external_requires_approval: bool = Field(
        default=True, description="External communication requires human approval"
    )
    reasoning_required: bool = Field(
        default=False,
        description="When True, any action touching this dimension must include a reasoning trace",
    )


class ConstraintEnvelopeConfig(BaseModel):
    """A complete constraint envelope across all five CARE dimensions.

    Now includes confidentiality_clearance (M15/1501) — the maximum
    confidentiality level of data this envelope's agent may access.

    M23/2301: financial is Optional — not all agents handle money. When None,
    the financial dimension is skipped during evaluation (no zero-spend default
    that blocks everything).

    M23/2302: max_delegation_depth controls how many levels deep trust can be
    delegated. expires_at is a config-level expiry (distinct from the envelope
    object's runtime expiry).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="Unique identifier for this envelope")
    description: str = Field(default="", description="Human-readable description")
    confidentiality_clearance: ConfidentialityLevel = Field(
        default=ConfidentialityLevel.PUBLIC,
        description=(
            "Maximum confidentiality level of data this envelope may access. "
            "Data classified above this level will be denied."
        ),
    )
    financial: FinancialConstraintConfig | None = Field(
        default_factory=FinancialConstraintConfig,
        description=(
            "Financial constraint config. None means the agent has no financial "
            "capability — the financial dimension is skipped during evaluation."
        ),
    )
    operational: OperationalConstraintConfig = Field(default_factory=OperationalConstraintConfig)
    temporal: TemporalConstraintConfig = Field(default_factory=TemporalConstraintConfig)
    data_access: DataAccessConstraintConfig = Field(default_factory=DataAccessConstraintConfig)
    communication: CommunicationConstraintConfig = Field(
        default_factory=CommunicationConstraintConfig
    )
    max_delegation_depth: int | None = Field(
        default=None,
        gt=0,
        description=(
            "Maximum delegation depth — how many levels deep trust can be delegated. "
            "None means unlimited."
        ),
    )
    expires_at: datetime | None = Field(
        default=None,
        description=(
            "Config-level expiry timestamp. When set, the constraint envelope config "
            "itself expires at this time, independent of the runtime envelope expiry."
        ),
    )


# --- Verification Gradient Config ---


class GradientRuleConfig(BaseModel):
    """A single verification gradient rule — maps action patterns to verification levels."""

    pattern: str = Field(description="Action pattern to match (glob or regex)")
    level: VerificationLevel = Field(description="Verification level for matching actions")
    reason: str = Field(default="", description="Why this level applies")


class VerificationGradientConfig(BaseModel):
    """Verification gradient rules for an agent or team."""

    rules: list[GradientRuleConfig] = Field(
        default_factory=list, description="Ordered list of gradient rules (first match wins)"
    )
    default_level: VerificationLevel = Field(
        default=VerificationLevel.HELD, description="Default level when no rule matches"
    )


# --- Agent Config ---


class AgentConfig(BaseModel):
    """Configuration for a single agent in a team."""

    id: str = Field(description="Unique agent identifier")
    name: str = Field(description="Human-readable agent name")
    role: str = Field(description="Agent's role description")
    constraint_envelope: str = Field(
        description="ID of the constraint envelope governing this agent"
    )
    initial_posture: TrustPostureLevel = Field(
        default=TrustPostureLevel.SUPERVISED,
        description="Starting trust posture",
    )
    capabilities: list[str] = Field(
        default_factory=list, description="Specific capabilities this agent has"
    )
    llm_backend: str | None = Field(
        default=None, description="LLM backend override (uses team default if None)"
    )
    verification_gradient: VerificationGradientConfig | None = Field(
        default=None, description="Agent-specific gradient rules (overrides team default)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional agent-specific metadata"
    )


# --- Workspace Config ---


class WorkspaceConfig(BaseModel):
    """Configuration for a workspace (knowledge base for an agent team)."""

    id: str = Field(description="Unique workspace identifier")
    path: str = Field(description="Filesystem path to workspace directory")
    description: str = Field(default="", description="Purpose of this workspace")
    knowledge_base_paths: list[str] = Field(
        default_factory=lambda: ["briefs/", "01-analysis/", "02-plans/"],
        description="Subdirectories constituting the knowledge base",
    )

    @field_validator("path")
    @classmethod
    def validate_path_not_empty(cls, v: str) -> str:
        if not v.strip():
            msg = "Workspace path must not be empty"
            raise ValueError(msg)
        return v


# --- Team Config ---


class TeamConfig(BaseModel):
    """Configuration for an agent team."""

    id: str = Field(description="Unique team identifier")
    name: str = Field(description="Human-readable team name")
    workspace: str = Field(description="ID of the workspace this team operates in")
    team_lead: str | None = Field(default=None, description="ID of the team lead agent")
    agents: list[str] = Field(default_factory=list, description="IDs of agents in this team")
    default_llm_backend: str = Field(
        default="anthropic", description="Default LLM backend for team agents"
    )
    verification_gradient: VerificationGradientConfig | None = Field(
        default=None, description="Team-level default gradient rules"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional team-specific metadata"
    )


# --- Platform Config (Top Level) ---


class GenesisConfig(BaseModel):
    """Configuration for the EATP genesis record (root of trust)."""

    authority: str = Field(description="Authority identifier (e.g., 'terrene.foundation')")
    authority_name: str = Field(description="Human-readable authority name")
    policy_reference: str = Field(
        default="", description="URI or path to the governance policy document"
    )


class PlatformConfig(BaseModel):
    """Top-level CARE Platform configuration.

    This is the root object that contains all platform configuration —
    genesis, teams, agents, constraint envelopes, workspaces, and gradient rules.
    """

    name: str = Field(description="Organization name")
    version: str = Field(default="1.0", description="Config schema version")
    genesis: GenesisConfig = Field(description="EATP genesis (root of trust)")
    default_posture: TrustPostureLevel = Field(
        default=TrustPostureLevel.SUPERVISED,
        description="Default trust posture for new agents",
    )
    constraint_envelopes: list[ConstraintEnvelopeConfig] = Field(
        default_factory=list, description="All constraint envelope definitions"
    )
    agents: list[AgentConfig] = Field(default_factory=list, description="All agent definitions")
    teams: list[TeamConfig] = Field(default_factory=list, description="All team definitions")
    workspaces: list[WorkspaceConfig] = Field(
        default_factory=list, description="All workspace definitions"
    )

    def get_envelope(self, envelope_id: str) -> ConstraintEnvelopeConfig | None:
        """Look up a constraint envelope by ID."""
        for envelope in self.constraint_envelopes:
            if envelope.id == envelope_id:
                return envelope
        return None

    def get_agent(self, agent_id: str) -> AgentConfig | None:
        """Look up an agent by ID."""
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def get_team(self, team_id: str) -> TeamConfig | None:
        """Look up a team by ID."""
        for team in self.teams:
            if team.id == team_id:
                return team
        return None

    def get_workspace(self, workspace_id: str) -> WorkspaceConfig | None:
        """Look up a workspace by ID."""
        for workspace in self.workspaces:
            if workspace.id == workspace_id:
                return workspace
        return None

    @field_validator("constraint_envelopes")
    @classmethod
    def validate_unique_envelope_ids(
        cls,
        v: list[ConstraintEnvelopeConfig],
    ) -> list[ConstraintEnvelopeConfig]:
        ids = [e.id for e in v]
        if len(ids) != len(set(ids)):
            dupes = [i for i in ids if ids.count(i) > 1]
            msg = f"Duplicate constraint envelope IDs: {set(dupes)}"
            raise ValueError(msg)
        return v

    @field_validator("agents")
    @classmethod
    def validate_unique_agent_ids(cls, v: list[AgentConfig]) -> list[AgentConfig]:
        ids = [a.id for a in v]
        if len(ids) != len(set(ids)):
            dupes = [i for i in ids if ids.count(i) > 1]
            msg = f"Duplicate agent IDs: {set(dupes)}"
            raise ValueError(msg)
        return v

    @field_validator("teams")
    @classmethod
    def validate_unique_team_ids(cls, v: list[TeamConfig]) -> list[TeamConfig]:
        ids = [t.id for t in v]
        if len(ids) != len(set(ids)):
            dupes = [i for i in ids if ids.count(i) > 1]
            msg = f"Duplicate team IDs: {set(dupes)}"
            raise ValueError(msg)
        return v
