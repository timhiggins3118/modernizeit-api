"""
Statement-Level Traceability

Purpose: Ensure every statement has stmt_id and line for AI evidence citation
Strategy: Validate and normalize statement traceability across all units

Date: November 3, 2025
Version: V3.0
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def add_statement_traceability(parse_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure all statements have proper stmt_id and line traceability

    Args:
        parse_result: Parse result from cobol_parser or synthetic_unit_generator

    Returns:
        Parse result with validated traceability
    """
    logger.info("Adding statement-level traceability")

    # Get units (either paragraphs or synthetic units)
    if 'units' in parse_result:
        units = parse_result['units']
    elif 'paragraphs' in parse_result:
        units = parse_result['paragraphs']
    else:
        logger.warning("No units or paragraphs found in parse result")
        return parse_result

    # Validate and normalize each unit's statements
    for unit in units:
        if 'statements' not in unit:
            logger.warning(f"Unit {unit.get('name', 'UNKNOWN')} has no statements")
            unit['statements'] = []
            continue

        unit['statements'] = validate_and_normalize_statements(
            unit['statements'],
            unit.get('name', 'UNKNOWN')
        )

    # Update parse result
    if 'units' in parse_result:
        parse_result['units'] = units
    elif 'paragraphs' in parse_result:
        parse_result['paragraphs'] = units

    # Add traceability metadata
    parse_result['traceability'] = {
        'enabled': True,
        'version': 'v3.0',
        'statement_id_format': 's{n}',
        'line_numbers_present': True
    }

    logger.info("Statement traceability added successfully")
    return parse_result


def validate_and_normalize_statements(statements: List[Dict[str, Any]], unit_name: str) -> List[Dict[str, Any]]:
    """
    Validate and normalize statement traceability

    Args:
        statements: List of statement dictionaries
        unit_name: Name of the unit (for logging)

    Returns:
        Normalized statements
    """
    normalized = []

    for i, stmt in enumerate(statements):
        # Ensure stmt_id exists
        if 'stmt_id' not in stmt:
            stmt['stmt_id'] = f's{i + 1}'
            logger.warning(f"Added missing stmt_id for statement in {unit_name}: {stmt['stmt_id']}")

        # Ensure line exists
        if 'line' not in stmt:
            logger.error(f"Statement {stmt['stmt_id']} in {unit_name} missing line number")
            stmt['line'] = -1  # Indicate missing line

        # Ensure operation exists
        if 'operation' not in stmt:
            logger.warning(f"Statement {stmt['stmt_id']} in {unit_name} missing operation")
            stmt['operation'] = 'UNKNOWN'

        # Add traceability metadata to each statement
        stmt['traceability'] = {
            'stmt_id': stmt['stmt_id'],
            'line': stmt['line'],
            'unit': unit_name
        }

        normalized.append(stmt)

    return normalized


def extract_traceability_map(parse_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract a traceability map for quick lookup

    Args:
        parse_result: Parse result with traceability

    Returns:
        Dictionary mapping stmt_id to line and unit
    """
    traceability_map = {}

    units = parse_result.get('units', parse_result.get('paragraphs', []))

    for unit in units:
        unit_name = unit.get('name', 'UNKNOWN')

        for stmt in unit.get('statements', []):
            stmt_id = stmt.get('stmt_id')
            line = stmt.get('line')

            if stmt_id:
                traceability_map[stmt_id] = {
                    'line': line,
                    'unit': unit_name,
                    'operation': stmt.get('operation', 'UNKNOWN')
                }

    return traceability_map


def validate_traceability_completeness(parse_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that all statements have complete traceability

    Args:
        parse_result: Parse result to validate

    Returns:
        Validation report
    """
    total_statements = 0
    statements_with_stmt_id = 0
    statements_with_line = 0
    statements_missing_traceability = []

    units = parse_result.get('units', parse_result.get('paragraphs', []))

    for unit in units:
        unit_name = unit.get('name', 'UNKNOWN')

        for stmt in unit.get('statements', []):
            total_statements += 1

            if 'stmt_id' in stmt and stmt['stmt_id']:
                statements_with_stmt_id += 1

            if 'line' in stmt and stmt['line'] > 0:
                statements_with_line += 1

            # Check if statement is missing any traceability
            if 'stmt_id' not in stmt or 'line' not in stmt or stmt.get('line', -1) < 0:
                statements_missing_traceability.append({
                    'unit': unit_name,
                    'stmt_id': stmt.get('stmt_id', 'MISSING'),
                    'line': stmt.get('line', -1)
                })

    validation_report = {
        'total_statements': total_statements,
        'statements_with_stmt_id': statements_with_stmt_id,
        'statements_with_line': statements_with_line,
        'stmt_id_coverage': round(statements_with_stmt_id / max(total_statements, 1), 3),
        'line_coverage': round(statements_with_line / max(total_statements, 1), 3),
        'complete_traceability': len(statements_missing_traceability) == 0,
        'missing_traceability_count': len(statements_missing_traceability),
        'missing_traceability_samples': statements_missing_traceability[:5]  # First 5 samples
    }

    logger.info(f"Traceability validation: {validation_report['stmt_id_coverage']*100:.1f}% stmt_id coverage, "
                f"{validation_report['line_coverage']*100:.1f}% line coverage")

    return validation_report


def add_traceability_to_unit(unit: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add traceability metadata to a single unit

    Args:
        unit: Unit dictionary (paragraph or synthetic unit)

    Returns:
        Unit with added traceability
    """
    unit['traceability'] = {
        'unit_name': unit.get('name', 'UNKNOWN'),
        'start_line': unit.get('start_line', -1),
        'end_line': unit.get('end_line', -1),
        'statement_count': unit.get('statement_count', 0),
        'has_stmt_ids': all('stmt_id' in stmt for stmt in unit.get('statements', [])),
        'has_line_numbers': all('line' in stmt for stmt in unit.get('statements', []))
    }

    return unit
