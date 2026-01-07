"""
Regex Data Extractor for Data Analysis

Extracts COBOL data structures using regex patterns:
- PIC clauses
- FD entries
- Level structures (01-88)
- OCCURS/REDEFINES
- COPY statements
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from engines.data_analysis.utils.type_mapper import map_cobol_to_sql


class RegexDataExtractor:
    """
    Extract data structures from COBOL files using regex patterns.

    This is Branch 1 of the data analysis pipeline - fast pattern matching.
    """

    def __init__(self):
        """Initialize the regex extractor."""
        self.total_fields = 0
        self.total_01_levels = 0
        self.total_copybooks = 0
        self.total_fd_entries = 0

    def extract_from_directory(self, source_path: str) -> Dict[str, Any]:
        """
        Extract data structures from all COBOL files in directory.

        Args:
            source_path: Path to directory containing COBOL files

        Returns:
            Combined data structures from all files
        """
        source_dir = Path(source_path)
        file_results = []

        # Reset counters
        self.total_fields = 0
        self.total_01_levels = 0
        self.total_copybooks = 0
        self.total_fd_entries = 0

        # Find all COBOL files
        cobol_patterns = ['*.cbl', '*.CBL', '*.cob', '*.COB', '*.cobol', '*.COBOL']
        cobol_files = []

        for pattern in cobol_patterns:
            cobol_files.extend(source_dir.rglob(pattern))

        # Also include copybooks
        copybook_patterns = ['*.cpy', '*.CPY', '*.copy', '*.COPY']
        for pattern in copybook_patterns:
            cobol_files.extend(source_dir.rglob(pattern))

        for file_path in cobol_files:
            # Skip junk files
            path_str = str(file_path)
            if '__MACOSX' in path_str or '.DS_Store' in path_str:
                continue
            if file_path.name.startswith('.'):
                continue

            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                relative_path = str(file_path.relative_to(source_dir))

                data_structures = self.extract_from_content(content)

                self.total_fields += data_structures['summary']['total_fields']
                self.total_01_levels += data_structures['summary']['total_01_levels']
                self.total_copybooks += data_structures['summary']['total_copybooks']
                self.total_fd_entries += data_structures['summary']['total_fd_entries']

                file_results.append({
                    'file_path': relative_path,
                    'data_structures': data_structures
                })
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue

        return {
            'summary': {
                'total_files': len(file_results),
                'total_data_items': self.total_fields,
                'total_01_levels': self.total_01_levels,
                'total_copybooks': self.total_copybooks,
                'total_fd_entries': self.total_fd_entries
            },
            'files': file_results
        }

    def extract_from_content(self, content: str) -> Dict[str, Any]:
        """
        Extract data structures from COBOL content.

        Args:
            content: COBOL source code content

        Returns:
            Extracted data structures
        """
        lines = content.split('\n')

        working_storage: List[Dict] = []
        file_section: List[Dict] = []
        linkage_section: List[Dict] = []
        copybooks: List[Dict] = []

        current_section: Optional[str] = None
        current_01_record: Optional[Dict] = None
        current_fd: Optional[Dict] = None

        for line in lines:
            # Strip sequence numbers (columns 1-6) and trailing whitespace
            if len(line) > 6:
                code_line = line[6:].rstrip()
            else:
                code_line = line.rstrip()

            # Skip comments and blank lines
            if not code_line or code_line.startswith('*'):
                continue

            code_upper = code_line.upper()

            # Detect sections
            if 'WORKING-STORAGE SECTION' in code_upper:
                current_section = 'working_storage'
                current_01_record = None
                continue
            elif 'FILE SECTION' in code_upper:
                current_section = 'file_section'
                current_01_record = None
                continue
            elif 'LINKAGE SECTION' in code_upper:
                current_section = 'linkage_section'
                current_01_record = None
                continue
            elif 'PROCEDURE DIVISION' in code_upper:
                current_section = None
                current_01_record = None
                continue

            # Extract COPY statements
            copy_match = re.search(r'\bCOPY\s+(\S+)', code_line, re.IGNORECASE)
            if copy_match:
                copybook_name = copy_match.group(1).strip('.')
                copybooks.append({
                    'copybook_name': copybook_name,
                    'statement': code_line.strip(),
                    'section': current_section
                })

            # Extract FD entries (may appear in copybooks without section header)
            if code_line.strip().upper().startswith('FD '):
                fd_entry = self._extract_fd_entry(code_line)
                if fd_entry:
                    # Auto-detect file_section context for copybooks
                    if current_section is None:
                        current_section = 'file_section'
                    current_fd = fd_entry
                    current_fd['records'] = []
                    file_section.append(current_fd)
                    current_01_record = None
                continue

            # Extract level definitions (01-88)
            level_match = re.match(r'^\s*(\d{2})\s+(\S+)', code_line)
            if level_match:
                level = level_match.group(1)
                name = level_match.group(2).strip('.')

                # Auto-detect working_storage context for copybooks starting with 01-level
                if current_section is None and level == '01':
                    current_section = 'working_storage'

                if not current_section:
                    continue

                # Skip FILLER
                if name.upper() == 'FILLER':
                    continue

                if level == '01':
                    # Start new 01-level record
                    current_01_record = {
                        'level': '01',
                        'name': name,
                        'record_name': name,
                        'fields': []
                    }

                    if current_section == 'working_storage':
                        working_storage.append(current_01_record)
                    elif current_section == 'linkage_section':
                        linkage_section.append(current_01_record)
                    elif current_section == 'file_section' and current_fd:
                        current_fd['records'].append(current_01_record)

                elif current_01_record:
                    # Extract field definition
                    field_def = self._extract_field_definition(code_line, level, name)
                    if field_def:
                        current_01_record['fields'].append(field_def)

        # Calculate summary
        total_fields = sum(len(rec.get('fields', [])) for rec in working_storage + linkage_section)
        for fd in file_section:
            for rec in fd.get('records', []):
                total_fields += len(rec.get('fields', []))

        return {
            'summary': {
                'total_fields': total_fields,
                'total_01_levels': len(working_storage) + len(linkage_section) + sum(
                    len(fd.get('records', [])) for fd in file_section
                ),
                'total_copybooks': len(copybooks),
                'total_fd_entries': len(file_section)
            },
            'working_storage': working_storage,
            'file_section': file_section,
            'linkage_section': linkage_section,
            'copybooks': copybooks
        }

    def _extract_fd_entry(self, line: str) -> Optional[Dict[str, Any]]:
        """Extract FD entry details."""
        match = re.search(r'FD\s+(\S+)', line, re.IGNORECASE)
        if match:
            fd_name = match.group(1).strip('.')

            # Try to extract record length
            record_length = None
            len_match = re.search(r'RECORD\s+(?:CONTAINS\s+)?(\d+)', line, re.IGNORECASE)
            if len_match:
                record_length = int(len_match.group(1))

            return {
                'fd_name': fd_name,
                'statement': line.strip(),
                'record_length': record_length
            }
        return None

    def _extract_field_definition(self, line: str, level: str, name: str) -> Dict[str, Any]:
        """
        Extract field definition with PIC, USAGE, OCCURS, REDEFINES.

        Args:
            line: Full line of COBOL code
            level: Level number (02-88)
            name: Field name

        Returns:
            Field definition dict
        """
        field = {
            'level': level,
            'name': name
        }

        line_upper = line.upper()

        # Extract PIC clause
        pic_match = re.search(r'\bPIC(?:TURE)?\s+(?:IS\s+)?(\S+)', line, re.IGNORECASE)
        if pic_match:
            pic_clause = pic_match.group(1).strip('.')
            field['pic'] = pic_clause

            # Determine USAGE if present
            usage = None
            if 'COMP-3' in line_upper:
                usage = 'COMP-3'
            elif 'COMP' in line_upper:
                usage = 'COMP'
            elif 'BINARY' in line_upper:
                usage = 'BINARY'

            # Map to SQL type with precision
            type_info = map_cobol_to_sql(pic_clause, usage)
            field['data_type'] = type_info.get('sql_type', 'VARCHAR')
            field['java_type'] = type_info.get('java_type', 'String')

            if 'length' in type_info:
                field['length'] = type_info['length']
            if 'precision' in type_info:
                field['precision'] = type_info['precision']
            if 'scale' in type_info:
                field['scale'] = type_info['scale']

        # Extract USAGE/COMP
        if 'COMP-3' in line_upper:
            field['usage'] = 'COMP-3'
            field['storage_type'] = 'packed_decimal'
        elif re.search(r'\bCOMP\b', line_upper):
            field['usage'] = 'COMP'
            field['storage_type'] = 'binary'
        elif 'BINARY' in line_upper:
            field['usage'] = 'BINARY'
            field['storage_type'] = 'binary'

        # Extract OCCURS
        occurs_match = re.search(r'\bOCCURS\s+(\d+)', line, re.IGNORECASE)
        if occurs_match:
            field['occurs'] = int(occurs_match.group(1))
            field['is_array'] = True

            # Check for DEPENDING ON
            depending_match = re.search(r'DEPENDING\s+ON\s+(\S+)', line, re.IGNORECASE)
            if depending_match:
                field['depending_on'] = depending_match.group(1).strip('.')

        # Extract REDEFINES
        redefines_match = re.search(r'\bREDEFINES\s+(\S+)', line, re.IGNORECASE)
        if redefines_match:
            field['redefines'] = redefines_match.group(1).strip('.')

        # Extract VALUE
        value_match = re.search(r'\bVALUE\s+(?:IS\s+)?([\'"].*?[\'"]|\S+)', line, re.IGNORECASE)
        if value_match:
            value = value_match.group(1).strip('"\'')
            field['value'] = value

            # Check for 88-level condition values
            if level == '88':
                field['is_condition'] = True

        return field
