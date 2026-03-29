// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Envelopes list page -- displays all constraint envelopes from the API.
 *
 * Each row links to the envelope detail view showing five dimension gauges.
 * Uses React Query (useEnvelopes) for data fetching and Shadcn UI components.
 */

"use client";

import { RefreshCw, Search } from "lucide-react";
import { useState, useMemo } from "react";
import DashboardShell from "../../components/layout/DashboardShell";
import { useEnvelopes } from "@/hooks";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
  Alert,
  AlertTitle,
  AlertDescription,
  Badge,
  Button,
  Input,
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/shadcn";

/** Loading skeleton for the envelopes table. */
function EnvelopesTableSkeleton() {
  return (
    <Card>
      <CardContent className="p-0">
        <div className="p-4">
          <Skeleton className="h-9 w-64" />
        </div>
        <div className="border-t border-border">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="flex items-center gap-4 border-b border-border px-6 py-4 last:border-0"
            >
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-48 flex-1" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-20" />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

export default function EnvelopesPage() {
  const { data, isLoading, error, refetch } = useEnvelopes();
  const [filter, setFilter] = useState("");

  const filteredEnvelopes = useMemo(() => {
    if (!data?.envelopes) return [];
    if (!filter.trim()) return data.envelopes;
    const lower = filter.toLowerCase();
    return data.envelopes.filter(
      (e) =>
        e.envelope_id.toLowerCase().includes(lower) ||
        (e.description?.toLowerCase().includes(lower) ?? false) ||
        (e.agent_id?.toLowerCase().includes(lower) ?? false) ||
        (e.team_id?.toLowerCase().includes(lower) ?? false),
    );
  }, [data, filter]);

  return (
    <DashboardShell
      activePath="/envelopes"
      title="Constraint Envelopes"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Envelopes" }]}
      actions={
        <Button
          variant="outline"
          size="sm"
          onClick={() => void refetch()}
          disabled={isLoading}
        >
          <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      }
    >
      <div className="space-y-6">
        <p className="text-sm text-muted-foreground">
          Constraint envelopes define the five-dimensional boundaries for agent
          actions: Financial, Operational, Temporal, Data Access, and
          Communication. Select an envelope to see utilization details.
        </p>

        {isLoading && <EnvelopesTableSkeleton />}

        {error && (
          <Alert variant="destructive">
            <AlertTitle>Failed to load envelopes</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>
                {error instanceof Error ? error.message : "Unknown error"}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void refetch()}
              >
                Retry
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {data && (
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold">
                  Envelopes ({filteredEnvelopes.length})
                </CardTitle>
                <div className="relative w-64">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search envelopes..."
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    className="pl-9"
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {filteredEnvelopes.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Envelope ID</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Agent</TableHead>
                      <TableHead>Team</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredEnvelopes.map((env) => (
                      <TableRow key={env.envelope_id}>
                        <TableCell>
                          <a
                            href={`/envelopes/${env.envelope_id}`}
                            className="font-medium text-primary hover:underline"
                          >
                            {env.envelope_id}
                          </a>
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {env.description}
                        </TableCell>
                        <TableCell>
                          {env.agent_id && (
                            <Badge variant="outline">{env.agent_id}</Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          {env.team_id && (
                            <Badge variant="secondary">{env.team_id}</Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="p-8 text-center text-muted-foreground">
                  {filter
                    ? "No envelopes match the current filter."
                    : "No constraint envelopes found."}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardShell>
  );
}
