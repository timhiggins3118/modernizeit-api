"""
Discovery V2 - Bedrock Discovery Analyzer Batch Handler
Lambda: DiscoveryV2BedrockAnalyzerBatch

Purpose: AI-powered discovery analysis using Bedrock Agent (batched)

Bedrock Agent: COBOLDiscoveryAnalystV2
Model: Claude 3.5 Sonnet

V2 Design Principles:
- Uses Bedrock Agent (NOT direct invoke_model)
- Analyzes 5 files per batch
- Independent Lambda (NO code sharing)
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List

s3_client = boto3.client('s3')
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name='us-east-1')

BUCKET_NAME = 'code-transformation-v2'
BEDROCK_AGENT_ID = 'TBD'  # Will be set after deploying Bedrock Agent
BEDROCK_AGENT_ALIAS_ID = 'TSTALIASID'  # Test alias


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Bedrock Discovery Analyzer - Batch Processing

    Input (from Step Functions Map state):
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "source_hash": "21a056...",
        "batch": {
            "batch_id": 0,
            "files": ["file1.cbl", "file2.cbl", ...]
        }
    }

    Output:
    {
        "batch_id": 0,
        "files_analyzed": 5,
        "results": [...]
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

        print(f"Analyzing batch {batch_id} with {len(files)} files for job {job_id}")

        # Process each file in batch
        results = []

        for file_path in files:
            print(f"Analyzing file: {file_path}")

            # Read COBOL file content
            cobol_key = f"{scout_account_id}/{application_name}/shared/uploads/{source_hash}/extracted/{file_path}"

            try:
                cobol_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=cobol_key)
                cobol_content = cobol_response['Body'].read().decode('utf-8', errors='ignore')
            except s3_client.exceptions.NoSuchKey:
                print(f"WARNING: File not found: {file_path}")
                results.append({
                    'file_path': file_path,
                    'error': 'File not found',
                    'analysis': None
                })
                continue

            # Get file size
            file_size = len(cobol_content)

            # Truncate if too large (max 15000 chars for prompt)
            cobol_content_truncated = cobol_content[:15000]
            if len(cobol_content) > 15000:
                print(f"File truncated from {len(cobol_content)} to 15000 chars")

            # Invoke Bedrock Agent for discovery analysis
            prompt = build_discovery_prompt(file_path, file_size, cobol_content_truncated)

            try:
                analysis = invoke_bedrock_agent(prompt)

                results.append({
                    'file_path': file_path,
                    'file_size': file_size,
                    'analysis': analysis,
                    'model': 'anthropic.claude-3-5-sonnet-20240620-v1:0',
                    'agent': 'COBOLDiscoveryAnalystV2',
                    'analyzed_at': datetime.now(timezone.utc).isoformat()
                })

                print(f"Successfully analyzed {file_path}")

            except Exception as e:
                print(f"ERROR analyzing {file_path}: {str(e)}")
                results.append({
                    'file_path': file_path,
                    'error': str(e),
                    'analysis': None
                })

        # Save batch results to S3
        batch_results_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/ai_discovery_analysis/batch_{batch_id}.json"

        batch_output = {
            'batch_id': batch_id,
            'files_analyzed': len(files),
            'successful_analyses': len([r for r in results if r.get('analysis')]),
            'failed_analyses': len([r for r in results if r.get('error')]),
            'results': results,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=batch_results_key,
            Body=json.dumps(batch_output, indent=2),
            ContentType='application/json'
        )

        print(f"Saved batch {batch_id} results to s3://{BUCKET_NAME}/{batch_results_key}")

        return batch_output

    except Exception as e:
        print(f"ERROR in DiscoveryV2BedrockAnalyzerBatch: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def build_discovery_prompt(file_path: str, file_size: int, cobol_content: str) -> str:
    """Build discovery analysis prompt for Bedrock Agent"""

    prompt = f"""Analyze this COBOL application for modernization discovery:

File: {file_path}
Size: {file_size} bytes

COBOL Code:
{cobol_content}

Provide comprehensive analysis in the following categories:

1. **Business Processes** (25% of response)
   - Identify business capabilities this program implements
   - Assign business value: High/Medium/Low
   - Estimate complexity level: High/Medium/Low
   - Determine execution frequency: Real-time/Daily/Weekly/Batch
   - Calculate confidence score (0-100)

2. **Integration Points** (25% of response)
   - Detect database connections: DB2, IMS, VSAM
   - Identify transaction managers: CICS, IMS DC
   - Find messaging systems: MQ
   - Locate file systems: QSAM, VSAM
   - Discover external APIs or web services
   - Recommend AWS service for each integration

3. **API Pattern Analysis** (20% of response)
   - Classify execution pattern:
     * Batch processing (scheduled, file-driven)
     * Real-time transaction (CICS online, request/response)
     * Event-driven (message-triggered, async)
     * Hybrid/mixed patterns
   - Recommend AWS architecture (Lambda, ECS, Step Functions, EventBridge, etc.)

4. **Data Flow Mapping** (15% of response)
   - Track input sources: files, databases, messages, APIs
   - Document processing/transformation logic
   - Identify output destinations: files, databases, messages, APIs

5. **External Dependencies** (10% of response)
   - List copybooks/includes
   - Identify called programs
   - Document required data files
   - Map database tables/views

6. **Modernization Insights** (5% of response)
   - Assess cloud readiness (score 0-100)
   - Identify decoupling opportunities
   - Evaluate microservices potential
   - Suggest technology replacements

Respond with structured, actionable insights for AWS modernization strategy.
Focus on practical recommendations, not just descriptions."""

    return prompt


def invoke_bedrock_agent(prompt: str) -> Dict[str, Any]:
    """
    Invoke Bedrock Agent for discovery analysis

    Returns parsed analysis from agent response
    """

    # TEMPORARY: Since agent isn't deployed yet, use direct bedrock invocation
    # This will be replaced with actual agent invocation after deployment

    # TODO: Replace with actual agent call after deploying COBOLDiscoveryAnalystV2
    # response = bedrock_agent_runtime.invoke_agent(
    #     agentId=BEDROCK_AGENT_ID,
    #     agentAliasId=BEDROCK_AGENT_ALIAS_ID,
    #     sessionId=f"discovery-{datetime.now(timezone.utc).timestamp()}",
    #     inputText=prompt
    # )

    # For now, use bedrock-runtime as placeholder
    bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')

    body = json.dumps({
        'anthropic_version': 'bedrock-2023-05-31',
        'max_tokens': 4000,
        'messages': [
            {
                'role': 'user',
                'content': prompt
            }
        ],
        'temperature': 0.3
    })

    response = bedrock_runtime.invoke_model(
        modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
        body=body
    )

    response_body = json.loads(response['body'].read())
    analysis_text = response_body['content'][0]['text']

    # Parse AI response into structured format
    # NOTE: In production, the Bedrock Agent will return structured JSON
    # For now, we return the raw text analysis

    return {
        'raw_analysis': analysis_text,
        'business_processes': [],  # Will be extracted by BusinessProcessExtractor
        'integration_points': [],  # Will be extracted by IntegrationDetector
        'api_pattern': None,       # Will be extracted by APIPatternAnalyzer
        'data_flow': {},
        'external_dependencies': [],
        'modernization_insights': {}
    }
