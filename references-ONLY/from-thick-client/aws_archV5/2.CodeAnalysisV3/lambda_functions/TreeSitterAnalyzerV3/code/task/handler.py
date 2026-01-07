"""
CodeAnalysisV3 TreeSitterAnalyzer Lambda Handler

Purpose: Parse COBOL files using Tree-sitter, extract paragraphs, generate synthetic units if needed
Input: job_id, scout_account_id, application_name, source_hash
Output: structural_context.json to S3

Date: November 3, 2025
Version: V3.0
"""

import json
import boto3
import logging
import os
import traceback
from typing import Dict, Any, List
from datetime import datetime

from encoding_detector import detect_encoding
from cobol_parser import parse_cobol_file
from synthetic_unit_generator import generate_synthetic_units
from statement_tracer import add_statement_traceability

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3_client = boto3.client('s3')

# Constants
BUCKET_NAME = 'code-transformation-v2'
SCHEMA_VERSION = 'v3.0'


def classify_error(exception: Exception) -> str:
    """
    Classify exception into error type category

    Args:
        exception: Exception object

    Returns:
        Error type string
    """
    error_str = str(exception).lower()

    if 'encoding' in error_str or 'decode' in error_str or 'codec' in error_str:
        return 'ENCODING_FAILED'
    elif 'parse' in error_str or 'syntax' in error_str or 'tree-sitter' in error_str:
        return 'PARSING_FAILED'
    elif 'empty' in error_str or 'zero' in error_str:
        return 'EMPTY_FILE'
    elif 'size' in error_str or 'too large' in error_str:
        return 'FILE_TOO_LARGE'
    elif 'format' in error_str or 'invalid' in error_str:
        return 'INVALID_FORMAT'
    else:
        return 'UNEXPECTED_ERROR'


def write_failure_log(
    job_id: str,
    scout_account_id: str,
    application_name: str,
    failure_entry: Dict
) -> None:
    """
    Write or append to failures.json in S3

    Args:
        job_id: Job ID
        scout_account_id: Account ID
        application_name: Application name
        failure_entry: Failure details dictionary
    """
    key = f"{scout_account_id}/{application_name}/code_analysis_v3/jobs/{job_id}/failures.json"

    try:
        # Try to read existing failures.json
        obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
        failures_data = json.loads(obj['Body'].read())
        failures_data['failures'].append(failure_entry)
        failures_data['failed_files'] = len(failures_data['failures'])

    except s3_client.exceptions.NoSuchKey:
        # First failure - create new file
        failures_data = {
            'schema_version': SCHEMA_VERSION,
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'total_files': 0,  # Will be updated at end
            'failed_files': 1,
            'failures': [failure_entry]
        }

    # Write back to S3
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=json.dumps(failures_data, indent=2),
        ContentType='application/json'
    )

    logger.info(f"Logged failure for {failure_entry['file_name']} to s3://{BUCKET_NAME}/{key}")


def update_failure_summary(
    job_id: str,
    scout_account_id: str,
    application_name: str,
    total_files: int
) -> None:
    """
    Update total_files count in failures.json

    Args:
        job_id: Job ID
        scout_account_id: Account ID
        application_name: Application name
        total_files: Total number of files processed
    """
    key = f"{scout_account_id}/{application_name}/code_analysis_v3/jobs/{job_id}/failures.json"

    try:
        obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
        failures_data = json.loads(obj['Body'].read())
        failures_data['total_files'] = total_files

        # Write back
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=json.dumps(failures_data, indent=2),
            ContentType='application/json'
        )
    except s3_client.exceptions.NoSuchKey:
        # No failures - nothing to update
        pass


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for TreeSitterAnalyzer V3

    Args:
        event: Lambda event with job_id, scout_account_id, application_name, source_hash
        context: Lambda context

    Returns:
        Success/failure response
    """
    try:
        logger.info(f"TreeSitterAnalyzer V3 started with event: {json.dumps(event)}")

        # Extract parameters
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']

        logger.info(f"Processing job: {job_id}")

        # Step 1: Get file catalog
        file_catalog = get_file_catalog(scout_account_id, application_name, source_hash)

        # Step 2: Process each file
        all_files_analysis = []
        stats = {
            'total_files': 0,
            'successful_files': 0,
            'failed_files': 0,
            'files_with_paragraphs': 0,
            'files_with_synthetic_units': 0,
            'total_paragraphs': 0,
            'total_synthetic_units': 0,
            'encoding_detections': {}
        }

        for file_info in file_catalog:
            file_path = file_info['path']
            file_name = os.path.basename(file_path)  # Extract filename from path
            stats['total_files'] += 1

            logger.info(f"Processing file {stats['total_files']}/{len(file_catalog)}: {file_name}")

            try:
                # Get file content from S3
                file_content = get_file_from_s3(
                    scout_account_id,
                    application_name,
                    source_hash,
                    file_path
                )

                # Detect encoding
                detected_encoding = detect_encoding(file_content)
                stats['encoding_detections'][file_name] = detected_encoding

                # Decode content
                try:
                    decoded_content = file_content.decode(detected_encoding)
                except Exception as e:
                    logger.warning(f"Failed to decode {file_name} with {detected_encoding}, trying latin-1")
                    decoded_content = file_content.decode('latin-1', errors='replace')
                    detected_encoding = 'latin-1 (fallback)'

                # Parse COBOL file
                parse_result = parse_cobol_file(file_name, decoded_content)

                # Check if we found paragraphs
                if parse_result['paragraph_count'] == 0:
                    logger.warning(f"No paragraphs found in {file_name}, generating synthetic units")

                    # Generate synthetic units
                    synthetic_units = generate_synthetic_units(file_name, decoded_content, parse_result)
                    parse_result['units'] = synthetic_units
                    parse_result['unit_type'] = 'synthetic'

                    stats['files_with_synthetic_units'] += 1
                    stats['total_synthetic_units'] += len(synthetic_units)
                else:
                    parse_result['unit_type'] = 'paragraph'
                    stats['files_with_paragraphs'] += 1
                    stats['total_paragraphs'] += parse_result['paragraph_count']

                # Add statement-level traceability
                parse_result = add_statement_traceability(parse_result)

                # For JCL and non-COBOL files, include raw content for AI analysis
                # (COBOL programs already have detailed paragraph analysis, don't need raw content)
                if parse_result.get('file_type') in ['JCL', 'COPYBOOK', 'CLP', 'DCLGEN', 'UNKNOWN']:
                    # Truncate to 50000 chars to avoid bloating file_analysis.json
                    max_content_length = 50000
                    if len(decoded_content) > max_content_length:
                        parse_result['raw_content'] = decoded_content[:max_content_length] + "\n\n[... truncated ...]"
                        parse_result['raw_content_truncated'] = True
                    else:
                        parse_result['raw_content'] = decoded_content
                        parse_result['raw_content_truncated'] = False

                # Add to results
                all_files_analysis.append(parse_result)
                stats['successful_files'] += 1

                # Write individual file analysis to S3
                write_individual_file_analysis(
                    scout_account_id,
                    application_name,
                    job_id,
                    parse_result
                )

                logger.info(f"✅ Successfully processed {file_name}")

            except Exception as e:
                # File processing failed - log to failures.json
                logger.error(f"❌ Failed to process {file_name}: {str(e)}")
                stats['failed_files'] += 1

                failure_entry = {
                    'file_name': file_name,
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'error_type': classify_error(e),
                    'error_message': str(e),
                    'phase': 'treesitter_analyzer',
                    'details': {
                        'file_path': file_path,
                        'file_size_bytes': len(file_content) if 'file_content' in locals() else 0,
                        'encoding_detected': stats['encoding_detections'].get(file_name, 'unknown'),
                        'stack_trace': traceback.format_exc()
                    }
                }

                # Write failure to S3
                write_failure_log(
                    job_id,
                    scout_account_id,
                    application_name,
                    failure_entry
                )

                # Continue processing next file (don't stop workflow)

        # Step 3: Build structural_context.json
        structural_context = build_structural_context(
            job_id,
            scout_account_id,
            application_name,
            source_hash,
            all_files_analysis,
            stats
        )

        # Step 4: Write to S3
        write_structural_context_to_s3(
            scout_account_id,
            application_name,
            job_id,
            structural_context
        )

        # Step 5: Update failure summary if there were failures
        if stats['failed_files'] > 0:
            update_failure_summary(
                job_id,
                scout_account_id,
                application_name,
                stats['total_files']
            )

        # Determine overall status
        if stats['failed_files'] == 0:
            status = 'success'
            message = f"All {stats['total_files']} files processed successfully"
        elif stats['successful_files'] == 0:
            status = 'failed'
            message = f"All {stats['total_files']} files failed to process. See failures.json for details."
        else:
            status = 'partial_success'
            message = f"{stats['successful_files']} of {stats['total_files']} files processed successfully. {stats['failed_files']} failed (see failures.json)."

        logger.info(f"TreeSitterAnalyzer V3 completed. Status: {status}. Stats: {json.dumps(stats)}")

        response_body = {
            'status': status,
            'message': message,
            'job_id': job_id,
            'total_files': stats['total_files'],
            'successful_files': stats['successful_files'],
            'failed_files': stats['failed_files'],
            'paragraphs_found': stats['total_paragraphs'],
            'synthetic_units_generated': stats['total_synthetic_units'],
            'output': f"s3://{BUCKET_NAME}/{scout_account_id}/{application_name}/code_analysis_v3/jobs/{job_id}/artifacts/structural_context.json"
        }

        # Add failures URL if there were failures
        if stats['failed_files'] > 0:
            response_body['failures_url'] = f"s3://{BUCKET_NAME}/{scout_account_id}/{application_name}/code_analysis_v3/jobs/{job_id}/failures.json"

        return {
            'statusCode': 200,
            'body': json.dumps(response_body)
        }

    except Exception as e:
        logger.error(f"TreeSitterAnalyzer V3 failed: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': str(e)
            })
        }


def get_file_catalog(scout_account_id: str, application_name: str, source_hash: str) -> List[Dict]:
    """Get file catalog from S3"""
    catalog_key = f"{scout_account_id}/{application_name}/shared/catalogs/{source_hash}/file_catalog.json"

    logger.info(f"Reading file catalog: s3://{BUCKET_NAME}/{catalog_key}")

    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=catalog_key)
    catalog = json.loads(response['Body'].read().decode('utf-8'))

    return catalog.get('files', [])


def get_file_from_s3(scout_account_id: str, application_name: str, source_hash: str, file_path: str) -> bytes:
    """Get file content from S3"""
    file_key = f"{scout_account_id}/{application_name}/shared/uploads/{source_hash}/extracted/{file_path}"

    logger.info(f"Reading file: s3://{BUCKET_NAME}/{file_key}")

    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
    return response['Body'].read()


def build_structural_context(
    job_id: str,
    scout_account_id: str,
    application_name: str,
    source_hash: str,
    all_files_analysis: List[Dict],
    stats: Dict
) -> Dict:
    """Build the structural_context.json output"""

    return {
        'schema_version': SCHEMA_VERSION,
        'job_id': job_id,
        'scout_account_id': scout_account_id,
        'application_name': application_name,
        'source_hash': source_hash,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'analyzer': 'TreeSitterAnalyzer',
        'version': 'v3.0',
        'statistics': {
            'total_files': stats['total_files'],
            'successful_files': stats['successful_files'],
            'failed_files': stats['failed_files'],
            'files_with_paragraphs': stats['files_with_paragraphs'],
            'files_with_synthetic_units': stats['files_with_synthetic_units'],
            'total_paragraphs': stats['total_paragraphs'],
            'total_synthetic_units': stats['total_synthetic_units'],
            'paragraph_zero_rate': round(stats['files_with_synthetic_units'] / max(stats['successful_files'], 1), 3),
            'encoding_detections': stats['encoding_detections']
        },
        'files': all_files_analysis
    }


def write_individual_file_analysis(
    scout_account_id: str,
    application_name: str,
    job_id: str,
    file_analysis: Dict
) -> None:
    """
    Write individual file analysis to S3

    Args:
        scout_account_id: Account ID
        application_name: Application name
        job_id: Job ID
        file_analysis: Single file's analysis result
    """
    filename = file_analysis.get('file_name', 'unknown')

    # Write to file_analyses/{filename}.json
    output_key = f"{scout_account_id}/{application_name}/code_analysis_v3/jobs/{job_id}/file_analyses/{filename}.json"

    logger.info(f"Writing individual file analysis: {filename}")

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body=json.dumps(file_analysis, indent=2),
        ContentType='application/json'
    )


def write_structural_context_to_s3(
    scout_account_id: str,
    application_name: str,
    job_id: str,
    structural_context: Dict
) -> None:
    """Write structural_context.json to S3"""

    output_key = f"{scout_account_id}/{application_name}/code_analysis_v3/jobs/{job_id}/artifacts/structural_context.json"

    logger.info(f"Writing structural context: s3://{BUCKET_NAME}/{output_key}")

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body=json.dumps(structural_context, indent=2),
        ContentType='application/json'
    )

    logger.info(f"Structural context written successfully")
