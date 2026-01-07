"""
Architecture Recommender Engine

Evidence-based AWS architecture recommendations using 5 input sources:
1. Discovery - Business processes, ROI, integration points
2. Data Analysis - ERD, relationships, data lineage
3. Code Analysis - COBOL complexity, static analysis
4. Code Refactor - Modernization patterns, recipes
5. Java Code - Generated Java from Code Analysis

Key improvements over reference implementation:
- Every recommendation has evidence
- Cross-validation between sources
- Conflicts are warnings (not blockers)
- Alternatives provided for each recommendation
- Full traceability from Java to AWS
"""

from engines.architecture.runner import (
    ArchitectureRunner,
    run_architecture_recommender,
)

__all__ = [
    'ArchitectureRunner',
    'run_architecture_recommender',
]
