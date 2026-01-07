"""
COBOL Static Analyzer for Monolith Identifier

Analyzes COBOL source files for monolithic pattern indicators:
- Lines of code (LOC)
- Section count
- Paragraph count
- PERFORM statements
- GOTO statements
- CALL statements
- COPY statements
- File I/O operations
- Nested IF depth
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ProgramMetrics:
    """Metrics for a single COBOL program."""
    program: str
    file_path: str
    loc: int = 0
    sections: int = 0
    paragraphs: int = 0
    perform_count: int = 0
    goto_count: int = 0
    call_count: int = 0
    copy_count: int = 0
    file_io_count: int = 0
    nested_if_depth: int = 0
    data_items: int = 0
    working_storage_items: int = 0


class COBOLStaticAnalyzer:
    """
    Static analyzer for COBOL source code.

    Extracts metrics relevant to monolith pattern detection.
    """

    def __init__(self):
        self.programs: List[ProgramMetrics] = []

    def analyze_directory(self, source_path: str) -> None:
        """
        Analyze all COBOL files in a directory.

        Args:
            source_path: Path to directory containing COBOL files
        """
        source_dir = Path(source_path)

        # Find all COBOL files
        cobol_extensions = ['.cbl', '.CBL', '.cob', '.COB', '.cobol', '.COBOL']
        cobol_files = []

        for ext in cobol_extensions:
            cobol_files.extend(source_dir.rglob(f'*{ext}'))

        # Analyze each file
        for cobol_file in cobol_files:
            try:
                metrics = self._analyze_file(cobol_file)
                self.programs.append(metrics)
            except Exception as e:
                print(f"Warning: Could not analyze {cobol_file}: {e}")

    def _analyze_file(self, file_path: Path) -> ProgramMetrics:
        """
        Analyze a single COBOL file.

        Args:
            file_path: Path to COBOL file

        Returns:
            ProgramMetrics for the file
        """
        content = file_path.read_text(errors='ignore')
        lines = content.split('\n')

        # Get program name from file
        program_name = file_path.stem

        metrics = ProgramMetrics(
            program=program_name,
            file_path=str(file_path)
        )

        # Count lines of code (excluding blank lines and comments)
        metrics.loc = self._count_loc(lines)

        # Count sections
        metrics.sections = self._count_sections(content)

        # Count paragraphs
        metrics.paragraphs = self._count_paragraphs(content)

        # Count PERFORM statements
        metrics.perform_count = self._count_performs(content)

        # Count GOTO statements
        metrics.goto_count = self._count_gotos(content)

        # Count CALL statements
        metrics.call_count = self._count_calls(content)

        # Count COPY statements
        metrics.copy_count = self._count_copies(content)

        # Count file I/O operations
        metrics.file_io_count = self._count_file_io(content)

        # Calculate nested IF depth
        metrics.nested_if_depth = self._calculate_nested_if_depth(lines)

        # Count data items
        metrics.data_items = self._count_data_items(content)

        # Count working storage items
        metrics.working_storage_items = self._count_working_storage(content)

        return metrics

    def _count_loc(self, lines: List[str]) -> int:
        """Count lines of code (excluding blanks and comments)."""
        count = 0
        for line in lines:
            # Skip blank lines
            if not line.strip():
                continue
            # Skip comment lines (column 7 = *)
            if len(line) > 6 and line[6] == '*':
                continue
            # Skip lines that are all whitespace in columns 1-6
            if len(line) <= 6:
                continue
            count += 1
        return count

    def _count_sections(self, content: str) -> int:
        """Count SECTION declarations."""
        # Match SECTION keyword at end of line (COBOL section declarations)
        pattern = r'\bSECTION\s*\.'
        return len(re.findall(pattern, content, re.IGNORECASE))

    def _count_paragraphs(self, content: str) -> int:
        """Count paragraph declarations in PROCEDURE DIVISION."""
        # Look for paragraph names (word followed by period at start of line area)
        # This is approximate - paragraphs are labels ending with period
        pattern = r'^\s{6,7}[A-Z0-9][-A-Z0-9]*\s*\.'
        return len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE))

    def _count_performs(self, content: str) -> int:
        """Count PERFORM statements."""
        pattern = r'\bPERFORM\b'
        return len(re.findall(pattern, content, re.IGNORECASE))

    def _count_gotos(self, content: str) -> int:
        """Count GO TO statements."""
        pattern = r'\bGO\s+TO\b'
        return len(re.findall(pattern, content, re.IGNORECASE))

    def _count_calls(self, content: str) -> int:
        """Count CALL statements."""
        pattern = r'\bCALL\b'
        return len(re.findall(pattern, content, re.IGNORECASE))

    def _count_copies(self, content: str) -> int:
        """Count COPY statements."""
        pattern = r'\bCOPY\b'
        return len(re.findall(pattern, content, re.IGNORECASE))

    def _count_file_io(self, content: str) -> int:
        """Count file I/O operations (READ, WRITE, REWRITE, DELETE, START)."""
        patterns = [
            r'\bREAD\b',
            r'\bWRITE\b',
            r'\bREWRITE\b',
            r'\bDELETE\b',
            r'\bSTART\b',
            r'\bOPEN\b',
            r'\bCLOSE\b'
        ]
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, content, re.IGNORECASE))
        return count

    def _calculate_nested_if_depth(self, lines: List[str]) -> int:
        """Calculate maximum nested IF depth."""
        max_depth = 0
        current_depth = 0

        for line in lines:
            upper_line = line.upper()

            # Count IF statements
            if_count = len(re.findall(r'\bIF\b', upper_line))
            current_depth += if_count

            # Count END-IF statements
            endif_count = len(re.findall(r'\bEND-IF\b', upper_line))
            current_depth -= endif_count

            # Track maximum
            if current_depth > max_depth:
                max_depth = current_depth

        return max_depth

    def _count_data_items(self, content: str) -> int:
        """Count data item declarations (01-49 level numbers)."""
        pattern = r'^\s*\d{2}\s+[A-Z]'
        return len(re.findall(pattern, content, re.MULTILINE | re.IGNORECASE))

    def _count_working_storage(self, content: str) -> int:
        """Count items in WORKING-STORAGE SECTION."""
        # Find WORKING-STORAGE SECTION
        ws_match = re.search(r'WORKING-STORAGE\s+SECTION', content, re.IGNORECASE)
        if not ws_match:
            return 0

        # Find next SECTION or PROCEDURE DIVISION
        ws_start = ws_match.end()
        next_section = re.search(r'(LINKAGE\s+SECTION|PROCEDURE\s+DIVISION)',
                                  content[ws_start:], re.IGNORECASE)

        if next_section:
            ws_content = content[ws_start:ws_start + next_section.start()]
        else:
            ws_content = content[ws_start:]

        # Count 01 level items in working storage
        pattern = r'^\s*01\s+[A-Z]'
        return len(re.findall(pattern, ws_content, re.MULTILINE | re.IGNORECASE))

    def get_analysis_result(self) -> Dict[str, Any]:
        """
        Get the complete analysis result.

        Returns:
            Dictionary with programs and summary
        """
        programs_data = []
        total_loc = 0
        total_sections = 0
        total_paragraphs = 0
        total_performs = 0
        total_gotos = 0
        total_calls = 0
        total_copies = 0
        total_file_io = 0
        max_loc = 0
        max_nested_if = 0

        for p in self.programs:
            programs_data.append({
                "program": p.program,
                "file_path": p.file_path,
                "loc": p.loc,
                "sections": p.sections,
                "paragraphs": p.paragraphs,
                "perform_count": p.perform_count,
                "goto_count": p.goto_count,
                "call_count": p.call_count,
                "copy_count": p.copy_count,
                "file_io_count": p.file_io_count,
                "nested_if_depth": p.nested_if_depth,
                "data_items": p.data_items,
                "working_storage_items": p.working_storage_items
            })

            total_loc += p.loc
            total_sections += p.sections
            total_paragraphs += p.paragraphs
            total_performs += p.perform_count
            total_gotos += p.goto_count
            total_calls += p.call_count
            total_copies += p.copy_count
            total_file_io += p.file_io_count

            if p.loc > max_loc:
                max_loc = p.loc
            if p.nested_if_depth > max_nested_if:
                max_nested_if = p.nested_if_depth

        program_count = len(self.programs)

        return {
            "programs": programs_data,
            "summary": {
                "total_programs": program_count,
                "total_loc": total_loc,
                "average_loc": total_loc // program_count if program_count > 0 else 0,
                "max_loc": max_loc,
                "total_sections": total_sections,
                "total_paragraphs": total_paragraphs,
                "total_performs": total_performs,
                "total_gotos": total_gotos,
                "total_calls": total_calls,
                "total_copies": total_copies,
                "total_file_io": total_file_io,
                "max_nested_if_depth": max_nested_if
            }
        }
