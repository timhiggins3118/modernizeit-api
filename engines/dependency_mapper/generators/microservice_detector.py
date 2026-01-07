"""
Microservice Detector

Suggests microservice boundaries based on dependency analysis.
Groups programs/classes with high internal cohesion and low external coupling.
"""

from typing import Any, Dict, List, Set
from collections import defaultdict


class MicroserviceDetector:
    """
    Detects potential microservice boundaries from dependency graph.

    Uses a simple clustering algorithm based on connectivity.
    """

    def __init__(self):
        self.services: List[Dict[str, Any]] = []
        self.shared_components: List[Dict[str, Any]] = []

    def detect(self, graph: Dict[str, Any], coupling_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect microservice boundaries.

        Args:
            graph: Dependency graph with nodes and edges
            coupling_metrics: Output from CouplingCalculator

        Returns:
            Suggested services and shared components
        """
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        if not nodes:
            return self._empty_result()

        # Build adjacency lists (both directions)
        outgoing: Dict[str, Set[str]] = defaultdict(set)
        incoming: Dict[str, Set[str]] = defaultdict(set)

        for edge in edges:
            source = edge.get("from", "")
            target = edge.get("to", "")
            if source and target:
                outgoing[source].add(target)
                incoming[target].add(source)

        # Separate programs from copybooks/shared components
        programs = [n for n in nodes if n.get("type") in ("program", "class")]
        copybooks = [n for n in nodes if n.get("type") in ("copybook", "interface")]

        # Find connected components using union-find
        clusters = self._find_clusters(programs, outgoing, incoming)

        # Build service suggestions
        self.services = []
        service_num = 0

        for cluster in clusters:
            if not cluster:
                continue

            service_num += 1
            programs_in_cluster = list(cluster)

            # Calculate internal vs external coupling
            internal_edges = 0
            external_edges = 0

            for prog in programs_in_cluster:
                for target in outgoing.get(prog, []):
                    if target in cluster:
                        internal_edges += 1
                    else:
                        external_edges += 1

            total_edges = internal_edges + external_edges
            internal_coupling = internal_edges / total_edges if total_edges > 0 else 0
            external_coupling = external_edges / total_edges if total_edges > 0 else 1

            # Calculate cohesion score
            cohesion = self._calculate_cohesion(programs_in_cluster, coupling_metrics)

            self.services.append({
                "service_name": f"Service{service_num}",
                "programs": programs_in_cluster,
                "program_count": len(programs_in_cluster),
                "internal_coupling": round(internal_coupling, 3),
                "external_coupling": round(external_coupling, 3),
                "cohesion_score": round(cohesion, 3),
                "justification": self._generate_justification(internal_coupling, cohesion)
            })

        # Sort by program count descending
        self.services.sort(key=lambda x: x["program_count"], reverse=True)

        # Identify shared components (copybooks used by multiple services)
        self.shared_components = self._find_shared_components(copybooks, incoming, self.services)

        return {
            "suggested_services": self.services,
            "shared_components": self.shared_components,
            "summary": {
                "total_services_suggested": len(self.services),
                "total_shared_components": len(self.shared_components)
            }
        }

    def _find_clusters(
        self,
        programs: List[Dict[str, Any]],
        outgoing: Dict[str, Set[str]],
        incoming: Dict[str, Set[str]]
    ) -> List[Set[str]]:
        """
        Find clusters of related programs using connected components.
        """
        program_ids = {p["id"] for p in programs}

        # Union-Find data structure
        parent: Dict[str, str] = {p: p for p in program_ids}
        rank: Dict[str, int] = {p: 0 for p in program_ids}

        def find(x: str) -> str:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: str, y: str):
            px, py = find(x), find(y)
            if px == py:
                return
            if rank[px] < rank[py]:
                px, py = py, px
            parent[py] = px
            if rank[px] == rank[py]:
                rank[px] += 1

        # Union programs that have CALL relationships
        for prog in program_ids:
            for target in outgoing.get(prog, []):
                if target in program_ids:
                    union(prog, target)
            for source in incoming.get(prog, []):
                if source in program_ids:
                    union(prog, source)

        # Group by root
        clusters: Dict[str, Set[str]] = defaultdict(set)
        for prog in program_ids:
            root = find(prog)
            clusters[root].add(prog)

        return list(clusters.values())

    def _calculate_cohesion(
        self,
        programs: List[str],
        coupling_metrics: Dict[str, Any]
    ) -> float:
        """Calculate cohesion score for a group of programs."""
        if not programs:
            return 0.0

        by_program = {p["program"]: p for p in coupling_metrics.get("by_program", [])}

        total_cohesion = 0.0
        count = 0

        for prog in programs:
            if prog in by_program:
                total_cohesion += by_program[prog].get("cohesion_score", 0.5)
                count += 1

        return total_cohesion / count if count > 0 else 0.5

    def _generate_justification(self, internal_coupling: float, cohesion: float) -> str:
        """Generate justification text for service grouping."""
        internal_pct = round(internal_coupling * 100, 1)

        if internal_coupling >= 0.7:
            return f"Strong internal cohesion ({internal_pct}%), well-defined boundary"
        elif internal_coupling >= 0.4:
            return f"Moderate internal cohesion ({internal_pct}%), some external dependencies"
        else:
            return f"High internal cohesion ({internal_pct}%), low external coupling"

    def _find_shared_components(
        self,
        copybooks: List[Dict[str, Any]],
        incoming: Dict[str, Set[str]],
        services: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Find components shared across multiple services."""
        # Build program-to-service mapping
        prog_to_service: Dict[str, str] = {}
        for svc in services:
            for prog in svc["programs"]:
                prog_to_service[prog] = svc["service_name"]

        shared = []

        for cb in copybooks:
            cb_id = cb["id"]
            users = incoming.get(cb_id, set())

            # Count unique services using this copybook
            services_using: Set[str] = set()
            programs_using: List[str] = []

            for user in users:
                programs_using.append(user)
                if user in prog_to_service:
                    services_using.add(prog_to_service[user])

            if len(services_using) >= 2:  # Used by 2+ services
                shared.append({
                    "component": cb_id,
                    "component_type": cb.get("type", "copybook"),
                    "used_by_services_count": len(services_using),
                    "used_by_programs_count": len(programs_using),
                    "recommendation": "Create shared library or duplicate to avoid cross-service dependencies"
                })

        return sorted(shared, key=lambda x: x["used_by_services_count"], reverse=True)

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "suggested_services": [],
            "shared_components": [],
            "summary": {
                "total_services_suggested": 0,
                "total_shared_components": 0
            }
        }
