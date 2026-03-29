// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Bridge list page -- shows all Cross-Functional Bridges with lifecycle
 * status badges, type indicators, and team connections.
 *
 * Uses React Query (useBridges) for data fetching and Shadcn UI components
 * for layout, filtering, and status display.
 */

"use client";

import { useState } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import { useBridges } from "@/hooks";
import type { BridgeStatus } from "../../types/pact";
import {
  Card,
  CardContent,
  Badge,
  Button,
  Skeleton,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
  Alert,
  AlertTitle,
  AlertDescription,
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/shadcn";

/** Human-readable labels for bridge types. */
const BRIDGE_TYPE_LABELS: Record<string, string> = {
  standing: "Standing",
  scoped: "Scoped",
  ad_hoc: "Ad-Hoc",
};

/** All possible bridge statuses for the filter. */
const STATUS_OPTIONS: Array<{ value: BridgeStatus | "all"; label: string }> = [
  { value: "all", label: "All Statuses" },
  { value: "active", label: "Active" },
  { value: "pending", label: "Pending" },
  { value: "negotiating", label: "Negotiating" },
  { value: "suspended", label: "Suspended" },
  { value: "expired", label: "Expired" },
  { value: "closed", label: "Closed" },
  { value: "revoked", label: "Revoked" },
];

/** Map status to badge variant. */
function statusVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "active":
      return "default";
    case "pending":
    case "negotiating":
      return "secondary";
    case "suspended":
    case "revoked":
      return "destructive";
    default:
      return "outline";
  }
}

/** Loading skeleton for bridges. */
function BridgesListSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-5 space-y-3">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
            <div className="flex justify-between">
              <Skeleton className="h-5 w-16 rounded-full" />
              <Skeleton className="h-3 w-20" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function BridgesPage() {
  const [statusFilter, setStatusFilter] = useState<BridgeStatus | "all">("all");

  const { data: bridgesData, isLoading, error, refetch } = useBridges();

  const allBridges = bridgesData?.bridges ?? [];
  const bridges =
    statusFilter === "all"
      ? allBridges
      : allBridges.filter((b) => b.status === statusFilter);

  // Group bridges by status for summary counts
  const statusCounts = allBridges.reduce(
    (acc, b) => {
      acc[b.status] = (acc[b.status] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <DashboardShell
      activePath="/bridges"
      title="Cross-Functional Bridges"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Bridges" }]}
      actions={
        <div className="flex gap-2">
          <Button asChild>
            <a href="/bridges/create">Create Bridge</a>
          </Button>
          <Button
            variant="outline"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            Refresh
          </Button>
        </div>
      }
    >
      <div className="space-y-6">
        <p className="text-sm text-muted-foreground">
          Cross-Functional Bridges enable controlled data and communication flow
          between agent teams. Standing bridges are permanent, Scoped bridges
          are time-bounded, and Ad-Hoc bridges serve one-time requests.
        </p>

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Failed to load bridges</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>
                {error instanceof Error ? error.message : "Unknown error"}
              </span>
              <Button variant="outline" size="sm" onClick={() => refetch()}>
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Summary stat cards */}
        {!isLoading && allBridges.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {[
              {
                label: "Total",
                count: allBridges.length,
                variant: "outline" as const,
              },
              {
                label: "Active",
                count: statusCounts["active"] ?? 0,
                variant: "default" as const,
              },
              {
                label: "Pending",
                count: statusCounts["pending"] ?? 0,
                variant: "secondary" as const,
              },
              {
                label: "Suspended",
                count: statusCounts["suspended"] ?? 0,
                variant: "destructive" as const,
              },
              {
                label: "Closed",
                count: statusCounts["closed"] ?? 0,
                variant: "outline" as const,
              },
              {
                label: "Revoked",
                count: statusCounts["revoked"] ?? 0,
                variant: "destructive" as const,
              },
            ].map((stat) => (
              <Card key={stat.label}>
                <CardContent className="p-3 text-center">
                  <p className="text-lg font-bold text-foreground">
                    {stat.count}
                  </p>
                  <Badge variant={stat.variant} className="mt-1">
                    {stat.label}
                  </Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Status filter */}
        {!isLoading && allBridges.length > 0 && (
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">Filter:</span>
            <Select
              value={statusFilter}
              onValueChange={(value) =>
                setStatusFilter(value as BridgeStatus | "all")
              }
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Loading skeleton */}
        {isLoading && <BridgesListSkeleton />}

        {/* Bridge list table */}
        {!isLoading && bridges.length > 0 && (
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Bridge</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Source / Target</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {bridges.map((bridge) => (
                  <TableRow
                    key={bridge.bridge_id}
                    className="cursor-pointer"
                    onClick={() => {
                      window.location.href = `/bridges/${bridge.bridge_id}`;
                    }}
                  >
                    <TableCell>
                      <div>
                        <p className="text-sm font-medium text-foreground truncate max-w-xs">
                          {bridge.purpose}
                        </p>
                        <p className="text-xs text-muted-foreground font-mono">
                          {bridge.bridge_id}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-foreground">
                        {BRIDGE_TYPE_LABELS[bridge.bridge_type] ??
                          bridge.bridge_type}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm text-foreground">
                        <span className="font-medium">
                          {bridge.source_team_id}
                        </span>
                        <span className="mx-1 text-muted-foreground">
                          &rarr;
                        </span>
                        <span className="font-medium">
                          {bridge.target_team_id}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(bridge.status)}>
                        {bridge.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(bridge.created_at).toLocaleDateString()}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}

        {/* Empty state */}
        {!isLoading && bridges.length === 0 && (
          <Card>
            <CardContent className="p-8 text-center">
              <p className="text-muted-foreground">
                No bridges found. Cross-Functional Bridges connect agent teams
                for controlled data sharing.
              </p>
              <Button className="mt-4" asChild>
                <a href="/bridges/create">Create Your First Bridge</a>
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardShell>
  );
}
