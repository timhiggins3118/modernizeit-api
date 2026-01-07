"""
Modularity Calculator for Monolith Identifier

Calculates modularity metrics for each program/class:
- Cohesion Score: How focused is the program on a single responsibility
- Coupling Score: How many external dependencies
- Complexity Score: Structural complexity
- Maintainability Index: Combined health score (0-100)
"""

from typing import Any, Dict, List


class ModularityCalculator:
    """
    Calculates modularity metrics for analyzed code.
    """

    def calculate(
        self,
        static_analysis: Dict[str, Any],
        patterns: Dict[str, Any],
        source_type: str = "cobol"
    ) -> Dict[str, Any]:
        """
        Calculate modularity metrics.

        Args:
            static_analysis: Results from static analyzer
            patterns: Detected patterns
            source_type: "cobol" or "java"

        Returns:
            Dictionary with modularity metrics per program and overall summary
        """
        programs = static_analysis.get("programs", [])
        summary = static_analysis.get("summary", {})
        total_programs = summary.get("total_programs", len(programs))

        # Build pattern lookup for business capability estimation
        pattern_lookup = self._build_pattern_lookup(patterns)

        metrics_by_program = []

        for program in programs:
            if source_type == "cobol":
                metrics = self._calculate_cobol_metrics(program, total_programs, pattern_lookup)
            else:
                metrics = self._calculate_java_metrics(program, total_programs, pattern_lookup)

            metrics_by_program.append(metrics)

        # Calculate overall metrics
        overall = self._calculate_overall(metrics_by_program)

        return {
            "by_program": metrics_by_program,
            "overall": overall
        }

    def _build_pattern_lookup(self, patterns: Dict[str, Any]) -> Dict[str, List[str]]:
        """Build a lookup of programs to their detected patterns."""
        lookup = {}
        for pattern in patterns.get("patterns", []):
            program = pattern.get("program", "")
            if program not in lookup:
                lookup[program] = []
            lookup[program].append(pattern.get("pattern_type", ""))
        return lookup

    def _calculate_cobol_metrics(
        self,
        program: Dict[str, Any],
        total_programs: int,
        pattern_lookup: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Calculate metrics for a COBOL program."""
        program_name = program.get("program", "UNKNOWN")
        loc = program.get("loc", 0)
        sections = program.get("sections", 0)
        paragraphs = program.get("paragraphs", 0)
        perform_count = program.get("perform_count", 0)
        goto_count = program.get("goto_count", 0)
        call_count = program.get("call_count", 0)
        copy_count = program.get("copy_count", 0)
        nested_if = program.get("nested_if_depth", 0)

        # Estimate business capabilities based on size and structure
        # More sections/paragraphs suggests more responsibilities
        estimated_capabilities = self._estimate_cobol_capabilities(sections, paragraphs, loc)

        # Cohesion Score (0-1, higher is better)
        # 1 capability = 1.0, more capabilities = lower cohesion
        cohesion_score = 1.0 / max(estimated_capabilities, 1)

        # Coupling Score (0-1, lower is better)
        # Based on external dependencies relative to codebase size
        total_dependencies = call_count + copy_count
        coupling_score = min(total_dependencies / max(total_programs * 2, 1), 1.0)

        # Complexity Score (lower is better)
        # Based on GOTO, PERFORM, sections, nested IFs
        complexity_score = (
            (goto_count * 2.0) +
            (perform_count * 0.5) +
            (sections * 0.1) +
            (nested_if * 3.0)
        )

        # Maintainability Index (0-100, higher is better)
        # Based on complexity, coupling, and cohesion
        maintainability = self._calculate_maintainability(
            cohesion_score, coupling_score, complexity_score
        )

        # Classification
        classification = self._classify_maintainability(maintainability)

        # Generate recommendations
        recommendations = self._generate_cobol_recommendations(
            cohesion_score, coupling_score, complexity_score, goto_count,
            pattern_lookup.get(program_name, [])
        )

        return {
            "program": program_name,
            "loc": loc,
            "estimated_capabilities": estimated_capabilities,
            "cohesion_score": round(cohesion_score, 3),
            "coupling_score": round(coupling_score, 3),
            "complexity_score": round(complexity_score, 1),
            "maintainability_index": round(maintainability, 1),
            "classification": classification,
            "recommendations": recommendations
        }

    def _calculate_java_metrics(
        self,
        program: Dict[str, Any],
        total_programs: int,
        pattern_lookup: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Calculate metrics for a Java class."""
        class_name = program.get("class_name", program.get("program", "UNKNOWN"))
        loc = program.get("loc", 0)
        methods = program.get("methods", 0)
        fields = program.get("fields", 0)
        imports = program.get("imports", 0)
        complexity = program.get("cyclomatic_complexity", 0)
        nested_depth = program.get("max_nested_depth", 0)
        external_calls = program.get("external_calls", 0)

        # Estimate business capabilities based on methods and fields
        estimated_capabilities = self._estimate_java_capabilities(methods, fields, loc)

        # Cohesion Score (0-1, higher is better)
        cohesion_score = 1.0 / max(estimated_capabilities, 1)

        # Coupling Score (0-1, lower is better)
        coupling_score = min(imports / max(total_programs * 3, 1), 1.0)

        # Complexity Score (lower is better)
        complexity_score = complexity + (nested_depth * 2.0)

        # Maintainability Index (0-100, higher is better)
        maintainability = self._calculate_maintainability(
            cohesion_score, coupling_score, complexity_score
        )

        # Classification
        classification = self._classify_maintainability(maintainability)

        # Generate recommendations
        recommendations = self._generate_java_recommendations(
            cohesion_score, coupling_score, complexity_score,
            pattern_lookup.get(class_name, [])
        )

        return {
            "program": class_name,
            "loc": loc,
            "estimated_capabilities": estimated_capabilities,
            "cohesion_score": round(cohesion_score, 3),
            "coupling_score": round(coupling_score, 3),
            "complexity_score": round(complexity_score, 1),
            "maintainability_index": round(maintainability, 1),
            "classification": classification,
            "recommendations": recommendations
        }

    def _estimate_cobol_capabilities(self, sections: int, paragraphs: int, loc: int) -> int:
        """
        Estimate number of business capabilities in a COBOL program.

        Based on program structure and size.
        """
        # Base: 1 capability
        capabilities = 1

        # Large programs likely have multiple capabilities
        if loc > 5000:
            capabilities += 2
        elif loc > 3000:
            capabilities += 1

        # Many sections suggest multiple responsibilities
        if sections > 50:
            capabilities += 2
        elif sections > 20:
            capabilities += 1

        # Many paragraphs suggest complexity
        if paragraphs > 200:
            capabilities += 1

        return min(capabilities, 6)  # Cap at 6

    def _estimate_java_capabilities(self, methods: int, fields: int, loc: int) -> int:
        """
        Estimate number of business capabilities in a Java class.

        Based on class structure and size.
        """
        # Base: 1 capability
        capabilities = 1

        # Large classes likely have multiple capabilities
        if loc > 3000:
            capabilities += 2
        elif loc > 1500:
            capabilities += 1

        # Many methods suggest multiple responsibilities
        if methods > 30:
            capabilities += 2
        elif methods > 15:
            capabilities += 1

        # Many fields suggest data complexity
        if fields > 20:
            capabilities += 1

        return min(capabilities, 6)  # Cap at 6

    def _calculate_maintainability(
        self,
        cohesion: float,
        coupling: float,
        complexity: float
    ) -> float:
        """
        Calculate maintainability index (0-100).

        Formula:
        maintainability = 100 - (complexity * 0.5) - (coupling * 20) - ((1 - cohesion) * 30)
        """
        # Normalize complexity to 0-100 range
        normalized_complexity = min(complexity, 100)

        maintainability = (
            100
            - (normalized_complexity * 0.5)
            - (coupling * 20)
            - ((1 - cohesion) * 30)
        )

        return max(0, min(100, maintainability))

    def _classify_maintainability(self, maintainability: float) -> str:
        """Classify maintainability level."""
        if maintainability > 70:
            return "HIGH"
        elif maintainability >= 40:
            return "MEDIUM"
        else:
            return "LOW"

    def _generate_cobol_recommendations(
        self,
        cohesion: float,
        coupling: float,
        complexity: float,
        goto_count: int,
        patterns: List[str]
    ) -> List[str]:
        """Generate improvement recommendations for COBOL."""
        recommendations = []

        if cohesion < 0.5:
            recommendations.append("Improve cohesion by extracting business capabilities into separate programs")

        if coupling > 0.3:
            recommendations.append("Reduce coupling by minimizing CALL dependencies")

        if goto_count > 5:
            recommendations.append("Eliminate GOTO statements to improve code flow")

        if complexity > 50:
            recommendations.append("Reduce complexity by simplifying nested logic")

        if "GOD_OBJECT" in patterns:
            recommendations.append("Priority: Decompose God Object into focused modules")

        if not recommendations:
            recommendations.append("Code quality is acceptable - consider minor optimizations")

        return recommendations

    def _generate_java_recommendations(
        self,
        cohesion: float,
        coupling: float,
        complexity: float,
        patterns: List[str]
    ) -> List[str]:
        """Generate improvement recommendations for Java."""
        recommendations = []

        if cohesion < 0.5:
            recommendations.append("Apply Single Responsibility Principle - extract separate classes")

        if coupling > 0.3:
            recommendations.append("Use dependency injection to reduce tight coupling")

        if complexity > 50:
            recommendations.append("Extract complex methods into helper classes")

        if "GOD_OBJECT" in patterns:
            recommendations.append("Priority: Split God Class following SOLID principles")

        if "SPAGHETTI_CODE" in patterns:
            recommendations.append("Refactor nested conditionals using strategy or state patterns")

        if not recommendations:
            recommendations.append("Code quality is acceptable - consider minor improvements")

        return recommendations

    def _calculate_overall(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall summary metrics."""
        if not metrics:
            return {
                "total_programs": 0,
                "average_cohesion": 0,
                "average_coupling": 0,
                "average_complexity": 0,
                "average_maintainability": 0,
                "high_maintainability_count": 0,
                "medium_maintainability_count": 0,
                "low_maintainability_count": 0
            }

        total = len(metrics)
        total_cohesion = sum(m["cohesion_score"] for m in metrics)
        total_coupling = sum(m["coupling_score"] for m in metrics)
        total_complexity = sum(m["complexity_score"] for m in metrics)
        total_maintainability = sum(m["maintainability_index"] for m in metrics)

        high_count = sum(1 for m in metrics if m["classification"] == "HIGH")
        medium_count = sum(1 for m in metrics if m["classification"] == "MEDIUM")
        low_count = sum(1 for m in metrics if m["classification"] == "LOW")

        return {
            "total_programs": total,
            "average_cohesion": round(total_cohesion / total, 3),
            "average_coupling": round(total_coupling / total, 3),
            "average_complexity": round(total_complexity / total, 1),
            "average_maintainability": round(total_maintainability / total, 1),
            "high_maintainability_count": high_count,
            "medium_maintainability_count": medium_count,
            "low_maintainability_count": low_count
        }
