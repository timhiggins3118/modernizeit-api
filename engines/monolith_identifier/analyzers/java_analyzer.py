"""
Java Static Analyzer for Monolith Identifier

Analyzes Java source files for monolithic pattern indicators:
- Lines of code (LOC)
- Class count
- Method count
- Import count
- Inheritance depth
- Cyclomatic complexity (estimated)
- Nested depth
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ClassMetrics:
    """Metrics for a single Java class."""
    class_name: str
    file_path: str
    package: str = ""
    loc: int = 0
    methods: int = 0
    fields: int = 0
    imports: int = 0
    extends: Optional[str] = None
    implements: List[str] = field(default_factory=list)
    inner_classes: int = 0
    cyclomatic_complexity: int = 0
    max_nested_depth: int = 0
    try_catch_blocks: int = 0
    external_calls: int = 0


class JavaStaticAnalyzer:
    """
    Static analyzer for Java source code.

    Extracts metrics relevant to monolith pattern detection.
    """

    def __init__(self):
        self.classes: List[ClassMetrics] = []

    def analyze_directory(self, source_path: str) -> None:
        """
        Analyze all Java files in a directory.

        Args:
            source_path: Path to directory containing Java files
        """
        source_dir = Path(source_path)

        # Find all Java files
        java_files = list(source_dir.rglob('*.java'))

        # Analyze each file
        for java_file in java_files:
            try:
                metrics = self._analyze_file(java_file)
                if metrics:
                    self.classes.append(metrics)
            except Exception as e:
                print(f"Warning: Could not analyze {java_file}: {e}")

    def _analyze_file(self, file_path: Path) -> Optional[ClassMetrics]:
        """
        Analyze a single Java file.

        Args:
            file_path: Path to Java file

        Returns:
            ClassMetrics for the file
        """
        content = file_path.read_text(errors='ignore')
        lines = content.split('\n')

        # Get class name
        class_name = self._extract_class_name(content)
        if not class_name:
            class_name = file_path.stem

        metrics = ClassMetrics(
            class_name=class_name,
            file_path=str(file_path)
        )

        # Extract package
        metrics.package = self._extract_package(content)

        # Count lines of code
        metrics.loc = self._count_loc(lines)

        # Count methods
        metrics.methods = self._count_methods(content)

        # Count fields
        metrics.fields = self._count_fields(content)

        # Count imports
        metrics.imports = self._count_imports(content)

        # Extract inheritance
        metrics.extends = self._extract_extends(content)
        metrics.implements = self._extract_implements(content)

        # Count inner classes
        metrics.inner_classes = self._count_inner_classes(content)

        # Estimate cyclomatic complexity
        metrics.cyclomatic_complexity = self._estimate_complexity(content)

        # Calculate max nested depth
        metrics.max_nested_depth = self._calculate_nested_depth(content)

        # Count try-catch blocks
        metrics.try_catch_blocks = self._count_try_catch(content)

        # Count external method calls
        metrics.external_calls = self._count_external_calls(content)

        return metrics

    def _extract_class_name(self, content: str) -> Optional[str]:
        """Extract the main class name."""
        pattern = r'(?:public\s+)?(?:abstract\s+)?(?:final\s+)?class\s+(\w+)'
        match = re.search(pattern, content)
        return match.group(1) if match else None

    def _extract_package(self, content: str) -> str:
        """Extract package declaration."""
        pattern = r'package\s+([\w.]+)\s*;'
        match = re.search(pattern, content)
        return match.group(1) if match else ""

    def _count_loc(self, lines: List[str]) -> int:
        """Count lines of code (excluding blanks and comments)."""
        count = 0
        in_block_comment = False

        for line in lines:
            stripped = line.strip()

            # Skip blank lines
            if not stripped:
                continue

            # Handle block comments
            if '/*' in stripped:
                in_block_comment = True
            if '*/' in stripped:
                in_block_comment = False
                continue
            if in_block_comment:
                continue

            # Skip single-line comments
            if stripped.startswith('//'):
                continue

            count += 1

        return count

    def _count_methods(self, content: str) -> int:
        """Count method declarations."""
        # Match method signatures (simplified)
        pattern = r'(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+\w+\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{'
        return len(re.findall(pattern, content))

    def _count_fields(self, content: str) -> int:
        """Count field declarations."""
        # Match field declarations
        pattern = r'(?:private|protected|public)\s+(?:static\s+)?(?:final\s+)?[\w<>\[\]]+\s+\w+\s*[;=]'
        return len(re.findall(pattern, content))

    def _count_imports(self, content: str) -> int:
        """Count import statements."""
        pattern = r'^import\s+'
        return len(re.findall(pattern, content, re.MULTILINE))

    def _extract_extends(self, content: str) -> Optional[str]:
        """Extract parent class."""
        pattern = r'class\s+\w+\s+extends\s+(\w+)'
        match = re.search(pattern, content)
        return match.group(1) if match else None

    def _extract_implements(self, content: str) -> List[str]:
        """Extract implemented interfaces."""
        pattern = r'implements\s+([\w\s,]+?)(?:\s*\{|extends)'
        match = re.search(pattern, content)
        if match:
            interfaces = match.group(1)
            return [i.strip() for i in interfaces.split(',')]
        return []

    def _count_inner_classes(self, content: str) -> int:
        """Count inner class declarations."""
        # Count all class declarations minus 1 (the outer class)
        pattern = r'\bclass\s+\w+'
        count = len(re.findall(pattern, content))
        return max(0, count - 1)

    def _estimate_complexity(self, content: str) -> int:
        """
        Estimate cyclomatic complexity.

        Based on counting decision points:
        - if, else if
        - for, while, do
        - case
        - catch
        - &&, ||
        - ?:
        """
        complexity = 1  # Base complexity

        # Decision points
        patterns = [
            (r'\bif\s*\(', 1),
            (r'\belse\s+if\s*\(', 1),
            (r'\bfor\s*\(', 1),
            (r'\bwhile\s*\(', 1),
            (r'\bdo\s*\{', 1),
            (r'\bcase\s+', 1),
            (r'\bcatch\s*\(', 1),
            (r'&&', 1),
            (r'\|\|', 1),
            (r'\?[^?]', 1),  # Ternary operator
        ]

        for pattern, weight in patterns:
            complexity += len(re.findall(pattern, content)) * weight

        return complexity

    def _calculate_nested_depth(self, content: str) -> int:
        """Calculate maximum nesting depth."""
        max_depth = 0
        current_depth = 0

        for char in content:
            if char == '{':
                current_depth += 1
                if current_depth > max_depth:
                    max_depth = current_depth
            elif char == '}':
                current_depth -= 1

        return max_depth

    def _count_try_catch(self, content: str) -> int:
        """Count try-catch blocks."""
        pattern = r'\btry\s*\{'
        return len(re.findall(pattern, content))

    def _count_external_calls(self, content: str) -> int:
        """
        Count external method calls (calls on objects).

        This is an approximation based on patterns like:
        - object.method()
        - ClassName.staticMethod()
        """
        pattern = r'\w+\.\w+\s*\('
        return len(re.findall(pattern, content))

    def get_analysis_result(self) -> Dict[str, Any]:
        """
        Get the complete analysis result.

        Returns:
            Dictionary with classes and summary
        """
        classes_data = []
        total_loc = 0
        total_methods = 0
        total_fields = 0
        total_imports = 0
        total_complexity = 0
        max_loc = 0
        max_methods = 0
        max_complexity = 0
        max_nested_depth = 0

        for c in self.classes:
            classes_data.append({
                "class_name": c.class_name,
                "file_path": c.file_path,
                "package": c.package,
                "loc": c.loc,
                "methods": c.methods,
                "fields": c.fields,
                "imports": c.imports,
                "extends": c.extends,
                "implements": c.implements,
                "inner_classes": c.inner_classes,
                "cyclomatic_complexity": c.cyclomatic_complexity,
                "max_nested_depth": c.max_nested_depth,
                "try_catch_blocks": c.try_catch_blocks,
                "external_calls": c.external_calls
            })

            total_loc += c.loc
            total_methods += c.methods
            total_fields += c.fields
            total_imports += c.imports
            total_complexity += c.cyclomatic_complexity

            if c.loc > max_loc:
                max_loc = c.loc
            if c.methods > max_methods:
                max_methods = c.methods
            if c.cyclomatic_complexity > max_complexity:
                max_complexity = c.cyclomatic_complexity
            if c.max_nested_depth > max_nested_depth:
                max_nested_depth = c.max_nested_depth

        class_count = len(self.classes)

        return {
            "programs": classes_data,  # Use "programs" for consistency with COBOL
            "summary": {
                "total_programs": class_count,  # Use "programs" for consistency
                "total_classes": class_count,
                "total_loc": total_loc,
                "average_loc": total_loc // class_count if class_count > 0 else 0,
                "max_loc": max_loc,
                "total_methods": total_methods,
                "average_methods": total_methods // class_count if class_count > 0 else 0,
                "max_methods": max_methods,
                "total_fields": total_fields,
                "total_imports": total_imports,
                "total_complexity": total_complexity,
                "average_complexity": total_complexity // class_count if class_count > 0 else 0,
                "max_complexity": max_complexity,
                "max_nested_depth": max_nested_depth
            }
        }
