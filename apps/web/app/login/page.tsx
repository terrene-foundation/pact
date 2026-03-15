// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Login page -- authentication entry point for the CARE Platform dashboard.
 *
 * Collects operator name and API token. Validates the token against the
 * backend health check before storing credentials. Redirects to the
 * dashboard on success.
 *
 * This page intentionally does NOT use DashboardShell (no sidebar).
 */

"use client";

import { useState, useCallback, useEffect, type FormEvent } from "react";
import { useAuth } from "../../lib/auth-context";

export default function LoginPage() {
  const { isAuthenticated, isLoaded, login } = useAuth();

  const [name, setName] = useState("");
  const [token, setToken] = useState("");
  const [remember, setRemember] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Redirect to dashboard if already authenticated
  useEffect(() => {
    if (isLoaded && isAuthenticated) {
      window.location.href = "/";
    }
  }, [isLoaded, isAuthenticated]);

  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setError(null);

      const trimmedName = name.trim();
      const trimmedToken = token.trim();

      if (!trimmedName) {
        setError("Please enter your operator name.");
        return;
      }
      if (!trimmedToken) {
        setError("Please enter your API token.");
        return;
      }

      setLoading(true);
      try {
        const result = await login(trimmedName, trimmedToken, remember);
        if (result === true) {
          // Redirect to dashboard
          window.location.href = "/";
        } else {
          setError(result);
        }
      } catch {
        setError("An unexpected error occurred. Please try again.");
      } finally {
        setLoading(false);
      }
    },
    [name, token, remember, login],
  );

  // Show nothing until auth state is loaded (prevents flash)
  if (!isLoaded) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-care-primary border-t-transparent" />
      </div>
    );
  }

  // Already authenticated -- will redirect via useEffect
  if (isAuthenticated) {
    return null;
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-4">
      {/* Brand */}
      <div className="mb-8 flex flex-col items-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-care-primary shadow-lg">
          <span className="text-2xl font-bold text-white">C</span>
        </div>
        <h1 className="mt-4 text-2xl font-bold text-gray-900">CARE Platform</h1>
        <p className="mt-1 text-sm text-care-muted">
          Governed operational model for AI agent orchestration
        </p>
      </div>

      {/* Login card */}
      <div className="w-full max-w-sm rounded-lg border border-care-border bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900">Sign in</h2>
        <p className="mt-1 text-sm text-care-muted">
          Enter your operator credentials to access the dashboard.
        </p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          {/* Error */}
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Operator name */}
          <div>
            <label
              htmlFor="operator-name"
              className="block text-sm font-medium text-gray-700"
            >
              Operator Name
            </label>
            <input
              id="operator-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Jane Smith"
              autoComplete="username"
              disabled={loading}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 shadow-sm focus:border-care-primary focus:outline-none focus:ring-1 focus:ring-care-primary disabled:opacity-50"
            />
          </div>

          {/* API token */}
          <div>
            <label
              htmlFor="api-token"
              className="block text-sm font-medium text-gray-700"
            >
              API Token
            </label>
            <input
              id="api-token"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Enter your CARE_API_TOKEN"
              autoComplete="current-password"
              disabled={loading}
              className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder-gray-400 shadow-sm focus:border-care-primary focus:outline-none focus:ring-1 focus:ring-care-primary disabled:opacity-50 font-mono"
            />
            <p className="mt-1 text-xs text-care-muted">
              The bearer token configured in your CARE Platform backend.
            </p>
          </div>

          {/* Remember me */}
          <div className="flex items-center gap-2">
            <input
              id="remember-me"
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              disabled={loading}
              className="h-4 w-4 rounded border-gray-300 text-care-primary focus:ring-care-primary"
            />
            <label htmlFor="remember-me" className="text-sm text-gray-700">
              Remember me
            </label>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-care-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-care-primary-dark focus:outline-none focus:ring-2 focus:ring-care-primary focus:ring-offset-2 disabled:opacity-50 transition-colors"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Verifying...
              </span>
            ) : (
              "Sign In"
            )}
          </button>
        </form>
      </div>

      {/* Footer */}
      <p className="mt-6 text-xs text-care-muted">
        CARE Platform v0.1.0 &middot; Terrene Foundation
      </p>
    </div>
  );
}
