"""
ERD Generator for Data Analysis

Combines results from:
- Regex extractor (data structures)
- AST analyzer (hierarchical entities, relationships)
- AI analyzer (business context, meanings)

Produces:
- erd.json (entities and relationships)
- data_lineage.json (data flows)
- copybook_analysis.json (copybook dependencies)
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from engines.data_analysis.utils.type_mapper import map_cobol_to_sql


class ERDGenerator:
    """
    Generate ERD and related artifacts by combining multiple analysis sources.

    This is the merge point of the data analysis pipeline.
    """

    def __init__(self):
        """Initialize ERD generator."""
        self.entities: Dict[str, Dict] = {}  # entity_id -> entity
        self.relationships: List[Dict] = []
        self.entity_name_map: Dict[str, str] = {}  # cobol_record -> entity_id

    def generate(
        self,
        regex_results: Dict[str, Any],
        ast_results: Dict[str, Any],
        ai_results: Optional[Dict[str, Any]] = None,
        job_id: str = ""
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """
        Generate ERD and related artifacts.

        Args:
            regex_results: Results from regex extractor
            ast_results: Results from AST analyzer
            ai_results: Optional results from AI analyzer

        Returns:
            Tuple of (erd, data_lineage, copybook_analysis)
        """
        # Reset state
        self.entities = {}
        self.relationships = []
        self.entity_name_map = {}

        # Phase 1: Build entities from AST (best structure)
        self._build_entities_from_ast(ast_results)

        # Phase 2: Enrich with regex data (type precision)
        self._enrich_from_regex(regex_results)

        # Phase 3: Enrich with AI insights (business context)
        if ai_results:
            self._enrich_from_ai(ai_results)

        # Phase 4: Detect relationships
        self._build_relationships(ast_results, ai_results)

        # Phase 5: Build data lineage
        data_lineage = self._build_data_lineage(ai_results)

        # Phase 6: Build copybook analysis
        copybook_analysis = self._build_copybook_analysis(regex_results, ast_results)

        # Build ERD output
        erd = self._build_erd_output(job_id)

        return erd, data_lineage, copybook_analysis

    def _build_entities_from_ast(self, ast_results: Dict[str, Any]) -> None:
        """Build initial entities from AST analysis."""
        for entity in ast_results.get('entities', []):
            entity_id = f"entity_{str(uuid.uuid4())[:8]}"
            record_name = entity.get('record_name', entity.get('name', ''))

            self.entity_name_map[record_name] = entity_id

            # Build attributes
            attributes = []
            for attr in entity.get('attributes', []):
                attributes.append({
                    'name': attr.get('name', ''),
                    'cobol_field': attr.get('cobol_name', ''),
                    'data_type': attr.get('data_type', 'VARCHAR'),
                    'sql_type': attr.get('data_type', 'VARCHAR'),
                    'length': attr.get('length'),
                    'precision': attr.get('precision'),
                    'scale': attr.get('scale'),
                    'is_primary_key': attr.get('is_potential_key', False),
                    'is_foreign_key': False,
                    'nullable': True,
                    'source_pic': attr.get('pic', ''),
                    'business_meaning': None  # Will be enriched by AI
                })

            self.entities[entity_id] = {
                'id': entity_id,
                'name': entity.get('name', ''),
                'source': {
                    'cobol_record': record_name,
                    'files': [entity.get('source_file', '')],
                    'section': entity.get('section', 'working_storage')
                },
                'business_purpose': None,  # Will be enriched by AI
                'attributes': attributes,
                'confidence': 0.85
            }

    def _enrich_from_regex(self, regex_results: Dict[str, Any]) -> None:
        """Enrich entities with precise type information from regex."""
        # Build lookup from regex results
        regex_records: Dict[str, Dict] = {}

        for file_data in regex_results.get('files', []):
            ds = file_data.get('data_structures', {})

            for record in ds.get('working_storage', []) + ds.get('linkage_section', []):
                record_name = record.get('name', '')
                regex_records[record_name] = record

        # Enrich entities
        for entity_id, entity in self.entities.items():
            record_name = entity['source'].get('cobol_record', '')
            if record_name not in regex_records:
                continue

            regex_record = regex_records[record_name]
            regex_fields = {f.get('name', ''): f for f in regex_record.get('fields', [])}

            # Update attributes with precise types
            for attr in entity['attributes']:
                cobol_field = attr.get('cobol_field', '')
                if cobol_field in regex_fields:
                    regex_field = regex_fields[cobol_field]

                    # Update with precise type info
                    if regex_field.get('data_type'):
                        attr['sql_type'] = regex_field['data_type']
                        attr['data_type'] = regex_field['data_type']
                    if regex_field.get('length'):
                        attr['length'] = regex_field['length']
                    if regex_field.get('precision'):
                        attr['precision'] = regex_field['precision']
                    if regex_field.get('scale'):
                        attr['scale'] = regex_field['scale']
                    if regex_field.get('pic'):
                        attr['source_pic'] = regex_field['pic']

    def _enrich_from_ai(self, ai_results: Dict[str, Any]) -> None:
        """Enrich entities with business context from AI analysis."""
        # Build lookup from AI results
        ai_entities: Dict[str, Dict] = {}
        ai_meanings: Dict[str, str] = ai_results.get('business_meanings', {})

        for entity in ai_results.get('entities', []):
            record = entity.get('cobol_record', '')
            ai_entities[record] = entity

        # Enrich entities
        for entity_id, entity in self.entities.items():
            record_name = entity['source'].get('cobol_record', '')

            if record_name in ai_entities:
                ai_entity = ai_entities[record_name]
                entity['business_purpose'] = ai_entity.get('business_purpose')
                entity['confidence'] = max(
                    entity['confidence'],
                    ai_entity.get('confidence', 0.8)
                )

            # Enrich attribute business meanings
            for attr in entity['attributes']:
                cobol_field = attr.get('cobol_field', '')
                if cobol_field in ai_meanings:
                    attr['business_meaning'] = ai_meanings[cobol_field]
                elif not attr.get('business_meaning'):
                    # Generate basic meaning from field name
                    attr['business_meaning'] = self._infer_business_meaning(cobol_field)

    def _build_relationships(
        self,
        ast_results: Dict[str, Any],
        ai_results: Optional[Dict[str, Any]] = None
    ) -> None:
        """Build relationships from AST and AI analysis."""
        seen_relationships: Set[Tuple[str, str]] = set()

        # Add AST-detected relationships
        for rel in ast_results.get('relationships', []):
            from_record = rel.get('from_record', rel.get('from_entity', ''))
            to_record = rel.get('to_record', rel.get('to_entity', ''))

            from_entity_id = self.entity_name_map.get(from_record)
            to_entity_id = self.entity_name_map.get(to_record)

            if not from_entity_id or not to_entity_id:
                continue

            pair = tuple(sorted([from_entity_id, to_entity_id]))
            if pair in seen_relationships:
                continue
            seen_relationships.add(pair)

            self.relationships.append({
                'id': f"rel_{str(uuid.uuid4())[:8]}",
                'from_entity': self.entities[from_entity_id]['name'],
                'to_entity': self.entities[to_entity_id]['name'],
                'from_entity_id': from_entity_id,
                'to_entity_id': to_entity_id,
                'relationship_type': rel.get('relationship_type', 'potential_foreign_key'),
                'cardinality': rel.get('cardinality', '1:N'),
                'business_rule': rel.get('business_rule'),
                'join_field': rel.get('join_field'),
                'confidence': rel.get('confidence', 0.7),
                'sources': ['ast_analysis']
            })

        # Add AI-detected relationships
        if ai_results:
            for rel in ai_results.get('relationships', []):
                from_entity = rel.get('from_entity', '')
                to_entity = rel.get('to_entity', '')

                # Find entity IDs by name
                from_entity_id = None
                to_entity_id = None

                for eid, entity in self.entities.items():
                    if entity['name'] == from_entity:
                        from_entity_id = eid
                    if entity['name'] == to_entity:
                        to_entity_id = eid

                if not from_entity_id or not to_entity_id:
                    continue

                pair = tuple(sorted([from_entity_id, to_entity_id]))
                if pair in seen_relationships:
                    # Update existing relationship with AI info
                    for existing in self.relationships:
                        existing_pair = tuple(sorted([
                            existing.get('from_entity_id', ''),
                            existing.get('to_entity_id', '')
                        ]))
                        if existing_pair == pair:
                            if rel.get('business_rule'):
                                existing['business_rule'] = rel['business_rule']
                            if rel.get('cardinality'):
                                existing['cardinality'] = rel['cardinality']
                            if 'ai_analysis' not in existing['sources']:
                                existing['sources'].append('ai_analysis')
                            break
                    continue

                seen_relationships.add(pair)

                self.relationships.append({
                    'id': f"rel_{str(uuid.uuid4())[:8]}",
                    'from_entity': from_entity,
                    'to_entity': to_entity,
                    'from_entity_id': from_entity_id,
                    'to_entity_id': to_entity_id,
                    'relationship_type': rel.get('relationship_type', 'foreign_key'),
                    'cardinality': rel.get('cardinality', '1:N'),
                    'business_rule': rel.get('business_rule'),
                    'join_field': rel.get('join_fields', [None])[0] if rel.get('join_fields') else None,
                    'confidence': rel.get('confidence', 0.8),
                    'sources': ['ai_analysis']
                })

    def _build_data_lineage(
        self,
        ai_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build data lineage from AI analysis."""
        flows = []

        if ai_results:
            for flow in ai_results.get('data_flows', []):
                flows.append({
                    'flow_name': flow.get('flow_name', 'Data Flow'),
                    'source_file': flow.get('source', 'Unknown'),
                    'source_type': 'file',
                    'transformations': [
                        {
                            'operation': t,
                            'program': '',
                            'description': t
                        }
                        for t in flow.get('transformations', [])
                    ],
                    'destination_file': flow.get('destination', 'Unknown'),
                    'destination_type': 'file',
                    'business_impact': flow.get('business_purpose', '')
                })

        return {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_flows': len(flows)
            },
            'flows': flows
        }

    def _build_copybook_analysis(
        self,
        regex_results: Dict[str, Any],
        ast_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build copybook analysis from regex and AST results."""
        copybooks: Dict[str, Dict] = {}

        # From AST
        for cb in ast_results.get('copybook_analysis', []):
            name = cb.get('copybook_name', cb.get('name', ''))
            if name not in copybooks:
                copybooks[name] = {
                    'name': name,
                    'used_by': [],
                    'data_structures': [],
                    'total_fields': 0
                }
            copybooks[name]['used_by'].extend(cb.get('used_by', []))

        # From regex
        for file_data in regex_results.get('files', []):
            file_path = file_data.get('file_path', '')
            ds = file_data.get('data_structures', {})

            for cb in ds.get('copybooks', []):
                name = cb.get('copybook_name', '')
                if not name:
                    continue

                if name not in copybooks:
                    copybooks[name] = {
                        'name': name,
                        'used_by': [],
                        'data_structures': [],
                        'total_fields': 0
                    }

                if file_path not in copybooks[name]['used_by']:
                    copybooks[name]['used_by'].append(file_path)

        # Deduplicate used_by lists
        for cb in copybooks.values():
            cb['used_by'] = list(set(cb['used_by']))

        return {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_copybooks': len(copybooks)
            },
            'copybooks': list(copybooks.values())
        }

    def _build_erd_output(self, job_id: str) -> Dict[str, Any]:
        """Build final ERD output."""
        # Calculate summary
        total_attributes = sum(
            len(e.get('attributes', []))
            for e in self.entities.values()
        )

        entities_by_section: Dict[str, int] = {}
        for entity in self.entities.values():
            section = entity['source'].get('section', 'unknown')
            entities_by_section[section] = entities_by_section.get(section, 0) + 1

        return {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'job_id': job_id,
            'summary': {
                'total_entities': len(self.entities),
                'total_relationships': len(self.relationships),
                'total_attributes': total_attributes,
                'entities_by_section': entities_by_section
            },
            'entities': list(self.entities.values()),
            'relationships': self.relationships
        }

    def _infer_business_meaning(self, field_name: str) -> str:
        """Infer business meaning from field name patterns."""
        name_lower = field_name.lower().replace('-', '_')

        patterns = [
            (r'_id$|^id_', 'Unique identifier'),
            (r'_key$|^key_', 'Key field'),
            (r'_cd$|_code$', 'Code value'),
            (r'_dt$|_date$', 'Date value'),
            (r'_tm$|_time$', 'Time value'),
            (r'_ts$|_timestamp$', 'Timestamp'),
            (r'_amt$|_amount$', 'Amount value'),
            (r'_cnt$|_count$', 'Count value'),
            (r'_nbr$|_num$|_number$', 'Number value'),
            (r'_nm$|_name$', 'Name field'),
            (r'_addr$|_address$', 'Address field'),
            (r'_desc$|_description$', 'Description'),
            (r'_ind$|_flag$', 'Boolean indicator'),
            (r'_pct$|_percent$', 'Percentage'),
            (r'_rate$', 'Rate value'),
            (r'_status$|_sts$', 'Status value'),
            (r'_type$|_typ$', 'Type classification'),
        ]

        import re
        for pattern, meaning in patterns:
            if re.search(pattern, name_lower):
                return meaning

        # Default: humanize the field name
        words = field_name.replace('-', ' ').replace('_', ' ').title()
        return f"{words} field"
