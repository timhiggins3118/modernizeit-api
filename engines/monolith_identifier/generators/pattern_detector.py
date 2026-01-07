"""
Pattern Detector for Monolith Identifier

Detects monolithic anti-patterns in source code:
- GOD_OBJECT: Single program/class with too many responsibilities
- BIG_BALL_OF_MUD: Tangled code with no clear structure
- LARGE_PROGRAM: Programs that are simply too large
- TIGHT_COUPLING: Programs with too many dependencies
- SPAGHETTI_CODE: Code with excessive branching and poor structure
"""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class DetectedPattern:
    """A detected monolithic pattern."""
    pattern_type: str
    program: str
    severity: str  # HIGH, MEDIUM, LOW
    confidence: float  # 0.0 - 1.0
    indicators: List[str]
    recommendation: str


class PatternDetector:
    """
    Detects monolithic anti-patterns in analyzed code.
    """

    # COBOL thresholds
    COBOL_GOD_OBJECT_LOC = 5000
    COBOL_GOD_OBJECT_SECTIONS = 100
    COBOL_LARGE_PROGRAM_LOC = 3000
    COBOL_SPAGHETTI_GOTO = 5
    COBOL_SPAGHETTI_NESTED_IF = 5
    COBOL_BIG_BALL_GOTO = 10
    COBOL_BIG_BALL_COMPLEXITY = 50
    COBOL_TIGHT_COUPLING_CALLS = 15

    # Java thresholds
    JAVA_GOD_OBJECT_LOC = 3000
    JAVA_GOD_OBJECT_METHODS = 50
    JAVA_LARGE_PROGRAM_LOC = 2000
    JAVA_BIG_BALL_COMPLEXITY = 50
    JAVA_BIG_BALL_COUPLING = 0.5
    JAVA_TIGHT_COUPLING_IMPORTS = 30
    JAVA_SPAGHETTI_NESTED = 6

    def __init__(self):
        self.patterns: List[DetectedPattern] = []

    def detect_patterns(
        self,
        static_analysis: Dict[str, Any],
        source_type: str = "cobol"
    ) -> Dict[str, Any]:
        """
        Detect patterns from static analysis results.

        Args:
            static_analysis: Results from static analyzer
            source_type: "cobol" or "java"

        Returns:
            Dictionary with detected patterns and summary
        """
        self.patterns = []

        programs = static_analysis.get("programs", [])

        for program in programs:
            if source_type == "cobol":
                self._detect_cobol_patterns(program)
            else:
                self._detect_java_patterns(program)

        return self._build_result()

    def _detect_cobol_patterns(self, program: Dict[str, Any]) -> None:
        """Detect patterns in a COBOL program."""
        program_name = program.get("program", "UNKNOWN")
        loc = program.get("loc", 0)
        sections = program.get("sections", 0)
        paragraphs = program.get("paragraphs", 0)
        goto_count = program.get("goto_count", 0)
        perform_count = program.get("perform_count", 0)
        call_count = program.get("call_count", 0)
        copy_count = program.get("copy_count", 0)
        nested_if = program.get("nested_if_depth", 0)

        # GOD_OBJECT detection
        god_object_indicators = []
        god_object_score = 0

        if loc > self.COBOL_GOD_OBJECT_LOC:
            god_object_indicators.append(f"LOC: {loc} (threshold: {self.COBOL_GOD_OBJECT_LOC})")
            god_object_score += 0.4

        if sections > self.COBOL_GOD_OBJECT_SECTIONS:
            god_object_indicators.append(f"Sections: {sections} (threshold: {self.COBOL_GOD_OBJECT_SECTIONS})")
            god_object_score += 0.3

        if paragraphs > 200:
            god_object_indicators.append(f"Paragraphs: {paragraphs} (high count)")
            god_object_score += 0.2

        if perform_count > 200:
            god_object_indicators.append(f"PERFORM count: {perform_count} (high count)")
            god_object_score += 0.1

        if god_object_score >= 0.5:
            self.patterns.append(DetectedPattern(
                pattern_type="GOD_OBJECT",
                program=program_name,
                severity="HIGH",
                confidence=min(god_object_score, 1.0),
                indicators=god_object_indicators,
                recommendation="Decompose into multiple services by business capability"
            ))

        # LARGE_PROGRAM detection
        if loc > self.COBOL_LARGE_PROGRAM_LOC and god_object_score < 0.5:
            self.patterns.append(DetectedPattern(
                pattern_type="LARGE_PROGRAM",
                program=program_name,
                severity="MEDIUM",
                confidence=min(loc / (self.COBOL_LARGE_PROGRAM_LOC * 2), 1.0),
                indicators=[f"LOC: {loc} (threshold: {self.COBOL_LARGE_PROGRAM_LOC})"],
                recommendation="Consider breaking into smaller modules"
            ))

        # BIG_BALL_OF_MUD detection
        complexity_estimate = (goto_count * 2) + (perform_count * 0.5) + (sections * 0.1)
        if goto_count > self.COBOL_BIG_BALL_GOTO and complexity_estimate > self.COBOL_BIG_BALL_COMPLEXITY:
            self.patterns.append(DetectedPattern(
                pattern_type="BIG_BALL_OF_MUD",
                program=program_name,
                severity="HIGH",
                confidence=0.85,
                indicators=[
                    f"GOTO count: {goto_count} (threshold: {self.COBOL_BIG_BALL_GOTO})",
                    f"Estimated complexity: {complexity_estimate:.1f} (threshold: {self.COBOL_BIG_BALL_COMPLEXITY})"
                ],
                recommendation="Major refactoring required to establish clear structure"
            ))

        # SPAGHETTI_CODE detection
        spaghetti_indicators = []
        if goto_count > self.COBOL_SPAGHETTI_GOTO:
            spaghetti_indicators.append(f"GOTO count: {goto_count} (threshold: {self.COBOL_SPAGHETTI_GOTO})")
        if nested_if > self.COBOL_SPAGHETTI_NESTED_IF:
            spaghetti_indicators.append(f"Nested IF depth: {nested_if} (threshold: {self.COBOL_SPAGHETTI_NESTED_IF})")

        if spaghetti_indicators:
            self.patterns.append(DetectedPattern(
                pattern_type="SPAGHETTI_CODE",
                program=program_name,
                severity="MEDIUM",
                confidence=0.75,
                indicators=spaghetti_indicators,
                recommendation="Refactor to eliminate GOTO statements and flatten conditionals"
            ))

        # TIGHT_COUPLING detection
        total_dependencies = call_count + copy_count
        if total_dependencies > self.COBOL_TIGHT_COUPLING_CALLS:
            self.patterns.append(DetectedPattern(
                pattern_type="TIGHT_COUPLING",
                program=program_name,
                severity="MEDIUM",
                confidence=min(total_dependencies / (self.COBOL_TIGHT_COUPLING_CALLS * 2), 1.0),
                indicators=[
                    f"CALL count: {call_count}",
                    f"COPY count: {copy_count}",
                    f"Total dependencies: {total_dependencies} (threshold: {self.COBOL_TIGHT_COUPLING_CALLS})"
                ],
                recommendation="Reduce dependencies through abstraction or interface segregation"
            ))

    def _detect_java_patterns(self, program: Dict[str, Any]) -> None:
        """Detect patterns in a Java class."""
        class_name = program.get("class_name", program.get("program", "UNKNOWN"))
        loc = program.get("loc", 0)
        methods = program.get("methods", 0)
        imports = program.get("imports", 0)
        complexity = program.get("cyclomatic_complexity", 0)
        nested_depth = program.get("max_nested_depth", 0)
        external_calls = program.get("external_calls", 0)

        # GOD_OBJECT detection
        god_object_indicators = []
        god_object_score = 0

        if loc > self.JAVA_GOD_OBJECT_LOC:
            god_object_indicators.append(f"LOC: {loc} (threshold: {self.JAVA_GOD_OBJECT_LOC})")
            god_object_score += 0.4

        if methods > self.JAVA_GOD_OBJECT_METHODS:
            god_object_indicators.append(f"Methods: {methods} (threshold: {self.JAVA_GOD_OBJECT_METHODS})")
            god_object_score += 0.4

        if complexity > 100:
            god_object_indicators.append(f"Cyclomatic complexity: {complexity} (high)")
            god_object_score += 0.2

        if god_object_score >= 0.5:
            self.patterns.append(DetectedPattern(
                pattern_type="GOD_OBJECT",
                program=class_name,
                severity="HIGH",
                confidence=min(god_object_score, 1.0),
                indicators=god_object_indicators,
                recommendation="Split into smaller, focused classes following Single Responsibility Principle"
            ))

        # LARGE_PROGRAM detection
        if loc > self.JAVA_LARGE_PROGRAM_LOC and god_object_score < 0.5:
            self.patterns.append(DetectedPattern(
                pattern_type="LARGE_PROGRAM",
                program=class_name,
                severity="MEDIUM",
                confidence=min(loc / (self.JAVA_LARGE_PROGRAM_LOC * 2), 1.0),
                indicators=[f"LOC: {loc} (threshold: {self.JAVA_LARGE_PROGRAM_LOC})"],
                recommendation="Extract methods into helper classes or services"
            ))

        # BIG_BALL_OF_MUD detection
        coupling_score = external_calls / max(loc, 1) if loc > 0 else 0
        if complexity > self.JAVA_BIG_BALL_COMPLEXITY and coupling_score > self.JAVA_BIG_BALL_COUPLING:
            self.patterns.append(DetectedPattern(
                pattern_type="BIG_BALL_OF_MUD",
                program=class_name,
                severity="HIGH",
                confidence=0.85,
                indicators=[
                    f"Cyclomatic complexity: {complexity} (threshold: {self.JAVA_BIG_BALL_COMPLEXITY})",
                    f"Coupling score: {coupling_score:.2f} (threshold: {self.JAVA_BIG_BALL_COUPLING})"
                ],
                recommendation="Major refactoring to establish clear architecture layers"
            ))

        # SPAGHETTI_CODE detection
        if nested_depth > self.JAVA_SPAGHETTI_NESTED:
            self.patterns.append(DetectedPattern(
                pattern_type="SPAGHETTI_CODE",
                program=class_name,
                severity="MEDIUM",
                confidence=0.75,
                indicators=[f"Max nested depth: {nested_depth} (threshold: {self.JAVA_SPAGHETTI_NESTED})"],
                recommendation="Flatten nested conditionals using early returns or strategy pattern"
            ))

        # TIGHT_COUPLING detection
        if imports > self.JAVA_TIGHT_COUPLING_IMPORTS:
            self.patterns.append(DetectedPattern(
                pattern_type="TIGHT_COUPLING",
                program=class_name,
                severity="MEDIUM",
                confidence=min(imports / (self.JAVA_TIGHT_COUPLING_IMPORTS * 2), 1.0),
                indicators=[f"Import count: {imports} (threshold: {self.JAVA_TIGHT_COUPLING_IMPORTS})"],
                recommendation="Use dependency injection and reduce direct dependencies"
            ))

    def _build_result(self) -> Dict[str, Any]:
        """Build the final result dictionary."""
        patterns_data = []
        god_objects = 0
        big_ball_of_mud = 0
        large_programs = 0
        tight_coupling = 0
        spaghetti_code = 0

        for p in self.patterns:
            patterns_data.append({
                "pattern_type": p.pattern_type,
                "program": p.program,
                "severity": p.severity,
                "confidence": p.confidence,
                "indicators": p.indicators,
                "recommendation": p.recommendation
            })

            if p.pattern_type == "GOD_OBJECT":
                god_objects += 1
            elif p.pattern_type == "BIG_BALL_OF_MUD":
                big_ball_of_mud += 1
            elif p.pattern_type == "LARGE_PROGRAM":
                large_programs += 1
            elif p.pattern_type == "TIGHT_COUPLING":
                tight_coupling += 1
            elif p.pattern_type == "SPAGHETTI_CODE":
                spaghetti_code += 1

        return {
            "patterns": patterns_data,
            "summary": {
                "god_objects": god_objects,
                "big_ball_of_mud": big_ball_of_mud,
                "large_programs": large_programs,
                "tight_coupling": tight_coupling,
                "spaghetti_code": spaghetti_code,
                "total_patterns": len(self.patterns)
            }
        }
