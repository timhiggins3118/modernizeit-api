"""
PrepareBedrockMap Lambda Handler

Purpose: Prepare file lists for BedrockAnalyzerPerFileV3 (Lambda) and Fargate routing
Input: TreeSitterAnalyzer output (job_id, scout_account_id, application_name)
Output: TWO arrays of files to analyze:
  - lambda_files: < 100 paragraphs (process with Lambda - fast & cheap)
  - fargate_files: >= 100 paragraphs (process with Fargate - no timeout)

Date: November 4, 2025 (created)
Last Updated: November 5, 2025 (added Fargate routing)
Version: V3.1
"""

import json
import logging
import os
from typing import Dict, Any, List

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# S3 client
try:
    import boto3
    s3_client = boto3.client('s3', region_name='us-east-1')
    logger.info("S3 client initialized")
except Exception as e:
    logger.warning(f"S3 client not available: {e}")
    s3_client = None

# Constants
BUCKET_NAME = 'code-transformation-v2'
SCHEMA_VERSION = 'v3.0'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for PrepareBedrockMap

    Args:
        event: Lambda event from TreeSitterAnalyzer with:
            - job_id: Job ID
            - scout_account_id: Account ID
            - application_name: Application name
            - output: S3 path to structural_context.json (optional, can be derived)

        context: Lambda context

    Returns:
        Array of files to analyze with BedrockAnalyzerPerFileV3
    """
    try:
        logger.info(f"PrepareBedrockMap started with event: {json.dumps(event, default=str)}")

        # Handle Step Functions input (body is JSON string)
        if 'body' in event and isinstance(event['body'], str):
            event_data = json.loads(event['body'])
        else:
            event_data = event

        # Validate required parameters
        required_params = ['job_id', 'scout_account_id', 'application_name']
        missing_params = [p for p in required_params if p not in event_data]

        if missing_params:
            error_msg = f"Missing required parameters: {', '.join(missing_params)}"
            logger.error(error_msg)
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'status': 'error',
                    'error': error_msg,
                    'missing_parameters': missing_params
                })
            }

        # Extract parameters
        job_id = event_data['job_id']
        scout_account_id = event_data['scout_account_id']
        application_name = event_data['application_name']
        source_hash = event_data.get('source_hash')  # Optional

        logger.info(f"Processing job: {job_id}")

        # Step 1: Read structural_context.json from S3
        structural_context_key = f"{scout_account_id}/{application_name}/code_analysis_v3/jobs/{job_id}/artifacts/structural_context.json"

        logger.info(f"Reading structural context: s3://{BUCKET_NAME}/{structural_context_key}")

        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=structural_context_key)
            structural_context = json.loads(response['Body'].read().decode('utf-8'))
        except Exception as e:
            error_msg = f"Failed to read structural_context.json: {str(e)}"
            logger.error(error_msg)
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'status': 'error',
                    'error': error_msg,
                    'error_type': 'S3_READ_FAILED'
                })
            }

        # Step 2: Extract files array and source_hash
        files = structural_context.get('files', [])
        if not source_hash:
            source_hash = structural_context.get('source_hash')

        logger.info(f"Found {len(files)} total files in structural context")

        # Step 3: Analyze ALL files (COBOL_PROGRAM, JCL, COPYBOOK, etc.)
        # Changed from COBOL_PROGRAM-only filter to analyze everything
        # Reason: JCL, COPYBOOK, and other file types also have business logic
        cobol_files = files  # Use ALL files, not just COBOL_PROGRAM

        logger.info(f"Will analyze ALL {len(cobol_files)} files (including JCL, COPYBOOK, etc.)")

        # Step 4: Write each file_analysis to S3 individually (to avoid Step Functions 256KB limit)
        # Then build TWO arrays: lambda_files (small) and fargate_files (large)
        lambda_files = []
        fargate_files = []

        # Routing threshold: files with >= 100 paragraphs go to Fargate
        PARAGRAPH_THRESHOLD = 100

        for idx, file_data in enumerate(cobol_files):
            file_name = file_data.get('file_name', 'UNKNOWN')
            file_type = file_data.get('file_type', 'UNKNOWN')
            paragraph_count = len(file_data.get('paragraphs', []))
            total_lines = file_data.get('total_lines', 0)

            # Determine routing metric based on file type
            # COBOL programs have paragraphs, JCL/COPYBOOK/etc. use line count
            if file_type == "COBOL_PROGRAM":
                routing_metric = paragraph_count
                threshold = PARAGRAPH_THRESHOLD  # 100 paragraphs
                metric_name = "paragraphs"
            else:
                # JCL, COPYBOOK, DCLGEN, CLP, etc. - use line count
                routing_metric = total_lines
                threshold = 1000  # 1000 lines ≈ 100 paragraphs complexity
                metric_name = "lines"

            # Write this file's analysis to S3
            file_analysis_key = f"{scout_account_id}/{application_name}/code_analysis_v3/jobs/{job_id}/file_analyses/{file_name}.json"

            logger.info(f"Writing file_analysis for {file_name} (type={file_type}) to S3: s3://{BUCKET_NAME}/{file_analysis_key}")

            try:
                s3_client.put_object(
                    Bucket=BUCKET_NAME,
                    Key=file_analysis_key,
                    Body=json.dumps(file_data, indent=2),
                    ContentType='application/json'
                )
            except Exception as e:
                logger.error(f"Failed to write file_analysis for {file_name}: {str(e)}")
                # Continue anyway - Lambda can still try to read structural_context.json

            # Build minimal map item (only metadata, not full file_analysis)
            map_item = {
                'job_id': job_id,
                'scout_account_id': scout_account_id,
                'application_name': application_name,
                'file_name': file_name,
                'source_hash': source_hash,
                'file_analysis_s3_key': file_analysis_key,  # S3 path to read full analysis
                'paragraph_count': paragraph_count,  # Add for visibility
                'file_type': file_type,  # Add file type for downstream processing
                'total_lines': total_lines  # Add line count for visibility
            }

            # Route based on appropriate metric (paragraphs for COBOL, lines for JCL/etc.)
            if routing_metric < threshold:
                lambda_files.append(map_item)
                logger.info(f"  → Routing to LAMBDA: {file_name} ({routing_metric} {metric_name}, type={file_type})")
            else:
                fargate_files.append(map_item)
                logger.info(f"  → Routing to FARGATE: {file_name} ({routing_metric} {metric_name}, type={file_type})")

        logger.info(f"PrepareBedrockMap completed successfully")
        logger.info(f"Total COBOL programs: {len(cobol_files)}")
        logger.info(f"  → Lambda files (< {PARAGRAPH_THRESHOLD} paragraphs): {len(lambda_files)}")
        logger.info(f"  → Fargate files (>= {PARAGRAPH_THRESHOLD} paragraphs): {len(fargate_files)}")

        # Return BOTH arrays (Step Functions will route accordingly)
        return {
            'statusCode': 200,
            'lambda_files': lambda_files,
            'fargate_files': fargate_files,
            'summary': {
                'job_id': job_id,
                'total_files': len(files),
                'cobol_programs': len(cobol_files),
                'skipped_files': len(files) - len(cobol_files),
                'lambda_files_count': len(lambda_files),
                'fargate_files_count': len(fargate_files),
                'paragraph_threshold': PARAGRAPH_THRESHOLD
            }
        }

    except Exception as e:
        logger.error(f"PrepareBedrockMap failed: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': str(e),
                'error_type': 'UNEXPECTED_ERROR'
            })
        }
