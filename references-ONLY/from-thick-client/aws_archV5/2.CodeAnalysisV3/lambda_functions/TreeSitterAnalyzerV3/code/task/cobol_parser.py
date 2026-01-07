"""
COBOL Parser using Tree-sitter

Purpose: Parse COBOL files to extract structure (paragraphs, data, control flow)
Strategy: Tree-sitter AST + text-based paragraph scanning (dual approach)

Date: November 3, 2025
Version: V3.0
"""

import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# COBOL paragraph pattern (text-based fallback)
# Matches: "       20000-PROCESS-CUSTOMER." or "       MAIN-LOGIC."
PARAGRAPH_PATTERN = re.compile(
    r'^\s{7,}([A-Z0-9][A-Z0-9\-]*)\.\s*$',
    re.MULTILINE
)

# Section pattern
SECTION_PATTERN = re.compile(
    r'^\s{7,}([A-Z0-9][A-Z0-9\-]*)\s+SECTION\.\s*$',
    re.MULTILINE | re.IGNORECASE
)

# Division pattern
DIVISION_PATTERN = re.compile(
    r'^\s*([A-Z\-]+)\s+DIVISION\.\s*$',
    re.MULTILINE | re.IGNORECASE
)


def parse_cobol_file(file_name: str, file_content: str) -> Dict[str, Any]:
    """
    Parse COBOL file and extract structure

    Args:
        file_name: Name of the file
        file_content: COBOL source code

    Returns:
        Dictionary with parsed structure
    """
    logger.info(f"Parsing COBOL file: {file_name}")

    # Classify file type
    file_type = classify_file_content(file_content)

    # Parse based on type
    if file_type == 'COBOL_PROGRAM':
        return parse_cobol_program(file_name, file_content)
    elif file_type == 'COPYBOOK':
        return parse_copybook(file_name, file_content)
    elif file_type == 'DCLGEN':
        return parse_dclgen(file_name, file_content)
    elif file_type == 'CLP':
        return parse_clp(file_name, file_content)
    elif file_type == 'JCL':
        return parse_jcl(file_name, file_content)
    elif file_type == 'DB2_DDL':
        return parse_db2_ddl(file_name, file_content)
    else:
        return parse_unknown(file_name, file_content)


def is_copybook(content: str) -> bool:
    """
    Detect if file is a COBOL copybook

    Copybooks have:
    - Level items (01, 02, 03, 05, 07, 77, 88) with or without PIC clauses
    - FD statements (File Description copybooks)
    - SELECT statements (File Selection copybooks)
    - NO PROCEDURE DIVISION (no executable code)
    - NO EXEC SQL DECLARE (that would be DCLGEN)

    Args:
        content: File content

    Returns:
        True if file is a copybook, False otherwise
    """
    content_upper = content.upper()

    # Must NOT have PROCEDURE DIVISION
    if 'PROCEDURE DIVISION' in content_upper:
        return False

    # Must NOT have EXEC SQL DECLARE (that's DCLGEN)
    if 'EXEC SQL DECLARE' in content_upper or 'EXEC SQL' in content_upper:
        return False

    # Pattern 1: Check for FD (File Description) copybooks
    # These have: "FD filename" followed by data items
    # Note: Allow for COBOL source format with 6-char prefix (e.g., "PAYBEN FD")
    has_fd = bool(re.search(r'^\s*[A-Z0-9]{0,6}\s*FD\s+[A-Z0-9-]+', content, re.MULTILINE | re.IGNORECASE))

    # Pattern 2: Check for SELECT (File Selection) copybooks
    # These have: "SELECT filename ASSIGN TO..."
    # Note: Allow for COBOL source format with 6-char prefix
    has_select = bool(re.search(r'^\s*[A-Z0-9]{0,6}\s*SELECT\s+[A-Z0-9-]+\s+ASSIGN', content, re.MULTILINE | re.IGNORECASE))

    # Pattern 3: Check for level items (with or without PIC clauses)
    # Pattern: level number + name (PIC is optional for SD copybooks)
    # Note: Allow for COBOL source format with 6-char prefix
    level_pattern = r'^\s*[A-Z0-9]{0,6}\s*(0[12357]|77|88)\s+[A-Z0-9-]+'
    has_level_items = bool(re.search(level_pattern, content, re.MULTILINE | re.IGNORECASE))

    # Pattern 5: Check for CONFIGURATION SECTION copybooks
    # These have: "SOURCE-COMPUTER" or "OBJECT-COMPUTER"
    has_config = 'SOURCE-COMPUTER' in content_upper or 'OBJECT-COMPUTER' in content_upper

    # Pattern 4: Check for DATA DIVISION or WORKING-STORAGE SECTION (common in copybooks)
    has_data_division = 'DATA DIVISION' in content_upper or 'WORKING-STORAGE' in content_upper

    # A file is a copybook if it has:
    # - FD statements (File Description), OR
    # - SELECT statements (File Selection), OR
    # - Level items (data structures), OR
    # - DATA DIVISION/WORKING-STORAGE (common copybook headers), OR
    # - CONFIGURATION SECTION (SOURCE-COMPUTER/OBJECT-COMPUTER)
    return has_fd or has_select or has_level_items or has_data_division or has_config


def is_dclgen(content: str) -> bool:
    """
    Detect if file is a DB2 DCLGEN (DB2 table mapping)

    DCLGENs have:
    - EXEC SQL DECLARE statement (table declaration)
    - 01-level COBOL structure mapping table columns

    Args:
        content: File content

    Returns:
        True if file is a DCLGEN, False otherwise
    """
    content_upper = content.upper()

    # Must have EXEC SQL DECLARE
    has_sql_declare = 'EXEC SQL DECLARE' in content_upper or (
        'EXEC SQL' in content_upper and 'DECLARE' in content_upper
    )

    if not has_sql_declare:
        return False

    # Must have 01-level structure
    # Pattern: 01 + name
    has_01_level = bool(re.search(r'^\s*01\s+[A-Z0-9-]+', content, re.MULTILINE | re.IGNORECASE))

    return has_01_level


def is_clp(content: str) -> bool:
    """
    Detect if file is a CLP (IBM i Control Language Program)

    CLP files have:
    - PGM command (program declaration)
    - DCL VAR statements (variable declarations)
    - CLP commands (CHGVAR, SNDPGMMSG, CALL, etc.)

    Args:
        content: File content

    Returns:
        True if file is a CLP, False otherwise
    """
    content_upper = content.upper()

    # Must have PGM command
    has_pgm = bool(re.search(r'\bPGM\b', content_upper))

    if not has_pgm:
        return False

    # Check for typical CLP patterns
    clp_indicators = [
        r'\bDCL\s+VAR\b',      # Variable declaration
        r'\bCHGVAR\b',         # Change variable
        r'\bSNDPGMMSG\b',      # Send program message
        r'\bENDPGM\b',         # End program
        r'\bIF\s+COND\b',      # Conditional
        r'\bCALL\s+PGM\b',     # Call program
    ]

    for pattern in clp_indicators:
        if re.search(pattern, content_upper):
            return True

    return False


def classify_file_content(content: str) -> str:
    """
    Classify file type based on content (not extension)

    Args:
        content: File content

    Returns:
        File type: COBOL_PROGRAM, COPYBOOK, DCLGEN, CLP, JCL, DB2_DDL, UNKNOWN
    """
    content_upper = content.upper()

    # Priority 1: Check for COBOL program (has PROCEDURE DIVISION)
    if 'PROCEDURE DIVISION' in content_upper:
        return 'COBOL_PROGRAM'

    # Priority 2: Check for DCLGEN (BEFORE copybook - has EXEC SQL DECLARE + 01-level)
    if is_dclgen(content):
        return 'DCLGEN'

    # Priority 3: Check for Copybook (has level items, no PROCEDURE DIVISION, no SQL)
    if is_copybook(content):
        return 'COPYBOOK'

    # Priority 4: Check for CLP (IBM i Control Language Program)
    if is_clp(content):
        return 'CLP'

    # Priority 5: Check for JCL (starts with //)
    if content.startswith('//') or '//' in content[:100]:
        return 'JCL'

    # Priority 6: Check for DB2 DDL (CREATE/ALTER TABLE)
    if 'CREATE TABLE' in content_upper or 'ALTER TABLE' in content_upper:
        return 'DB2_DDL'

    # Priority 7: Unknown file type
    return 'UNKNOWN'


def parse_cobol_program(file_name: str, content: str) -> Dict[str, Any]:
    """
    Parse COBOL program file

    Args:
        file_name: Name of the file
        content: COBOL source code

    Returns:
        Parsed structure with paragraphs, data, control flow
    """
    lines = content.split('\n')

    # Extract divisions
    divisions = extract_divisions(content)

    # Extract sections
    sections = extract_sections(content)

    # Extract paragraphs (dual approach: Tree-sitter would go here, but we're using text-based for now)
    paragraphs = extract_paragraphs_text_based(content, lines)

    # Extract data dictionary
    data_dictionary = extract_data_dictionary(content)

    # Extract dependencies (copybooks, files, calls, SQL)
    dependencies = extract_dependencies(content)

    # Calculate confidence score
    confidence = calculate_parse_confidence(paragraphs, sections, divisions, content)

    return {
        'file_name': file_name,
        'file_type': 'COBOL_PROGRAM',
        'confidence': confidence,
        'divisions': divisions,
        'sections': sections,
        'paragraphs': paragraphs,
        'paragraph_count': len(paragraphs),
        'data_dictionary': data_dictionary,
        'dependencies': dependencies,
        'total_lines': len(lines)
    }


def extract_paragraphs_text_based(content: str, lines: List[str]) -> List[Dict[str, Any]]:
    """
    Extract paragraphs using text-based pattern matching

    This is the V3 fix: use regex to find paragraph headers, then extract their content

    Args:
        content: Full file content
        lines: File content split by lines

    Returns:
        List of paragraph dictionaries
    """
    paragraphs = []

    # Find all paragraph matches
    matches = list(PARAGRAPH_PATTERN.finditer(content))

    logger.info(f"Found {len(matches)} paragraph candidates")

    for i, match in enumerate(matches):
        paragraph_name = match.group(1)
        start_line = content[:match.start()].count('\n') + 1

        # Determine end line (next paragraph or end of file)
        if i + 1 < len(matches):
            end_line = content[:matches[i + 1].start()].count('\n')
        else:
            end_line = len(lines)

        # Extract paragraph body
        body_lines = lines[start_line:end_line]
        body = '\n'.join(body_lines)

        # Extract statements from paragraph body
        statements = extract_statements_from_paragraph(body, start_line + 1)

        paragraph = {
            'name': paragraph_name,
            'start_line': start_line,
            'end_line': end_line,
            'line_count': end_line - start_line,
            'statements': statements,
            'statement_count': len(statements)
        }

        paragraphs.append(paragraph)

    logger.info(f"Extracted {len(paragraphs)} paragraphs")

    return paragraphs


def extract_statements_from_paragraph(paragraph_body: str, start_line: int) -> List[Dict[str, Any]]:
    """
    Extract individual statements from paragraph body

    Args:
        paragraph_body: Paragraph content
        start_line: Starting line number

    Returns:
        List of statement dictionaries
    """
    statements = []
    stmt_id = 1

    # Common COBOL verbs
    cobol_verbs = [
        'MOVE', 'COMPUTE', 'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE',
        'IF', 'ELSE', 'END-IF', 'EVALUATE', 'WHEN', 'END-EVALUATE',
        'PERFORM', 'CALL', 'GO TO', 'GOTO',
        'READ', 'WRITE', 'OPEN', 'CLOSE',
        'ACCEPT', 'DISPLAY',
        'EXEC SQL', 'EXEC CICS',
        'STRING', 'UNSTRING', 'INSPECT', 'SEARCH'
    ]

    lines = paragraph_body.split('\n')
    for i, line in enumerate(lines):
        line_stripped = line.strip()

        if not line_stripped or line_stripped.startswith('*'):
            continue  # Skip empty lines and comments

        # Check if line contains a COBOL verb
        for verb in cobol_verbs:
            if verb in line_stripped.upper():
                statement = {
                    'stmt_id': f's{stmt_id}',
                    'line': start_line + i,
                    'operation': verb,
                    'source': line_stripped
                }
                statements.append(statement)
                stmt_id += 1
                break

    return statements


def extract_divisions(content: str) -> List[Dict[str, Any]]:
    """Extract COBOL divisions"""
    divisions = []
    for match in DIVISION_PATTERN.finditer(content):
        divisions.append({
            'name': match.group(1),
            'line': content[:match.start()].count('\n') + 1
        })
    return divisions


def extract_sections(content: str) -> List[Dict[str, Any]]:
    """Extract COBOL sections"""
    sections = []
    for match in SECTION_PATTERN.finditer(content):
        sections.append({
            'name': match.group(1),
            'line': content[:match.start()].count('\n') + 1
        })
    return sections


def extract_data_dictionary(content: str) -> List[Dict[str, Any]]:
    """
    Extract data dictionary (variables) from DATA DIVISION

    Based on V2's extract_symbols_and_segments() - extracts level items with full details
    including USAGE, REDEFINES, and OCCURS clauses.

    Args:
        content: COBOL source code

    Returns:
        List of data item dictionaries with level, name, pic, usage, redefines, occurs
    """
    data_items = []

    # Find DATA DIVISION section (from V2)
    data_div_re = re.compile(r"\bDATA\s+DIVISION\b", re.IGNORECASE)
    m = data_div_re.search(content)
    data_text = content[m.start():] if m else content

    # Level item pattern with optional clauses (from V2 line 46)
    # Matches: 01/02/05/07/08/88 level items with PIC clause
    level_item_pattern = re.compile(
        r"^\s*(0[12578]|88)\s+([A-Z0-9-]+)"  # Level + Name
        r"(?:\s+REDEFINES\s+([A-Z0-9-]+))?"  # Optional REDEFINES
        r"\s+(?:PIC|PICTURE)\s+([A-Z0-9\(\)V\.\-]+)"  # Required PIC/PICTURE
        r"(?:\s+USAGE\s+([A-Z0-9-]+))?"  # Optional USAGE
        r"(?:\s+OCCURS\s+(\d+))?",  # Optional OCCURS
        re.IGNORECASE | re.MULTILINE
    )

    for match in level_item_pattern.finditer(data_text):
        level, name, redefines, pic, usage, occurs = match.groups()
        data_items.append({
            'level': int(level),
            'name': name,
            'pic': pic,
            'usage': usage,
            'redefines': redefines,
            'occurs': int(occurs) if occurs else None
        })

    logger.info(f"Extracted {len(data_items)} data items from DATA DIVISION")

    return data_items


def extract_dependencies(content: str) -> Dict[str, Any]:
    """
    Extract external dependencies (copybooks, files, calls, SQL)

    Based on V2's extract_dependencies() - extracts actual names of dependencies,
    not just counts.

    Args:
        content: COBOL source code

    Returns:
        Dictionary with copybooks, files, calls, and sql_count
    """
    # COPY statements (copybooks) - from V2 line 60
    copybooks = re.findall(
        r"\bCOPY\s+([A-Z0-9-]+)(?:\s+OF\s+([A-Z0-9-]+))?",
        content,
        re.IGNORECASE
    )

    # SELECT statements (file names) - from V2 line 61
    files = re.findall(r"\bSELECT\s+([A-Z0-9-]+)\b", content, re.IGNORECASE)

    # CALL statements (called programs) - from V2 line 62
    calls = re.findall(r"\bCALL\s+['\"]([A-Z0-9_$-]+)['\"]", content, re.IGNORECASE)

    # EXEC SQL blocks (count only) - from V2 line 63
    sqls = re.findall(r"\bEXEC\s+SQL\b.*?\bEND-EXEC\b", content, re.IGNORECASE | re.DOTALL)

    dependencies = {
        "copybooks": [{"name": a, "of": b or None} for (a, b) in copybooks],
        "files": sorted(set(files)),
        "calls": sorted(set(calls)),
        "sql_count": len(sqls)
    }

    logger.info(f"Extracted dependencies: {len(copybooks)} copybooks, {len(set(files))} files, {len(set(calls))} calls, {len(sqls)} SQL blocks")

    return dependencies


def calculate_parse_confidence(paragraphs: List, sections: List, divisions: List, content: str) -> float:
    """
    Calculate confidence score for the parse

    Args:
        paragraphs: Extracted paragraphs
        sections: Extracted sections
        divisions: Extracted divisions
        content: Source code

    Returns:
        Confidence score from 0.0 to 1.0
    """
    score = 0.0

    # Has PROCEDURE DIVISION (+0.3)
    if 'PROCEDURE DIVISION' in content.upper():
        score += 0.3

    # Has divisions (+0.2)
    if len(divisions) >= 2:
        score += 0.2

    # Has paragraphs or sections (+0.3)
    if len(paragraphs) > 0:
        score += 0.3
    elif len(sections) > 0:
        score += 0.2

    # Has data dictionary (+0.2)
    if 'DATA DIVISION' in content.upper():
        score += 0.2

    return min(score, 1.0)


def build_nested_data_dictionary(flat_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build NESTED data dictionary from flat level items

    Preserves parent-child hierarchy for easy reading and no mistakes.

    Args:
        flat_items: Flat list of data items with 'level' field

    Returns:
        Nested list where children are under 'children' key
    """
    if not flat_items:
        return []

    nested = []
    stack = []  # Stack of (level, item_dict) tuples

    for item in flat_items:
        level = int(item['level'])

        # Create new dict with children array
        nested_item = {
            'level': item['level'],
            'name': item['name'],
            'pic': item.get('pic'),
            'usage': item.get('usage'),
            'redefines': item.get('redefines'),
            'occurs': item.get('occurs'),
            'children': []
        }

        # Pop stack until we find parent level
        while stack and stack[-1][0] >= level:
            stack.pop()

        # Add to parent's children or root
        if stack:
            parent_level, parent_item = stack[-1]
            parent_item['children'].append(nested_item)
        else:
            nested.append(nested_item)

        # Push current item onto stack
        stack.append((level, nested_item))

    return nested


def parse_copybook(file_name: str, content: str) -> Dict[str, Any]:
    """
    Parse copybook file (data-only)

    Extracts NESTED data dictionary preserving parent-child hierarchy.
    Handles FD copybooks, SELECT copybooks, and standard data copybooks.

    Args:
        file_name: Name of the copybook file
        content: Copybook source code

    Returns:
        Dict with file_type=COPYBOOK and nested data_dictionary
    """
    # Extract flat data dictionary
    flat_data_items = extract_data_dictionary(content)

    # Build NESTED structure (user preference: "nested.. easy to read... and no room for mistakes")
    nested_data_dictionary = build_nested_data_dictionary(flat_data_items)

    # Check for copybook metadata
    content_upper = content.upper()
    has_fd = 'FD ' in content_upper
    has_select = 'SELECT ' in content_upper and 'ASSIGN' in content_upper
    has_working_storage = 'WORKING-STORAGE' in content_upper

    copybook_type = 'DATA'  # Default
    if has_fd:
        copybook_type = 'FD'
    elif has_select:
        copybook_type = 'SELECT'
    elif has_working_storage:
        copybook_type = 'WORKING_STORAGE'

    return {
        'file_name': file_name,
        'file_type': 'COPYBOOK',
        'copybook_type': copybook_type,
        'confidence': 0.9,
        'data_dictionary': nested_data_dictionary,
        'data_items_count': len(flat_data_items),
        'paragraphs': [],
        'paragraph_count': 0,
        'note': 'Copybook - data dictionary only (NESTED structure)'
    }


def parse_dclgen(file_name: str, content: str) -> Dict[str, Any]:
    """
    Parse DCLGEN file (DB2 table mapping)

    Extracts FULL DETAILS from EXEC SQL DECLARE and COBOL mapping.
    User preference: "as much as we need... as much as we can"

    Args:
        file_name: Name of the DCLGEN file
        content: DCLGEN source code

    Returns:
        Dict with file_type=DCLGEN and complete table/column information
    """
    content_upper = content.upper()

    # Extract table name from EXEC SQL DECLARE
    # Pattern: EXEC SQL DECLARE schema.table TABLE
    table_match = re.search(
        r'EXEC\s+SQL\s+DECLARE\s+([A-Z0-9_]+)\.([A-Z0-9_]+)\s+TABLE',
        content_upper,
        re.IGNORECASE
    )

    schema_name = None
    table_name = None
    full_table_name = None

    if table_match:
        schema_name = table_match.group(1)
        table_name = table_match.group(2)
        full_table_name = f"{schema_name}.{table_name}"

    # Extract columns from EXEC SQL DECLARE section
    # Pattern: column_name  DB2_TYPE(size, precision)  [NOT] NULL [WITH DEFAULT]
    columns = []

    # Find the EXEC SQL DECLARE block
    sql_declare_match = re.search(
        r'EXEC\s+SQL\s+DECLARE.*?TABLE\s*\((.*?)\)\s*END-EXEC',
        content,
        re.IGNORECASE | re.DOTALL
    )

    if sql_declare_match:
        declare_block = sql_declare_match.group(1)

        # Parse each column definition
        # Pattern: column_name  TYPE(len, prec)  [NOT] NULL [WITH DEFAULT]
        column_pattern = r'([A-Z0-9_]+)\s+(CHAR|DEC|DATE|DECIMAL|INTEGER|SMALLINT|BIGINT|VARCHAR|TIMESTAMP)\s*(?:\(([0-9,\s]+)\))?\s*(NOT\s+NULL|NULL)?\s*(WITH\s+DEFAULT)?'

        for match in re.finditer(column_pattern, declare_block, re.IGNORECASE):
            column_name = match.group(1)
            data_type = match.group(2).upper()
            size_info = match.group(3)  # e.g., "11, 3" or "10"
            nullable_clause = match.group(4)  # "NOT NULL" or "NULL"
            default_clause = match.group(5)  # "WITH DEFAULT"

            # Parse size/precision
            length = None
            precision = None
            if size_info:
                parts = [p.strip() for p in size_info.split(',')]
                length = int(parts[0]) if parts else None
                precision = int(parts[1]) if len(parts) > 1 else None

            # Determine nullability
            nullable = True  # Default
            if nullable_clause and 'NOT NULL' in nullable_clause.upper():
                nullable = False

            has_default = bool(default_clause)

            columns.append({
                'name': column_name,
                'db2_type': data_type,
                'length': length,
                'precision': precision,
                'nullable': nullable,
                'has_default': has_default
            })

    # Extract COBOL structure (01-level mapping)
    flat_data_items = extract_data_dictionary(content)
    nested_cobol_structure = build_nested_data_dictionary(flat_data_items)

    # Extract COBOL record name (e.g., DCLADL042TB)
    cobol_record_name = None
    record_match = re.search(r'01\s+([A-Z0-9-]+)', content, re.IGNORECASE | re.MULTILINE)
    if record_match:
        cobol_record_name = record_match.group(1)

    return {
        'file_name': file_name,
        'file_type': 'DCLGEN',
        'confidence': 0.95,
        'db2_table': {
            'schema': schema_name,
            'table': table_name,
            'full_name': full_table_name,
            'column_count': len(columns),
            'columns': columns
        },
        'cobol_mapping': {
            'record_name': cobol_record_name,
            'structure': nested_cobol_structure,
            'field_count': len(flat_data_items)
        },
        'paragraphs': [],
        'paragraph_count': 0,
        'note': 'DCLGEN - DB2 table mapping with FULL DETAILS'
    }


def parse_clp(file_name: str, content: str) -> Dict[str, Any]:
    """
    Parse CLP file (IBM i Control Language Program)

    Extracts DETAILED information from CLP source.
    User preference: DETAILED extraction

    Args:
        file_name: Name of the CLP file
        content: CLP source code

    Returns:
        Dict with file_type=CLP and detailed program information
    """
    content_upper = content.upper()

    # Extract program name from PGM command
    # Pattern: PGM PARM(&param) or just PGM
    program_name = file_name.replace('.CLP', '').replace('.clp', '')
    parameters = []

    pgm_match = re.search(r'PGM\s+PARM\(([&A-Z0-9_\s]+)\)', content_upper, re.IGNORECASE)
    if pgm_match:
        param_str = pgm_match.group(1).strip()
        # Extract parameter names (e.g., &PARMS)
        parameters = re.findall(r'&[A-Z0-9_]+', param_str)

    # Extract variables from DCL VAR statements
    # Pattern: DCL VAR(&name) TYPE(*type) LEN(size precision)
    variables = []
    var_pattern = r'DCL\s+VAR\((&[A-Z0-9_]+)\s*\)\s+TYPE\(\*([A-Z]+)\)\s+LEN\(([0-9\s]+)\)'

    for match in re.finditer(var_pattern, content_upper, re.IGNORECASE):
        var_name = match.group(1)
        var_type = match.group(2)
        len_info = match.group(3).strip()

        # Parse length/precision
        len_parts = [p.strip() for p in len_info.split()]
        length = int(len_parts[0]) if len_parts else None
        precision = int(len_parts[1]) if len(len_parts) > 1 else None

        variables.append({
            'name': var_name,
            'type': var_type,
            'length': length,
            'precision': precision
        })

    # Extract called programs from CALL statements
    # Pattern: CALL PGM(program_name)
    called_programs = []
    call_pattern = r'CALL\s+PGM\(([A-Z0-9_]+)\)'

    for match in re.finditer(call_pattern, content_upper, re.IGNORECASE):
        called_programs.append(match.group(1))

    # Extract labels (program flow control)
    # Pattern: LABEL: or GOTO CMDLBL(LABEL)
    labels = []
    label_pattern = r'^\s*([A-Z0-9_]+):'

    for match in re.finditer(label_pattern, content, re.MULTILINE | re.IGNORECASE):
        label_name = match.group(1)
        if label_name not in labels:
            labels.append(label_name)

    # Extract CLP commands used
    clp_commands = []
    command_patterns = [
        'CHGVAR', 'IF', 'THEN', 'ELSE', 'ENDDO', 'GOTO', 'ENDPGM',
        'SNDPGMMSG', 'MONMSG', 'RTVJOBA', 'RTVMBRD', 'OVRDBF',
        'DLTOVR', 'CLRPFM', 'CPYF', 'DLYJOB'
    ]

    for cmd in command_patterns:
        if cmd in content_upper:
            clp_commands.append(cmd)

    # Count lines and comments
    lines = content.splitlines()
    comment_count = sum(1 for line in lines if line.strip().startswith('/*'))
    code_lines = len(lines) - comment_count

    return {
        'file_name': file_name,
        'file_type': 'CLP',
        'confidence': 0.9,
        'program': {
            'name': program_name,
            'parameters': parameters,
            'parameter_count': len(parameters)
        },
        'variables': variables,
        'variable_count': len(variables),
        'called_programs': sorted(set(called_programs)),
        'called_program_count': len(set(called_programs)),
        'labels': labels,
        'label_count': len(labels),
        'commands': clp_commands,
        'command_count': len(clp_commands),
        'statistics': {
            'total_lines': len(lines),
            'code_lines': code_lines,
            'comment_lines': comment_count
        },
        'paragraphs': [],
        'paragraph_count': 0,
        'note': 'CLP - IBM i Control Language Program with DETAILED extraction'
    }


def parse_jcl(file_name: str, content: str) -> Dict[str, Any]:
    """Parse JCL file"""
    return {
        'file_name': file_name,
        'file_type': 'JCL',
        'confidence': 0.6,
        'paragraphs': [],
        'paragraph_count': 0
    }


def parse_db2_ddl(file_name: str, content: str) -> Dict[str, Any]:
    """Parse DB2 DDL file"""
    return {
        'file_name': file_name,
        'file_type': 'DB2_DDL',
        'confidence': 0.6,
        'paragraphs': [],
        'paragraph_count': 0
    }


def parse_unknown(file_name: str, content: str) -> Dict[str, Any]:
    """Parse unknown file type"""
    return {
        'file_name': file_name,
        'file_type': 'UNKNOWN',
        'confidence': 0.3,
        'paragraphs': [],
        'paragraph_count': 0
    }
