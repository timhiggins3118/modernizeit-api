"""
Rule-Based Analyzer

Detects refactoring opportunities using deterministic rules.
This is the first layer of the hybrid approach - gathering facts.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from engines.code_refactor.utils.java_parser import (
    JavaClass,
    JavaField,
    JavaMethod,
    JavaParser,
)


@dataclass
class PatternMatch:
    """A detected pattern that suggests a refactoring opportunity."""
    pattern_type: str  # e.g., "class_too_large", "field_grouping", "goto_usage"
    severity: str  # "high", "medium", "low"
    confidence: float  # 0.0 to 1.0
    location: Dict[str, Any]  # file, lines, element names
    details: str  # Human-readable description
    suggested_recipe: str  # e.g., "split_class", "extract_enum", "rename_method"
    evidence: Dict[str, Any] = field(default_factory=dict)  # Supporting data


@dataclass
class RuleAnalysisResult:
    """Results from rule-based analysis."""
    java_file: str
    class_name: str
    patterns: List[PatternMatch]
    metrics: Dict[str, Any]
    summary: Dict[str, Any]


class RuleAnalyzer:
    """
    Rule-based analyzer for Java code.

    Detects patterns that indicate refactoring opportunities:
    - Class too large (lines, fields, methods)
    - Field groupings (common prefixes suggesting cohesive classes)
    - Method groupings (COBOL paragraph prefixes)
    - GO TO comments (unhandled control flow)
    - BigDecimal overuse (loop counters, simple integers)
    - Array patterns (parallel arrays, fixed sizes)
    - Deeply nested structures
    - COBOL naming conventions
    """

    # Thresholds for pattern detection
    MAX_CLASS_LINES = 1000
    MAX_FIELDS = 100
    MAX_METHODS = 50
    MAX_METHOD_COMPLEXITY = 10
    MIN_FIELD_GROUP_SIZE = 5
    MIN_METHOD_GROUP_SIZE = 3

    def __init__(self, semantic_models_path: Optional[str] = None):
        """
        Initialize the rule analyzer.

        Args:
            semantic_models_path: Path to code_analysis semantic models
                                 (data_model.json, procedure_model.json)
                                 Used to enhance analysis with COBOL context.
        """
        self.parser = JavaParser()
        self.semantic_models_path = semantic_models_path
        self.data_model = None
        self.procedure_model = None

        if semantic_models_path:
            self._load_semantic_models(semantic_models_path)

    def _load_semantic_models(self, path: str) -> None:
        """Load semantic models from code_analysis output."""
        import json
        models_dir = Path(path)

        # Find and load data model
        data_model_files = list(models_dir.glob("*_data_model.json"))
        if data_model_files:
            with open(data_model_files[0]) as f:
                self.data_model = json.load(f)

        # Find and load procedure model
        proc_model_files = list(models_dir.glob("*_procedure_model.json"))
        if proc_model_files:
            with open(proc_model_files[0]) as f:
                self.procedure_model = json.load(f)

    def analyze(self, java_file: str) -> RuleAnalysisResult:
        """
        Analyze a Java file for refactoring patterns.

        Args:
            java_file: Path to Java source file

        Returns:
            RuleAnalysisResult with detected patterns and metrics
        """
        # Parse the Java file
        java_class = self.parser.parse_file(java_file)

        # Get complexity metrics
        metrics = self.parser.analyze_complexity(java_class)

        # Detect patterns
        patterns: List[PatternMatch] = []

        # 1. Class size patterns
        patterns.extend(self._detect_class_size_patterns(java_class, metrics))

        # 2. Field grouping patterns
        patterns.extend(self._detect_field_patterns(java_class))

        # 3. Method grouping patterns
        patterns.extend(self._detect_method_patterns(java_class))

        # 4. GO TO patterns
        patterns.extend(self._detect_goto_patterns(java_class))

        # 5. Type patterns (BigDecimal, arrays)
        patterns.extend(self._detect_type_patterns(java_class))

        # 6. Naming patterns
        patterns.extend(self._detect_naming_patterns(java_class))

        # 7. Inner class patterns
        patterns.extend(self._detect_inner_class_patterns(java_class))

        # Build summary
        summary = self._build_summary(patterns, metrics)

        return RuleAnalysisResult(
            java_file=java_file,
            class_name=java_class.name,
            patterns=patterns,
            metrics=metrics,
            summary=summary,
        )

    def _detect_class_size_patterns(
        self,
        java_class: JavaClass,
        metrics: Dict[str, Any]
    ) -> List[PatternMatch]:
        """Detect patterns related to class size."""
        patterns = []

        # Too many lines
        if java_class.total_lines > self.MAX_CLASS_LINES:
            patterns.append(PatternMatch(
                pattern_type="class_too_large",
                severity="high",
                confidence=0.95,
                location={"file": java_class.file_path, "lines": java_class.total_lines},
                details=f"Class has {java_class.total_lines} lines (threshold: {self.MAX_CLASS_LINES})",
                suggested_recipe="split_class",
                evidence={
                    "total_lines": java_class.total_lines,
                    "threshold": self.MAX_CLASS_LINES,
                    "excess": java_class.total_lines - self.MAX_CLASS_LINES,
                },
            ))

        # Too many fields
        if len(java_class.fields) > self.MAX_FIELDS:
            patterns.append(PatternMatch(
                pattern_type="too_many_fields",
                severity="high",
                confidence=0.90,
                location={"file": java_class.file_path, "field_count": len(java_class.fields)},
                details=f"Class has {len(java_class.fields)} fields (threshold: {self.MAX_FIELDS})",
                suggested_recipe="extract_class",
                evidence={
                    "field_count": len(java_class.fields),
                    "threshold": self.MAX_FIELDS,
                },
            ))

        # Too many methods
        if len(java_class.methods) > self.MAX_METHODS:
            patterns.append(PatternMatch(
                pattern_type="too_many_methods",
                severity="medium",
                confidence=0.85,
                location={"file": java_class.file_path, "method_count": len(java_class.methods)},
                details=f"Class has {len(java_class.methods)} methods (threshold: {self.MAX_METHODS})",
                suggested_recipe="split_class",
                evidence={
                    "method_count": len(java_class.methods),
                    "threshold": self.MAX_METHODS,
                },
            ))

        return patterns

    def _detect_field_patterns(self, java_class: JavaClass) -> List[PatternMatch]:
        """Detect patterns in field declarations."""
        patterns = []

        # Get field groups by prefix
        field_groups = self.parser.get_field_prefix_groups(java_class.fields)

        for prefix, fields in field_groups.items():
            if len(fields) >= self.MIN_FIELD_GROUP_SIZE:
                patterns.append(PatternMatch(
                    pattern_type="field_grouping",
                    severity="medium",
                    confidence=0.80,
                    location={
                        "file": java_class.file_path,
                        "prefix": prefix,
                        "lines": [f.line_number for f in fields],
                    },
                    details=f"{len(fields)} fields with prefix '{prefix}' suggest a cohesive class",
                    suggested_recipe="extract_class",
                    evidence={
                        "prefix": prefix,
                        "field_count": len(fields),
                        "field_names": [f.name for f in fields],
                        "field_types": list(set(f.java_type for f in fields)),
                    },
                ))

        return patterns

    def _detect_method_patterns(self, java_class: JavaClass) -> List[PatternMatch]:
        """Detect patterns in method declarations."""
        patterns = []

        # Get method groups by COBOL paragraph prefix
        method_groups = self.parser.get_method_prefix_groups(java_class.methods)

        for prefix, methods in method_groups.items():
            if len(methods) >= self.MIN_METHOD_GROUP_SIZE:
                patterns.append(PatternMatch(
                    pattern_type="method_grouping",
                    severity="medium",
                    confidence=0.75,
                    location={
                        "file": java_class.file_path,
                        "prefix": prefix,
                        "lines": [m.start_line for m in methods],
                    },
                    details=f"{len(methods)} methods with COBOL prefix '{prefix}' may form a functional unit",
                    suggested_recipe="extract_class",
                    evidence={
                        "prefix": prefix,
                        "method_count": len(methods),
                        "method_names": [m.name for m in methods],
                        "cobol_paragraphs": [m.cobol_paragraph for m in methods if m.cobol_paragraph],
                    },
                ))

        # High complexity methods
        for method in java_class.methods:
            if method.complexity > self.MAX_METHOD_COMPLEXITY:
                patterns.append(PatternMatch(
                    pattern_type="high_complexity_method",
                    severity="medium",
                    confidence=0.85,
                    location={
                        "file": java_class.file_path,
                        "method": method.name,
                        "start_line": method.start_line,
                        "end_line": method.end_line,
                    },
                    details=f"Method '{method.name}' has complexity {method.complexity} (threshold: {self.MAX_METHOD_COMPLEXITY})",
                    suggested_recipe="decompose_method",
                    evidence={
                        "complexity": method.complexity,
                        "threshold": self.MAX_METHOD_COMPLEXITY,
                        "line_count": method.end_line - method.start_line,
                    },
                ))

        return patterns

    def _detect_goto_patterns(self, java_class: JavaClass) -> List[PatternMatch]:
        """Detect GO TO comment patterns (unhandled control flow)."""
        patterns = []

        goto_methods = [m for m in java_class.methods if m.has_goto_comment]

        if goto_methods:
            patterns.append(PatternMatch(
                pattern_type="goto_usage",
                severity="high",
                confidence=0.95,
                location={
                    "file": java_class.file_path,
                    "methods": [m.name for m in goto_methods],
                },
                details=f"{len(goto_methods)} methods contain GO TO comments (unhandled control flow)",
                suggested_recipe="implement_control_flow",
                evidence={
                    "method_count": len(goto_methods),
                    "method_names": [m.name for m in goto_methods],
                    "lines": [m.start_line for m in goto_methods],
                },
            ))

        return patterns

    def _detect_type_patterns(self, java_class: JavaClass) -> List[PatternMatch]:
        """Detect type-related patterns."""
        patterns = []

        # BigDecimal fields that might be simple integers
        bigdecimal_fields = [f for f in java_class.fields if 'BigDecimal' in f.java_type]

        # Look for likely counter/index fields
        counter_patterns = re.compile(r'(count|cnt|idx|index|i|j|k|n|num|seq)$', re.IGNORECASE)
        likely_int_fields = [f for f in bigdecimal_fields if counter_patterns.search(f.name)]

        if likely_int_fields:
            patterns.append(PatternMatch(
                pattern_type="bigdecimal_overuse",
                severity="low",
                confidence=0.70,
                location={
                    "file": java_class.file_path,
                    "fields": [f.name for f in likely_int_fields],
                },
                details=f"{len(likely_int_fields)} BigDecimal fields appear to be simple counters/indexes",
                suggested_recipe="optimize_types",
                evidence={
                    "field_names": [f.name for f in likely_int_fields],
                    "suggested_type": "int",
                },
            ))

        # Parallel arrays (arrays of same size)
        array_fields = [f for f in java_class.fields if f.is_array and f.array_size]
        size_groups: Dict[int, List[JavaField]] = {}
        for f in array_fields:
            if f.array_size:
                if f.array_size not in size_groups:
                    size_groups[f.array_size] = []
                size_groups[f.array_size].append(f)

        for size, fields in size_groups.items():
            if len(fields) >= 3:
                patterns.append(PatternMatch(
                    pattern_type="parallel_arrays",
                    severity="medium",
                    confidence=0.80,
                    location={
                        "file": java_class.file_path,
                        "array_size": size,
                        "fields": [f.name for f in fields],
                    },
                    details=f"{len(fields)} arrays of size {size} - consider List<Object> instead",
                    suggested_recipe="convert_to_object_list",
                    evidence={
                        "array_size": size,
                        "field_count": len(fields),
                        "field_names": [f.name for f in fields],
                        "field_types": [f.java_type for f in fields],
                    },
                ))

        return patterns

    def _detect_naming_patterns(self, java_class: JavaClass) -> List[PatternMatch]:
        """Detect COBOL-style naming patterns that should be modernized."""
        patterns = []

        # Methods with COBOL paragraph naming (e.g., verifyEoqEoy_150)
        cobol_method_pattern = re.compile(r'_\d+(_\d+)?$')
        cobol_named_methods = [m for m in java_class.methods if cobol_method_pattern.search(m.name)]

        if cobol_named_methods:
            patterns.append(PatternMatch(
                pattern_type="cobol_method_naming",
                severity="low",
                confidence=0.90,
                location={
                    "file": java_class.file_path,
                    "methods": [m.name for m in cobol_named_methods[:10]],  # First 10
                },
                details=f"{len(cobol_named_methods)} methods have COBOL paragraph naming convention",
                suggested_recipe="rename_methods",
                evidence={
                    "method_count": len(cobol_named_methods),
                    "sample_names": [m.name for m in cobol_named_methods[:10]],
                    "cobol_paragraphs": [m.cobol_paragraph for m in cobol_named_methods[:10] if m.cobol_paragraph],
                },
            ))

        # Fields with all-caps or underscore naming
        non_java_field_pattern = re.compile(r'^[A-Z][A-Z0-9_]+$')
        non_java_fields = [f for f in java_class.fields if non_java_field_pattern.match(f.name)]

        if len(non_java_fields) > 5:
            patterns.append(PatternMatch(
                pattern_type="cobol_field_naming",
                severity="low",
                confidence=0.85,
                location={
                    "file": java_class.file_path,
                    "fields": [f.name for f in non_java_fields[:10]],
                },
                details=f"{len(non_java_fields)} fields have non-Java naming (COBOL style)",
                suggested_recipe="rename_fields",
                evidence={
                    "field_count": len(non_java_fields),
                    "sample_names": [f.name for f in non_java_fields[:10]],
                },
            ))

        return patterns

    def _detect_inner_class_patterns(self, java_class: JavaClass) -> List[PatternMatch]:
        """Detect patterns in inner classes."""
        patterns = []

        # Inner classes that are just data structures (POJOs)
        data_only_classes = []
        for ic in java_class.inner_classes:
            # If inner class is marked as data structure (has only fields)
            if ic.cobol_record:
                data_only_classes.append(ic)

        if len(data_only_classes) > 5:
            patterns.append(PatternMatch(
                pattern_type="inner_class_extraction",
                severity="low",
                confidence=0.75,
                location={
                    "file": java_class.file_path,
                    "inner_classes": [ic.name for ic in data_only_classes[:10]],
                },
                details=f"{len(data_only_classes)} inner classes could be extracted to separate files",
                suggested_recipe="extract_inner_classes",
                evidence={
                    "class_count": len(data_only_classes),
                    "class_names": [ic.name for ic in data_only_classes[:10]],
                    "cobol_records": [ic.cobol_record for ic in data_only_classes[:10] if ic.cobol_record],
                },
            ))

        return patterns

    def _build_summary(
        self,
        patterns: List[PatternMatch],
        metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build a summary of analysis results."""
        high_severity = [p for p in patterns if p.severity == "high"]
        medium_severity = [p for p in patterns if p.severity == "medium"]
        low_severity = [p for p in patterns if p.severity == "low"]

        # Group by recipe type
        recipe_counts: Dict[str, int] = {}
        for p in patterns:
            recipe = p.suggested_recipe
            recipe_counts[recipe] = recipe_counts.get(recipe, 0) + 1

        return {
            "total_patterns": len(patterns),
            "high_severity": len(high_severity),
            "medium_severity": len(medium_severity),
            "low_severity": len(low_severity),
            "recipe_breakdown": recipe_counts,
            "needs_refactoring": metrics.get("needs_refactoring", False),
            "primary_issues": [p.pattern_type for p in high_severity],
            "avg_confidence": sum(p.confidence for p in patterns) / max(1, len(patterns)),
        }
