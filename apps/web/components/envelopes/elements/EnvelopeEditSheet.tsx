// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * EnvelopeEditSheet -- side panel form for editing constraint envelope values.
 *
 * Uses React Hook Form + Zod for validation across all five CARE dimensions:
 *   1. Financial
 *   2. Operational
 *   3. Temporal
 *   4. Data Access
 *   5. Communication
 */

"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import type { ConstraintEnvelope } from "@/types/pact";
import { useUpdateEnvelope } from "@/hooks";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
  Button,
  Input,
  Label,
  Switch,
  Separator,
} from "@/components/ui/shadcn";

// ---------------------------------------------------------------------------
// Zod schema
// ---------------------------------------------------------------------------

const envelopeFormSchema = z.object({
  // Financial
  max_spend_usd: z
    .number()
    .min(0, "Must be non-negative")
    .finite("Must be a finite number"),
  requires_approval_above_usd: z
    .number()
    .min(0, "Must be non-negative")
    .finite("Must be a finite number")
    .nullable(),

  // Operational
  allowed_actions: z.string(),
  max_actions_per_day: z
    .number()
    .int("Must be a whole number")
    .min(0, "Must be non-negative")
    .nullable(),

  // Temporal
  active_hours_start: z.string().nullable(),
  active_hours_end: z.string().nullable(),
  timezone: z.string().min(1, "Timezone is required"),

  // Data Access
  read_paths: z.string(),
  write_paths: z.string(),

  // Communication
  internal_only: z.boolean(),
  allowed_channels: z.string(),
});

type EnvelopeFormValues = z.infer<typeof envelopeFormSchema>;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface EnvelopeEditSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  envelope: ConstraintEnvelope;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert comma-separated string to array, filtering empty strings. */
function csvToArray(value: string): string[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function EnvelopeEditSheet({
  open,
  onOpenChange,
  envelope,
}: EnvelopeEditSheetProps) {
  const updateEnvelope = useUpdateEnvelope();

  const form = useForm<EnvelopeFormValues>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(envelopeFormSchema) as any,
    defaultValues: {
      max_spend_usd: envelope.financial.max_spend_usd,
      requires_approval_above_usd:
        envelope.financial.requires_approval_above_usd,
      allowed_actions: envelope.operational.allowed_actions.join(", "),
      max_actions_per_day: envelope.operational.max_actions_per_day,
      active_hours_start: envelope.temporal.active_hours_start ?? "",
      active_hours_end: envelope.temporal.active_hours_end ?? "",
      timezone: envelope.temporal.timezone,
      read_paths: envelope.data_access.read_paths.join(", "),
      write_paths: envelope.data_access.write_paths.join(", "),
      internal_only: envelope.communication.internal_only,
      allowed_channels: envelope.communication.allowed_channels.join(", "),
    },
  });

  const onSubmit = (values: EnvelopeFormValues) => {
    updateEnvelope.mutate(
      {
        envelopeId: envelope.envelope_id,
        data: {
          financial: {
            max_spend_usd: values.max_spend_usd,
            requires_approval_above_usd: values.requires_approval_above_usd,
          },
          operational: {
            allowed_actions: csvToArray(values.allowed_actions),
            max_actions_per_day: values.max_actions_per_day,
          },
          temporal: {
            active_hours_start: values.active_hours_start || null,
            active_hours_end: values.active_hours_end || null,
            timezone: values.timezone,
          },
          data_access: {
            read_paths: csvToArray(values.read_paths),
            write_paths: csvToArray(values.write_paths),
          },
          communication: {
            internal_only: values.internal_only,
            allowed_channels: csvToArray(values.allowed_channels),
          },
        },
      },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Edit Envelope</SheetTitle>
          <SheetDescription>
            Update constraint values for{" "}
            {envelope.description || envelope.envelope_id}.
          </SheetDescription>
        </SheetHeader>

        <form onSubmit={form.handleSubmit(onSubmit)} className="mt-6 space-y-6">
          {/* Financial */}
          <section>
            <h4 className="mb-3 text-sm font-semibold text-gray-900">
              Financial
            </h4>
            <div className="space-y-3">
              <div>
                <Label htmlFor="max_spend_usd" className="text-xs">
                  Max Spend (USD)
                </Label>
                <Input
                  id="max_spend_usd"
                  type="number"
                  step="0.01"
                  {...form.register("max_spend_usd", { valueAsNumber: true })}
                />
                {form.formState.errors.max_spend_usd && (
                  <p className="mt-1 text-xs text-red-600">
                    {form.formState.errors.max_spend_usd.message}
                  </p>
                )}
              </div>
              <div>
                <Label
                  htmlFor="requires_approval_above_usd"
                  className="text-xs"
                >
                  Requires Approval Above (USD)
                </Label>
                <Input
                  id="requires_approval_above_usd"
                  type="number"
                  step="0.01"
                  {...form.register("requires_approval_above_usd", {
                    valueAsNumber: true,
                  })}
                />
                {form.formState.errors.requires_approval_above_usd && (
                  <p className="mt-1 text-xs text-red-600">
                    {form.formState.errors.requires_approval_above_usd.message}
                  </p>
                )}
              </div>
            </div>
          </section>

          <Separator />

          {/* Operational */}
          <section>
            <h4 className="mb-3 text-sm font-semibold text-gray-900">
              Operational
            </h4>
            <div className="space-y-3">
              <div>
                <Label htmlFor="allowed_actions" className="text-xs">
                  Allowed Actions (comma-separated)
                </Label>
                <Input
                  id="allowed_actions"
                  {...form.register("allowed_actions")}
                  placeholder="file_read, file_write, api_call"
                />
              </div>
              <div>
                <Label htmlFor="max_actions_per_day" className="text-xs">
                  Max Actions Per Day
                </Label>
                <Input
                  id="max_actions_per_day"
                  type="number"
                  {...form.register("max_actions_per_day", {
                    valueAsNumber: true,
                  })}
                  placeholder="Unlimited if empty"
                />
              </div>
            </div>
          </section>

          <Separator />

          {/* Temporal */}
          <section>
            <h4 className="mb-3 text-sm font-semibold text-gray-900">
              Temporal
            </h4>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="active_hours_start" className="text-xs">
                    Active Hours Start
                  </Label>
                  <Input
                    id="active_hours_start"
                    type="time"
                    {...form.register("active_hours_start")}
                  />
                </div>
                <div>
                  <Label htmlFor="active_hours_end" className="text-xs">
                    Active Hours End
                  </Label>
                  <Input
                    id="active_hours_end"
                    type="time"
                    {...form.register("active_hours_end")}
                  />
                </div>
              </div>
              <div>
                <Label htmlFor="timezone" className="text-xs">
                  Timezone
                </Label>
                <Input
                  id="timezone"
                  {...form.register("timezone")}
                  placeholder="UTC"
                />
                {form.formState.errors.timezone && (
                  <p className="mt-1 text-xs text-red-600">
                    {form.formState.errors.timezone.message}
                  </p>
                )}
              </div>
            </div>
          </section>

          <Separator />

          {/* Data Access */}
          <section>
            <h4 className="mb-3 text-sm font-semibold text-gray-900">
              Data Access
            </h4>
            <div className="space-y-3">
              <div>
                <Label htmlFor="read_paths" className="text-xs">
                  Read Paths (comma-separated)
                </Label>
                <Input
                  id="read_paths"
                  {...form.register("read_paths")}
                  placeholder="/data/reports, /data/metrics"
                />
              </div>
              <div>
                <Label htmlFor="write_paths" className="text-xs">
                  Write Paths (comma-separated)
                </Label>
                <Input
                  id="write_paths"
                  {...form.register("write_paths")}
                  placeholder="/data/output"
                />
              </div>
            </div>
          </section>

          <Separator />

          {/* Communication */}
          <section>
            <h4 className="mb-3 text-sm font-semibold text-gray-900">
              Communication
            </h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <Label htmlFor="internal_only" className="text-xs">
                  Internal Only
                </Label>
                <Switch
                  id="internal_only"
                  checked={form.watch("internal_only")}
                  onCheckedChange={(checked) =>
                    form.setValue("internal_only", checked)
                  }
                />
              </div>
              <div>
                <Label htmlFor="allowed_channels" className="text-xs">
                  Allowed Channels (comma-separated)
                </Label>
                <Input
                  id="allowed_channels"
                  {...form.register("allowed_channels")}
                  placeholder="slack, email"
                />
              </div>
            </div>
          </section>

          <SheetFooter className="pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={updateEnvelope.isPending}>
              {updateEnvelope.isPending ? "Saving..." : "Save Changes"}
            </Button>
          </SheetFooter>

          {updateEnvelope.isError && (
            <p className="text-sm text-red-600">
              {updateEnvelope.error instanceof Error
                ? updateEnvelope.error.message
                : "Failed to save changes"}
            </p>
          )}
        </form>
      </SheetContent>
    </Sheet>
  );
}
