"""
Java Analyzer for Dependencies

Parses Java source files to extract:
- Import statements (class dependencies)
- Class/interface inheritance (extends, implements)
- Method calls (inter-class calls)
- Field references
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class ImportDependency:
    """An import statement dependency."""
    package: str
    class_name: str
    line: int
    is_static: bool = False
    is_wildcard: bool = False


@dataclass
class InheritanceDependency:
    """An inheritance relationship (extends/implements)."""
    parent: str
    relationship: str  # "extends" or "implements"
    line: int


@dataclass
class MethodCallDependency:
    """A method call to another class."""
    target_class: str
    method_name: str
    line: int


@dataclass
class FieldDependency:
    """A field that references another class."""
    field_name: str
    field_type: str
    line: int


@dataclass
class JavaClassAnalysis:
    """Analysis result for a single Java class."""
    class_name: str
    package: str
    file_path: str
    class_type: str  # "class", "interface", "enum", "record"
    imports: List[ImportDependency] = field(default_factory=list)
    inheritance: List[InheritanceDependency] = field(default_factory=list)
    method_calls: List[MethodCallDependency] = field(default_factory=list)
    fields: List[FieldDependency] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    lines_of_code: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_name": self.class_name,
            "package": self.package,
            "file_path": self.file_path,
            "class_type": self.class_type,
            "imports": [
                {
                    "package": i.package,
                    "class": i.class_name,
                    "line": i.line,
                    "is_static": i.is_static,
                    "is_wildcard": i.is_wildcard
                }
                for i in self.imports
            ],
            "inheritance": [
                {"parent": i.parent, "relationship": i.relationship, "line": i.line}
                for i in self.inheritance
            ],
            "method_calls": [
                {"target_class": m.target_class, "method": m.method_name, "line": m.line}
                for m in self.method_calls
            ],
            "fields": [
                {"name": f.field_name, "type": f.field_type, "line": f.line}
                for f in self.fields
            ],
            "methods": self.methods,
            "lines_of_code": self.lines_of_code,
            "method_count": len(self.methods),
            "field_count": len(self.fields)
        }


class JavaAnalyzer:
    """
    Analyzer for Java source code dependencies.

    Uses regex-based parsing to extract dependencies from Java source.
    """

    # Regex patterns for Java statements
    PACKAGE_PATTERN = re.compile(
        r'^\s*package\s+([\w.]+)\s*;',
        re.MULTILINE
    )

    IMPORT_PATTERN = re.compile(
        r'^\s*import\s+(static\s+)?([\w.]+)(\.\*)?;',
        re.MULTILINE
    )

    CLASS_PATTERN = re.compile(
        r'^\s*(?:public\s+|private\s+|protected\s+)?(?:abstract\s+|final\s+)?(class|interface|enum|record)\s+(\w+)',
        re.MULTILINE
    )

    EXTENDS_PATTERN = re.compile(
        r'\bextends\s+([\w.]+)',
        re.MULTILINE
    )

    IMPLEMENTS_PATTERN = re.compile(
        r'\bimplements\s+([\w.,\s]+)',
        re.MULTILINE
    )

    FIELD_PATTERN = re.compile(
        r'^\s*(?:private|protected|public)\s+(?:static\s+)?(?:final\s+)?([\w<>\[\],\s]+)\s+(\w+)\s*[;=]',
        re.MULTILINE
    )

    METHOD_PATTERN = re.compile(
        r'^\s*(?:@\w+\s*)*(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:<[\w,\s]+>\s+)?([\w<>\[\]]+)\s+(\w+)\s*\(',
        re.MULTILINE
    )

    # Method call pattern: ClassName.methodName( or variable.methodName(
    METHOD_CALL_PATTERN = re.compile(
        r'(\w+)\.(\w+)\s*\(',
        re.MULTILINE
    )

    # New instance pattern: new ClassName(
    NEW_INSTANCE_PATTERN = re.compile(
        r'\bnew\s+([\w.]+)\s*\(',
        re.MULTILINE
    )

    def __init__(self):
        self.analyses: List[JavaClassAnalysis] = []

    def analyze_directory(self, source_dir: str) -> List[JavaClassAnalysis]:
        """
        Analyze all Java files in a directory.

        Args:
            source_dir: Path to directory containing Java files

        Returns:
            List of JavaClassAnalysis results
        """
        source_path = Path(source_dir)
        self.analyses = []

        # Find all Java files
        java_files = list(source_path.rglob('*.java'))

        # Analyze each file
        for java_file in java_files:
            analysis = self.analyze_file(str(java_file))
            if analysis:
                self.analyses.append(analysis)

        return self.analyses

    def analyze_file(self, file_path: str) -> Optional[JavaClassAnalysis]:
        """
        Analyze a single Java file.

        Args:
            file_path: Path to Java file

        Returns:
            JavaClassAnalysis or None if file cannot be read
        """
        try:
            path = Path(file_path)
            content = path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')

            # Get package
            package = ""
            package_match = self.PACKAGE_PATTERN.search(content)
            if package_match:
                package = package_match.group(1)

            # Get class name and type
            class_name = path.stem
            class_type = "class"
            class_match = self.CLASS_PATTERN.search(content)
            if class_match:
                class_type = class_match.group(1)
                class_name = class_match.group(2)

            analysis = JavaClassAnalysis(
                class_name=class_name,
                package=package,
                file_path=str(path),
                class_type=class_type,
                lines_of_code=len([l for l in lines if l.strip() and not l.strip().startswith('//')])
            )

            # Parse imports
            for match in self.IMPORT_PATTERN.finditer(content):
                is_static = bool(match.group(1))
                full_import = match.group(2)
                is_wildcard = bool(match.group(3))

                # Split package and class
                if '.' in full_import:
                    parts = full_import.rsplit('.', 1)
                    pkg = parts[0]
                    cls = parts[1] if not is_wildcard else "*"
                else:
                    pkg = ""
                    cls = full_import

                line_num = content[:match.start()].count('\n') + 1

                analysis.imports.append(ImportDependency(
                    package=pkg,
                    class_name=cls,
                    line=line_num,
                    is_static=is_static,
                    is_wildcard=is_wildcard
                ))

            # Parse inheritance (extends)
            extends_match = self.EXTENDS_PATTERN.search(content)
            if extends_match:
                line_num = content[:extends_match.start()].count('\n') + 1
                analysis.inheritance.append(InheritanceDependency(
                    parent=extends_match.group(1),
                    relationship="extends",
                    line=line_num
                ))

            # Parse inheritance (implements)
            implements_match = self.IMPLEMENTS_PATTERN.search(content)
            if implements_match:
                line_num = content[:implements_match.start()].count('\n') + 1
                interfaces = [i.strip() for i in implements_match.group(1).split(',')]
                for iface in interfaces:
                    if iface:
                        analysis.inheritance.append(InheritanceDependency(
                            parent=iface,
                            relationship="implements",
                            line=line_num
                        ))

            # Parse fields
            for match in self.FIELD_PATTERN.finditer(content):
                field_type = match.group(1).strip()
                field_name = match.group(2)
                line_num = content[:match.start()].count('\n') + 1

                # Skip primitive types
                if not self._is_primitive(field_type):
                    analysis.fields.append(FieldDependency(
                        field_name=field_name,
                        field_type=field_type,
                        line=line_num
                    ))

            # Parse methods
            for match in self.METHOD_PATTERN.finditer(content):
                method_name = match.group(2)
                analysis.methods.append(method_name)

            # Parse method calls (simplified - looks for ClassName.method patterns)
            seen_calls: Set[str] = set()
            for match in self.METHOD_CALL_PATTERN.finditer(content):
                target = match.group(1)
                method = match.group(2)

                # Skip common non-class targets
                if target.lower() in ('this', 'super', 'system', 'string', 'integer', 'double', 'boolean', 'list', 'map', 'set'):
                    continue

                # Skip if starts with lowercase (likely variable, not class)
                if target[0].islower() and target not in ('parent',):
                    continue

                call_key = f"{target}.{method}"
                if call_key not in seen_calls:
                    seen_calls.add(call_key)
                    line_num = content[:match.start()].count('\n') + 1
                    analysis.method_calls.append(MethodCallDependency(
                        target_class=target,
                        method_name=method,
                        line=line_num
                    ))

            return analysis

        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return None

    def _is_primitive(self, type_name: str) -> bool:
        """Check if a type is a primitive or common type."""
        primitives = {
            'int', 'long', 'short', 'byte', 'float', 'double', 'boolean', 'char',
            'Integer', 'Long', 'Short', 'Byte', 'Float', 'Double', 'Boolean', 'Character',
            'String', 'Object', 'void'
        }
        # Strip generics
        base_type = type_name.split('<')[0].strip()
        return base_type in primitives

    def get_all_dependencies(self) -> Dict[str, Any]:
        """
        Get aggregated dependency data from all analyzed classes.

        Returns:
            Dictionary with classes list and summary statistics
        """
        classes = [a.to_dict() for a in self.analyses]

        # Calculate totals
        total_imports = sum(len(a.imports) for a in self.analyses)
        total_inheritance = sum(len(a.inheritance) for a in self.analyses)
        total_method_calls = sum(len(a.method_calls) for a in self.analyses)
        total_fields = sum(len(a.fields) for a in self.analyses)
        total_methods = sum(len(a.methods) for a in self.analyses)

        return {
            "classes": classes,
            "summary": {
                "total_classes": len(classes),
                "total_imports": total_imports,
                "total_inheritance": total_inheritance,
                "total_method_calls": total_method_calls,
                "total_fields": total_fields,
                "total_methods": total_methods,
                "total_dependencies": total_imports + total_inheritance + total_method_calls
            }
        }
