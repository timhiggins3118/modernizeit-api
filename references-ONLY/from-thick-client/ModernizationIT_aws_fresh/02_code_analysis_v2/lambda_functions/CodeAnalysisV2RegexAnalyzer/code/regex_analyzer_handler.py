#!/usr/bin/env python3
"""
Code Analysis V2 - Regex-Based Static Analyzer
Lambda handler for fast regex-based COBOL analysis
"""

import json
import boto3
import re
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

# Constants
BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    Regex-based static analysis for COBOL files
    Reads from shared/uploads/{source_hash}/extracted/
    Writes to code_analysis_v2/jobs/{job_id}/artifacts/regex_analysis.json
    """

    try:
        print(f"Regex Analyzer starting: {json.dumps(event)}")

        # Parse input
        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')
        source_hash = event.get('source_hash')

        if not all([job_id, scout_account_id, application_name, source_hash]):
            return error_response(400, 'Missing required fields')

        base_path = f"{scout_account_id}/{application_name}"
        job_path = f"{base_path}/code_analysis_v2/jobs/{job_id}"

        print(f"Analyzing job: {job_id}")

        # Read classified_catalog.json to know which files are COBOL
        classified_catalog_key = f"{base_path}/shared/catalogs/{source_hash}/classified_catalog.json"
        catalog_response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=classified_catalog_key
        )
        classified_catalog = json.loads(catalog_response['Body'].read().decode('utf-8'))

        # Get list of COBOL files to analyze
        cobol_files = classified_catalog.get('classifications', {}).get('cobol', [])
        print(f"Found {len(cobol_files)} COBOL files to analyze")

        if len(cobol_files) == 0:
            return error_response(400, 'No COBOL files found in catalog')

        # Analyze each COBOL file
        file_results = []
        total_loc = 0
        total_smells = 0

        for file_path in cobol_files:
            file_key = f"{base_path}/shared/uploads/{source_hash}/extracted/{file_path}"

            print(f"Analyzing: {file_path}")

            try:
                # Read COBOL file content
                file_response = s3_client.get_object(
                    Bucket=BUCKET_NAME,
                    Key=file_key
                )
                content = file_response['Body'].read().decode('utf-8', errors='ignore')

                # Analyze the file
                analysis = analyze_cobol_file(file_path, content)
                file_results.append(analysis)

                total_loc += analysis['metrics']['lines_of_code']
                total_smells += len(analysis['code_smells'])

            except ClientError as e:
                print(f"Error reading file {file_path}: {str(e)}")
                # Continue with other files
                continue

        # Create summary
        summary = {
            'total_files': len(file_results),
            'total_loc': total_loc,
            'total_code_smells': total_smells,
            'total_programs': len([f for f in file_results if f.get('program_id')]),
            'average_complexity': round(sum([f['code_quality']['cyclomatic_complexity'] for f in file_results]) / max(len(file_results), 1), 2)
        }

        # Build final output
        regex_analysis = {
            'analyzer': 'regex',
            'job_id': job_id,
            'source_hash': source_hash,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': summary,
            'files': file_results
        }

        # Write results to S3
        output_key = f"{job_path}/artifacts/regex_analysis.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(regex_analysis, indent=2),
            ContentType='application/json'
        )

        print(f"Regex analysis complete. Analyzed {len(file_results)} files with {total_smells} code smells found.")
        print(f"Output written to: {output_key}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'completed',
                'job_id': job_id,
                'files_analyzed': len(file_results),
                'total_code_smells': total_smells,
                'output_path': f"s3://{BUCKET_NAME}/{output_key}"
            })
        }

    except Exception as e:
        print(f"Error in regex analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Analysis failed: {str(e)}")


def analyze_cobol_file(file_path, content):
    """
    Analyze a single COBOL file using regex patterns
    Returns comprehensive analysis with code smells, metrics, quality scores
    """

    lines = content.split('\n')

    analysis = {
        'path': file_path,
        'type': 'cobol',
        'size': len(content),
        'metrics': {
            'lines_of_code': len(lines),
            'comment_lines': sum(1 for line in lines if line.strip().startswith('*')),
            'blank_lines': sum(1 for line in lines if not line.strip())
        },
        'structure': {},
        'dependencies': {
            'copybooks': [],
            'called_programs': [],
            'files': []
        },
        'variables': [],
        'paragraphs': []
    }

    # Extract PROGRAM-ID
    program_id_match = re.search(r'PROGRAM-ID\.\s+([A-Z0-9-]+)', content, re.IGNORECASE)
    if program_id_match:
        analysis['program_id'] = program_id_match.group(1)

    # Extract AUTHOR
    author_match = re.search(r'AUTHOR\.\s+(.+)', content, re.IGNORECASE)
    if author_match:
        analysis['author'] = author_match.group(1).strip()

    # Detect divisions
    analysis['structure']['has_identification'] = bool(re.search(r'IDENTIFICATION\s+DIVISION', content, re.IGNORECASE))
    analysis['structure']['has_environment'] = bool(re.search(r'ENVIRONMENT\s+DIVISION', content, re.IGNORECASE))
    analysis['structure']['has_data'] = bool(re.search(r'DATA\s+DIVISION', content, re.IGNORECASE))
    analysis['structure']['has_procedure'] = bool(re.search(r'PROCEDURE\s+DIVISION', content, re.IGNORECASE))

    # Extract COPY statements
    copy_matches = re.findall(r'COPY\s+([A-Z0-9-]+)', content, re.IGNORECASE)
    analysis['dependencies']['copybooks'] = list(set(copy_matches))

    # Extract CALL statements
    call_matches = re.findall(r'CALL\s+[\'"]([A-Z0-9-]+)[\'"]', content, re.IGNORECASE)
    analysis['dependencies']['called_programs'] = list(set(call_matches))

    # Extract SELECT file names
    select_matches = re.findall(r'SELECT\s+([A-Z0-9-]+)', content, re.IGNORECASE)
    analysis['dependencies']['files'] = list(set(select_matches))

    # Extract WORKING-STORAGE variables
    ws_section = re.search(r'WORKING-STORAGE\s+SECTION\.(.*?)(?:PROCEDURE\s+DIVISION|LINKAGE\s+SECTION|$)', content, re.DOTALL | re.IGNORECASE)
    if ws_section:
        var_matches = re.findall(r'^\s*(\d{2})\s+([A-Z0-9-]+)\s+(?:PIC|PICTURE)\s+([A-Z0-9\(\)]+)', ws_section.group(1), re.MULTILINE | re.IGNORECASE)
        for level, name, pic in var_matches[:50]:
            analysis['variables'].append({
                'level': level,
                'name': name,
                'pic': pic
            })

    # Extract paragraphs
    proc_section = re.search(r'PROCEDURE\s+DIVISION\.(.*)', content, re.DOTALL | re.IGNORECASE)
    if proc_section:
        para_matches = re.findall(r'^\s*([A-Z0-9-]+)\.\s*$', proc_section.group(1), re.MULTILINE)
        analysis['paragraphs'] = para_matches[:100]

    # Count complexity indicators
    analysis['metrics']['perform_count'] = len(re.findall(r'\bPERFORM\b', content, re.IGNORECASE))
    analysis['metrics']['if_count'] = len(re.findall(r'\bIF\b', content, re.IGNORECASE))
    analysis['metrics']['evaluate_count'] = len(re.findall(r'\bEVALUATE\b', content, re.IGNORECASE))
    analysis['metrics']['call_count'] = len(call_matches)

    # === CODE QUALITY ANALYSIS ===
    analysis['code_quality'] = {}

    perform_with_until = len(re.findall(r'\bPERFORM\s+.*?\bUNTIL\b', content, re.IGNORECASE | re.DOTALL))
    perform_with_varying = len(re.findall(r'\bPERFORM\s+.*?\bVARYING\b', content, re.IGNORECASE | re.DOTALL))
    cyclomatic_complexity = 1 + analysis['metrics']['if_count'] + analysis['metrics']['evaluate_count'] + perform_with_until + perform_with_varying
    analysis['code_quality']['cyclomatic_complexity'] = cyclomatic_complexity

    loc = analysis['metrics']['lines_of_code']
    comment_ratio = analysis['metrics']['comment_lines'] / max(1, len(lines))
    maintainability = max(0, min(100, 100 - (cyclomatic_complexity * 2) - (loc / 10) + (comment_ratio * 20)))
    analysis['code_quality']['maintainability_index'] = round(maintainability, 2)

    tech_debt_ratio = (loc - analysis['metrics']['comment_lines']) / max(1, cyclomatic_complexity * 25)
    analysis['code_quality']['technical_debt_ratio'] = round(tech_debt_ratio, 2)

    # === CODE SMELLS ===
    analysis['code_smells'] = []

    # 1. Magic Numbers (exclude PIC clauses and LEVEL numbers)
    magic_numbers = re.findall(r'\b(?<!LEVEL\s)(?<!PIC\s)(?<!PICTURE\s)(?<!-)\d{2,}\b(?!\s*PIC)', content, re.IGNORECASE)
    if len(magic_numbers) > 10:
        analysis['code_smells'].append({
            'type': 'Magic Numbers',
            'severity': 'MEDIUM',
            'count': len(magic_numbers),
            'description': f'Found {len(magic_numbers)} hardcoded numeric literals in code',
            'recommendation': 'Replace with named constants in WORKING-STORAGE'
        })

    # 2. Missing File Status Handling
    open_count = len(re.findall(r'\bOPEN\s+(INPUT|OUTPUT)', content, re.IGNORECASE))
    read_count = len(re.findall(r'\bREAD\b', content, re.IGNORECASE))
    write_count = len(re.findall(r'\bWRITE\b', content, re.IGNORECASE))
    file_status_count = len(re.findall(r'\bFILE\s+STATUS\b', content, re.IGNORECASE))
    io_operations = open_count + read_count + write_count

    if io_operations > 0 and file_status_count == 0:
        analysis['code_smells'].append({
            'type': 'Missing File Status Handling',
            'severity': 'HIGH',
            'description': f'{io_operations} file operations without FILE STATUS checks',
            'recommendation': 'Add FILE STATUS clause and check after each I/O operation'
        })

    # 3. Dead Code (unreferenced paragraphs)
    referenced_paras = set(re.findall(r'\bPERFORM\s+([A-Z0-9-]+)', content, re.IGNORECASE))
    defined_paras = set(analysis['paragraphs'])
    dead_paras = defined_paras - referenced_paras
    if dead_paras:
        analysis['code_smells'].append({
            'type': 'Dead Code (Unreferenced Paragraphs)',
            'severity': 'LOW',
            'count': len(dead_paras),
            'paragraphs': list(dead_paras)[:5],
            'description': f'{len(dead_paras)} paragraphs defined but never called',
            'recommendation': 'Remove unused paragraphs or verify if they should be called'
        })

    # === ANTI-PATTERNS ===
    analysis['anti_patterns'] = []

    # === QUALITY METRICS ===
    analysis['quality_metrics'] = {
        'code_to_comment_ratio': round(loc / max(1, analysis['metrics']['comment_lines']), 2),
        'average_paragraph_complexity': round(cyclomatic_complexity / max(1, len(analysis['paragraphs'])), 2),
        'coupling': {
            'external_calls': len(analysis['dependencies']['called_programs']),
            'copybooks': len(analysis['dependencies']['copybooks']),
            'files': len(analysis['dependencies']['files'])
        },
        'cohesion_score': round(max(0, 100 - (len(analysis['dependencies']['called_programs']) * 10)), 2),
        'testability_score': round(max(0, 100 - (cyclomatic_complexity * 3)), 2),
        'readability_score': round(comment_ratio * 100, 2)
    }

    return analysis


def error_response(status_code, message):
    """Return error response"""
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'error': message
        })
    }
