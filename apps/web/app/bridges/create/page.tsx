// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Bridge creation wizard -- multi-step form for creating Cross-Functional Bridges.
 *
 * Uses React Hook Form + Zod for form validation, React Query (useCreateBridge)
 * for submission, and Shadcn UI components for layout and inputs.
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
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import DashboardShell from "../../../components/layout/DashboardShell";
import { useCreateBridge } from "@/hooks";
import type { BridgeType, CreateBridgeRequest } from "../../../types/pact";
import {
  Card,
  CardContent,
  Button,
  Input,
  Textarea,
  Label,
  Alert,
  AlertTitle,
  AlertDescription,
  Badge,
  Form,
  FormField,
  FormItem,
  FormLabel,
  FormControl,
  FormDescription,
  FormMessage,
  Separator,
} from "@/components/ui/shadcn";

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

/** Zod schema for the bridge creation form. */
const bridgeSchema = z.object({
  bridge_type: z.enum(["standing", "scoped", "ad_hoc"]),
  source_team_id: z.string().min(1, "Source team is required"),
  target_team_id: z.string().min(1, "Target team is required"),
  purpose: z
    .string()
    .min(1, "Purpose is required")
    .max(500, "Purpose must be 500 characters or fewer"),
  read_paths: z.string().optional(),
  write_paths: z.string().optional(),
  message_types: z.string().optional(),
  valid_days: z.number().min(1).max(365).optional(),
  request_payload: z.string().optional(),
});

type BridgeFormValues = z.infer<typeof bridgeSchema>;

/** Step indicator with completed/current/upcoming states. */
function StepIndicator({ currentStep }: { currentStep: number }) {
  return (
    <nav aria-label="Bridge creation progress">
      <ol className="flex items-center justify-between">
        {STEPS.map((step, idx) => (
          <li key={step} className="flex items-center">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-colors ${
                idx === currentStep
                  ? "bg-primary text-primary-foreground"
                  : idx < currentStep
                    ? "bg-green-500 text-white dark:bg-green-600"
                    : "bg-muted text-muted-foreground"
              }`}
              aria-current={idx === currentStep ? "step" : undefined}
              aria-label={`Step ${idx + 1}: ${step}${idx < currentStep ? " (completed)" : idx === currentStep ? " (current)" : ""}`}
            >
              {idx < currentStep ? "\u2713" : idx + 1}
            </div>
            <span
              className={`ml-2 text-xs hidden sm:inline ${
                idx === currentStep
                  ? "font-medium text-foreground"
                  : "text-muted-foreground"
              }`}
            >
              {step}
            </span>
            {idx < STEPS.length - 1 && (
              <div
                className="mx-2 h-px w-8 bg-border sm:w-12"
                aria-hidden="true"
              />
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export default function CreateBridgePage() {
  const [currentStep, setCurrentStep] = useState(0);
  const createBridge = useCreateBridge();

  const form = useForm<BridgeFormValues>({
    resolver: zodResolver(bridgeSchema),
    defaultValues: {
      bridge_type: undefined,
      source_team_id: "",
      target_team_id: "",
      purpose: "",
      read_paths: "",
      write_paths: "",
      message_types: "",
      valid_days: 7,
      request_payload: "",
    },
    mode: "onChange",
  });

  const watchedValues = form.watch();

  const canProceed = (): boolean => {
    switch (currentStep) {
      case 0:
        return !!watchedValues.bridge_type;
      case 1:
        return (
          !!watchedValues.source_team_id?.trim() &&
          !!watchedValues.target_team_id?.trim() &&
          !!watchedValues.purpose?.trim()
        );
      case 2:
        return true; // Permissions are optional
      case 3:
        return true; // Validity step always passable
      case 4:
        return true; // Review step
      default:
        return false;
    }
  };

  const handleSubmit = () => {
    const values = form.getValues();
    if (!values.bridge_type) return;

    const splitLines = (text: string | undefined): string[] =>
      (text ?? "")
        .split("\n")
        .map((p) => p.trim())
        .filter(Boolean);

    const data: CreateBridgeRequest = {
      bridge_type: values.bridge_type,
      source_team_id: values.source_team_id.trim(),
      target_team_id: values.target_team_id.trim(),
      purpose: values.purpose.trim(),
      permissions: {
        read_paths: splitLines(values.read_paths),
        write_paths: splitLines(values.write_paths),
        message_types: splitLines(values.message_types),
      },
    };

    if (values.bridge_type === "scoped" && values.valid_days) {
      data.valid_days = values.valid_days;
    }

    if (values.bridge_type === "ad_hoc" && values.request_payload?.trim()) {
      try {
        data.request_payload = JSON.parse(values.request_payload);
      } catch {
        data.request_payload = { content: values.request_payload.trim() };
      }
    }

    createBridge.mutate(data, {
      onSuccess: (result) => {
        if (result?.bridge_id) {
          window.location.href = `/bridges/${result.bridge_id}`;
        } else {
          window.location.href = "/bridges";
        }
      },
    });
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
        <StepIndicator currentStep={currentStep} />

        {createBridge.error && (
          <Alert variant="destructive">
            <AlertTitle>Creation failed</AlertTitle>
            <AlertDescription>
              {createBridge.error instanceof Error
                ? createBridge.error.message
                : "Bridge creation failed"}
            </AlertDescription>
          </Alert>
        )}

        {/* Step content */}
        <Form {...form}>
          <Card>
            <CardContent className="p-6">
              {/* Step 1: Bridge Type */}
              {currentStep === 0 && (
                <div>
                  <h2 className="text-lg font-semibold text-foreground mb-4">
                    Select Bridge Type
                  </h2>
                  <FormField
                    control={form.control}
                    name="bridge_type"
                    render={({ field }) => (
                      <FormItem>
                        <div className="space-y-3">
                          {BRIDGE_TYPES.map((bt) => (
                            <label
                              key={bt.value}
                              className={`flex cursor-pointer rounded-lg border p-4 transition-colors ${
                                field.value === bt.value
                                  ? "border-primary bg-primary/5"
                                  : "border-border hover:border-primary/50"
                              }`}
                            >
                              <input
                                type="radio"
                                name="bridgeType"
                                value={bt.value}
                                checked={field.value === bt.value}
                                onChange={() => field.onChange(bt.value)}
                                className="mt-1 mr-3"
                              />
                              <div>
                                <p className="text-sm font-medium text-foreground">
                                  {bt.label}
                                </p>
                                <p className="mt-1 text-xs text-muted-foreground">
                                  {bt.description}
                                </p>
                              </div>
                            </label>
                          ))}
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              )}

              {/* Step 2: Teams */}
              {currentStep === 1 && (
                <div>
                  <h2 className="text-lg font-semibold text-foreground mb-4">
                    Select Source and Target Teams
                  </h2>
                  <div className="space-y-4">
                    <FormField
                      control={form.control}
                      name="source_team_id"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Source Team ID</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder="e.g., team-engineering"
                            />
                          </FormControl>
                          <FormDescription>
                            The team initiating the bridge request.
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="target_team_id"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Target Team ID</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder="e.g., team-standards"
                            />
                          </FormControl>
                          <FormDescription>
                            The team that will receive or respond to bridge
                            requests.
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="purpose"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Purpose</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder="e.g., Content review and approval"
                            />
                          </FormControl>
                          <FormDescription>
                            A clear description of why this bridge is needed.
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </div>
              )}

              {/* Step 3: Permissions */}
              {currentStep === 2 && (
                <div>
                  <h2 className="text-lg font-semibold text-foreground mb-4">
                    Define Permissions
                  </h2>
                  <p className="text-xs text-muted-foreground mb-4">
                    Specify access paths and message types. Enter one per line.
                    Use glob patterns for paths (e.g., workspaces/content/*).
                  </p>
                  <div className="space-y-4">
                    <FormField
                      control={form.control}
                      name="read_paths"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Read Paths</FormLabel>
                          <FormControl>
                            <Textarea
                              {...field}
                              placeholder={
                                "workspaces/content/*\nworkspaces/analytics/*"
                              }
                              rows={3}
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="write_paths"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Write Paths</FormLabel>
                          <FormControl>
                            <Textarea
                              {...field}
                              placeholder="workspaces/reviews/*"
                              rows={2}
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                    <FormField
                      control={form.control}
                      name="message_types"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Message Types</FormLabel>
                          <FormControl>
                            <Textarea
                              {...field}
                              placeholder={"review_request\napproval_response"}
                              rows={2}
                              className="font-mono"
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </div>
              )}

              {/* Step 4: Validity */}
              {currentStep === 3 && (
                <div>
                  <h2 className="text-lg font-semibold text-foreground mb-4">
                    Set Validity Period
                  </h2>
                  {watchedValues.bridge_type === "scoped" ? (
                    <FormField
                      control={form.control}
                      name="valid_days"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Valid for (days)</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              min={1}
                              max={365}
                              className="w-32"
                              onChange={(e) =>
                                field.onChange(
                                  Math.max(1, parseInt(e.target.value) || 1),
                                )
                              }
                            />
                          </FormControl>
                          <FormDescription>
                            The bridge will automatically expire after{" "}
                            {field.value ?? 7} day
                            {(field.value ?? 7) !== 1 ? "s" : ""}.
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  ) : watchedValues.bridge_type === "ad_hoc" ? (
                    <FormField
                      control={form.control}
                      name="request_payload"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Request Payload (optional)</FormLabel>
                          <FormControl>
                            <Textarea
                              {...field}
                              placeholder='{"review_type": "governance", "document": "constitution-v2.md"}'
                              rows={4}
                              className="font-mono"
                            />
                          </FormControl>
                          <FormDescription>
                            Ad-Hoc bridges carry a request payload. Enter JSON
                            or plain text. The bridge auto-closes after a
                            response is provided.
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  ) : (
                    <Card className="bg-muted/50">
                      <CardContent className="p-4">
                        <p className="text-sm text-muted-foreground">
                          Standing bridges have no expiry. They remain active
                          until explicitly closed or revoked. No additional
                          configuration is needed for this step.
                        </p>
                      </CardContent>
                    </Card>
                  )}
                </div>
              )}

              {/* Step 5: Review */}
              {currentStep === 4 && (
                <div>
                  <h2 className="text-lg font-semibold text-foreground mb-4">
                    Review and Submit
                  </h2>
                  <Card className="bg-muted/50">
                    <CardContent className="p-4 space-y-3">
                      <div className="flex justify-between">
                        <span className="text-xs text-muted-foreground">
                          Type
                        </span>
                        <Badge variant="outline">
                          {BRIDGE_TYPES.find(
                            (bt) => bt.value === watchedValues.bridge_type,
                          )?.label ?? watchedValues.bridge_type}
                        </Badge>
                      </div>
                      <Separator />
                      <div className="flex justify-between">
                        <span className="text-xs text-muted-foreground">
                          Source Team
                        </span>
                        <span className="text-sm font-medium text-foreground">
                          {watchedValues.source_team_id}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-xs text-muted-foreground">
                          Target Team
                        </span>
                        <span className="text-sm font-medium text-foreground">
                          {watchedValues.target_team_id}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-xs text-muted-foreground">
                          Purpose
                        </span>
                        <span className="text-sm text-foreground">
                          {watchedValues.purpose}
                        </span>
                      </div>
                      {watchedValues.read_paths?.trim() && (
                        <div>
                          <span className="text-xs text-muted-foreground">
                            Read Paths
                          </span>
                          <pre className="mt-1 text-xs font-mono text-foreground bg-background rounded p-2">
                            {watchedValues.read_paths.trim()}
                          </pre>
                        </div>
                      )}
                      {watchedValues.write_paths?.trim() && (
                        <div>
                          <span className="text-xs text-muted-foreground">
                            Write Paths
                          </span>
                          <pre className="mt-1 text-xs font-mono text-foreground bg-background rounded p-2">
                            {watchedValues.write_paths.trim()}
                          </pre>
                        </div>
                      )}
                      {watchedValues.message_types?.trim() && (
                        <div>
                          <span className="text-xs text-muted-foreground">
                            Message Types
                          </span>
                          <pre className="mt-1 text-xs font-mono text-foreground bg-background rounded p-2">
                            {watchedValues.message_types.trim()}
                          </pre>
                        </div>
                      )}
                      {watchedValues.bridge_type === "scoped" && (
                        <>
                          <Separator />
                          <div className="flex justify-between">
                            <span className="text-xs text-muted-foreground">
                              Valid Days
                            </span>
                            <span className="text-sm font-medium text-foreground">
                              {watchedValues.valid_days}
                            </span>
                          </div>
                        </>
                      )}
                    </CardContent>
                  </Card>
                  <p className="mt-4 text-xs text-muted-foreground">
                    After submission, the bridge will be in PENDING status and
                    require bilateral approval from both source and target teams
                    before it becomes ACTIVE.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </Form>

        {/* Navigation buttons */}
        <div className="flex justify-between">
          <Button
            variant="outline"
            onClick={() => setCurrentStep((s) => Math.max(0, s - 1))}
            disabled={currentStep === 0}
          >
            Back
          </Button>
          {currentStep < STEPS.length - 1 ? (
            <Button
              onClick={() => setCurrentStep((s) => s + 1)}
              disabled={!canProceed()}
            >
              Next
            </Button>
          ) : (
            <Button
              onClick={handleSubmit}
              disabled={createBridge.isPending || !canProceed()}
              className="bg-green-600 hover:bg-green-700 text-white"
            >
              {createBridge.isPending ? "Creating..." : "Create Bridge"}
            </Button>
          )}
        </div>
      </div>
    </DashboardShell>
  );
}
