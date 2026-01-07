#!/usr/bin/env python3
"""
Data Analyzer V2 - Bedrock Data Analyzer Batch
Processes batches of COBOL files through COBOLDataAnalystV2 Bedrock Agent
Focuses on: Business entity identification, relationships, data lineage
"""

import json
import boto3
import time
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name='us-east-1')

# Constants
BUCKET_NAME = 'code-transformation-v2'
BEDROCK_AGENT_ID = 'TP8XJLYJUM'  # COBOLDataAnalystV2
BEDROCK_AGENT_ALIAS_ID = 'TSTALIASID'

def lambda_handler(event, context):
    """
    Process a batch of COBOL files for AI data analysis
    Input: job_id, scout_account_id, application_name, source_hash, batch
    Output: AI data analysis for the batch
    """

    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event['source_hash']
        batch = event['batch']
        batch_id = batch['batch_id']
        files = batch['files']

        print(f"Processing data analysis batch {batch_id} with {len(files)} files for job: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        extracted_path = f"{base_path}/shared/uploads/{source_hash}/extracted/"

        batch_results = []

        for file_path in files:
            print(f"Analyzing data in: {file_path}")

            # Read COBOL file
            full_key = f"{extracted_path}{file_path}"
            file_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=full_key)
            cobol_content = file_response['Body'].read().decode('utf-8', errors='ignore')

            # Invoke Bedrock Agent for data analysis
            ai_analysis = invoke_data_agent(cobol_content, file_path)

            batch_results.append({
                'file_path': file_path,
                'analysis': ai_analysis
            })

        # Save batch results
        output_key = f"{base_path}/data_analysis_v2/jobs/{job_id}/artifacts/ai_data_analysis/batch_{batch_id}.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps({
                'batch_id': batch_id,
                'files_analyzed': len(files),
                'results': batch_results
            }, indent=2),
            ContentType='application/json'
        )

        print(f"Batch {batch_id} complete: {len(files)} files analyzed")

        return {
            'statusCode': 200,
            'body': {
                'batch_id': batch_id,
                'files_analyzed': len(files),
                'output_path': f"s3://{BUCKET_NAME}/{output_key}"
            }
        }

    except Exception as e:
        print(f"Error processing data batch: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': {'error': str(e)}
        }


def invoke_data_agent(cobol_content, file_path):
    """Invoke COBOLDataAnalystV2 Bedrock Agent for data analysis"""

    try:
        # Create prompt for data analysis
        user_prompt = f"""Analyze the data structures in this COBOL file for database design:

File: {file_path}

COBOL Code:
{cobol_content[:15000]}

Focus on:
1. **Business Entity Identification** - What real-world entities do these data structures represent?
2. **Relationship Discovery** - How do these entities relate to each other?
3. **Data Lineage** - How does data flow through this program (READ → TRANSFORM → WRITE)?
4. **Normalization Opportunities** - Any data redundancy or normalization improvements?
5. **Data Quality Issues** - Missing constraints, integrity risks?

Provide actionable insights for ERD generation and database design."""

        # Invoke agent
        response = bedrock_agent_runtime.invoke_agent(
            agentId=BEDROCK_AGENT_ID,
            agentAliasId=BEDROCK_AGENT_ALIAS_ID,
            sessionId=f"data-batch-{int(time.time())}",
            inputText=user_prompt
        )

        # Collect response
        full_response = ""
        for event in response['completion']:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    full_response += chunk['bytes'].decode('utf-8')

        return {
            'analysis_text': full_response,
            'model': 'anthropic.claude-3-5-sonnet-20240620-v1:0',
            'agent': 'COBOLDataAnalystV2'
        }

    except Exception as e:
        print(f"Error invoking Bedrock agent: {str(e)}")
        return {
            'analysis_text': f"Error: {str(e)}",
            'error': True
        }
