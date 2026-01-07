"""
BedrockAnalyzerPerFile Lambda Handler

Purpose: AI-powered business logic analysis for individual COBOL files
Input: ONE file_analysis.json (from TreeSitterAnalyzer)
Output: ONE ai_analysis.json (AI insights for that file)

Date: November 3, 2025
Version: V3.0
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

from token_estimator import estimate_tokens
from batch_strategy import determine_batch_strategy, create_paragraph_batches
from prompt_templates import (
    build_program_level_prompt,
    build_full_file_prompt,
    build_batch_prompt,
    build_jcl_program_level_prompt,
    build_generic_file_prompt
)
from bedrock_client import invoke_bedrock, parse_bedrock_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants
SCHEMA_VERSION = 'v3.0'
MAX_CONTEXT_CHARS = 5000
BUCKET_NAME = 'code-transformation-v2'

# Import boto3 and initialize S3 client
import boto3
s3_client = boto3.client('s3', region_name='us-east-1')
logger.info("S3 client initialized for AI analysis writing")


def read_user_context_file(scout_account_id: str, application_name: str, source_hash: str) -> Optional[str]:
    """
    Read user-provided .md context file from S3

    Args:
        scout_account_id: Account ID
        application_name: Application name
        source_hash: Source hash from upload

    Returns:
        Context file content (truncated to 5000 chars) or None
    """
    if not s3_client:
        logger.info("S3 client not available - skipping context file")
        return None

    if not source_hash:
        logger.info("No source_hash provided - skipping context file")
        return None

    try:
        bucket = 'code-transformation-v2'
        prefix = f"{scout_account_id}/{application_name}/shared/uploads/{source_hash}/extracted/"

        logger.info(f"Looking for .md context file in s3://{bucket}/{prefix}")

        # List objects in extracted folder
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=100
        )

        if 'Contents' not in response:
            logger.info("No files found in extracted folder")
            return None

        # Find first .md file
        md_files = [obj['Key'] for obj in response['Contents'] if obj['Key'].endswith('.md')]

        if not md_files:
            logger.info("No .md context file found")
            return None

        # Read first .md file
        md_key = md_files[0]
        logger.info(f"Found context file: {md_key}")

        obj = s3_client.get_object(Bucket=bucket, Key=md_key)
        content = obj['Body'].read().decode('utf-8', errors='replace')

        # Truncate if too long
        if len(content) > MAX_CONTEXT_CHARS:
            logger.warning(f"Context file truncated from {len(content)} to {MAX_CONTEXT_CHARS} chars")
            content = content[:MAX_CONTEXT_CHARS] + "\n\n[... truncated ...]"

        logger.info(f"Loaded context file ({len(content)} chars): {os.path.basename(md_key)}")
        return content

    except Exception as e:
        logger.warning(f"Failed to read context file: {str(e)}")
        return None


def write_ai_analysis_to_s3(
    scout_account_id: str,
    application_name: str,
    job_id: str,
    file_name: str,
    ai_analysis: Dict
) -> None:
    """
    Write AI analysis to S3

    Args:
        scout_account_id: Account ID
        application_name: Application name
        job_id: Job ID
        file_name: File name (e.g., CMCMCL00.CBL)
        ai_analysis: AI analysis dictionary
    """
    # Remove .json extension if present in filename
    base_filename = file_name.replace('.json', '') if file_name.endswith('.json') else file_name

    # Write to ai_analyses/{filename}_ai_analysis.json
    output_key = f"{scout_account_id}/{application_name}/code_analysis_v3/jobs/{job_id}/ai_analyses/{base_filename}_ai_analysis.json"

    logger.info(f"Writing AI analysis to S3: s3://{BUCKET_NAME}/{output_key}")

    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=output_key,
        Body=json.dumps(ai_analysis, indent=2),
        ContentType='application/json'
    )

    logger.info(f"✅ AI analysis written successfully for {file_name}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for BedrockAnalyzerPerFile

    Args:
        event: Lambda event with:
            - job_id: Job ID
            - scout_account_id: Account ID
            - application_name: Application name
            - file_name: COBOL file name
            - file_analysis: File analysis dictionary (or path to S3 file)

        context: Lambda context

    Returns:
        Success/failure response with AI analysis output
    """
    file_name = None
    try:
        logger.info(f"BedrockAnalyzerPerFile started with event: {json.dumps(event, default=str)}")

        # Validate required parameters
        required_params = ['job_id', 'scout_account_id', 'application_name', 'file_name']
        missing_params = [p for p in required_params if p not in event]

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
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        file_name = event['file_name']
        source_hash = event.get('source_hash')  # Optional - for context file reading

        # Read user context file (.md) if available
        user_context = read_user_context_file(scout_account_id, application_name, source_hash)
        if user_context:
            logger.info(f"User context loaded ({len(user_context)} chars) - will be injected into prompts")
        else:
            logger.info("No user context file - proceeding without additional context")

        # Get file analysis (either directly or from S3)
        file_analysis = event.get('file_analysis')

        if not file_analysis:
            # Check if file_analysis_s3_key is provided (V3 workflow with PrepareBedrockMap)
            file_analysis_s3_key = event.get('file_analysis_s3_key')

            if file_analysis_s3_key:
                logger.info(f"Reading file_analysis from S3: s3://{BUCKET_NAME}/{file_analysis_s3_key}")
                try:
                    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_analysis_s3_key)
                    file_analysis = json.loads(response['Body'].read().decode('utf-8'))
                    logger.info(f"Successfully loaded file_analysis from S3")
                except Exception as e:
                    error_msg = f"Failed to read file_analysis from S3: {str(e)}"
                    logger.error(error_msg)
                    return {
                        'statusCode': 500,
                        'body': json.dumps({
                            'status': 'error',
                            'file_name': file_name,
                            'error': error_msg,
                            'error_type': 'S3_READ_FAILED'
                        })
                    }
            else:
                error_msg = "Neither file_analysis nor file_analysis_s3_key provided in event"
                logger.error(error_msg)
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'status': 'error',
                        'file_name': file_name,
                        'error': error_msg
                    })
                }

        logger.info(f"Processing file: {file_name}")

        # Get file type to determine analysis approach
        file_type = file_analysis.get('file_type', 'UNKNOWN')
        logger.info(f"Analyzing {file_name} (type={file_type})")

        # Step 1: Determine batching strategy (only for COBOL_PROGRAM with paragraphs)
        strategy = None
        if file_type == 'COBOL_PROGRAM':
            try:
                strategy = determine_batch_strategy(file_analysis)
                logger.info(f"Batching strategy: {strategy}")
            except Exception as e:
                error_msg = f"Failed to determine batching strategy: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'status': 'error',
                        'file_name': file_name,
                        'error': error_msg,
                        'error_type': 'STRATEGY_FAILED'
                    })
                }
        else:
            # Non-COBOL files (JCL, COPYBOOK, etc.) don't use batching
            logger.info(f"Non-COBOL file - single-pass analysis (no batching)")
            strategy = {'strategy': 'single_call', 'num_batches': 1, 'estimated_tokens': 0}

        # Step 2: Phase 1 - File-Level Analysis (ALWAYS)
        try:
            logger.info("Starting file-level analysis...")

            # Select appropriate prompt based on file type
            if file_type == 'JCL':
                logger.info("Using JCL-specific prompt")
                program_prompt = build_jcl_program_level_prompt(file_analysis, user_context)
            elif file_type == 'COBOL_PROGRAM':
                logger.info("Using COBOL-specific prompt")
                program_prompt = build_program_level_prompt(file_analysis, user_context)
            else:
                logger.info(f"Using generic prompt for {file_type}")
                program_prompt = build_generic_file_prompt(file_analysis, user_context)

            program_response = invoke_bedrock(program_prompt)
            program_summary = parse_bedrock_response(program_response)
            logger.info("File-level analysis complete")
        except Exception as e:
            error_msg = f"Failed program-level analysis: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'status': 'error',
                    'file_name': file_name,
                    'error': error_msg,
                    'error_type': 'PROGRAM_ANALYSIS_FAILED'
                })
            }

        # Step 3: Phase 2 - Paragraph-Level Analysis (COBOL_PROGRAM only)
        paragraph_results = []

        # Only do paragraph analysis for COBOL programs (JCL, COPYBOOK, etc. don't have paragraphs)
        if file_type == 'COBOL_PROGRAM':
            try:
                if strategy['strategy'] == 'single_call':
                    # Small file - one detailed call
                    logger.info("Single call strategy - analyzing all paragraphs together")
                    full_prompt = build_full_file_prompt(file_analysis, program_summary, user_context)
                    full_response = invoke_bedrock(full_prompt)
                    paragraph_data = parse_bedrock_response(full_response)
                    paragraph_results = paragraph_data.get('paragraphs', [])
                    logger.info(f"Analyzed {len(paragraph_results)} paragraphs in single call")

                else:
                    # Large file - batched calls
                    logger.info(f"Batched strategy - {strategy['num_batches']} batches")
                    paragraphs = file_analysis.get('paragraphs', [])
                    batches = create_paragraph_batches(paragraphs, strategy['batch_size'])

                    for i, batch in enumerate(batches):
                        logger.info(f"Processing batch {i+1}/{len(batches)} ({len(batch)} paragraphs)")
                        batch_prompt = build_batch_prompt(batch, i+1, len(batches), program_summary, user_context)
                        batch_response = invoke_bedrock(batch_prompt)
                        batch_data = parse_bedrock_response(batch_response)
                        paragraph_results.extend(batch_data.get('paragraphs', []))

                    logger.info(f"Analyzed {len(paragraph_results)} paragraphs across {len(batches)} batches")

            except Exception as e:
                error_msg = f"Failed paragraph-level analysis: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'status': 'error',
                        'file_name': file_name,
                        'error': error_msg,
                        'error_type': 'PARAGRAPH_ANALYSIS_FAILED'
                    })
                }
        else:
            logger.info(f"Non-COBOL file - skipping paragraph-level analysis (not applicable)")

        # Step 4: Build AI analysis output
        ai_analysis = {
            'schema_version': SCHEMA_VERSION,
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'file_name': file_name,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'analyzer': 'BedrockAnalyzerPerFile',
            'model': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0',
            'batching_strategy': strategy,
            'program_level': program_summary,
            'paragraphs': paragraph_results,
            'paragraph_count': len(paragraph_results)
        }

        # Step 5: Write AI analysis to S3
        try:
            write_ai_analysis_to_s3(
                scout_account_id,
                application_name,
                job_id,
                file_name,
                ai_analysis
            )
        except Exception as e:
            logger.error(f"Failed to write AI analysis to S3: {str(e)}", exc_info=True)
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'status': 'error',
                    'file_name': file_name,
                    'error': f"Failed to write AI analysis to S3: {str(e)}",
                    'error_type': 'S3_WRITE_FAILED'
                })
            }

        logger.info(f"BedrockAnalyzerPerFile completed successfully for {file_name}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'success',
                'file_name': file_name,
                'program_analysis': True,
                'paragraphs_analyzed': len(paragraph_results),
                'batches_used': strategy['num_batches'],
                'estimated_tokens': strategy['estimated_tokens'],
                'ai_analysis': ai_analysis
            })
        }

    except Exception as e:
        logger.error(f"BedrockAnalyzerPerFile failed for {event.get('file_name', 'UNKNOWN')}: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'file_name': event.get('file_name', 'UNKNOWN'),
                'error': str(e),
                'error_type': 'UNEXPECTED_ERROR'
            })
        }
