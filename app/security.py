"""Security validation for ops assistant input processing."""

import re
from typing import Tuple

import structlog

logger = structlog.get_logger()

# Patterns that may indicate prompt injection attempts
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+(instructions?|prompts?)",
    r"disregard\s+(previous|above|all)\s+(instructions?|prompts?)",
    r"forget\s+(previous|above|all)\s+(instructions?|prompts?)",
    r"you\s+are\s+now\s+a",
    r"act\s+as\s+if\s+you\s+are",
    r"pretend\s+(to\s+be|you\s+are)",
    r"new\s+instructions?:",
    r"system\s*:\s*you\s+are",
    r"<\s*system\s*>",
    r"\[\s*system\s*\]",
    r"override\s+(system|previous)",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"dan\s+mode",
]

# Patterns for potential PII (simplified - production should use more robust detection)
PII_PATTERNS = [
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "email"),
    (r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "phone_number"),
    (r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b", "ssn"),
    (r"\b(?:\d{4}[-.\s]?){3}\d{4}\b", "credit_card"),
    (r"\bsk-[a-zA-Z0-9]{48}\b", "api_key_openai"),
    (r"\bdd[a-z]{1,2}_[a-zA-Z0-9]{32,}\b", "api_key_datadog"),
]

# Maximum input length to prevent DoS
MAX_INPUT_LENGTH = 10000


def check_prompt_injection(text: str) -> Tuple[bool, str | None]:
    """Check for potential prompt injection attempts.

    Args:
        text: Input text to validate

    Returns:
        Tuple of (is_safe, detected_pattern). If safe, detected_pattern is None.
    """
    text_lower = text.lower()

    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            logger.warning(
                "prompt_injection_detected",
                pattern=pattern,
                input_preview=text[:100],
            )
            return False, pattern

    return True, None


def check_pii(text: str) -> Tuple[bool, list[str]]:
    """Check for potential PII in input.

    Args:
        text: Input text to validate

    Returns:
        Tuple of (is_clean, detected_pii_types). If clean, detected_pii_types is empty.
    """
    detected = []

    for pattern, pii_type in PII_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            detected.append(pii_type)
            logger.warning(
                "pii_detected",
                pii_type=pii_type,
                input_preview=text[:50] + "...",
            )

    return len(detected) == 0, detected


def validate_input(text: str) -> Tuple[bool, str | None]:
    """Validate user input for security issues.

    Performs the following checks:
    1. Input length validation
    2. Prompt injection detection
    3. PII detection

    Args:
        text: User input to validate

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
    """
    # Check input length
    if len(text) > MAX_INPUT_LENGTH:
        logger.warning(
            "input_too_long",
            length=len(text),
            max_length=MAX_INPUT_LENGTH,
        )
        return False, f"Input exceeds maximum length of {MAX_INPUT_LENGTH} characters"

    # Check for empty input
    if not text or not text.strip():
        return False, "Input cannot be empty"

    # Check for prompt injection
    is_safe, pattern = check_prompt_injection(text)
    if not is_safe:
        return False, "Potential prompt injection detected"

    # Check for PII (log warning but don't block - let Datadog Sensitive Data Scanner handle)
    is_clean, pii_types = check_pii(text)
    if not is_clean:
        logger.info(
            "pii_warning",
            pii_types=pii_types,
            message="PII detected in input - will be handled by Sensitive Data Scanner",
        )

    return True, None


def sanitise_for_logging(text: str, max_length: int = 200) -> str:
    """Sanitise text for safe logging.

    Args:
        text: Text to sanitise
        max_length: Maximum length of output

    Returns:
        Sanitised text safe for logging
    """
    # Truncate
    if len(text) > max_length:
        text = text[:max_length] + "..."

    # Remove potential control characters
    text = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)

    return text
