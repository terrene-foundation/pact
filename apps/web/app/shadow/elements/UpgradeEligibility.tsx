// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * UpgradeEligibility -- card showing posture upgrade eligibility and blockers.
 *
 * Displays whether the agent is eligible for a trust posture upgrade based
 * on ShadowEnforcer metrics, with specific blockers listed when not eligible,
 * and the human-readable recommendation from the ShadowReport.
 */

"use client";

import type { ShadowReport } from "./mock-data";

interface UpgradeEligibilityProps {
  report: ShadowReport;
}

/** Upgrade eligibility card with blockers and recommendation. */
export default function UpgradeEligibility({
  report,
}: UpgradeEligibilityProps) {
  const eligible = report.upgrade_eligible;

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
      </div>

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
