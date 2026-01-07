"""
Repository layer for data persistence.

Provides abstract interfaces that can be implemented for different backends:
- MongoDB (current)
- DynamoDB (future)
- Other (future)

Each flow has its own collection:
- code_analysis: Code Analysis artifacts
- code_refactor: Code Refactor artifacts
- dependency_mapper: Dependency Mapper artifacts
- monolith_identifier: Monolith Identifier artifacts
- data_analysis: Data Analysis artifacts
- discovery: Discovery artifacts
- architecture: Architecture Recommender artifacts

Usage:
    from db.repositories import code_analysis_repo

    # Save artifact (works with any backend)
    code_analysis_repo.save_artifact(...)

    # Query artifacts
    artifacts = code_analysis_repo.get_artifacts(...)

For synchronous code (runners), import save_artifact_sync directly:
    from db.repositories.code_analysis_repo import save_artifact_sync
"""

from db.repositories.code_analysis_repo import CodeAnalysisRepository
from db.repositories.code_refactor_repo import CodeRefactorRepository

# Singleton instances - swap implementations here if backend changes
code_analysis_repo = CodeAnalysisRepository()
code_refactor_repo = CodeRefactorRepository()

__all__ = [
    "code_analysis_repo",
    "CodeAnalysisRepository",
    "code_refactor_repo",
    "CodeRefactorRepository",
]
