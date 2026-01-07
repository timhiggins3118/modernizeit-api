"""
Monolith Identifier V2 - Static Parser Handler
Lambda: MonolithIdentifierV2StaticParser

Purpose: Parse COBOL programs for size, complexity, and structure (parallel execution)

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
- Runs in parallel via Distributed Map
"""

import json
import boto3
import re
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Static Parser - Analyze COBOL program structure

    Input:
    {
        "job_id": "miv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "source_hash": "21a056207887...",
        "batch_id": 0,
        "files": ["Labs/cbl/PROGRAM1.cobol", ...]
    }

    Output:
    {
        "batch_id": 0,
        "programs": [...]
    }
    """
    try:
        print("=" * 80)
        print("MONOLITH IDENTIFIER V2 - STATIC PARSER")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']
        batch_id = event['batch_id']
        files = event['files']

        print(f"Batch ID: {batch_id}, Files: {len(files)}")

        programs = []

        for file_path in files:
            print(f"\nAnalyzing: {file_path}")

            try:
                # Read COBOL source
                source_key = f"{scout_account_id}/{application_name}/shared/uploads/{source_hash}/extracted/{file_path}"
                response = s3_client.get_object(Bucket=BUCKET_NAME, Key=source_key)
                source_code = response['Body'].read().decode('utf-8', errors='ignore')

                # Analyze program
                analysis = analyze_cobol_program(file_path, source_code)
                programs.append(analysis)

                print(f"  LOC: {analysis['loc']}, Complexity: {analysis['cyclomatic_complexity']}, Size: {analysis['size_category']}")

            except Exception as e:
                print(f"  ERROR analyzing {file_path}: {str(e)}")
                # Continue with other files
                programs.append({
                    'program_name': file_path,
                    'error': str(e),
                    'loc': 0,
                    'size_category': 'unknown'
                })

        # Write batch result
        batch_result = {
            'batch_id': batch_id,
            'programs': programs
        }

        batch_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/batches/static_batch_{batch_id}.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=batch_key,
            Body=json.dumps(batch_result, indent=2),
            ContentType='application/json'
        )

        print(f"\nWrote batch result: s3://{BUCKET_NAME}/{batch_key}")
        print(f"Analyzed {len(programs)} programs")

        return batch_result

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def analyze_cobol_program(file_path: str, source_code: str) -> Dict[str, Any]:
    """Analyze a single COBOL program"""

    # Split into lines
    lines = source_code.split('\n')

    # Count lines of code (skip comments and blank lines)
    loc = 0
    for line in lines:
        # COBOL comments start with * in column 7
        if len(line) > 6 and line[6] != '*' and line.strip():
            loc += 1

    # Count structural elements
    divisions = count_pattern(source_code, r'\bDIVISION\b')
    sections = count_pattern(source_code, r'\bSECTION\b')
    paragraphs = count_pattern(source_code, r'^\s*[A-Z0-9\-]+\.\s*$')

    # Estimate cyclomatic complexity
    ifs = count_pattern(source_code, r'\bIF\b')
    performs = count_pattern(source_code, r'\bPERFORM\b')
    evaluates = count_pattern(source_code, r'\bEVALUATE\b')
    cyclomatic_complexity = 1 + ifs + performs + evaluates

    # Count dependencies
    call_statements = count_pattern(source_code, r'\bCALL\b')
    copy_statements = count_pattern(source_code, r'\bCOPY\b')
    file_operations = count_pattern(source_code, r'\bSELECT\b')
    database_operations = count_pattern(source_code, r'\bEXEC\s+SQL\b')

    # Extract copybook names
    copybooks_used = extract_copybooks(source_code)

    # Classify size
    if loc < 500:
        size_category = 'small'
    elif loc < 2000:
        size_category = 'medium'
    elif loc < 5000:
        size_category = 'large'
    else:
        size_category = 'god_program'

    return {
        'program_name': file_path,
        'loc': loc,
        'size_category': size_category,
        'divisions': divisions,
        'sections': sections,
        'paragraphs': paragraphs,
        'cyclomatic_complexity': cyclomatic_complexity,
        'call_statements': call_statements,
        'copy_statements': copy_statements,
        'file_operations': file_operations,
        'database_operations': database_operations,
        'copybooks_used': copybooks_used
    }


def count_pattern(text: str, pattern: str) -> int:
    """Count occurrences of a regex pattern"""
    return len(re.findall(pattern, text, re.IGNORECASE | re.MULTILINE))


def extract_copybooks(source_code: str) -> List[str]:
    """Extract copybook names from COPY statements"""
    copybooks = []
    pattern = r'\bCOPY\s+([A-Z0-9\-]+)'
    matches = re.findall(pattern, source_code, re.IGNORECASE)
    return list(set(matches))  # Unique copybooks
