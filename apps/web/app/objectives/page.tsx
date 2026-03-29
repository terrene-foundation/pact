// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Objectives page -- manage work objectives with status tracking,
 * budget monitoring, and decomposed request summaries.
 *
 * Uses React Query hooks for data fetching and React Hook Form + Zod
 * for the create form. Shared Shadcn components for UI primitives.
 */

"use client";

import { useState, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import DashboardShell from "../../components/layout/DashboardShell";
import StatusBadge from "../../components/ui/StatusBadge";

import { useObjectives, useObjectiveDetail, useCreateObjective } from "@/hooks";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Input,
  Textarea,
  Progress,
  Skeleton,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  Alert,
  AlertTitle,
  AlertDescription,
  Form,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormMessage,
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/shadcn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Objective {
  id: string;
  title: string;
  description: string;
  org_address: string;
  status: "draft" | "active" | "completed" | "cancelled";
  priority: "low" | "medium" | "high" | "critical";
  budget: number;
  spent: number;
  request_count: number;
  created_at: string;
  updated_at: string;
}

interface ObjectiveDetail extends Objective {
  requests: Array<{
    id: string;
    title: string;
    status: string;
    assigned_to: string | null;
    cost: number;
  }>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_OPTIONS = [
  { value: "all", label: "All Statuses" },
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "cancelled", label: "Cancelled" },
] as const;

const PRIORITY_COLORS: Record<string, string> = {
  low: "text-muted-foreground",
  medium: "text-blue-600",
  high: "text-orange-600",
  critical: "text-red-600",
};

// ---------------------------------------------------------------------------
// Zod schema for create form
// ---------------------------------------------------------------------------

const objectiveSchema = z.object({
  title: z.string().min(1, "Title is required").max(200),
  org_address: z.string().min(1, "Organization address is required"),
  budget: z.number().min(0, "Budget must be non-negative"),
  priority: z.enum(["low", "medium", "high", "critical"]),
  description: z.string().optional(),
});

type ObjectiveFormValues = z.infer<typeof objectiveSchema>;

// ---------------------------------------------------------------------------
// Budget bar (using Shadcn Progress)
// ---------------------------------------------------------------------------

function BudgetBar({ spent, budget }: { spent: number; budget: number }) {
  const pct = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
  const overBudget = spent > budget;

  return (
    <div className="flex items-center gap-2">
      <Progress
        value={pct}
        className={cn(
          "h-2 w-24",
          overBudget
            ? "[&>[data-state]]:bg-destructive"
            : pct > 80
              ? "[&>[data-state]]:bg-orange-500"
              : "[&>[data-state]]:bg-primary",
        )}
      />
      <span className="text-xs text-muted-foreground">
        ${spent.toLocaleString()} / ${budget.toLocaleString()}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail panel
// ---------------------------------------------------------------------------

function ObjectiveDetailPanel({
  objectiveId,
  onClose,
}: {
  objectiveId: string;
  onClose: () => void;
}) {
  const { data: objective, isLoading, error } = useObjectiveDetail(objectiveId);

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6 space-y-3">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </CardContent>
      </Card>
    );
  }

  if (error || !objective) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Failed to load objective</AlertTitle>
        <AlertDescription>
          {error instanceof Error ? error.message : "Unknown error"}
        </AlertDescription>
      </Alert>
    );
  }

  const detail = objective as unknown as ObjectiveDetail;
  const totalRequestCost =
    detail.requests?.reduce((sum, r) => sum + r.cost, 0) ?? 0;

  return (
    <Card>
      <CardContent className="p-6 space-y-5">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              {detail.title}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {detail.org_address}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>

        {detail.description && (
          <p className="text-sm text-muted-foreground">{detail.description}</p>
        )}

        {/* Cost summary */}
        <div className="grid grid-cols-3 gap-4">
          <Card className="bg-muted/50">
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground">Budget</p>
              <p className="text-lg font-semibold text-foreground">
                ${detail.budget.toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card className="bg-muted/50">
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground">Spent</p>
              <p className="text-lg font-semibold text-foreground">
                ${detail.spent.toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card className="bg-muted/50">
            <CardContent className="p-3">
              <p className="text-xs text-muted-foreground">
                Request Cost Total
              </p>
              <p className="text-lg font-semibold text-foreground">
                ${totalRequestCost.toLocaleString()}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Decomposed requests */}
        <div>
          <h4 className="mb-2 text-sm font-semibold text-foreground">
            Decomposed Requests ({detail.requests?.length ?? 0})
          </h4>
          {!detail.requests || detail.requests.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No requests have been created for this objective yet.
            </p>
          ) : (
            <div className="rounded-lg border border-border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Title</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Assigned</TableHead>
                    <TableHead className="text-right">Cost</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detail.requests.map((req) => (
                    <TableRow key={req.id}>
                      <TableCell className="text-sm text-foreground">
                        {req.title}
                      </TableCell>
                      <TableCell>
                        <StatusBadge value={req.status} size="xs" />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {req.assigned_to ?? "--"}
                      </TableCell>
                      <TableCell className="text-right text-sm text-foreground">
                        ${req.cost.toLocaleString()}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Create form (Sheet panel with React Hook Form + Zod)
// ---------------------------------------------------------------------------

function CreateObjectiveSheet({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createMutation = useCreateObjective();

  const form = useForm<ObjectiveFormValues>({
    resolver: zodResolver(objectiveSchema),
    defaultValues: {
      title: "",
      org_address: "",
      budget: 0,
      priority: "medium",
      description: "",
    },
  });

  const onSubmit = (values: ObjectiveFormValues) => {
    createMutation.mutate(values, {
      onSuccess: () => {
        form.reset();
        onOpenChange(false);
      },
    });
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle>Create Objective</SheetTitle>
          <SheetDescription>
            Define a new work objective with scope, budget, and priority.
          </SheetDescription>
        </SheetHeader>

        {createMutation.error && (
          <Alert variant="destructive" className="mt-4">
            <AlertTitle>Creation failed</AlertTitle>
            <AlertDescription>
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : "Failed to create objective"}
            </AlertDescription>
          </Alert>
        )}

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="mt-6 space-y-4"
          >
            <FormField
              control={form.control}
              name="title"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Title</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="e.g. Q2 Platform Migration"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="org_address"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Org Address (D/T/R)</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. D1-R1-T1-R1" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="budget"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Budget ($)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min="0"
                        step="0.01"
                        placeholder="10000"
                        {...field}
                        onChange={(e) =>
                          field.onChange(
                            e.target.value === ""
                              ? 0
                              : parseFloat(e.target.value),
                          )
                        }
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="priority"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Priority</FormLabel>
                  <Select
                    onValueChange={field.onChange}
                    defaultValue={field.value}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Select priority" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="low">Low</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="critical">Critical</SelectItem>
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      rows={3}
                      placeholder="Describe the objective and expected outcomes..."
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="flex justify-end gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating..." : "Create Objective"}
              </Button>
            </div>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ObjectivesPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [showCreate, setShowCreate] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Fetch objectives via React Query
  const {
    data: objectivesData,
    isLoading,
    error,
    refetch,
  } = useObjectives(
    statusFilter !== "all" ? { status: statusFilter } : undefined,
  );

  const objectives: Objective[] =
    (objectivesData as unknown as { objectives: Objective[] })?.objectives ??
    [];

  // Filtered list (client-side for the "all" case since the API returns all)
  const filtered = useMemo(() => {
    if (statusFilter === "all") return objectives;
    return objectives.filter((o) => o.status === statusFilter);
  }, [objectives, statusFilter]);

  // Status summary counts
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const obj of objectives) {
      counts[obj.status] = (counts[obj.status] ?? 0) + 1;
    }
    return counts;
  }, [objectives]);

  return (
    <DashboardShell
      activePath="/objectives"
      title="Objectives"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Objectives" }]}
      actions={
        <div className="flex gap-2">
          <Button size="sm" onClick={() => setShowCreate(true)}>
            New Objective
          </Button>
          <Button
            variant="outline"
            size="sm"
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
          Work objectives define the scope, budget, and priority of governed
          work items. Each objective decomposes into requests assigned to pools
          and agents.
        </p>

        {/* Summary bar */}
        {!isLoading && objectives.length > 0 && (
          <Card>
            <CardContent className="flex flex-wrap items-center gap-4 px-4 py-3">
              <span className="text-sm font-medium text-foreground">
                {objectives.length} objective
                {objectives.length !== 1 ? "s" : ""}
              </span>
              {statusCounts.active !== undefined && statusCounts.active > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-primary" />
                  <span className="text-sm text-muted-foreground">
                    {statusCounts.active} active
                  </span>
                </div>
              )}
              {statusCounts.draft !== undefined && statusCounts.draft > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    {statusCounts.draft} draft
                  </span>
                </div>
              )}
              {statusCounts.completed !== undefined &&
                statusCounts.completed > 0 && (
                  <div className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-green-500" />
                    <span className="text-sm text-muted-foreground">
                      {statusCounts.completed} completed
                    </span>
                  </div>
                )}
            </CardContent>
          </Card>
        )}

        {/* Filter */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">Filter:</span>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
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

        {/* Create sheet */}
        <CreateObjectiveSheet open={showCreate} onOpenChange={setShowCreate} />

        {/* Loading */}
        {isLoading && <div className="space-y-2">{Array.from({length:5}).map((_,i)=><Skeleton key={i} className="h-12 rounded" />)}</div>}

        {/* Error */}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Something went wrong</AlertTitle>
            <AlertDescription>
              {error instanceof Error
                ? error.message
                : "Failed to load objectives"}
            </AlertDescription>
          </Alert>
        )}

        {/* Detail panel */}
        {selectedId && (
          <ObjectiveDetailPanel
            objectiveId={selectedId}
            onClose={() => setSelectedId(null)}
          />
        )}

        {/* Table */}
        {!isLoading && !error && (
          <>
            {filtered.length > 0 ? (
              <div className="rounded-lg border border-border overflow-hidden bg-card">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Title</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Priority</TableHead>
                      <TableHead>Budget</TableHead>
                      <TableHead>Requests</TableHead>
                      <TableHead>Address</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((obj) => (
                      <TableRow
                        key={obj.id}
                        onClick={() => setSelectedId(obj.id)}
                        className="cursor-pointer"
                      >
                        <TableCell className="font-medium text-foreground">
                          {obj.title}
                        </TableCell>
                        <TableCell>
                          <StatusBadge value={obj.status} size="xs" />
                        </TableCell>
                        <TableCell>
                          <span
                            className={cn(
                              "font-medium",
                              PRIORITY_COLORS[obj.priority] ??
                                "text-muted-foreground",
                            )}
                          >
                            {obj.priority.charAt(0).toUpperCase() +
                              obj.priority.slice(1)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <BudgetBar spent={obj.spent} budget={obj.budget} />
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {obj.request_count}
                        </TableCell>
                        <TableCell className="font-mono text-muted-foreground">
                          {obj.org_address}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <Card>
                <CardContent className="p-8 text-center">
                  <p className="text-sm text-muted-foreground">
                    {objectives.length === 0
                      ? "No objectives yet. Create one to get started."
                      : "No objectives match the selected filter."}
                  </p>
                </CardContent>
              </Card>
            )}
          </>
        )}
      </div>
    </DashboardShell>
  );
}
