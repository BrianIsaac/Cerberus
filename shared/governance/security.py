"""Security validation for AI agent inputs and outputs.

This module provides the SecurityValidator class for detecting prompt injection
attempts, PII in inputs/outputs, and other security concerns.
"""

import re
from dataclasses import dataclass
from typing import NamedTuple

import structlog
from datadog import statsd

from shared.governance.constants import (
    GOVERNANCE_DEFAULTS,
    EscalationReason,
    GovernanceMetrics,
    GovernanceTags,
)
from shared.observability import build_tags, emit_quality_score

logger = structlog.get_logger()


class ValidationResult(NamedTuple):
    """Result of input/output validation.

    Attributes:
        is_valid: Whether the validation passed.
        reason: EscalationReason if validation failed, None otherwise.
        message: Human-readable error message if validation failed.
        detected_items: List of detected patterns or PII types.
    """

    is_valid: bool
    reason: EscalationReason | None
    message: str | None
    detected_items: list[str]


# Prompt injection patterns that may indicate malicious attempts
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?prior\s+instructions",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"act\s+as\s+if\s+you\s+are",
    r"pretend\s+you\s+are",
    r"you\s+are\s+now",
    r"new\s+instructions:",
    r"system\s+prompt:",
    r"<\s*system\s*>",
    r"\[\s*system\s*\]",
    r"jailbreak",
    r"DAN\s+mode",
    r"developer\s+mode",
    r"override\s+(system|previous)",
    r"do\s+anything\s+now",
]

# PII patterns with type labels for detection and redaction
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "ssn": r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",
    "credit_card": r"\b(?:\d{4}[-.\s]?){3}\d{4}\b",
    "api_key_openai": r"\bsk-[a-zA-Z0-9]{48}\b",
    "api_key_datadog": r"\bdd[a-z]{1,2}_[a-zA-Z0-9]{32,}\b",
}


@dataclass
class SecurityValidator:
    """Validates inputs and outputs for security concerns.

    This class provides comprehensive security validation including:
    - Input length validation
    - Prompt injection detection
    - PII detection (with optional blocking)
    - Output PII validation

    Attributes:
        service: Service name for metrics tagging.
        agent_type: Agent type for metrics tagging.
        max_input_length: Maximum allowed input length in characters.
        block_on_pii: Whether to block requests containing PII.

    Example:
        validator = SecurityValidator("my-agent", "triage")
        result = validator.validate_input(user_query)
        if not result.is_valid:
            return escalation.escalate(result.reason, result.message)
    """

    service: str
    agent_type: str
    max_input_length: int = GOVERNANCE_DEFAULTS.max_input_length
    block_on_pii: bool = False

    def _emit_security_metric(self, check_type: str, passed: bool) -> None:
        """Emit security check metric.

        Args:
            check_type: Type of security check performed.
            passed: Whether the check passed.
        """
        result = "passed" if passed else "failed"
        tags = build_tags(
            self.service,
            self.agent_type,
            [
                f"{GovernanceTags.CHECK_TYPE}:{check_type}",
                f"{GovernanceTags.RESULT}:{result}",
            ],
        )
        statsd.increment(GovernanceMetrics.SECURITY_CHECK, tags=tags)

    def _check_prompt_injection(self, text: str) -> list[str]:
        """Check for prompt injection attempts.

        Args:
            text: Text to check for injection patterns.

        Returns:
            List of detected injection patterns.
        """
        detected = []
        text_lower = text.lower()
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                detected.append(pattern)
        return detected

    def _check_pii(self, text: str) -> dict[str, list[str]]:
        """Check for PII in text.

        Args:
            text: Text to check for PII patterns.

        Returns:
            Dictionary mapping PII types to lists of matches.
        """
        detected = {}
        for pii_type, pattern in PII_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                detected[pii_type] = matches
        return detected

    def validate_input(self, text: str) -> ValidationResult:
        """Validate user input for security concerns.

        Performs the following checks in order:
        1. Input length validation
        2. Empty input check
        3. Prompt injection detection
        4. PII detection (blocks if block_on_pii is True)

        Args:
            text: User input text to validate.

        Returns:
            ValidationResult with validation status and details.
        """
        detected_items: list[str] = []

        # Length check
        if len(text) > self.max_input_length:
            self._emit_security_metric("length", False)
            return ValidationResult(
                is_valid=False,
                reason=EscalationReason.SECURITY_VIOLATION,
                message=f"Input exceeds maximum length of {self.max_input_length} characters",
                detected_items=[],
            )

        # Empty check
        if not text or not text.strip():
            self._emit_security_metric("empty", False)
            return ValidationResult(
                is_valid=False,
                reason=EscalationReason.SECURITY_VIOLATION,
                message="Input cannot be empty",
                detected_items=[],
            )

        # Prompt injection check
        injection_patterns = self._check_prompt_injection(text)
        if injection_patterns:
            self._emit_security_metric("prompt_injection", False)
            logger.warning(
                "Prompt injection detected",
                service=self.service,
                patterns=injection_patterns,
                input_preview=text[:100],
            )
            emit_quality_score(
                self.service,
                self.agent_type,
                1.0,
                "prompt_injection_detected",
            )
            return ValidationResult(
                is_valid=False,
                reason=EscalationReason.PROMPT_INJECTION,
                message="Potential prompt injection detected",
                detected_items=injection_patterns,
            )

        # PII check
        pii_detected = self._check_pii(text)
        if pii_detected:
            self._emit_security_metric("pii", False)
            pii_types = list(pii_detected.keys())
            logger.warning(
                "PII detected in input",
                service=self.service,
                pii_types=pii_types,
            )
            emit_quality_score(
                self.service,
                self.agent_type,
                float(len(pii_types)),
                "pii_detected",
            )
            detected_items.extend(pii_types)

            if self.block_on_pii:
                return ValidationResult(
                    is_valid=False,
                    reason=EscalationReason.PII_DETECTED,
                    message=f"PII detected: {', '.join(pii_types)}",
                    detected_items=detected_items,
                )

        self._emit_security_metric("input", True)
        return ValidationResult(
            is_valid=True,
            reason=None,
            message=None,
            detected_items=detected_items,
        )

    def validate_output(self, text: str) -> ValidationResult:
        """Validate agent output for PII leakage.

        Args:
            text: Agent output text to validate.

        Returns:
            ValidationResult with validation status and details.
        """
        pii_detected = self._check_pii(text)
        if pii_detected:
            self._emit_security_metric("output_pii", False)
            pii_types = list(pii_detected.keys())
            logger.warning(
                "PII detected in output",
                service=self.service,
                pii_types=pii_types,
            )
            emit_quality_score(
                self.service,
                self.agent_type,
                float(len(pii_types)),
                "pii_in_output",
            )
            return ValidationResult(
                is_valid=False,
                reason=EscalationReason.PII_DETECTED,
                message=f"PII detected in output: {', '.join(pii_types)}",
                detected_items=pii_types,
            )

        self._emit_security_metric("output", True)
        return ValidationResult(
            is_valid=True,
            reason=None,
            message=None,
            detected_items=[],
        )

    def redact_pii(self, text: str) -> str:
        """Redact PII from text.

        Replaces detected PII patterns with type-specific redaction markers.

        Args:
            text: Text containing potential PII.

        Returns:
            Text with PII redacted.
        """
        result = text
        for pii_type, pattern in PII_PATTERNS.items():
            result = re.sub(
                pattern,
                f"[{pii_type.upper()}_REDACTED]",
                result,
                flags=re.IGNORECASE,
            )
        return result

    def sanitise_for_logging(self, text: str, max_length: int = 200) -> str:
        """Sanitise text for safe logging.

        Args:
            text: Text to sanitise.
            max_length: Maximum length of output.

        Returns:
            Sanitised text safe for logging.
        """
        if len(text) > max_length:
            text = text[:max_length] + "..."
        # Remove potential control characters
        text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
        return text
