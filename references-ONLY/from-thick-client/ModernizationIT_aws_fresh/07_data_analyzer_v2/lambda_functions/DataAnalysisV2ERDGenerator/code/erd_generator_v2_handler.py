#!/usr/bin/env python3
"""
Data Analyzer V2 - ERD Generator
THE INTELLIGENCE LAYER - Combines regex, AST, and AI analysis into unified ERD
"""

import json
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def load_type_mapping(base_path, source_hash):
    """
    Load COBOL→Java type mapping from shared storage
    Falls back to minimal defaults if not found
    """
    try:
        mapping_key = f"{base_path}/shared/type_mappings/{source_hash}/cobol_to_java.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=mapping_key)
        type_mapping = json.loads(response['Body'].read().decode('utf-8'))
        print(f"✓ Loaded type mapping: {mapping_key}")
        return type_mapping
    except ClientError as e:
        print(f"WARNING: Type mapping not found, using defaults: {str(e)}")
        # Return minimal default mapping
        return {
            'default_mapping': {'sql_type': 'VARCHAR', 'java_type': 'String'}
        }


def map_cobol_pic_to_sql(pic_clause, type_mapping):
    """
    Map COBOL PIC clause to SQL data type using type mapping rules

    Args:
        pic_clause: COBOL PIC clause (e.g., "9(7)V99", "X(50)", "$$,$$$,$$9.99")
        type_mapping: Type mapping dict loaded from S3

    Returns:
        SQL data type string (e.g., "DECIMAL", "INTEGER", "VARCHAR")
    """
    if not pic_clause or pic_clause == 'N/A':
        return type_mapping.get('default_mapping', {}).get('sql_type', 'VARCHAR')

    pic_upper = pic_clause.upper()

    # Check for decimal indicators (V, ., $, Z, ,)
    # These indicate the field has decimal places → DECIMAL
    decimal_indicators = ['V', '.', '$', 'Z', ',']
    has_decimal = any(char in pic_upper for char in decimal_indicators)

    if has_decimal:
        # Has decimal places → DECIMAL
        return 'DECIMAL'

    # Check for numeric patterns without decimals
    if '9' in pic_upper or 'S9' in pic_upper:
        # Numeric without decimal → INTEGER
        return 'INTEGER'

    # Check for alphanumeric
    if 'X' in pic_upper or 'A' in pic_upper:
        return 'VARCHAR'

    # Check for special types
    if 'COMP' in pic_upper or 'BINARY' in pic_upper:
        return 'INTEGER'

    # Default fallback
    return type_mapping.get('default_mapping', {}).get('sql_type', 'VARCHAR')


def lambda_handler(event, context):
    """
    Generate ERD from combined data analysis sources
    Input: job_id, scout_account_id, application_name, source_hash
    Output: erd.json, data_lineage.json, copybook_analysis.json
    """

    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']

        print(f"Generating ERD for job: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        artifacts_path = f"{base_path}/data_analysis_v2/jobs/{job_id}/artifacts"

        # Load type mapping from shared storage
        type_mapping = load_type_mapping(base_path, source_hash)

        # Read all analysis results
        regex_data = read_json(f"{artifacts_path}/data_structures.json")
        ast_data = read_json(f"{artifacts_path}/hierarchical_structures.json")
        ai_data = read_json(f"{artifacts_path}/ai_data_analysis.json")

        # Generate ERD with type mapping
        erd = generate_erd(regex_data, ast_data, ai_data, type_mapping)

        # Generate data lineage
        data_lineage = generate_data_lineage(regex_data, ast_data, ai_data)

        # Generate copybook analysis
        copybook_analysis = generate_copybook_analysis(regex_data, ast_data)

        # Save ERD
        erd_key = f"{artifacts_path}/erd.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=erd_key,
            Body=json.dumps(erd, indent=2),
            ContentType='application/json'
        )

        # Save data lineage
        lineage_key = f"{artifacts_path}/data_lineage.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=lineage_key,
            Body=json.dumps(data_lineage, indent=2),
            ContentType='application/json'
        )

        # Save copybook analysis
        copybook_key = f"{artifacts_path}/copybook_analysis.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=copybook_key,
            Body=json.dumps(copybook_analysis, indent=2),
            ContentType='application/json'
        )

        print(f"ERD generation complete: {len(erd['entities'])} entities, {len(erd['relationships'])} relationships")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'entities': len(erd['entities']),
                'relationships': len(erd['relationships']),
                'output_path': f"s3://{BUCKET_NAME}/{erd_key}"
            }
        }

    except Exception as e:
        print(f"Error generating ERD: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }


def read_json(key):
    """Read JSON from S3"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return {}
        raise


def merge_entity_attributes(ast_attributes, regex_data, record_name, source_file):
    """
    Merge attributes from AST and regex analysis to get ALL fields
    This ensures we capture every field from the copybook
    """
    # Start with AST attributes
    merged_attrs = {}

    for attr in ast_attributes:
        cobol_name = attr.get('cobol_name', attr.get('name', 'UNKNOWN'))
        merged_attrs[cobol_name.upper()] = attr

    initial_count = len(merged_attrs)

    # Add fields from regex data that AST might have missed
    # Search ALL files (not just source_file) because records may be in copybooks
    for file_result in regex_data.get('files', []):
        data_structures = file_result.get('data_structures', {})

        # Check working storage section
        for ws_record in data_structures.get('working_storage', []):
            if ws_record.get('record_name', '').upper() == record_name.upper():
                for field in ws_record.get('fields', []):
                    field_name = field.get('name', 'UNKNOWN')
                    if field_name.upper() not in merged_attrs:
                        # This field was in regex but NOT in AST - add it!
                        merged_attrs[field_name.upper()] = {
                            'name': field_name,
                            'cobol_name': field_name,
                            'pic': field.get('pic', 'N/A'),
                            'level': field.get('level', '05')
                        }

        # Also check file section
        for fd_record in data_structures.get('file_section', []):
            # FD records have nested record structures
            for record in fd_record.get('records', []):
                if record.get('name', '').upper() == record_name.upper():
                    for field in record.get('fields', []):
                        field_name = field.get('name', 'UNKNOWN')
                        if field_name.upper() not in merged_attrs:
                            merged_attrs[field_name.upper()] = {
                                'name': field_name,
                                'cobol_name': field_name,
                                'pic': field.get('pic', 'N/A'),
                                'level': field.get('level', '05')
                            }

    final_count = len(merged_attrs)
    if final_count > initial_count:
        print(f"  Merged {record_name}: {initial_count} AST fields + {final_count - initial_count} regex fields = {final_count} total")

    # Return list of all attributes
    return list(merged_attrs.values())


def generate_erd(regex_data, ast_data, ai_data, type_mapping):
    """Generate ERD from all analysis sources with proper type mapping"""

    entities = []
    relationships = []

    # Parse AI analysis to extract entities and relationships
    ai_entities = parse_ai_entities(ai_data)
    ai_relationships = parse_ai_relationships(ai_data)

    # Get entities from AST analysis (hierarchical structures)
    ast_entities = ast_data.get('entities', [])

    entity_id_counter = 1
    entity_name_map = {}  # Track entities by name for relationship linking

    for ast_entity in ast_entities:
        entity_name = ast_entity['name']

        # Find matching AI entity for enhanced metadata
        ai_match = next((e for e in ai_entities if e['record_name'].upper() == ast_entity['record_name'].upper()), None)

        entity = {
            'id': f"entity_{entity_id_counter:03d}",
            'name': ai_match['table_name'] if ai_match else entity_name,
            'source': {
                'cobol_record': ast_entity['record_name'],
                'files': [ast_entity['source_file']],
                'section': ast_entity.get('section', 'working_storage')
            },
            'attributes': []
        }

        # Add business purpose from AI if available
        if ai_match:
            entity['business_purpose'] = ai_match.get('business_purpose', '')

        # COMBINE fields from AST and regex data to get ALL fields
        all_attributes = merge_entity_attributes(
            ast_attributes=ast_entity.get('attributes', []),
            regex_data=regex_data,
            record_name=ast_entity['record_name'],
            source_file=ast_entity['source_file']
        )

        # Add attributes with AI-enhanced metadata
        for attr in all_attributes:
            # Map PIC clause to SQL data type using type mapping rules
            pic_clause = attr.get('pic', 'N/A')
            sql_type = map_cobol_pic_to_sql(pic_clause, type_mapping)

            attribute = {
                'name': attr['name'],
                'cobol_field': attr['cobol_name'],
                'data_type': sql_type,  # Now using proper PIC clause mapping!
                'is_primary_key': False,
                'nullable': True,
                'source_pic': pic_clause
            }

            # Check if AI identified this as a primary key
            if ai_match and attr['cobol_name'].upper() in [pk.upper() for pk in ai_match.get('primary_keys', [])]:
                attribute['is_primary_key'] = True
                attribute['nullable'] = False

            entity['attributes'].append(attribute)

        # Calculate confidence (higher if AI agrees with AST)
        entity['confidence'] = ai_match['confidence'] if ai_match else 0.85

        entities.append(entity)
        entity_name_map[ast_entity['record_name'].upper()] = entity['id']
        entity_id_counter += 1

    # Build AI entity name to record name lookup
    ai_entity_to_record = {}
    for ai_ent in ai_entities:
        ai_entity_to_record[ai_ent['entity_name'].upper()] = ai_ent['record_name'].upper()

    # Extract relationships from AI analysis
    print(f"Entity name map has {len(entity_name_map)} records: {list(entity_name_map.keys())[:10]}")
    print(f"Found {len(ai_relationships)} AI relationships to process")
    print(f"AI entity to record mapping: {ai_entity_to_record}")

    rel_id_counter = 1
    for ai_rel in ai_relationships:
        # Try to map AI relationship to entity IDs
        # First try direct record name match
        from_record = ai_rel['from_record'].upper()
        to_record = ai_rel['to_record'].upper()

        # If the from/to are entity names, look up the actual record name
        if from_record in ai_entity_to_record:
            from_record = ai_entity_to_record[from_record]
        elif ai_rel['from_entity'].upper() in ai_entity_to_record:
            from_record = ai_entity_to_record[ai_rel['from_entity'].upper()]

        if to_record in ai_entity_to_record:
            to_record = ai_entity_to_record[to_record]
        elif ai_rel['to_entity'].upper() in ai_entity_to_record:
            to_record = ai_entity_to_record[ai_rel['to_entity'].upper()]

        from_id = entity_name_map.get(from_record)
        to_id = entity_name_map.get(to_record)

        # If direct match failed, try fuzzy matching based on entity name
        if not from_id:
            from_name_lower = ai_rel['from_entity'].lower()
            for record_name, eid in entity_name_map.items():
                # Find entity with this ID
                matching_entity = next((e for e in entities if e['id'] == eid), None)
                if matching_entity:
                    entity_name_lower = matching_entity['name'].lower()
                    if from_name_lower in entity_name_lower or entity_name_lower in from_name_lower:
                        from_id = eid
                        break

        if not to_id:
            to_name_lower = ai_rel['to_entity'].lower()
            for record_name, eid in entity_name_map.items():
                matching_entity = next((e for e in entities if e['id'] == eid), None)
                if matching_entity:
                    entity_name_lower = matching_entity['name'].lower()
                    if to_name_lower in entity_name_lower or entity_name_lower in to_name_lower:
                        to_id = eid
                        break

        if from_id and to_id:
            relationships.append({
                'id': f"rel_{rel_id_counter:03d}",
                'from_entity': from_id,
                'to_entity': to_id,
                'relationship_type': ai_rel['relationship_type'],
                'cardinality': ai_rel['cardinality'],
                'business_rule': ai_rel.get('business_rule', ''),
                'join_field': ai_rel.get('join_field'),
                'confidence': ai_rel.get('confidence', 0.8),
                'sources': ['ai']
            })
            rel_id_counter += 1
        else:
            print(f"Could not map relationship: {ai_rel['from_entity']} → {ai_rel['to_entity']} (from_record={ai_rel['from_record']}, to_record={ai_rel['to_record']})")

    # Also add AST relationships if they don't duplicate AI ones
    ast_relationships = ast_data.get('relationships', [])
    for ast_rel in ast_relationships:
        # Check if not already added from AI
        from_record = ast_rel.get('from_entity', '').upper()
        to_record = ast_rel.get('to_entity', '').upper()

        already_exists = any(
            r['from_entity'] == entity_name_map.get(from_record) and
            r['to_entity'] == entity_name_map.get(to_record)
            for r in relationships
        )

        if not already_exists:
            from_id = entity_name_map.get(from_record)
            to_id = entity_name_map.get(to_record)

            if from_id and to_id:
                relationships.append({
                    'id': f"rel_{rel_id_counter:03d}",
                    'from_entity': from_id,
                    'to_entity': to_id,
                    'relationship_type': ast_rel['relationship_type'],
                    'cardinality': '1:N',
                    'join_field': ast_rel.get('join_field'),
                    'confidence': ast_rel.get('confidence', 0.7),
                    'sources': ['ast']
                })
                rel_id_counter += 1

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'summary': {
            'total_entities': len(entities),
            'total_relationships': len(relationships)
        },
        'entities': entities,
        'relationships': relationships
    }


def generate_data_lineage(regex_data, ast_data, ai_data):
    """Generate data lineage graph"""

    flows = []

    # Parse AI analysis for data lineage flows
    ai_flows = parse_ai_data_lineage(ai_data)
    flows.extend(ai_flows)

    # Extract file operations from regex data (if AI didn't catch them)
    for file_result in regex_data.get('files', []):
        file_path = file_result['file_path']
        data_structures = file_result.get('data_structures', {})

        # Check for FD entries (file definitions)
        for fd in data_structures.get('file_section', []):
            fd_name = fd.get('fd_name', 'UNKNOWN')

            # Only add if AI didn't already identify this flow
            already_exists = any(f['source_file'] == fd_name for f in flows)

            if not already_exists:
                flows.append({
                    'source_file': fd_name,
                    'source_type': 'indexed_file',
                    'transformations': [
                        {
                            'operation': 'READ',
                            'program': file_path,
                            'paragraph': 'UNKNOWN'
                        }
                    ],
                    'destination_file': 'UNKNOWN',
                    'destination_type': 'unknown'
                })

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'summary': {
            'total_flows': len(flows)
        },
        'flows': flows
    }


def generate_copybook_analysis(regex_data, ast_data):
    """Generate copybook dependency graph"""

    copybook_map = {}

    # Collect copybooks from regex analysis
    for file_result in regex_data.get('files', []):
        file_path = file_result['file_path']
        copybooks = file_result.get('data_structures', {}).get('copybooks', [])

        for cb in copybooks:
            cb_name = cb['copybook_name']
            if cb_name not in copybook_map:
                copybook_map[cb_name] = {
                    'name': cb_name,
                    'used_by': [],
                    'data_structures': []
                }
            copybook_map[cb_name]['used_by'].append(file_path)

    # Merge with AST copybook analysis
    for ast_cb in ast_data.get('copybook_analysis', []):
        cb_name = ast_cb['copybook_name']
        if cb_name in copybook_map:
            copybook_map[cb_name]['used_by'] = list(set(
                copybook_map[cb_name]['used_by'] + ast_cb.get('used_by', [])
            ))

    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'summary': {
            'total_copybooks': len(copybook_map)
        },
        'copybooks': list(copybook_map.values())
    }


def parse_ai_entities(ai_data):
    """Parse AI analysis text to extract business entities"""
    import re

    entities = []
    file_analyses = ai_data.get('file_analyses', [])

    for file_analysis in file_analyses:
        if file_analysis.get('analysis', {}).get('error'):
            continue

        analysis_text = file_analysis.get('analysis', {}).get('analysis_text', '')

        # Find all entity blocks in the "Business Entity Identification" section
        entity_pattern = r'- Entity: ([^\n]+) \(Confidence: ([\d.]+)\)\s+- COBOL Record: ([^\n]+)\s+- Suggested Table: ([^\n]+)(?:\s+- Business Purpose: ([^\n]+))?(?:\s+- Attributes: ([^\n]+))?'

        for match in re.finditer(entity_pattern, analysis_text):
            entity_name = match.group(1).strip()
            confidence = float(match.group(2))
            record_name = match.group(3).strip()
            table_name = match.group(4).strip()
            business_purpose = match.group(5).strip() if match.group(5) else ''
            attributes_str = match.group(6).strip() if match.group(6) else ''

            # Look for primary key mentions in the Data Quality Issues section
            primary_keys = []
            pk_pattern = rf'{record_name}.*?PRIMARY KEY.*?on\s+(\w+)'
            for pk_match in re.finditer(pk_pattern, analysis_text, re.IGNORECASE):
                primary_keys.append(pk_match.group(1))

            entities.append({
                'entity_name': entity_name,
                'record_name': record_name,
                'table_name': table_name,
                'business_purpose': business_purpose,
                'confidence': confidence,
                'primary_keys': primary_keys
            })

    return entities


def parse_ai_relationships(ai_data):
    """Parse AI analysis text to extract relationships"""
    import re

    relationships = []
    file_analyses = ai_data.get('file_analyses', [])

    for file_analysis in file_analyses:
        if file_analysis.get('analysis', {}).get('error'):
            continue

        analysis_text = file_analysis.get('analysis', {}).get('analysis_text', '')

        # Find relationship blocks in the "Relationship Discovery" section
        rel_pattern = r'- ([^\n]+) → ([^\n]+) \(Confidence: ([\d.]+)\)\s+- Type: ([^\n]+)\s+- Cardinality: ([^\n]+)(?:\s+- Business Rule: "([^"]+)")?(?:\s+- Evidence: ([^\n]+))?'

        for match in re.finditer(rel_pattern, analysis_text):
            from_entity = match.group(1).strip()
            to_entity = match.group(2).strip()
            confidence = float(match.group(3))
            rel_type = match.group(4).strip()
            cardinality = match.group(5).strip()
            business_rule = match.group(6).strip() if match.group(6) else ''
            evidence = match.group(7).strip() if match.group(7) else ''

            # Try to extract record names from evidence or entity names
            # Many relationships reference COBOL records in the evidence
            from_record = extract_record_name(from_entity, evidence)
            to_record = extract_record_name(to_entity, evidence)

            relationships.append({
                'from_entity': from_entity,
                'to_entity': to_entity,
                'from_record': from_record,
                'to_record': to_record,
                'relationship_type': rel_type,
                'cardinality': cardinality,
                'business_rule': business_rule,
                'confidence': confidence
            })

    return relationships


def parse_ai_data_lineage(ai_data):
    """Parse AI analysis text to extract data lineage flows"""
    import re

    flows = []
    file_analyses = ai_data.get('file_analyses', [])

    for file_analysis in file_analyses:
        if file_analysis.get('analysis', {}).get('error'):
            continue

        analysis_text = file_analysis.get('analysis', {}).get('analysis_text', '')
        file_path = file_analysis.get('file_path', 'UNKNOWN')

        # Find data lineage flow blocks
        flow_pattern = r'- Flow[^:]*: ([^\n]+)\s+- Source: ([^\n]+)(?:\s+\(([^)]+)\))?\s+- Transformation: ([^\n]+)\s+- Destination: ([^\n]+)(?:\s+\(([^)]+)\))?(?:\s+- Business Impact: ([^\n]+))?'

        for match in re.finditer(flow_pattern, analysis_text):
            flow_name = match.group(1).strip()
            source = match.group(2).strip()
            source_type = match.group(3).strip() if match.group(3) else 'unknown'
            transformation = match.group(4).strip()
            destination = match.group(5).strip()
            dest_type = match.group(6).strip() if match.group(6) else 'unknown'
            business_impact = match.group(7).strip() if match.group(7) else ''

            # Parse transformation operations
            transformations = []
            for op in transformation.split('→'):
                op = op.strip()
                if op:
                    # Determine operation type
                    if 'READ' in op.upper():
                        op_type = 'READ'
                    elif 'WRITE' in op.upper():
                        op_type = 'WRITE'
                    elif 'MOVE' in op.upper():
                        op_type = 'MOVE'
                    elif 'COMPUTE' in op.upper():
                        op_type = 'COMPUTE'
                    else:
                        op_type = 'TRANSFORM'

                    transformations.append({
                        'operation': op_type,
                        'program': file_path,
                        'description': op
                    })

            flows.append({
                'flow_name': flow_name,
                'source_file': source,
                'source_type': source_type,
                'transformations': transformations,
                'destination_file': destination,
                'destination_type': dest_type,
                'business_impact': business_impact
            })

    return flows


def extract_record_name(entity_name, evidence):
    """Extract COBOL record name from entity name or evidence text"""
    import re

    # Try to find COBOL record pattern (ALL-CAPS-WITH-HYPHENS)
    record_pattern = r'\b([A-Z][A-Z0-9-]+)\b'

    # First try evidence text
    if evidence:
        matches = re.findall(record_pattern, evidence)
        if matches:
            return matches[0]

    # Then try entity name (might already be the record name)
    matches = re.findall(record_pattern, entity_name)
    if matches:
        return matches[0]

    # Default to entity name
    return entity_name.upper().replace(' ', '-')
