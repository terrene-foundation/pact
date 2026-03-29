// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * StatCard -- reusable dashboard stat card with icon, value, label, and
 * optional trend indicator or sub-content.
 *
 * Extracted from app/page.tsx inline StatCard pattern. Uses Shadcn Card
 * primitives for consistent styling.
 */

"use client";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/shadcn/card";

interface StatCardProps {
  /** Navigation target when the card is clicked. */
  href?: string;
  /** Icon element displayed in the top-left corner. */
  icon?: React.ReactNode;
  /** Background color class for the icon container. */
  iconBg?: string;
  /** Primary metric value (number, string, or element). */
  value: React.ReactNode;
  /** Short label describing the metric. */
  label: string;
  /** Optional subtitle text below the value. */
  subtitle?: string;
  /** Optional trend indicator (percentage change and description). */
  trend?: { value: number; label: string };
  /** Optional arbitrary content below the label. */
  subContent?: React.ReactNode;
  /** Additional CSS classes. */
  className?: string;
}

/**
 * Dashboard stat card with icon, value, label, and optional trend or
 * sub-content. Renders as a link when `href` is provided.
 */
export function StatCard({
  href,
  icon,
  iconBg = "bg-muted",
  value,
  label,
  subtitle,
  trend,
  subContent,
  className,
}: StatCardProps) {
  const Wrapper = href ? "a" : "div";
  const wrapperProps = href ? { href } : {};

  return (
    <Wrapper
      {...wrapperProps}
      className={cn("group block", href && "cursor-pointer", className)}
    >
      <Card className={cn("transition-shadow", href && "hover:shadow-md")}>
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            {icon && (
              <div
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-lg",
                  iconBg,
                )}
              >
                {icon}
              </div>
            )}
            {href && (
              <svg
                className="h-5 w-5 text-muted-foreground/40 group-hover:text-primary transition-colors"
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

          <p className="mt-3 text-3xl font-semibold tracking-tight">{value}</p>
          <p className="text-sm text-muted-foreground">{label}</p>

          {subtitle && (
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          )}

          {trend && (
            <p
              className={cn(
                "mt-2 text-xs",
                trend.value >= 0 ? "text-green-600" : "text-red-600",
              )}
            >
              {trend.value >= 0 ? "+" : ""}
              {trend.value}% {trend.label}
            </p>
          )}

          {subContent && <div className="mt-1">{subContent}</div>}
        </CardContent>
      </Card>
    </Wrapper>
  );
}
