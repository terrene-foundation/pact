// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Agents page -- overview cards showing all agents from all teams.
 *
 * Uses React Query (useAllAgents) for data fetching and Shadcn UI components
 * for layout, badges, and loading states.
 */

"use client";

import DashboardShell from "../../components/layout/DashboardShell";
import PostureBadge from "../../components/agents/PostureBadge";
import { useAllAgents } from "@/hooks";
import {
  Card,
  CardContent,
  Badge,
  Skeleton,
  Alert,
  AlertTitle,
  AlertDescription,
  Button,
} from "@/components/ui/shadcn";

/** Map agent status to Shadcn Badge variant and semantic color. */
function statusVariant(
  status: string,
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "active":
      return "default";
    case "suspended":
      return "secondary";
    case "revoked":
      return "destructive";
    default:
      return "outline";
  }
}

/** Loading skeleton for the agents grid. */
function AgentsGridSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-5 space-y-3">
            <div className="flex items-start justify-between">
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-24 rounded-full" />
              <Skeleton className="h-3 w-20" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function AgentsPage() {
  const { data: agents, isLoading, error, refetch } = useAllAgents();

  /** Count agents by status for the summary. */
  const statusCounts = (agents ?? []).reduce<Record<string, number>>(
    (acc, a) => {
      acc[a.status] = (acc[a.status] ?? 0) + 1;
      return acc;
    },
    {},
  );

  return (
    <DashboardShell
      activePath="/agents"
      title="Agents"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Agents" }]}
    >
      <div className="space-y-6">
        <p className="text-sm text-muted-foreground">
          All AI agents operating under EATP trust governance. Each agent
          operates within a constraint envelope and at a defined trust posture
          level.
        </p>

        {/* Summary stats */}
        {!isLoading && agents && agents.length > 0 && (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Card>
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-foreground">
                  {agents.length}
                </p>
                <p className="text-xs text-muted-foreground">Total Agents</p>
              </CardContent>
            </Card>
            <Card className="border-green-200 dark:border-green-800">
              <CardContent className="p-4 text-center bg-green-50 dark:bg-green-950 rounded-lg">
                <p className="text-2xl font-bold text-green-700 dark:text-green-400">
                  {statusCounts["active"] ?? 0}
                </p>
                <p className="text-xs text-green-600 dark:text-green-500">
                  Active
                </p>
              </CardContent>
            </Card>
            <Card className="border-yellow-200 dark:border-yellow-800">
              <CardContent className="p-4 text-center bg-yellow-50 dark:bg-yellow-950 rounded-lg">
                <p className="text-2xl font-bold text-yellow-700 dark:text-yellow-400">
                  {statusCounts["suspended"] ?? 0}
                </p>
                <p className="text-xs text-yellow-600 dark:text-yellow-500">
                  Suspended
                </p>
              </CardContent>
            </Card>
            <Card className="border-red-200 dark:border-red-800">
              <CardContent className="p-4 text-center bg-red-50 dark:bg-red-950 rounded-lg">
                <p className="text-2xl font-bold text-red-700 dark:text-red-400">
                  {statusCounts["revoked"] ?? 0}
                </p>
                <p className="text-xs text-red-600 dark:text-red-500">
                  Revoked
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Loading state */}
        {isLoading && <AgentsGridSkeleton />}

        {/* Error state */}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Failed to load agents</AlertTitle>
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

        {/* Agent cards */}
        {!isLoading && !error && agents && agents.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {agents.map((agent) => (
              <a
                key={agent.agent_id}
                href={`/agents/${agent.agent_id}`}
                className="group"
              >
                <Card className="transition-shadow hover:shadow-md">
                  <CardContent className="p-5">
                    <div className="mb-3 flex items-start justify-between">
                      <div className="min-w-0 flex-1">
                        <h3 className="text-sm font-semibold text-foreground group-hover:text-primary truncate">
                          {agent.name}
                        </h3>
                        <p className="text-xs text-muted-foreground">
                          {agent.role}
                        </p>
                      </div>
                      <Badge variant={statusVariant(agent.status)}>
                        {agent.status}
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between">
                      <PostureBadge posture={agent.posture} size="sm" />
                      <span className="text-xs text-muted-foreground">
                        Team: {agent.team_id}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </a>
            ))}
          </div>
        )}

        {!isLoading && !error && agents && agents.length === 0 && (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              No agents found. Teams may not have been provisioned yet.
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardShell>
  );
}
