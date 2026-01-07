#!/usr/bin/env python3
"""
Data Analyzer V2 - Regex Data Extractor
Extracts all data structure definitions using regex patterns
"""

import json
import boto3
import re
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    Extract data structures from COBOL files using regex
    Focuses on: PIC clauses, COMP types, FD entries, level structures, OCCURS, REDEFINES
    """

    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']

        print(f"Starting regex data extraction for job: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        extracted_path = f"{base_path}/shared/uploads/{source_hash}/extracted/"

        # Read classified catalog
        catalog_key = f"{base_path}/shared/catalogs/{source_hash}/classified_catalog.json"
        catalog_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=catalog_key)
        classified_catalog = json.loads(catalog_response['Body'].read().decode('utf-8'))

        cobol_files = classified_catalog.get('classifications', {}).get('cobol', [])

        file_results = []
        total_data_items = 0
        total_01_levels = 0
        total_copybooks = 0

        for file_path in cobol_files:
            print(f"Analyzing: {file_path}")

            # Read file
            full_key = f"{extracted_path}{file_path}"
            file_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=full_key)
            content = file_response['Body'].read().decode('utf-8', errors='ignore')

            # Extract data structures
            data_structures = extract_data_structures(content)

            total_data_items += data_structures['summary']['total_fields']
            total_01_levels += data_structures['summary']['total_01_levels']
            total_copybooks += data_structures['summary']['total_copybooks']

            file_results.append({
                'file_path': file_path,
                'data_structures': data_structures
            })

        # Save results
        output = {
            'job_id': job_id,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_files': len(cobol_files),
                'total_data_items': total_data_items,
                'total_01_levels': total_01_levels,
                'total_copybooks': total_copybooks
            },
            'files': file_results
        }

        output_key = f"{base_path}/data_analysis_v2/jobs/{job_id}/artifacts/data_structures.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(output, indent=2),
            ContentType='application/json'
        )

        print(f"Data structure extraction complete: {total_data_items} fields found")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'data_items_found': total_data_items,
                'files_analyzed': len(cobol_files),
                'output_path': f"s3://{BUCKET_NAME}/{output_key}"
            }
        }

    except Exception as e:
        print(f"Error in regex data extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }


def extract_data_structures(content):
    """Extract all data structure definitions"""

    lines = content.split('\n')

    working_storage = []
    file_section = []
    linkage_section = []
    copybooks = []

    current_section = None
    current_01_record = None

    for line in lines:
        # Strip line numbers (columns 1-6)
        if len(line) > 6:
            code_line = line[6:].rstrip()
        else:
            code_line = line.rstrip()

        # Skip comments and blank lines
        if not code_line or code_line.startswith('*'):
            continue

        # Detect sections
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

        # Extract COPY statements
        if re.search(r'\bCOPY\s+(\S+)', code_line, re.IGNORECASE):
            match = re.search(r'\bCOPY\s+(\S+)', code_line, re.IGNORECASE)
            copybook_name = match.group(1).strip('.')
            copybooks.append({
                'copybook_name': copybook_name,
                'statement': code_line.strip()
            })

        # Extract FD entries
        if current_section == 'file_section' and code_line.strip().startswith('FD'):
            fd_entry = extract_fd_entry(code_line)
            if fd_entry:
                file_section.append(fd_entry)

        # Extract level definitions (01-88)
        level_match = re.match(r'^\s*(\d{2})\s+(\S+)', code_line)
        if level_match and current_section:
            level = level_match.group(1)
            name = level_match.group(2)

            field_def = extract_field_definition(code_line, level, name)

            if level == '01':
                # Start new 01-level record
                current_01_record = {
                    'level': '01',
                    'name': name,
                    'fields': []
                }

                if current_section == 'working_storage':
                    working_storage.append(current_01_record)
                elif current_section == 'linkage_section':
                    linkage_section.append(current_01_record)

            elif current_01_record and field_def:
                # Add field to current 01-level record
                current_01_record['fields'].append(field_def)

    total_fields = sum(len(rec.get('fields', [])) for rec in working_storage + linkage_section)

    return {
        'summary': {
            'total_fields': total_fields,
            'total_01_levels': len(working_storage) + len(linkage_section),
            'total_copybooks': len(copybooks),
            'total_fd_entries': len(file_section)
        },
        'working_storage': working_storage,
        'file_section': file_section,
        'linkage_section': linkage_section,
        'copybooks': copybooks
    }


def extract_fd_entry(line):
    """Extract FD entry details"""
    match = re.search(r'FD\s+(\S+)', line, re.IGNORECASE)
    if match:
        return {
            'fd_name': match.group(1).strip('.'),
            'statement': line.strip()
        }
    return None


def extract_field_definition(line, level, name):
    """Extract field definition with PIC, USAGE, OCCURS, REDEFINES"""

    field = {
        'level': level,
        'name': name
    }

    # Extract PIC clause
    pic_match = re.search(r'\bPIC(?:TURE)?\s+IS\s+(\S+)', line, re.IGNORECASE)
    if not pic_match:
        pic_match = re.search(r'\bPIC(?:TURE)?\s+(\S+)', line, re.IGNORECASE)

    if pic_match:
        pic_clause = pic_match.group(1).strip('.')
        field['pic'] = pic_clause
        field['data_type'] = determine_data_type(pic_clause)
        field['length'] = calculate_length(pic_clause)

    # Extract USAGE/COMP
    if re.search(r'\bCOMP-3\b', line, re.IGNORECASE):
        field['usage'] = 'COMP-3'
        field['storage_type'] = 'packed_decimal'
    elif re.search(r'\bCOMP\b', line, re.IGNORECASE):
        field['usage'] = 'COMP'
        field['storage_type'] = 'binary'
    elif re.search(r'\bBINARY\b', line, re.IGNORECASE):
        field['usage'] = 'BINARY'
        field['storage_type'] = 'binary'

    # Extract OCCURS
    occurs_match = re.search(r'\bOCCURS\s+(\d+)', line, re.IGNORECASE)
    if occurs_match:
        field['occurs'] = int(occurs_match.group(1))
        field['is_array'] = True

    # Extract REDEFINES
    redefines_match = re.search(r'\bREDEFINES\s+(\S+)', line, re.IGNORECASE)
    if redefines_match:
        field['redefines'] = redefines_match.group(1).strip('.')

    # Extract VALUE
    value_match = re.search(r'\bVALUE\s+(?:IS\s+)?([\'"].*?[\'"]|\S+)', line, re.IGNORECASE)
    if value_match:
        field['value'] = value_match.group(1).strip('"\'')

    return field


def determine_data_type(pic_clause):
    """Determine data type from PIC clause"""
    if re.match(r'^[9SV\(\)]+$', pic_clause):
        return 'numeric'
    elif re.match(r'^X', pic_clause):
        return 'alphanumeric'
    elif re.match(r'^A', pic_clause):
        return 'alphabetic'
    else:
        return 'mixed'


def calculate_length(pic_clause):
    """Calculate field length from PIC clause"""
    try:
        # Handle 9(10) format
        match = re.search(r'(\w)\((\d+)\)', pic_clause)
        if match:
            return int(match.group(2))

        # Handle X(50) format
        return len(re.sub(r'[^X9A]', '', pic_clause))
    except:
        return 0
