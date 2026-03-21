// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Firebase configuration for the PACT dashboard.
 *
 * Initializes Firebase Auth with Google and GitHub SSO providers.
 * All configuration comes from NEXT_PUBLIC_FIREBASE_* environment variables.
 *
 * When Firebase is not configured (env vars missing), the module exports
 * null values so the app can fall back to static token authentication.
 */

import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import {
  getAuth,
  GoogleAuthProvider,
  GithubAuthProvider,
  type Auth,
} from "firebase/auth";

// ---------------------------------------------------------------------------
// Configuration from environment variables
// ---------------------------------------------------------------------------

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? "",
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? "",
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? "",
};

/**
 * Whether Firebase is configured. When false, the app falls back
 * to static token authentication.
 */
export const isFirebaseConfigured: boolean =
  !!firebaseConfig.apiKey &&
  !!firebaseConfig.authDomain &&
  !!firebaseConfig.projectId;

// ---------------------------------------------------------------------------
// Firebase initialization (only when configured)
// ---------------------------------------------------------------------------

let app: FirebaseApp | null = null;
let auth: Auth | null = null;
let googleProvider: GoogleAuthProvider | null = null;
let githubProvider: GithubAuthProvider | null = null;

if (isFirebaseConfigured) {
  // Prevent duplicate initialization in development (HMR)
  app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
  auth = getAuth(app);

  googleProvider = new GoogleAuthProvider();
  googleProvider.addScope("profile");
  googleProvider.addScope("email");

  githubProvider = new GithubAuthProvider();
  githubProvider.addScope("read:user");
  githubProvider.addScope("user:email");
}

export { app, auth, googleProvider, githubProvider };
