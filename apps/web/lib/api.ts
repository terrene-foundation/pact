// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * API client for the PACT backend.
 *
 * Provides typed methods for every API endpoint. All methods return
 * properly typed ApiResponse<T> objects with error handling.
 *
 * Auth: Bearer token via Authorization header. The token can be provided
 * at construction time or set dynamically via setToken().
 */

import type {
  AgentDetail,
  ApiResponse,
  AuditAnchor,
  Bridge,
  BridgeAuditResponse,
  BridgeDetail,
  ConstraintEnvelope,
  CreateBridgeRequest,
  DmStatus,
  DmTask,
  EnvelopeSummary,
  PlatformEvent,
  ShadowMetrics,
  ShadowReport,
  TrustChainDetail,
  TrustChainSummary,
  VerificationStats,
  Workspace,
} from "../types/pact";

/** Configuration for the API client. */
export interface ApiClientConfig {
  /** Base URL of the PACT API (e.g., "http://localhost:8000"). */
  baseUrl: string;
  /** Optional Bearer token for Authorization header. */
  token?: string;
  /** Optional request timeout in milliseconds. Defaults to 10000. */
  timeoutMs?: number;
}

/** Error thrown when the API returns a non-OK HTTP status. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly responseBody: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Error thrown when a network request fails entirely. */
export class NetworkError extends Error {
  constructor(
    message: string,
    public readonly cause?: unknown,
  ) {
    super(message);
    this.name = "NetworkError";
  }
}

/**
 * PACT API client.
 *
 * Usage:
 * ```ts
 * const client = new PactApiClient({
 *   baseUrl: "http://localhost:8000",
 *   token: "my-api-token",
 * });
 * const chains = await client.listTrustChains();
 * ```
 */
export class PactApiClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private token: string | undefined;

  constructor(config: ApiClientConfig) {
    if (!config.baseUrl) {
      throw new Error(
        "PactApiClient requires a non-empty baseUrl. " +
          "Provide the PACT API URL (e.g., 'http://localhost:8000').",
      );
    }
    // Strip trailing slash for consistent URL construction
    this.baseUrl = config.baseUrl.replace(/\/+$/, "");
    this.timeoutMs = config.timeoutMs ?? 10000;
    this.token = config.token;
  }

  /** Set or update the Bearer token for authenticated requests. */
  setToken(token: string | undefined): void {
    this.token = token;
  }

  /** Get the current token (useful for checking auth state). */
  getToken(): string | undefined {
    return this.token;
  }

  /** Get the configured base URL. */
  getBaseUrl(): string {
    return this.baseUrl;
  }

  // ------------------------------------------------------------------
  // Internal fetch helper
  // ------------------------------------------------------------------

  private async request<T>(
    path: string,
    options?: RequestInit,
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options?.headers as Record<string, string> | undefined),
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers,
      });

      if (response.status === 401) {
        const body = await response.text();
        throw new ApiError(
          `Authentication failed: invalid or missing API token for ${path}`,
          401,
          body,
        );
      }

      if (response.status === 403) {
        const body = await response.text();
        throw new ApiError(
          `Access denied: insufficient permissions for ${path}`,
          403,
          body,
        );
      }

      if (!response.ok) {
        const body = await response.text();
        throw new ApiError(
          `API request failed: ${response.status} ${response.statusText} for ${path}`,
          response.status,
          body,
        );
      }

      const data: ApiResponse<T> = await response.json();
      return data;
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new NetworkError(
          `Request to ${path} timed out after ${this.timeoutMs}ms`,
        );
      }
      throw new NetworkError(
        `Network request to ${path} failed: ${error instanceof Error ? error.message : String(error)}`,
        error,
      );
    } finally {
      clearTimeout(timeout);
    }
  }

  // ------------------------------------------------------------------
  // Health check
  // ------------------------------------------------------------------

  /** Check if the API server is healthy. */
  async health(): Promise<{ status: string; service: string }> {
    const url = `${this.baseUrl}/health`;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) {
        throw new ApiError(
          "Health check failed",
          response.status,
          await response.text(),
        );
      }
      return response.json();
    } finally {
      clearTimeout(timeout);
    }
  }

  // ------------------------------------------------------------------
  // Phase 1 endpoints
  // ------------------------------------------------------------------

  /** List all active teams. */
  async listTeams(): Promise<ApiResponse<{ teams: string[] }>> {
    return this.request("/api/v1/teams");
  }

  /** List agents in a team. */
  async listAgents(teamId: string): Promise<
    ApiResponse<{
      agents: Array<{
        agent_id: string;
        name: string;
        role: string;
        posture: string;
        status: string;
      }>;
    }>
  > {
    return this.request(`/api/v1/teams/${encodeURIComponent(teamId)}/agents`);
  }

  /** Get agent status and posture. */
  async agentStatus(agentId: string): Promise<ApiResponse<TrustChainDetail>> {
    return this.request(`/api/v1/agents/${encodeURIComponent(agentId)}/status`);
  }

  /** Approve a held action. */
  async approveAction(
    agentId: string,
    actionId: string,
    approverId: string,
    reason?: string,
  ): Promise<
    ApiResponse<{ action_id: string; decision: string; decided_by: string }>
  > {
    const params = new URLSearchParams({ approver_id: approverId });
    if (reason) params.set("reason", reason);
    return this.request(
      `/api/v1/agents/${encodeURIComponent(agentId)}/approve/${encodeURIComponent(actionId)}?${params}`,
      { method: "POST" },
    );
  }

  /** Reject a held action. */
  async rejectAction(
    agentId: string,
    actionId: string,
    approverId: string,
    reason?: string,
  ): Promise<
    ApiResponse<{ action_id: string; decision: string; decided_by: string }>
  > {
    const params = new URLSearchParams({ approver_id: approverId });
    if (reason) params.set("reason", reason);
    return this.request(
      `/api/v1/agents/${encodeURIComponent(agentId)}/reject/${encodeURIComponent(actionId)}?${params}`,
      { method: "POST" },
    );
  }

  /** List all pending approval actions. */
  async heldActions(): Promise<
    ApiResponse<{
      actions: Array<{
        action_id: string;
        agent_id: string;
        team_id: string;
        action: string;
        reason: string;
        urgency: string;
        submitted_at: string;
      }>;
    }>
  > {
    return this.request("/api/v1/held-actions");
  }

  /** Get API cost report. */
  async costReport(params?: {
    teamId?: string;
    agentId?: string;
    days?: number;
  }): Promise<
    ApiResponse<{
      total_cost: string;
      period_days: number;
      total_calls: number;
      by_agent: Record<string, string>;
      by_model: Record<string, string>;
      by_day: Record<string, string>;
      alerts_triggered: number;
    }>
  > {
    const searchParams = new URLSearchParams();
    if (params?.teamId) searchParams.set("team_id", params.teamId);
    if (params?.agentId) searchParams.set("agent_id", params.agentId);
    if (params?.days !== undefined)
      searchParams.set("days", String(params.days));
    const qs = searchParams.toString();
    return this.request(`/api/v1/cost/report${qs ? `?${qs}` : ""}`);
  }

  // ------------------------------------------------------------------
  // M18 Dashboard endpoints
  // ------------------------------------------------------------------

  /** List all trust chains with status. */
  async listTrustChains(): Promise<
    ApiResponse<{ trust_chains: TrustChainSummary[] }>
  > {
    return this.request("/api/v1/trust-chains");
  }

  /** Get trust chain detail for an agent. */
  async getTrustChainDetail(
    agentId: string,
  ): Promise<ApiResponse<TrustChainDetail>> {
    return this.request(`/api/v1/trust-chains/${encodeURIComponent(agentId)}`);
  }

  /** List all constraint envelopes. */
  async listEnvelopes(): Promise<
    ApiResponse<{ envelopes: EnvelopeSummary[] }>
  > {
    return this.request("/api/v1/envelopes");
  }

  /** Get constraint envelope with all five CARE dimensions. */
  async getEnvelope(
    envelopeId: string,
  ): Promise<ApiResponse<ConstraintEnvelope>> {
    return this.request(`/api/v1/envelopes/${encodeURIComponent(envelopeId)}`);
  }

  /** List audit anchors with optional filters. */
  async listAuditAnchors(params?: {
    agentId?: string;
    level?: string;
    startDate?: string;
    endDate?: string;
  }): Promise<ApiResponse<{ anchors: AuditAnchor[] }>> {
    const searchParams = new URLSearchParams();
    if (params?.agentId) searchParams.set("agent_id", params.agentId);
    if (params?.level) searchParams.set("level", params.level);
    if (params?.startDate) searchParams.set("start_date", params.startDate);
    if (params?.endDate) searchParams.set("end_date", params.endDate);
    const qs = searchParams.toString();
    return this.request(`/api/v1/audit${qs ? `?${qs}` : ""}`);
  }

  /** Get audit trail for a specific team. */
  async getTeamAudit(
    teamId: string,
  ): Promise<ApiResponse<{ anchors: AuditAnchor[] }>> {
    return this.request(`/api/v1/audit/team/${encodeURIComponent(teamId)}`);
  }

  /** Get detailed agent info with posture history. */
  async getAgentDetail(agentId: string): Promise<ApiResponse<AgentDetail>> {
    return this.request(`/api/v1/agents/${encodeURIComponent(agentId)}`);
  }

  /** Suspend an active agent. */
  async suspendAgent(
    agentId: string,
    reason: string,
    suspendedBy: string,
  ): Promise<ApiResponse<{ agent_id: string; status: string }>> {
    const params = new URLSearchParams({ reason, suspended_by: suspendedBy });
    return this.request(
      `/api/v1/agents/${encodeURIComponent(agentId)}/suspend?${params}`,
      { method: "POST" },
    );
  }

  /** Revoke an agent (irreversible). */
  async revokeAgent(
    agentId: string,
    reason: string,
    revokedBy: string,
  ): Promise<ApiResponse<{ agent_id: string; status: string }>> {
    const params = new URLSearchParams({ reason, revoked_by: revokedBy });
    return this.request(
      `/api/v1/agents/${encodeURIComponent(agentId)}/revoke?${params}`,
      { method: "POST" },
    );
  }

  /** Change an agent's trust posture. */
  async changePosture(
    agentId: string,
    newPosture: string,
    reason: string,
    changedBy: string,
  ): Promise<ApiResponse<{ agent_id: string; posture: string }>> {
    return this.request(
      `/api/v1/agents/${encodeURIComponent(agentId)}/posture`,
      {
        method: "PUT",
        body: JSON.stringify({
          posture: newPosture,
          reason,
          changed_by: changedBy,
        }),
      },
    );
  }

  /** List all workspaces with state and phase. */
  async listWorkspaces(): Promise<ApiResponse<{ workspaces: Workspace[] }>> {
    return this.request("/api/v1/workspaces");
  }

  /** List all cross-functional bridges with status. */
  async listBridges(): Promise<ApiResponse<{ bridges: Bridge[] }>> {
    return this.request("/api/v1/bridges");
  }

  /** Get bridge detail by ID. */
  async getBridge(bridgeId: string): Promise<ApiResponse<BridgeDetail>> {
    return this.request(`/api/v1/bridges/${encodeURIComponent(bridgeId)}`);
  }

  /** Create a cross-functional bridge. */
  async createBridge(
    data: CreateBridgeRequest,
  ): Promise<ApiResponse<BridgeDetail>> {
    return this.request("/api/v1/bridges", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  /** Approve a bridge on source or target side. */
  async approveBridge(
    bridgeId: string,
    side: "source" | "target",
    approverId: string,
  ): Promise<ApiResponse<BridgeDetail>> {
    const params = new URLSearchParams({ side, approver_id: approverId });
    return this.request(
      `/api/v1/bridges/${encodeURIComponent(bridgeId)}/approve?${params}`,
      { method: "PUT" },
    );
  }

  /** Suspend an active bridge. */
  async suspendBridge(
    bridgeId: string,
    reason: string,
  ): Promise<ApiResponse<BridgeDetail>> {
    const params = new URLSearchParams({ reason });
    return this.request(
      `/api/v1/bridges/${encodeURIComponent(bridgeId)}/suspend?${params}`,
      { method: "POST" },
    );
  }

  /** Close a bridge. */
  async closeBridge(
    bridgeId: string,
    reason: string,
  ): Promise<ApiResponse<BridgeDetail>> {
    const params = new URLSearchParams({ reason });
    return this.request(
      `/api/v1/bridges/${encodeURIComponent(bridgeId)}/close?${params}`,
      { method: "POST" },
    );
  }

  /** List bridges for a specific team. */
  async listBridgesByTeam(
    teamId: string,
  ): Promise<ApiResponse<{ bridges: Bridge[] }>> {
    return this.request(`/api/v1/bridges/team/${encodeURIComponent(teamId)}`);
  }

  /** Get bridge audit trail. */
  async bridgeAudit(
    bridgeId: string,
    params?: {
      startDate?: string;
      endDate?: string;
      limit?: number;
      offset?: number;
    },
  ): Promise<ApiResponse<BridgeAuditResponse>> {
    const searchParams = new URLSearchParams();
    if (params?.startDate) searchParams.set("start_date", params.startDate);
    if (params?.endDate) searchParams.set("end_date", params.endDate);
    if (params?.limit !== undefined)
      searchParams.set("limit", String(params.limit));
    if (params?.offset !== undefined)
      searchParams.set("offset", String(params.offset));
    const qs = searchParams.toString();
    return this.request(
      `/api/v1/bridges/${encodeURIComponent(bridgeId)}/audit${qs ? `?${qs}` : ""}`,
    );
  }

  /** Get verification gradient counts by level. */
  async verificationStats(): Promise<ApiResponse<VerificationStats>> {
    return this.request("/api/v1/verification/stats");
  }

  /** Get 7-day verification gradient trends for sparklines. */
  async dashboardTrends(): Promise<
    ApiResponse<{
      dates: string[];
      auto_approved: number[];
      flagged: number[];
      held: number[];
      blocked: number[];
    }>
  > {
    return this.request("/api/v1/dashboard/trends");
  }

  // ------------------------------------------------------------------
  // ShadowEnforcer endpoints
  // ------------------------------------------------------------------

  /** Get ShadowEnforcer metrics for a specific agent. */
  async shadowMetrics(agentId: string): Promise<ApiResponse<ShadowMetrics>> {
    return this.request(
      `/api/v1/shadow/${encodeURIComponent(agentId)}/metrics`,
    );
  }

  /** Get ShadowEnforcer report for a specific agent. */
  async shadowReport(agentId: string): Promise<ApiResponse<ShadowReport>> {
    return this.request(`/api/v1/shadow/${encodeURIComponent(agentId)}/report`);
  }

  // ------------------------------------------------------------------
  // Upgrade Evidence endpoint (M42)
  // ------------------------------------------------------------------

  /** Get upgrade evidence for posture upgrade evaluation. */
  async upgradeEvidence(agentId: string): Promise<
    ApiResponse<{
      agent_id: string;
      total_operations: number;
      successful_operations: number;
      shadow_enforcer_pass_rate: number;
      incidents: number;
      recommendation: "eligible" | "not_eligible" | "needs_review";
      current_posture: string;
      target_posture: string | null;
    }>
  > {
    return this.request(
      `/api/v1/agents/${encodeURIComponent(agentId)}/upgrade-evidence`,
    );
  }

  // ------------------------------------------------------------------
  // DM (Decision-Making) Team endpoints
  // ------------------------------------------------------------------

  /** Get DM team status overview with all agents and summary stats. */
  async getDmStatus(): Promise<ApiResponse<DmStatus>> {
    return this.request("/api/v1/dm/status");
  }

  /** Submit a task to the DM team for routing and execution. */
  async submitDmTask(
    description: string,
    targetAgent?: string,
  ): Promise<ApiResponse<DmTask>> {
    return this.request("/api/v1/dm/tasks", {
      method: "POST",
      body: JSON.stringify({
        description,
        ...(targetAgent ? { target_agent: targetAgent } : {}),
      }),
    });
  }

  /** Get the current status of a DM task. */
  async getDmTaskStatus(taskId: string): Promise<ApiResponse<DmTask>> {
    return this.request(`/api/v1/dm/tasks/${encodeURIComponent(taskId)}`);
  }
}

// ---------------------------------------------------------------------------
// WebSocket Client
// ---------------------------------------------------------------------------

/** Connection state for the WebSocket client. */
export type WebSocketState =
  | "connecting"
  | "connected"
  | "disconnected"
  | "reconnecting";

/** Listener for platform events. */
export type EventListener = (event: PlatformEvent) => void;

/** Listener for connection state changes. */
export type StateListener = (state: WebSocketState) => void;

/** Configuration for the WebSocket client. */
export interface WebSocketClientConfig {
  /** WebSocket URL (e.g., "ws://localhost:8000/ws"). */
  url: string;
  /** Optional Bearer token for authentication (sent as query param). */
  token?: string;
  /** Maximum reconnection attempts. Defaults to 10. */
  maxReconnectAttempts?: number;
  /** Initial reconnect delay in ms. Defaults to 1000. */
  initialReconnectDelayMs?: number;
  /** Maximum reconnect delay in ms (backoff cap). Defaults to 30000. */
  maxReconnectDelayMs?: number;
}

/**
 * WebSocket client for real-time PACT events.
 *
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Event type listeners
 * - Connection state tracking
 *
 * Usage:
 * ```ts
 * const ws = new PactWebSocketClient({
 *   url: "ws://localhost:8000/ws",
 *   token: "my-token",
 * });
 * ws.onEvent((event) => console.log(event));
 * ws.onStateChange((state) => console.log("WS:", state));
 * ws.connect();
 * // later: ws.disconnect();
 * ```
 */
export class PactWebSocketClient {
  private ws: WebSocket | null = null;
  private state: WebSocketState = "disconnected";
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly eventListeners: Set<EventListener> = new Set();
  private readonly stateListeners: Set<StateListener> = new Set();

  private readonly url: string;
  private readonly token: string | undefined;
  private readonly maxReconnectAttempts: number;
  private readonly initialReconnectDelayMs: number;
  private readonly maxReconnectDelayMs: number;
  private intentionalClose = false;

  constructor(config: WebSocketClientConfig) {
    this.url = config.url;
    this.token = config.token;
    this.maxReconnectAttempts = config.maxReconnectAttempts ?? 2;
    this.initialReconnectDelayMs = config.initialReconnectDelayMs ?? 1000;
    this.maxReconnectDelayMs = config.maxReconnectDelayMs ?? 30000;
  }

  /** Get the current connection state. */
  getState(): WebSocketState {
    return this.state;
  }

  /** Register a listener for all platform events. */
  onEvent(listener: EventListener): () => void {
    this.eventListeners.add(listener);
    return () => {
      this.eventListeners.delete(listener);
    };
  }

  /** Register a listener for connection state changes. */
  onStateChange(listener: StateListener): () => void {
    this.stateListeners.add(listener);
    return () => {
      this.stateListeners.delete(listener);
    };
  }

  /** Connect to the WebSocket server. */
  connect(): void {
    if (
      this.ws &&
      (this.state === "connected" || this.state === "connecting")
    ) {
      return;
    }

    this.intentionalClose = false;
    this.createConnection();
  }

  /** Disconnect from the WebSocket server and stop reconnecting. */
  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnectTimer();
    this.reconnectAttempts = 0;

    if (this.ws) {
      this.ws.close(1000, "Client disconnect");
      this.ws = null;
    }

    this.setState("disconnected");
  }

  /** Get the current reconnect attempt count. */
  getReconnectAttempts(): number {
    return this.reconnectAttempts;
  }

  // ------------------------------------------------------------------
  // Internal
  // ------------------------------------------------------------------

  private setState(newState: WebSocketState): void {
    if (this.state === newState) return;
    this.state = newState;
    for (const listener of this.stateListeners) {
      try {
        listener(newState);
      } catch {
        // Listener errors should not break state management
      }
    }
  }

  private createConnection(): void {
    this.setState("connecting");

    // Build URL — prefer Sec-WebSocket-Protocol for auth (avoids server warning)
    const wsUrl = this.url;
    const protocols = this.token ? [`bearer.${this.token}`] : undefined;

    try {
      this.ws = new WebSocket(wsUrl, protocols);
    } catch {
      this.setState("disconnected");
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.setState("connected");
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(String(event.data)) as PlatformEvent;
        for (const listener of this.eventListeners) {
          try {
            listener(data);
          } catch {
            // Listener errors should not break event dispatch
          }
        }
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onclose = (event: CloseEvent) => {
      this.ws = null;

      if (this.intentionalClose) {
        this.setState("disconnected");
        return;
      }

      // Server closed or connection lost -- try to reconnect
      this.setState("disconnected");
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      // Error events are followed by close events, so reconnection
      // is handled in onclose. Just update state if still connecting.
      if (this.state === "connecting") {
        this.setState("disconnected");
      }
    };
  }

  private scheduleReconnect(): void {
    if (this.intentionalClose) return;
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.setState("disconnected");
      return;
    }

    // Exponential backoff with jitter
    const baseDelay =
      this.initialReconnectDelayMs * Math.pow(2, this.reconnectAttempts);
    const delay = Math.min(baseDelay, this.maxReconnectDelayMs);
    const jitter = delay * 0.1 * Math.random();
    const finalDelay = delay + jitter;

    this.reconnectAttempts++;
    this.setState("reconnecting");

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.intentionalClose) {
        this.createConnection();
      }
    }, finalDelay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
