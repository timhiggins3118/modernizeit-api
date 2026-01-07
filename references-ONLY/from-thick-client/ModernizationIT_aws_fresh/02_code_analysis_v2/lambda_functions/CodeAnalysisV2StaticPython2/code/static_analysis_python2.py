#!/usr/bin/env python3
"""
Code Analysis v2 - Python Static Analyzer
Multi-file-type parser for COBOL, JCL, Copybooks, SQL, and more
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
    Python-based static analysis for multiple file types
    """

    try:
        print(f"Python Static Analysis v2 starting: {json.dumps(event)}")

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

        # Read classified_catalog.json to know file types
        classified_catalog_key = f"{base_path}/shared/catalogs/{source_hash}/classified_catalog.json"
        catalog_response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=classified_catalog_key
        )
        classified_catalog = json.loads(catalog_response['Body'].read().decode('utf-8'))

        # Read file_catalog.json for file details
        file_catalog_key = f"{base_path}/shared/catalogs/{source_hash}/file_catalog.json"
        file_catalog_response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=file_catalog_key
        )
        file_catalog = json.loads(file_catalog_response['Body'].read().decode('utf-8'))

        extracted_path = f"{base_path}/shared/uploads/{source_hash}/extracted/"

        # Analyze each file type
        analysis_results = {
            'job_id': job_id,
            'source_hash': source_hash,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'parser_info': {
                'type': 'python_regex',
                'version': '1.0',
                'language': 'Python 3.11'
            },
            'files': [],
            'summary': {
                'total_files': 0,
                'by_type': {},
                'total_lines': 0,
                'program_calls': [],
                'copybook_references': [],
                'file_operations': []
            }
        }

        # Process each file type
        classifications = classified_catalog.get('classifications', {})

        # Analyze COBOL files
        for cobol_file in classifications.get('cobol', []):
            print(f"Analyzing COBOL: {cobol_file}")
            file_key = f"{extracted_path}{cobol_file}"
            file_analysis = analyze_cobol_file(file_key, cobol_file)
            if file_analysis:
                analysis_results['files'].append(file_analysis)

        # Analyze Copybooks
        for copybook_file in classifications.get('copybook', []):
            print(f"Analyzing Copybook: {copybook_file}")
            file_key = f"{extracted_path}{copybook_file}"
            file_analysis = analyze_copybook_file(file_key, copybook_file)
            if file_analysis:
                analysis_results['files'].append(file_analysis)

        # Analyze JCL files
        for jcl_file in classifications.get('jcl', []):
            print(f"Analyzing JCL: {jcl_file}")
            file_key = f"{extracted_path}{jcl_file}"
            file_analysis = analyze_jcl_file(file_key, jcl_file)
            if file_analysis:
                analysis_results['files'].append(file_analysis)

        # Analyze SQL files
        for sql_file in classifications.get('sql', []):
            print(f"Analyzing SQL: {sql_file}")
            file_key = f"{extracted_path}{sql_file}"
            file_analysis = analyze_sql_file(file_key, sql_file)
            if file_analysis:
                analysis_results['files'].append(file_analysis)

        # Analyze other files (config, docs, etc.)
        for file_type in ['config', 'documentation', 'unknown']:
            for other_file in classifications.get(file_type, []):
                print(f"Analyzing {file_type}: {other_file}")
                file_key = f"{extracted_path}{other_file}"
                file_analysis = analyze_generic_file(file_key, other_file, file_type)
                if file_analysis:
                    analysis_results['files'].append(file_analysis)

        # Generate summary
        analysis_results['summary']['total_files'] = len(analysis_results['files'])
        analysis_results['summary']['by_type'] = {
            'cobol': len(classifications.get('cobol', [])),
            'copybook': len(classifications.get('copybook', [])),
            'jcl': len(classifications.get('jcl', [])),
            'sql': len(classifications.get('sql', [])),
            'config': len(classifications.get('config', [])),
            'documentation': len(classifications.get('documentation', [])),
            'unknown': len(classifications.get('unknown', []))
        }

        # Calculate total lines
        analysis_results['summary']['total_lines'] = sum(
            f.get('metrics', {}).get('lines_of_code', 0) for f in analysis_results['files']
        )

        # Collect program calls and copybook references
        for file_data in analysis_results['files']:
            if 'dependencies' in file_data:
                analysis_results['summary']['program_calls'].extend(
                    file_data['dependencies'].get('called_programs', [])
                )
                analysis_results['summary']['copybook_references'].extend(
                    file_data['dependencies'].get('copybooks', [])
                )
                analysis_results['summary']['file_operations'].extend(
                    file_data['dependencies'].get('files', [])
                )

        # Deduplicate
        analysis_results['summary']['program_calls'] = list(set(analysis_results['summary']['program_calls']))
        analysis_results['summary']['copybook_references'] = list(set(analysis_results['summary']['copybook_references']))
        analysis_results['summary']['file_operations'] = list(set(analysis_results['summary']['file_operations']))

        # Save to S3
        output_key = f"{job_path}/artifacts/python_analysis.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(analysis_results, indent=2),
            ContentType='application/json'
        )

        print(f"Python analysis completed: {len(analysis_results['files'])} files analyzed")

        return {
            'statusCode': 200,
            'body': {
                'message': 'Python static analysis completed',
                'output_s3_key': output_key,
                'files_analyzed': len(analysis_results['files']),
                'total_lines': analysis_results['summary']['total_lines']
            }
        }

    except Exception as e:
        print(f"Error in Python static analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Analysis failed: {str(e)}")

def analyze_cobol_file(file_key, file_path):
    """Parse COBOL source file"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
        content = response['Body'].read().decode('utf-8', errors='ignore')
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

        # Extract COPY statements (copybook references)
        copy_matches = re.findall(r'COPY\s+([A-Z0-9-]+)', content, re.IGNORECASE)
        analysis['dependencies']['copybooks'] = list(set(copy_matches))

        # Extract CALL statements (program calls)
        call_matches = re.findall(r'CALL\s+[\'"]([A-Z0-9-]+)[\'"]', content, re.IGNORECASE)
        analysis['dependencies']['called_programs'] = list(set(call_matches))

        # Extract file names from SELECT statements
        select_matches = re.findall(r'SELECT\s+([A-Z0-9-]+)', content, re.IGNORECASE)
        analysis['dependencies']['files'] = list(set(select_matches))

        # Extract WORKING-STORAGE variables (simple regex)
        ws_section = re.search(r'WORKING-STORAGE\s+SECTION\.(.*?)(?:PROCEDURE\s+DIVISION|LINKAGE\s+SECTION|$)', content, re.DOTALL | re.IGNORECASE)
        if ws_section:
            var_matches = re.findall(r'^\s*(\d{2})\s+([A-Z0-9-]+)\s+(?:PIC|PICTURE)\s+([A-Z0-9\(\)]+)', ws_section.group(1), re.MULTILINE | re.IGNORECASE)
            for level, name, pic in var_matches[:50]:  # Limit to 50 to avoid huge lists
                analysis['variables'].append({
                    'level': level,
                    'name': name,
                    'pic': pic
                })

        # Extract paragraph names from PROCEDURE DIVISION
        proc_section = re.search(r'PROCEDURE\s+DIVISION\.(.*)', content, re.DOTALL | re.IGNORECASE)
        if proc_section:
            para_matches = re.findall(r'^\s*([A-Z0-9-]+)\.\s*$', proc_section.group(1), re.MULTILINE)
            analysis['paragraphs'] = para_matches[:100]  # Limit to 100

        # Count complexity indicators
        analysis['metrics']['perform_count'] = len(re.findall(r'\bPERFORM\b', content, re.IGNORECASE))
        analysis['metrics']['if_count'] = len(re.findall(r'\bIF\b', content, re.IGNORECASE))
        analysis['metrics']['evaluate_count'] = len(re.findall(r'\bEVALUATE\b', content, re.IGNORECASE))
        analysis['metrics']['call_count'] = len(call_matches)

        return analysis

    except Exception as e:
        print(f"Error analyzing COBOL file {file_path}: {str(e)}")
        return None

def analyze_copybook_file(file_key, file_path):
    """Parse copybook file (similar to COBOL but focus on data structures)"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
        content = response['Body'].read().decode('utf-8', errors='ignore')
        lines = content.split('\n')

        analysis = {
            'path': file_path,
            'type': 'copybook',
            'size': len(content),
            'metrics': {
                'lines_of_code': len(lines),
                'comment_lines': sum(1 for line in lines if line.strip().startswith('*'))
            },
            'records': []
        }

        # Extract record definitions
        record_matches = re.findall(r'^\s*(\d{2})\s+([A-Z0-9-]+)\s+(?:PIC|PICTURE)\s+([A-Z0-9\(\)]+)', content, re.MULTILINE | re.IGNORECASE)
        for level, name, pic in record_matches[:100]:
            analysis['records'].append({
                'level': level,
                'name': name,
                'pic': pic
            })

        return analysis

    except Exception as e:
        print(f"Error analyzing copybook {file_path}: {str(e)}")
        return None

def analyze_jcl_file(file_key, file_path):
    """Parse JCL file"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
        content = response['Body'].read().decode('utf-8', errors='ignore')
        lines = content.split('\n')

        analysis = {
            'path': file_path,
            'type': 'jcl',
            'size': len(content),
            'metrics': {
                'lines_of_code': len(lines),
                'comment_lines': sum(1 for line in lines if line.strip().startswith('//*'))
            },
            'job_info': {},
            'steps': [],
            'datasets': []
        }

        # Extract job name
        job_match = re.search(r'^//([A-Z0-9]+)\s+JOB\s', content, re.MULTILINE)
        if job_match:
            analysis['job_info']['job_name'] = job_match.group(1)

        # Extract step names and programs
        step_matches = re.findall(r'^//([A-Z0-9]+)\s+EXEC\s+(?:PGM=)?([A-Z0-9]+)', content, re.MULTILINE)
        for step_name, program in step_matches:
            analysis['steps'].append({
                'step_name': step_name,
                'program': program
            })

        # Extract DD statements (datasets)
        dd_matches = re.findall(r'^//([A-Z0-9]+)\s+DD\s+(?:DSN=)?([A-Z0-9\.\(\)]+)', content, re.MULTILINE)
        analysis['datasets'] = [{'dd_name': dd, 'dataset': dsn} for dd, dsn in dd_matches[:50]]

        return analysis

    except Exception as e:
        print(f"Error analyzing JCL file {file_path}: {str(e)}")
        return None

def analyze_sql_file(file_key, file_path):
    """Parse SQL/DDL file"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
        content = response['Body'].read().decode('utf-8', errors='ignore')
        lines = content.split('\n')

        analysis = {
            'path': file_path,
            'type': 'sql',
            'size': len(content),
            'metrics': {
                'lines_of_code': len(lines),
                'comment_lines': sum(1 for line in lines if line.strip().startswith('--'))
            },
            'objects': []
        }

        # Extract CREATE TABLE statements
        table_matches = re.findall(r'CREATE\s+TABLE\s+([A-Z0-9_\.]+)', content, re.IGNORECASE)
        for table_name in table_matches:
            analysis['objects'].append({
                'type': 'table',
                'name': table_name
            })

        # Extract CREATE INDEX statements
        index_matches = re.findall(r'CREATE\s+INDEX\s+([A-Z0-9_\.]+)', content, re.IGNORECASE)
        for index_name in index_matches:
            analysis['objects'].append({
                'type': 'index',
                'name': index_name
            })

        return analysis

    except Exception as e:
        print(f"Error analyzing SQL file {file_path}: {str(e)}")
        return None

def analyze_generic_file(file_key, file_path, file_type):
    """Parse generic file (config, doc, etc.)"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
        content = response['Body'].read().decode('utf-8', errors='ignore')
        lines = content.split('\n')

        analysis = {
            'path': file_path,
            'type': file_type,
            'size': len(content),
            'metrics': {
                'lines_of_code': len(lines)
            },
            'preview': content[:500] if len(content) > 500 else content
        }

        return analysis

    except Exception as e:
        print(f"Error analyzing generic file {file_path}: {str(e)}")
        return None

def error_response(status_code, message):
    """Return error response"""
    return {
        'statusCode': status_code,
        'error': message
    }