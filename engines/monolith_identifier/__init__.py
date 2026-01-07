"""
Monolith Identifier Engine

Analyzes source code to detect monolithic anti-patterns and provides
business capability-driven decomposition recommendations.
"""

from engines.monolith_identifier.runner import run_monolith_identifier

__all__ = ["run_monolith_identifier"]
