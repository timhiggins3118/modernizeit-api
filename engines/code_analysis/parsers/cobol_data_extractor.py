#!/usr/bin/env python3
"""
COBOL Data Extractor

Reads line_inventory.json and extracts ALL data items with full hierarchy.
Maps to Java types per IBM ODM 9.5.0 rules.

Input:  ifpr321_line_inventory.json (10,646 lines, zero-loss)
Output: ifpr321_complete_data_model.json (717 data items with hierarchy)
"""

import json
import re
from typing import Dict, List, Any, Optional
from pathlib import Path


def parse_level(raw_text: str) -> Optional[int]:
    """Extract level number from raw COBOL line."""
    # Skip comments
    if raw_text.strip().startswith('*'):
        return None

    # Match level number at start: "       01  NAME" or "      77  NAME"
    match = re.match(r'^\s*(\d{2})\s+', raw_text)
    if match:
        return int(match.group(1))
    return None


def parse_name(raw_text: str) -> str:
    """Extract field/group name from raw COBOL line."""
    # Pattern: level  NAME  PIC/OCCURS/REDEFINES/VALUE/.
    match = re.match(r'^\s*\d{2}\s+([A-Z0-9][-A-Z0-9]*)', raw_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return "FILLER"


def parse_pic(raw_text: str) -> Optional[str]:
    """Extract PIC clause from raw COBOL line."""
    # Pattern: PIC X(10) or PIC S9(7)V99 or PIC 9 etc.
    match = re.search(r'PIC\s+([^\s.]+(?:\([^)]+\))?[^\s.]*)', raw_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def parse_occurs(raw_text: str) -> Dict[str, Any]:
    """Extract OCCURS clause from raw COBOL line."""
    result = {'occurs': None, 'depending_on': None}

    # Pattern: OCCURS n TIMES
    match = re.search(r'OCCURS\s+(\d+)\s+TIMES?', raw_text, re.IGNORECASE)
    if match:
        result['occurs'] = int(match.group(1))

    # Pattern: DEPENDING ON field-name
    dep_match = re.search(r'DEPENDING\s+ON\s+([A-Z0-9][-A-Z0-9]*)', raw_text, re.IGNORECASE)
    if dep_match:
        result['depending_on'] = dep_match.group(1).upper()

    return result


def parse_redefines(raw_text: str) -> Optional[str]:
    """Extract REDEFINES clause from raw COBOL line."""
    match = re.search(r'REDEFINES\s+([A-Z0-9][-A-Z0-9]*)', raw_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def parse_comp(raw_text: str) -> Optional[str]:
    """Extract COMP/USAGE clause from raw COBOL line."""
    # Match COMP, COMP-1, COMP-2, COMP-3, COMP-4, COMP-5, BINARY, PACKED-DECIMAL
    match = re.search(r'(COMP-[1-5]|COMP|BINARY|PACKED-DECIMAL)', raw_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    # Also check for USAGE clause
    match = re.search(r'USAGE\s+(COMP-[1-5]|COMP|BINARY|PACKED-DECIMAL|DISPLAY)', raw_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def parse_value(raw_text: str) -> Optional[str]:
    """Extract VALUE clause from raw COBOL line."""
    # VALUE "string" or VALUE 'string' or VALUE SPACES/ZEROS/etc.
    match = re.search(r'VALUE\s+["\']([^"\']*)["\']', raw_text, re.IGNORECASE)
    if match:
        return match.group(1)

    # VALUE keyword (SPACES, ZEROS, etc.)
    match = re.search(r'VALUE\s+(SPACES?|ZEROS?|ZEROES?|LOW-VALUES?|HIGH-VALUES?)', raw_text, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    return None


def parse_88_values(raw_text: str) -> List[str]:
    """Extract VALUES from 88-level condition."""
    values = []

    # VALUE "X" or VALUES "X" "Y" or VALUE "X" THRU "Z"
    # Simple pattern for quoted values
    for match in re.finditer(r'["\']([^"\']+)["\']', raw_text):
        values.append(match.group(1))

    return values


def cobol_to_java_name(cobol_name: str) -> str:
    """Convert COBOL-NAME to javaName (camelCase)."""
    if not cobol_name or cobol_name == "FILLER":
        return "filler"

    # Remove leading digits
    name = re.sub(r'^\d+-', '', cobol_name)

    # Split on hyphens
    parts = name.lower().split('-')

    # camelCase: first word lowercase, rest Title case
    if len(parts) == 1:
        return parts[0]

    return parts[0] + ''.join(p.title() for p in parts[1:])


def cobol_to_java_class_name(cobol_name: str) -> str:
    """Convert COBOL-NAME to JavaClassName (PascalCase)."""
    if not cobol_name:
        return "Unknown"

    name = re.sub(r'^\d+-', '', cobol_name)
    parts = name.lower().split('-')
    return ''.join(p.capitalize() for p in parts)


def get_java_type(pic: Optional[str], occurs: Dict[str, Any], level: int, comp_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Determine Java type from COBOL PIC clause.
    Per IBM COBOL z/OS 6.4.0 mapping rules.

    IBM Mapping:
    - PIC X(m) -> String
    - PIC S9(n) COMP-5 (1-4 digits) -> short
    - PIC S9(n) COMP-5 (5-9 digits) -> int
    - PIC S9(n) COMP-5 (10-18 digits) -> long
    - COMP-1 -> float
    - COMP-2 -> double
    - COMP-3/PACKED-DECIMAL -> BigDecimal
    - DISPLAY numeric (zoned) -> BigDecimal
    """
    result = {
        'java_type': 'Object',
        'java_import': None,
        'is_array': False,
        'is_list': False,
        'base_type': 'Object'
    }

    # Level 88 = boolean accessor
    if level == 88:
        result['java_type'] = 'boolean'
        result['base_type'] = 'boolean'
        return result

    # No PIC = group item (becomes class)
    if not pic:
        result['java_type'] = 'class'
        result['base_type'] = 'class'
        return result

    pic = pic.upper()

    # Determine base type first
    base_type = 'Object'
    java_import = None

    # Has decimal (V or P) -> BigDecimal always
    if 'V' in pic or 'P' in pic:
        base_type = 'BigDecimal'
        java_import = 'java.math.BigDecimal'

    # Alphanumeric: X(n) or just X
    elif 'X' in pic:
        base_type = 'String'

    # Alphabetic: A(n)
    elif re.match(r'^A', pic):
        base_type = 'String'

    # Edited numeric (Z, $, *, etc.) -> String
    elif any(c in pic for c in ['Z', '$', '*', ',']):
        base_type = 'String'

    # Numeric: 9(n) - type depends on COMP
    elif '9' in pic:
        # Count digits
        digit_match = re.search(r'9\((\d+)\)', pic)
        if digit_match:
            digits = int(digit_match.group(1))
        else:
            digits = pic.count('9')

        # IBM COMP-5 / COMP / COMP-4 / BINARY -> binary integer types
        if comp_type in ('COMP', 'COMP-4', 'COMP-5', 'BINARY'):
            if digits <= 4:
                base_type = 'short'
            elif digits <= 9:
                base_type = 'int'
            elif digits <= 18:
                base_type = 'long'
            else:
                base_type = 'BigInteger'
                java_import = 'java.math.BigInteger'
        # COMP-1 -> float
        elif comp_type == 'COMP-1':
            base_type = 'float'
        # COMP-2 -> double
        elif comp_type == 'COMP-2':
            base_type = 'double'
        # COMP-3 / PACKED-DECIMAL -> BigDecimal
        elif comp_type in ('COMP-3', 'PACKED-DECIMAL'):
            base_type = 'BigDecimal'
            java_import = 'java.math.BigDecimal'
        # DISPLAY (no COMP) -> BigDecimal per IBM spec
        else:
            base_type = 'BigDecimal'
            java_import = 'java.math.BigDecimal'

    result['base_type'] = base_type
    result['java_import'] = java_import

    # Handle OCCURS
    if occurs.get('occurs'):
        result['is_array'] = True
        if occurs.get('depending_on'):
            # Variable length -> List<Type>
            result['is_list'] = True
            result['java_type'] = f"List<{base_type}>"
            result['java_import'] = 'java.util.List'
        else:
            # Fixed length -> Type[]
            result['java_type'] = f"{base_type}[]"
    else:
        result['java_type'] = base_type

    return result


def extract_data_items(line_inventory_path: Path) -> Dict[str, Any]:
    """
    Extract ALL data items from line inventory with full hierarchy.
    """
    with open(line_inventory_path) as f:
        lines = json.load(f)['lines']

    data_items = []
    groups = []
    conditions = []
    imports_needed = set()

    # Stack for tracking hierarchy - includes OCCURS info for inheritance
    # Format: [(level, name, index, occurs_count), ...]
    # occurs_count: None or int - inherited down to children
    parent_stack = []

    stats = {
        'total_lines': len(lines),
        'data_lines': 0,
        'by_level': {},
        'with_occurs': 0,
        'with_depending_on': 0,
        'with_redefines': 0,
        'by_java_type': {}
    }

    for line in lines:
        raw_text = line.get('raw_text', '')
        line_num = line.get('line_num', 0)

        level = parse_level(raw_text)
        if level is None:
            continue

        stats['data_lines'] += 1
        stats['by_level'][level] = stats['by_level'].get(level, 0) + 1

        name = parse_name(raw_text)
        pic = parse_pic(raw_text)
        comp_type = parse_comp(raw_text)  # COMP, COMP-3, etc.
        occurs_info = parse_occurs(raw_text)
        redefines = parse_redefines(raw_text)
        value = parse_value(raw_text)

        # Get Java type using IBM COBOL z/OS mapping rules
        java_info = get_java_type(pic, occurs_info, level, comp_type)

        if java_info.get('java_import'):
            imports_needed.add(java_info['java_import'])

        # Track stats
        if occurs_info.get('occurs'):
            stats['with_occurs'] += 1
        if occurs_info.get('depending_on'):
            stats['with_depending_on'] += 1
        if redefines:
            stats['with_redefines'] += 1

        base_type = java_info['base_type']
        stats['by_java_type'][base_type] = stats['by_java_type'].get(base_type, 0) + 1

        # Level 77 is standalone - no parent hierarchy
        # Level 88 conditions belong to the previous non-88 field
        inherited_occurs = None
        if level == 77:
            parent_name = None
        elif level == 88:
            # Level 88 belongs to the last field on the stack (its parent field)
            parent_name = parent_stack[-1][1] if parent_stack else None
        else:
            # Update parent stack (pop items with level >= current)
            while parent_stack and parent_stack[-1][0] >= level:
                parent_stack.pop()

            # Determine parent and check for inherited OCCURS
            if parent_stack:
                parent_name = parent_stack[-1][1]
                # Inherit OCCURS from any ancestor in the stack
                for parent_item in parent_stack:
                    if parent_item[3]:  # parent has OCCURS
                        inherited_occurs = parent_item[3]
                        break  # Use the closest ancestor with OCCURS
            else:
                parent_name = None

        # If this item has its own OCCURS, use that; otherwise check inherited
        effective_occurs = occurs_info.get('occurs') or inherited_occurs

        # Recalculate java_type with inherited OCCURS
        if effective_occurs and not occurs_info.get('occurs'):
            # Has inherited OCCURS - make it an array
            base_type = java_info['base_type']
            java_type = f"{base_type}[]"
            is_array = True
            is_list = False
        else:
            java_type = java_info['java_type']
            is_array = java_info['is_array']
            is_list = java_info['is_list']

        # Build item
        item = {
            'line_num': line_num,
            'level': level,
            'cobol_name': name,
            'java_name': cobol_to_java_name(name),
            'raw_text': raw_text.strip(),
            'pic': pic,
            'occurs': occurs_info.get('occurs'),
            'inherited_occurs': inherited_occurs,  # Track where OCCURS came from
            'depending_on': occurs_info.get('depending_on'),
            'redefines': redefines,
            'value': value,
            'parent': parent_name,
            'java_type': java_type,
            'java_base_type': java_info['base_type'],
            'is_array': is_array,
            'is_list': is_list,
            'is_group': pic is None and level != 88,
            'is_filler': name == 'FILLER'
        }

        # Categorize
        if level == 88:
            item['values'] = parse_88_values(raw_text)
            # Build accessor: is + PascalCase name
            java_name = cobol_to_java_name(name)
            item['java_accessor'] = 'is' + java_name[0].upper() + java_name[1:] if name != 'FILLER' else 'isCondition'
            conditions.append(item)
        elif pic is None and level < 77:
            # Group item (no PIC, not 77/88)
            class_name = cobol_to_java_class_name(name)
            item['java_class_name'] = class_name

            # If OCCURS, it's an array of this class type
            if occurs_info.get('occurs'):
                if occurs_info.get('depending_on'):
                    item['java_type'] = f"List<{class_name}>"
                    imports_needed.add('java.util.List')
                else:
                    item['java_type'] = f"{class_name}[]"
            else:
                item['java_type'] = class_name

            groups.append(item)
            # Push to parent stack with OCCURS count for inheritance
            parent_stack.append((level, name, len(groups) - 1, occurs_info.get('occurs')))
        else:
            # Regular data item
            data_items.append(item)
            # Also push to parent stack if it could be a parent (with OCCURS for inheritance)
            if level < 77:
                parent_stack.append((level, name, len(data_items) - 1, occurs_info.get('occurs')))

    return {
        'source': str(line_inventory_path),
        'generated': __import__('datetime').datetime.now().isoformat(),
        'mapping_reference': 'IBM ODM 9.5.0 - COBOL to Java Mapping',
        'imports_needed': sorted(imports_needed),
        'stats': stats,
        'groups': groups,
        'fields': data_items,
        'conditions': conditions
    }


if __name__ == '__main__':
    print("=" * 60)
    print("COBOL Data Extractor (from line_inventory.json)")
    print("=" * 60)

    # Extract from line inventory
    result = extract_data_items(Path('reports/ifpr321_line_inventory.json'))

    # Save output
    output_file = 'reports/ifpr321_complete_data_model.json'
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    stats = result['stats']

    print(f"\n{'='*40}")
    print("EXTRACTION SUMMARY")
    print(f"{'='*40}")
    print(f"Total lines scanned:     {stats['total_lines']}")
    print(f"Data lines found:        {stats['data_lines']}")
    print(f"{'─'*40}")
    print(f"Groups (→ Java class):   {len(result['groups'])}")
    print(f"Fields (→ Java attr):    {len(result['fields'])}")
    print(f"Conditions (→ boolean):  {len(result['conditions'])}")
    print(f"{'─'*40}")
    print(f"With OCCURS:             {stats['with_occurs']}")
    print(f"With DEPENDING ON:       {stats['with_depending_on']}")
    print(f"With REDEFINES:          {stats['with_redefines']}")

    print(f"\n{'='*40}")
    print("BY LEVEL")
    print(f"{'='*40}")
    for lvl, count in sorted(stats['by_level'].items()):
        print(f"  Level {lvl:02d}: {count}")

    print(f"\n{'='*40}")
    print("BY JAVA TYPE")
    print(f"{'='*40}")
    for jtype, count in sorted(stats['by_java_type'].items(), key=lambda x: -x[1]):
        print(f"  {jtype}: {count}")

    print(f"\n{'='*40}")
    print("IMPORTS NEEDED")
    print(f"{'='*40}")
    for imp in result['imports_needed']:
        print(f"  import {imp};")

    print(f"\nOutput saved to: {output_file}")

    # Show samples
    print("\n" + "=" * 60)
    print("SAMPLE GROUPS")
    print("=" * 60)
    for g in result['groups'][:5]:
        print(f"  class {g['java_class_name']:25} // Level {g['level']:02d} {g['cobol_name']}")

    print("\n" + "=" * 60)
    print("SAMPLE FIELDS WITH OCCURS")
    print("=" * 60)
    occurs_fields = [f for f in result['fields'] if f.get('occurs')]
    for f in occurs_fields[:5]:
        dep = f" DEPENDING ON {f['depending_on']}" if f.get('depending_on') else ""
        print(f"  {f['java_type']:25} {f['java_name']}")
        print(f"      // OCCURS {f['occurs']}{dep}")

    print("\n" + "=" * 60)
    print("SAMPLE CONDITIONS (88-level)")
    print("=" * 60)
    for c in result['conditions'][:5]:
        print(f"  boolean {c['java_accessor']}()")
        print(f"      // VALUES: {c.get('values', [])}")
