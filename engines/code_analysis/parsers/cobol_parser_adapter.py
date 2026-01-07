"""
COBOL Parser Adapter - Tree-Sitter COBOL Parser Wrapper

Minimal adapter to load and use the tree-sitter COBOL grammar.
Uses the pre-built cobol.so from the main ModernizeIT project.

Date: December 12, 2025
"""

import ctypes
import os
from pathlib import Path
from typing import Optional, Tuple

try:
    from tree_sitter import Language, Parser
except ImportError:
    raise ImportError("tree-sitter not installed. Run: pip install tree-sitter")


# Path to the pre-built COBOL grammar (relative to this module)
_THIS_DIR = Path(__file__).resolve().parent
COBOL_LIB_PATH = str(_THIS_DIR.parent / "grammar" / "cobol.so")

if not os.path.exists(COBOL_LIB_PATH):
    raise FileNotFoundError(
        f"COBOL grammar library not found at {COBOL_LIB_PATH}. "
        f"Make sure cobol.so is in engines/code_analysis/grammar/"
    )


def load_cobol_language() -> Language:
    """
    Load the COBOL language grammar for tree-sitter.

    Uses tree-sitter 0.25.2+ API which requires ctypes to load .so files.

    Returns:
        Language object for COBOL parsing

    Raises:
        FileNotFoundError: If the grammar file doesn't exist
        RuntimeError: If the grammar fails to load
    """
    try:
        # tree-sitter 0.25.2+ API: Load .so using ctypes
        lib = ctypes.CDLL(COBOL_LIB_PATH)

        # Get the tree_sitter_COBOL function (note: uppercase COBOL)
        tree_sitter_COBOL = lib.tree_sitter_COBOL
        tree_sitter_COBOL.restype = ctypes.c_void_p
        lang_ptr = tree_sitter_COBOL()

        # Create Language object from pointer
        return Language(lang_ptr)

    except Exception as e:
        raise RuntimeError(f"Failed to load COBOL grammar: {e}")


def create_parser() -> Parser:
    """
    Create a tree-sitter parser configured for COBOL.

    Returns:
        Parser object ready to parse COBOL source code
    """
    cobol_lang = load_cobol_language()
    parser = Parser()
    parser.language = cobol_lang  # tree-sitter 0.25.2+ API
    return parser


def parse_cobol_source(source_code: bytes) -> "Tree":
    """
    Parse COBOL source code and return the parse tree.

    Args:
        source_code: COBOL source as UTF-8 bytes

    Returns:
        tree-sitter Tree object
    """
    parser = create_parser()
    return parser.parse(source_code)


def read_cobol_file_with_encoding(file_path: Path) -> Tuple[bytes, str]:
    """
    Read a COBOL file with encoding detection.

    Tries multiple encodings and returns UTF-8 bytes for tree-sitter.

    Args:
        file_path: Path to the COBOL file

    Returns:
        Tuple of (UTF-8 bytes, encoding used)

    Raises:
        ValueError: If file cannot be read with any encoding
    """
    # Read raw bytes
    with open(file_path, 'rb') as f:
        raw_bytes = f.read()

    # COBOL indicators to verify content
    cobol_indicators = [
        b'IDENTIFICATION DIVISION',
        b'PROCEDURE DIVISION',
        b'DATA DIVISION',
        b'WORKING-STORAGE',
        b'PROGRAM-ID',
        b'PERFORM',
        b'MOVE',
    ]

    # Try encodings in order of likelihood
    encodings_to_try = ["utf-8", "latin-1", "cp037", "cp1252"]

    for encoding in encodings_to_try:
        try:
            decoded = raw_bytes.decode(encoding)
            content_upper = decoded.upper().encode('utf-8')

            # Check if it looks like COBOL
            matches = sum(1 for ind in cobol_indicators if ind in content_upper)
            if matches >= 2:
                # Re-encode as UTF-8 for tree-sitter
                return decoded.encode('utf-8'), encoding

        except (UnicodeDecodeError, LookupError):
            continue

    # Fallback: try latin-1 which handles all byte values
    try:
        decoded = raw_bytes.decode('latin-1')
        return decoded.encode('utf-8'), 'latin-1'
    except Exception:
        pass

    raise ValueError(f"Cannot read file '{file_path}' with any supported encoding")


def parse_cobol_file(file_path: Path) -> Tuple["Tree", bytes, str]:
    """
    Parse a COBOL file and return the tree, source, and encoding.

    Args:
        file_path: Path to the COBOL file

    Returns:
        Tuple of (Tree, source_bytes, encoding_used)
    """
    source_bytes, encoding = read_cobol_file_with_encoding(file_path)
    tree = parse_cobol_source(source_bytes)
    return tree, source_bytes, encoding
