# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Firebase Admin SDK integration for verifying Firebase ID tokens.

Initializes the Firebase Admin SDK using:
  1. GCP Application Default Credentials (when running on Cloud Run / GCE)
  2. GOOGLE_APPLICATION_CREDENTIALS env var (for local development with
     a service account JSON file)
  3. Falls back gracefully: when Firebase Admin cannot initialize, all
     verification calls return None so the server can fall back to
     static token authentication.

Usage:
    from pact_platform.trust.auth.firebase_admin import verify_firebase_id_token

    user_info = verify_firebase_id_token(id_token)
    if user_info is not None:
        # Authenticated via Firebase
        uid = user_info["uid"]
        email = user_info["email"]
        name = user_info["name"]
"""

from __future__ import annotations

import logging
import os
from typing import TypedDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Firebase Admin SDK initialization
# ---------------------------------------------------------------------------

_firebase_app = None
_firebase_auth = None
_initialized = False


class FirebaseUserInfo(TypedDict):
    """Typed dict returned by verify_firebase_id_token on success."""

    uid: str
    email: str
    name: str
    picture: str


def _ensure_initialized() -> bool:
    """Initialize Firebase Admin SDK on first use. Returns True if available."""
    global _firebase_app, _firebase_auth, _initialized

    if _initialized:
        return _firebase_auth is not None

    _initialized = True

    try:
        import firebase_admin  # noqa: F811
        from firebase_admin import auth as fb_auth
        from firebase_admin import credentials

        # Check if already initialized (e.g., by another module)
        try:
            _firebase_app = firebase_admin.get_app()
            _firebase_auth = fb_auth
            logger.info("Firebase Admin SDK: using existing app instance")
            return True
        except ValueError:
            pass

        # Initialize with Application Default Credentials (works on GCP)
        # or explicit credentials file
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if creds_path:
            cred = credentials.Certificate(creds_path)
            logger.info(
                "Firebase Admin SDK: initializing with service account from %s",
                creds_path,
            )
        else:
            cred = credentials.ApplicationDefault()
            logger.info("Firebase Admin SDK: initializing with Application Default Credentials")

        gcp_project = os.environ.get("NEXT_PUBLIC_FIREBASE_PROJECT_ID") or os.environ.get(
            "GCP_PROJECT", ""
        )

        init_options: dict[str, str] = {}
        if gcp_project:
            init_options["projectId"] = gcp_project

        _firebase_app = firebase_admin.initialize_app(cred, init_options)
        _firebase_auth = fb_auth
        logger.info(
            "Firebase Admin SDK initialized successfully (project: %s)",
            gcp_project or "auto-detect",
        )
        return True

    except ImportError:
        logger.info(
            "firebase-admin package not installed. "
            "Firebase ID token verification is disabled. "
            "Install with: pip install firebase-admin"
        )
        return False

    except Exception as exc:
        logger.warning(
            "Firebase Admin SDK initialization failed: %s. "
            "Firebase ID token verification is disabled. "
            "Static token authentication will be used as fallback.",
            exc,
        )
        return False


def verify_firebase_id_token(id_token: str) -> FirebaseUserInfo | None:
    """Verify a Firebase ID token and return user information.

    Args:
        id_token: The Firebase ID token from the frontend
            (obtained via ``firebase.auth().currentUser.getIdToken()``).

    Returns:
        A FirebaseUserInfo dict with uid, email, name, and picture
        on successful verification. Returns None if:
        - Firebase Admin SDK is not available/initialized
        - The token is invalid, expired, or revoked
    """
    if not _ensure_initialized() or _firebase_auth is None:
        return None

    try:
        decoded = _firebase_auth.verify_id_token(id_token, check_revoked=True)

        return FirebaseUserInfo(
            uid=decoded.get("uid", ""),
            email=decoded.get("email", ""),
            name=decoded.get("name", decoded.get("email", "")),
            picture=decoded.get("picture", ""),
        )

    except _firebase_auth.ExpiredIdTokenError:
        logger.debug("Firebase ID token expired")
        return None

    except _firebase_auth.RevokedIdTokenError:
        logger.warning("Firebase ID token has been revoked")
        return None

    except _firebase_auth.InvalidIdTokenError:
        logger.debug("Invalid Firebase ID token")
        return None

    except Exception as exc:
        logger.warning("Firebase ID token verification failed: %s", exc)
        return None


def is_firebase_available() -> bool:
    """Check whether Firebase Admin SDK is available and initialized."""
    return _ensure_initialized()
