"""
Impact Analyzer

Calculates the impact/blast radius for each program.
Determines which programs would be affected if a program changes.
"""

from typing import Any, Dict, List, Set
from collections import defaultdict


class ImpactAnalyzer:
    """
    Analyzes the impact of changes to each program.

    Calculates:
    - Direct dependents (programs that directly depend on this)
    - Indirect dependents (transitive dependencies)
    - Total impact radius
    - Risk level
    """

    # Risk thresholds
    HIGH_IMPACT_THRESHOLD = 10
    MEDIUM_IMPACT_THRESHOLD = 5

    def __init__(self):
        self.impact_map: Dict[str, Dict[str, Any]] = {}

    def analyze(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze impact for all programs in the graph.

        Args:
            graph: Dependency graph with nodes and edges

        Returns:
            Impact analysis for each program
        """
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        if not nodes:
            return self._empty_result()

        # Build reverse adjacency (who depends on this node)
        dependents: Dict[str, Set[str]] = defaultdict(set)
        dependencies: Dict[str, Set[str]] = defaultdict(set)

        for edge in edges:
            source = edge.get("from", "")
            target = edge.get("to", "")
            if source and target:
                dependents[target].add(source)  # source depends on target
                dependencies[source].add(target)  # source has dependency on target

        # Calculate impact for each node
        self.impact_map = {}

        for node in nodes:
            node_id = node["id"]

            # Direct dependents
            direct = list(dependents.get(node_id, set()))

            # Indirect dependents (BFS)
            indirect = self._find_indirect_dependents(node_id, dependents)

            # Programs this calls
            calls = list(dependencies.get(node_id, set()))

            # Calculate impact radius
            total_impact = len(direct) + len(indirect)

            # Determine risk level
            risk_level = self._calculate_risk_level(total_impact)

            # Generate recommendation
            recommendation = self._generate_recommendation(total_impact)

            self.impact_map[node_id] = {
                "program": node_id,
                "direct_dependents": direct,
                "direct_dependents_count": len(direct),
                "indirect_dependents": list(indirect),
                "indirect_dependents_count": len(indirect),
                "total_impact_radius": total_impact,
                "risk_level": risk_level,
                "refactoring_recommendation": recommendation,
                "programs_it_calls": calls,
                "programs_it_calls_count": len(calls)
            }

        # Sort by impact
        sorted_by_impact = sorted(
            self.impact_map.values(),
            key=lambda x: x["total_impact_radius"],
            reverse=True
        )

        # Calculate summary
        high_impact = sum(1 for p in sorted_by_impact if p["risk_level"] == "High")
        medium_impact = sum(1 for p in sorted_by_impact if p["risk_level"] in ("Medium", "Medium-High"))
        low_impact = sum(1 for p in sorted_by_impact if p["risk_level"] == "Low")

        return {
            "program_impact_map": self.impact_map,
            "sorted_by_impact": [
                {"program": p["program"], "impact_radius": p["total_impact_radius"], "risk_level": p["risk_level"]}
                for p in sorted_by_impact[:20]  # Top 20
            ],
            "summary": {
                "total_programs": len(self.impact_map),
                "high_impact_count": high_impact,
                "medium_impact_count": medium_impact,
                "low_impact_count": low_impact,
                "max_impact_radius": sorted_by_impact[0]["total_impact_radius"] if sorted_by_impact else 0
            }
        }

    def _find_indirect_dependents(
        self,
        node_id: str,
        dependents: Dict[str, Set[str]]
    ) -> Set[str]:
        """
        Find all indirect dependents using BFS.

        These are programs that depend on programs that depend on this node.
        """
        indirect: Set[str] = set()
        direct = dependents.get(node_id, set())

        # BFS queue
        queue = list(direct)
        visited = set(direct)
        visited.add(node_id)

        while queue:
            current = queue.pop(0)
            for dependent in dependents.get(current, []):
                if dependent not in visited:
                    visited.add(dependent)
                    indirect.add(dependent)
                    queue.append(dependent)

        return indirect

    def _calculate_risk_level(self, impact_radius: int) -> str:
        """Calculate risk level based on impact radius."""
        if impact_radius >= self.HIGH_IMPACT_THRESHOLD:
            return "High"
        elif impact_radius >= self.MEDIUM_IMPACT_THRESHOLD:
            return "Medium-High" if impact_radius >= 7 else "Medium"
        elif impact_radius > 0:
            return "Low"
        else:
            return "None"

    def _generate_recommendation(self, impact_radius: int) -> str:
        """Generate refactoring recommendation based on impact."""
        if impact_radius >= self.HIGH_IMPACT_THRESHOLD:
            return "Major impact - requires careful planning, staged rollout, and comprehensive testing"
        elif impact_radius >= self.MEDIUM_IMPACT_THRESHOLD:
            return "Significant impact - requires phased approach with extensive testing"
        elif impact_radius > 2:
            return "Moderate impact - requires coordination with dependent teams"
        elif impact_radius > 0:
            return "Low impact - standard testing procedures apply"
        else:
            return "No dependents - safe to modify with normal precautions"

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "program_impact_map": {},
            "sorted_by_impact": [],
            "summary": {
                "total_programs": 0,
                "high_impact_count": 0,
                "medium_impact_count": 0,
                "low_impact_count": 0,
                "max_impact_radius": 0
            }
        }

    def get_critical_programs(self) -> List[Dict[str, Any]]:
        """Get programs with highest impact."""
        return [
            p for p in self.impact_map.values()
            if p["risk_level"] == "High"
        ]

    def get_safe_to_modify(self) -> List[str]:
        """Get programs that are safe to modify (no dependents)."""
        return [
            p["program"] for p in self.impact_map.values()
            if p["total_impact_radius"] == 0
        ]
