"""
Static Analyzer for COBOL Dependencies

Parses COBOL source files to extract:
- CALL statements (program-to-program calls)
- COPY statements (copybook inclusions)
- FILE I/O operations (READ, WRITE, REWRITE, DELETE)
- DATABASE operations (EXEC SQL)
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CallDependency:
    """A CALL statement dependency."""
    target: str
    line: int
    call_type: str = "CALL"  # CALL, CALL USING, etc.


@dataclass
class CopyDependency:
    """A COPY statement dependency."""
    copybook: str
    line: int
    replacing: Optional[str] = None


@dataclass
class FileIODependency:
    """A file I/O operation."""
    operation: str  # READ, WRITE, REWRITE, DELETE, OPEN, CLOSE
    file_name: str
    line: int


@dataclass
class DatabaseDependency:
    """A database operation."""
    operation: str  # SELECT, INSERT, UPDATE, DELETE
    table: str
    line: int


@dataclass
class ProgramAnalysis:
    """Analysis result for a single program."""
    program: str
    file_path: str
    calls: List[CallDependency] = field(default_factory=list)
    copies: List[CopyDependency] = field(default_factory=list)
    file_io: List[FileIODependency] = field(default_factory=list)
    database: List[DatabaseDependency] = field(default_factory=list)
    lines_of_code: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "program": self.program,
            "file_path": self.file_path,
            "calls": [
                {"target": c.target, "line": c.line, "type": c.call_type}
                for c in self.calls
            ],
            "copies": [
                {"copybook": c.copybook, "line": c.line, "replacing": c.replacing}
                for c in self.copies
            ],
            "file_io": [
                {"operation": f.operation, "file": f.file_name, "line": f.line}
                for f in self.file_io
            ],
            "database": [
                {"operation": d.operation, "table": d.table, "line": d.line}
                for d in self.database
            ],
            "lines_of_code": self.lines_of_code
        }


class StaticAnalyzer:
    """
    Static analyzer for COBOL source code dependencies.

    Uses regex-based parsing to extract dependencies from COBOL source.
    """

    # Regex patterns for COBOL statements
    CALL_PATTERN = re.compile(
        r'^\s*CALL\s+["\']?(\w+)["\']?',
        re.IGNORECASE | re.MULTILINE
    )

    COPY_PATTERN = re.compile(
        r'^\s*COPY\s+([^\s.]+)',
        re.IGNORECASE | re.MULTILINE
    )

    COPY_REPLACING_PATTERN = re.compile(
        r'^\s*COPY\s+([^\s.]+)\s+REPLACING\s+(.+)',
        re.IGNORECASE | re.MULTILINE
    )

    # File I/O patterns
    READ_PATTERN = re.compile(
        r'^\s*READ\s+(\S+)',
        re.IGNORECASE | re.MULTILINE
    )

    WRITE_PATTERN = re.compile(
        r'^\s*WRITE\s+(\S+)',
        re.IGNORECASE | re.MULTILINE
    )

    REWRITE_PATTERN = re.compile(
        r'^\s*REWRITE\s+(\S+)',
        re.IGNORECASE | re.MULTILINE
    )

    DELETE_PATTERN = re.compile(
        r'^\s*DELETE\s+(\S+)',
        re.IGNORECASE | re.MULTILINE
    )

    OPEN_PATTERN = re.compile(
        r'^\s*OPEN\s+(INPUT|OUTPUT|I-O|EXTEND)\s+(\S+)',
        re.IGNORECASE | re.MULTILINE
    )

    # Database patterns (EXEC SQL)
    EXEC_SQL_PATTERN = re.compile(
        r'EXEC\s+SQL\s+(SELECT|INSERT|UPDATE|DELETE)\s+.*?(FROM|INTO)\s+(\w+)',
        re.IGNORECASE | re.DOTALL
    )

    def __init__(self):
        self.analyses: List[ProgramAnalysis] = []

    def analyze_directory(self, source_dir: str) -> List[ProgramAnalysis]:
        """
        Analyze all COBOL files in a directory.

        Args:
            source_dir: Path to directory containing COBOL files

        Returns:
            List of ProgramAnalysis results
        """
        source_path = Path(source_dir)
        self.analyses = []

        # Find all COBOL files
        cobol_extensions = ['.cbl', '.CBL', '.cob', '.COB', '.cobol', '.COBOL']
        cobol_files = []

        for ext in cobol_extensions:
            cobol_files.extend(source_path.rglob(f'*{ext}'))

        # Analyze each file
        for cobol_file in cobol_files:
            analysis = self.analyze_file(str(cobol_file))
            if analysis:
                self.analyses.append(analysis)

        return self.analyses

    def analyze_file(self, file_path: str) -> Optional[ProgramAnalysis]:
        """
        Analyze a single COBOL file.

        Args:
            file_path: Path to COBOL file

        Returns:
            ProgramAnalysis or None if file cannot be read
        """
        try:
            path = Path(file_path)
            content = path.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')

            # Get program name from filename
            program_name = path.stem

            analysis = ProgramAnalysis(
                program=program_name,
                file_path=str(path),
                lines_of_code=len([l for l in lines if l.strip() and not self._is_comment(l)])
            )

            # Parse line by line for accurate line numbers
            for line_num, line in enumerate(lines, 1):
                # Skip comments
                if self._is_comment(line):
                    continue

                # Check for CALL statements
                call_match = self.CALL_PATTERN.search(line)
                if call_match:
                    analysis.calls.append(CallDependency(
                        target=call_match.group(1),
                        line=line_num
                    ))

                # Check for COPY statements (with REPLACING)
                copy_replacing_match = self.COPY_REPLACING_PATTERN.search(line)
                if copy_replacing_match:
                    analysis.copies.append(CopyDependency(
                        copybook=copy_replacing_match.group(1),
                        line=line_num,
                        replacing=copy_replacing_match.group(2).strip()
                    ))
                else:
                    copy_match = self.COPY_PATTERN.search(line)
                    if copy_match:
                        analysis.copies.append(CopyDependency(
                            copybook=copy_match.group(1),
                            line=line_num
                        ))

                # Check for file I/O
                self._check_file_io(line, line_num, analysis)

            # Check for database operations (multi-line)
            self._check_database_ops(content, analysis)

            return analysis

        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return None

    def _is_comment(self, line: str) -> bool:
        """Check if a line is a COBOL comment."""
        if len(line) < 7:
            return False
        # Column 7 indicator: * or / means comment
        if len(line) > 6 and line[6] in ('*', '/'):
            return True
        return False

    def _check_file_io(self, line: str, line_num: int, analysis: ProgramAnalysis):
        """Check for file I/O operations in a line."""
        # READ
        read_match = self.READ_PATTERN.search(line)
        if read_match:
            analysis.file_io.append(FileIODependency(
                operation="READ",
                file_name=read_match.group(1),
                line=line_num
            ))

        # WRITE
        write_match = self.WRITE_PATTERN.search(line)
        if write_match:
            analysis.file_io.append(FileIODependency(
                operation="WRITE",
                file_name=write_match.group(1),
                line=line_num
            ))

        # REWRITE
        rewrite_match = self.REWRITE_PATTERN.search(line)
        if rewrite_match:
            analysis.file_io.append(FileIODependency(
                operation="REWRITE",
                file_name=rewrite_match.group(1),
                line=line_num
            ))

        # DELETE
        delete_match = self.DELETE_PATTERN.search(line)
        if delete_match:
            analysis.file_io.append(FileIODependency(
                operation="DELETE",
                file_name=delete_match.group(1),
                line=line_num
            ))

        # OPEN
        open_match = self.OPEN_PATTERN.search(line)
        if open_match:
            analysis.file_io.append(FileIODependency(
                operation=f"OPEN_{open_match.group(1).upper()}",
                file_name=open_match.group(2),
                line=line_num
            ))

    def _check_database_ops(self, content: str, analysis: ProgramAnalysis):
        """Check for database operations (EXEC SQL)."""
        for match in self.EXEC_SQL_PATTERN.finditer(content):
            operation = match.group(1).upper()
            table = match.group(3)
            # Estimate line number from position
            line_num = content[:match.start()].count('\n') + 1

            analysis.database.append(DatabaseDependency(
                operation=operation,
                table=table,
                line=line_num
            ))

    def get_all_dependencies(self) -> Dict[str, Any]:
        """
        Get aggregated dependency data from all analyzed programs.

        Returns:
            Dictionary with programs list and summary statistics
        """
        programs = [a.to_dict() for a in self.analyses]

        # Calculate totals
        total_calls = sum(len(a.calls) for a in self.analyses)
        total_copies = sum(len(a.copies) for a in self.analyses)
        total_file_io = sum(len(a.file_io) for a in self.analyses)
        total_database = sum(len(a.database) for a in self.analyses)

        return {
            "programs": programs,
            "summary": {
                "total_programs": len(programs),
                "total_calls": total_calls,
                "total_copies": total_copies,
                "total_file_io": total_file_io,
                "total_database": total_database,
                "total_dependencies": total_calls + total_copies + total_file_io + total_database
            }
        }
