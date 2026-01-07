"""
Dependency Mapper Engine

Analyzes dependencies in COBOL source code or Java code.
Produces reports for:
- Dependency graph (nodes + edges)
- Coupling metrics (fan-in, fan-out)
- Risk assessment (god programs, single points of failure)
- Microservice boundaries (suggested service groupings)
- Impact analysis (blast radius per program)
"""

from engines.dependency_mapper.runner import run_dependency_mapper

__all__ = ["run_dependency_mapper"]
