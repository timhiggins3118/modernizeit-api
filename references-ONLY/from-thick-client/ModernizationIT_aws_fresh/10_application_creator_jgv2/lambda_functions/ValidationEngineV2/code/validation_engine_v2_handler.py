"""
Java Generation V2 - ValidationEngineV2 Handler
Lambda: ValidationEngineV2 (Docker)

Purpose: Multi-phase code validation with auto-fixing

Validation Phases:
1. TreeSitter: Syntax validation (50ms)
2. javalang: AST/structure validation (100ms)
3. Regex: Pattern checks (10ms)
4. Maven: Compilation (5s) - conditional

V2 Design Principles:
- NO HARDCODING
- Multi-phase validation (fast → thorough)
- Auto-fix with retry logic
- Docker-based (all tools available)
"""

import json
import boto3
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

# Import validation modules
from treesitter_validator import TreeSitterValidator
from javalang_validator import JavalangValidator
from regex_validator import RegexValidator
from maven_validator import MavenValidator
from error_fixer import ErrorFixer

s3_client = boto3.client('s3')

# Environment variables (NO HARDCODING)
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v2')
MAX_RETRY_ATTEMPTS = int(os.environ.get('MAX_RETRY_ATTEMPTS', '3'))
ENABLE_AI_FIXING = os.environ.get('ENABLE_AI_FIXING', 'true').lower() == 'true'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    ValidationEngineV2 - Multi-phase code validation

    Input:
    {
        "job_id": "jgv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "validate": false  # true = full Maven compile, false = fast only
    }

    Output (Success):
    {
        "statusCode": 200,
        "validation_status": "success",
        "phases_run": ["treesitter", "javalang", "regex"],
        "errors_found": 0,
        "errors_fixed": 0,
        "warnings": [],
        "execution_time_ms": 160
    }
    """
    start_time = time.time()

    try:
        print("=" * 80)
        print("VALIDATION ENGINE V2 - MULTI-PHASE CODE VALIDATION")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        validate_full = event.get('validate', False)

        print(f"Job ID: {job_id}")
        print(f"Full validation: {validate_full}")

        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v2/jobs/{job_id}"

        # Update status
        update_status(job_base, 'running', 'validating', 85, 'Running code validation...')

        # Read project metadata to get all generated files
        project_metadata = read_json(f"{job_base}/project_metadata.json")
        projects = project_metadata.get('projects', [])

        # Read generation plan for entity list
        generation_plan = read_json(f"{job_base}/generation_plan.json")
        entities = generation_plan.get('entities', [])
        # Entity names are already normalized by PrepareGenerationV2 (PascalCase)
        # DO NOT capitalize() here - it breaks names like "FinancialReports" -> "Financialreports"
        entity_names = [e.get('entity_name', e.get('name', '')) for e in entities]
        print(f"Entity names (from generation plan): {entity_names}")

        # Initialize validators
        treesitter_val = TreeSitterValidator()
        javalang_val = JavalangValidator(entity_names)
        regex_val = RegexValidator(entity_names)
        maven_val = MavenValidator()
        error_fixer = ErrorFixer(entity_names, ENABLE_AI_FIXING)

        # Track metrics
        phases_run = []
        total_errors_found = 0
        total_errors_fixed = 0
        all_warnings = []

        # Process each project
        for project in projects:
            project_base = project['base_path']
            service_name = project['service_name']

            print(f"\n=== Validating {service_name} ===")

            # Get all Java files
            java_files = list_java_files(project_base)
            print(f"Found {len(java_files)} Java files")

            # PHASE 1: TreeSitter Syntax Validation
            print("\n[Phase 1] TreeSitter Syntax Validation...")
            phase_start = time.time()

            syntax_errors = []
            for file_key in java_files:
                file_content = read_file(file_key)
                errors = treesitter_val.validate(file_content, file_key)
                syntax_errors.extend(errors)

            phase_duration = (time.time() - phase_start) * 1000
            print(f"  Completed in {phase_duration:.0f}ms - Found {len(syntax_errors)} errors")
            phases_run.append('treesitter')

            if syntax_errors:
                print(f"  Attempting to fix {len(syntax_errors)} syntax errors...")
                fixed_count = error_fixer.fix_errors(syntax_errors, 'syntax', project_base)
                total_errors_found += len(syntax_errors)
                total_errors_fixed += fixed_count
                all_warnings.extend([f"Fixed syntax error in {e['file']}" for e in syntax_errors[:fixed_count]])

            # PHASE 2: javalang AST Validation
            print("\n[Phase 2] javalang AST Validation...")
            phase_start = time.time()

            ast_errors = []
            for file_key in java_files:
                file_content = read_file(file_key)
                errors = javalang_val.validate(file_content, file_key)
                ast_errors.extend(errors)

            phase_duration = (time.time() - phase_start) * 1000
            print(f"  Completed in {phase_duration:.0f}ms - Found {len(ast_errors)} errors")
            phases_run.append('javalang')

            if ast_errors:
                print(f"  Attempting to fix {len(ast_errors)} AST errors...")
                fixed_count = error_fixer.fix_errors(ast_errors, 'ast', project_base)
                total_errors_found += len(ast_errors)
                total_errors_fixed += fixed_count
                all_warnings.extend([f"Fixed AST error in {e['file']}" for e in ast_errors[:fixed_count]])

            # PHASE 3: Regex Pattern Validation
            print("\n[Phase 3] Regex Pattern Validation...")
            phase_start = time.time()

            pattern_errors = []
            for file_key in java_files:
                file_content = read_file(file_key)
                errors = regex_val.validate(file_content, file_key)
                pattern_errors.extend(errors)

            phase_duration = (time.time() - phase_start) * 1000
            print(f"  Completed in {phase_duration:.0f}ms - Found {len(pattern_errors)} errors")
            phases_run.append('regex')

            if pattern_errors:
                print(f"  Attempting to fix {len(pattern_errors)} pattern errors...")
                fixed_count = error_fixer.fix_errors(pattern_errors, 'pattern', project_base)
                total_errors_found += len(pattern_errors)
                total_errors_fixed += fixed_count
                all_warnings.extend([f"Fixed pattern error in {e['file']}" for e in pattern_errors[:fixed_count]])

            # PHASE 4: Maven Compilation (conditional)
            if validate_full or (syntax_errors or ast_errors or pattern_errors):
                print("\n[Phase 4] Maven Compilation...")
                phase_start = time.time()

                compile_errors = maven_val.validate(project_base, job_id)

                phase_duration = (time.time() - phase_start) * 1000
                print(f"  Completed in {phase_duration:.0f}ms - Found {len(compile_errors)} errors")
                phases_run.append('maven')

                if compile_errors:
                    print(f"  Attempting to fix {len(compile_errors)} compilation errors...")
                    fixed_count = error_fixer.fix_errors(compile_errors, 'compilation', project_base, max_attempts=3)
                    total_errors_found += len(compile_errors)
                    total_errors_fixed += fixed_count

                    if fixed_count < len(compile_errors):
                        # Some errors couldn't be fixed
                        unfixed = len(compile_errors) - fixed_count
                        print(f"  WARNING: {unfixed} compilation errors remain unfixed")
                        all_warnings.append(f"{unfixed} compilation errors could not be auto-fixed")
            else:
                print("\n[Phase 4] Skipping Maven compilation (no errors in Phase 1-3)")

        # Calculate total execution time
        execution_time_ms = int((time.time() - start_time) * 1000)

        # Determine validation status
        unfixed_errors = total_errors_found - total_errors_fixed
        if unfixed_errors == 0:
            validation_status = 'success' if total_errors_found == 0 else 'success_with_warnings'
        else:
            validation_status = 'success_with_warnings'  # Still proceed, but warn

        print(f"\n{'=' * 80}")
        print(f"Validation Complete!")
        print(f"  Status: {validation_status}")
        print(f"  Phases run: {', '.join(phases_run)}")
        print(f"  Errors found: {total_errors_found}")
        print(f"  Errors fixed: {total_errors_fixed}")
        print(f"  Execution time: {execution_time_ms}ms")
        print(f"{'=' * 80}")

        # Update status
        update_status(job_base, 'running', 'validated', 90,
                     f'Validation complete: {total_errors_found} errors found, {total_errors_fixed} fixed')

        return {
            'statusCode': 200,
            'validation_status': validation_status,
            'phases_run': phases_run,
            'errors_found': total_errors_found,
            'errors_fixed': total_errors_fixed,
            'warnings': all_warnings,
            'execution_time_ms': execution_time_ms,
            'job_id': job_id
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        # Update status to failed
        try:
            update_status(job_base, 'failed', 'validation_failed', 85, f'Validation error: {str(e)}')
        except:
            pass

        return {
            'statusCode': 500,
            'validation_status': 'failed',
            'error': str(e)
        }


def list_java_files(prefix: str) -> List[str]:
    """List all Java files under S3 prefix"""
    java_files = []

    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=prefix)

        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    if key.endswith('.java'):
                        java_files.append(key)

    except Exception as e:
        print(f"WARNING: Could not list files for {prefix}: {str(e)}")

    return java_files


def read_file(s3_key: str) -> str:
    """Read file from S3"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        return response['Body'].read().decode('utf-8')
    except Exception as e:
        print(f"ERROR reading {s3_key}: {str(e)}")
        return ""


def read_json(s3_key: str) -> Dict[str, Any]:
    """Read JSON from S3"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        print(f"WARNING: Could not read {s3_key}: {str(e)}")
        return {}


def update_status(job_base: str, state: str, phase: str, progress: int, message: str):
    """Update job status"""
    try:
        status_key = f"{job_base}/status.json"
        status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
        status_data = json.loads(status_response['Body'].read())

        status_data['state'] = state
        status_data['phase'] = phase
        status_data['progress'] = progress
        status_data['message'] = message
        status_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status: {state} / {phase} ({progress}%) - {message}")
    except Exception as e:
        print(f"ERROR updating status: {str(e)}")
