// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * TaskSubmissionForm -- form for submitting tasks to the DM team.
 *
 * Provides a text area for the task description, an optional agent
 * selector dropdown (with an "Auto-route" default), and a submit
 * button. After submission, displays the task status inline with
 * polling until the task reaches a terminal state.
 */

"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getApiClient } from "../../../lib/use-api";
import { ApiError, NetworkError } from "../../../lib/api";
import type { DmAgentSummary, DmTask, DmTaskStatus } from "../../../types/pact";

interface TaskSubmissionFormProps {
  /** Available agents for the target selector. */
  agents: DmAgentSummary[];
}

/** Status label and color mapping for task status display. */
const STATUS_CONFIG: Record<
  DmTaskStatus,
  {
    label: string;
    color: string;
    bgColor: string;
    borderColor: string;
    isTerminal: boolean;
  }
> = {
  pending: {
    label: "Pending",
    color: "text-yellow-800",
    bgColor: "bg-yellow-50",
    borderColor: "border-yellow-200",
    isTerminal: false,
  },
  routing: {
    label: "Routing to agent...",
    color: "text-blue-800",
    bgColor: "bg-blue-50",
    borderColor: "border-blue-200",
    isTerminal: false,
  },
  executing: {
    label: "Executing",
    color: "text-purple-800",
    bgColor: "bg-purple-50",
    borderColor: "border-purple-200",
    isTerminal: false,
  },
  complete: {
    label: "Complete",
    color: "text-green-800",
    bgColor: "bg-green-50",
    borderColor: "border-green-200",
    isTerminal: true,
  },
  held: {
    label: "Held for approval",
    color: "text-orange-800",
    bgColor: "bg-orange-50",
    borderColor: "border-orange-200",
    isTerminal: true,
  },
  failed: {
    label: "Failed",
    color: "text-red-800",
    bgColor: "bg-red-50",
    borderColor: "border-red-200",
    isTerminal: true,
  },
};

/** Task submission form with inline status tracking. */
export default function TaskSubmissionForm({
  agents,
}: TaskSubmissionFormProps) {
  const [description, setDescription] = useState("");
  const [targetAgent, setTargetAgent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [activeTask, setActiveTask] = useState<DmTask | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, []);

  /** Poll for task status updates until a terminal state is reached. */
  const pollTaskStatus = useCallback((taskId: string) => {
    const client = getApiClient();

    const poll = () => {
      client
        .getDmTaskStatus(taskId)
        .then((response) => {
          if (!mountedRef.current) return;

          if (response.status === "ok" && response.data) {
            setActiveTask(response.data);
            const config = STATUS_CONFIG[response.data.status];
            if (!config.isTerminal) {
              pollTimerRef.current = setTimeout(poll, 2000);
            }
          }
        })
        .catch(() => {
          // Silently stop polling on error -- the task status card
          // will show the last known state.
        });
    };

    pollTimerRef.current = setTimeout(poll, 1500);
  }, []);

  /** Handle form submission. */
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const trimmed = description.trim();
    if (!trimmed) return;

    setSubmitting(true);
    setSubmitError(null);
    setActiveTask(null);

    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }

    const client = getApiClient();
    client
      .submitDmTask(trimmed, targetAgent || undefined)
      .then((response) => {
        if (!mountedRef.current) return;

        if (response.status === "error") {
          setSubmitError(response.error ?? "Failed to submit task");
          return;
        }

        if (response.data) {
          setActiveTask(response.data);
          setDescription("");

          // Start polling if task is not already terminal
          const config = STATUS_CONFIG[response.data.status];
          if (!config.isTerminal) {
            pollTaskStatus(response.data.task_id);
          }
        }
      })
      .catch((err: unknown) => {
        if (!mountedRef.current) return;

        if (err instanceof ApiError) {
          if (err.statusCode === 404) {
            setSubmitError(
              "The task submission endpoint is not available yet. " +
                "The DM team backend may still be provisioning.",
            );
          } else {
            setSubmitError(`API error (${err.statusCode}): ${err.message}`);
          }
        } else if (err instanceof NetworkError) {
          setSubmitError(`Network error: ${err.message}`);
        } else {
          setSubmitError(
            err instanceof Error ? err.message : "Unknown error occurred",
          );
        }
      })
      .finally(() => {
        if (mountedRef.current) {
          setSubmitting(false);
        }
      });
  };

  /** Dismiss the active task card and reset the form. */
  const handleDismissTask = () => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    setActiveTask(null);
    setSubmitError(null);
  };

  const activeAgents = agents.filter((a) => a.status === "active");

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6">
      <h2 className="mb-1 text-base font-semibold text-gray-900">
        Submit Task
      </h2>
      <p className="mb-4 text-sm text-gray-500">
        Describe what you need done. The DM team will route the task to the most
        suitable agent, or you can pick one.
      </p>

      <form onSubmit={handleSubmit}>
        {/* Task description */}
        <label htmlFor="task-description" className="sr-only">
          Task description
        </label>
        <textarea
          id="task-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Describe the task..."
          rows={3}
          disabled={submitting}
          className="mb-3 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
        />

        {/* Agent selector + submit */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label htmlFor="target-agent" className="sr-only">
            Target agent
          </label>
          <select
            id="target-agent"
            value={targetAgent}
            onChange={(e) => setTargetAgent(e.target.value)}
            disabled={submitting}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 sm:w-56"
          >
            <option value="">Auto-route (recommended)</option>
            {activeAgents.map((agent) => (
              <option key={agent.agent_id} value={agent.agent_id}>
                {agent.name}
              </option>
            ))}
          </select>

          <button
            type="submit"
            disabled={submitting || !description.trim()}
            className="inline-flex items-center justify-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? (
              <>
                <svg
                  className="mr-2 h-4 w-4 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
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
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
                Submitting...
              </>
            ) : (
              "Submit Task"
            )}
          </button>
        </div>
      </form>

      {/* Submission error */}
      {submitError && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3">
          <p className="text-sm text-red-700">{submitError}</p>
        </div>
      )}

      {/* Active task status */}
      {activeTask && (
        <TaskStatusCard task={activeTask} onDismiss={handleDismissTask} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Task Status Card (inline display below the form)
// ---------------------------------------------------------------------------

interface TaskStatusCardProps {
  task: DmTask;
  onDismiss: () => void;
}

/** Inline card showing the status and result of a submitted task. */
function TaskStatusCard({ task, onDismiss }: TaskStatusCardProps) {
  const config = STATUS_CONFIG[task.status];

  return (
    <div
      className={`mt-4 rounded-lg border p-4 ${config.borderColor} ${config.bgColor}`}
    >
      <div className="flex items-start justify-between">
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${config.color} ${config.borderColor}`}
              role="status"
            >
              {!config.isTerminal && (
                <svg
                  className="mr-1 h-3 w-3 animate-spin"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
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
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  />
                </svg>
              )}
              {config.label}
            </span>
            {task.target_agent && (
              <span className="text-xs text-gray-500">
                Agent: {task.target_agent}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-700 truncate">{task.description}</p>

          {/* Task result */}
          {task.result && (
            <div className="mt-2 rounded border border-gray-200 bg-white p-3">
              <p className="text-xs font-medium text-gray-500 mb-1">Result</p>
              <p className="text-sm text-gray-800 whitespace-pre-wrap">
                {task.result}
              </p>
            </div>
          )}
        </div>

        {/* Dismiss button (only on terminal states) */}
        {config.isTerminal && (
          <button
            onClick={onDismiss}
            className="ml-3 flex-shrink-0 rounded p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-600 transition-colors"
            aria-label="Dismiss task status"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
