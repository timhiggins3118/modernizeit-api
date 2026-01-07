"""
Dependency Mapper V2 - Static Parser Handler
Lambda: DependencyMapperV2StaticParser

Purpose: Parse COBOL source for dependencies (static analysis)

V2 Design Principles:
- Standalone architecture (NO integration with other flows)
- Independent Lambda (NO code sharing)
- Event-driven architecture
- Runs in parallel via Distributed Map
"""

import json
import boto3
import re
from typing import Dict, Any, List
from datetime import datetime, timezone

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Parse COBOL for Dependencies (Static Analysis)

    Input (from Step Functions Map - per batch):
    {
        "job_id": "dmv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "source_hash": "21a056...",
        "batch": {
            "batch_id": 0,
            "files": ["Labs/cbl/ORD001.cobol", ...]
        }
    }

    Output:
    {
        "batch_id": 0,
        "files_analyzed": 5,
        "dependencies_found": [...]
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']
        batch = event['batch']
        batch_id = batch['batch_id']
        files = batch['files']

        print(f"Static parsing batch {batch_id} with {len(files)} files")

        dependencies_found = []

        for file_path in files:
            print(f"Parsing: {file_path}")

            # Read COBOL source from S3
            source_key = f"{scout_account_id}/{application_name}/shared/uploads/{source_hash}/extracted/{file_path}"

            try:
                source_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=source_key)
                source_code = source_response['Body'].read().decode('utf-8', errors='ignore')
            except Exception as e:
                print(f"Failed to read {file_path}: {str(e)}")
                continue

            # Parse for dependencies
            program_deps = {
                'program': file_path,
                'calls': parse_calls(source_code),
                'copies': parse_copies(source_code),
                'file_io': parse_file_io(source_code),
                'database': parse_database(source_code)
            }

            dependencies_found.append(program_deps)

        # Save batch results to temp storage
        temp_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/temp/batch_analysis/batch_{batch_id}.json"

        batch_result = {
            'batch_id': batch_id,
            'files_analyzed': len(files),
            'dependencies_found': dependencies_found,
            'analyzed_at': datetime.now(timezone.utc).isoformat()
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=temp_key,
            Body=json.dumps(batch_result, indent=2),
            ContentType='application/json'
        )

        print(f"Saved batch {batch_id} results to s3://{BUCKET_NAME}/{temp_key}")

        return batch_result

    except Exception as e:
        print(f"ERROR in DependencyMapperV2StaticParser: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def parse_calls(source_code: str) -> List[Dict[str, Any]]:
    """Parse CALL/LINK/XCTL statements"""
    calls = []
    lines = source_code.split('\n')

    for line_num, line in enumerate(lines, start=1):
        # Remove comments (columns 1-6 and 73+)
        if len(line) >= 7:
            code_line = line[6:72] if len(line) >= 72 else line[6:]
        else:
            code_line = line

        # Skip comment lines
        if code_line.strip().startswith('*'):
            continue

        # Pattern: CALL 'PROGRAM' or CALL "PROGRAM" or CALL PROGRAM-NAME
        call_match = re.search(r'\bCALL\s+["\']?([A-Za-z0-9\-]+)["\']?', code_line, re.IGNORECASE)
        if call_match:
            target = call_match.group(1)
            calls.append({
                'type': 'CALL',
                'target': target,
                'line': line_num
            })

        # Pattern: EXEC CICS LINK PROGRAM('PROGRAM')
        link_match = re.search(r'LINK\s+PROGRAM\(["\']?([A-Za-z0-9\-]+)["\']?\)', code_line, re.IGNORECASE)
        if link_match:
            target = link_match.group(1)
            calls.append({
                'type': 'LINK',
                'target': target,
                'line': line_num
            })

        # Pattern: EXEC CICS XCTL PROGRAM('PROGRAM')
        xctl_match = re.search(r'XCTL\s+PROGRAM\(["\']?([A-Za-z0-9\-]+)["\']?\)', code_line, re.IGNORECASE)
        if xctl_match:
            target = xctl_match.group(1)
            calls.append({
                'type': 'XCTL',
                'target': target,
                'line': line_num
            })

    return calls


def parse_copies(source_code: str) -> List[Dict[str, Any]]:
    """Parse COPY statements"""
    copies = []
    lines = source_code.split('\n')

    for line_num, line in enumerate(lines, start=1):
        # Remove comments
        if len(line) >= 7:
            code_line = line[6:72] if len(line) >= 72 else line[6:]
        else:
            code_line = line

        # Skip comment lines
        if code_line.strip().startswith('*'):
            continue

        # Pattern: COPY COPYBOOK or COPY "COPYBOOK"
        copy_match = re.search(r'\bCOPY\s+["\']?([A-Za-z0-9\-]+)["\']?', code_line, re.IGNORECASE)
        if copy_match:
            copybook = copy_match.group(1)
            copies.append({
                'copybook': copybook,
                'line': line_num
            })

    return copies


def parse_file_io(source_code: str) -> List[Dict[str, Any]]:
    """Parse FILE-CONTROL and file operations"""
    file_ops = []
    lines = source_code.split('\n')

    # Find FILE-CONTROL section and extract file names
    files_declared = set()
    in_file_control = False

    for line_num, line in enumerate(lines, start=1):
        if len(line) >= 7:
            code_line = line[6:72] if len(line) >= 72 else line[6:]
        else:
            code_line = line

        if code_line.strip().startswith('*'):
            continue

        # Detect FILE-CONTROL section
        if 'FILE-CONTROL' in code_line.upper():
            in_file_control = True

        # Detect end of FILE-CONTROL
        if in_file_control and ('I-O-CONTROL' in code_line.upper() or 'DATA DIVISION' in code_line.upper()):
            in_file_control = False

        # Parse SELECT statements in FILE-CONTROL
        if in_file_control:
            select_match = re.search(r'SELECT\s+([A-Za-z0-9\-]+)', code_line, re.IGNORECASE)
            if select_match:
                file_name = select_match.group(1)
                files_declared.add(file_name)

    # Now find READ/WRITE/REWRITE/DELETE operations
    for line_num, line in enumerate(lines, start=1):
        if len(line) >= 7:
            code_line = line[6:72] if len(line) >= 72 else line[6:]
        else:
            code_line = line

        if code_line.strip().startswith('*'):
            continue

        # READ
        read_match = re.search(r'\bREAD\s+([A-Za-z0-9\-]+)', code_line, re.IGNORECASE)
        if read_match:
            file_name = read_match.group(1)
            file_ops.append({
                'operation': 'READ',
                'file': file_name,
                'line': line_num
            })

        # WRITE
        write_match = re.search(r'\bWRITE\s+([A-Za-z0-9\-]+)', code_line, re.IGNORECASE)
        if write_match:
            file_name = write_match.group(1)
            file_ops.append({
                'operation': 'WRITE',
                'file': file_name,
                'line': line_num
            })

        # REWRITE
        rewrite_match = re.search(r'\bREWRITE\s+([A-Za-z0-9\-]+)', code_line, re.IGNORECASE)
        if rewrite_match:
            file_name = rewrite_match.group(1)
            file_ops.append({
                'operation': 'REWRITE',
                'file': file_name,
                'line': line_num
            })

        # DELETE
        delete_match = re.search(r'\bDELETE\s+([A-Za-z0-9\-]+)', code_line, re.IGNORECASE)
        if delete_match:
            file_name = delete_match.group(1)
            file_ops.append({
                'operation': 'DELETE',
                'file': file_name,
                'line': line_num
            })

    return file_ops


def parse_database(source_code: str) -> List[Dict[str, Any]]:
    """Parse EXEC SQL statements"""
    db_ops = []
    lines = source_code.split('\n')

    for line_num, line in enumerate(lines, start=1):
        if len(line) >= 7:
            code_line = line[6:72] if len(line) >= 72 else line[6:]
        else:
            code_line = line

        if code_line.strip().startswith('*'):
            continue

        # Pattern: EXEC SQL ... END-EXEC
        if 'EXEC SQL' in code_line.upper():
            # Determine operation type
            operation = 'UNKNOWN'
            table = 'UNKNOWN'

            if 'SELECT' in code_line.upper():
                operation = 'SELECT'
                # Extract table name after FROM
                from_match = re.search(r'FROM\s+([A-Za-z0-9_]+)', code_line, re.IGNORECASE)
                if from_match:
                    table = from_match.group(1)

            elif 'INSERT' in code_line.upper():
                operation = 'INSERT'
                # Extract table name after INTO
                into_match = re.search(r'INTO\s+([A-Za-z0-9_]+)', code_line, re.IGNORECASE)
                if into_match:
                    table = into_match.group(1)

            elif 'UPDATE' in code_line.upper():
                operation = 'UPDATE'
                # Extract table name after UPDATE
                update_match = re.search(r'UPDATE\s+([A-Za-z0-9_]+)', code_line, re.IGNORECASE)
                if update_match:
                    table = update_match.group(1)

            elif 'DELETE' in code_line.upper():
                operation = 'DELETE'
                # Extract table name after FROM
                from_match = re.search(r'FROM\s+([A-Za-z0-9_]+)', code_line, re.IGNORECASE)
                if from_match:
                    table = from_match.group(1)

            db_ops.append({
                'type': 'EXEC SQL',
                'operation': operation,
                'table': table,
                'line': line_num
            })

    return db_ops
