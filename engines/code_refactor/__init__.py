"""
Code Refactor Engine

Hybrid (Rules + AI) engine for modernizing generated Java code.

Two-phase architecture:
1. ANALYZE: Detect patterns using rules, then AI interprets for recommendations
2. TRANSFORM: Apply approved changes to create modernized Java

This engine takes output from code_analysis (generated Java) and produces
cleaner, more idiomatic Java that customers would expect.
"""

from engines.code_refactor.runner import run_code_refactor, CodeRefactorResult

__all__ = ["run_code_refactor", "CodeRefactorResult"]
