#!/usr/bin/env python3
"""
Build tree-sitter COBOL grammar for the current platform.

This script compiles the tree-sitter-cobol grammar into a platform-specific
shared library (.so on Linux, .dylib on macOS).

Usage:
    python3 build_tree_sitter_grammar.py

Requirements:
    - tree-sitter Python package
    - tree-sitter-cobol source in vendor/tree-sitter-cobol/
"""

import os
import sys
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).parent
VENDOR_DIR = SCRIPT_DIR / "vendor" / "tree-sitter-cobol"
GRAMMAR_DIR = SCRIPT_DIR / "engines" / "code_analysis" / "grammar"
OUTPUT_FILE = GRAMMAR_DIR / "cobol.so"

def main():
    print("=" * 60)
    print("BUILDING TREE-SITTER COBOL GRAMMAR")
    print("=" * 60)

    # Verify source exists
    if not VENDOR_DIR.exists():
        print(f"\n❌ ERROR: tree-sitter-cobol source not found at {VENDOR_DIR}")
        print("Please ensure vendor/tree-sitter-cobol/ exists with grammar.js")
        return 1

    grammar_js = VENDOR_DIR / "grammar.js"
    if not grammar_js.exists():
        print(f"\n❌ ERROR: grammar.js not found at {grammar_js}")
        return 1

    print(f"\n✓ Found tree-sitter-cobol source: {VENDOR_DIR}")
    print(f"✓ Output directory: {GRAMMAR_DIR}")

    # Ensure output directory exists
    GRAMMAR_DIR.mkdir(parents=True, exist_ok=True)

    # Build the grammar using gcc directly
    print(f"\n🔨 Building COBOL grammar with gcc...")
    print(f"   Source: {VENDOR_DIR}")
    print(f"   Output: {OUTPUT_FILE}")

    try:
        import subprocess

        # Compile the grammar using gcc
        # This creates a shared library from the parser.c and scanner.c files
        src_dir = VENDOR_DIR / "src"
        parser_c = src_dir / "parser.c"
        scanner_c = src_dir / "scanner.c"

        if not parser_c.exists():
            print(f"\n❌ ERROR: parser.c not found at {parser_c}")
            return 1

        compile_cmd = [
            "gcc",
            "-shared",
            "-fPIC",
            "-I" + str(src_dir),  # Add include path for tree_sitter/parser.h
            "-o", str(OUTPUT_FILE),
            str(parser_c),
        ]

        # Add scanner.c if it exists
        if scanner_c.exists():
            compile_cmd.append(str(scanner_c))

        print(f"\n   Running: {' '.join(compile_cmd)}")
        result = subprocess.run(compile_cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"\n❌ ERROR: Compilation failed")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return 1

        print(f"\n✅ SUCCESS! Grammar built: {OUTPUT_FILE}")
        print(f"   File size: {OUTPUT_FILE.stat().st_size:,} bytes")

        # Test loading it with tree-sitter
        print(f"\n🧪 Testing grammar...")
        try:
            from tree_sitter import Language
            lang = Language(str(OUTPUT_FILE), 'cobol')
            print(f"✅ Grammar loads successfully!")
        except Exception as e:
            print(f"⚠️  Warning: Could not test grammar loading: {e}")
            print(f"   But the .so file was compiled successfully!")

        return 0

    except Exception as e:
        print(f"\n❌ ERROR: Failed to build grammar")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
