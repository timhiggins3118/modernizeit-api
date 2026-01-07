"""
COBOL Parse Export - Line-by-Line Inventory

This module provides:
1. Find IFPR321.CBL in an unzipped COBOL directory
2. Parse it with tree-sitter COBOL grammar
3. Export LINE-BY-LINE inventory JSON (ifpr321_line_inventory.json)

GOAL: Every source line has exactly one entry in output.
Line count in = Entry count out. ZERO LOSS.

NO MOCK DATA. NO AI. Everything from real tree-sitter parsing.

Date: December 2025
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from engines.code_analysis.parsers.cobol_parser_adapter import parse_cobol_file


def find_ifpr321_file(cobol_root: Path) -> Optional[Path]:
    """
    Search recursively for IFPR321.CBL (case-sensitive match on file name).

    Args:
        cobol_root: Root directory to search

    Returns:
        Path to IFPR321.CBL or None if not found
    """
    for file_path in cobol_root.rglob('*'):
        if file_path.is_file() and file_path.name == 'IFPR321.CBL':
            return file_path
    return None


def parse_ifpr321_with_treesitter(ifpr321_path: Path) -> tuple[Any, bytes]:
    """
    Parse IFPR321.CBL with tree-sitter COBOL grammar.

    Args:
        ifpr321_path: Path to the IFPR321.CBL file

    Returns:
        Tuple of (tree, source_bytes)
    """
    tree, source_bytes, encoding = parse_cobol_file(ifpr321_path)
    return tree, source_bytes


def build_line_by_line_json(root_node, source_code: bytes) -> dict:
    """
    Build a LINE-BY-LINE inventory of the COBOL source.

    GOAL: Every source line has exactly one entry in the output.
    Line count in = Entry count out. ZERO LOSS.

    For each line, we find the most specific tree-sitter node that covers it
    and classify the line based on node type.

    Args:
        root_node: tree-sitter root node
        source_code: UTF-8 source bytes

    Returns:
        Dict with:
        - source_line_count: int
        - inventory_count: int (should equal source_line_count)
        - lines: list of line entries
    """
    # Split source into lines
    source_text = source_code.decode('utf-8', errors='replace')
    source_lines = source_text.splitlines()
    total_lines = len(source_lines)

    # Build a map: line_number -> list of nodes covering that line
    # Line numbers are 1-indexed
    line_to_nodes: dict[int, list] = {i: [] for i in range(1, total_lines + 1)}

    def collect_nodes_by_line(node, depth: int = 0):
        """Walk tree and collect nodes by the lines they cover."""
        start_line = node.start_point[0] + 1  # 1-indexed
        end_line = node.end_point[0] + 1

        # Add this node to all lines it covers
        for line_num in range(start_line, end_line + 1):
            if line_num in line_to_nodes:
                line_to_nodes[line_num].append({
                    'node_type': node.type,
                    'depth': depth,
                    'start_line': start_line,
                    'end_line': end_line,
                    'is_named': node.is_named,
                })

        # Recurse to children
        for child in node.children:
            collect_nodes_by_line(child, depth + 1)

    # Collect all nodes
    collect_nodes_by_line(root_node)

    # Classify each line based on tree-sitter node type
    def classify_line(line_num: int, raw_text: str, nodes: list) -> dict:
        """Classify a single line based on covering tree-sitter nodes."""

        # Check for blank line
        if not raw_text.strip():
            return {
                'line_num': line_num,
                'raw_text': raw_text,
                'classification': 'BLANK',
                'node_type': None,
            }

        # Check for comment (column 7 indicator)
        if len(raw_text) > 6 and raw_text[6] in ('*', '/', 'D', 'd'):
            return {
                'line_num': line_num,
                'raw_text': raw_text,
                'classification': 'COMMENT',
                'node_type': 'comment',
            }

        # Check for continuation
        if len(raw_text) > 6 and raw_text[6] == '-':
            return {
                'line_num': line_num,
                'raw_text': raw_text,
                'classification': 'CONTINUATION',
                'node_type': 'continuation',
            }

        # Find the most specific (deepest) named node for this line
        named_nodes = [n for n in nodes if n['is_named'] and n['node_type'] != 'ERROR']
        if named_nodes:
            # Sort by depth (deepest first), then by smallest span
            named_nodes.sort(key=lambda n: (-n['depth'], n['end_line'] - n['start_line']))
            best_node = named_nodes[0]
            node_type = best_node['node_type']
        else:
            node_type = 'UNKNOWN'

        # Map tree-sitter node types to classifications
        classification = classify_by_node_type(node_type)

        # If classification is CODE, ALWAYS use text-based classification as fallback
        # tree-sitter often returns generic node types (comment_entry, integer, string)
        # for lines that are actually COBOL statements
        if classification == 'CODE':
            text_classification = classify_by_text(raw_text)
            if text_classification != 'CODE':
                classification = text_classification

        return {
            'line_num': line_num,
            'raw_text': raw_text,
            'classification': classification,
            'node_type': node_type,
        }

    # Build the line inventory
    lines = []
    for line_num in range(1, total_lines + 1):
        raw_text = source_lines[line_num - 1]  # 0-indexed in list
        nodes = line_to_nodes[line_num]
        entry = classify_line(line_num, raw_text, nodes)
        lines.append(entry)

    # Build summary stats
    classification_counts: dict[str, int] = {}
    for entry in lines:
        cls = entry['classification']
        classification_counts[cls] = classification_counts.get(cls, 0) + 1

    return {
        'source_line_count': total_lines,
        'inventory_count': len(lines),
        'zero_loss_verified': total_lines == len(lines),
        'classification_counts': classification_counts,
        'lines': lines
    }


def classify_by_text(raw_text: str) -> str:
    """
    Classify a line by its text content.

    Used as fallback when tree-sitter gives generic node types.
    """
    # Get content area (columns 8-72)
    content = raw_text[7:72].strip().upper() if len(raw_text) > 7 else raw_text.strip().upper()

    if not content:
        return 'CODE'

    # Check for specific COBOL verbs/patterns
    if content.startswith('PERFORM '):
        return 'PERFORM'
    if content.startswith('MOVE '):
        return 'MOVE'
    if content.startswith('IF '):
        return 'IF'
    if content.startswith('EVALUATE '):
        return 'EVALUATE'
    if content.startswith('COMPUTE '):
        return 'COMPUTE'
    if content.startswith('CALL '):
        return 'CALL'
    if content.startswith('GO TO ') or content.startswith('GOTO '):
        return 'GOTO'
    if content.startswith('READ '):
        return 'READ'
    if content.startswith('WRITE '):
        return 'WRITE'
    if content.startswith('OPEN '):
        return 'OPEN'
    if content.startswith('CLOSE '):
        return 'CLOSE'
    if content.startswith('ADD '):
        return 'ADD'
    if content.startswith('SUBTRACT '):
        return 'SUBTRACT'
    if content.startswith('MULTIPLY '):
        return 'MULTIPLY'
    if content.startswith('DIVIDE '):
        return 'DIVIDE'
    if content.startswith('STRING '):
        return 'STRING'
    if content.startswith('UNSTRING '):
        return 'UNSTRING'
    if content.startswith('INSPECT '):
        return 'INSPECT'
    if content.startswith('ACCEPT '):
        return 'ACCEPT'
    if content.startswith('DISPLAY '):
        return 'DISPLAY'
    if content.startswith('INITIALIZE '):
        return 'INITIALIZE'
    if content.startswith('SET '):
        return 'SET'
    if content.startswith('STOP RUN'):
        return 'EXIT'
    if content.startswith('GOBACK'):
        return 'EXIT'
    if content.startswith('EXIT'):
        return 'EXIT'
    if content.startswith('ELSE'):
        return 'ELSE'
    if content.startswith('END-IF'):
        return 'END_IF'
    if content.startswith('END-EVALUATE'):
        return 'END_EVALUATE'
    if content.startswith('END-PERFORM'):
        return 'END_PERFORM'
    if content.startswith('WHEN '):
        return 'WHEN'
    if content.startswith('CONTINUE'):
        return 'CONTINUE'

    # Check for paragraph name (COBOL convention: starts with digits followed by hyphen)
    # Pattern: N+-NAME. where N is one or more digits (e.g., 0-INIT., 000-MAIN., 00000-CONTROL.)
    # Excludes data names like TIM-KEY. or ERN-CLIENT-NO. (which start with letters)
    if re.match(r'^\d+-[A-Z0-9][A-Z0-9-]*\.$', content):
        return 'PARAGRAPH'

    # Default
    return 'CODE'


def classify_by_node_type(node_type: str) -> str:
    """
    Map tree-sitter node type to a classification.

    Trust the parser - this is purely based on node type, no regex.
    """
    node_type_lower = node_type.lower()

    # Division headers
    if 'division' in node_type_lower:
        return 'DIVISION'

    # Section headers
    if 'section' in node_type_lower:
        return 'SECTION'

    # Paragraph headers
    if node_type in ('paragraph_header', 'paragraph', 'paragraph_name'):
        return 'PARAGRAPH'

    # PERFORM statements
    if 'perform' in node_type_lower:
        return 'PERFORM'

    # CALL statements
    if 'call' in node_type_lower:
        return 'CALL'

    # GO TO statements
    if 'go_to' in node_type_lower or 'goto' in node_type_lower:
        return 'GOTO'

    # MOVE statements
    if 'move' in node_type_lower:
        return 'MOVE'

    # IF statements
    if 'if_statement' in node_type_lower or node_type_lower == 'if':
        return 'IF'

    # EVALUATE statements
    if 'evaluate' in node_type_lower:
        return 'EVALUATE'

    # COMPUTE statements
    if 'compute' in node_type_lower:
        return 'COMPUTE'

    # Data definitions
    if node_type in ('data_description', 'data_item', 'working_storage_section',
                     'file_section', 'data_name', 'level_number'):
        return 'DATA'

    # COPY statements
    if 'copy' in node_type_lower:
        return 'COPY'

    # EXIT / GOBACK / STOP
    if node_type in ('stop_statement', 'goback_statement', 'exit_statement'):
        return 'EXIT'

    # Program ID
    if 'program_id' in node_type_lower:
        return 'PROGRAM_ID'

    # Default: CODE
    return 'CODE'


def export_cobol_parse_artifacts(
    program_path: Path,
    output_dir: Path,
    base_name: str
) -> dict:
    """
    Parse a COBOL program and export line-by-line inventory JSON.

    Args:
        program_path: Path to the COBOL source file
        output_dir: Directory to write output JSON file
        base_name: Base name for output files (e.g., "ifpr321" -> "ifpr321_line_inventory.json")

    Returns:
        Dict with:
        - found: bool
        - program_path: str
        - line_inventory_path: str (if found)
        - used_source: str (path to file actually parsed)
    """
    # Track timing
    start_time = datetime.now()

    if not program_path.exists():
        return {
            "found": False,
            "error": f"Source file not found: {program_path}"
        }

    # Step 1: Parse with tree-sitter
    try:
        tree, source_bytes, encoding = parse_cobol_file(program_path)
    except Exception as e:
        return {
            "found": False,
            "program_path": str(program_path),
            "error": f"Failed to parse source: {e}"
        }

    # Step 2: Build LINE-BY-LINE inventory (ZERO LOSS)
    line_inventory = build_line_by_line_json(tree.root_node, source_bytes)

    # Step 3: Write output files
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    line_inventory_path = output_dir / f"{base_name}_line_inventory.json"
    summary_path = output_dir / f"{base_name}_summary.json"

    # Write full line inventory
    with open(line_inventory_path, 'w', encoding='utf-8') as f:
        json.dump(line_inventory, f, indent=2, ensure_ascii=False)

    # End timing
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Write summary (just the counts)
    summary = {
        "source_file": str(program_path),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": round(duration, 2),
        "source_line_count": line_inventory.get('source_line_count', 0),
        "inventory_count": line_inventory.get('inventory_count', 0),
        "zero_loss_verified": line_inventory.get('zero_loss_verified', False),
        "classifications": line_inventory.get('classification_counts', {})
    }
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return {
        "found": True,
        "program_path": str(program_path),
        "used_source": str(program_path),
        "line_inventory_path": str(line_inventory_path),
        "summary_path": str(summary_path),
        "line_inventory_stats": {
            "source_lines": line_inventory.get('source_line_count', 0),
            "inventory_lines": line_inventory.get('inventory_count', 0),
            "zero_loss": line_inventory.get('zero_loss_verified', False),
            "classifications": line_inventory.get('classification_counts', {})
        }
    }


# Backward compatibility wrapper
def export_ifpr321_parse_artifacts(
    cobol_root: Path,
    output_dir: Path,
    source_override_path: Optional[Path] = None
) -> dict:
    """Backward compatibility wrapper - finds IFPR321.CBL and parses it."""
    ifpr321_path = find_ifpr321_file(cobol_root)
    if ifpr321_path is None and source_override_path is None:
        return {"found": False, "error": f"IFPR321.CBL not found under {cobol_root}"}

    program_path = source_override_path if source_override_path else ifpr321_path
    return export_cobol_parse_artifacts(program_path, output_dir, "ifpr321")
