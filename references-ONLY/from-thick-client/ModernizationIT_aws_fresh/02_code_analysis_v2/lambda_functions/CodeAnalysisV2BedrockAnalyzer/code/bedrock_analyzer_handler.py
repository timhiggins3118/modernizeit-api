#!/usr/bin/env python3
"""
Code Analysis V2 - Bedrock AI Analyzer
Invokes COBOLAnalystV2 Bedrock Agent for AI-powered code analysis
"""

import json
import boto3
import time
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

BUCKET_NAME = 'code-transformation-v2'
BEDROCK_AGENT_ID = 'LGXEUDJILW'  # COBOLAnalystV2
BEDROCK_AGENT_ALIAS_ID = 'TSTALIASID'  # Default test alias

def lambda_handler(event, context):
    """
    Analyze COBOL files using Bedrock Agent
    Runs in parallel with regex and tree-sitter analyzers
    """

    try:
        print(f"Bedrock Analyzer V2 starting: {json.dumps(event)}")

        # Parse input
        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')
        source_hash = event.get('source_hash')

        if not all([job_id, scout_account_id, application_name, source_hash]):
            return error_response(400, 'Missing required fields')

        base_path = f"{scout_account_id}/{application_name}"
        print(f"Analyzing job: {job_id}")

        # Read classified catalog to get COBOL files
        catalog_key = f"{base_path}/shared/catalogs/{source_hash}/classified_catalog.json"
        catalog_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=catalog_key)
        classified_catalog = json.loads(catalog_response['Body'].read().decode('utf-8'))

        cobol_files = classified_catalog.get('classifications', {}).get('cobol', [])

        if not cobol_files:
            print("No COBOL files found in catalog")
            return {
                'statusCode': 200,
                'body': {
                    'status': 'completed',
                    'job_id': job_id,
                    'files_analyzed': 0,
                    'message': 'No COBOL files to analyze',
                    'output_path': None
                }
            }

        print(f"Found {len(cobol_files)} COBOL files to analyze")

        # Analyze each COBOL file with Bedrock Agent
        ai_results = []
        total_files = len(cobol_files)

        for idx, file_path in enumerate(cobol_files, 1):
            print(f"Analyzing file {idx}/{total_files}: {file_path}")

            try:
                # Read COBOL file content
                file_key = f"{base_path}/shared/uploads/{source_hash}/extracted/{file_path}"
                file_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
                cobol_content = file_response['Body'].read().decode('utf-8')

                # Invoke Bedrock Agent
                ai_analysis = invoke_bedrock_agent(cobol_content, file_path)

                ai_results.append({
                    'path': file_path,
                    'analysis': ai_analysis,
                    'analyzed_at': datetime.now(timezone.utc).isoformat()
                })

            except Exception as file_error:
                print(f"Error analyzing {file_path}: {str(file_error)}")
                ai_results.append({
                    'path': file_path,
                    'error': str(file_error),
                    'analysis': None
                })

        # Write results to S3
        output_key = f"{base_path}/code_analysis_v2/jobs/{job_id}/artifacts/ai_analysis.json"

        output_data = {
            'job_id': job_id,
            'source_hash': source_hash,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'agent_id': BEDROCK_AGENT_ID,
            'agent_name': 'COBOLAnalystV2',
            'files_analyzed': len(ai_results),
            'files': ai_results
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(output_data, indent=2),
            ContentType='application/json'
        )

        print(f"AI analysis complete. Output written to: {output_key}")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'job_id': job_id,
                'files_analyzed': len(ai_results),
                'output_path': f"s3://{BUCKET_NAME}/{output_key}"
            }
        }

    except Exception as e:
        print(f"Error in Bedrock analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Bedrock analysis failed: {str(e)}")


def invoke_bedrock_agent(cobol_content, file_path):
    """
    Invoke Bedrock Agent to analyze COBOL code
    Returns the AI-generated analysis text
    """

    try:
        # Prepare the prompt for the agent
        user_prompt = f"""Analyze the following COBOL program from file: {file_path}

```cobol
{cobol_content}
```

Provide a detailed analysis following the structure outlined in your instructions."""

        print(f"Invoking Bedrock Agent for {file_path} (content length: {len(cobol_content)} bytes)")

        # Invoke the agent
        response = bedrock_agent_runtime.invoke_agent(
            agentId=BEDROCK_AGENT_ID,
            agentAliasId=BEDROCK_AGENT_ALIAS_ID,
            sessionId=f"session-{int(time.time())}",
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

        print(f"Received AI analysis ({len(full_response)} chars)")

        return {
            'analysis_text': full_response,
            'model': 'anthropic.claude-3-5-sonnet-20240620-v1:0',
            'agent': 'COBOLAnalystV2',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        print(f"Error invoking Bedrock Agent: {str(e)}")
        raise


def error_response(status_code, message):
    return {
        'statusCode': status_code,
        'body': {
            'error': message
        }
    }
