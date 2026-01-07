#!/usr/bin/env python3
"""
Code Refactor V2 - Bedrock Refactor Analyzer Batch V2
Analyzes COBOL files using Bedrock Claude model to detect transformation patterns
FOCUS: Recipes and transformation opportunities, NOT code understanding

Uses direct bedrock-runtime.invoke_model() like Code Analysis V3.
"""

import json
import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path

import boto3

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Add shared module to path for Lambda deployment
handler_dir = Path(__file__).parent
shared_dir = handler_dir.parent.parent / 'shared'
if shared_dir.exists():
    sys.path.insert(0, str(shared_dir))

try:
    from refactor_v2_common import get_refactor_job_context, error_response
    from ai_config import get_ai_config
except ImportError:
    # Fallback for local testing
    from shared.refactor_v2_common import get_refactor_job_context, error_response
    from shared.ai_config import get_ai_config

s3_client = boto3.client('s3')


def lambda_handler(event, context):
    """
    Analyze a batch of COBOL files for refactoring patterns using Bedrock model
    Processes up to 5 files and writes pattern results to S3
    """

    try:
        print(f"Bedrock Refactor Analyzer Batch V2 starting: {json.dumps(event)}")

        # Get job context using shared helper
        job_ctx = get_refactor_job_context(event)
        bucket = job_ctx.bucket_name

        # Get AI configuration
        ai_cfg = get_ai_config()

        # Initialize Bedrock runtime client (like Code Analysis V3)
        bedrock_runtime = boto3.client(
            'bedrock-runtime',
            region_name=ai_cfg.region
        )

        logger.info(
            "Using Bedrock model for Refactor V2",
            extra={"provider": ai_cfg.provider, "region": ai_cfg.region, "model_id": ai_cfg.model_id}
        )

        print(f"Job context: job_id={job_ctx.job_id}, job_root={job_ctx.job_root}")
        print(f"AI config: provider={ai_cfg.provider}, region={ai_cfg.region}, model_id={ai_cfg.model_id}")

        # Batch-specific parameters
        batch = event.get('batch', {})
        batch_id = batch.get('batch_id', 0)
        files_to_process = batch.get('files', [])

        if not files_to_process:
            return error_response(400, 'No files in batch')

        print(f"Processing refactor batch {batch_id} with {len(files_to_process)} files")

        # Analyze each COBOL file in the batch for patterns
        batch_results = []
        files_processed = 0
        files_failed = 0

        for file_path in files_to_process:
            print(f"Analyzing file {files_processed + 1}/{len(files_to_process)}: {file_path}")

            try:
                # Read COBOL file content using job context helper
                file_key = job_ctx.get_file_key(file_path)
                file_response = s3_client.get_object(Bucket=bucket, Key=file_key)
                cobol_content = file_response['Body'].read().decode('utf-8')

                # Invoke Bedrock model for pattern analysis
                pattern_analysis = invoke_refactor_model(
                    bedrock_runtime,
                    ai_cfg,
                    cobol_content,
                    file_path
                )

                batch_results.append({
                    'path': file_path,
                    'patterns': pattern_analysis,
                    'analyzed_at': datetime.now(timezone.utc).isoformat()
                })
                files_processed += 1

            except Exception as file_error:
                print(f"Error analyzing {file_path}: {str(file_error)}")
                batch_results.append({
                    'path': file_path,
                    'error': str(file_error),
                    'patterns': None
                })
                files_failed += 1

        # Write batch results to S3 using job context helper
        batch_output_key = job_ctx.get_batch_key('ai_patterns', batch_id)

        batch_data = {
            'batch_id': batch_id,
            'job_id': job_ctx.job_id,
            'source_hash': job_ctx.source_hash,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'ai_config': {
                'provider': ai_cfg.provider,
                'region': ai_cfg.region,
                'model_id': ai_cfg.model_id
            },
            'files_processed': files_processed,
            'files_failed': files_failed,
            'files': batch_results
        }

        s3_client.put_object(
            Bucket=bucket,
            Key=batch_output_key,
            Body=json.dumps(batch_data, indent=2),
            ContentType='application/json'
        )

        print(f"Refactor batch {batch_id} complete. Processed: {files_processed}, Failed: {files_failed}")
        print(f"Output written to: {batch_output_key}")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'batch_id': batch_id,
                'files_processed': files_processed,
                'files_failed': files_failed,
                'output_path': f"s3://{bucket}/{batch_output_key}"
            }
        }

    except ValueError as e:
        # Missing required fields
        print(f"Validation error: {str(e)}")
        return error_response(400, str(e))

    except Exception as e:
        print(f"Error in refactor batch analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Batch analysis failed: {str(e)}")


def invoke_refactor_model(bedrock_runtime, ai_cfg, cobol_content, file_path, max_retries=3):
    """
    Invoke Bedrock model to analyze COBOL for transformation patterns.
    Uses direct invoke_model like Code Analysis V3.

    Returns pattern analysis focused on recipes and improvements.
    """
    # Build prompt for refactor analysis
    prompt = f"""Analyze the following COBOL program for refactoring and modernization opportunities: {file_path}

```cobol
{cobol_content}
```

Provide your analysis in JSON format with these sections:
1. transformation_opportunities - List of patterns that can be modernized (e.g., nested conditionals → Strategy pattern, GO TO → State machine)
2. modernization_recipes - Specific actionable recipes for Java generation
3. complexity_reduction - How to reduce cyclomatic complexity
4. performance_optimization - Performance improvement opportunities
5. testability_improvements - How to make the code more testable

Return ONLY valid JSON."""

    print(f"Invoking Bedrock model for {file_path} (content length: {len(cobol_content)} bytes)")

    # Call Bedrock with retries (same pattern as Code Analysis V3)
    for attempt in range(max_retries):
        try:
            response = bedrock_runtime.invoke_model(
                modelId=ai_cfg.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 8192,
                    "temperature": 0.3,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )

            # Parse response (same as Code Analysis V3)
            response_body = json.loads(response['body'].read().decode('utf-8'))
            response_text = response_body['content'][0]['text']

            print(f"Received refactor pattern analysis ({len(response_text)} chars)")

            # Parse the JSON response
            parsed = parse_model_response(response_text)

            return {
                'transformation_opportunities': parsed.get('transformation_opportunities'),
                'modernization_recipes': parsed.get('modernization_recipes'),
                'complexity_reduction': parsed.get('complexity_reduction'),
                'performance_optimization': parsed.get('performance_optimization'),
                'testability_improvements': parsed.get('testability_improvements'),
                'raw_analysis': response_text,
                'model_id': ai_cfg.model_id,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            if 'ThrottlingException' in str(e):
                # Rate limit hit - exponential backoff
                wait_time = 2 ** attempt
                logger.warning(f"Throttled, retrying in {wait_time}s...")
                time.sleep(wait_time)
            elif 'ModelTimeoutException' in str(e):
                # Model timeout - retry
                logger.warning(f"Model timeout on attempt {attempt + 1}")
                if attempt == max_retries - 1:
                    raise
            else:
                logger.error(f"Bedrock error: {str(e)}")
                raise

    raise Exception("Max retries exceeded")


def parse_model_response(response_text):
    """
    Parse JSON response from Bedrock model.
    Handles markdown code blocks if present.
    """
    try:
        # Try direct JSON parse
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
            return json.loads(json_str)
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
            return json.loads(json_str)
        else:
            # Return raw text in a wrapper
            return {
                'raw_response': response_text,
                'parse_error': 'Could not parse as JSON'
            }
