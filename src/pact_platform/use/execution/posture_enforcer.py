# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Posture-specific execution enforcement — applies trust posture rules to actions.

Each trust posture level imposes different constraints on how actions are handled:

- PSEUDO_AGENT: Block ALL actions before any LLM call
- SUPERVISED: Place ALL actions in HELD queue regardless of constraint state
- SHARED_PLANNING: Planning actions auto-approve; consequential actions HELD
- CONTINUOUS_INSIGHT: Within-envelope auto-approve; boundary-crossing HELD
- DELEGATED: Within-envelope auto-approve; out-of-envelope BLOCKED (not HELD)

The posture is read from the trust record at action time (not cached at startup).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

from pact_platform.build.config.schema import TrustPostureLevel, VerificationLevel
from pact_platform.trust._compat import TrustPosture

logger = logging.getLogger(__name__)

# Consequential action keywords — actions containing these words require
# human approval at SHARED_PLANNING posture level.
_CONSEQUENTIAL_KEYWORDS: frozenset[str] = frozenset(
    {
        "write",
        "send",
        "execute",
        "deploy",
        "delete",
        "remove",
        "create",
        "update",
        "modify",
        "publish",
        "commit",
        "push",
        "release",
        "transfer",
        "approve",
        "revoke",
    }
)

# Planning action keywords — actions containing these words are considered
# safe planning operations at SHARED_PLANNING posture level.
_PLANNING_KEYWORDS: frozenset[str] = frozenset(
    {
        "analyze",
        "draft",
        "reason",
        "plan",
        "review",
        "summarize",
        "read",
        "research",
        "evaluate",
        "assess",
        "compare",
        "list",
        "search",
        "inspect",
        "check",
        "describe",
        "outline",
        "think",
        "consider",
    }
)


@dataclass(frozen=True)
class PostureCheckResult:
    """Result of a posture enforcement check.

    Attributes:
        level: The verification level after posture enforcement.
        reason: Human-readable explanation of the posture decision.
    """

    level: VerificationLevel
    reason: str


class PostureEnforcer:
    """Enforces trust posture rules on agent actions.

    The enforcer takes the current verification level (from constraint
    middleware / gradient engine) and applies posture-specific escalation
    or blocking rules. It reads the posture from the TrustPosture object
    at each call, never caching posture state.
    """

    def check_posture(
        self,
        *,
        posture: TrustPosture,
        action: str,
        verification_level: VerificationLevel,
    ) -> PostureCheckResult:
        """Apply posture-specific enforcement to an action.

        The posture is read from the provided TrustPosture object at call
        time, ensuring posture changes are reflected immediately.

        Args:
            posture: The agent's current TrustPosture (read at action time).
            action: The action being evaluated.
            verification_level: The verification level from constraint
                middleware / gradient engine.

        Returns:
            PostureCheckResult with the potentially escalated/modified
            verification level and reason.

        Raises:
            ValueError: If posture has no current_level set.
        """
        level = posture.current_level

        if level == TrustPostureLevel.PSEUDO_AGENT:
            return self._enforce_pseudo_agent(action)
        elif level == TrustPostureLevel.SUPERVISED:
            return self._enforce_supervised(action, verification_level)
        elif level == TrustPostureLevel.SHARED_PLANNING:
            return self._enforce_shared_planning(action, verification_level)
        elif level == TrustPostureLevel.CONTINUOUS_INSIGHT:
            return self._enforce_continuous_insight(action, verification_level)
        elif level == TrustPostureLevel.DELEGATED:
            return self._enforce_delegated(action, verification_level)
        else:
            # Fail-closed: unknown posture level blocks the action
            logger.error(
                "Unknown posture level '%s' for action '%s' — blocking (fail-closed)",
                level,
                action,
            )
            return PostureCheckResult(
                level=VerificationLevel.BLOCKED,
                reason=f"Unknown posture level '{level}' — blocked (fail-closed)",
            )

    def _enforce_pseudo_agent(self, action: str) -> PostureCheckResult:
        """PSEUDO_AGENT: Block ALL actions before any LLM call."""
        logger.info(
            "PSEUDO_AGENT: blocking action '%s' — no action authority",
            action,
        )
        return PostureCheckResult(
            level=VerificationLevel.BLOCKED,
            reason="PSEUDO_AGENT posture: all actions are blocked — agent has no action authority",
        )

    def _enforce_supervised(
        self,
        action: str,
        verification_level: VerificationLevel,
    ) -> PostureCheckResult:
        """SUPERVISED: Place ALL actions in HELD queue regardless of constraint state.

        Exception: BLOCKED stays BLOCKED (cannot downgrade a block to a hold).
        """
        if verification_level == VerificationLevel.BLOCKED:
            return PostureCheckResult(
                level=VerificationLevel.BLOCKED,
                reason="SUPERVISED posture: action was already BLOCKED by constraints",
            )

        logger.info(
            "SUPERVISED: escalating action '%s' from %s to HELD",
            action,
            verification_level.value,
        )
        return PostureCheckResult(
            level=VerificationLevel.HELD,
            reason=(
                f"SUPERVISED posture: all actions require human approval "
                f"(original level: {verification_level.value})"
            ),
        )

    def _enforce_shared_planning(
        self,
        action: str,
        verification_level: VerificationLevel,
    ) -> PostureCheckResult:
        """SHARED_PLANNING: Planning actions auto-approve; consequential actions HELD.

        - Planning: reasoning, drafting, analyzing -> preserve original level
        - Consequential: write, send, execute, deploy -> escalate to HELD
        - BLOCKED: stays BLOCKED
        """
        if verification_level == VerificationLevel.BLOCKED:
            return PostureCheckResult(
                level=VerificationLevel.BLOCKED,
                reason="SHARED_PLANNING posture: action was already BLOCKED by constraints",
            )

        if self._is_consequential_action(action):
            logger.info(
                "SHARED_PLANNING: consequential action '%s' escalated to HELD",
                action,
            )
            return PostureCheckResult(
                level=VerificationLevel.HELD,
                reason=(
                    f"SHARED_PLANNING posture: consequential action '{action}' "
                    f"requires human approval"
                ),
            )

        # Planning action — preserve original level
        return PostureCheckResult(
            level=verification_level,
            reason=(
                f"SHARED_PLANNING posture: planning action '{action}' "
                f"auto-approved (level: {verification_level.value})"
            ),
        )

    def _enforce_continuous_insight(
        self,
        action: str,
        verification_level: VerificationLevel,
    ) -> PostureCheckResult:
        """CONTINUOUS_INSIGHT: Within-envelope auto-approve; boundary-crossing HELD.

        - AUTO_APPROVED: pass through (within envelope)
        - FLAGGED: escalate to HELD (near boundary)
        - HELD: stays HELD (already queued)
        - BLOCKED: stays BLOCKED
        """
        if verification_level == VerificationLevel.BLOCKED:
            return PostureCheckResult(
                level=VerificationLevel.BLOCKED,
                reason="CONTINUOUS_INSIGHT posture: action was already BLOCKED by constraints",
            )

        if verification_level == VerificationLevel.AUTO_APPROVED:
            return PostureCheckResult(
                level=VerificationLevel.AUTO_APPROVED,
                reason=(
                    f"CONTINUOUS_INSIGHT posture: action '{action}' is within "
                    f"constraint envelope — auto-approved"
                ),
            )

        # FLAGGED or HELD — escalate to HELD (boundary crossing)
        if verification_level == VerificationLevel.FLAGGED:
            logger.info(
                "CONTINUOUS_INSIGHT: boundary-crossing action '%s' escalated to HELD",
                action,
            )
            return PostureCheckResult(
                level=VerificationLevel.HELD,
                reason=(
                    f"CONTINUOUS_INSIGHT posture: action '{action}' is near "
                    f"constraint boundary — escalated to HELD"
                ),
            )

        # HELD stays HELD
        return PostureCheckResult(
            level=VerificationLevel.HELD,
            reason=(f"CONTINUOUS_INSIGHT posture: action '{action}' was HELD by constraints"),
        )

    def _enforce_delegated(
        self,
        action: str,
        verification_level: VerificationLevel,
    ) -> PostureCheckResult:
        """DELEGATED: Within-envelope auto-approve; out-of-envelope BLOCKED (not HELD).

        Key difference from CONTINUOUS_INSIGHT: DELEGATED agents are trusted
        to operate autonomously within their envelope, but anything outside
        the envelope is immediately BLOCKED rather than queued for approval.

        - AUTO_APPROVED: pass through (within envelope)
        - FLAGGED: BLOCKED (out of envelope)
        - HELD: BLOCKED (out of envelope)
        - BLOCKED: stays BLOCKED
        """
        if verification_level == VerificationLevel.AUTO_APPROVED:
            return PostureCheckResult(
                level=VerificationLevel.AUTO_APPROVED,
                reason=(
                    f"DELEGATED posture: action '{action}' is within "
                    f"constraint envelope — auto-approved"
                ),
            )

        # Everything else is BLOCKED (not HELD)
        logger.info(
            "DELEGATED: out-of-envelope action '%s' BLOCKED (was %s)",
            action,
            verification_level.value,
        )
        return PostureCheckResult(
            level=VerificationLevel.BLOCKED,
            reason=(
                f"DELEGATED posture: action '{action}' is outside constraint "
                f"envelope — BLOCKED (original level: {verification_level.value})"
            ),
        )

    # RT12-008: Cyrillic-to-Latin transliteration map for common homoglyphs
    _HOMOGLYPH_MAP: dict[str, str] = {
        # --- Cyrillic homoglyphs ---
        "\u0430": "a",  # Cyrillic а → Latin a
        "\u0441": "c",  # Cyrillic с → Latin c
        "\u0435": "e",  # Cyrillic е → Latin e
        "\u043e": "o",  # Cyrillic о → Latin o
        "\u0440": "p",  # Cyrillic р → Latin p
        "\u0445": "x",  # Cyrillic х → Latin x
        "\u0443": "y",  # Cyrillic у → Latin y
        "\u0456": "i",  # Cyrillic і → Latin i
        "\u0455": "s",  # Cyrillic ѕ → Latin s
        "\u04bb": "h",  # Cyrillic һ → Latin h
        "\u0410": "A",  # Cyrillic А → Latin A
        "\u0421": "C",  # Cyrillic С → Latin C
        "\u0415": "E",  # Cyrillic Е → Latin E
        "\u041e": "O",  # Cyrillic О → Latin O
        "\u0420": "P",  # Cyrillic Р → Latin P
        "\u0425": "X",  # Cyrillic Х → Latin X
        "\u0423": "Y",  # Cyrillic У → Latin Y
        "\u0406": "I",  # Cyrillic І → Latin I
        "\u0405": "S",  # Cyrillic Ѕ → Latin S
        "\u041d": "H",  # Cyrillic Н → Latin H
        "\u0412": "B",  # Cyrillic В → Latin B
        "\u041c": "M",  # Cyrillic М → Latin M
        "\u0422": "T",  # Cyrillic Т → Latin T
        # --- RT13-H6: Greek homoglyphs ---
        "\u03bf": "o",  # Greek omicron ο → Latin o
        "\u039f": "O",  # Greek Omicron Ο → Latin O
        "\u03b1": "a",  # Greek alpha α → Latin a (NFKD doesn't collapse)
        "\u0391": "A",  # Greek Alpha Α → Latin A
        "\u03b5": "e",  # Greek epsilon ε → Latin e
        "\u0395": "E",  # Greek Epsilon Ε → Latin E
        "\u03b9": "i",  # Greek iota ι → Latin i
        "\u0399": "I",  # Greek Iota Ι → Latin I
        "\u03ba": "k",  # Greek kappa κ → Latin k
        "\u039a": "K",  # Greek Kappa Κ → Latin K
        "\u03c4": "t",  # Greek tau τ → Latin t
        "\u03a4": "T",  # Greek Tau Τ → Latin T
        "\u03c5": "u",  # Greek upsilon υ → Latin u
        "\u03a5": "Y",  # Greek Upsilon Υ → Latin Y
        "\u03c7": "x",  # Greek chi χ → Latin x
        "\u03a7": "X",  # Greek Chi Χ → Latin X
    }
    # Backward compat alias
    _CYRILLIC_HOMOGLYPHS = _HOMOGLYPH_MAP

    @classmethod
    def _normalize_action_text(cls, text: str) -> str:
        """Normalize action text to defeat keyword bypass attacks.

        Applies four normalization layers:
        1. Homoglyph transliteration — maps Cyrillic and Greek visual
           homoglyphs to Latin equivalents that NFKD does not collapse.
        2. Unicode NFKD decomposition — collapses compatibility characters
           to their ASCII equivalents.
        3. casefold() — locale-aware lowercasing (handles edge cases
           like German sharp-s that ``lower()`` misses).
        4. Strip non-alphanumeric characters — removes hyphens, zero-
           width joiners, and other separators that can split keywords.

        The result is a lowercase ASCII-only string suitable for
        keyword matching.
        """
        # Step 1: Transliterate homoglyphs (Cyrillic + Greek) to Latin equivalents
        text = "".join(cls._HOMOGLYPH_MAP.get(ch, ch) for ch in text)
        # Step 2: NFKD decomposition
        text = unicodedata.normalize("NFKD", text)
        # Step 3: casefold (locale-aware lowercasing)
        text = text.casefold()
        # Step 4: strip to ASCII alphanumeric + spaces only
        text = re.sub(r"[^a-z0-9 ]", "", text)
        return text

    def _is_consequential_action(self, action: str) -> bool:
        """Determine if an action is consequential (has side effects).

        Checks if the normalized action string contains any consequential
        keyword, either as a whole word or as a substring. This is
        deliberately conservative — if in doubt, the action is treated
        as consequential (fail-closed).

        Normalization defeats common bypass techniques:
        - CamelCase: "executeCommand" → "executecommand" (contains "execute")
        - Hyphenation: "exe-cute" → "execute" (contains "execute")
        - Unicode homoglyphs: Cyrillic "е" → Latin "e" via NFKD
        """
        normalized = self._normalize_action_text(action)

        # Check if any keyword appears as a substring in the normalized text
        for keyword in _CONSEQUENTIAL_KEYWORDS:
            if keyword in normalized:
                return True

        return False
