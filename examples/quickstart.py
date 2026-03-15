# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""
Quickstart — demonstrates the core CARE Platform API.

This script shows how to:
1. Create a constraint envelope and evaluate an agent action
2. Calculate a trust score for an agent
3. Build and verify an audit chain

Run with:
    python examples/quickstart.py
"""

from datetime import UTC, datetime

from care_platform import (
    AuditChain,
    ConstraintEnvelope,
    EvaluationResult,
    TrustScore,
    calculate_trust_score,
)
from care_platform.config.schema import (
    CommunicationConstraintConfig,
    ConstraintEnvelopeConfig,
    DataAccessConstraintConfig,
    FinancialConstraintConfig,
    OperationalConstraintConfig,
    TemporalConstraintConfig,
    TrustPostureLevel,
    VerificationLevel,
)
from care_platform.trust.scoring import TrustFactors


def main() -> None:
    # ---------------------------------------------------------------
    # 1. Create a constraint envelope and evaluate an action
    # ---------------------------------------------------------------
    print("=== Step 1: Constraint Envelope Evaluation ===\n")

    envelope_config = ConstraintEnvelopeConfig(
        id="demo-envelope",
        description="Demo agent — can read metrics, cannot publish",
        financial=FinancialConstraintConfig(max_spend_usd=0.0),
        operational=OperationalConstraintConfig(
            allowed_actions=["collect_metrics", "generate_report"],
            blocked_actions=["publish_external", "send_email"],
            max_actions_per_day=20,
        ),
        temporal=TemporalConstraintConfig(
            active_hours_start="09:00",
            active_hours_end="18:00",
            timezone="Asia/Singapore",
        ),
        data_access=DataAccessConstraintConfig(
            read_paths=["workspaces/media/analytics/"],
            write_paths=["workspaces/media/reports/"],
            blocked_data_types=["pii"],
        ),
        communication=CommunicationConstraintConfig(
            internal_only=True,
            external_requires_approval=True,
        ),
    )

    envelope = ConstraintEnvelope(config=envelope_config)

    # Evaluate an allowed action
    result = envelope.evaluate_action(
        "collect_metrics",
        "demo-agent",
        current_time=datetime(2026, 3, 11, 10, 0, tzinfo=UTC),
    )
    print("Action: collect_metrics")
    print(f"Result: {result.overall_result.value}")
    print(f"Allowed: {result.is_allowed}")
    assert result.overall_result == EvaluationResult.ALLOWED

    # Evaluate a blocked action
    result_blocked = envelope.evaluate_action(
        "publish_external",
        "demo-agent",
        current_time=datetime(2026, 3, 11, 10, 0, tzinfo=UTC),
    )
    print("\nAction: publish_external")
    print(f"Result: {result_blocked.overall_result.value}")
    print(f"Allowed: {result_blocked.is_allowed}")
    assert result_blocked.overall_result == EvaluationResult.DENIED

    # ---------------------------------------------------------------
    # 2. Calculate a trust score
    # ---------------------------------------------------------------
    print("\n=== Step 2: Trust Score Calculation ===\n")

    factors = TrustFactors(
        has_genesis=True,
        has_delegation=True,
        has_envelope=True,
        has_attestation=True,
        has_audit_anchor=True,
        delegation_depth=1,
        dimensions_configured=5,
        posture_level=TrustPostureLevel.SUPERVISED,
        newest_attestation_age_days=7,
    )

    score: TrustScore = calculate_trust_score("demo-agent", factors)
    print(f"Agent: {score.agent_id}")
    print(f"Overall Score: {score.overall_score:.2f}")
    print(f"Grade: {score.grade.value}")
    print("Factor breakdown:")
    for factor_name, factor_value in score.factors.items():
        print(f"  {factor_name}: {factor_value:.2f}")

    # ---------------------------------------------------------------
    # 3. Build and verify an audit chain
    # ---------------------------------------------------------------
    print("\n=== Step 3: Audit Chain ===\n")

    chain = AuditChain(chain_id="demo-chain")

    chain.append(
        agent_id="demo-agent",
        action="collect_metrics",
        verification_level=VerificationLevel.AUTO_APPROVED,
        result="success",
    )
    chain.append(
        agent_id="demo-agent",
        action="generate_report",
        verification_level=VerificationLevel.AUTO_APPROVED,
        result="success",
    )
    chain.append(
        agent_id="demo-agent",
        action="publish_external",
        verification_level=VerificationLevel.BLOCKED,
        result="denied",
    )

    is_valid, errors = chain.verify_chain_integrity()
    print(f"Chain length: {chain.length}")
    print(f"Chain integrity valid: {is_valid}")
    if errors:
        print(f"Errors: {errors}")

    print("\nAll steps completed successfully.")


if __name__ == "__main__":
    main()
