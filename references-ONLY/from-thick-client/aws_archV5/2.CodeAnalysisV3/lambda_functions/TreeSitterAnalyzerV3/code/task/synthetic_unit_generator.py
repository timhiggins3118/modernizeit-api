"""
Synthetic Unit Generator

Purpose: Generate synthetic units (SYN-BLOCK-*) when no paragraphs found
Strategy: Use sections, control flow, or statement grouping to create units

This is the KEY V3 innovation that prevents pipeline breaks when paragraphs = 0

Date: November 3, 2025
Version: V3.0
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Target statements per synthetic unit (configurable)
TARGET_STATEMENTS_PER_UNIT = 20


def generate_synthetic_units(file_name: str, content: str, parse_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate synthetic units when no paragraphs found

    Strategy (in order of preference):
    1. Use sections as unit boundaries
    2. Use control flow patterns (IF/PERFORM blocks)
    3. Fall back to statement grouping

    Args:
        file_name: Name of the file
        content: COBOL source code
        parse_result: Result from cobol_parser

    Returns:
        List of synthetic unit dictionaries
    """
    logger.warning(f"Generating synthetic units for {file_name} (no paragraphs found)")

    # Strategy 1: Use sections
    if parse_result.get('sections') and len(parse_result['sections']) > 0:
        logger.info("Using sections as synthetic units")
        return generate_units_from_sections(content, parse_result['sections'])

    # Strategy 2: Use control flow
    logger.info("Attempting to generate units from control flow")
    units_from_flow = generate_units_from_control_flow(content)
    if units_from_flow:
        return units_from_flow

    # Strategy 3: Fall back to statement grouping
    logger.info("Falling back to statement grouping")
    return generate_units_from_statements(content)


def generate_units_from_sections(content: str, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate synthetic units based on sections

    Args:
        content: COBOL source code
        sections: List of sections from parse_result

    Returns:
        List of synthetic units
    """
    units = []
    lines = content.split('\n')

    for i, section in enumerate(sections):
        # Determine section boundaries
        start_line = section['line']

        if i + 1 < len(sections):
            end_line = sections[i + 1]['line'] - 1
        else:
            end_line = len(lines)

        # Extract section content
        section_lines = lines[start_line:end_line]
        section_content = '\n'.join(section_lines)

        # Extract statements from section
        statements = extract_statements_from_block(section_content, start_line + 1)

        unit = {
            'name': f"SYN-BLOCK-{i + 1}",
            'original_section': section['name'],
            'start_line': start_line,
            'end_line': end_line,
            'line_count': end_line - start_line,
            'statements': statements,
            'statement_count': len(statements),
            'synthetic': True,
            'generation_method': 'section_based'
        }

        units.append(unit)

    logger.info(f"Generated {len(units)} synthetic units from sections")
    return units


def generate_units_from_control_flow(content: str) -> List[Dict[str, Any]]:
    """
    Generate synthetic units based on control flow patterns

    Args:
        content: COBOL source code

    Returns:
        List of synthetic units (or empty if not applicable)
    """
    # Look for PROCEDURE DIVISION
    lines = content.split('\n')
    procedure_start = None

    for i, line in enumerate(lines):
        if 'PROCEDURE DIVISION' in line.upper():
            procedure_start = i + 1
            break

    if procedure_start is None:
        return []

    # Extract procedure division content
    procedure_lines = lines[procedure_start:]
    procedure_content = '\n'.join(procedure_lines)

    # Group by statement count
    units = []
    current_unit_lines = []
    current_unit_start = procedure_start
    unit_id = 1

    for i, line in enumerate(procedure_lines):
        current_unit_lines.append(line)

        # Create a unit every TARGET_STATEMENTS_PER_UNIT lines (simple heuristic)
        if len(current_unit_lines) >= TARGET_STATEMENTS_PER_UNIT:
            # Extract statements
            unit_content = '\n'.join(current_unit_lines)
            statements = extract_statements_from_block(unit_content, current_unit_start)

            if len(statements) > 0:
                unit = {
                    'name': f"SYN-BLOCK-{unit_id}",
                    'start_line': current_unit_start,
                    'end_line': current_unit_start + len(current_unit_lines),
                    'line_count': len(current_unit_lines),
                    'statements': statements,
                    'statement_count': len(statements),
                    'synthetic': True,
                    'generation_method': 'control_flow_based'
                }

                units.append(unit)
                unit_id += 1

            # Reset for next unit
            current_unit_lines = []
            current_unit_start = procedure_start + i + 1

    # Handle remaining lines
    if current_unit_lines:
        unit_content = '\n'.join(current_unit_lines)
        statements = extract_statements_from_block(unit_content, current_unit_start)

        if len(statements) > 0:
            unit = {
                'name': f"SYN-BLOCK-{unit_id}",
                'start_line': current_unit_start,
                'end_line': current_unit_start + len(current_unit_lines),
                'line_count': len(current_unit_lines),
                'statements': statements,
                'statement_count': len(statements),
                'synthetic': True,
                'generation_method': 'control_flow_based'
            }

            units.append(unit)

    logger.info(f"Generated {len(units)} synthetic units from control flow")
    return units


def generate_units_from_statements(content: str) -> List[Dict[str, Any]]:
    """
    Generate synthetic units based on statement grouping (fallback)

    Args:
        content: COBOL source code

    Returns:
        List of synthetic units
    """
    lines = content.split('\n')
    units = []
    unit_id = 1

    # Simple strategy: Group every 30 lines into a unit
    chunk_size = 30
    for i in range(0, len(lines), chunk_size):
        chunk_lines = lines[i:i + chunk_size]
        chunk_content = '\n'.join(chunk_lines)

        statements = extract_statements_from_block(chunk_content, i + 1)

        if len(statements) > 0:
            unit = {
                'name': f"SYN-BLOCK-{unit_id}",
                'start_line': i + 1,
                'end_line': i + len(chunk_lines),
                'line_count': len(chunk_lines),
                'statements': statements,
                'statement_count': len(statements),
                'synthetic': True,
                'generation_method': 'statement_grouping'
            }

            units.append(unit)
            unit_id += 1

    logger.info(f"Generated {len(units)} synthetic units from statement grouping")
    return units


def extract_statements_from_block(block_content: str, start_line: int) -> List[Dict[str, Any]]:
    """
    Extract statements from a block of code

    Args:
        block_content: Block content
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

    lines = block_content.split('\n')
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


def validate_synthetic_units(units: List[Dict[str, Any]]) -> bool:
    """
    Validate that synthetic units meet minimum requirements

    Args:
        units: List of synthetic units

    Returns:
        True if valid
    """
    if len(units) == 0:
        logger.error("Synthetic unit generation produced 0 units (CRITICAL)")
        return False

    for unit in units:
        if unit['statement_count'] == 0:
            logger.warning(f"Synthetic unit {unit['name']} has 0 statements")
            return False

    logger.info(f"Synthetic units validation passed: {len(units)} units generated")
    return True
