"""
COBOL Data Division Semantic Model Parser

Parses DATA DIVISION from line inventory and builds semantic data model.
Works with ANY COBOL file - not hardcoded to specific files.

Input: Line inventory JSON (from cobol_parse_export.py)
Output: Data model JSON with:
  - Fields (77-level standalone, group members)
  - Groups (01-level structures with children)
  - Conditions (88-level)
  - Arrays (OCCURS)
  - Redefines relationships

Date: December 2025
"""

import json
import re
from pathlib import Path
from typing import Optional
from datetime import datetime


class PicClauseParser:
    """Parse COBOL PIC clauses and determine Java types."""

    @staticmethod
    def parse(pic_clause: str, comp_type: Optional[str] = None) -> dict:
        """
        Parse a PIC clause and return type information.

        Args:
            pic_clause: The PIC clause (e.g., "X(10)", "S9(5)V99", "9(7)")
            comp_type: Optional COMP type (COMP, COMP-3, etc.)

        Returns:
            Dict with type info: java_type, size, decimal_places, signed, etc.
        """
        if not pic_clause:
            return {'java_type': 'Object', 'size': 0, 'decimal_places': 0, 'category': 'unknown'}

        pic = pic_clause.upper().strip()

        # Remove PIC/PICTURE keyword if present
        pic = re.sub(r'^(PIC|PICTURE)\s+', '', pic)

        result = {
            'pic': pic_clause,
            'size': 0,
            'decimal_places': 0,
            'signed': False,
            'category': 'unknown',
            'java_type': 'String',
            'comp': comp_type
        }

        # Check for signed
        if pic.startswith('S'):
            result['signed'] = True
            pic = pic[1:]

        # Character types (X, A)
        if pic.startswith('X') or pic.startswith('A'):
            result['category'] = 'alphanumeric'
            size = PicClauseParser._extract_size(pic)
            result['size'] = size
            result['decimal_places'] = 0
            result['java_type'] = 'String'
            return result

        # Numeric types
        if '9' in pic:
            result['category'] = 'numeric'

            # Check for decimal (V)
            if 'V' in pic:
                parts = pic.split('V')
                integer_part = parts[0]
                decimal_part = parts[1] if len(parts) > 1 else ''

                int_size = PicClauseParser._count_digits(integer_part)
                dec_size = PicClauseParser._count_digits(decimal_part)

                result['size'] = int_size + dec_size
                result['decimal_places'] = dec_size
                result['java_type'] = 'BigDecimal'
            else:
                size = PicClauseParser._count_digits(pic)
                result['size'] = size

                # Determine integer type based on size
                # IBM: PIC S9(n) COMP-5 maps based on digit count
                if comp_type in ('COMP', 'COMP-4', 'COMP-5', 'BINARY'):
                    if size <= 4:
                        result['java_type'] = 'short'
                    elif size <= 9:
                        result['java_type'] = 'int'
                    else:
                        result['java_type'] = 'long'
                elif comp_type == 'COMP-3':
                    result['java_type'] = 'BigDecimal'
                elif comp_type == 'COMP-1':
                    result['java_type'] = 'float'
                elif comp_type == 'COMP-2':
                    result['java_type'] = 'double'
                else:
                    # Display numeric (zoned decimal) - IBM spec says BigDecimal
                    # Per IBM COBOL z/OS: "DISPLAY numeric (zoned) -> java.math.BigDecimal"
                    result['java_type'] = 'BigDecimal'

            # Override for COMP-3 with decimals
            if comp_type == 'COMP-3':
                result['java_type'] = 'BigDecimal'

            return result

        return result

    @staticmethod
    def _extract_size(pic: str) -> int:
        """Extract size from PIC clause like X(10) or XXX."""
        # Check for (n) notation
        match = re.search(r'\((\d+)\)', pic)
        if match:
            return int(match.group(1))
        # Count repeated characters
        return len(re.sub(r'[^X9A]', '', pic))

    @staticmethod
    def _count_digits(pic_part: str) -> int:
        """Count digits in a PIC part like 9(5) or 999."""
        # Check for (n) notation
        match = re.search(r'9\((\d+)\)', pic_part)
        if match:
            return int(match.group(1))
        # Count 9s
        return pic_part.count('9')


class DataDivisionParser:
    """Parse DATA DIVISION and build semantic model."""

    def __init__(self, line_inventory: dict):
        """
        Initialize parser with line inventory.

        Args:
            line_inventory: Dict from line inventory JSON
        """
        self.lines = line_inventory.get('lines', [])
        self.source_file = line_inventory.get('source_file', 'unknown')
        self.data_model = {
            'source_file': self.source_file,
            'generated': datetime.now().isoformat(),
            'fields': [],
            'groups': [],
            'conditions': [],
            'summary': {}
        }

    def find_data_division_bounds(self) -> tuple:
        """
        Find start and end line numbers of DATA DIVISION.
        Works dynamically - not hardcoded.

        Returns:
            Tuple of (start_line, end_line)
        """
        start_line = None
        end_line = None

        for line in self.lines:
            text = line['raw_text'].upper()
            line_num = line['line_num']

            # Find DATA DIVISION start
            if 'DATA DIVISION' in text and start_line is None:
                start_line = line_num

            # Find PROCEDURE DIVISION (marks end of DATA DIVISION)
            if 'PROCEDURE DIVISION' in text and start_line is not None:
                end_line = line_num - 1
                break

        # If no PROCEDURE DIVISION found, go to end of file
        if start_line and not end_line:
            end_line = self.lines[-1]['line_num']

        return (start_line, end_line)

    def parse_data_line(self, line: dict) -> Optional[dict]:
        """
        Parse a single DATA DIVISION line.

        Args:
            line: Line dict from inventory

        Returns:
            Parsed field dict or None
        """
        text = line['raw_text']
        line_num = line['line_num']

        # Skip comments and blanks
        if len(text) > 6 and text[6] in ('*', '/'):
            return None

        content = text[6:72].strip() if len(text) > 6 else text.strip()
        if not content:
            return None

        # Check for level number
        level_match = re.match(r'^(\d{2})\s+', content)
        if not level_match:
            return None

        level = level_match.group(1)
        rest = content[level_match.end():].strip()

        # Parse field name
        name_match = re.match(r'^([A-Z0-9][-A-Z0-9]*)', rest, re.IGNORECASE)
        if not name_match:
            # Could be FILLER
            if rest.upper().startswith('FILLER'):
                name = 'FILLER'
                rest = rest[6:].strip()
            else:
                return None
        else:
            name = name_match.group(1)
            rest = rest[name_match.end():].strip()

        # Initialize field dict
        field = {
            'line_num': line_num,
            'level': level,
            'name': name,
            'raw_text': text.rstrip(),
            'pic': None,
            'java_type': None,
            'java_name': self._cobol_to_java_name(name),
            'size': 0,
            'decimal_places': 0,
            'value': None,
            'comp': None,
            'occurs': None,
            'redefines': None,
            'is_filler': name == 'FILLER',
            'is_group': False
        }

        # Parse PIC clause
        pic_match = re.search(r'PIC(?:TURE)?\s+([^\s.]+)', rest, re.IGNORECASE)
        if pic_match:
            field['pic'] = pic_match.group(1)

        # Parse COMP type
        comp_match = re.search(r'(COMP-[0-9]|COMP|BINARY|PACKED-DECIMAL)', rest, re.IGNORECASE)
        if comp_match:
            comp = comp_match.group(1).upper()
            if comp == 'PACKED-DECIMAL':
                comp = 'COMP-3'
            field['comp'] = comp

        # Parse VALUE clause
        value_match = re.search(r'VALUE\s+(.+?)(?:\.|$)', rest, re.IGNORECASE)
        if value_match:
            value = value_match.group(1).strip()
            # Handle different value types
            if value.upper() in ('SPACES', 'SPACE'):
                field['value'] = ' '
            elif value.upper() in ('ZEROS', 'ZEROES', 'ZERO'):
                field['value'] = 0
            elif value.upper() in ('LOW-VALUES', 'LOW-VALUE'):
                field['value'] = '\\u0000'
            elif value.upper() in ('HIGH-VALUES', 'HIGH-VALUE'):
                field['value'] = '\\uFFFF'
            elif value.startswith('"') or value.startswith("'"):
                field['value'] = value.strip('"\'')
            else:
                try:
                    field['value'] = int(value) if '.' not in value else float(value)
                except ValueError:
                    field['value'] = value

        # Parse OCCURS clause
        occurs_match = re.search(r'OCCURS\s+(\d+)\s+TIMES?', rest, re.IGNORECASE)
        if occurs_match:
            field['occurs'] = int(occurs_match.group(1))

        # Parse REDEFINES clause
        redefines_match = re.search(r'REDEFINES\s+([A-Z0-9][-A-Z0-9]*)', rest, re.IGNORECASE)
        if redefines_match:
            field['redefines'] = redefines_match.group(1)

        # Determine if group (no PIC clause, level 01-49)
        if field['pic'] is None and level in ('01', '02', '03', '04', '05', '10', '15', '20', '25', '30', '49'):
            field['is_group'] = True
            field['java_type'] = 'class'  # Will be inner class or record
        elif field['pic'] is not None:
            # Parse PIC clause for type
            pic_info = PicClauseParser.parse(field['pic'], field['comp'])
            field['java_type'] = pic_info['java_type']
            field['size'] = pic_info['size']
            field['decimal_places'] = pic_info.get('decimal_places', 0)
        # else: No PIC and not a standard group level - keep defaults

        return field

    def parse_88_level(self, line: dict, parent_name: str) -> Optional[dict]:
        """
        Parse an 88-level condition.

        Args:
            line: Line dict from inventory
            parent_name: Name of parent field

        Returns:
            Condition dict or None
        """
        text = line['raw_text']
        content = text[6:72].strip() if len(text) > 6 else text.strip()

        if not content.startswith('88'):
            return None

        rest = content[2:].strip()

        # Parse condition name
        name_match = re.match(r'^([A-Z0-9][-A-Z0-9]*)', rest, re.IGNORECASE)
        if not name_match:
            return None

        name = name_match.group(1)
        rest = rest[name_match.end():].strip()

        # Parse VALUE(S)
        values = []
        value_match = re.search(r'VALUES?\s+(.+?)(?:\.|$)', rest, re.IGNORECASE)
        if value_match:
            value_str = value_match.group(1)
            # Handle THRU ranges and multiple values
            if 'THRU' in value_str.upper() or 'THROUGH' in value_str.upper():
                # Range value
                values = [value_str.strip()]
            else:
                # Split by spaces or commas for multiple values
                for v in re.split(r'[\s,]+', value_str):
                    v = v.strip().strip('"\'')
                    if v:
                        values.append(v)

        return {
            'line_num': line['line_num'],
            'level': '88',
            'name': name,
            'java_name': self._cobol_to_java_name(name),
            'parent': parent_name,
            'values': values,
            'raw_text': text.rstrip()
        }

    def _cobol_to_java_name(self, cobol_name: str) -> str:
        """Convert COBOL name to Java identifier."""
        if not cobol_name or cobol_name == 'FILLER':
            return 'filler'

        # Handle names starting with numbers
        if cobol_name[0].isdigit():
            cobol_name = 'n' + cobol_name

        # Convert to camelCase
        parts = cobol_name.lower().split('-')
        return parts[0] + ''.join(p.capitalize() for p in parts[1:])

    def build_model(self) -> dict:
        """
        Build complete semantic data model.

        Returns:
            Data model dict
        """
        start, end = self.find_data_division_bounds()

        if not start:
            return self.data_model

        # Filter to DATA DIVISION lines
        data_lines = [l for l in self.lines if start <= l['line_num'] <= end]

        current_parent = None
        current_01_group = None

        for line in data_lines:
            text = line['raw_text']
            content = text[6:72].strip() if len(text) > 6 else text.strip()

            if not content:
                continue

            # Check level number
            level_match = re.match(r'^(\d{2})\s+', content)
            if not level_match:
                continue

            level = level_match.group(1)

            # Handle 88-level conditions
            if level == '88':
                if current_parent:
                    condition = self.parse_88_level(line, current_parent)
                    if condition:
                        self.data_model['conditions'].append(condition)
                continue

            # Parse regular field/group
            field = self.parse_data_line(line)
            if not field:
                continue

            # Track current parent for 88 levels
            if not field['is_filler']:
                current_parent = field['name']

            # Handle 01-level groups
            if level == '01':
                if field['is_group']:
                    current_01_group = {
                        'line_num': field['line_num'],
                        'name': field['name'],
                        'java_name': self._cobol_to_java_name(field['name']),
                        'raw_text': field['raw_text'],
                        'children': [],
                        'redefines': field['redefines']
                    }
                    self.data_model['groups'].append(current_01_group)
                else:
                    # 01-level with PIC clause (standalone)
                    self.data_model['fields'].append(field)
                    current_01_group = None

            # Handle 77-level (always standalone)
            elif level == '77':
                self.data_model['fields'].append(field)

            # Handle subordinate levels (02-49)
            elif level in ('02', '03', '04', '05', '10', '15', '20', '25', '30', '49'):
                if current_01_group:
                    current_01_group['children'].append(field)
                else:
                    # Orphan field - add to fields
                    self.data_model['fields'].append(field)

        # Build summary
        self.data_model['summary'] = {
            'data_division_start': start,
            'data_division_end': end,
            'total_lines': end - start + 1 if start and end else 0,
            'standalone_fields': len(self.data_model['fields']),
            'groups': len(self.data_model['groups']),
            'group_children': sum(len(g['children']) for g in self.data_model['groups']),
            'conditions': len(self.data_model['conditions']),
            'total_data_items': (
                len(self.data_model['fields']) +
                sum(len(g['children']) for g in self.data_model['groups'])
            )
        }

        return self.data_model


def parse_data_division(line_inventory_path: Path, output_path: Path) -> dict:
    """
    Parse DATA DIVISION and output semantic model.

    Args:
        line_inventory_path: Path to line inventory JSON
        output_path: Path for output data model JSON

    Returns:
        Result dict with summary
    """
    with open(line_inventory_path) as f:
        inventory = json.load(f)

    parser = DataDivisionParser(inventory)
    model = parser.build_model()

    with open(output_path, 'w') as f:
        json.dump(model, f, indent=2, ensure_ascii=False)

    return {
        'output_path': str(output_path),
        'summary': model['summary']
    }


if __name__ == '__main__':
    import sys

    # Default paths (can be overridden by command line)
    inventory_path = Path("reports/ifpr321_line_inventory.json")
    output_path = Path("reports/ifpr321_data_model.json")

    if len(sys.argv) >= 3:
        inventory_path = Path(sys.argv[1])
        output_path = Path(sys.argv[2])

    if not inventory_path.exists():
        print(f"ERROR: {inventory_path} not found")
        print("Run main.py first to generate line inventory")
        sys.exit(1)

    print("=" * 60)
    print("COBOL Data Division Parser")
    print("=" * 60)
    print(f"\nInput:  {inventory_path}")
    print(f"Output: {output_path}")

    result = parse_data_division(inventory_path, output_path)

    print(f"\n=== DATA MODEL SUMMARY ===")
    for key, value in result['summary'].items():
        print(f"  {key}: {value}")

    print(f"\nOutput written to: {output_path}")
    print("=" * 60)
