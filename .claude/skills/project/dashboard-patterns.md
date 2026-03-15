# Dashboard Patterns

Patterns for working with the CARE Platform governance dashboard (Next.js web app).

## Design System Quick Reference

### Color Tokens (tailwind.config.js)

```
Verification gradient:  gradient-auto (#16a34a), gradient-flagged (#eab308), gradient-held (#f97316), gradient-blocked (#dc2626)
Trust postures:         posture-pseudo, posture-supervised, posture-shared, posture-continuous, posture-delegated
Agent status:           status-active (#16a34a), status-suspended (#eab308), status-revoked (#dc2626)
Approval urgency:       urgency-critical (#dc2626), urgency-high (#f97316), urgency-medium (#eab308), urgency-low (#6b7280)
Platform:               care-primary (#2563eb), care-surface, care-border, care-muted
```

### CSS Classes (globals.css)

```css
.badge-auto-approved / .badge-flagged / .badge-held / .badge-blocked
.badge-posture-pseudo / .badge-posture-supervised / etc.
.card / .card-interactive
.stat-card / .stat-value / .stat-label
.feed-item (animate-slide-in)
.gauge-bar / .gauge-fill
.font-hash (monospace for crypto values)
```

## Page Conventions

### Data Fetching

Every page uses `useApi` from `lib/use-api.ts`:

```typescript
const { data, loading, error, refetch } = useApi<ResponseType>(
  (client) => client.methodName(params),
  [dependency],
);
```

### Layout

All pages except `/login` use `DashboardShell` which provides sidebar, header, auth guard, notification listener, and toast container.

### Auth

`useAuth()` from `lib/auth-context.tsx` provides `user.name` for approver IDs. Never hardcode operator identity.

### Notifications

`useNotifications()` / `useNotificationsSafe()` from `lib/notification-context.tsx`. WebSocket events are converted to notifications by `NotificationListener` in DashboardShell.

## Component Patterns

### Confirmation Modal

```typescript
import ConfirmationModal from "@/components/ui/ConfirmationModal";

<ConfirmationModal
  isOpen={showModal}
  onClose={() => setShowModal(false)}
  onConfirm={handleConfirm}
  title="Suspend Agent"
  description="This will pause all agent operations."
  confirmLabel="Suspend"
  destructive={true}  // Red button
  requireReason={true}
  loading={isSubmitting}
/>
```

### Activity Feed

```typescript
import ActivityFeed from "@/components/activity/ActivityFeed";
<ActivityFeed maxHeight="500px" compact={false} />
```

### Charts (CSS-only, no libraries)

- Bar charts: styled `div` elements with percentage widths
- Gauges: `gauge-bar` + `gauge-fill` classes with dynamic width
- Sparklines: array of `div` bars with `transition-all`
- Circular gauge: SVG `circle` with `stroke-dashoffset`

## Accessibility Checklist

When creating new components:

- [ ] Icon-only buttons have `aria-label`
- [ ] Decorative elements have `aria-hidden="true"`
- [ ] Status elements have `role="status"`
- [ ] Live-updating regions have `aria-live="polite"`
- [ ] Forms have `htmlFor`/`id` pairing on all inputs
- [ ] Modals trap focus and restore on close
- [ ] Color is not the only indicator (use icons/text too)

## Demo Seed

Run `python scripts/seed_demo.py` to populate all pages with realistic data. The script is deterministic (seed=42) and idempotent.

## Key Architecture Decisions

See `workspaces/care-platform/decisions.yml` for full rationale on:

- Auth via /health endpoint (no dedicated login API)
- Client-side notifications from WebSocket events
- No external npm dependencies (all CSS-only)
- Demo seed deterministic via random.seed(42)
