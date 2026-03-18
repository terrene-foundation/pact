#!/usr/bin/env python3
# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Shadow calibration script — feeds synthetic DM actions through ShadowEnforcer.

Generates baseline metrics for each of the 5 DM team agents by running
a predefined set of synthetic actions through each agent's ShadowEnforcer.
Outputs per-agent metrics including pass rate, blocked count, and
verification level distribution.

Usage:
    python scripts/shadow_calibrate.py           # Run calibration and print results
    python scripts/shadow_calibrate.py --json    # Output as JSON

The calibration data set covers:
- AUTO_APPROVED actions (read_*, draft_*, analyze_*)
- FLAGGED actions (default level for unmatched patterns)
- HELD actions (approve_* pattern)
- BLOCKED actions (delete_*, modify_constraints)
"""

from __future__ import annotations

import argparse
import json

from care_platform.build.verticals.dm_runner import DMTeamRunner


def main() -> None:
    """Run shadow calibration and print results."""
    parser = argparse.ArgumentParser(
        description="Run DM team shadow calibration",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    runner = DMTeamRunner()
    metrics = runner.run_shadow_calibration()

    if args.json:
        print(json.dumps(metrics, indent=2))
        return

    print("=" * 70)
    print("DM Team Shadow Calibration Results")
    print("=" * 70)
    print()

    for agent_id, m in sorted(metrics.items()):
        print(f"Agent: {agent_id}")
        print(f"  Total evaluations:  {m['total_evaluations']}")
        print(f"  Auto-approved:      {m['auto_approved_count']}")
        print(f"  Flagged:            {m['flagged_count']}")
        print(f"  Held:               {m['held_count']}")
        print(f"  Blocked:            {m['blocked_count']}")
        print(f"  Pass rate:          {m['pass_rate']:.1%}")
        print()

    # Summary
    total = sum(m["total_evaluations"] for m in metrics.values())
    total_auto = sum(m["auto_approved_count"] for m in metrics.values())
    total_flagged = sum(m["flagged_count"] for m in metrics.values())
    total_held = sum(m["held_count"] for m in metrics.values())
    total_blocked = sum(m["blocked_count"] for m in metrics.values())

    print("-" * 70)
    print("SUMMARY")
    print(f"  Total actions evaluated: {total}")
    print(f"  AUTO_APPROVED: {total_auto} ({total_auto / total:.0%})")
    print(f"  FLAGGED:       {total_flagged} ({total_flagged / total:.0%})")
    print(f"  HELD:          {total_held} ({total_held / total:.0%})")
    print(f"  BLOCKED:       {total_blocked} ({total_blocked / total:.0%})")
    print()

    # Generate upgrade recommendations
    print("=" * 70)
    print("Posture Upgrade Recommendations")
    print("=" * 70)
    print()

    for agent_id in sorted(metrics.keys()):
        try:
            rec = runner.get_upgrade_recommendation(agent_id)
            eligible = "YES" if rec["eligible"] else "NO"
            print(f"Agent: {agent_id}")
            print(f"  Eligible: {eligible}")
            print(f"  {rec['recommendation']}")
            if rec.get("blockers"):
                for blocker in rec["blockers"]:
                    print(f"    - {blocker}")
            print()
        except KeyError as exc:
            print(f"Agent: {agent_id} — ERROR: {exc}")
            print()


if __name__ == "__main__":
    main()
