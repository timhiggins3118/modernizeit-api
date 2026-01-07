"""
Graph Builder

Builds dependency graph from static analysis data.
Creates nodes (programs/classes) and edges (dependencies).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


@dataclass
class Node:
    """A node in the dependency graph."""
    id: str
    node_type: str  # "program", "copybook", "class", "interface"
    fan_in: int = 0  # How many other nodes depend on this
    fan_out: int = 0  # How many nodes this depends on
    lines_of_code: int = 0
    complexity_score: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.node_type,
            "fan_in": self.fan_in,
            "fan_out": self.fan_out,
            "lines_of_code": self.lines_of_code,
            "complexity_score": self.complexity_score,
            **self.metadata
        }


@dataclass
class Edge:
    """An edge in the dependency graph."""
    source: str
    target: str
    edge_type: str  # "CALL", "COPY", "FILE_IO", "IMPORT", "EXTENDS", "IMPLEMENTS"
    line_number: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.source,
            "to": self.target,
            "type": self.edge_type,
            "line_number": self.line_number,
            **self.metadata
        }


class GraphBuilder:
    """
    Builds dependency graph from analysis data.

    Supports both COBOL and Java source analysis.
    """

    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []

    def build_from_cobol(self, static_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build graph from COBOL static analysis.

        Args:
            static_analysis: Output from StaticAnalyzer

        Returns:
            Graph structure with nodes and edges
        """
        self.nodes = {}
        self.edges = []

        programs = static_analysis.get("programs", [])

        # First pass: Create nodes for all programs
        for prog in programs:
            prog_id = prog["program"]
            self.nodes[prog_id] = Node(
                id=prog_id,
                node_type="program",
                lines_of_code=prog.get("lines_of_code", 0),
                metadata={"file_path": prog.get("file_path", "")}
            )

        # Track copybooks
        copybook_usage: Dict[str, List[str]] = {}

        # Second pass: Create edges and track dependencies
        for prog in programs:
            prog_id = prog["program"]

            # CALL edges
            for call in prog.get("calls", []):
                target = call["target"]
                self.edges.append(Edge(
                    source=prog_id,
                    target=target,
                    edge_type="CALL",
                    line_number=call.get("line", 0)
                ))

                # Ensure target node exists
                if target not in self.nodes:
                    self.nodes[target] = Node(id=target, node_type="program")

            # COPY edges
            for copy in prog.get("copies", []):
                copybook = copy["copybook"]
                self.edges.append(Edge(
                    source=prog_id,
                    target=copybook,
                    edge_type="COPY",
                    line_number=copy.get("line", 0)
                ))

                # Track copybook usage
                if copybook not in copybook_usage:
                    copybook_usage[copybook] = []
                copybook_usage[copybook].append(prog_id)

                # Ensure copybook node exists
                if copybook not in self.nodes:
                    self.nodes[copybook] = Node(id=copybook, node_type="copybook")

            # FILE_IO edges
            for file_op in prog.get("file_io", []):
                file_name = file_op["file"]
                self.edges.append(Edge(
                    source=prog_id,
                    target=file_name,
                    edge_type="FILE_IO",
                    line_number=file_op.get("line", 0),
                    metadata={"operation": file_op.get("operation", "")}
                ))

        # Update copybook nodes with usage info
        for copybook, programs_using in copybook_usage.items():
            if copybook in self.nodes:
                self.nodes[copybook].metadata["used_by_count"] = len(programs_using)
                self.nodes[copybook].metadata["programs"] = programs_using
                self.nodes[copybook].fan_in = len(programs_using)

        # Calculate fan-in and fan-out
        self._calculate_fan_metrics()

        return self._build_output()

    def build_from_java(self, java_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build graph from Java analysis.

        Args:
            java_analysis: Output from JavaAnalyzer

        Returns:
            Graph structure with nodes and edges
        """
        self.nodes = {}
        self.edges = []

        classes = java_analysis.get("classes", [])

        # First pass: Create nodes for all classes
        for cls in classes:
            cls_id = cls["class_name"]
            full_id = f"{cls['package']}.{cls_id}" if cls.get("package") else cls_id

            self.nodes[cls_id] = Node(
                id=cls_id,
                node_type=cls.get("class_type", "class"),
                lines_of_code=cls.get("lines_of_code", 0),
                metadata={
                    "package": cls.get("package", ""),
                    "file_path": cls.get("file_path", ""),
                    "method_count": cls.get("method_count", 0),
                    "field_count": cls.get("field_count", 0)
                }
            )

        # Second pass: Create edges
        for cls in classes:
            cls_id = cls["class_name"]

            # Import edges (filtered to project classes only)
            for imp in cls.get("imports", []):
                target = imp["class"]
                if target != "*" and target in self.nodes:
                    self.edges.append(Edge(
                        source=cls_id,
                        target=target,
                        edge_type="IMPORT",
                        line_number=imp.get("line", 0)
                    ))

            # Inheritance edges
            for inh in cls.get("inheritance", []):
                parent = inh["parent"]
                self.edges.append(Edge(
                    source=cls_id,
                    target=parent,
                    edge_type=inh["relationship"].upper(),
                    line_number=inh.get("line", 0)
                ))

                # Ensure parent node exists
                if parent not in self.nodes:
                    self.nodes[parent] = Node(
                        id=parent,
                        node_type="class" if inh["relationship"] == "extends" else "interface"
                    )

            # Method call edges
            for call in cls.get("method_calls", []):
                target = call["target_class"]
                if target in self.nodes and target != cls_id:
                    self.edges.append(Edge(
                        source=cls_id,
                        target=target,
                        edge_type="METHOD_CALL",
                        line_number=call.get("line", 0),
                        metadata={"method": call.get("method", "")}
                    ))

            # Field type edges (class references in fields)
            for fld in cls.get("fields", []):
                field_type = fld["type"].split('<')[0].strip()  # Remove generics
                if field_type in self.nodes and field_type != cls_id:
                    self.edges.append(Edge(
                        source=cls_id,
                        target=field_type,
                        edge_type="FIELD_REF",
                        line_number=fld.get("line", 0),
                        metadata={"field_name": fld.get("name", "")}
                    ))

        # Calculate fan-in and fan-out
        self._calculate_fan_metrics()

        return self._build_output()

    def _calculate_fan_metrics(self):
        """Calculate fan-in and fan-out for all nodes."""
        # Reset counts
        for node in self.nodes.values():
            node.fan_in = 0
            node.fan_out = 0

        # Count edges
        for edge in self.edges:
            if edge.source in self.nodes:
                self.nodes[edge.source].fan_out += 1
            if edge.target in self.nodes:
                self.nodes[edge.target].fan_in += 1

        # Calculate complexity score (simple heuristic)
        for node in self.nodes.values():
            node.complexity_score = node.fan_in + node.fan_out + (node.lines_of_code // 100)

    def _build_output(self) -> Dict[str, Any]:
        """Build output dictionary."""
        nodes_list = [n.to_dict() for n in self.nodes.values()]
        edges_list = [e.to_dict() for e in self.edges]

        # Separate by type
        program_nodes = [n for n in nodes_list if n["type"] in ("program", "class")]
        copybook_nodes = [n for n in nodes_list if n["type"] in ("copybook", "interface")]

        return {
            "nodes": nodes_list,
            "edges": edges_list,
            "summary": {
                "total_nodes": len(nodes_list),
                "total_edges": len(edges_list),
                "program_count": len(program_nodes),
                "copybook_count": len(copybook_nodes),
                "edge_types": self._count_edge_types()
            }
        }

    def _count_edge_types(self) -> Dict[str, int]:
        """Count edges by type."""
        counts: Dict[str, int] = {}
        for edge in self.edges:
            edge_type = edge.edge_type
            counts[edge_type] = counts.get(edge_type, 0) + 1
        return counts
