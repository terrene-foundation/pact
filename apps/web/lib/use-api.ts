// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * useApi -- React hook for data fetching from the PACT API.
 *
 * Provides loading, error, and data states. Handles AbortController cleanup
 * on unmount to prevent state updates on unmounted components.
 *
 * useWebSocket -- React hook for real-time events via WebSocket.
 *
 * Token resolution priority:
 *   1. Firebase Auth ID token (when user is signed in via SSO)
 *   2. NEXT_PUBLIC_API_TOKEN environment variable
 *   3. localStorage CARE_API_TOKEN (static token login)
 */

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { ApiResponse, PlatformEvent } from "../types/pact";
import type { WebSocketState } from "./api";
import {
  PactApiClient,
  PactWebSocketClient,
  ApiError,
  NetworkError,
} from "./api";
import { auth as firebaseAuth, isFirebaseConfigured } from "./firebase";

/** Default API base URL. Uses environment variable or falls back to localhost. */
const DEFAULT_BASE_URL =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
    : "http://localhost:8000";

/**
 * Resolve the API token. Checks Firebase first, then env var, then localStorage.
 */
function resolveToken(): string | undefined {
  if (typeof window === "undefined") return undefined;

  // Priority 1: Firebase Auth -- get cached token from current user
  // (The fresh token is set by auth-context onAuthStateChanged)
  if (isFirebaseConfigured && firebaseAuth?.currentUser) {
    // getIdToken() returns a promise; for synchronous resolution we rely
    // on the token being refreshed by auth-context and stored in localStorage
    // via the auth method. The actual token is set on the client by
    // resetApiClient() calls in auth-context.
  }

  // Priority 2: Environment variable
  const envToken = process.env.NEXT_PUBLIC_API_TOKEN;
  if (envToken) return envToken;

  // Priority 3: localStorage (set by both Firebase and token auth flows)
  try {
    return localStorage.getItem("CARE_API_TOKEN") ?? undefined;
  } catch {
    return undefined;
  }
}

/**
 * Get a fresh token, including async Firebase token retrieval.
 * Used when creating or refreshing the API client.
 */
async function resolveTokenAsync(): Promise<string | undefined> {
  if (typeof window === "undefined") return undefined;

  // Priority 1: Firebase Auth ID token
  if (isFirebaseConfigured && firebaseAuth?.currentUser) {
    try {
      return await firebaseAuth.currentUser.getIdToken();
    } catch {
      // Fall through to other methods
    }
  }

  // Priority 2: Environment variable
  const envToken = process.env.NEXT_PUBLIC_API_TOKEN;
  if (envToken) return envToken;

  // Priority 3: localStorage
  try {
    return localStorage.getItem("CARE_API_TOKEN") ?? undefined;
  } catch {
    return undefined;
  }
}

/** Shared API client instance. */
let sharedClient: PactApiClient | null = null;

/** Get the shared API client instance. */
export function getApiClient(): PactApiClient {
  if (!sharedClient) {
    sharedClient = new PactApiClient({
      baseUrl: DEFAULT_BASE_URL,
      token: resolveToken(),
    });
  }
  return sharedClient;
}

/**
 * Get the shared API client with a fresh async token.
 * Preferred for Firebase auth where tokens may need refresh.
 */
export async function getApiClientAsync(): Promise<PactApiClient> {
  if (!sharedClient) {
    const token = await resolveTokenAsync();
    sharedClient = new PactApiClient({
      baseUrl: DEFAULT_BASE_URL,
      token,
    });
  } else {
    // Refresh token on existing client
    const token = await resolveTokenAsync();
    sharedClient.setToken(token);
  }
  return sharedClient;
}

/** Reset the shared client (useful for token changes). */
export function resetApiClient(): void {
  sharedClient = null;
}

/** State shape returned by the useApi hook. */
export interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Hook for fetching data from the PACT API.
 *
 * @param fetcher - Async function that calls the API client and returns data.
 * @param deps - Dependency array to re-fetch when values change.
 */
export function useApi<T>(
  fetcher: (client: PactApiClient) => Promise<ApiResponse<T>>,
  deps: ReadonlyArray<unknown> = [],
): UseApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(() => {
    mountedRef.current = true;
    setLoading(true);
    setError(null);

    // Use async token resolution for Firebase support
    getApiClientAsync()
      .then((client) => fetcher(client))
      .then((response) => {
        if (!mountedRef.current) return;
        if (response.status === "error") {
          setError(response.error ?? "Unknown API error");
          setData(null);
        } else {
          setData(response.data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!mountedRef.current) return;
        if (err instanceof ApiError) {
          if (err.statusCode === 401) {
            setError(
              "Authentication required. Please configure your API token.",
            );
          } else if (err.statusCode === 403) {
            setError(
              "Access denied. You do not have permission for this operation.",
            );
          } else {
            setError(`API error (${err.statusCode}): ${err.message}`);
          }
        } else if (err instanceof NetworkError) {
          setError(`Network error: ${err.message}`);
        } else {
          setError(
            err instanceof Error ? err.message : "Unknown error occurred",
          );
        }
        setData(null);
      })
      .finally(() => {
        if (mountedRef.current) {
          setLoading(false);
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    fetchData();
    return () => {
      mountedRef.current = false;
    };
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}

// ---------------------------------------------------------------------------
// WebSocket Hook
// ---------------------------------------------------------------------------

/** State shape returned by the useWebSocket hook. */
export interface UseWebSocketState {
  /** Current connection state. */
  connectionState: WebSocketState;
  /** Last received event (null until the first event arrives). */
  lastEvent: PlatformEvent | null;
  /** Connect to the WebSocket server. */
  connect: () => void;
  /** Disconnect from the WebSocket server. */
  disconnect: () => void;
}

/**
 * Derive the WebSocket URL from the HTTP API base URL.
 * Converts http:// to ws:// and https:// to wss://.
 */
function deriveWsUrl(baseUrl: string): string {
  return (
    baseUrl
      .replace(/^http:\/\//, "ws://")
      .replace(/^https:\/\//, "wss://")
      .replace(/\/+$/, "") + "/ws"
  );
}

/**
 * Hook for real-time WebSocket events from PACT.
 *
 * @param onEvent - Optional callback invoked for every received event.
 * @param autoConnect - Whether to connect automatically on mount. Defaults to true.
 */
export function useWebSocket(
  onEvent?: (event: PlatformEvent) => void,
  autoConnect = true,
): UseWebSocketState {
  const [connectionState, setConnectionState] =
    useState<WebSocketState>("disconnected");
  const [lastEvent, setLastEvent] = useState<PlatformEvent | null>(null);
  const clientRef = useRef<PactWebSocketClient | null>(null);
  const onEventRef = useRef(onEvent);

  // Keep the callback ref current without triggering reconnects
  onEventRef.current = onEvent;

  useEffect(() => {
    const wsUrl = deriveWsUrl(DEFAULT_BASE_URL);
    const token = resolveToken();

    const client = new PactWebSocketClient({
      url: wsUrl,
      token,
    });

    clientRef.current = client;

    const unsubState = client.onStateChange((state) => {
      setConnectionState(state);
    });

    const unsubEvent = client.onEvent((event) => {
      setLastEvent(event);
      onEventRef.current?.(event);
    });

    if (autoConnect) {
      client.connect();
    }

    return () => {
      unsubState();
      unsubEvent();
      client.disconnect();
      clientRef.current = null;
    };
  }, [autoConnect]);

  const connect = useCallback(() => {
    clientRef.current?.connect();
  }, []);

  const disconnect = useCallback(() => {
    clientRef.current?.disconnect();
  }, []);

  return { connectionState, lastEvent, connect, disconnect };
}
