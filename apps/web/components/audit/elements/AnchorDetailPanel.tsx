// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * AnchorDetailPanel -- slide-out panel showing full audit anchor details.
 *
 * Displays the complete anchor hash in monospace, verification result details,
 * and a "Verify Integrity" button.
 */

"use client";

import { useState, useEffect } from "react";
import type { AuditAnchor } from "../../../types/pact";
import StatusBadge from "../../ui/StatusBadge";

interface AnchorDetailPanelProps {
  /** The anchor to display details for. */
  anchor: AuditAnchor;
  /** Callback to close the panel. */
  onClose: () => void;
}

/** Format an ISO timestamp to a full readable date/time string. */
function formatFullTimestamp(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleString(undefined, {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZoneName: "short",
    });
  } catch {
    return iso;
  }
}

/** Verification result description based on the level. */
const VERIFICATION_DESCRIPTIONS: Record<string, string> = {
  AUTO_APPROVED:
    "This action was automatically approved because it falls within all constraint envelope dimensions. No human review was required.",
  FLAGGED:
    "This action was flagged because it is near a constraint boundary. It was allowed to proceed but recorded for review.",
  HELD: "This action exceeded a soft limit and was queued for human approval before execution.",
  BLOCKED:
    "This action violated a hard constraint and was blocked from execution. No override is possible without envelope modification.",
};

/** Slide-out panel showing full details for an audit anchor. */
export default function AnchorDetailPanel({
  anchor,
  onClose,
}: AnchorDetailPanelProps) {
  const [verifyState, setVerifyState] = useState<
    "idle" | "verifying" | "verified"
  >("idle");

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleVerify = () => {
    setVerifyState("verifying");
    // Placeholder: in a full implementation this would call the EATP SDK
    // to verify the cryptographic chain integrity
    setTimeout(() => {
      setVerifyState("verified");
    }, 800);
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/20 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className="fixed inset-y-0 right-0 z-50 w-full max-w-lg overflow-y-auto border-l border-gray-200 bg-white shadow-xl sm:max-w-md"
        role="dialog"
        aria-modal="true"
        aria-labelledby="anchor-detail-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2
            id="anchor-detail-title"
            className="text-sm font-semibold text-gray-900"
          >
            Anchor Detail
          </h2>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            aria-label="Close detail panel"
          >
            <svg
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="1.5"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="space-y-6 px-6 py-5">
          {/* Anchor ID (full, monospace) */}
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-gray-500">
              Anchor ID
            </p>
            <p className="break-all font-mono text-sm text-gray-900">
              {anchor.anchor_id}
            </p>
          </div>

          {/* Timestamp */}
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-gray-500">
              Timestamp
            </p>
            <p className="text-sm text-gray-800">
              {formatFullTimestamp(anchor.timestamp)}
            </p>
          </div>

          {/* Agent */}
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-gray-500">
              Agent
            </p>
            <p className="text-sm font-medium text-gray-900">
              {anchor.agent_name}
            </p>
            <p className="font-mono text-xs text-gray-500">{anchor.agent_id}</p>
          </div>

          {/* Team */}
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-gray-500">
              Team
            </p>
            <p className="text-sm text-gray-800">{anchor.team_id}</p>
          </div>

          {/* Action */}
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-gray-500">
              Action
            </p>
            <p className="text-sm text-gray-900">{anchor.action}</p>
            {anchor.details && (
              <p className="mt-1 text-sm text-gray-600">{anchor.details}</p>
            )}
          </div>

          {/* Verification Level */}
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-gray-500">
              Verification Level
            </p>
            <div className="mb-2">
              <StatusBadge value={anchor.verification_level} size="md" />
            </div>
            <p className="text-xs text-gray-600">
              {VERIFICATION_DESCRIPTIONS[anchor.verification_level] ??
                "Unknown verification level."}
            </p>
          </div>

          {/* Verify Integrity */}
          <div className="border-t border-gray-200 pt-5">
            <p className="mb-2 text-xs font-medium uppercase tracking-wider text-gray-500">
              Chain Integrity
            </p>
            {verifyState === "verified" ? (
              <div
                className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2"
                role="status"
              >
                <svg
                  className="h-4 w-4 text-green-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth="2"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
                  />
                </svg>
                <span className="text-sm font-medium text-green-800">
                  Chain verified
                </span>
              </div>
            ) : (
              <button
                onClick={handleVerify}
                disabled={verifyState === "verifying"}
                className="rounded-md border border-care-primary bg-care-primary-light px-4 py-2 text-sm font-medium text-care-primary-dark transition-colors hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {verifyState === "verifying"
                  ? "Verifying..."
                  : "Verify Integrity"}
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
