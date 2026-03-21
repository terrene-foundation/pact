// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * UpgradeEligibility -- card showing posture upgrade eligibility and blockers.
 *
 * Displays whether the agent is eligible for a trust posture upgrade based
 * on ShadowEnforcer metrics, with specific blockers listed when not eligible,
 * and the human-readable recommendation from the ShadowReport.
 *
 * When eligible, an "Upgrade Posture" button triggers a confirmation dialog
 * and calls PUT /api/v1/agents/{agent_id}/posture with the next posture level.
 */

"use client";

import { useState, useCallback } from "react";
import type { ShadowReport, TrustPosture } from "../../../types/pact";
import { getApiClient } from "../../../lib/use-api";

// ---------------------------------------------------------------------------
// Trust posture progression (ordered from lowest to highest autonomy)
// ---------------------------------------------------------------------------

const POSTURE_ORDER: TrustPosture[] = [
  "pseudo_agent",
  "supervised",
  "shared_planning",
  "continuous_insight",
  "delegated",
];

/** Map a posture string to a human-readable label. */
function postureLabel(posture: string): string {
  return posture.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Get the next posture level or null if already at maximum. */
function nextPosture(current: string): TrustPosture | null {
  const idx = POSTURE_ORDER.indexOf(current as TrustPosture);
  if (idx < 0 || idx >= POSTURE_ORDER.length - 1) return null;
  return POSTURE_ORDER[idx + 1];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface UpgradeEligibilityProps {
  report: ShadowReport;
  agentId: string;
  agentName: string;
  currentPosture: string;
  onPostureUpgraded: () => void;
}

/** Upgrade eligibility card with blockers, recommendation, and upgrade action. */
export default function UpgradeEligibility({
  report,
  agentId,
  agentName,
  currentPosture,
  onPostureUpgraded,
}: UpgradeEligibilityProps) {
  const eligible = report.upgrade_eligible;
  const next = nextPosture(currentPosture);

  const [showConfirm, setShowConfirm] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const [upgradeError, setUpgradeError] = useState<string | null>(null);
  const [upgradeSuccess, setUpgradeSuccess] = useState(false);

  const handleUpgrade = useCallback(async () => {
    if (!next) return;
    setUpgrading(true);
    setUpgradeError(null);

    try {
      const client = getApiClient();
      const response = await client.changePosture(
        agentId,
        next,
        `ShadowEnforcer upgrade: pass rate ${(report.pass_rate * 100).toFixed(1)}%, eligible for ${postureLabel(next)}`,
        "governance_officer",
      );

      if (response.status === "ok") {
        setShowConfirm(false);
        setUpgradeSuccess(true);
        onPostureUpgraded();
        // Clear success toast after a delay
        setTimeout(() => setUpgradeSuccess(false), 4000);
      } else {
        setUpgradeError(response.error ?? "Failed to upgrade posture");
      }
    } catch (err: unknown) {
      setUpgradeError(
        err instanceof Error ? err.message : "An unexpected error occurred",
      );
    } finally {
      setUpgrading(false);
    }
  }, [agentId, next, report.pass_rate, onPostureUpgraded]);

  return (
    <div
      className={`rounded-lg border p-6 ${
        eligible
          ? "border-green-200 bg-green-50"
          : "border-orange-200 bg-orange-50"
      }`}
    >
      {/* Header with status */}
      <div className="flex items-start gap-3">
        <div
          className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full ${
            eligible ? "bg-green-200" : "bg-orange-200"
          }`}
        >
          {eligible ? (
            <svg
              className="h-5 w-5 text-green-700"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          ) : (
            <svg
              className="h-5 w-5 text-orange-700"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
              />
            </svg>
          )}
        </div>

        <div className="flex-1">
          <h3
            className={`text-sm font-semibold ${
              eligible ? "text-green-800" : "text-orange-800"
            }`}
          >
            {eligible
              ? "Eligible for Posture Upgrade"
              : "Not Yet Eligible for Posture Upgrade"}
          </h3>

          {/* Blockers */}
          {!eligible && report.upgrade_blockers.length > 0 && (
            <div className="mt-2">
              <p className="text-xs font-medium text-orange-700">Blockers:</p>
              <ul className="mt-1 space-y-1">
                {report.upgrade_blockers.map((blocker, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-xs text-orange-700"
                  >
                    <span
                      className="mt-1 inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full bg-orange-400"
                      aria-hidden="true"
                    />
                    {blocker}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Upgrade button -- only shown when eligible and not at max posture */}
        {eligible && next && (
          <button
            onClick={() => {
              setUpgradeError(null);
              setShowConfirm(true);
            }}
            className="flex-shrink-0 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-colors"
          >
            Upgrade Posture
          </button>
        )}
      </div>

      {/* Success toast */}
      {upgradeSuccess && (
        <div className="mt-3 rounded-md border border-green-300 bg-green-100 p-3 text-sm text-green-800">
          Posture upgraded successfully. The dashboard data is refreshing.
        </div>
      )}

      {/* Confirmation dialog (inline) */}
      {showConfirm && next && (
        <div className="mt-4 rounded-lg border border-gray-300 bg-white p-4 shadow-sm">
          <h4 className="text-sm font-semibold text-gray-900">
            Confirm Posture Upgrade
          </h4>
          <p className="mt-1 text-sm text-gray-600">
            Upgrade <span className="font-medium">{agentName}</span> from{" "}
            <span className="font-medium">{postureLabel(currentPosture)}</span>{" "}
            to <span className="font-medium">{postureLabel(next)}</span>?
          </p>
          <p className="mt-1 text-xs text-gray-500">
            This will change the agent&apos;s trust posture level based on
            ShadowEnforcer evaluation evidence. The change is recorded in the
            audit trail.
          </p>

          {/* Error */}
          {upgradeError && (
            <div className="mt-2 rounded-md border border-red-200 bg-red-50 p-2 text-xs text-red-700">
              {upgradeError}
            </div>
          )}

          <div className="mt-3 flex justify-end gap-2">
            <button
              onClick={() => setShowConfirm(false)}
              disabled={upgrading}
              className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleUpgrade}
              disabled={upgrading}
              className="rounded-md bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {upgrading ? "Upgrading..." : "Confirm Upgrade"}
            </button>
          </div>
        </div>
      )}

      {/* Recommendation */}
      <div className="mt-4 rounded-lg border border-gray-200 bg-white p-4">
        <p className="text-xs font-medium text-gray-500">
          ShadowEnforcer Recommendation
        </p>
        <p className="mt-1 text-sm text-gray-700">{report.recommendation}</p>
      </div>

      {/* Quick stats summary */}
      <div className="mt-3 flex flex-wrap gap-4 text-xs text-gray-600">
        <span>
          Period: {report.evaluation_period_days} day
          {report.evaluation_period_days !== 1 ? "s" : ""}
        </span>
        <span>Pass: {(report.pass_rate * 100).toFixed(1)}%</span>
        <span>Block: {(report.block_rate * 100).toFixed(1)}%</span>
        <span>Hold: {(report.hold_rate * 100).toFixed(1)}%</span>
        <span>Flag: {(report.flag_rate * 100).toFixed(1)}%</span>
      </div>
    </div>
  );
}
