#!/usr/bin/env python3
"""
Comprehensive COBOL Parser

Parses EVERYTHING in the uploaded ZIP:
- All COBOL programs (.CBL, .COB)
- All copybooks
- Resolves COPY statements
- Builds unified data model
- Creates cross-reference

This is the REAL parser - not just one file.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

from engines.code_analysis.parsers.cobol_parser_adapter import parse_cobol_file


class ComprehensiveParser:
    """Parse entire COBOL codebase from ZIP."""

    def __init__(self, work_dir: Path):
        self.work_dir = Path(work_dir)
        self.programs: Dict[str, Dict] = {}  # Main COBOL programs
        self.copybooks: Dict[str, Dict] = {}  # Copybook files
        self.copy_statements: Dict[str, List[Dict]] = {}  # COPY statements per file
        self.data_items: Dict[str, List[Dict]] = {}  # Data items per file
        self.all_data_items: List[Dict] = []  # Unified data model
        self.cross_ref: Dict[str, Dict] = {}  # Cross-reference
        self.errors: List[str] = []

    def scan_files(self) -> Dict[str, List[Path]]:
        """Find all COBOL files in the work directory."""
        extensions = ['.CBL', '.cbl', '.COB', '.cob', '.CPY', '.cpy']

        all_files = []
        for ext in extensions:
            all_files.extend(self.work_dir.rglob(f'*{ext}'))

        # Categorize files
        programs = []
        copybooks = []

        for f in all_files:
            # Heuristic: copybooks are usually in folders named "copy*" or have certain patterns
            path_lower = str(f).lower()
            if 'copy' in path_lower or 'cpy' in f.suffix.lower():
                copybooks.append(f)
            else:
                # Check if it looks like a copybook (no PROCEDURE DIVISION)
                try:
                    content = f.read_text(encoding='latin-1', errors='replace')
                    if 'PROCEDURE DIVISION' in content.upper():
                        programs.append(f)
                    else:
                        copybooks.append(f)
                except:
                    programs.append(f)  # Default to program if can't read

        return {
            'programs': sorted(programs),
            'copybooks': sorted(copybooks)
        }

    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse a single COBOL file and extract all information."""
        try:
            # Read file content
            content = file_path.read_text(encoding='latin-1', errors='replace')
            lines = content.splitlines()

            result = {
                'file_path': str(file_path),
                'file_name': file_path.name,
                'line_count': len(lines),
                'copy_statements': [],
                'data_items': [],
                'paragraphs': [],
                'calls': [],
                'file_operations': [],
                'parsed_ok': True
            }

            # Extract COPY statements
            result['copy_statements'] = self._extract_copy_statements(lines)

            # Extract data items (levels 01-88)
            result['data_items'] = self._extract_data_items(lines)

            # Extract paragraphs (for programs)
            result['paragraphs'] = self._extract_paragraphs(lines)

            # Extract CALL statements
            result['calls'] = self._extract_calls(lines)

            # Extract file operations
            result['file_operations'] = self._extract_file_ops(lines)

            return result

        except Exception as e:
            self.errors.append(f"Error parsing {file_path}: {e}")
            return {
                'file_path': str(file_path),
                'file_name': file_path.name,
                'parsed_ok': False,
                'error': str(e)
            }

    def _extract_copy_statements(self, lines: List[str]) -> List[Dict]:
        """Extract all COPY statements from source."""
        copies = []
        for i, line in enumerate(lines, 1):
            # Skip comments
            if len(line) > 6 and line[6] == '*':
                continue

            # Look for COPY statement
            match = re.search(r'\bCOPY\s+([A-Z0-9_-]+)(?:\s+OF\s+([A-Z0-9_-]+))?',
                            line.upper())
            if match:
                copies.append({
                    'line_num': i,
                    'copybook': match.group(1),
                    'of_file': match.group(2),
                    'raw_text': line.strip()
                })
        return copies

    def _extract_data_items(self, lines: List[str]) -> List[Dict]:
        """Extract all data items (01-88 levels)."""
        items = []
        in_data_division = False

        for i, line in enumerate(lines, 1):
            upper_line = line.upper()

            # Track if we're in DATA DIVISION
            if 'DATA DIVISION' in upper_line:
                in_data_division = True
                continue
            if 'PROCEDURE DIVISION' in upper_line:
                in_data_division = False
                continue

            # Skip comments
            if len(line) > 6 and line[6] == '*':
                continue

            # Look for level numbers
            match = re.match(r'^\s*(\d{2})\s+([A-Z0-9][-A-Z0-9]*)', line, re.IGNORECASE)
            if match:
                level = int(match.group(1))
                name = match.group(2).upper()

                # Extract PIC clause
                pic_match = re.search(r'PIC\s+([^\s.]+(?:\([^)]+\))?[^\s.]*)',
                                     line, re.IGNORECASE)
                pic = pic_match.group(1).upper() if pic_match else None

                # Extract OCCURS
                occurs_match = re.search(r'OCCURS\s+(\d+)', line, re.IGNORECASE)
                occurs = int(occurs_match.group(1)) if occurs_match else None

                # Extract REDEFINES
                redef_match = re.search(r'REDEFINES\s+([A-Z0-9][-A-Z0-9]*)',
                                       line, re.IGNORECASE)
                redefines = redef_match.group(1).upper() if redef_match else None

                # Extract VALUE
                value_match = re.search(r'VALUE\s+["\']([^"\']*)["\']', line, re.IGNORECASE)
                if not value_match:
                    value_match = re.search(r'VALUE\s+(SPACES?|ZEROS?|ZEROES?)',
                                           line, re.IGNORECASE)
                value = value_match.group(1) if value_match else None

                items.append({
                    'line_num': i,
                    'level': level,
                    'name': name,
                    'pic': pic,
                    'occurs': occurs,
                    'redefines': redefines,
                    'value': value,
                    'raw_text': line.strip(),
                    'is_group': pic is None and level not in [66, 77, 88],
                    'is_condition': level == 88
                })

        return items

    def _extract_paragraphs(self, lines: List[str]) -> List[Dict]:
        """Extract paragraph/section names."""
        paragraphs = []
        in_procedure = False

        for i, line in enumerate(lines, 1):
            upper_line = line.upper()

            if 'PROCEDURE DIVISION' in upper_line:
                in_procedure = True
                continue

            if not in_procedure:
                continue

            # Skip comments
            if len(line) > 6 and line[6] == '*':
                continue

            # Look for paragraph headers (name followed by period or SECTION)
            # Paragraph: starts in column 8, ends with period
            match = re.match(r'^.{7}([A-Z0-9][-A-Z0-9]*)\s*\.\s*$', line, re.IGNORECASE)
            if match:
                paragraphs.append({
                    'line_num': i,
                    'name': match.group(1).upper(),
                    'type': 'paragraph'
                })
            else:
                # Check for SECTION
                sec_match = re.search(r'([A-Z0-9][-A-Z0-9]*)\s+SECTION\s*\.',
                                     line, re.IGNORECASE)
                if sec_match:
                    paragraphs.append({
                        'line_num': i,
                        'name': sec_match.group(1).upper(),
                        'type': 'section'
                    })

        return paragraphs

    def _extract_calls(self, lines: List[str]) -> List[Dict]:
        """Extract CALL statements."""
        calls = []
        for i, line in enumerate(lines, 1):
            # Skip comments
            if len(line) > 6 and line[6] == '*':
                continue

            # Look for CALL statement
            match = re.search(r'\bCALL\s+["\']?([A-Z0-9_-]+)["\']?', line, re.IGNORECASE)
            if match:
                calls.append({
                    'line_num': i,
                    'target': match.group(1).upper(),
                    'raw_text': line.strip()
                })
        return calls

    def _extract_file_ops(self, lines: List[str]) -> List[Dict]:
        """Extract file operations (OPEN, READ, WRITE, CLOSE)."""
        ops = []
        for i, line in enumerate(lines, 1):
            # Skip comments
            if len(line) > 6 and line[6] == '*':
                continue

            upper_line = line.upper()

            for op in ['OPEN', 'READ', 'WRITE', 'CLOSE']:
                if f' {op} ' in upper_line or upper_line.strip().startswith(op):
                    ops.append({
                        'line_num': i,
                        'operation': op,
                        'raw_text': line.strip()
                    })
                    break
        return ops

    def resolve_copybooks(self) -> None:
        """Link COPY statements to their copybook files."""
        # Build copybook lookup by name (without extension)
        copybook_lookup = {}
        for name, data in self.copybooks.items():
            base_name = Path(name).stem.upper()
            copybook_lookup[base_name] = data

        # Resolve each COPY statement
        for prog_name, prog_data in self.programs.items():
            for copy_stmt in prog_data.get('copy_statements', []):
                copybook_name = copy_stmt['copybook']

                # Try to find matching copybook
                if copybook_name in copybook_lookup:
                    copy_stmt['resolved'] = True
                    copy_stmt['copybook_file'] = copybook_lookup[copybook_name]['file_path']
                    copy_stmt['copybook_items'] = len(copybook_lookup[copybook_name].get('data_items', []))
                else:
                    copy_stmt['resolved'] = False
                    copy_stmt['copybook_file'] = None

    def build_unified_model(self) -> Dict[str, Any]:
        """Build unified data model from all sources."""
        all_items = []
        source_map = {}  # Track which file each item comes from

        # Add items from programs
        for prog_name, prog_data in self.programs.items():
            for item in prog_data.get('data_items', []):
                item['source_file'] = prog_name
                item['source_type'] = 'program'
                all_items.append(item)

        # Add items from copybooks
        for copy_name, copy_data in self.copybooks.items():
            for item in copy_data.get('data_items', []):
                item['source_file'] = copy_name
                item['source_type'] = 'copybook'
                all_items.append(item)

        # Build stats
        stats = {
            'total_items': len(all_items),
            'from_programs': sum(1 for i in all_items if i['source_type'] == 'program'),
            'from_copybooks': sum(1 for i in all_items if i['source_type'] == 'copybook'),
            'by_level': {},
            'groups': sum(1 for i in all_items if i.get('is_group')),
            'conditions': sum(1 for i in all_items if i.get('is_condition')),
            'with_occurs': sum(1 for i in all_items if i.get('occurs')),
            'with_redefines': sum(1 for i in all_items if i.get('redefines'))
        }

        for item in all_items:
            level = item['level']
            stats['by_level'][level] = stats['by_level'].get(level, 0) + 1

        self.all_data_items = all_items

        return {
            'generated': datetime.now().isoformat(),
            'stats': stats,
            'items': all_items
        }

    def build_cross_reference(self) -> Dict[str, Any]:
        """Build cross-reference: what uses what."""
        xref = {
            'copybook_usage': {},  # Which programs use which copybooks
            'call_graph': {},  # Which programs call which
            'file_usage': {},  # Which programs use which files
            'data_names': {}  # Where each data name is defined
        }

        # Copybook usage
        for prog_name, prog_data in self.programs.items():
            for copy_stmt in prog_data.get('copy_statements', []):
                copybook = copy_stmt['copybook']
                if copybook not in xref['copybook_usage']:
                    xref['copybook_usage'][copybook] = []
                xref['copybook_usage'][copybook].append(prog_name)

        # Call graph
        for prog_name, prog_data in self.programs.items():
            xref['call_graph'][prog_name] = [
                call['target'] for call in prog_data.get('calls', [])
            ]

        # Data name definitions
        for item in self.all_data_items:
            name = item['name']
            if name not in xref['data_names']:
                xref['data_names'][name] = []
            xref['data_names'][name].append({
                'file': item['source_file'],
                'line': item['line_num'],
                'level': item['level']
            })

        self.cross_ref = xref
        return xref

    def parse_all(self) -> Dict[str, Any]:
        """Main entry point: parse everything."""
        print("=" * 60)
        print("COMPREHENSIVE COBOL PARSER")
        print("=" * 60)

        # Step 1: Scan for files
        print("\n[1/6] Scanning for COBOL files...")
        files = self.scan_files()
        print(f"  Found {len(files['programs'])} programs")
        print(f"  Found {len(files['copybooks'])} copybooks")

        # Step 2: Parse all programs
        print("\n[2/6] Parsing programs...")
        for prog_file in files['programs']:
            print(f"  Parsing {prog_file.name}...")
            result = self.parse_file(prog_file)
            self.programs[prog_file.name] = result
            print(f"    {result.get('line_count', 0)} lines, "
                  f"{len(result.get('data_items', []))} data items, "
                  f"{len(result.get('copy_statements', []))} COPY statements")

        # Step 3: Parse all copybooks
        print("\n[3/6] Parsing copybooks...")
        for copy_file in files['copybooks']:
            result = self.parse_file(copy_file)
            self.copybooks[copy_file.name] = result
        print(f"  Parsed {len(self.copybooks)} copybooks")
        total_copybook_items = sum(
            len(c.get('data_items', [])) for c in self.copybooks.values()
        )
        print(f"  Total data items in copybooks: {total_copybook_items}")

        # Step 4: Resolve COPY statements
        print("\n[4/6] Resolving COPY statements...")
        self.resolve_copybooks()
        resolved = sum(
            1 for p in self.programs.values()
            for c in p.get('copy_statements', [])
            if c.get('resolved')
        )
        total_copies = sum(
            len(p.get('copy_statements', [])) for p in self.programs.values()
        )
        print(f"  Resolved {resolved}/{total_copies} COPY statements")

        # Step 5: Build unified model
        print("\n[5/6] Building unified data model...")
        unified = self.build_unified_model()
        print(f"  Total data items: {unified['stats']['total_items']}")
        print(f"    From programs: {unified['stats']['from_programs']}")
        print(f"    From copybooks: {unified['stats']['from_copybooks']}")
        print(f"    Groups: {unified['stats']['groups']}")
        print(f"    Conditions (88): {unified['stats']['conditions']}")

        # Step 6: Build cross-reference
        print("\n[6/6] Building cross-reference...")
        xref = self.build_cross_reference()
        print(f"  Copybooks referenced: {len(xref['copybook_usage'])}")
        print(f"  External CALLs: {sum(len(v) for v in xref['call_graph'].values())}")
        print(f"  Unique data names: {len(xref['data_names'])}")

        # Summary
        print("\n" + "=" * 60)
        print("PARSING COMPLETE")
        print("=" * 60)

        if self.errors:
            print(f"\nWarnings/Errors: {len(self.errors)}")
            for err in self.errors[:5]:
                print(f"  - {err}")

        return {
            'generated': datetime.now().isoformat(),
            'programs': self.programs,
            'copybooks': self.copybooks,
            'unified_data_model': unified,
            'cross_reference': xref,
            'errors': self.errors,
            'summary': {
                'program_count': len(self.programs),
                'copybook_count': len(self.copybooks),
                'total_files': len(self.programs) + len(self.copybooks),
                'total_data_items': unified['stats']['total_items'],
                'copy_statements_resolved': resolved,
                'copy_statements_total': total_copies
            }
        }


def run_comprehensive_parse(work_dir: Path, output_dir: Path) -> Dict[str, Any]:
    """Run comprehensive parse and save results."""
    parser = ComprehensiveParser(work_dir)
    results = parser.parse_all()

    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save full results
    full_output = output_dir / "comprehensive_parse_results.json"
    with open(full_output, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results saved to: {full_output}")

    # Save unified data model separately
    unified_output = output_dir / "unified_data_model.json"
    with open(unified_output, 'w') as f:
        json.dump(results['unified_data_model'], f, indent=2)
    print(f"Unified data model saved to: {unified_output}")

    # Save cross-reference
    xref_output = output_dir / "cross_reference.json"
    with open(xref_output, 'w') as f:
        json.dump(results['cross_reference'], f, indent=2)
    print(f"Cross-reference saved to: {xref_output}")

    return results


if __name__ == '__main__':
    work_dir = Path("work/cobol_unzipped")
    output_dir = Path("reports")

    if not work_dir.exists():
        print(f"ERROR: {work_dir} not found")
        print("Run main.py first to unzip COBOL files")
        exit(1)

    results = run_comprehensive_parse(work_dir, output_dir)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Programs: {results['summary']['program_count']}")
    print(f"Copybooks: {results['summary']['copybook_count']}")
    print(f"Total data items: {results['summary']['total_data_items']}")
    print(f"COPY statements: {results['summary']['copy_statements_resolved']}/{results['summary']['copy_statements_total']} resolved")
