// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Pool Management page -- displays agent pools with member counts,
 * capacity utilization, and routing strategy. Supports pool creation
 * and member management via drill-down detail view.
 *
 * Uses React Query hooks for data fetching. React Hook Form + Zod for
 * the create form. Shadcn components for UI primitives.
 */

"use client";

import { useState, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import DashboardShell from "../../components/layout/DashboardShell";
import {
  usePools,
  usePoolDetail,
  useCreatePool,
  useAddPoolMember,
  useRemovePoolMember,
} from "@/hooks";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  Button,
  Input,
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
  Badge,
  Progress,
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

interface Pool {
  id: string;
  name: string;
  org_id: string;
  type: string;
  routing_strategy: string;
  member_count: number;
  capacity: number;
  active_requests: number;
  created_at: string;
}

interface PoolMember {
  agent_id: string;
  name: string;
  role: string;
  status: string;
  current_load: number;
  joined_at: string;
}

interface PoolDetail extends Pool {
  members: PoolMember[];
  description: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const POOL_TYPES = [
  { value: "general", label: "General" },
  { value: "specialized", label: "Specialized" },
  { value: "overflow", label: "Overflow" },
] as const;

const ROUTING_STRATEGIES = [
  { value: "round_robin", label: "Round Robin" },
  { value: "least_loaded", label: "Least Loaded" },
  { value: "priority_based", label: "Priority Based" },
  { value: "skill_match", label: "Skill Match" },
] as const;

const MEMBER_STATUS_COLORS: Record<string, string> = {
  active: "bg-green-100 text-green-800 border-green-300",
  idle: "bg-blue-100 text-blue-800 border-blue-300",
  busy: "bg-orange-100 text-orange-800 border-orange-300",
  offline: "bg-muted text-muted-foreground border-border",
  suspended: "bg-red-100 text-red-800 border-red-300",
};

// ---------------------------------------------------------------------------
// Zod schema for create form
// ---------------------------------------------------------------------------

const poolSchema = z.object({
  name: z.string().min(1, "Pool name is required").max(200),
  org_id: z.string().min(1, "Org ID is required"),
  type: z.enum(["general", "specialized", "overflow"]),
  routing_strategy: z.enum([
    "round_robin",
    "least_loaded",
    "priority_based",
    "skill_match",
  ]),
});

type PoolFormValues = z.infer<typeof poolSchema>;

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function CapacityBar({ used, capacity }: { used: number; capacity: number }) {
  const pct = capacity > 0 ? Math.min((used / capacity) * 100, 100) : 0;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>
          {used} / {capacity} members
        </span>
        <span>{Math.round(pct)}%</span>
      </div>
      <Progress
        value={pct}
        className={cn(
          "h-2",
          pct >= 90
            ? "[&>[data-state]]:bg-destructive"
            : pct >= 70
              ? "[&>[data-state]]:bg-orange-500"
              : pct >= 40
                ? "[&>[data-state]]:bg-primary"
                : "[&>[data-state]]:bg-green-500",
        )}
      />
    </div>
  );
}

function RoutingBadge({ strategy }: { strategy: string }) {
  const label = strategy
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <Badge variant="outline" className="text-xs">
      {label}
    </Badge>
  );
}

function TypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    general: "bg-blue-50 text-blue-700 border-blue-200",
    specialized: "bg-purple-50 text-purple-700 border-purple-200",
    overflow: "bg-amber-50 text-amber-700 border-amber-200",
  };
  const colorClass =
    colors[type] ?? "bg-muted text-muted-foreground border-border";
  const label = type.charAt(0).toUpperCase() + type.slice(1);
  return (
    <Badge variant="outline" className={cn("text-xs", colorClass)}>
      {label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Pool card
// ---------------------------------------------------------------------------

function PoolCard({ pool, onClick }: { pool: Pool; onClick: () => void }) {
  return (
    <Card
      onClick={onClick}
      className="cursor-pointer hover:border-primary/50 hover:shadow-sm transition-all"
    >
      <CardContent className="p-5">
        <div className="flex items-start justify-between mb-3">
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              {pool.name}
            </h3>
            <p className="text-xs text-muted-foreground font-mono">
              {pool.org_id}
            </p>
          </div>
          <TypeBadge type={pool.type} />
        </div>

        <CapacityBar used={pool.member_count} capacity={pool.capacity} />

        <div className="mt-3 flex items-center justify-between">
          <RoutingBadge strategy={pool.routing_strategy} />
          <span className="text-xs text-muted-foreground">
            {pool.active_requests} active request
            {pool.active_requests !== 1 ? "s" : ""}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Detail panel
// ---------------------------------------------------------------------------

function PoolDetailPanel({
  poolId,
  onClose,
}: {
  poolId: string;
  onClose: () => void;
}) {
  const { data: poolData, isLoading, error } = usePoolDetail(poolId);
  const addMember = useAddPoolMember();
  const removeMember = useRemovePoolMember();
  const [addAgentId, setAddAgentId] = useState("");

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

  if (error || !poolData) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Failed to load pool</AlertTitle>
        <AlertDescription>
          {error instanceof Error ? error.message : "Unknown error"}
        </AlertDescription>
      </Alert>
    );
  }

  const pool = poolData as unknown as PoolDetail;

  const handleAddMember = (e: React.FormEvent) => {
    e.preventDefault();
    if (!addAgentId.trim()) return;
    addMember.mutate(
      { poolId: pool.id, agent_id: addAgentId.trim() },
      {
        onSuccess: () => setAddAgentId(""),
      },
    );
  };

  const handleRemoveMember = (agentId: string) => {
    removeMember.mutate({ poolId: pool.id, agentId });
  };

  return (
    <Card>
      <CardContent className="p-6 space-y-5">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-foreground">
              {pool.name}
            </h3>
            <div className="mt-1 flex items-center gap-2">
              <TypeBadge type={pool.type} />
              <RoutingBadge strategy={pool.routing_strategy} />
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>

        {pool.description && (
          <p className="text-sm text-muted-foreground">{pool.description}</p>
        )}

        <CapacityBar used={pool.member_count} capacity={pool.capacity} />

        {(addMember.error || removeMember.error) && (
          <Alert variant="destructive">
            <AlertTitle>Action failed</AlertTitle>
            <AlertDescription>
              {addMember.error instanceof Error
                ? addMember.error.message
                : removeMember.error instanceof Error
                  ? removeMember.error.message
                  : "Operation failed"}
            </AlertDescription>
          </Alert>
        )}

        {/* Add member form */}
        <form onSubmit={handleAddMember} className="flex items-end gap-3">
          <div className="flex-1">
            <label
              htmlFor="add-agent"
              className="block text-sm font-medium text-foreground mb-1"
            >
              Add Member
            </label>
            <Input
              id="add-agent"
              type="text"
              value={addAgentId}
              onChange={(e) => setAddAgentId(e.target.value)}
              placeholder="Agent ID"
            />
          </div>
          <Button
            type="submit"
            disabled={addMember.isPending || !addAgentId.trim()}
          >
            {addMember.isPending ? "Adding..." : "Add"}
          </Button>
        </form>

        {/* Members table */}
        <div>
          <h4 className="mb-2 text-sm font-semibold text-foreground">
            Members ({pool.members?.length ?? 0})
          </h4>
          {!pool.members || pool.members.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No members in this pool yet. Add agents to start routing work.
            </p>
          ) : (
            <div className="rounded-lg border border-border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Agent</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Load</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pool.members.map((member) => (
                    <TableRow key={member.agent_id}>
                      <TableCell>
                        <div className="text-sm font-medium text-foreground">
                          {member.name}
                        </div>
                        <div className="text-xs font-mono text-muted-foreground">
                          {member.agent_id}
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {member.role}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-xs rounded-full",
                            MEMBER_STATUS_COLORS[member.status] ??
                              "bg-muted text-muted-foreground border-border",
                          )}
                        >
                          {member.status.charAt(0).toUpperCase() +
                            member.status.slice(1)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Progress
                            value={Math.min(member.current_load, 100)}
                            className={cn(
                              "h-1.5 w-16",
                              member.current_load > 80
                                ? "[&>[data-state]]:bg-destructive"
                                : member.current_load > 50
                                  ? "[&>[data-state]]:bg-orange-500"
                                  : "[&>[data-state]]:bg-green-500",
                            )}
                          />
                          <span className="text-xs text-muted-foreground">
                            {member.current_load}%
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRemoveMember(member.agent_id)}
                          disabled={
                            removeMember.isPending &&
                            removeMember.variables?.agentId === member.agent_id
                          }
                          className="border-red-200 bg-red-50 text-red-700 hover:bg-red-100 text-xs"
                        >
                          {removeMember.isPending &&
                          removeMember.variables?.agentId === member.agent_id
                            ? "Removing..."
                            : "Remove"}
                        </Button>
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

function CreatePoolSheet({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const createMutation = useCreatePool();

  const form = useForm<PoolFormValues>({
    resolver: zodResolver(poolSchema),
    defaultValues: {
      name: "",
      org_id: "",
      type: "general",
      routing_strategy: "round_robin",
    },
  });

  const onSubmit = (values: PoolFormValues) => {
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
          <SheetTitle>Create Pool</SheetTitle>
          <SheetDescription>
            Configure a new agent pool with routing strategy.
          </SheetDescription>
        </SheetHeader>

        {createMutation.error && (
          <Alert variant="destructive" className="mt-4">
            <AlertTitle>Creation failed</AlertTitle>
            <AlertDescription>
              {createMutation.error instanceof Error
                ? createMutation.error.message
                : "Failed to create pool"}
            </AlertDescription>
          </Alert>
        )}

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="mt-6 space-y-4"
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Pool Name</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. Engineering Pool" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="org_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Org ID</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. org-001" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField
                control={form.control}
                name="type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Type</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select type" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {POOL_TYPES.map((pt) => (
                          <SelectItem key={pt.value} value={pt.value}>
                            {pt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="routing_strategy"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Routing Strategy</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select strategy" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {ROUTING_STRATEGIES.map((rs) => (
                          <SelectItem key={rs.value} value={rs.value}>
                            {rs.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="flex justify-end gap-3 pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating..." : "Create Pool"}
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

export default function PoolsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Fetch pools via React Query
  const { data: poolsData, isLoading, error, refetch } = usePools();

  const pools: Pool[] =
    (poolsData as unknown as { pools: Pool[] })?.pools ?? [];

  // Summary stats
  const totalMembers = useMemo(
    () => pools.reduce((sum, p) => sum + p.member_count, 0),
    [pools],
  );
  const totalCapacity = useMemo(
    () => pools.reduce((sum, p) => sum + p.capacity, 0),
    [pools],
  );
  const totalActive = useMemo(
    () => pools.reduce((sum, p) => sum + p.active_requests, 0),
    [pools],
  );

  return (
    <DashboardShell
      activePath="/pools"
      title="Pool Management"
      breadcrumbs={[{ label: "Dashboard", href: "/" }, { label: "Pools" }]}
      actions={
        <div className="flex gap-2">
          <Button size="sm" onClick={() => setShowCreate(true)}>
            New Pool
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
          Agent pools group workers by capability and route requests using
          configurable strategies. Each pool has a capacity limit and tracks
          active request load across its members.
        </p>

        {/* Summary bar */}
        {!isLoading && pools.length > 0 && (
          <Card>
            <CardContent className="flex flex-wrap items-center gap-6 px-4 py-3">
              <div>
                <span className="text-2xl font-bold text-foreground">
                  {pools.length}
                </span>
                <span className="ml-1 text-sm text-muted-foreground">
                  pool{pools.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="h-8 w-px bg-border" />
              <div>
                <span className="text-2xl font-bold text-foreground">
                  {totalMembers}
                </span>
                <span className="ml-1 text-sm text-muted-foreground">
                  / {totalCapacity} members
                </span>
              </div>
              <div className="h-8 w-px bg-border" />
              <div>
                <span className="text-2xl font-bold text-foreground">
                  {totalActive}
                </span>
                <span className="ml-1 text-sm text-muted-foreground">
                  active request{totalActive !== 1 ? "s" : ""}
                </span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Create sheet */}
        <CreatePoolSheet open={showCreate} onOpenChange={setShowCreate} />

        {/* Loading */}
        {isLoading && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-lg" />
            ))}
          </div>
        )}

        {/* Error */}
        {error && (
          <Alert variant="destructive">
            <AlertTitle>Something went wrong</AlertTitle>
            <AlertDescription>
              {error instanceof Error ? error.message : "Failed to load pools"}
            </AlertDescription>
          </Alert>
        )}

        {/* Detail panel */}
        {selectedId && (
          <PoolDetailPanel
            poolId={selectedId}
            onClose={() => setSelectedId(null)}
          />
        )}

        {/* Pool cards */}
        {!isLoading && !error && (
          <>
            {pools.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {pools.map((pool) => (
                  <PoolCard
                    key={pool.id}
                    pool={pool}
                    onClick={() => setSelectedId(pool.id)}
                  />
                ))}
              </div>
            ) : (
              <Card>
                <CardContent className="p-8 text-center">
                  <p className="text-sm text-muted-foreground">
                    No pools configured yet. Create one to start routing work to
                    agents.
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
