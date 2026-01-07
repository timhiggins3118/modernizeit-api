"""
Risk Assessor

Identifies high-risk elements in the dependency graph:
- God programs/classes (too many dependencies)
- Single points of failure (many dependents)
- Circular dependencies
- Tight coupling areas
"""

from typing import Any, Dict, List, Set, Tuple


class RiskAssessor:
    """
    Assesses risk based on dependency analysis.
    """

    # Thresholds
    GOD_PROGRAM_FAN_OUT_THRESHOLD = 20  # Fan-out > 20 = god program
    SPOF_FAN_IN_THRESHOLD = 10  # Fan-in > 10 = single point of failure
    TIGHT_COUPLING_THRESHOLD = 0.3

    def __init__(self):
        self.risks: Dict[str, Any] = {}

    def assess(self, graph: Dict[str, Any], coupling_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess risk from dependency graph and coupling metrics.

        Args:
            graph: Dependency graph with nodes and edges
            coupling_metrics: Output from CouplingCalculator

        Returns:
            Risk assessment with categorized issues
        """
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        # Find god programs (high fan-out)
        god_programs = self._find_god_programs(nodes)

        # Find single points of failure (high fan-in)
        spof = self._find_single_points_of_failure(nodes)

        # Find circular dependencies
        circular = self._find_circular_dependencies(edges)

        # Find tight coupling areas
        tight_coupling = self._find_tight_coupling(coupling_metrics)

        # Find shared copybooks/classes (used by many)
        shared = self._find_shared_components(nodes)

        # Calculate summary
        high_risk_count = len([s for s in spof if s["risk_level"] == "High"])
        medium_risk_count = len(god_programs) + len([s for s in spof if s["risk_level"] != "High"])

        self.risks = {
            "circular_dependencies": circular,
            "tight_coupling_areas": tight_coupling,
            "single_points_of_failure": spof,
            "god_programs": god_programs,
            "shared_copybooks": shared,
            "summary": {
                "high_risk_count": high_risk_count,
                "medium_risk_count": medium_risk_count,
                "total_risk_items": len(circular) + len(tight_coupling) + len(spof) + len(god_programs)
            }
        }

        return self.risks

    def _find_god_programs(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find programs with too many outgoing dependencies."""
        god_programs = []

        for node in nodes:
            fan_out = node.get("fan_out", 0)
            if fan_out >= self.GOD_PROGRAM_FAN_OUT_THRESHOLD:
                god_programs.append({
                    "program": node["id"],
                    "fan_out": fan_out,
                    "risk": f"Calls {fan_out} other programs - too many responsibilities",
                    "risk_level": "Medium-High",
                    "recommendation": "Refactor to split responsibilities into smaller, focused programs"
                })

        return sorted(god_programs, key=lambda x: x["fan_out"], reverse=True)

    def _find_single_points_of_failure(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find programs that many others depend on."""
        spof = []

        for node in nodes:
            fan_in = node.get("fan_in", 0)
            if fan_in >= self.SPOF_FAN_IN_THRESHOLD:
                risk_level = "High" if fan_in >= 15 else "Medium"
                spof.append({
                    "program": node["id"],
                    "fan_in": fan_in,
                    "risk": f"{fan_in} programs depend on this - single point of failure",
                    "risk_level": risk_level,
                    "recommendation": "Ensure comprehensive testing and monitoring; consider redundancy"
                })

        return sorted(spof, key=lambda x: x["fan_in"], reverse=True)

    def _find_circular_dependencies(self, edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find circular dependency chains."""
        # Build adjacency list
        adjacency: Dict[str, Set[str]] = {}
        for edge in edges:
            source = edge.get("from", "")
            target = edge.get("to", "")
            if source and target:
                if source not in adjacency:
                    adjacency[source] = set()
                adjacency[source].add(target)

        circular = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def find_cycle(node: str, path: List[str]) -> List[Dict[str, Any]]:
            """DFS to find cycles."""
            cycles = []

            if node in rec_stack:
                # Found cycle - extract it
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                return [{
                    "cycle": cycle,
                    "risk": "Medium",
                    "recommendation": "Extract shared functionality to break cycle"
                }]

            if node in visited:
                return []

            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adjacency.get(node, []):
                cycles.extend(find_cycle(neighbor, path.copy()))

            rec_stack.discard(node)
            return cycles

        # Find cycles starting from each node
        for node in adjacency:
            if node not in visited:
                circular.extend(find_cycle(node, []))

        return circular

    def _find_tight_coupling(self, coupling_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find areas of tight coupling."""
        tight = []
        by_program = coupling_metrics.get("by_program", [])

        for prog in by_program:
            if prog.get("coupling_factor", 0) >= self.TIGHT_COUPLING_THRESHOLD:
                tight.append({
                    "program": prog["program"],
                    "coupling_factor": prog["coupling_factor"],
                    "risk": "High coupling indicates tight integration",
                    "recommendation": "Consider extracting to reduce coupling"
                })

        return tight

    def _find_shared_components(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find heavily shared copybooks/classes."""
        shared = []

        for node in nodes:
            if node.get("type") in ("copybook", "interface"):
                used_by = node.get("used_by_count", node.get("fan_in", 0))
                if used_by >= 5:  # Used by 5+ programs
                    shared.append({
                        "component": node["id"],
                        "used_by_count": used_by,
                        "risk": "Shared across many programs - changes have wide impact",
                        "recommendation": "Ensure backwards compatibility; consider versioning"
                    })

        return sorted(shared, key=lambda x: x["used_by_count"], reverse=True)
