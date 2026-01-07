"""
COBOL File Section Semantic Model Parser

Parses FILE SECTION and ENVIRONMENT DIVISION file definitions.
Works with ANY COBOL file - not hardcoded to specific files.

Input: Line inventory JSON (from cobol_parse_export.py)
Output: File model JSON with:
  - SELECT statements (file assignments)
  - FD definitions (file descriptions)
  - Record layouts
  - File modes (INPUT, OUTPUT, I-O)

Date: December 2025
"""

import json
import re
from pathlib import Path
from typing import Optional, List
from datetime import datetime


class FileSectionParser:
    """Parse FILE SECTION and file-related definitions."""

    def __init__(self, line_inventory: dict):
        """Initialize parser with line inventory."""
        self.lines = line_inventory.get('lines', [])
        self.source_file = line_inventory.get('source_file', 'unknown')
        self.file_model = {
            'source_file': self.source_file,
            'generated': datetime.now().isoformat(),
            'select_statements': [],
            'file_descriptions': [],
            'file_operations': {
                'open': [],
                'close': [],
                'read': [],
                'write': []
            },
            'summary': {}
        }

    def find_environment_division_bounds(self) -> tuple:
        """Find ENVIRONMENT DIVISION bounds for SELECT statements."""
        start_line = None
        end_line = None

        for line in self.lines:
            text = line['raw_text'].upper()
            line_num = line['line_num']

            if 'ENVIRONMENT DIVISION' in text and start_line is None:
                start_line = line_num

            if 'DATA DIVISION' in text and start_line is not None:
                end_line = line_num - 1
                break

        return (start_line, end_line)

    def find_file_section_bounds(self) -> tuple:
        """Find FILE SECTION bounds for FD definitions."""
        start_line = None
        end_line = None

        for line in self.lines:
            text = line['raw_text'].upper()
            line_num = line['line_num']

            if 'FILE SECTION' in text and start_line is None:
                start_line = line_num

            if start_line is not None:
                # End at WORKING-STORAGE or other section
                if any(x in text for x in ['WORKING-STORAGE', 'LOCAL-STORAGE', 'LINKAGE SECTION', 'PROCEDURE DIVISION']):
                    end_line = line_num - 1
                    break

        return (start_line, end_line)

    def parse_select_statement(self, lines: List[dict], start_idx: int) -> Optional[dict]:
        """Parse a SELECT statement (may span multiple lines)."""
        result = {
            'file_name': None,
            'assign_to': None,
            'organization': None,
            'access_mode': None,
            'record_key': None,
            'file_status': None,
            'start_line': None,
            'end_line': None,
            'raw_text': ''
        }

        # Collect full SELECT statement (may span multiple lines)
        full_text = ''
        start_line = None
        end_line = None

        for i in range(start_idx, len(lines)):
            line = lines[i]
            text = line['raw_text']
            content = text[6:72] if len(text) > 6 else text

            if start_line is None:
                start_line = line['line_num']

            full_text += ' ' + content
            end_line = line['line_num']

            # Check if statement ends (period found)
            if '.' in content:
                break

        result['start_line'] = start_line
        result['end_line'] = end_line
        result['raw_text'] = full_text.strip()

        upper = full_text.upper()

        # Parse SELECT file-name
        select_match = re.search(r'SELECT\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if select_match:
            result['file_name'] = select_match.group(1)

        # Parse ASSIGN TO
        assign_match = re.search(r'ASSIGN\s+TO\s+([A-Z0-9][-A-Z0-9]*)', upper)
        if assign_match:
            result['assign_to'] = assign_match.group(1)

        # Parse ORGANIZATION
        org_match = re.search(r'ORGANIZATION\s+IS\s+([A-Z]+)', upper)
        if org_match:
            result['organization'] = org_match.group(1)

        # Parse ACCESS MODE
        access_match = re.search(r'ACCESS\s+(?:MODE\s+)?(?:IS\s+)?([A-Z]+)', upper)
        if access_match:
            result['access_mode'] = access_match.group(1)

        # Parse RECORD KEY
        key_match = re.search(r'RECORD\s+KEY\s+(?:IS\s+)?([A-Z0-9][-A-Z0-9]*)', upper)
        if key_match:
            result['record_key'] = key_match.group(1)

        # Parse FILE STATUS
        status_match = re.search(r'FILE\s+STATUS\s+(?:IS\s+)?([A-Z0-9][-A-Z0-9]*)', upper)
        if status_match:
            result['file_status'] = status_match.group(1)

        return result if result['file_name'] else None

    def parse_fd_definition(self, lines: List[dict], start_idx: int) -> Optional[dict]:
        """Parse an FD (File Description) definition."""
        result = {
            'file_name': None,
            'record_name': None,
            'record_size': None,
            'block_contains': None,
            'label_records': None,
            'start_line': None,
            'end_line': None,
            'record_fields': []
        }

        line = lines[start_idx]
        text = line['raw_text']
        content = text[6:72] if len(text) > 6 else text

        result['start_line'] = line['line_num']

        # Parse FD file-name
        fd_match = re.search(r'FD\s+([A-Z0-9][-A-Z0-9]*)', content, re.IGNORECASE)
        if not fd_match:
            return None

        result['file_name'] = fd_match.group(1).upper()

        # Look for record definition (01 level after FD)
        for i in range(start_idx + 1, min(start_idx + 20, len(lines))):
            next_line = lines[i]
            next_content = next_line['raw_text'][6:72] if len(next_line['raw_text']) > 6 else next_line['raw_text']
            next_upper = next_content.strip().upper()

            # Stop if we hit another FD or section
            if next_upper.startswith('FD ') or 'SECTION' in next_upper:
                result['end_line'] = lines[i - 1]['line_num']
                break

            # Look for 01 level record
            if next_upper.startswith('01 '):
                record_match = re.search(r'01\s+([A-Z0-9][-A-Z0-9]*)', next_upper)
                if record_match:
                    result['record_name'] = record_match.group(1)
                    result['end_line'] = next_line['line_num']
                    # Could parse record fields here
                    break

        if not result['end_line']:
            result['end_line'] = result['start_line']

        return result

    def find_file_operations(self) -> None:
        """Find all OPEN, CLOSE, READ, WRITE operations in PROCEDURE DIVISION."""
        for line in self.lines:
            classification = line.get('classification', '')
            content = line['raw_text'][6:72] if len(line['raw_text']) > 6 else line['raw_text']
            upper = content.strip().upper()

            if classification == 'OPEN' or upper.startswith('OPEN '):
                operation = {
                    'line_num': line['line_num'],
                    'mode': None,
                    'files': []
                }
                if 'INPUT' in upper:
                    operation['mode'] = 'INPUT'
                elif 'OUTPUT' in upper:
                    operation['mode'] = 'OUTPUT'
                elif 'I-O' in upper or 'I/O' in upper:
                    operation['mode'] = 'I-O'
                elif 'EXTEND' in upper:
                    operation['mode'] = 'EXTEND'

                # Extract file names
                files_part = re.sub(r'OPEN\s+(INPUT|OUTPUT|I-O|I/O|EXTEND)\s*', '', upper)
                operation['files'] = [f.strip() for f in files_part.split() if f.strip() and f not in ('INPUT', 'OUTPUT', 'I-O')]
                self.file_model['file_operations']['open'].append(operation)

            elif classification == 'CLOSE' or upper.startswith('CLOSE '):
                operation = {
                    'line_num': line['line_num'],
                    'files': []
                }
                files_part = re.sub(r'CLOSE\s*', '', upper).rstrip('.')
                operation['files'] = [f.strip() for f in files_part.split() if f.strip()]
                self.file_model['file_operations']['close'].append(operation)

            elif classification == 'READ' or upper.startswith('READ '):
                operation = {
                    'line_num': line['line_num'],
                    'file': None,
                    'into': None
                }
                file_match = re.search(r'READ\s+([A-Z0-9][-A-Z0-9]*)', upper)
                if file_match:
                    operation['file'] = file_match.group(1)
                into_match = re.search(r'INTO\s+([A-Z0-9][-A-Z0-9]*)', upper)
                if into_match:
                    operation['into'] = into_match.group(1)
                self.file_model['file_operations']['read'].append(operation)

            elif classification == 'WRITE' or upper.startswith('WRITE '):
                operation = {
                    'line_num': line['line_num'],
                    'record': None,
                    'from_var': None
                }
                rec_match = re.search(r'WRITE\s+([A-Z0-9][-A-Z0-9]*)', upper)
                if rec_match:
                    operation['record'] = rec_match.group(1)
                from_match = re.search(r'FROM\s+([A-Z0-9][-A-Z0-9]*)', upper)
                if from_match:
                    operation['from_var'] = from_match.group(1)
                self.file_model['file_operations']['write'].append(operation)

    def build_model(self) -> dict:
        """Build complete file semantic model."""
        # Parse SELECT statements from ENVIRONMENT DIVISION
        env_start, env_end = self.find_environment_division_bounds()
        if env_start and env_end:
            env_lines = [l for l in self.lines if env_start <= l['line_num'] <= env_end]
            i = 0
            while i < len(env_lines):
                content = env_lines[i]['raw_text'].upper()
                if 'SELECT ' in content:
                    select = self.parse_select_statement(env_lines, i)
                    if select:
                        self.file_model['select_statements'].append(select)
                i += 1

        # Parse FD definitions from FILE SECTION
        file_start, file_end = self.find_file_section_bounds()
        if file_start and file_end:
            file_lines = [l for l in self.lines if file_start <= l['line_num'] <= file_end]
            for i, line in enumerate(file_lines):
                content = line['raw_text'].upper()
                if content.strip().startswith('FD ') or ' FD ' in content:
                    fd = self.parse_fd_definition(file_lines, i)
                    if fd:
                        self.file_model['file_descriptions'].append(fd)

        # Find file operations in PROCEDURE DIVISION
        self.find_file_operations()

        # Build summary
        self.file_model['summary'] = {
            'select_count': len(self.file_model['select_statements']),
            'fd_count': len(self.file_model['file_descriptions']),
            'open_count': len(self.file_model['file_operations']['open']),
            'close_count': len(self.file_model['file_operations']['close']),
            'read_count': len(self.file_model['file_operations']['read']),
            'write_count': len(self.file_model['file_operations']['write'])
        }

        return self.file_model


def parse_file_section(line_inventory_path: Path, output_path: Path) -> dict:
    """Parse file definitions and output semantic model."""
    with open(line_inventory_path) as f:
        inventory = json.load(f)

    parser = FileSectionParser(inventory)
    model = parser.build_model()

    with open(output_path, 'w') as f:
        json.dump(model, f, indent=2, ensure_ascii=False)

    return {
        'output_path': str(output_path),
        'summary': model['summary']
    }


if __name__ == '__main__':
    import sys

    inventory_path = Path("reports/ifpr321_line_inventory.json")
    output_path = Path("reports/ifpr321_file_model.json")

    if len(sys.argv) >= 3:
        inventory_path = Path(sys.argv[1])
        output_path = Path(sys.argv[2])

    if not inventory_path.exists():
        print(f"ERROR: {inventory_path} not found")
        sys.exit(1)

    print("=" * 60)
    print("COBOL File Section Parser")
    print("=" * 60)
    print(f"\nInput:  {inventory_path}")
    print(f"Output: {output_path}")

    result = parse_file_section(inventory_path, output_path)

    print(f"\n=== FILE MODEL SUMMARY ===")
    for key, value in result['summary'].items():
        print(f"  {key}: {value}")

    print(f"\nOutput written to: {output_path}")
    print("=" * 60)
