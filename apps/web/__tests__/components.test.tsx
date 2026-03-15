// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * M20 component smoke tests.
 *
 * Verifies that all dashboard components render without errors when
 * provided valid props. Does not test API integration (uses static data).
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

// -- UI Components --
import StatusBadge from "../components/ui/StatusBadge";
import ConstraintGauge from "../components/ui/ConstraintGauge";
import ErrorAlert from "../components/ui/ErrorAlert";
import Skeleton, {
  CardSkeleton,
  TableSkeleton,
} from "../components/ui/Skeleton";

// -- Trust --
import TrustChainGraph from "../components/trust/TrustChainGraph";

// -- Constraints --
import DimensionGauge from "../components/constraints/DimensionGauge";

// -- Audit --
import AuditTable from "../components/audit/AuditTable";
import AuditFilters from "../components/audit/AuditFilters";

// -- Agents --
import PostureBadge, { PostureDot } from "../components/agents/PostureBadge";

// -- Verification --
import GradientChart from "../components/verification/GradientChart";

// -- Workspaces --
import WorkspaceCard from "../components/workspaces/WorkspaceCard";
import BridgeConnections from "../components/workspaces/BridgeConnections";

// -- Approvals --
import ApprovalCard from "../components/approvals/ApprovalCard";
import ApprovalActions from "../components/approvals/ApprovalActions";

// -- Layout --
import DashboardShell from "../components/layout/DashboardShell";
import Sidebar from "../components/layout/Sidebar";
import Header from "../components/layout/Header";

// =========================================================================
// UI Components
// =========================================================================

describe("StatusBadge", () => {
  it("renders verification level", () => {
    render(<StatusBadge value="AUTO_APPROVED" />);
    // formatLabel replaces _ with space and capitalizes each word
    expect(screen.getByText("AUTO APPROVED")).toBeInTheDocument();
  });

  it("renders trust posture", () => {
    render(<StatusBadge value="delegated" />);
    expect(screen.getByText("Delegated")).toBeInTheDocument();
  });

  it("renders custom label", () => {
    render(<StatusBadge value="active" label="Online" />);
    expect(screen.getByText("Online")).toBeInTheDocument();
  });
});

describe("ConstraintGauge", () => {
  it("renders with label and percentage", () => {
    render(
      <ConstraintGauge
        label="Budget"
        current={500}
        maximum={1000}
        unit="USD"
      />,
    );
    expect(screen.getByText("Budget")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("renders with zero maximum safely", () => {
    render(<ConstraintGauge label="Empty" current={0} maximum={0} />);
    expect(screen.getByText("0%")).toBeInTheDocument();
  });
});

describe("ErrorAlert", () => {
  it("renders error message", () => {
    render(<ErrorAlert message="Something broke" />);
    expect(screen.getByText("Something broke")).toBeInTheDocument();
  });

  it("renders retry button when callback provided", () => {
    render(<ErrorAlert message="Error" onRetry={() => {}} />);
    expect(screen.getByText("Retry")).toBeInTheDocument();
  });
});

describe("Skeleton", () => {
  it("renders default skeleton", () => {
    render(<Skeleton />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("renders CardSkeleton", () => {
    const { container } = render(<CardSkeleton />);
    expect(container.firstChild).toBeTruthy();
  });

  it("renders TableSkeleton", () => {
    const { container } = render(<TableSkeleton rows={3} />);
    expect(container.firstChild).toBeTruthy();
  });
});

// =========================================================================
// Trust Chain
// =========================================================================

describe("TrustChainGraph", () => {
  it("renders empty state", () => {
    render(<TrustChainGraph chains={[]} />);
    expect(screen.getByText("No trust chains found.")).toBeInTheDocument();
  });

  it("renders chains grouped by team", () => {
    render(
      <TrustChainGraph
        chains={[
          {
            agent_id: "agent-1",
            name: "Analyst Bot",
            team_id: "team-alpha",
            posture: "supervised",
            status: "active",
          },
          {
            agent_id: "agent-2",
            name: "Builder Bot",
            team_id: "team-alpha",
            posture: "shared_planning",
            status: "active",
          },
        ]}
      />,
    );
    expect(screen.getByText("Analyst Bot")).toBeInTheDocument();
    expect(screen.getByText("Builder Bot")).toBeInTheDocument();
    expect(screen.getByText("Genesis: Team team-alpha")).toBeInTheDocument();
  });
});

// =========================================================================
// Constraints
// =========================================================================

describe("DimensionGauge", () => {
  it("renders dimension with details", () => {
    render(
      <DimensionGauge
        dimension="Financial"
        current={250}
        maximum={1000}
        unit="USD"
        iconPath="M12 8v4l3 3"
        details={[
          { label: "Max Spend", value: "$1,000" },
          { label: "Threshold", value: "$500" },
        ]}
      />,
    );
    expect(screen.getByText("Financial")).toBeInTheDocument();
    expect(screen.getByText("Max Spend")).toBeInTheDocument();
  });
});

// =========================================================================
// Audit
// =========================================================================

describe("AuditTable", () => {
  it("renders empty state", () => {
    render(<AuditTable anchors={[]} />);
    expect(
      screen.getByText("No audit anchors found matching the current filters."),
    ).toBeInTheDocument();
  });

  it("renders audit entries", () => {
    render(
      <AuditTable
        anchors={[
          {
            anchor_id: "anc-001",
            agent_id: "agent-1",
            agent_name: "Test Agent",
            team_id: "team-alpha",
            action: "file_write",
            verification_level: "AUTO_APPROVED",
            timestamp: "2026-03-13T10:00:00Z",
            details: "Wrote config file",
          },
        ]}
      />,
    );
    expect(screen.getByText("Test Agent")).toBeInTheDocument();
    expect(screen.getByText("file_write")).toBeInTheDocument();
  });
});

describe("AuditFilters", () => {
  it("renders filter controls", () => {
    render(
      <AuditFilters
        filters={{
          agentQuery: "",
          actionQuery: "",
          teamId: "",
          level: "",
          startDate: "",
          endDate: "",
        }}
        onChange={() => {}}
        onReset={() => {}}
        teams={["team-alpha", "team-beta"]}
      />,
    );
    expect(screen.getByLabelText("Agent")).toBeInTheDocument();
    expect(screen.getByLabelText("Verification Level")).toBeInTheDocument();
  });
});

// =========================================================================
// Agents
// =========================================================================

describe("PostureBadge", () => {
  it("renders all posture types without error", () => {
    const postures = [
      "pseudo_agent",
      "supervised",
      "shared_planning",
      "continuous_insight",
      "delegated",
    ] as const;

    postures.forEach((posture) => {
      const { unmount } = render(<PostureBadge posture={posture} />);
      unmount();
    });
  });

  it("renders correct label", () => {
    render(<PostureBadge posture="delegated" />);
    expect(screen.getByText("Delegated")).toBeInTheDocument();
  });
});

describe("PostureDot", () => {
  it("renders without error", () => {
    const { container } = render(<PostureDot posture="supervised" />);
    expect(container.firstChild).toBeTruthy();
  });
});

// =========================================================================
// Verification
// =========================================================================

describe("GradientChart", () => {
  it("renders all four levels", () => {
    render(
      <GradientChart
        stats={{
          AUTO_APPROVED: 100,
          FLAGGED: 20,
          HELD: 5,
          BLOCKED: 2,
          total: 127,
        }}
      />,
    );
    // Each level label appears twice (bar chart + summary card)
    expect(screen.getAllByText("Auto Approved")).toHaveLength(2);
    expect(screen.getAllByText("Flagged")).toHaveLength(2);
    expect(screen.getAllByText("Held")).toHaveLength(2);
    expect(screen.getAllByText("Blocked")).toHaveLength(2);
    expect(screen.getByText("127")).toBeInTheDocument();
  });

  it("handles zero total gracefully", () => {
    render(
      <GradientChart
        stats={{
          AUTO_APPROVED: 0,
          FLAGGED: 0,
          HELD: 0,
          BLOCKED: 0,
          total: 0,
        }}
      />,
    );
    // Should render without division-by-zero errors
    // 4 levels each show "0%" in summary cards, bar percentages show "(0%)"
    const zeroPercentElements = screen.getAllByText("0%");
    expect(zeroPercentElements.length).toBeGreaterThanOrEqual(4);
  });
});

// =========================================================================
// Workspaces
// =========================================================================

describe("WorkspaceCard", () => {
  it("renders workspace info", () => {
    render(
      <WorkspaceCard
        workspace={{
          id: "ws-001",
          path: "/workspaces/platform",
          description: "Core platform workspace",
          state: "active",
          phase: "implement",
          team_id: "team-alpha",
        }}
      />,
    );
    expect(screen.getByText("platform")).toBeInTheDocument();
    expect(screen.getByText("Implement")).toBeInTheDocument();
  });
});

describe("BridgeConnections", () => {
  it("renders empty state", () => {
    render(<BridgeConnections bridges={[]} />);
    expect(
      screen.getByText("No Cross-Functional Bridges established."),
    ).toBeInTheDocument();
  });

  it("renders bridge entries", () => {
    render(
      <BridgeConnections
        bridges={[
          {
            bridge_id: "br-001",
            bridge_type: "standing",
            source_team_id: "alpha",
            target_team_id: "beta",
            purpose: "Shared knowledge transfer",
            status: "active",
            created_at: "2026-01-15T00:00:00Z",
          },
        ]}
      />,
    );
    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.getByText("beta")).toBeInTheDocument();
    expect(screen.getByText("Standing")).toBeInTheDocument();
  });
});

// =========================================================================
// Approvals
// =========================================================================

describe("ApprovalCard", () => {
  it("renders held action details", () => {
    render(
      <ApprovalCard
        item={{
          action_id: "act-001",
          agent_id: "agent-1",
          team_id: "team-alpha",
          action: "deploy_service",
          reason: "Exceeds daily action limit",
          urgency: "high",
          submitted_at: "2026-03-13T10:00:00Z",
        }}
        onResolved={() => {}}
        onApprove={async () => {}}
        onReject={async () => {}}
      />,
    );
    expect(screen.getByText("deploy_service")).toBeInTheDocument();
    expect(screen.getByText("Exceeds daily action limit")).toBeInTheDocument();
    expect(screen.getByText("Approve")).toBeInTheDocument();
    expect(screen.getByText("Reject")).toBeInTheDocument();
  });
});

describe("ApprovalActions", () => {
  it("renders approve and reject buttons", () => {
    render(
      <ApprovalActions
        agentId="agent-1"
        actionId="act-001"
        onResolved={() => {}}
        onApprove={async () => {}}
        onReject={async () => {}}
      />,
    );
    expect(screen.getByText("Approve")).toBeInTheDocument();
    expect(screen.getByText("Reject")).toBeInTheDocument();
  });
});

// =========================================================================
// Layout
// =========================================================================

describe("Sidebar", () => {
  it("renders navigation items", () => {
    render(<Sidebar activePath="/" />);
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Trust Chains")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Approvals")).toBeInTheDocument();
  });

  it("highlights active path", () => {
    render(<Sidebar activePath="/trust-chains" />);
    const link = screen.getByText("Trust Chains").closest("a");
    expect(link).toHaveAttribute("aria-current", "page");
  });
});

describe("Header", () => {
  it("renders title", () => {
    render(<Header title="Dashboard" />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("renders breadcrumbs", () => {
    render(
      <Header
        title="Detail Page"
        breadcrumbs={[{ label: "Home", href: "/" }, { label: "Detail" }]}
      />,
    );
    expect(screen.getByText("Home")).toBeInTheDocument();
    // "Detail" in breadcrumb, "Detail Page" in h1
    expect(screen.getByText("Detail")).toBeInTheDocument();
    expect(screen.getByText("Detail Page")).toBeInTheDocument();
  });
});

describe("DashboardShell", () => {
  it("renders with children", () => {
    render(
      <DashboardShell activePath="/" title="Test Page">
        <p>Content here</p>
      </DashboardShell>,
    );
    expect(screen.getByText("Test Page")).toBeInTheDocument();
    expect(screen.getByText("Content here")).toBeInTheDocument();
  });
});
