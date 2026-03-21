// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * AuthContext -- authentication state management for the PACT dashboard.
 *
 * Supports two authentication methods:
 *   1. Firebase SSO (Google / GitHub) -- primary, when Firebase is configured
 *   2. Static token login -- fallback for API-only access or when Firebase
 *      is not configured
 *
 * On Firebase auth state change, the Firebase ID token is automatically
 * used as the Bearer token for API calls. Tokens are refreshed before
 * expiry.
 *
 * The useAuth() hook exposes:
 *   { user, loading, signInWithGoogle, signInWithGithub, signOut,
 *     login (legacy token), isAuthenticated, isLoaded, token }
 */

"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import {
  signInWithPopup,
  onAuthStateChanged,
  type User as FirebaseUser,
} from "firebase/auth";
import { resetApiClient } from "./use-api";
import {
  auth as firebaseAuth,
  googleProvider,
  githubProvider,
  isFirebaseConfigured,
} from "./firebase";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Supported user roles. Only governance_officer is active today. */
export type UserRole = "governance_officer" | "admin" | "auditor" | "operator";

/** Human-readable labels for each role. */
export const ROLE_LABELS: Record<UserRole, string> = {
  governance_officer: "Governance Officer",
  admin: "Administrator",
  auditor: "Auditor",
  operator: "Operator",
};

/** Authenticated user information. */
export interface AuthUser {
  name: string;
  role: UserRole;
  email?: string;
  photoURL?: string;
  /** "firebase" for SSO users, "token" for static token users. */
  authMethod: "firebase" | "token";
}

/** Shape of the auth context value. */
export interface AuthContextValue {
  /** Current user, or null if not authenticated. */
  user: AuthUser | null;
  /** Current API token (Firebase ID token or static token), or null. */
  token: string | null;
  /** Whether the user is authenticated. */
  isAuthenticated: boolean;
  /** Whether auth state has been loaded (from Firebase or localStorage). */
  isLoaded: boolean;
  /** Whether an auth operation is in progress (SSO popup, token validation). */
  loading: boolean;
  /** Sign in with Google SSO. Returns true on success, error string on failure. */
  signInWithGoogle: () => Promise<true | string>;
  /** Sign in with GitHub SSO. Returns true on success, error string on failure. */
  signInWithGithub: () => Promise<true | string>;
  /** Sign out (works for both Firebase and token auth). */
  signOut: () => void;
  /** Legacy token login. Returns true on success, error string on failure. */
  login: (
    name: string,
    token: string,
    remember?: boolean,
  ) => Promise<true | string>;
  /** Legacy logout alias. */
  logout: () => void;
}

// ---------------------------------------------------------------------------
// localStorage keys (for static token fallback)
// ---------------------------------------------------------------------------

const STORAGE_KEY_TOKEN = "CARE_API_TOKEN";
const STORAGE_KEY_USER_NAME = "CARE_USER_NAME";
const STORAGE_KEY_USER_ROLE = "CARE_USER_ROLE";
const STORAGE_KEY_AUTH_METHOD = "CARE_AUTH_METHOD";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextValue | null>(null);

/** Use the auth context. Throws if called outside AuthProvider. */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [loading, setLoading] = useState(false);

  // -----------------------------------------------------------------------
  // Firebase auth state listener
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!isFirebaseConfigured || !firebaseAuth) {
      // Firebase not configured -- fall back to localStorage token
      hydrateFromLocalStorage();
      return;
    }

    const unsubscribe = onAuthStateChanged(
      firebaseAuth,
      async (firebaseUser: FirebaseUser | null) => {
        if (firebaseUser) {
          // Get the ID token for API calls
          const idToken = await firebaseUser.getIdToken();
          setToken(idToken);
          setUser({
            name: firebaseUser.displayName ?? firebaseUser.email ?? "User",
            email: firebaseUser.email ?? undefined,
            photoURL: firebaseUser.photoURL ?? undefined,
            role: "governance_officer",
            authMethod: "firebase",
          });

          // Persist auth method so we know how to restore on refresh
          try {
            localStorage.setItem(STORAGE_KEY_AUTH_METHOD, "firebase");
          } catch {
            // Storage unavailable
          }

          resetApiClient();
        } else {
          // Firebase user signed out -- check if there's a token-based session
          const storedMethod = safeGetItem(STORAGE_KEY_AUTH_METHOD);
          if (storedMethod === "firebase") {
            // Was Firebase auth, now signed out -- clear everything
            clearStoredCredentials();
            setToken(null);
            setUser(null);
            resetApiClient();
          } else {
            // Token auth -- hydrate from localStorage
            hydrateFromLocalStorage();
          }
        }
        setIsLoaded(true);
      },
    );

    return () => unsubscribe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // -----------------------------------------------------------------------
  // Token refresh (Firebase ID tokens expire after 1 hour)
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (
      !isFirebaseConfigured ||
      !firebaseAuth ||
      !user ||
      user.authMethod !== "firebase"
    ) {
      return;
    }

    // Capture a non-null reference for the closure (guard above ensures non-null)
    const authInstance = firebaseAuth;

    // Refresh the token every 50 minutes (tokens expire at 60 minutes)
    const interval = setInterval(
      async () => {
        const currentUser = authInstance.currentUser;
        if (currentUser) {
          const freshToken = await currentUser.getIdToken(true);
          setToken(freshToken);
          resetApiClient();
        }
      },
      50 * 60 * 1000,
    );

    return () => clearInterval(interval);
  }, [user]);

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  function safeGetItem(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  }

  function hydrateFromLocalStorage() {
    try {
      const storedToken = localStorage.getItem(STORAGE_KEY_TOKEN);
      const storedName = localStorage.getItem(STORAGE_KEY_USER_NAME);
      const storedRole = localStorage.getItem(
        STORAGE_KEY_USER_ROLE,
      ) as UserRole | null;

      if (storedToken && storedName) {
        setToken(storedToken);
        setUser({
          name: storedName,
          role: storedRole ?? "governance_officer",
          authMethod: "token",
        });
      }
    } catch {
      // localStorage unavailable (SSR, incognito edge cases)
    }
    setIsLoaded(true);
  }

  function clearStoredCredentials() {
    try {
      localStorage.removeItem(STORAGE_KEY_TOKEN);
      localStorage.removeItem(STORAGE_KEY_USER_NAME);
      localStorage.removeItem(STORAGE_KEY_USER_ROLE);
      localStorage.removeItem(STORAGE_KEY_AUTH_METHOD);
    } catch {
      // Ignore storage errors
    }
  }

  // -----------------------------------------------------------------------
  // Firebase SSO sign-in
  // -----------------------------------------------------------------------

  const signInWithGoogle = useCallback(async (): Promise<true | string> => {
    if (!firebaseAuth || !googleProvider) {
      return "Google sign-in is not available. Firebase is not configured.";
    }
    setLoading(true);
    try {
      await signInWithPopup(firebaseAuth, googleProvider);
      // onAuthStateChanged will handle setting user + token
      return true;
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      if (
        message.includes("popup-closed-by-user") ||
        message.includes("cancelled-popup-request")
      ) {
        return "Sign-in was cancelled.";
      }
      return `Google sign-in failed: ${message}`;
    } finally {
      setLoading(false);
    }
  }, []);

  const signInWithGithub = useCallback(async (): Promise<true | string> => {
    if (!firebaseAuth || !githubProvider) {
      return "GitHub sign-in is not available. Firebase is not configured.";
    }
    setLoading(true);
    try {
      await signInWithPopup(firebaseAuth, githubProvider);
      // onAuthStateChanged will handle setting user + token
      return true;
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      if (
        message.includes("popup-closed-by-user") ||
        message.includes("cancelled-popup-request")
      ) {
        return "Sign-in was cancelled.";
      }
      if (message.includes("account-exists-with-different-credential")) {
        return "An account already exists with the same email. Try signing in with a different provider.";
      }
      return `GitHub sign-in failed: ${message}`;
    } finally {
      setLoading(false);
    }
  }, []);

  // -----------------------------------------------------------------------
  // Sign out (works for both Firebase and token auth)
  // -----------------------------------------------------------------------

  const handleSignOut = useCallback(() => {
    // Clear stored credentials
    clearStoredCredentials();

    // Sign out of Firebase if applicable
    if (firebaseAuth && user?.authMethod === "firebase") {
      firebaseAuth.signOut().catch(() => {
        // Ignore sign-out errors -- we clear local state regardless
      });
    }

    setToken(null);
    setUser(null);
    resetApiClient();

    // Redirect to login
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }, [user]);

  // -----------------------------------------------------------------------
  // Legacy token login (backward compatible)
  // -----------------------------------------------------------------------

  const login = useCallback(
    async (
      name: string,
      inputToken: string,
      remember = true,
    ): Promise<true | string> => {
      const baseUrl =
        typeof window !== "undefined"
          ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
          : "http://localhost:8000";

      setLoading(true);
      try {
        const response = await fetch(`${baseUrl}/health`, {
          headers: {
            Authorization: `Bearer ${inputToken}`,
          },
        });

        if (!response.ok) {
          return "Unable to connect to the PACT API. Please check the server is running.";
        }
      } catch {
        return "Unable to reach the PACT API. Please check your network connection and ensure the server is running.";
      } finally {
        setLoading(false);
      }

      // Store credentials
      const role: UserRole = "governance_officer";

      if (remember) {
        try {
          localStorage.setItem(STORAGE_KEY_TOKEN, inputToken);
          localStorage.setItem(STORAGE_KEY_USER_NAME, name);
          localStorage.setItem(STORAGE_KEY_USER_ROLE, role);
          localStorage.setItem(STORAGE_KEY_AUTH_METHOD, "token");
        } catch {
          // Storage full or unavailable -- proceed anyway
        }
      }

      setToken(inputToken);
      setUser({ name, role, authMethod: "token" });
      resetApiClient();

      return true;
    },
    [],
  );

  // -----------------------------------------------------------------------
  // Context value
  // -----------------------------------------------------------------------

  const value: AuthContextValue = {
    user,
    token,
    isAuthenticated: !!token && !!user,
    isLoaded,
    loading,
    signInWithGoogle,
    signInWithGithub,
    signOut: handleSignOut,
    login,
    logout: handleSignOut,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
