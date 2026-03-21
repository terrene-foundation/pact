// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * PostureUpgradeWizard -- multi-step modal guiding governance officers through
 * reviewing evidence and approving agent posture upgrades.
 *
 * Three steps:
 *   1. Current Status -- shows current posture, target posture, and requirements
 *   2. Evidence Review -- agent evidence vs. each requirement with progress bars
 *   3. Decision -- approve (if eligible), override (with warning), or dismiss
 *
 * The upgrade requirements mirror UPGRADE_REQUIREMENTS from
 * src/pact/trust/posture.py.
 */

"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import PostureBadge from "./PostureBadge";
import { useApi } from "../../lib/use-api";
import type { TrustPosture, AgentDetail } from "../../types/pact";

// ---------------------------------------------------------------------------
// Constants -- mirrors Python UPGRADE_REQUIREMENTS
// ---------------------------------------------------------------------------

/** All trust postures in ascending autonomy order. */
const ALL_POSTURES: TrustPosture[] = [
  "pseudo_agent",
  "supervised",
  "shared_planning",
  "continuous_insight",
  "delegated",
];

/** Human-readable posture labels. */
const POSTURE_LABELS: Record<TrustPosture, string> = {
  pseudo_agent: "Pseudo Agent",
  supervised: "Supervised",
  shared_planning: "Shared Planning",
  continuous_insight: "Continuous Insight",
  delegated: "Delegated",
};

/** Posture descriptions for Step 1 context. */
const POSTURE_DESCRIPTIONS: Record<TrustPosture, string> = {
  pseudo_agent: "Minimal autonomy, maximum oversight",
  supervised: "Executes under close human supervision",
  shared_planning: "Human and agent plan together, agent executes",
  continuous_insight: "Agent operates autonomously, human monitors",
  delegated: "Full delegation within constraint envelope",
};

/**
 * Upgrade requirements per target posture.
 * Mirrors UPGRADE_REQUIREMENTS from src/pact/trust/posture.py.
 */
interface UpgradeRequirements {
  min_days: number;
  min_operations: number;
  min_success_rate: number;
  max_incidents?: number;
  shadow_enforcer_required?: boolean;
  shadow_pass_rate?: number;
}

const UPGRADE_REQUIREMENTS: Partial<Record<TrustPosture, UpgradeRequirements>> =
  {
    supervised: {
      min_days: 7,
      min_operations: 10,
      min_success_rate: 0.9,
      max_incidents: 0,
    },
    shared_planning: {
      min_days: 90,
      min_success_rate: 0.95,
      min_operations: 100,
      shadow_enforcer_required: true,
      shadow_pass_rate: 0.9,
    },
    continuous_insight: {
      min_days: 180,
      min_success_rate: 0.98,
      min_operations: 500,
      shadow_enforcer_required: true,
      shadow_pass_rate: 0.95,
    },
    delegated: {
      min_days: 365,
      min_success_rate: 0.99,
      min_operations: 1000,
      shadow_enforcer_required: true,
      shadow_pass_rate: 0.98,
    },
  };

// ---------------------------------------------------------------------------
// Evidence shape
// ---------------------------------------------------------------------------

/**
 * Agent upgrade evidence -- in a production system this would come from
 * an API endpoint (e.g., GET /api/v1/agents/{id}/upgrade-evidence).
 *
 * TODO: Replace placeholder data with real API call once the endpoint exists.
 */
export interface UpgradeEvidence {
  days_at_current_posture: number;
  total_operations: number;
  successful_operations: number;
  success_rate: number;
  shadow_enforcer_pass_rate: number | null;
  incidents: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Get the next posture in the autonomy ladder, or null if already at max. */
function getNextPosture(current: TrustPosture): TrustPosture | null {
  const idx = ALL_POSTURES.indexOf(current);
  if (idx < 0 || idx >= ALL_POSTURES.length - 1) return null;
  return ALL_POSTURES[idx + 1];
}

/** Evaluate evidence against requirements. Returns list of blockers. */
function evaluateBlockers(
  evidence: UpgradeEvidence,
  requirements: UpgradeRequirements,
): string[] {
  const blockers: string[] = [];

  if (evidence.days_at_current_posture < requirements.min_days) {
    blockers.push(
      `Needs ${requirements.min_days} days at current posture (currently ${evidence.days_at_current_posture})`,
    );
  }
  if (evidence.total_operations < requirements.min_operations) {
    blockers.push(
      `Needs ${requirements.min_operations} total operations (currently ${evidence.total_operations})`,
    );
  }
  if (evidence.success_rate < requirements.min_success_rate) {
    blockers.push(
      `Needs ${fmt(requirements.min_success_rate)} success rate (currently ${fmt(evidence.success_rate)})`,
    );
  }
  if (
    requirements.shadow_enforcer_required &&
    requirements.shadow_pass_rate !== undefined
  ) {
    if (evidence.shadow_enforcer_pass_rate === null) {
      blockers.push("ShadowEnforcer evidence required but not available");
    } else if (
      evidence.shadow_enforcer_pass_rate < requirements.shadow_pass_rate
    ) {
      blockers.push(
        `Needs ${fmt(requirements.shadow_pass_rate)} ShadowEnforcer pass rate (currently ${fmt(evidence.shadow_enforcer_pass_rate)})`,
      );
    }
  }
  if (evidence.incidents > 0) {
    blockers.push(
      `${evidence.incidents} unresolved incident${evidence.incidents > 1 ? "s" : ""} must be resolved`,
    );
  }

  return blockers;
}

/** Format a ratio as a percentage string. */
function fmt(ratio: number): string {
  return `${Math.round(ratio * 100)}%`;
}

/** Clamp a value between 0 and 1. */
function clamp01(val: number): number {
  return Math.max(0, Math.min(1, val));
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Step indicator dots. */
function StepIndicator({
  currentStep,
  totalSteps,
}: {
  currentStep: number;
  totalSteps: number;
}) {
  const stepLabels = ["Current Status", "Evidence Review", "Decision"];
  return (
    <div className="flex items-center justify-center gap-2">
      {Array.from({ length: totalSteps }, (_, i) => {
        const stepNum = i + 1;
        const isActive = stepNum === currentStep;
        const isComplete = stepNum < currentStep;
        return (
          <div key={stepNum} className="flex items-center gap-2">
            {i > 0 && (
              <div
                className={`h-px w-8 ${isComplete ? "bg-blue-500" : "bg-gray-200"}`}
              />
            )}
            <div className="flex flex-col items-center gap-1">
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                  isActive
                    ? "bg-blue-600 text-white"
                    : isComplete
                      ? "bg-blue-100 text-blue-700"
                      : "bg-gray-100 text-gray-400"
                }`}
              >
                {isComplete ? (
                  <svg
                    className="h-3.5 w-3.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2.5}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                ) : (
                  stepNum
                )}
              </div>
              <span
                className={`text-[10px] font-medium ${isActive ? "text-blue-700" : "text-gray-400"}`}
              >
                {stepLabels[i]}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Progress bar for a metric (days, operations). */
function MetricProgressBar({
  label,
  current,
  required,
  unit,
}: {
  label: string;
  current: number;
  required: number;
  unit?: string;
}) {
  const ratio = required > 0 ? clamp01(current / required) : 0;
  const percent = Math.round(ratio * 100);
  const met = current >= required;
  const barColor = met ? "bg-green-500" : "bg-red-400";
  const textColor = met ? "text-green-700" : "text-red-600";

  return (
    <div className="w-full">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className={`text-sm font-semibold ${textColor}`}>
          {current.toLocaleString()}
          {unit ? ` ${unit}` : ""} / {required.toLocaleString()}
          {unit ? ` ${unit}` : ""} required
        </span>
      </div>
      <div className="h-2.5 w-full rounded-full bg-gray-200">
        <div
          className={`h-2.5 rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${percent}%` }}
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label}: ${percent}%`}
        />
      </div>
      {met && (
        <div className="mt-1 flex items-center gap-1">
          <svg
            className="h-3.5 w-3.5 text-green-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          <span className="text-xs text-green-600">Requirement met</span>
        </div>
      )}
    </div>
  );
}

/** Percentage gauge for rates (success rate, shadow pass rate). */
function RateGauge({
  label,
  current,
  required,
  useGradient,
}: {
  label: string;
  current: number;
  required: number;
  useGradient?: boolean;
}) {
  const percent = Math.round(current * 100);
  const reqPercent = Math.round(required * 100);
  const met = current >= required;
  const textColor = met ? "text-green-700" : "text-red-600";

  // For the gradient variant, transition through colors
  let barColor: string;
  if (useGradient) {
    if (percent >= reqPercent) {
      barColor = "bg-gradient-to-r from-green-400 to-green-600";
    } else if (percent >= reqPercent * 0.8) {
      barColor = "bg-gradient-to-r from-yellow-400 to-orange-500";
    } else {
      barColor = "bg-gradient-to-r from-red-400 to-red-500";
    }
  } else {
    barColor = met ? "bg-green-500" : "bg-red-400";
  }

  // Marker position for the required threshold
  const markerLeft = clamp01(required) * 100;

  return (
    <div className="w-full">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className={`text-sm font-semibold ${textColor}`}>
          {percent}% / {reqPercent}% required
        </span>
      </div>
      <div className="relative h-3 w-full rounded-full bg-gray-200">
        <div
          className={`h-3 rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${clamp01(current) * 100}%` }}
          role="progressbar"
          aria-valuenow={percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${label}: ${percent}%`}
        />
        {/* Threshold marker */}
        <div
          className="absolute top-0 h-3 w-0.5 bg-gray-600"
          style={{ left: `${markerLeft}%` }}
          title={`Required: ${reqPercent}%`}
        />
      </div>
      <div className="mt-1 flex items-center justify-between">
        {met ? (
          <div className="flex items-center gap-1">
            <svg
              className="h-3.5 w-3.5 text-green-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
            <span className="text-xs text-green-600">Requirement met</span>
          </div>
        ) : (
          <span className="text-xs text-red-500">
            Below threshold ({reqPercent - percent}% short)
          </span>
        )}
        <span className="text-xs text-gray-400">
          Marker = {reqPercent}% threshold
        </span>
      </div>
    </div>
  );
}

/** Blocker list for Step 2 or 3. */
function BlockerList({ blockers }: { blockers: string[] }) {
  if (blockers.length === 0) return null;
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4">
      <h4 className="mb-2 text-sm font-semibold text-red-800">
        Upgrade Blockers ({blockers.length})
      </h4>
      <ul className="space-y-1">
        {blockers.map((blocker, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-red-700">
            <svg
              className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
            {blocker}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface PostureUpgradeWizardProps {
  /** Whether the wizard is open. */
  open: boolean;
  /** Callback to close the wizard. */
  onClose: () => void;
  /** The agent detail data. */
  agent: AgentDetail;
  /** Callback when the upgrade is approved. */
  onApprove: (reason: string, override: boolean) => void | Promise<void>;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function PostureUpgradeWizard({
  open,
  onClose,
  agent,
  onApprove,
}: PostureUpgradeWizardProps) {
  const [step, setStep] = useState(1);
  const [reason, setReason] = useState("");
  const [overrideMode, setOverrideMode] = useState(false);
  const [overrideConfirmed, setOverrideConfirmed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const backdropRef = useRef<HTMLDivElement>(null);
  const reasonRef = useRef<HTMLTextAreaElement>(null);

  // Derive target posture
  const targetPosture = useMemo(
    () => getNextPosture(agent.posture),
    [agent.posture],
  );

  // Derive requirements for target
  const requirements = useMemo(
    () => (targetPosture ? UPGRADE_REQUIREMENTS[targetPosture] : undefined),
    [targetPosture],
  );

  // Fetch upgrade evidence from the backend API
  const {
    data: evidenceData,
    loading: evidenceLoading,
    error: evidenceError,
  } = useApi(
    (client) => client.upgradeEvidence(agent.agent_id),
    [agent.agent_id, open],
  );

  // Build evidence from API response, with fallback to locally derived data
  const evidence: UpgradeEvidence = useMemo(() => {
    // Derive days from posture_since (using last history entry or created_at)
    const lastChange =
      agent.posture_history.length > 0
        ? agent.posture_history[agent.posture_history.length - 1]
        : null;
    const sinceDate = lastChange
      ? new Date(lastChange.changed_at)
      : new Date(agent.created_at);
    const daysSince = Math.floor(
      (Date.now() - sinceDate.getTime()) / (1000 * 60 * 60 * 24),
    );

    // Use real API data when available
    if (evidenceData) {
      const totalOps = evidenceData.total_operations ?? 0;
      const successOps = evidenceData.successful_operations ?? 0;
      return {
        days_at_current_posture: daysSince,
        total_operations: totalOps,
        successful_operations: successOps,
        success_rate: totalOps > 0 ? successOps / totalOps : 0,
        shadow_enforcer_pass_rate:
          evidenceData.shadow_enforcer_pass_rate ?? null,
        incidents: evidenceData.incidents ?? 0,
      };
    }

    // Fallback: return zero-valued evidence while loading or on error
    return {
      days_at_current_posture: daysSince,
      total_operations: 0,
      successful_operations: 0,
      success_rate: 0,
      shadow_enforcer_pass_rate: null,
      incidents: 0,
    };
  }, [agent, evidenceData]);

  // Evaluate blockers
  const blockers = useMemo(() => {
    if (!requirements) return [];
    return evaluateBlockers(evidence, requirements);
  }, [evidence, requirements]);

  const isEligible = blockers.length === 0;

  // Reset state when modal opens
  useEffect(() => {
    if (open) {
      setStep(1);
      setReason("");
      setOverrideMode(false);
      setOverrideConfirmed(false);
      setSubmitting(false);
      setError(null);
    }
  }, [open]);

  // Focus reason input when reaching step 3
  useEffect(() => {
    if (step === 3) {
      requestAnimationFrame(() => {
        reasonRef.current?.focus();
      });
    }
  }, [step]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, submitting, onClose]);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === backdropRef.current && !submitting) {
        onClose();
      }
    },
    [submitting, onClose],
  );

  const handleApprove = useCallback(async () => {
    if (!reason.trim()) {
      setError("A reason is required for the upgrade decision.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await onApprove(reason.trim(), overrideMode);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to process upgrade.",
      );
    } finally {
      setSubmitting(false);
    }
  }, [reason, overrideMode, onApprove]);

  if (!open) return null;

  // Cannot upgrade from the highest posture
  if (!targetPosture || !requirements) {
    return (
      <div
        ref={backdropRef}
        onClick={handleBackdropClick}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="wizard-title"
      >
        <div className="w-full max-w-lg rounded-lg border border-gray-200 bg-white shadow-xl">
          <div className="border-b border-gray-100 px-6 py-4">
            <h2
              id="wizard-title"
              className="text-lg font-semibold text-gray-900"
            >
              Posture Upgrade
            </h2>
          </div>
          <div className="px-6 py-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-gray-100">
              <svg
                className="h-6 w-6 text-gray-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <p className="text-sm text-gray-600">
              This agent is already at the highest trust posture (
              {POSTURE_LABELS[agent.posture]}). No further upgrades are
              available.
            </p>
          </div>
          <div className="flex justify-end border-t border-gray-100 px-6 py-4">
            <button
              onClick={onClose}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={backdropRef}
      onClick={handleBackdropClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="wizard-title"
    >
      <div className="flex w-full max-w-2xl flex-col rounded-lg border border-gray-200 bg-white shadow-xl max-h-[90vh]">
        {/* Header */}
        <div className="flex-shrink-0 border-b border-gray-100 px-6 py-4">
          <div className="flex items-center justify-between">
            <h2
              id="wizard-title"
              className="text-lg font-semibold text-gray-900"
            >
              Posture Upgrade Wizard
            </h2>
            <button
              onClick={onClose}
              disabled={submitting}
              className="rounded-md p-1 text-gray-400 hover:text-gray-600 disabled:opacity-50 transition-colors"
              aria-label="Close wizard"
            >
              <svg
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
          <div className="mt-4">
            <StepIndicator currentStep={step} totalSteps={3} />
          </div>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {/* Step 1: Current Status */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h3 className="mb-1 text-sm font-semibold text-gray-900">
                  Agent: {agent.name}
                </h3>
                <p className="text-xs text-gray-500">{agent.role}</p>
              </div>

              {/* Current and target posture */}
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                  <p className="mb-2 text-xs font-medium text-gray-500">
                    Current Posture
                  </p>
                  <PostureBadge posture={agent.posture} size="md" />
                  <p className="mt-2 text-xs text-gray-500">
                    {POSTURE_DESCRIPTIONS[agent.posture]}
                  </p>
                </div>
                <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                  <p className="mb-2 text-xs font-medium text-blue-600">
                    Target Posture
                  </p>
                  <PostureBadge posture={targetPosture} size="md" />
                  <p className="mt-2 text-xs text-blue-600">
                    {POSTURE_DESCRIPTIONS[targetPosture]}
                  </p>
                </div>
              </div>

              {/* Posture progression arrow */}
              <div className="flex items-center justify-center gap-3">
                <PostureBadge posture={agent.posture} size="sm" />
                <svg
                  className="h-5 w-5 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M14 5l7 7m0 0l-7 7m7-7H3"
                  />
                </svg>
                <PostureBadge posture={targetPosture} size="sm" />
              </div>

              {/* Requirements summary */}
              <div className="rounded-lg border border-gray-200 bg-white p-4">
                <h4 className="mb-3 text-sm font-semibold text-gray-900">
                  Requirements for {POSTURE_LABELS[targetPosture]}
                </h4>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
                    <p className="text-xs text-gray-500">Minimum Days</p>
                    <p className="text-sm font-semibold text-gray-900">
                      {requirements.min_days} days
                    </p>
                  </div>
                  <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
                    <p className="text-xs text-gray-500">Minimum Operations</p>
                    <p className="text-sm font-semibold text-gray-900">
                      {requirements.min_operations.toLocaleString()}
                    </p>
                  </div>
                  <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
                    <p className="text-xs text-gray-500">
                      Minimum Success Rate
                    </p>
                    <p className="text-sm font-semibold text-gray-900">
                      {fmt(requirements.min_success_rate)}
                    </p>
                  </div>
                  {requirements.shadow_enforcer_required && (
                    <div className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
                      <p className="text-xs text-gray-500">
                        ShadowEnforcer Pass Rate
                      </p>
                      <p className="text-sm font-semibold text-gray-900">
                        {requirements.shadow_pass_rate !== undefined
                          ? fmt(requirements.shadow_pass_rate)
                          : "Required"}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Evidence Review */}
          {step === 2 && (
            <div className="space-y-6">
              <div>
                <h3 className="mb-1 text-sm font-semibold text-gray-900">
                  Evidence Review
                </h3>
                <p className="text-xs text-gray-500">
                  Comparing {agent.name}&apos;s performance against the
                  requirements for {POSTURE_LABELS[targetPosture]}.
                </p>
              </div>

              {/* Evidence data status */}
              {evidenceLoading && (
                <div className="rounded-lg border border-blue-200 bg-blue-50 p-3">
                  <p className="text-xs text-blue-700">
                    Loading upgrade evidence from ShadowEnforcer metrics...
                  </p>
                </div>
              )}
              {evidenceError && (
                <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-3">
                  <p className="text-xs text-yellow-700">
                    Could not load upgrade evidence from the API. Showing
                    locally derived data only.
                  </p>
                </div>
              )}

              {/* Days at current posture */}
              <MetricProgressBar
                label="Days at Current Posture"
                current={evidence.days_at_current_posture}
                required={requirements.min_days}
                unit="days"
              />

              {/* Total operations */}
              <MetricProgressBar
                label="Total Operations"
                current={evidence.total_operations}
                required={requirements.min_operations}
                unit="ops"
              />

              {/* Success rate */}
              <RateGauge
                label="Success Rate"
                current={evidence.success_rate}
                required={requirements.min_success_rate}
              />

              {/* ShadowEnforcer pass rate (if required) */}
              {requirements.shadow_enforcer_required &&
                requirements.shadow_pass_rate !== undefined && (
                  <RateGauge
                    label="ShadowEnforcer Pass Rate"
                    current={evidence.shadow_enforcer_pass_rate ?? 0}
                    required={requirements.shadow_pass_rate}
                    useGradient
                  />
                )}

              {/* Incidents */}
              {evidence.incidents > 0 && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                  <div className="flex items-center gap-2">
                    <svg
                      className="h-5 w-5 text-red-500"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                      />
                    </svg>
                    <span className="text-sm font-medium text-red-800">
                      {evidence.incidents} Unresolved Incident
                      {evidence.incidents > 1 ? "s" : ""}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-red-600">
                    All incidents must be resolved before a posture upgrade can
                    be approved.
                  </p>
                </div>
              )}

              {/* Blockers */}
              <BlockerList blockers={blockers} />

              {/* All clear */}
              {isEligible && (
                <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                  <div className="flex items-center gap-2">
                    <svg
                      className="h-5 w-5 text-green-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    <span className="text-sm font-medium text-green-800">
                      All requirements met
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-green-600">
                    This agent is eligible for upgrade to{" "}
                    {POSTURE_LABELS[targetPosture]}.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Step 3: Decision */}
          {step === 3 && (
            <div className="space-y-6">
              {/* Eligible state */}
              {isEligible && (
                <>
                  <div className="rounded-lg border border-green-200 bg-green-50 p-4 text-center">
                    <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
                      <svg
                        className="h-6 w-6 text-green-600"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                    </div>
                    <h3 className="text-sm font-semibold text-green-800">
                      Eligible for Upgrade
                    </h3>
                    <p className="mt-1 text-xs text-green-600">
                      {agent.name} meets all requirements for{" "}
                      {POSTURE_LABELS[targetPosture]}.
                    </p>
                  </div>

                  <div>
                    <label
                      htmlFor="upgrade-reason"
                      className="mb-1 block text-sm font-medium text-gray-700"
                    >
                      Approval Reason
                    </label>
                    <textarea
                      ref={reasonRef}
                      id="upgrade-reason"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Describe why you are approving this posture upgrade..."
                      disabled={submitting}
                      rows={3}
                      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                    />
                  </div>
                </>
              )}

              {/* Not eligible state */}
              {!isEligible && (
                <>
                  <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-center">
                    <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                      <svg
                        className="h-6 w-6 text-red-500"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                        />
                      </svg>
                    </div>
                    <h3 className="text-sm font-semibold text-red-800">
                      Not Yet Eligible
                    </h3>
                    <p className="mt-1 text-xs text-red-600">
                      {agent.name} does not meet all requirements for{" "}
                      {POSTURE_LABELS[targetPosture]}.
                    </p>
                  </div>

                  <BlockerList blockers={blockers} />

                  {/* Override option */}
                  {!overrideMode && (
                    <div className="border-t border-gray-100 pt-4">
                      <button
                        onClick={() => setOverrideMode(true)}
                        className="text-sm font-medium text-orange-600 hover:text-orange-800 transition-colors"
                      >
                        Override requirements and approve anyway...
                      </button>
                    </div>
                  )}

                  {overrideMode && (
                    <div className="rounded-lg border border-orange-300 bg-orange-50 p-4 space-y-4">
                      <div className="flex items-start gap-3">
                        <svg
                          className="mt-0.5 h-5 w-5 flex-shrink-0 text-orange-600"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                          />
                        </svg>
                        <div>
                          <h4 className="text-sm font-semibold text-orange-800">
                            Override Warning
                          </h4>
                          <p className="mt-1 text-xs text-orange-700">
                            You are about to override the evidence-based upgrade
                            requirements. This will be recorded in the audit
                            trail as a governance override. The agent has not
                            demonstrated sufficient evidence for this posture
                            level, which may increase operational risk.
                          </p>
                        </div>
                      </div>

                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={overrideConfirmed}
                          onChange={(e) =>
                            setOverrideConfirmed(e.target.checked)
                          }
                          className="h-4 w-4 rounded border-gray-300 text-orange-600 focus:ring-orange-500"
                        />
                        <span className="text-xs font-medium text-orange-800">
                          I understand the risks and accept responsibility for
                          this governance override
                        </span>
                      </label>

                      <div>
                        <label
                          htmlFor="override-reason"
                          className="mb-1 block text-sm font-medium text-orange-800"
                        >
                          Override Reason (required)
                        </label>
                        <textarea
                          ref={reasonRef}
                          id="override-reason"
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                          placeholder="Explain why this override is necessary and what mitigating measures are in place..."
                          disabled={submitting}
                          rows={3}
                          className="w-full rounded-md border border-orange-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500 disabled:opacity-50"
                        />
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Error */}
              {error && (
                <p className="text-sm text-red-600" role="alert">
                  {error}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex-shrink-0 flex items-center justify-between border-t border-gray-100 px-6 py-4">
          <div>
            {step > 1 && (
              <button
                onClick={() => setStep((s) => s - 1)}
                disabled={submitting}
                className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
              >
                Back
              </button>
            )}
          </div>

          <div className="flex gap-3">
            <button
              onClick={onClose}
              disabled={submitting}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>

            {step < 3 && (
              <button
                onClick={() => setStep((s) => s + 1)}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              >
                Next
              </button>
            )}

            {step === 3 && isEligible && (
              <button
                onClick={handleApprove}
                disabled={submitting || !reason.trim()}
                className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
              >
                {submitting ? (
                  <span className="flex items-center gap-2">
                    <svg
                      className="h-4 w-4 animate-spin"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Processing...
                  </span>
                ) : (
                  "Approve Upgrade"
                )}
              </button>
            )}

            {step === 3 && !isEligible && overrideMode && (
              <button
                onClick={handleApprove}
                disabled={submitting || !reason.trim() || !overrideConfirmed}
                className="rounded-md bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-700 disabled:opacity-50 transition-colors focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2"
              >
                {submitting ? (
                  <span className="flex items-center gap-2">
                    <svg
                      className="h-4 w-4 animate-spin"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      />
                    </svg>
                    Processing...
                  </span>
                ) : (
                  "Override & Approve"
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
