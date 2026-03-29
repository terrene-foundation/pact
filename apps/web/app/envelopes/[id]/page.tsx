// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Envelope detail page -- shows all five CARE constraint dimension gauges.
 *
 * Fetches a single envelope by ID and renders utilization gauges for:
 *   1. Financial
 *   2. Operational
 *   3. Temporal
 *   4. Data Access
 *   5. Communication
 */

"use client";

import { use, useState } from "react";
import DashboardShell from "../../../components/layout/DashboardShell";
import DimensionGauge from "../../../components/constraints/DimensionGauge";
import EnvelopeEditSheet from "../../../components/envelopes/elements/EnvelopeEditSheet";
import { Alert, AlertDescription } from "@/components/ui/shadcn/alert";
import { Skeleton } from "@/components/ui/shadcn/skeleton";
import { Button } from "@/components/ui/shadcn/button";
import { useEnvelopeDetail } from "@/hooks";
import { AlertCircle, Pencil } from "lucide-react";

/** SVG icon paths for each dimension. */
const DIMENSION_ICONS = {
  financial:
    "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  operational:
    "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z",
  temporal: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  dataAccess:
    "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4",
  communication:
    "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z",
};

interface EnvelopeDetailPageProps {
  params: Promise<{ id: string }>;
}

export default function EnvelopeDetailPage({
  params,
}: EnvelopeDetailPageProps) {
  const { id } = use(params);
  const [editOpen, setEditOpen] = useState(false);

  const {
    data,
    isLoading: loading,
    error: queryError,
    refetch,
  } = useEnvelopeDetail(id);
  const error = queryError?.message ?? null;

  return (
    <DashboardShell
      activePath="/envelopes"
      title={data?.description ?? `Envelope ${id}`}
      breadcrumbs={[
        { label: "Dashboard", href: "/" },
        { label: "Envelopes", href: "/envelopes" },
        { label: data?.description ?? id },
      ]}
      actions={
        data ? (
          <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
            <Pencil className="mr-1.5 h-4 w-4" />
            Edit
          </Button>
        ) : undefined
      }
    >
      <div className="space-y-6">
        {/* Loading state */}
        {loading && (
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-48 rounded-lg" />
            ))}
          </div>
        )}

        {/* Error state */}
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Envelope details */}
        {data && (
          <>
            {/* Envelope metadata */}
            <div className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="flex flex-wrap gap-6 text-sm">
                <div>
                  <span className="text-gray-500">Envelope ID</span>
                  <p className="font-medium text-gray-900">
                    {data.envelope_id}
                  </p>
                </div>
                <div>
                  <span className="text-gray-500">Description</span>
                  <p className="font-medium text-gray-900">
                    {data.description}
                  </p>
                </div>
              </div>
            </div>

            {/* Five dimension gauges */}
            <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
              {/* 1. Financial */}
              <DimensionGauge
                dimension="Financial"
                current={data.financial.api_cost_budget_usd ?? 0}
                maximum={data.financial.max_spend_usd}
                unit="USD"
                iconPath={DIMENSION_ICONS.financial}
                details={[
                  {
                    label: "Max Spend",
                    value: `$${data.financial.max_spend_usd.toLocaleString()}`,
                  },
                  {
                    label: "Approval Threshold",
                    value: data.financial.requires_approval_above_usd
                      ? `$${data.financial.requires_approval_above_usd.toLocaleString()}`
                      : "None",
                  },
                ]}
              />

              {/* 2. Operational */}
              <DimensionGauge
                dimension="Operational"
                current={data.operational.allowed_actions.length}
                maximum={
                  data.operational.max_actions_per_day ??
                  data.operational.allowed_actions.length +
                    data.operational.blocked_actions.length
                }
                unit="actions"
                iconPath={DIMENSION_ICONS.operational}
                details={[
                  {
                    label: "Allowed Actions",
                    value: String(data.operational.allowed_actions.length),
                  },
                  {
                    label: "Blocked Actions",
                    value: String(data.operational.blocked_actions.length),
                  },
                  {
                    label: "Max per Day",
                    value: data.operational.max_actions_per_day
                      ? String(data.operational.max_actions_per_day)
                      : "Unlimited",
                  },
                ]}
              />

              {/* 3. Temporal */}
              <DimensionGauge
                dimension="Temporal"
                current={0}
                maximum={1}
                utilization={
                  data.temporal.active_hours_start &&
                  data.temporal.active_hours_end
                    ? 0.5
                    : 0
                }
                iconPath={DIMENSION_ICONS.temporal}
                details={[
                  {
                    label: "Active Hours",
                    value:
                      data.temporal.active_hours_start &&
                      data.temporal.active_hours_end
                        ? `${data.temporal.active_hours_start} - ${data.temporal.active_hours_end}`
                        : "24/7",
                  },
                  {
                    label: "Timezone",
                    value: data.temporal.timezone,
                  },
                  {
                    label: "Blackout Periods",
                    value: String(data.temporal.blackout_periods.length),
                  },
                ]}
              />

              {/* 4. Data Access */}
              <DimensionGauge
                dimension="Data Access"
                current={data.data_access.read_paths.length}
                maximum={
                  data.data_access.read_paths.length +
                  data.data_access.write_paths.length +
                  data.data_access.blocked_data_types.length
                }
                unit="paths"
                iconPath={DIMENSION_ICONS.dataAccess}
                details={[
                  {
                    label: "Read Paths",
                    value: String(data.data_access.read_paths.length),
                  },
                  {
                    label: "Write Paths",
                    value: String(data.data_access.write_paths.length),
                  },
                  {
                    label: "Blocked Types",
                    value: String(data.data_access.blocked_data_types.length),
                  },
                ]}
              />

              {/* 5. Communication */}
              <DimensionGauge
                dimension="Communication"
                current={data.communication.allowed_channels.length}
                maximum={data.communication.allowed_channels.length + 2}
                unit="channels"
                iconPath={DIMENSION_ICONS.communication}
                details={[
                  {
                    label: "Internal Only",
                    value: data.communication.internal_only ? "Yes" : "No",
                  },
                  {
                    label: "Channels",
                    value:
                      data.communication.allowed_channels.join(", ") ||
                      "None configured",
                  },
                  {
                    label: "External Approval",
                    value: data.communication.external_requires_approval
                      ? "Required"
                      : "Not required",
                  },
                ]}
              />
            </div>
          </>
        )}
      </div>

      {/* Edit side panel */}
      {data && (
        <EnvelopeEditSheet
          open={editOpen}
          onOpenChange={setEditOpen}
          envelope={data}
        />
      )}
    </DashboardShell>
  );
}
