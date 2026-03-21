// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Bridge creation wizard -- multi-step form for creating Cross-Functional Bridges.
 *
 * Steps:
 * 1. Select bridge type (Standing, Scoped, Ad-Hoc) with descriptions
 * 2. Select source and target teams
 * 3. Define permissions (read paths, write paths, message types)
 * 4. Set validity period (for Scoped bridges)
 * 5. Review and submit
 */

"use client";

import { useState } from "react";
import DashboardShell from "../../../components/layout/DashboardShell";
import ErrorAlert from "../../../components/ui/ErrorAlert";
import { getApiClient } from "../../../lib/use-api";
import type { BridgeType, CreateBridgeRequest } from "../../../types/pact";

/** Step definitions for the wizard. */
const STEPS = [
  "Bridge Type",
  "Teams",
  "Permissions",
  "Validity",
  "Review",
] as const;

/** Bridge type descriptions. */
const BRIDGE_TYPES: Array<{
  value: BridgeType;
  label: string;
  description: string;
}> = [
  {
    value: "standing",
    label: "Standing",
    description:
      "Permanent relationship between teams. Remains active until explicitly closed or revoked. Best for teams that regularly need to share data.",
  },
  {
    value: "scoped",
    label: "Scoped",
    description:
      "Time-bounded bridge with a specific validity period. Automatically expires after the configured duration. Ideal for project-based collaboration.",
  },
  {
    value: "ad_hoc",
    label: "Ad-Hoc",
    description:
      "One-time request/response bridge. Carries a request payload and auto-closes after a response is provided. For single governance reviews or approvals.",
  },
];

export default function CreateBridgePage() {
  const [currentStep, setCurrentStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Form state
  const [bridgeType, setBridgeType] = useState<BridgeType | "">("");
  const [sourceTeamId, setSourceTeamId] = useState("");
  const [targetTeamId, setTargetTeamId] = useState("");
  const [purpose, setPurpose] = useState("");
  const [readPaths, setReadPaths] = useState("");
  const [writePaths, setWritePaths] = useState("");
  const [messageTypes, setMessageTypes] = useState("");
  const [validDays, setValidDays] = useState(7);
  const [requestPayload, setRequestPayload] = useState("");

  const canProceed = (): boolean => {
    switch (currentStep) {
      case 0:
        return bridgeType !== "";
      case 1:
        return (
          sourceTeamId.trim() !== "" &&
          targetTeamId.trim() !== "" &&
          purpose.trim() !== ""
        );
      case 2:
        return true; // Permissions are optional
      case 3:
        return true; // Validity step always passable (only relevant for scoped)
      case 4:
        return true; // Review step
      default:
        return false;
    }
  };

  const handleSubmit = async () => {
    if (!bridgeType) return;

    setSubmitting(true);
    setSubmitError(null);

    const data: CreateBridgeRequest = {
      bridge_type: bridgeType,
      source_team_id: sourceTeamId.trim(),
      target_team_id: targetTeamId.trim(),
      purpose: purpose.trim(),
      permissions: {
        read_paths: readPaths
          .split("\n")
          .map((p) => p.trim())
          .filter(Boolean),
        write_paths: writePaths
          .split("\n")
          .map((p) => p.trim())
          .filter(Boolean),
        message_types: messageTypes
          .split("\n")
          .map((p) => p.trim())
          .filter(Boolean),
      },
    };

    if (bridgeType === "scoped") {
      data.valid_days = validDays;
    }

    if (bridgeType === "ad_hoc" && requestPayload.trim()) {
      try {
        data.request_payload = JSON.parse(requestPayload);
      } catch {
        data.request_payload = { content: requestPayload.trim() };
      }
    }

    try {
      const client = getApiClient();
      const result = await client.createBridge(data);
      if (result.status === "error") {
        setSubmitError(result.error ?? "Bridge creation failed");
      } else if (result.data) {
        window.location.href = `/bridges/${result.data.bridge_id}`;
      }
    } catch (err) {
      setSubmitError(
        err instanceof Error ? err.message : "Bridge creation failed",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <DashboardShell
      activePath="/bridges"
      title="Create Bridge"
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Bridges", href: "/bridges" },
        { label: "Create" },
      ]}
    >
      <div className="mx-auto max-w-2xl space-y-6">
        {/* Step indicator */}
        <nav aria-label="Bridge creation progress">
          <ol className="flex items-center justify-between">
            {STEPS.map((step, idx) => (
              <li key={step} className="flex items-center">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${
                    idx === currentStep
                      ? "bg-blue-600 text-white"
                      : idx < currentStep
                        ? "bg-green-500 text-white"
                        : "bg-gray-200 text-gray-500"
                  }`}
                  aria-current={idx === currentStep ? "step" : undefined}
                  aria-label={`Step ${idx + 1}: ${step}${idx < currentStep ? " (completed)" : idx === currentStep ? " (current)" : ""}`}
                >
                  {idx < currentStep ? "\u2713" : idx + 1}
                </div>
                <span
                  className={`ml-2 text-xs hidden sm:inline ${
                    idx === currentStep
                      ? "font-medium text-gray-900"
                      : "text-gray-500"
                  }`}
                >
                  {step}
                </span>
                {idx < STEPS.length - 1 && (
                  <div
                    className="mx-2 h-px w-8 bg-gray-300 sm:w-12"
                    aria-hidden="true"
                  />
                )}
              </li>
            ))}
          </ol>
        </nav>

        {submitError && (
          <ErrorAlert
            message={submitError}
            onRetry={() => setSubmitError(null)}
          />
        )}

        {/* Step content */}
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          {/* Step 1: Bridge Type */}
          {currentStep === 0 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Select Bridge Type
              </h2>
              <div className="space-y-3">
                {BRIDGE_TYPES.map((bt) => (
                  <label
                    key={bt.value}
                    className={`flex cursor-pointer rounded-lg border p-4 transition-colors ${
                      bridgeType === bt.value
                        ? "border-blue-500 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <input
                      type="radio"
                      name="bridgeType"
                      value={bt.value}
                      checked={bridgeType === bt.value}
                      onChange={() => setBridgeType(bt.value)}
                      className="mt-1 mr-3"
                    />
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {bt.label}
                      </p>
                      <p className="mt-1 text-xs text-gray-500">
                        {bt.description}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          {/* Step 2: Teams */}
          {currentStep === 1 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Select Source and Target Teams
              </h2>
              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="bridge-source-team"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Source Team ID
                  </label>
                  <input
                    id="bridge-source-team"
                    type="text"
                    value={sourceTeamId}
                    onChange={(e) => setSourceTeamId(e.target.value)}
                    placeholder="e.g., team-dm"
                    aria-required="true"
                    aria-describedby="bridge-source-team-desc"
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <p
                    id="bridge-source-team-desc"
                    className="mt-1 text-xs text-gray-500"
                  >
                    The team initiating the bridge request.
                  </p>
                </div>
                <div>
                  <label
                    htmlFor="bridge-target-team"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Target Team ID
                  </label>
                  <input
                    id="bridge-target-team"
                    type="text"
                    value={targetTeamId}
                    onChange={(e) => setTargetTeamId(e.target.value)}
                    placeholder="e.g., team-standards"
                    aria-required="true"
                    aria-describedby="bridge-target-team-desc"
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <p
                    id="bridge-target-team-desc"
                    className="mt-1 text-xs text-gray-500"
                  >
                    The team that will receive or respond to bridge requests.
                  </p>
                </div>
                <div>
                  <label
                    htmlFor="bridge-purpose"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Purpose
                  </label>
                  <input
                    id="bridge-purpose"
                    type="text"
                    value={purpose}
                    onChange={(e) => setPurpose(e.target.value)}
                    placeholder="e.g., Content review and approval"
                    aria-required="true"
                    aria-describedby="bridge-purpose-desc"
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <p
                    id="bridge-purpose-desc"
                    className="mt-1 text-xs text-gray-500"
                  >
                    A clear description of why this bridge is needed.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Permissions */}
          {currentStep === 2 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Define Permissions
              </h2>
              <p className="text-xs text-gray-500 mb-4">
                Specify access paths and message types. Enter one per line. Use
                glob patterns for paths (e.g., workspaces/dm/content/*).
              </p>
              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="bridge-read-paths"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Read Paths
                  </label>
                  <textarea
                    id="bridge-read-paths"
                    value={readPaths}
                    onChange={(e) => setReadPaths(e.target.value)}
                    placeholder="workspaces/dm/content/*&#10;workspaces/dm/analytics/*"
                    rows={3}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label
                    htmlFor="bridge-write-paths"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Write Paths
                  </label>
                  <textarea
                    id="bridge-write-paths"
                    value={writePaths}
                    onChange={(e) => setWritePaths(e.target.value)}
                    placeholder="workspaces/dm/reviews/*"
                    rows={2}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label
                    htmlFor="bridge-message-types"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Message Types
                  </label>
                  <textarea
                    id="bridge-message-types"
                    value={messageTypes}
                    onChange={(e) => setMessageTypes(e.target.value)}
                    placeholder="review_request&#10;approval_response"
                    rows={2}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Validity */}
          {currentStep === 3 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Set Validity Period
              </h2>
              {bridgeType === "scoped" ? (
                <div>
                  <label
                    htmlFor="bridge-valid-days"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Valid for (days)
                  </label>
                  <input
                    id="bridge-valid-days"
                    type="number"
                    value={validDays}
                    onChange={(e) =>
                      setValidDays(Math.max(1, parseInt(e.target.value) || 1))
                    }
                    min={1}
                    max={365}
                    className="w-32 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <p className="mt-2 text-xs text-gray-500">
                    The bridge will automatically expire after {validDays} day
                    {validDays !== 1 ? "s" : ""}.
                  </p>
                </div>
              ) : bridgeType === "ad_hoc" ? (
                <div>
                  <label
                    htmlFor="bridge-request-payload"
                    className="block text-sm font-medium text-gray-700 mb-1"
                  >
                    Request Payload (optional)
                  </label>
                  <textarea
                    id="bridge-request-payload"
                    value={requestPayload}
                    onChange={(e) => setRequestPayload(e.target.value)}
                    placeholder='{"review_type": "governance", "document": "constitution-v2.md"}'
                    rows={4}
                    className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm font-mono focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <p className="mt-2 text-xs text-gray-500">
                    Ad-Hoc bridges carry a request payload. Enter JSON or plain
                    text. The bridge auto-closes after a response is provided.
                  </p>
                </div>
              ) : (
                <div className="rounded-lg bg-gray-50 p-4">
                  <p className="text-sm text-gray-600">
                    Standing bridges have no expiry. They remain active until
                    explicitly closed or revoked. No additional configuration is
                    needed for this step.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Step 5: Review */}
          {currentStep === 4 && (
            <div>
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Review and Submit
              </h2>
              <div className="space-y-3 rounded-lg bg-gray-50 p-4">
                <div className="flex justify-between">
                  <span className="text-xs text-gray-500">Type</span>
                  <span className="text-sm font-medium text-gray-900">
                    {BRIDGE_TYPES.find((bt) => bt.value === bridgeType)
                      ?.label ?? bridgeType}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-gray-500">Source Team</span>
                  <span className="text-sm font-medium text-gray-900">
                    {sourceTeamId}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-gray-500">Target Team</span>
                  <span className="text-sm font-medium text-gray-900">
                    {targetTeamId}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-gray-500">Purpose</span>
                  <span className="text-sm text-gray-900">{purpose}</span>
                </div>
                {readPaths.trim() && (
                  <div>
                    <span className="text-xs text-gray-500">Read Paths</span>
                    <pre className="mt-1 text-xs font-mono text-gray-700 bg-white rounded p-2">
                      {readPaths.trim()}
                    </pre>
                  </div>
                )}
                {writePaths.trim() && (
                  <div>
                    <span className="text-xs text-gray-500">Write Paths</span>
                    <pre className="mt-1 text-xs font-mono text-gray-700 bg-white rounded p-2">
                      {writePaths.trim()}
                    </pre>
                  </div>
                )}
                {messageTypes.trim() && (
                  <div>
                    <span className="text-xs text-gray-500">Message Types</span>
                    <pre className="mt-1 text-xs font-mono text-gray-700 bg-white rounded p-2">
                      {messageTypes.trim()}
                    </pre>
                  </div>
                )}
                {bridgeType === "scoped" && (
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-500">Valid Days</span>
                    <span className="text-sm font-medium text-gray-900">
                      {validDays}
                    </span>
                  </div>
                )}
              </div>
              <p className="mt-4 text-xs text-gray-500">
                After submission, the bridge will be in PENDING status and
                require bilateral approval from both source and target teams
                before it becomes ACTIVE.
              </p>
            </div>
          )}
        </div>

        {/* Navigation buttons */}
        <div className="flex justify-between">
          <button
            onClick={() => setCurrentStep((s) => Math.max(0, s - 1))}
            disabled={currentStep === 0}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
          >
            Back
          </button>
          {currentStep < STEPS.length - 1 ? (
            <button
              onClick={() => setCurrentStep((s) => s + 1)}
              disabled={!canProceed()}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting || !canProceed()}
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {submitting ? "Creating..." : "Create Bridge"}
            </button>
          )}
        </div>
      </div>
    </DashboardShell>
  );
}
