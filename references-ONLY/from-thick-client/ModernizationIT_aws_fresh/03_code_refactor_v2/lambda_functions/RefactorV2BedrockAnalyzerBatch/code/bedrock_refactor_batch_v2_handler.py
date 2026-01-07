#!/usr/bin/env python3
"""
Code Refactor V2 - Bedrock Refactor Analyzer Batch V2
Analyzes COBOL files using COBOLRefactorAnalystV2 Bedrock Agent to detect transformation patterns
FOCUS: Recipes and transformation opportunities, NOT code understanding
"""

import json
import boto3
import time
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

BUCKET_NAME = 'code-transformation-v2'
BEDROCK_AGENT_ID = 'TBD'  # COBOLRefactorAnalystV2 - to be created
BEDROCK_AGENT_ALIAS_ID = 'TSTALIASID'

def lambda_handler(event, context):
    """
    Analyze a batch of COBOL files for refactoring patterns using Bedrock Agent
    Processes up to 5 files and writes pattern results to S3
    """

    try:
        print(f"Bedrock Refactor Analyzer Batch V2 starting: {json.dumps(event)}")

        # Parse input
        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')
        source_hash = event.get('source_hash')

        # Batch-specific parameters
        batch = event.get('batch', {})
        batch_id = batch.get('batch_id', 0)
        files_to_process = batch.get('files', [])

        if not all([job_id, scout_account_id, application_name, source_hash]):
            return error_response(400, 'Missing required fields')

        if not files_to_process:
            return error_response(400, 'No files in batch')

        base_path = f"{scout_account_id}/{application_name}"
        job_path = f"{base_path}/code_refactor_v2/jobs/{job_id}"

        print(f"Processing refactor batch {batch_id} with {len(files_to_process)} files")

        # Analyze each COBOL file in the batch for patterns
        batch_results = []
        files_processed = 0
        files_failed = 0

        for file_path in files_to_process:
            print(f"Analyzing file {files_processed + 1}/{len(files_to_process)}: {file_path}")

            try:
                # Read COBOL file content
                file_key = f"{base_path}/shared/uploads/{source_hash}/extracted/{file_path}"
                file_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
                cobol_content = file_response['Body'].read().decode('utf-8')

                # Invoke Bedrock Agent for pattern analysis
                pattern_analysis = invoke_refactor_agent(cobol_content, file_path)

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

        # Write batch results to S3
        batch_output_key = f"{job_path}/artifacts/ai_patterns/batch_{batch_id}.json"

        batch_data = {
            'batch_id': batch_id,
            'job_id': job_id,
            'source_hash': source_hash,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'files_processed': files_processed,
            'files_failed': files_failed,
            'files': batch_results
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
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
                'output_path': f"s3://{BUCKET_NAME}/{batch_output_key}"
            }
        }

    except Exception as e:
        print(f"Error in refactor batch analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Batch analysis failed: {str(e)}")


def invoke_refactor_agent(cobol_content, file_path):
    """
    Invoke Bedrock Refactor Agent to analyze COBOL for transformation patterns
    Returns pattern analysis focused on recipes and improvements
    """

    try:
        # Prepare the prompt for the agent
        user_prompt = f"""Analyze the following COBOL program for refactoring and modernization opportunities: {file_path}

```cobol
{cobol_content}
```

Focus on transformation patterns and provide actionable refactoring recipes for Java generation."""

        print(f"Invoking Bedrock Refactor Agent for {file_path} (content length: {len(cobol_content)} bytes)")

        # Invoke the agent
        response = bedrock_agent_runtime.invoke_agent(
            agentId=BEDROCK_AGENT_ID,
            agentAliasId=BEDROCK_AGENT_ALIAS_ID,
            sessionId=f"refactor-batch-{int(time.time())}",
            inputText=user_prompt
        )

        # Process the streaming response
        event_stream = response['completion']
        full_response = ""

        for event in event_stream:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    full_response += chunk['bytes'].decode('utf-8')

        print(f"Received refactor pattern analysis ({len(full_response)} chars)")

        return {
            'transformation_opportunities': extract_section(full_response, 'Transformation Opportunities'),
            'modernization_recipes': extract_section(full_response, 'Modernization Recipes'),
            'complexity_reduction': extract_section(full_response, 'Complexity Reduction'),
            'performance_optimization': extract_section(full_response, 'Performance Optimization'),
            'testability_improvements': extract_section(full_response, 'Testability Improvements'),
            'raw_analysis': full_response,
            'model': 'anthropic.claude-3-5-sonnet-20240620-v1:0',
            'agent': 'COBOLRefactorAnalystV2',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        print(f"Error invoking Bedrock Refactor Agent: {str(e)}")
        raise


def extract_section(text, section_name):
    """Extract a specific section from AI response"""
    # Simple extraction - look for section header
    import re
    pattern = rf'\*\*{section_name}\*\*.*?\n(.*?)(?=\n\*\*|\Z)'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Alternative pattern
    pattern = rf'{section_name}.*?\n(.*?)(?=\n[A-Z][a-z]+:|\Z)'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return None


def error_response(status_code, message):
    return {
        'statusCode': status_code,
        'body': {
            'error': message
        }
    }
