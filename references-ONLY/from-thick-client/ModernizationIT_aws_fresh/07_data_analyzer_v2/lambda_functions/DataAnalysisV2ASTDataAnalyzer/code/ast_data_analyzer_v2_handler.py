#!/usr/bin/env python3
"""
Data Analyzer V2 - AST Data Analyzer
Analyzes hierarchical data structures and relationships
NO CODE SHARING with Code Analysis V2
"""

import json
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    Analyze data hierarchies and relationships using simple parsing
    (NO tree-sitter dependency - independent implementation)
    """

    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']

        print(f"Starting AST data analysis for job: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        extracted_path = f"{base_path}/shared/uploads/{source_hash}/extracted/"

        # Read classified catalog
        catalog_key = f"{base_path}/shared/catalogs/{source_hash}/classified_catalog.json"
        catalog_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=catalog_key)
        classified_catalog = json.loads(catalog_response['Body'].read().decode('utf-8'))

        cobol_files = classified_catalog.get('classifications', {}).get('cobol', [])

        entities = []
        relationships = []
        copybook_usage = {}

        for file_path in cobol_files:
            print(f"Analyzing: {file_path}")

            # Read file
            full_key = f"{extracted_path}{file_path}"
            file_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=full_key)
            content = file_response['Body'].read().decode('utf-8', errors='ignore')

            # Analyze hierarchical structures
            file_entities = analyze_hierarchical_structures(content, file_path)
            entities.extend(file_entities)

            # Analyze copybook usage
            file_copybooks = extract_copybook_usage(content, file_path)
            for cb_name, cb_info in file_copybooks.items():
                if cb_name not in copybook_usage:
                    copybook_usage[cb_name] = {'used_by': [], 'data_structures': []}
                copybook_usage[cb_name]['used_by'].append(file_path)

        # Detect relationships between entities
        relationships = detect_relationships(entities)

        # Build output
        output = {
            'job_id': job_id,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_entities': len(entities),
                'total_relationships': len(relationships),
                'copybook_files': len(copybook_usage)
            },
            'entities': entities,
            'relationships': relationships,
            'copybook_analysis': [
                {'copybook_name': name, **info}
                for name, info in copybook_usage.items()
            ]
        }

        # Save results
        output_key = f"{base_path}/data_analysis_v2/jobs/{job_id}/artifacts/hierarchical_structures.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(output, indent=2),
            ContentType='application/json'
        )

        print(f"AST data analysis complete: {len(entities)} entities, {len(relationships)} relationships")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'entities_found': len(entities),
                'relationships_found': len(relationships),
                'output_path': f"s3://{BUCKET_NAME}/{output_key}"
            }
        }

    except Exception as e:
        print(f"Error in AST data analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }


def analyze_hierarchical_structures(content, file_path):
    """Analyze hierarchical data structures to identify entities"""

    lines = content.split('\n')
    entities = []
    current_entity = None
    current_section = None

    for line in lines:
        # Strip line numbers
        if len(line) > 6:
            code_line = line[6:].rstrip()
        else:
            code_line = line.rstrip()

        # Skip comments and blank lines
        if not code_line or code_line.startswith('*'):
            continue

        # Track sections
        if 'WORKING-STORAGE SECTION' in code_line.upper():
            current_section = 'working_storage'
            continue
        elif 'FILE SECTION' in code_line.upper():
            current_section = 'file_section'
            continue
        elif 'LINKAGE SECTION' in code_line.upper():
            current_section = 'linkage_section'
            continue
        elif 'PROCEDURE DIVISION' in code_line.upper():
            current_section = None
            continue

        # Look for 01-level records (potential entities)
        if code_line.strip().startswith('01 '):
            parts = code_line.strip().split(None, 2)
            if len(parts) >= 2:
                record_name = parts[1].strip('.')

                # Skip FILLER
                if record_name == 'FILLER':
                    continue

                # Determine if this is a potential entity
                # Heuristic: Records with multiple fields in FILE or WORKING-STORAGE
                if current_section in ['file_section', 'working_storage']:
                    # Save previous entity
                    if current_entity and len(current_entity['attributes']) > 2:
                        entities.append(current_entity)

                    # Start new entity
                    current_entity = {
                        'name': convert_to_entity_name(record_name),
                        'source_file': file_path,
                        'record_name': record_name,
                        'section': current_section,
                        'attributes': []
                    }

        # Look for field definitions (05-49 levels)
        elif current_entity and code_line.strip() and code_line.strip()[0].isdigit():
            parts = code_line.strip().split(None, 2)
            if len(parts) >= 2:
                level = parts[0]
                field_name = parts[1].strip('.')

                if level in ['05', '10', '15', '20'] and field_name != 'FILLER':
                    # Extract field attributes
                    attribute = {
                        'name': field_name.replace('-', '_').lower(),
                        'cobol_name': field_name,
                        'level': level
                    }

                    # Check for PIC clause
                    if 'PIC' in code_line.upper():
                        pic_start = code_line.upper().find('PIC')
                        pic_section = code_line[pic_start:].split()[1]
                        attribute['pic'] = pic_section.strip('.')

                        # Determine SQL type
                        attribute['data_type'] = map_cobol_to_sql_type(pic_section, code_line)

                    # Check if potential key (contains ID, KEY, CODE)
                    if any(kw in field_name.upper() for kw in ['ID', 'KEY', 'CODE', 'NUMBER']):
                        attribute['is_potential_key'] = True

                    current_entity['attributes'].append(attribute)

    # Add last entity
    if current_entity and len(current_entity['attributes']) > 2:
        entities.append(current_entity)

    return entities


def detect_relationships(entities):
    """Detect potential relationships between entities based on field names"""

    relationships = []

    for i, entity_a in enumerate(entities):
        for entity_b in entities[i+1:]:
            # Look for common fields that suggest a relationship
            for attr_a in entity_a['attributes']:
                for attr_b in entity_b['attributes']:
                    # Match on field names containing ID, KEY, etc.
                    if attr_a.get('is_potential_key') and attr_b.get('is_potential_key'):
                        if attr_a['cobol_name'] == attr_b['cobol_name']:
                            # Found a potential FK relationship
                            relationships.append({
                                'from_entity': entity_a['name'],
                                'to_entity': entity_b['name'],
                                'relationship_type': 'potential_foreign_key',
                                'join_field': attr_a['name'],
                                'confidence': 0.7,
                                'source': 'field_name_match'
                            })

    return relationships


def extract_copybook_usage(content, file_path):
    """Extract which copybooks are used"""

    copybooks = {}
    lines = content.split('\n')

    for line in lines:
        if 'COPY' in line.upper():
            # Extract copybook name
            import re
            match = re.search(r'\bCOPY\s+(\S+)', line, re.IGNORECASE)
            if match:
                copybook_name = match.group(1).strip('.')
                copybooks[copybook_name] = {
                    'statement': line.strip()
                }

    return copybooks


def convert_to_entity_name(record_name):
    """Convert COBOL record name to entity name"""
    # Remove -RECORD, -REC, -FILE suffixes
    name = record_name.replace('-RECORD', '').replace('-REC', '').replace('-FILE', '')
    # Convert to title case
    parts = name.split('-')
    return ''.join(p.capitalize() for p in parts)


def map_cobol_to_sql_type(pic_clause, full_line):
    """Map COBOL PIC clause to SQL data type"""

    pic_upper = pic_clause.upper()

    # Check for COMP-3 (packed decimal)
    if 'COMP-3' in full_line.upper():
        return 'DECIMAL'

    # Check for COMP/BINARY
    if 'COMP' in full_line.upper() or 'BINARY' in full_line.upper():
        return 'INTEGER'

    # Numeric types
    if '9' in pic_upper:
        if 'V' in pic_upper:
            return 'DECIMAL'
        else:
            return 'INTEGER'

    # Alphanumeric
    if 'X' in pic_upper:
        return 'VARCHAR'

    # Alphabetic
    if 'A' in pic_upper:
        return 'VARCHAR'

    return 'VARCHAR'  # Default
