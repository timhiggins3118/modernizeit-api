"""
COBOL Structural Analyzer - File Analysis Module

This module provides functions for analyzing COBOL source files:
- Unzipping COBOL archives
- Finding COBOL files by extension
- Parsing COBOL structure (divisions, sections, paragraphs)
- Calculating statistics and complexity scores
- Building JSON output
"""

import re
import zipfile
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


# Regex patterns for COBOL structure detection
# Division patterns (case-insensitive)
DIVISION_PATTERN = re.compile(
    r'^\s{0,6}\s*(IDENTIFICATION|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION',
    re.IGNORECASE
)

# Section pattern within PROCEDURE DIVISION
SECTION_PATTERN = re.compile(
    r'^\s{0,11}([A-Z0-9][A-Z0-9-]*)\s+SECTION\s*\.',
    re.IGNORECASE
)

# Paragraph pattern - name followed by period in Area A (columns 8-11 in fixed format)
# This captures paragraph names that start in Area A
PARAGRAPH_PATTERN = re.compile(
    r'^[\s]{0,7}([A-Z][A-Z0-9-]*)\s*\.\s*$',
    re.IGNORECASE
)

# Alternative paragraph pattern for paragraphs that may have content on same line
PARAGRAPH_PATTERN_ALT = re.compile(
    r'^[\s]{0,7}([A-Z][A-Z0-9-]+)\s*\.',
    re.IGNORECASE
)

# Comment line pattern (asterisk in column 7 for fixed format)
COMMENT_PATTERN = re.compile(r'^.{6}\*')

# Continuation line pattern (hyphen in column 7)
CONTINUATION_PATTERN = re.compile(r'^.{6}-')

# Statement patterns for statistics
PERFORM_PATTERN = re.compile(r'\bPERFORM\b', re.IGNORECASE)
CALL_PATTERN = re.compile(r'\bCALL\b', re.IGNORECASE)
IF_PATTERN = re.compile(r'\bIF\b', re.IGNORECASE)
EVALUATE_PATTERN = re.compile(r'\bEVALUATE\b', re.IGNORECASE)


def unzip_cobol_zip(zip_path: Path, output_dir: Path) -> Path:
    """
    Unzip a COBOL archive to a working directory.

    Args:
        zip_path: Path to the ZIP file
        output_dir: Base output directory

    Returns:
        Path to the unzipped directory

    Raises:
        ValueError: If the zip file cannot be opened
    """
    work_dir = output_dir / "work" / "cobol_unzipped"
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(work_dir)
    except zipfile.BadZipFile as e:
        raise ValueError(f"Cannot open ZIP file '{zip_path}': {e}")
    except Exception as e:
        raise ValueError(f"Error extracting ZIP file '{zip_path}': {e}")

    return work_dir


def find_cobol_files(search_dir: Path, extensions: list[str]) -> list[Path]:
    """
    Recursively find all COBOL files with the specified extensions.

    Args:
        search_dir: Directory to search
        extensions: List of file extensions to match (e.g., ['.cbl', '.CBL'])

    Returns:
        List of Path objects for found COBOL files
    """
    cobol_files = []

    # Normalize extensions to lowercase for comparison
    ext_lower = set(ext.lower() for ext in extensions)

    for file_path in search_dir.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in ext_lower:
            cobol_files.append(file_path)

    # Sort for consistent ordering
    cobol_files.sort(key=lambda p: str(p).lower())

    return cobol_files


def looks_like_cobol(content: str) -> bool:
    """
    Heuristic check to see if content looks like valid COBOL.
    Returns True if the content contains COBOL-like patterns.
    """
    # Check for common COBOL keywords (case-insensitive)
    cobol_indicators = [
        'IDENTIFICATION DIVISION',
        'PROCEDURE DIVISION',
        'DATA DIVISION',
        'WORKING-STORAGE',
        'PROGRAM-ID',
        'PERFORM',
        'MOVE',
        'IF ',
        'END-IF',
        'DISPLAY',
        'PIC ',
        'VALUE ',
    ]

    content_upper = content.upper()
    matches = sum(1 for indicator in cobol_indicators if indicator in content_upper)

    # If at least 2 COBOL indicators are found, it's likely COBOL
    return matches >= 2


def read_file_with_encoding(file_path: Path, primary_encoding: str = "cp037") -> tuple[list[str], str]:
    """
    Read a file trying multiple encodings with smart detection.

    Strategy:
    1. Try UTF-8 first (most common for modern files)
    2. Try latin-1 (common fallback)
    3. Try the user-specified primary encoding (e.g., cp037 for EBCDIC mainframe files)
    4. Try cp1252 as last resort

    Uses heuristics to verify the content looks like valid COBOL.

    Args:
        file_path: Path to the file
        primary_encoding: Primary encoding for mainframe files (default cp037)

    Returns:
        Tuple of (lines, encoding_used)

    Raises:
        ValueError: If file cannot be read with any encoding
    """
    # Try common text encodings first, then EBCDIC
    encodings_to_try = ["utf-8", "latin-1", primary_encoding, "cp1252"]

    best_result = None
    best_encoding = None

    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                lines = content.splitlines()

                # Check if content looks like valid COBOL
                if looks_like_cobol(content):
                    return lines, encoding

                # Keep track of first successful read as fallback
                if best_result is None:
                    best_result = lines
                    best_encoding = encoding

        except (UnicodeDecodeError, LookupError):
            continue

    # Return best result even if it didn't pass COBOL heuristics
    if best_result is not None:
        return best_result, best_encoding

    raise ValueError(f"Cannot read file '{file_path}' with any supported encoding")


def is_comment_line(line: str) -> bool:
    """Check if a line is a COBOL comment."""
    if len(line) < 7:
        return False
    # Column 7 (index 6) contains * for comments
    return line[6:7] == '*'


def is_blank_or_trivial(line: str) -> bool:
    """Check if a line is blank or contains only trivial content."""
    stripped = line.strip()
    if not stripped:
        return True
    # Lines that are just a period or section/paragraph markers
    if stripped == '.':
        return True
    return False


def get_content_area(line: str) -> str:
    """Extract the content area of a COBOL line (columns 8-72 for fixed format)."""
    if len(line) <= 7:
        return ""
    # Columns 8-72 (indices 7-71)
    return line[7:72] if len(line) > 7 else line[7:]


def count_statements(lines: list[str]) -> dict[str, int]:
    """
    Count COBOL statements in a list of lines.

    Returns dict with perform_count, call_count, if_count, evaluate_count
    """
    text = '\n'.join(lines)

    return {
        'perform_count': len(PERFORM_PATTERN.findall(text)),
        'call_count': len(CALL_PATTERN.findall(text)),
        'if_count': len(IF_PATTERN.findall(text)),
        'evaluate_count': len(EVALUATE_PATTERN.findall(text))
    }


def find_division_lines(lines: list[str]) -> dict[str, Optional[int]]:
    """
    Find the line numbers where each division starts.

    Returns dict mapping division name to line number (1-indexed)
    """
    divisions = {
        'IDENTIFICATION': None,
        'ENVIRONMENT': None,
        'DATA': None,
        'PROCEDURE': None
    }

    for i, line in enumerate(lines):
        if is_comment_line(line):
            continue
        match = DIVISION_PATTERN.search(line)
        if match:
            div_name = match.group(1).upper()
            if div_name in divisions and divisions[div_name] is None:
                divisions[div_name] = i + 1  # 1-indexed

    return divisions


def parse_procedure_division(lines: list[str], proc_start: int) -> tuple[list[dict], list[dict]]:
    """
    Parse the PROCEDURE DIVISION to extract sections and paragraphs.

    Args:
        lines: All lines of the file
        proc_start: 1-indexed line number where PROCEDURE DIVISION starts

    Returns:
        Tuple of (sections_list, paragraphs_list)
    """
    sections = []
    paragraphs = []

    # Work with 0-indexed lines from the PROCEDURE DIVISION onward
    start_idx = proc_start - 1

    current_section = None
    current_paragraph = None

    # Skip reserved words that shouldn't be treated as paragraphs
    reserved_words = {
        'IDENTIFICATION', 'ENVIRONMENT', 'DATA', 'PROCEDURE', 'DIVISION',
        'SECTION', 'WORKING-STORAGE', 'LOCAL-STORAGE', 'LINKAGE', 'FILE',
        'INPUT-OUTPUT', 'FILE-CONTROL', 'I-O-CONTROL', 'CONFIGURATION',
        'SOURCE-COMPUTER', 'OBJECT-COMPUTER', 'SPECIAL-NAMES', 'REPOSITORY',
        'FD', 'SD', 'COPY', 'REPLACE', 'EXEC', 'END-EXEC', 'EJECT', 'SKIP1',
        'SKIP2', 'SKIP3', 'PROGRAM-ID', 'AUTHOR', 'DATE-WRITTEN', 'DATE-COMPILED',
        'SECURITY', 'INSTALLATION', 'SELECT', 'ASSIGN', 'ORGANIZATION',
        'ACCESS', 'RECORD', 'FILE-STATUS', 'STOP', 'RUN', 'GOBACK', 'EXIT'
    }

    for i in range(start_idx, len(lines)):
        line = lines[i]
        line_no = i + 1  # 1-indexed

        if is_comment_line(line):
            continue

        # Check for SECTION
        section_match = SECTION_PATTERN.match(line)
        if section_match:
            section_name = section_match.group(1).upper()

            # Close previous section
            if current_section:
                current_section['line_end'] = line_no - 1
                sections.append(current_section)

            # Close previous paragraph
            if current_paragraph:
                current_paragraph['line_end'] = line_no - 1
                paragraphs.append(current_paragraph)
                current_paragraph = None

            current_section = {
                'name': section_name,
                'line_start': line_no,
                'line_end': None
            }
            continue

        # Check for paragraph - must be in Area A (columns 8-11)
        # First, check if this looks like a paragraph name
        stripped = line.strip()

        # Try the strict pattern first (paragraph name alone on line)
        para_match = PARAGRAPH_PATTERN.match(line)
        if not para_match:
            # Try alternative pattern
            para_match = PARAGRAPH_PATTERN_ALT.match(line)

        if para_match:
            potential_name = para_match.group(1).upper()

            # Skip if it's a reserved word or looks like a statement
            if potential_name not in reserved_words:
                # Additional check: make sure this isn't a continuation of a statement
                # Paragraph names typically start at column 8 (index 7) or before
                # and don't have much leading whitespace
                leading_spaces = len(line) - len(line.lstrip())

                # In fixed format COBOL, Area A is columns 8-11 (indices 7-10)
                # Paragraphs should start in Area A
                if leading_spaces <= 7:
                    # Close previous paragraph
                    if current_paragraph:
                        current_paragraph['line_end'] = line_no - 1
                        paragraphs.append(current_paragraph)

                    current_paragraph = {
                        'name': potential_name,
                        'line_start': line_no,
                        'line_end': None,
                        'raw_lines': []
                    }
                    continue

        # Accumulate lines for current paragraph
        if current_paragraph:
            current_paragraph['raw_lines'].append((line_no, line))

    # Close final section and paragraph
    if current_section:
        current_section['line_end'] = len(lines)
        sections.append(current_section)

    if current_paragraph:
        current_paragraph['line_end'] = len(lines)
        paragraphs.append(current_paragraph)

    return sections, paragraphs


def get_preview_lines(raw_lines: list[tuple[int, str]], max_lines: int) -> list[dict]:
    """
    Get preview lines for a paragraph (non-blank, non-comment lines).

    Args:
        raw_lines: List of (line_no, text) tuples
        max_lines: Maximum number of preview lines to return

    Returns:
        List of dicts with line_no and text
    """
    preview = []

    for line_no, text in raw_lines:
        if is_comment_line(text):
            continue

        stripped = text.strip()
        if not stripped or stripped == '.':
            continue

        # Get a cleaner version of the text
        content = get_content_area(text).strip()
        if content:
            preview.append({
                'line_no': line_no,
                'text': content
            })

        if len(preview) >= max_lines:
            break

    return preview


def analyze_cobol_file(
    file_path: Path,
    base_dir: Path,
    max_lines_preview: int = 5,
    encoding: str = "cp037"
) -> Optional[dict]:
    """
    Analyze a single COBOL file and return its structure.

    Args:
        file_path: Path to the COBOL file
        base_dir: Base directory for computing relative paths
        max_lines_preview: Maximum preview lines per paragraph
        encoding: Primary encoding to try

    Returns:
        Dict with file analysis or None if file couldn't be read
    """
    try:
        lines, encoding_used = read_file_with_encoding(file_path, encoding)
    except ValueError as e:
        return None

    # Compute paths
    try:
        relative_path = str(file_path.relative_to(base_dir))
    except ValueError:
        relative_path = str(file_path)

    # Find divisions
    divisions = find_division_lines(lines)

    # Parse procedure division if present
    sections = []
    paragraphs = []

    if divisions['PROCEDURE']:
        sections, raw_paragraphs = parse_procedure_division(lines, divisions['PROCEDURE'])

        # Process paragraphs: compute stats and previews
        for para in raw_paragraphs:
            raw_lines = para.get('raw_lines', [])
            line_texts = [text for _, text in raw_lines]

            stats = count_statements(line_texts)
            stats['complexity_score'] = (
                stats['perform_count'] +
                stats['call_count'] +
                stats['if_count'] +
                stats['evaluate_count']
            )

            preview = get_preview_lines(raw_lines, max_lines_preview)

            paragraphs.append({
                'name': para['name'],
                'line_start': para['line_start'],
                'line_end': para['line_end'],
                'stats': stats,
                'preview_lines': preview
            })

    # Compute file-level stats
    file_complexity = sum(p['stats']['complexity_score'] for p in paragraphs)

    return {
        'path': str(file_path),
        'relative_path': relative_path,
        'loc': len(lines),
        'encoding_used': encoding_used,
        'sections': sections,
        'paragraphs': paragraphs,
        'file_stats': {
            'section_count': len(sections),
            'paragraph_count': len(paragraphs),
            'complexity_score': file_complexity
        }
    }


def build_structural_summary(
    file_analyses: list[dict],
    source_zip: str
) -> dict:
    """
    Build the summary section of the structural analysis.

    Args:
        file_analyses: List of file analysis dicts
        source_zip: Path to the source ZIP file

    Returns:
        Summary dict
    """
    total_files = len(file_analyses)
    total_loc = sum(f['loc'] for f in file_analyses)
    total_paragraphs = sum(f['file_stats']['paragraph_count'] for f in file_analyses)
    total_sections = sum(f['file_stats']['section_count'] for f in file_analyses)
    total_complexity = sum(f['file_stats']['complexity_score'] for f in file_analyses)

    avg_complexity = total_complexity / total_files if total_files > 0 else 0.0

    return {
        'total_files': total_files,
        'total_loc': total_loc,
        'total_paragraphs': total_paragraphs,
        'total_sections': total_sections,
        'average_file_complexity': round(avg_complexity, 2),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'source_zip': source_zip
    }


def write_json_output(output_path: Path, summary: dict, files: list[dict]) -> None:
    """
    Write the structural analysis JSON file.

    Args:
        output_path: Path to write the JSON file
        summary: Summary dict
        files: List of file analysis dicts
    """
    # Remove internal fields from file analyses before output
    clean_files = []
    for f in files:
        clean_file = {
            'path': f['path'],
            'relative_path': f['relative_path'],
            'loc': f['loc'],
            'sections': f['sections'],
            'paragraphs': f['paragraphs'],
            'file_stats': f['file_stats']
        }
        clean_files.append(clean_file)

    output = {
        'summary': summary,
        'files': clean_files
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)


# =============================================================================
# PROCEDURAL PLAN BUILDER FOR IFPR321
# =============================================================================

# Regex patterns for control flow extraction
PERFORM_STMT_PATTERN = re.compile(
    r'\bPERFORM\s+([A-Z0-9][A-Z0-9-]*)\s*(?:THRU|THROUGH)\s+([A-Z0-9][A-Z0-9-]*)',
    re.IGNORECASE
)
PERFORM_SIMPLE_PATTERN = re.compile(
    r'\bPERFORM\s+([A-Z0-9][A-Z0-9-]*)(?:\s|\.|\,|$)',
    re.IGNORECASE
)
GOTO_PATTERN = re.compile(
    r'\bGO\s+TO\s+([A-Z0-9][A-Z0-9-]*)',
    re.IGNORECASE
)

# Pattern to detect END PROGRAM
END_PROGRAM_PATTERN = re.compile(r'\bEND\s+PROGRAM\b', re.IGNORECASE)


def find_ifpr321_file(unzipped_root: Path) -> Optional[Path]:
    """
    Search recursively for IFPR321.CBL (case-insensitive stem match).

    Args:
        unzipped_root: Root directory to search

    Returns:
        Path to IFPR321 file or None if not found
    """
    for file_path in unzipped_root.rglob('*'):
        if file_path.is_file() and file_path.stem.upper() == 'IFPR321':
            return file_path
    return None


def extract_procedure_division_lines(lines: list[str]) -> tuple[int, int]:
    """
    Find the start and end line indices for the PROCEDURE DIVISION.

    Args:
        lines: All lines of the file

    Returns:
        Tuple of (start_idx, end_idx) as 0-indexed line numbers.
        end_idx is exclusive.
    """
    proc_start = None
    proc_end = len(lines)

    for i, line in enumerate(lines):
        if is_comment_line(line):
            continue

        upper_line = line.upper()

        # Find PROCEDURE DIVISION start
        if proc_start is None and 'PROCEDURE DIVISION' in upper_line:
            proc_start = i
            continue

        # Find END PROGRAM (marks end of procedure division)
        if proc_start is not None and END_PROGRAM_PATTERN.search(line):
            proc_end = i
            break

    return proc_start if proc_start else 0, proc_end


def parse_paragraphs_for_plan(lines: list[str], proc_start: int, proc_end: int) -> list[dict]:
    """
    Parse paragraphs from the PROCEDURE DIVISION for the procedural plan.

    Args:
        lines: All lines of the file
        proc_start: Start index of PROCEDURE DIVISION (0-indexed)
        proc_end: End index of PROCEDURE DIVISION (0-indexed, exclusive)

    Returns:
        List of paragraph dicts with name, start_line, end_line, raw_lines
    """
    paragraphs = []
    current_paragraph = None

    # Reserved words to skip
    reserved_words = {
        'IDENTIFICATION', 'ENVIRONMENT', 'DATA', 'PROCEDURE', 'DIVISION',
        'SECTION', 'WORKING-STORAGE', 'LOCAL-STORAGE', 'LINKAGE', 'FILE',
        'INPUT-OUTPUT', 'FILE-CONTROL', 'I-O-CONTROL', 'CONFIGURATION',
        'SOURCE-COMPUTER', 'OBJECT-COMPUTER', 'SPECIAL-NAMES', 'REPOSITORY',
        'FD', 'SD', 'COPY', 'REPLACE', 'EXEC', 'END-EXEC', 'EJECT', 'SKIP1',
        'SKIP2', 'SKIP3', 'PROGRAM-ID', 'AUTHOR', 'DATE-WRITTEN', 'DATE-COMPILED',
        'SECURITY', 'INSTALLATION', 'SELECT', 'ASSIGN', 'ORGANIZATION',
        'ACCESS', 'RECORD', 'FILE-STATUS', 'STOP', 'RUN', 'GOBACK', 'EXIT',
        'END', 'PROGRAM', 'USING', 'RETURNING'
    }

    for i in range(proc_start, proc_end):
        line = lines[i]
        line_no = i + 1  # 1-indexed for output

        if is_comment_line(line):
            # Still include comments in raw lines if we're in a paragraph
            if current_paragraph:
                current_paragraph['raw_lines'].append((line_no, line))
            continue

        # Check for SECTION (skip but close current paragraph)
        section_match = SECTION_PATTERN.match(line)
        if section_match:
            if current_paragraph:
                current_paragraph['end_line'] = line_no - 1
                paragraphs.append(current_paragraph)
                current_paragraph = None
            continue

        # Check for paragraph label
        para_match = PARAGRAPH_PATTERN.match(line)
        if not para_match:
            para_match = PARAGRAPH_PATTERN_ALT.match(line)

        if para_match:
            potential_name = para_match.group(1).upper()
            leading_spaces = len(line) - len(line.lstrip())

            # Must be in Area A and not a reserved word
            if leading_spaces <= 7 and potential_name not in reserved_words:
                # Close previous paragraph
                if current_paragraph:
                    current_paragraph['end_line'] = line_no - 1
                    paragraphs.append(current_paragraph)

                # Start new paragraph
                current_paragraph = {
                    'name': potential_name,
                    'start_line': line_no,
                    'end_line': None,
                    'raw_lines': [(line_no, line)]  # Include the label line
                }
                continue

        # Accumulate lines for current paragraph
        if current_paragraph:
            current_paragraph['raw_lines'].append((line_no, line))

    # Close final paragraph
    if current_paragraph:
        current_paragraph['end_line'] = proc_end
        paragraphs.append(current_paragraph)

    return paragraphs


def extract_control_flow(raw_lines: list[tuple[int, str]]) -> dict:
    """
    Extract PERFORM and GO TO targets from paragraph body lines.

    Args:
        raw_lines: List of (line_no, text) tuples

    Returns:
        Dict with 'calls', 'gotos', 'perform_type'
    """
    calls = []
    gotos = []
    perform_type = None

    for line_no, line in raw_lines:
        if is_comment_line(line):
            continue

        # Check for PERFORM ... THRU/THROUGH
        thru_matches = PERFORM_STMT_PATTERN.findall(line)
        for match in thru_matches:
            target = match[0].upper()
            if target not in calls:
                calls.append(target)
            perform_type = "THRU"

        # Check for simple PERFORM (but not those already caught by THRU pattern)
        simple_matches = PERFORM_SIMPLE_PATTERN.findall(line)
        for target in simple_matches:
            target_upper = target.upper()
            # Skip if this is part of a THRU statement (already captured)
            if target_upper not in calls:
                # Make sure it's not a COBOL keyword
                if target_upper not in {'UNTIL', 'VARYING', 'TIMES', 'WITH', 'TEST'}:
                    calls.append(target_upper)
                    if perform_type is None:
                        perform_type = "ONCE"

        # Check for GO TO
        goto_matches = GOTO_PATTERN.findall(line)
        for target in goto_matches:
            target_upper = target.upper()
            if target_upper not in gotos:
                gotos.append(target_upper)

    return {
        'calls': calls,
        'gotos': gotos,
        'perform_type': perform_type
    }


def get_raw_text_preview(raw_lines: list[tuple[int, str]], max_lines: int = 5) -> list[str]:
    """
    Get first N non-blank lines as raw text preview.

    Args:
        raw_lines: List of (line_no, text) tuples
        max_lines: Maximum lines to include

    Returns:
        List of text strings (cleaned)
    """
    preview = []

    for line_no, text in raw_lines:
        # Skip blank lines
        stripped = text.strip()
        if not stripped:
            continue

        # Clean up the line - get content area for fixed format
        if len(text) > 7:
            content = text[7:72].rstrip() if len(text) > 7 else text[7:].rstrip()
        else:
            content = stripped

        if content:
            preview.append(content)

        if len(preview) >= max_lines:
            break

    return preview


def detect_entry_paragraphs(paragraphs: list[dict]) -> list[str]:
    """
    Detect entry point paragraphs using heuristics.

    Heuristics:
    1. Paragraph name ends with -MAIN or -MAIN-PARA
    2. Paragraph name contains 'MAIN' as a word
    3. Otherwise, first paragraph

    Args:
        paragraphs: List of paragraph dicts

    Returns:
        List of entry paragraph names (usually just one)
    """
    if not paragraphs:
        return []

    # Look for paragraphs with MAIN in the name
    main_candidates = []
    for p in paragraphs:
        name = p['name']
        # Check for common entry point patterns
        if name.endswith('-MAIN') or name.endswith('-MAIN-PARA'):
            main_candidates.append(name)
        elif '-MAIN-' in name or name == 'MAIN' or name.startswith('MAIN-'):
            main_candidates.append(name)

    if main_candidates:
        return main_candidates[:1]  # Return first match

    # Fallback: first paragraph is the entry
    return [paragraphs[0]['name']]


def build_call_graph(paragraphs: list[dict]) -> list[dict]:
    """
    Build the call graph from paragraph control flow info.

    Args:
        paragraphs: List of processed paragraph dicts with 'calls' and 'gotos'

    Returns:
        List of call graph edges
    """
    edges = []

    for p in paragraphs:
        from_name = p['name']

        for target in p.get('calls', []):
            edges.append({
                'from': from_name,
                'to': target,
                'type': 'PERFORM'
            })

        for target in p.get('gotos', []):
            edges.append({
                'from': from_name,
                'to': target,
                'type': 'GO TO'
            })

    return edges


def build_procedural_plan_for_ifpr321(unzipped_root: Path, output_dir: Path) -> Optional[Path]:
    """
    Build a procedural plan JSON for IFPR321.CBL.

    Args:
        unzipped_root: Root directory containing unzipped COBOL files
        output_dir: Directory to write the output JSON

    Returns:
        Path to the written JSON file, or None if IFPR321 not found
    """
    # Step 1: Find IFPR321.CBL
    ifpr321_path = find_ifpr321_file(unzipped_root)
    if ifpr321_path is None:
        return None

    # Step 2: Read the file
    try:
        lines, encoding_used = read_file_with_encoding(ifpr321_path)
    except ValueError:
        return None

    total_lines = len(lines)

    # Step 3: Find PROCEDURE DIVISION bounds
    proc_start, proc_end = extract_procedure_division_lines(lines)
    if proc_start is None:
        return None

    # Step 4: Parse paragraphs
    raw_paragraphs = parse_paragraphs_for_plan(lines, proc_start, proc_end)

    # Step 5: Process each paragraph
    processed_paragraphs = []
    for p in raw_paragraphs:
        control_flow = extract_control_flow(p['raw_lines'])
        preview = get_raw_text_preview(p['raw_lines'], max_lines=5)

        processed_paragraphs.append({
            'name': p['name'],
            'start_line': p['start_line'],
            'end_line': p['end_line'],
            'is_entry': False,  # Will be set later
            'calls': control_flow['calls'],
            'gotos': control_flow['gotos'],
            'perform_type': control_flow['perform_type'],
            'raw_text_preview': preview
        })

    # Step 6: Detect entry paragraphs
    entry_paragraphs = detect_entry_paragraphs(processed_paragraphs)
    for p in processed_paragraphs:
        if p['name'] in entry_paragraphs:
            p['is_entry'] = True

    # Step 7: Build call graph
    call_graph = build_call_graph(processed_paragraphs)

    # Step 8: Compute relative path
    try:
        relative_path = str(ifpr321_path.relative_to(output_dir))
    except ValueError:
        relative_path = str(ifpr321_path)

    # Step 9: Build output structure
    output = {
        'program_name': 'IFPR321',
        'file_path': relative_path,
        'total_lines': total_lines,
        'paragraphs': processed_paragraphs,
        'entry_paragraphs': entry_paragraphs,
        'call_graph': call_graph
    }

    # Step 10: Write JSON
    output_path = output_dir / 'procedural_plan_IFPR321.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return output_path
