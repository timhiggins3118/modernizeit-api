"""
Java Parser Utility

Parses Java source files to extract structure information for refactoring analysis.
Uses regex-based parsing (simpler than full AST for our needs).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class JavaField:
    """Represents a Java field declaration."""
    name: str
    java_type: str
    modifiers: List[str]
    line_number: int
    comment: Optional[str] = None
    cobol_name: Optional[str] = None  # From comment like "// L:123 COBOL-NAME"
    is_array: bool = False
    array_size: Optional[int] = None


@dataclass
class JavaMethod:
    """Represents a Java method."""
    name: str
    return_type: str
    modifiers: List[str]
    parameters: List[Tuple[str, str]]  # (type, name)
    start_line: int
    end_line: int
    cobol_paragraph: Optional[str] = None  # From comment like "// L:123 PARAGRAPH-NAME"
    calls: List[str] = field(default_factory=list)  # Methods this calls
    complexity: int = 1  # Cyclomatic complexity estimate
    has_goto_comment: bool = False


@dataclass
class JavaInnerClass:
    """Represents a Java inner class."""
    name: str
    modifiers: List[str]
    start_line: int
    end_line: int
    fields: List[JavaField] = field(default_factory=list)
    cobol_record: Optional[str] = None


@dataclass
class JavaClass:
    """Represents a parsed Java class."""
    name: str
    package: Optional[str]
    file_path: str
    total_lines: int
    fields: List[JavaField] = field(default_factory=list)
    methods: List[JavaMethod] = field(default_factory=list)
    inner_classes: List[JavaInnerClass] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)


class JavaParser:
    """
    Parser for Java source files.

    Extracts structural information needed for refactoring analysis:
    - Fields with types, names, and COBOL references
    - Methods with parameters, calls, and complexity
    - Inner classes
    - Import statements
    """

    # Regex patterns
    PACKAGE_PATTERN = re.compile(r'^package\s+([\w.]+)\s*;')
    IMPORT_PATTERN = re.compile(r'^import\s+([\w.*]+)\s*;')
    CLASS_PATTERN = re.compile(r'(public|private|protected)?\s*(static)?\s*class\s+(\w+)')
    FIELD_PATTERN = re.compile(
        r'(public|private|protected)?\s*(static)?\s*(final)?\s*'
        r'([\w<>\[\],\s]+)\s+(\w+)\s*(=.*)?;'
    )
    METHOD_PATTERN = re.compile(
        r'(public|private|protected)?\s*(static)?\s*([\w<>\[\]]+)\s+(\w+)\s*\(([^)]*)\)'
    )
    ARRAY_INIT_PATTERN = re.compile(r'new\s+\w+\[(\d+)\]')
    COBOL_COMMENT_PATTERN = re.compile(r'//\s*L:(\d+)\s+(.+)$')
    GOTO_COMMENT_PATTERN = re.compile(r'//.*GO\s*TO', re.IGNORECASE)
    METHOD_CALL_PATTERN = re.compile(r'(\w+)\s*\(')

    def __init__(self):
        pass

    def parse_file(self, file_path: str) -> JavaClass:
        """
        Parse a Java source file.

        Args:
            file_path: Path to Java file

        Returns:
            JavaClass with extracted structure
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Java file not found: {file_path}")

        content = path.read_text()
        lines = content.split('\n')

        java_class = JavaClass(
            name=path.stem,
            package=None,
            file_path=str(path),
            total_lines=len(lines),
        )

        # Parse package
        java_class.package = self._extract_package(lines)

        # Parse imports
        java_class.imports = self._extract_imports(lines)

        # Parse fields
        java_class.fields = self._extract_fields(lines)

        # Parse methods
        java_class.methods = self._extract_methods(lines)

        # Parse inner classes
        java_class.inner_classes = self._extract_inner_classes(lines)

        return java_class

    def _extract_package(self, lines: List[str]) -> Optional[str]:
        """Extract package declaration."""
        for line in lines[:20]:  # Package is always near top
            match = self.PACKAGE_PATTERN.match(line.strip())
            if match:
                return match.group(1)
        return None

    def _extract_imports(self, lines: List[str]) -> List[str]:
        """Extract import statements."""
        imports = []
        for line in lines[:100]:  # Imports are near top
            match = self.IMPORT_PATTERN.match(line.strip())
            if match:
                imports.append(match.group(1))
        return imports

    def _extract_fields(self, lines: List[str]) -> List[JavaField]:
        """Extract field declarations."""
        fields = []
        in_method = False
        brace_depth = 0
        class_depth = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Track brace depth to know if we're in class body vs method body
            brace_depth += stripped.count('{') - stripped.count('}')

            # Track class depth
            if self.CLASS_PATTERN.search(stripped):
                class_depth += 1

            # Skip if inside a method (brace depth > 1 after class started)
            if 'void ' in stripped or self.METHOD_PATTERN.match(stripped):
                in_method = True

            if brace_depth == 0:
                in_method = False
                class_depth = max(0, class_depth - 1)

            # Only look for fields at class level (brace_depth == 1, class_depth == 1)
            if in_method or brace_depth != 1:
                continue

            # Look for field declarations
            match = self.FIELD_PATTERN.match(stripped)
            if match and 'class ' not in stripped and '(' not in stripped.split('=')[0]:
                modifiers = [m for m in [match.group(1), match.group(2), match.group(3)] if m]
                java_type = match.group(4).strip()
                name = match.group(5)

                # Check for array
                is_array = '[]' in java_type or 'new ' in stripped and '[' in stripped
                array_size = None
                if is_array:
                    size_match = self.ARRAY_INIT_PATTERN.search(stripped)
                    if size_match:
                        array_size = int(size_match.group(1))

                # Check for COBOL comment
                cobol_name = None
                cobol_match = self.COBOL_COMMENT_PATTERN.search(stripped)
                if cobol_match:
                    cobol_name = cobol_match.group(2).strip()

                fields.append(JavaField(
                    name=name,
                    java_type=java_type,
                    modifiers=modifiers,
                    line_number=i,
                    comment=stripped.split('//')[-1].strip() if '//' in stripped else None,
                    cobol_name=cobol_name,
                    is_array=is_array,
                    array_size=array_size,
                ))

        return fields

    def _extract_methods(self, lines: List[str]) -> List[JavaMethod]:
        """Extract method declarations with complexity analysis."""
        methods = []
        current_method = None
        brace_depth = 0
        method_start_depth = 0
        method_content = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Look for method start
            if current_method is None:
                match = self.METHOD_PATTERN.match(stripped)
                if match and '{' in line:  # Method with opening brace
                    modifiers = [m for m in [match.group(1), match.group(2)] if m]
                    return_type = match.group(3)
                    name = match.group(4)
                    params_str = match.group(5)

                    # Parse parameters
                    parameters = []
                    if params_str.strip():
                        for param in params_str.split(','):
                            parts = param.strip().split()
                            if len(parts) >= 2:
                                parameters.append((parts[-2], parts[-1]))

                    # Check for COBOL paragraph comment
                    cobol_paragraph = None
                    cobol_match = self.COBOL_COMMENT_PATTERN.search(stripped)
                    if cobol_match:
                        cobol_paragraph = cobol_match.group(2).strip()

                    current_method = JavaMethod(
                        name=name,
                        return_type=return_type,
                        modifiers=modifiers,
                        parameters=parameters,
                        start_line=i,
                        end_line=i,
                        cobol_paragraph=cobol_paragraph,
                    )
                    method_start_depth = brace_depth
                    method_content = [stripped]

            # Track braces
            brace_depth += stripped.count('{') - stripped.count('}')

            # If in method, collect content
            if current_method is not None:
                if stripped not in method_content:
                    method_content.append(stripped)

                # Check for GO TO comment
                if self.GOTO_COMMENT_PATTERN.search(stripped):
                    current_method.has_goto_comment = True

                # Count complexity (if, for, while, case, &&, ||)
                current_method.complexity += stripped.count(' if ')
                current_method.complexity += stripped.count(' if(')
                current_method.complexity += stripped.count(' for ')
                current_method.complexity += stripped.count(' for(')
                current_method.complexity += stripped.count(' while ')
                current_method.complexity += stripped.count(' while(')
                current_method.complexity += stripped.count(' case ')
                current_method.complexity += stripped.count(' && ')
                current_method.complexity += stripped.count(' || ')

                # Check if method ended
                if brace_depth <= method_start_depth:
                    current_method.end_line = i

                    # Extract method calls
                    content_str = ' '.join(method_content)
                    calls = self.METHOD_CALL_PATTERN.findall(content_str)
                    # Filter out keywords and common constructs
                    keywords = {'if', 'for', 'while', 'switch', 'catch', 'new', 'return', 'throw'}
                    current_method.calls = [c for c in calls if c not in keywords and c != current_method.name]

                    methods.append(current_method)
                    current_method = None
                    method_content = []

        return methods

    def _extract_inner_classes(self, lines: List[str]) -> List[JavaInnerClass]:
        """Extract inner class declarations."""
        inner_classes = []
        class_depth = 0
        current_inner = None
        brace_depth = 0
        inner_start_depth = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Track class declarations
            class_match = self.CLASS_PATTERN.search(stripped)
            if class_match:
                class_depth += 1

                # Inner class is at depth > 1
                if class_depth > 1 and current_inner is None:
                    modifiers = [m for m in [class_match.group(1), class_match.group(2)] if m]
                    name = class_match.group(3)

                    # Check for COBOL record comment
                    cobol_record = None
                    cobol_match = self.COBOL_COMMENT_PATTERN.search(stripped)
                    if cobol_match:
                        cobol_record = cobol_match.group(2).strip()

                    current_inner = JavaInnerClass(
                        name=name,
                        modifiers=modifiers,
                        start_line=i,
                        end_line=i,
                        cobol_record=cobol_record,
                    )
                    inner_start_depth = brace_depth

            # Track braces
            brace_depth += stripped.count('{') - stripped.count('}')

            # Check for class end
            if brace_depth < class_depth:
                class_depth = brace_depth

                if current_inner is not None and brace_depth <= inner_start_depth:
                    current_inner.end_line = i
                    inner_classes.append(current_inner)
                    current_inner = None

        return inner_classes

    def get_field_prefix_groups(self, fields: List[JavaField]) -> Dict[str, List[JavaField]]:
        """
        Group fields by common prefixes.

        Useful for identifying cohesive field groups that might belong
        in separate classes.
        """
        # Extract prefixes (first word before camelCase or underscore)
        prefix_pattern = re.compile(r'^([a-z]+)')
        groups: Dict[str, List[JavaField]] = {}

        for field in fields:
            match = prefix_pattern.match(field.name)
            if match:
                prefix = match.group(1)
                if len(prefix) >= 3:  # Only meaningful prefixes
                    if prefix not in groups:
                        groups[prefix] = []
                    groups[prefix].append(field)

        # Only return groups with multiple fields
        return {k: v for k, v in groups.items() if len(v) >= 3}

    def get_method_prefix_groups(self, methods: List[JavaMethod]) -> Dict[str, List[JavaMethod]]:
        """
        Group methods by COBOL paragraph number prefix.

        Methods like processControl_200_010, processDed_200_100 share prefix "200".
        """
        prefix_pattern = re.compile(r'_(\d+)_')
        groups: Dict[str, List[JavaMethod]] = {}

        for method in methods:
            matches = prefix_pattern.findall(method.name)
            if matches:
                prefix = matches[0]  # First number group
                if prefix not in groups:
                    groups[prefix] = []
                groups[prefix].append(method)

        return {k: v for k, v in groups.items() if len(v) >= 2}

    def analyze_complexity(self, java_class: JavaClass) -> Dict:
        """
        Analyze overall complexity of a Java class.

        Returns metrics useful for refactoring decisions.
        """
        total_complexity = sum(m.complexity for m in java_class.methods)
        goto_methods = [m for m in java_class.methods if m.has_goto_comment]
        high_complexity_methods = [m for m in java_class.methods if m.complexity > 10]

        # BigDecimal fields that might be simple counters
        bigdecimal_fields = [f for f in java_class.fields if 'BigDecimal' in f.java_type]

        # Array fields
        array_fields = [f for f in java_class.fields if f.is_array]

        return {
            "total_lines": java_class.total_lines,
            "field_count": len(java_class.fields),
            "method_count": len(java_class.methods),
            "inner_class_count": len(java_class.inner_classes),
            "total_complexity": total_complexity,
            "avg_method_complexity": total_complexity / max(1, len(java_class.methods)),
            "goto_method_count": len(goto_methods),
            "high_complexity_method_count": len(high_complexity_methods),
            "bigdecimal_field_count": len(bigdecimal_fields),
            "array_field_count": len(array_fields),
            "needs_refactoring": (
                java_class.total_lines > 1000 or
                len(java_class.fields) > 100 or
                len(goto_methods) > 0 or
                len(high_complexity_methods) > 5
            ),
        }
