"""
Coupling Calculator

Calculates coupling metrics for each node in the dependency graph.
- Fan-in: Number of incoming dependencies
- Fan-out: Number of outgoing dependencies
- Coupling factor: Normalized coupling score
- Classification: HIGH, MEDIUM, LOW coupling
"""

from typing import Any, Dict, List


class CouplingCalculator:
    """
    Calculates coupling metrics from dependency graph.
    """

    # Thresholds for coupling classification
    HIGH_COUPLING_THRESHOLD = 0.3
    MEDIUM_COUPLING_THRESHOLD = 0.1

    def __init__(self):
        self.metrics: List[Dict[str, Any]] = []
        self.overall: Dict[str, Any] = {}

    def calculate(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate coupling metrics from dependency graph.

        Args:
            graph: Dependency graph with nodes and edges

        Returns:
            Coupling metrics by program and overall statistics
        """
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        if not nodes:
            return self._empty_result()

        total_nodes = len(nodes)
        max_possible_edges = total_nodes * (total_nodes - 1) if total_nodes > 1 else 1

        self.metrics = []

        for node in nodes:
            node_id = node["id"]
            fan_in = node.get("fan_in", 0)
            fan_out = node.get("fan_out", 0)

            # Calculate coupling factor (normalized)
            coupling_factor = (fan_in + fan_out) / max_possible_edges if max_possible_edges > 0 else 0

            # Calculate cohesion score (inverse of fan_out ratio)
            # Programs with high fan_out relative to fan_in have lower cohesion
            if fan_in + fan_out > 0:
                cohesion_score = fan_in / (fan_in + fan_out)
            else:
                cohesion_score = 1.0

            # Classify coupling level
            classification = self._classify_coupling(coupling_factor)

            self.metrics.append({
                "program": node_id,
                "fan_in": fan_in,
                "fan_out": fan_out,
                "coupling_factor": round(coupling_factor, 3),
                "cohesion_score": round(cohesion_score, 2),
                "classification": classification
            })

        # Sort by coupling factor descending
        self.metrics.sort(key=lambda x: x["coupling_factor"], reverse=True)

        # Calculate overall statistics
        total_fan_in = sum(m["fan_in"] for m in self.metrics)
        total_fan_out = sum(m["fan_out"] for m in self.metrics)
        total_coupling = sum(m["coupling_factor"] for m in self.metrics)

        high_count = sum(1 for m in self.metrics if m["classification"] == "High Coupling")
        medium_count = sum(1 for m in self.metrics if m["classification"] == "Medium Coupling")
        low_count = sum(1 for m in self.metrics if m["classification"] == "Low Coupling")

        self.overall = {
            "total_programs": total_nodes,
            "average_fan_in": round(total_fan_in / total_nodes, 2) if total_nodes > 0 else 0,
            "average_fan_out": round(total_fan_out / total_nodes, 2) if total_nodes > 0 else 0,
            "average_coupling": round(total_coupling / total_nodes, 3) if total_nodes > 0 else 0,
            "high_coupling_count": high_count,
            "medium_coupling_count": medium_count,
            "low_coupling_count": low_count
        }

        return {
            "by_program": self.metrics,
            "overall": self.overall
        }

    def _classify_coupling(self, coupling_factor: float) -> str:
        """Classify coupling level based on factor."""
        if coupling_factor >= self.HIGH_COUPLING_THRESHOLD:
            return "High Coupling"
        elif coupling_factor >= self.MEDIUM_COUPLING_THRESHOLD:
            return "Medium Coupling"
        else:
            return "Low Coupling"

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            "by_program": [],
            "overall": {
                "total_programs": 0,
                "average_fan_in": 0,
                "average_fan_out": 0,
                "average_coupling": 0,
                "high_coupling_count": 0,
                "medium_coupling_count": 0,
                "low_coupling_count": 0
            }
        }

    def get_high_coupling_programs(self) -> List[Dict[str, Any]]:
        """Get list of high coupling programs."""
        return [m for m in self.metrics if m["classification"] == "High Coupling"]

    def get_coupling_clusters(self) -> List[Dict[str, Any]]:
        """
        Identify clusters of tightly coupled programs.

        Returns programs that have mutual dependencies.
        """
        # This is a simplified version - full implementation would use
        # graph algorithms to find strongly connected components
        clusters = []

        high_coupling = self.get_high_coupling_programs()
        if high_coupling:
            clusters.append({
                "cluster_name": "High Coupling Cluster",
                "programs": [p["program"] for p in high_coupling],
                "internal_coupling": sum(p["coupling_factor"] for p in high_coupling) / len(high_coupling)
            })

        return clusters
