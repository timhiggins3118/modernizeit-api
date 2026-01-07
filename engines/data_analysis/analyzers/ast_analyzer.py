"""
AST-based Data Analyzer for Data Analysis

Analyzes hierarchical data structures to identify:
- Potential database entities
- Relationships between entities
- Primary/foreign key candidates
- Copybook dependencies
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from engines.data_analysis.utils.type_mapper import map_cobol_to_sql


class ASTDataAnalyzer:
    """
    Analyze COBOL data structures for entity-relationship modeling.

    This is Branch 2 of the data analysis pipeline - structural analysis.
    """

    # Keywords that suggest a field is a key
    KEY_INDICATORS = {'ID', 'KEY', 'CODE', 'NUMBER', 'NBR', 'NUM', 'NO', 'SEQ'}

    # Suffixes to remove for entity naming
    ENTITY_SUFFIXES = ['-RECORD', '-REC', '-FILE', '-DATA', '-AREA', '-WS', '-WORK']

    def __init__(self):
        """Initialize the AST analyzer."""
        self.entities: List[Dict] = []
        self.relationships: List[Dict] = []
        self.copybook_usage: Dict[str, Dict] = {}
        self.field_index: Dict[str, List[Dict]] = {}  # field_name -> list of entities

    def analyze_directory(self, source_path: str) -> Dict[str, Any]:
        """
        Analyze all COBOL files in directory for entities and relationships.

        Args:
            source_path: Path to directory containing COBOL files

        Returns:
            Analysis results with entities, relationships, copybook usage
        """
        source_dir = Path(source_path)

        # Reset state
        self.entities = []
        self.relationships = []
        self.copybook_usage = {}
        self.field_index = {}

        # Find all COBOL files
        cobol_patterns = ['*.cbl', '*.CBL', '*.cob', '*.COB', '*.cobol', '*.COBOL']
        cobol_files = []

        for pattern in cobol_patterns:
            cobol_files.extend(source_dir.rglob(pattern))

        # Analyze each file
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

                self._analyze_file(content, relative_path)
            except Exception as e:
                print(f"Error analyzing {file_path}: {e}")
                continue

        # Detect relationships after all entities are collected
        self._detect_relationships()

        return {
            'summary': {
                'total_entities': len(self.entities),
                'total_relationships': len(self.relationships),
                'copybook_files': len(self.copybook_usage)
            },
            'entities': self.entities,
            'relationships': self.relationships,
            'copybook_analysis': [
                {'copybook_name': name, **info}
                for name, info in self.copybook_usage.items()
            ]
        }

    def _analyze_file(self, content: str, file_path: str) -> None:
        """Analyze a single COBOL file."""
        lines = content.split('\n')

        current_section: Optional[str] = None
        current_entity: Optional[Dict] = None
        level_stack: List[Tuple[int, Dict]] = []  # Stack of (level, entity/group)

        for line in lines:
            # Strip sequence numbers
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
                current_entity = None
                level_stack = []
                continue
            elif 'FILE SECTION' in code_upper:
                current_section = 'file_section'
                current_entity = None
                level_stack = []
                continue
            elif 'LINKAGE SECTION' in code_upper:
                current_section = 'linkage_section'
                current_entity = None
                level_stack = []
                continue
            elif 'PROCEDURE DIVISION' in code_upper:
                current_section = None
                current_entity = None
                level_stack = []
                continue

            # Track copybook usage
            copy_match = re.search(r'\bCOPY\s+(\S+)', code_line, re.IGNORECASE)
            if copy_match:
                copybook_name = copy_match.group(1).strip('.')
                if copybook_name not in self.copybook_usage:
                    self.copybook_usage[copybook_name] = {
                        'used_by': [],
                        'data_structures': []
                    }
                if file_path not in self.copybook_usage[copybook_name]['used_by']:
                    self.copybook_usage[copybook_name]['used_by'].append(file_path)

            # Look for FD entries in copybooks (auto-detect file_section)
            if code_line.strip().upper().startswith('FD '):
                if current_section is None:
                    current_section = 'file_section'
                continue

            # Look for level numbers
            level_match = re.match(r'^\s*(\d{2})\s+(\S+)', code_line)
            if not level_match:
                continue

            level = int(level_match.group(1))
            name = level_match.group(2).strip('.')

            # Auto-detect working_storage context for copybooks starting with 01-level
            if current_section is None and level == 1:
                current_section = 'working_storage'

            if not current_section:
                continue

            # Skip FILLER
            if name.upper() == 'FILLER':
                continue

            # 01-level: potential entity
            if level == 1:
                # Save previous entity if it has enough attributes
                if current_entity and len(current_entity['attributes']) >= 2:
                    self.entities.append(current_entity)
                    self._index_entity_fields(current_entity)

                # Start new entity
                current_entity = {
                    'name': self._to_entity_name(name),
                    'source_file': file_path,
                    'record_name': name,
                    'section': current_section,
                    'attributes': []
                }
                level_stack = [(1, current_entity)]

            # Field levels (02-49)
            elif 2 <= level <= 49 and current_entity:
                # Pop stack to find parent
                while level_stack and level_stack[-1][0] >= level:
                    level_stack.pop()

                attribute = self._extract_attribute(code_line, level, name)
                current_entity['attributes'].append(attribute)

                # Push this level if it might have children (group item)
                if 'pic' not in attribute:
                    level_stack.append((level, attribute))

        # Save last entity
        if current_entity and len(current_entity['attributes']) >= 2:
            self.entities.append(current_entity)
            self._index_entity_fields(current_entity)

    def _extract_attribute(self, line: str, level: int, name: str) -> Dict[str, Any]:
        """Extract attribute details from a field definition."""
        attribute = {
            'name': self._to_attribute_name(name),
            'cobol_name': name,
            'level': str(level).zfill(2)
        }

        line_upper = line.upper()

        # Extract PIC clause
        pic_match = re.search(r'\bPIC(?:TURE)?\s+(?:IS\s+)?(\S+)', line, re.IGNORECASE)
        if pic_match:
            pic_clause = pic_match.group(1).strip('.')
            attribute['pic'] = pic_clause

            # Get usage
            usage = None
            if 'COMP-3' in line_upper:
                usage = 'COMP-3'
            elif 'COMP' in line_upper:
                usage = 'COMP'

            # Map to SQL type
            type_info = map_cobol_to_sql(pic_clause, usage)
            attribute['data_type'] = type_info.get('sql_type', 'VARCHAR')

            if 'length' in type_info:
                attribute['length'] = type_info['length']
            if 'precision' in type_info:
                attribute['precision'] = type_info['precision']
            if 'scale' in type_info:
                attribute['scale'] = type_info['scale']

        # Check if potential key
        name_upper = name.upper()
        if any(indicator in name_upper for indicator in self.KEY_INDICATORS):
            attribute['is_potential_key'] = True

        # Check for OCCURS (array)
        occurs_match = re.search(r'\bOCCURS\s+(\d+)', line, re.IGNORECASE)
        if occurs_match:
            attribute['occurs'] = int(occurs_match.group(1))
            attribute['is_array'] = True

        # Check for REDEFINES
        redefines_match = re.search(r'\bREDEFINES\s+(\S+)', line, re.IGNORECASE)
        if redefines_match:
            attribute['redefines'] = redefines_match.group(1).strip('.')

        return attribute

    def _detect_relationships(self) -> None:
        """Detect relationships between entities based on field name matching."""
        processed_pairs: Set[Tuple[str, str]] = set()

        for i, entity_a in enumerate(self.entities):
            for entity_b in self.entities[i + 1:]:
                # Skip if same entity or already processed
                pair_key = tuple(sorted([entity_a['record_name'], entity_b['record_name']]))
                if pair_key in processed_pairs:
                    continue
                processed_pairs.add(pair_key)

                # Find common key fields
                for attr_a in entity_a['attributes']:
                    if not attr_a.get('is_potential_key'):
                        continue

                    for attr_b in entity_b['attributes']:
                        if not attr_b.get('is_potential_key'):
                            continue

                        # Match on COBOL field name
                        if attr_a['cobol_name'].upper() == attr_b['cobol_name'].upper():
                            self.relationships.append({
                                'from_entity': entity_a['name'],
                                'to_entity': entity_b['name'],
                                'from_record': entity_a['record_name'],
                                'to_record': entity_b['record_name'],
                                'relationship_type': 'potential_foreign_key',
                                'join_field': attr_a['name'],
                                'cobol_field': attr_a['cobol_name'],
                                'confidence': 0.7,
                                'source': 'field_name_match'
                            })

    def _index_entity_fields(self, entity: Dict) -> None:
        """Index entity fields for relationship detection."""
        for attr in entity['attributes']:
            if attr.get('is_potential_key'):
                field_name = attr['cobol_name'].upper()
                if field_name not in self.field_index:
                    self.field_index[field_name] = []
                self.field_index[field_name].append({
                    'entity': entity['name'],
                    'record': entity['record_name'],
                    'attribute': attr
                })

    def _to_entity_name(self, record_name: str) -> str:
        """Convert COBOL record name to entity name (PascalCase)."""
        name = record_name

        # Remove common suffixes
        for suffix in self.ENTITY_SUFFIXES:
            if name.upper().endswith(suffix):
                name = name[:-len(suffix)]
                break

        # Convert to PascalCase
        parts = name.replace('_', '-').split('-')
        return ''.join(p.capitalize() for p in parts if p)

    def _to_attribute_name(self, field_name: str) -> str:
        """Convert COBOL field name to attribute name (snake_case)."""
        return field_name.replace('-', '_').lower()
