// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * EnvelopeCard -- constraint envelope card showing all five PACT dimensions.
 *
 * Composes Shadcn Card with the existing DimensionGauge and ConstraintGauge
 * components. Displays Financial, Operational, Temporal, Data Access, and
 * Communication dimensions in a responsive grid.
 */

"use client";

import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/shadcn/card";
import { Badge } from "@/components/ui/shadcn/badge";
import { Progress } from "@/components/ui/shadcn/progress";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A single constraint dimension with utilization data. */
interface DimensionData {
  /** Dimension name (Financial, Operational, Temporal, Data Access, Communication). */
  name: string;
  /** Current utilization value. */
  current: number;
  /** Maximum allowed value. */
  maximum: number;
  /** Unit label (e.g., "USD", "actions", "hours"). */
  unit?: string;
  /** Key metrics to display below the gauge. */
  details?: Array<{ label: string; value: string }>;
}

interface EnvelopeCardProps {
  /** Envelope identifier. */
  envelopeId: string;
  /** Human-readable description. */
  description?: string;
  /** Associated agent identifier. */
  agentId?: string;
  /** Associated team identifier. */
  teamId?: string;
  /** The five constraint dimensions with utilization data. */
  dimensions: DimensionData[];
  /** Navigation target on card click. */
  href?: string;
  /** Additional CSS classes. */
  className?: string;
}

// ---------------------------------------------------------------------------
// SVG icon paths for each dimension
// ---------------------------------------------------------------------------

const DIMENSION_ICONS: Record<string, string> = {
  financial:
    "M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  operational:
    "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
  temporal: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  "data access":
    "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4",
  communication:
    "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z",
};

/** Get the icon SVG path for a dimension name. */
function getDimensionIcon(dimensionName: string): string {
  const key = dimensionName.toLowerCase();
  return (
    DIMENSION_ICONS[key] ??
    // Fallback: generic info circle
    "M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
  );
}

/** Calculate utilization percentage from current/maximum. */
function getUtilization(current: number, maximum: number): number {
  if (maximum <= 0) return 0;
  return Math.min(Math.round((current / maximum) * 100), 100);
}

/** Get progress bar color based on utilization percentage. */
function getBarColorClass(percent: number): string {
  if (percent >= 81) return "[&>div]:bg-red-500";
  if (percent >= 61) return "[&>div]:bg-yellow-500";
  return "[&>div]:bg-green-500";
}

/** Get text color for the utilization percentage. */
function getTextColorClass(percent: number): string {
  if (percent >= 81) return "text-red-700";
  if (percent >= 61) return "text-yellow-700";
  return "text-green-700";
}

// ---------------------------------------------------------------------------
// DimensionRow sub-component
// ---------------------------------------------------------------------------

function DimensionRow({ dim }: { dim: DimensionData }) {
  const percent = getUtilization(dim.current, dim.maximum);
  const iconPath = getDimensionIcon(dim.name);

  return (
    <div className="space-y-2">
      {/* Header: icon + name + percentage */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50">
            <svg
              className="h-3.5 w-3.5 text-blue-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d={iconPath}
              />
            </svg>
          </div>
          <span className="text-sm font-medium text-foreground">
            {dim.name}
          </span>
        </div>
        <span
          className={cn("text-sm font-semibold", getTextColorClass(percent))}
        >
          {percent}%
        </span>
      </div>

      {/* Progress bar */}
      <Progress
        value={percent}
        className={cn("h-2", getBarColorClass(percent))}
        aria-label={`${dim.name}: ${percent}% utilized`}
      />

      {/* Detail metrics */}
      {dim.details && dim.details.length > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 pt-0.5">
          {dim.details.map((detail) => (
            <div key={detail.label} className="flex items-center gap-1 text-xs">
              <span className="text-muted-foreground">{detail.label}:</span>
              <span className="font-medium text-foreground">
                {detail.value}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// EnvelopeCard
// ---------------------------------------------------------------------------

/**
 * Card displaying a constraint envelope with its five dimensions.
 * Shows utilization gauges for each dimension in a vertical stack.
 */
export function EnvelopeCard({
  envelopeId,
  description,
  agentId,
  teamId,
  dimensions,
  href,
  className,
}: EnvelopeCardProps) {
  const Wrapper = href ? "a" : "div";
  const wrapperProps = href ? { href } : {};

  return (
    <Wrapper {...wrapperProps}>
      <Card
        className={cn(
          "transition-shadow",
          href && "hover:shadow-md cursor-pointer",
          className,
        )}
      >
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-base">{envelopeId}</CardTitle>
              {description && (
                <CardDescription className="mt-1">
                  {description}
                </CardDescription>
              )}
            </div>
            {href && (
              <svg
                className="h-5 w-5 text-muted-foreground/40"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            )}
          </div>

          {/* Agent/Team badges */}
          {(agentId || teamId) && (
            <div className="flex flex-wrap gap-2 pt-2">
              {agentId && (
                <Badge variant="secondary" className="text-xs">
                  Agent: {agentId}
                </Badge>
              )}
              {teamId && (
                <Badge variant="secondary" className="text-xs">
                  Team: {teamId}
                </Badge>
              )}
            </div>
          )}
        </CardHeader>

        <CardContent className="space-y-4">
          {dimensions.map((dim) => (
            <DimensionRow key={dim.name} dim={dim} />
          ))}

          {dimensions.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">
              No dimension data available.
            </p>
          )}
        </CardContent>
      </Card>
    </Wrapper>
  );
}
