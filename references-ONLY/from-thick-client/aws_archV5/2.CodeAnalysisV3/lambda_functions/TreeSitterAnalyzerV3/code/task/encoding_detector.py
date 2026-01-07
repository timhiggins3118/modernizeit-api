"""
Encoding Detection for Mainframe Files

Purpose: Auto-detect file encoding (UTF-8, latin-1, EBCDIC variants)
Strategy: Try each encoding, measure printable character ratio, pick best

Date: November 3, 2025
Version: V3.0
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Encoding probe order (from most common to least)
ENCODING_PROBE_ORDER = [
    'utf-8',
    'latin-1',
    'cp037',    # EBCDIC US
    'cp1047',   # EBCDIC Latin-1
    'cp500',    # EBCDIC International
]


def detect_encoding(file_bytes: bytes) -> str:
    """
    Detect the most likely encoding for a file

    Args:
        file_bytes: Raw bytes from file

    Returns:
        Detected encoding name (e.g., 'utf-8', 'cp037')
    """
    best_encoding = 'latin-1'  # Safe fallback
    best_score = 0.0

    for encoding in ENCODING_PROBE_ORDER:
        try:
            # Try to decode
            decoded = file_bytes.decode(encoding)

            # Calculate printable character ratio
            score = calculate_printable_ratio(decoded)

            logger.debug(f"Encoding {encoding}: score={score:.3f}")

            if score > best_score:
                best_score = score
                best_encoding = encoding

            # If we get a very high score, stop early
            if score > 0.95:
                logger.info(f"Detected encoding: {encoding} (score={score:.3f})")
                return encoding

        except (UnicodeDecodeError, LookupError):
            # This encoding doesn't work
            logger.debug(f"Encoding {encoding} failed to decode")
            continue

    logger.info(f"Best encoding detected: {best_encoding} (score={best_score:.3f})")
    return best_encoding


def calculate_printable_ratio(text: str) -> float:
    """
    Calculate ratio of printable characters to total characters

    Args:
        text: Decoded text string

    Returns:
        Ratio from 0.0 to 1.0
    """
    if len(text) == 0:
        return 0.0

    printable_count = 0
    for char in text:
        # Count as printable if:
        # - Alphanumeric
        # - Common punctuation
        # - Whitespace (space, tab, newline)
        if char.isalnum() or char.isspace() or char in '.,;:!?()[]{}"\'-_=+/*<>@#$%&|\\':
            printable_count += 1

    return printable_count / len(text)


def detect_encoding_with_confidence(file_bytes: bytes) -> Tuple[str, float]:
    """
    Detect encoding and return confidence score

    Args:
        file_bytes: Raw bytes from file

    Returns:
        Tuple of (encoding_name, confidence_score)
    """
    best_encoding = 'latin-1'
    best_score = 0.0

    for encoding in ENCODING_PROBE_ORDER:
        try:
            decoded = file_bytes.decode(encoding)
            score = calculate_printable_ratio(decoded)

            if score > best_score:
                best_score = score
                best_encoding = encoding

            if score > 0.95:
                return encoding, score

        except (UnicodeDecodeError, LookupError):
            continue

    return best_encoding, best_score


def is_likely_ebcdic(file_bytes: bytes) -> bool:
    """
    Quick check if file is likely EBCDIC encoded

    Args:
        file_bytes: Raw bytes from file

    Returns:
        True if likely EBCDIC
    """
    # Try UTF-8 first
    try:
        decoded = file_bytes.decode('utf-8')
        ratio = calculate_printable_ratio(decoded)

        # If UTF-8 works well, it's not EBCDIC
        if ratio > 0.85:
            return False
    except UnicodeDecodeError:
        pass

    # Try EBCDIC
    try:
        decoded = file_bytes.decode('cp037')
        ratio = calculate_printable_ratio(decoded)

        # If EBCDIC works better, it's likely EBCDIC
        if ratio > 0.70:
            return True
    except (UnicodeDecodeError, LookupError):
        pass

    return False
