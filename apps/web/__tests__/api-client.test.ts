// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Tests for the PactApiClient and PactWebSocketClient.
 *
 * Uses vi.fn() mocks for fetch and WebSocket to test:
 * - HTTP request construction and error handling
 * - Auth token inclusion
 * - WebSocket reconnection with exponential backoff
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  PactApiClient,
  PactWebSocketClient,
  ApiError,
  NetworkError,
} from "../lib/api";
import type { WebSocketState } from "../lib/api";

// =========================================================================
// PactApiClient
// =========================================================================

describe("PactApiClient", () => {
  const mockFetch = vi.fn();
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = mockFetch;
    mockFetch.mockReset();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("throws if baseUrl is empty", () => {
    expect(() => new PactApiClient({ baseUrl: "" })).toThrow(
      "PactApiClient requires a non-empty baseUrl",
    );
  });

  it("strips trailing slashes from baseUrl", () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000///" });
    expect(client.getBaseUrl()).toBe("http://localhost:8000");
  });

  it("stores and retrieves tokens", () => {
    const client = new PactApiClient({
      baseUrl: "http://localhost:8000",
      token: "test-token",
    });
    expect(client.getToken()).toBe("test-token");

    client.setToken("new-token");
    expect(client.getToken()).toBe("new-token");

    client.setToken(undefined);
    expect(client.getToken()).toBeUndefined();
  });

  it("includes Authorization header when token is set", async () => {
    const client = new PactApiClient({
      baseUrl: "http://localhost:8000",
      token: "my-secret-token",
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "ok",
          data: { teams: ["team-a"] },
          error: null,
        }),
    });

    await client.listTeams();

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const calledHeaders = mockFetch.mock.calls[0][1].headers;
    expect(calledHeaders["Authorization"]).toBe("Bearer my-secret-token");
  });

  it("does not include Authorization header when no token", async () => {
    const client = new PactApiClient({
      baseUrl: "http://localhost:8000",
    });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "ok",
          data: { teams: [] },
          error: null,
        }),
    });

    await client.listTeams();

    const calledHeaders = mockFetch.mock.calls[0][1].headers;
    expect(calledHeaders["Authorization"]).toBeUndefined();
  });

  it("returns typed data for listTeams", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "ok",
          data: { teams: ["alpha", "beta"] },
          error: null,
        }),
    });

    const result = await client.listTeams();
    expect(result.status).toBe("ok");
    expect(result.data?.teams).toEqual(["alpha", "beta"]);
  });

  it("throws ApiError on 401", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      text: () => Promise.resolve("Unauthorized"),
    });

    await expect(client.listTeams()).rejects.toThrow(ApiError);
    await expect(
      new PactApiClient({ baseUrl: "http://localhost:8000" })
        .listTeams()
        .catch((e: ApiError) => {
          // Re-mock for this call
          throw e;
        }),
    ).rejects.toThrow(); // just verify it rejects
  });

  it("throws ApiError on 403", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      text: () => Promise.resolve("Forbidden"),
    });

    try {
      await client.listTeams();
      expect.fail("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).statusCode).toBe(403);
      expect((err as ApiError).message).toContain("Access denied");
    }
  });

  it("throws ApiError on 500", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      text: () => Promise.resolve("Server error"),
    });

    try {
      await client.listTeams();
      expect.fail("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).statusCode).toBe(500);
    }
  });

  it("throws NetworkError on fetch failure", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockRejectedValueOnce(new Error("Failed to fetch"));

    try {
      await client.listTeams();
      expect.fail("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(NetworkError);
      expect((err as NetworkError).message).toContain("Failed to fetch");
    }
  });

  it("throws NetworkError on timeout", async () => {
    const client = new PactApiClient({
      baseUrl: "http://localhost:8000",
      timeoutMs: 10,
    });

    mockFetch.mockImplementationOnce(
      (_url: string, opts: RequestInit) =>
        new Promise((_resolve, reject) => {
          opts.signal?.addEventListener("abort", () =>
            reject(
              new DOMException("The operation was aborted.", "AbortError"),
            ),
          );
        }),
    );

    try {
      await client.listTeams();
      expect.fail("Should have thrown");
    } catch (err) {
      expect(err).toBeInstanceOf(NetworkError);
      expect((err as NetworkError).message).toContain("timed out");
    }
  });

  it("encodes URL parameters in listAgents", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "ok",
          data: { agents: [] },
          error: null,
        }),
    });

    await client.listAgents("team with spaces");

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain("team%20with%20spaces");
  });

  it("sends POST for approveAction", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "ok",
          data: {
            action_id: "act-1",
            decision: "approved",
            decided_by: "op-1",
          },
          error: null,
        }),
    });

    const result = await client.approveAction(
      "agent-1",
      "act-1",
      "op-1",
      "Looks good",
    );
    expect(result.data?.decision).toBe("approved");
    expect(mockFetch.mock.calls[0][1].method).toBe("POST");
  });

  it("sends POST for rejectAction", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "ok",
          data: {
            action_id: "act-1",
            decision: "rejected",
            decided_by: "op-1",
          },
          error: null,
        }),
    });

    const result = await client.rejectAction("agent-1", "act-1", "op-1");
    expect(result.data?.decision).toBe("rejected");
  });

  it("builds costReport URL with query params", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "ok",
          data: {
            total_cost: "150.00",
            period_days: 7,
            total_calls: 100,
            by_agent: {},
            by_model: {},
            alerts_triggered: 0,
          },
          error: null,
        }),
    });

    await client.costReport({ teamId: "alpha", days: 7 });

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain("team_id=alpha");
    expect(calledUrl).toContain("days=7");
  });

  it("builds listAuditAnchors URL with filters", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "ok",
          data: { anchors: [] },
          error: null,
        }),
    });

    await client.listAuditAnchors({
      agentId: "agent-1",
      level: "HELD",
      startDate: "2026-01-01",
      endDate: "2026-01-31",
    });

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain("agent_id=agent-1");
    expect(calledUrl).toContain("level=HELD");
    expect(calledUrl).toContain("start_date=2026-01-01");
    expect(calledUrl).toContain("end_date=2026-01-31");
  });

  it("calls health endpoint correctly", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ status: "healthy", service: "pact" }),
    });

    const result = await client.health();
    expect(result.status).toBe("healthy");

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toBe("http://localhost:8000/health");
  });

  it("calls getTeamAudit with team ID", async () => {
    const client = new PactApiClient({ baseUrl: "http://localhost:8000" });

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          status: "ok",
          data: { anchors: [] },
          error: null,
        }),
    });

    await client.getTeamAudit("team-alpha");

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toBe(
      "http://localhost:8000/api/v1/audit/team/team-alpha",
    );
  });
});

// =========================================================================
// PactWebSocketClient
// =========================================================================

describe("PactWebSocketClient", () => {
  let mockWebSocketInstances: MockWebSocket[];

  class MockWebSocket {
    url: string;
    protocols: string | string[] | undefined;
    onopen: ((event: Event) => void) | null = null;
    onclose: ((event: CloseEvent) => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    readyState = 0; // CONNECTING

    constructor(url: string, protocols?: string | string[]) {
      this.url = url;
      this.protocols = protocols;
      mockWebSocketInstances.push(this);
    }

    close(_code?: number, _reason?: string): void {
      this.readyState = 3; // CLOSED
    }

    /** Simulate the server opening the connection. */
    simulateOpen(): void {
      this.readyState = 1; // OPEN
      this.onopen?.(new Event("open"));
    }

    /** Simulate a message from the server. */
    simulateMessage(data: string): void {
      this.onmessage?.(new MessageEvent("message", { data }));
    }

    /** Simulate the connection closing. */
    simulateClose(code = 1006): void {
      this.readyState = 3;
      this.onclose?.(new CloseEvent("close", { code }));
    }

    /** Simulate an error. */
    simulateError(): void {
      this.onerror?.(new Event("error"));
    }
  }

  beforeEach(() => {
    mockWebSocketInstances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("starts in disconnected state", () => {
    const client = new PactWebSocketClient({
      url: "ws://localhost:8000/ws",
    });
    expect(client.getState()).toBe("disconnected");
  });

  it("transitions to connected on open", () => {
    const client = new PactWebSocketClient({
      url: "ws://localhost:8000/ws",
    });

    const states: WebSocketState[] = [];
    client.onStateChange((state) => states.push(state));

    client.connect();
    expect(states).toContain("connecting");

    mockWebSocketInstances[0].simulateOpen();
    expect(states).toContain("connected");
    expect(client.getState()).toBe("connected");

    client.disconnect();
  });

  it("sends token via Sec-WebSocket-Protocol header", () => {
    const client = new PactWebSocketClient({
      url: "ws://localhost:8000/ws",
      token: "secret-token",
    });

    client.connect();
    expect(mockWebSocketInstances[0].url).toBe("ws://localhost:8000/ws");
    expect(mockWebSocketInstances[0].protocols).toContain(
      "bearer.secret-token",
    );

    client.disconnect();
  });

  it("dispatches events to listeners", () => {
    const client = new PactWebSocketClient({
      url: "ws://localhost:8000/ws",
    });

    const events: unknown[] = [];
    client.onEvent((event) => events.push(event));

    client.connect();
    mockWebSocketInstances[0].simulateOpen();

    mockWebSocketInstances[0].simulateMessage(
      JSON.stringify({
        event_id: "evt-1",
        event_type: "audit_anchor",
        data: { action: "test" },
        source_agent_id: "agent-1",
        source_team_id: "team-alpha",
        timestamp: "2026-03-14T10:00:00Z",
      }),
    );

    expect(events).toHaveLength(1);
    expect((events[0] as Record<string, unknown>).event_id).toBe("evt-1");

    client.disconnect();
  });

  it("removes listeners via unsubscribe function", () => {
    const client = new PactWebSocketClient({
      url: "ws://localhost:8000/ws",
    });

    const events: unknown[] = [];
    const unsubscribe = client.onEvent((event) => events.push(event));

    client.connect();
    mockWebSocketInstances[0].simulateOpen();

    // First event should be received
    mockWebSocketInstances[0].simulateMessage(
      JSON.stringify({
        event_id: "evt-1",
        event_type: "audit_anchor",
        data: {},
        source_agent_id: "a",
        source_team_id: "t",
        timestamp: "2026-03-14T10:00:00Z",
      }),
    );
    expect(events).toHaveLength(1);

    // Unsubscribe and send another event
    unsubscribe();
    mockWebSocketInstances[0].simulateMessage(
      JSON.stringify({
        event_id: "evt-2",
        event_type: "audit_anchor",
        data: {},
        source_agent_id: "a",
        source_team_id: "t",
        timestamp: "2026-03-14T10:01:00Z",
      }),
    );
    expect(events).toHaveLength(1); // Still 1, not 2

    client.disconnect();
  });

  it("ignores malformed messages", () => {
    const client = new PactWebSocketClient({
      url: "ws://localhost:8000/ws",
    });

    const events: unknown[] = [];
    client.onEvent((event) => events.push(event));

    client.connect();
    mockWebSocketInstances[0].simulateOpen();

    mockWebSocketInstances[0].simulateMessage("not valid json");
    expect(events).toHaveLength(0);

    client.disconnect();
  });

  it("reconnects with exponential backoff on close", () => {
    const client = new PactWebSocketClient({
      url: "ws://localhost:8000/ws",
      initialReconnectDelayMs: 100,
      maxReconnectAttempts: 3,
    });

    const states: WebSocketState[] = [];
    client.onStateChange((state) => states.push(state));

    client.connect();
    mockWebSocketInstances[0].simulateOpen();
    expect(client.getState()).toBe("connected");

    // Simulate unexpected close
    mockWebSocketInstances[0].simulateClose(1006);

    // Should be in reconnecting state
    expect(states).toContain("reconnecting");
    expect(client.getReconnectAttempts()).toBe(1);

    // Advance timer past first reconnect delay (100ms + jitter)
    vi.advanceTimersByTime(200);

    // A new WebSocket should have been created
    expect(mockWebSocketInstances).toHaveLength(2);

    client.disconnect();
  });

  it("stops reconnecting after max attempts", () => {
    const client = new PactWebSocketClient({
      url: "ws://localhost:8000/ws",
      initialReconnectDelayMs: 100,
      maxReconnectAttempts: 2,
    });

    client.connect();
    // instance[0]: original connection

    // Fail first connection -> scheduleReconnect, attempts becomes 1
    mockWebSocketInstances[0].simulateError();
    mockWebSocketInstances[0].simulateClose(1006);
    expect(client.getReconnectAttempts()).toBe(1);

    // Advance past first reconnect delay (~100ms)
    vi.advanceTimersByTime(200);
    expect(mockWebSocketInstances).toHaveLength(2);
    // instance[1]: reconnect attempt 1

    // Fail second connection -> scheduleReconnect, attempts becomes 2
    mockWebSocketInstances[1].simulateError();
    mockWebSocketInstances[1].simulateClose(1006);
    expect(client.getReconnectAttempts()).toBe(2);

    // Advance past second reconnect delay (~200ms + jitter)
    vi.advanceTimersByTime(500);
    expect(mockWebSocketInstances).toHaveLength(3);
    // instance[2]: reconnect attempt 2

    // Fail third connection -> scheduleReconnect checks
    // attempts(2) >= max(2) -> true, stops reconnecting
    mockWebSocketInstances[2].simulateError();
    mockWebSocketInstances[2].simulateClose(1006);

    // No more reconnections should be scheduled
    vi.advanceTimersByTime(5000);
    expect(mockWebSocketInstances).toHaveLength(3);
    expect(client.getState()).toBe("disconnected");

    client.disconnect();
  });

  it("does not reconnect on intentional disconnect", () => {
    const client = new PactWebSocketClient({
      url: "ws://localhost:8000/ws",
      initialReconnectDelayMs: 100,
    });

    client.connect();
    mockWebSocketInstances[0].simulateOpen();
    expect(client.getState()).toBe("connected");

    // Intentional disconnect
    client.disconnect();
    expect(client.getState()).toBe("disconnected");
    expect(client.getReconnectAttempts()).toBe(0);

    // No new connections should be attempted
    vi.advanceTimersByTime(5000);
    expect(mockWebSocketInstances).toHaveLength(1);
  });

  it("resets reconnect attempts on successful connection", () => {
    const client = new PactWebSocketClient({
      url: "ws://localhost:8000/ws",
      initialReconnectDelayMs: 100,
      maxReconnectAttempts: 5,
    });

    client.connect();

    // Fail first connection
    mockWebSocketInstances[0].simulateError();
    mockWebSocketInstances[0].simulateClose(1006);
    expect(client.getReconnectAttempts()).toBe(1);

    // Advance past reconnect delay
    vi.advanceTimersByTime(200);

    // Successfully connect this time
    mockWebSocketInstances[1].simulateOpen();
    expect(client.getState()).toBe("connected");
    expect(client.getReconnectAttempts()).toBe(0); // Reset on success

    client.disconnect();
  });

  it("does not create duplicate connections when already connected", () => {
    const client = new PactWebSocketClient({
      url: "ws://localhost:8000/ws",
    });

    client.connect();
    mockWebSocketInstances[0].simulateOpen();

    // Trying to connect again should be a no-op
    client.connect();
    expect(mockWebSocketInstances).toHaveLength(1);

    client.disconnect();
  });
});
