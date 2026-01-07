"""
Dependency Mapper V2 - AI Dependency Analyzer Handler
Lambda: DependencyMapperV2AIAnalyzer

Purpose: AI-powered deep dependency analysis using Bedrock

V2 Design Principles:
- Standalone architecture (NO integration with other flows)
- Independent Lambda (NO code sharing)
- Event-driven architecture
- Uses AWS Bedrock Claude 3.5 Sonnet
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any

s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

BUCKET_NAME = 'code-transformation-v2'
BEDROCK_MODEL_ID = 'anthropic.claude-3-5-sonnet-20240620-v1:0'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AI-Powered Dependency Analysis

    Input (from Step Functions):
    {
        "job_id": "dmv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "ai_analysis_complete": true,
        "insights_file": "artifacts/ai_dependency_analysis.json"
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"AI dependency analysis for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'ai_analysis', 50, 'AI analyzing dependencies...')

        # Read static_analysis.json
        static_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/static_analysis.json"

        try:
            static_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=static_key)
            static_data = json.loads(static_response['Body'].read())
        except s3_client.exceptions.NoSuchKey:
            raise Exception(f"Static analysis not found at s3://{BUCKET_NAME}/{static_key}")

        summary = static_data.get('summary', {})
        programs = static_data.get('programs', [])

        print(f"Static analysis: {summary.get('total_programs')} programs, {summary.get('total_dependencies')} dependencies")

        # Build Bedrock prompt
        prompt = build_dependency_analysis_prompt(summary, programs)

        # Call Bedrock
        print("Calling AWS Bedrock for AI analysis...")
        ai_response = call_bedrock(prompt)

        print(f"AI analysis received: {len(ai_response)} characters")

        # Parse AI response (expect JSON)
        try:
            ai_insights = json.loads(ai_response)
        except json.JSONDecodeError:
            # If not JSON, wrap it
            ai_insights = {
                'raw_analysis': ai_response,
                'parsed': False
            }

        # Save AI analysis
        ai_analysis = {
            'ai_insights': ai_insights,
            'static_summary': summary,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id,
            'model_used': BEDROCK_MODEL_ID
        }

        output_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/ai_dependency_analysis.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(ai_analysis, indent=2),
            ContentType='application/json'
        )

        print(f"Saved AI analysis to s3://{BUCKET_NAME}/{output_key}")

        # Update status
        update_status(status_key, 'running', 'ai_analysis_complete', 55, 'AI analysis completed')

        return {
            'ai_analysis_complete': True,
            'insights_file': 'artifacts/ai_dependency_analysis.json'
        }

    except Exception as e:
        print(f"ERROR in DependencyMapperV2AIAnalyzer: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def build_dependency_analysis_prompt(summary: Dict[str, Any], programs: list) -> str:
    """Build comprehensive Bedrock prompt for dependency analysis"""

    # Truncate programs list if too large (max 50 programs for prompt size)
    programs_sample = programs[:50] if len(programs) > 50 else programs

    prompt = f"""You are a Senior Software Architect analyzing COBOL program dependencies for cloud migration planning.

**STATIC ANALYSIS RESULTS:**

Summary:
- Total programs analyzed: {summary.get('total_programs')}
- Total dependencies found: {summary.get('total_dependencies')}
- Program calls (CALL/LINK/XCTL): {summary.get('program_calls')}
- Copybook dependencies (COPY): {summary.get('copybook_dependencies')}
- File operations (READ/WRITE): {summary.get('file_operations')}
- Database operations (EXEC SQL): {summary.get('database_operations')}

Program Dependency Details:
{json.dumps(programs_sample, indent=2)}

**ANALYSIS REQUIREMENTS:**

1. **Dependency Graph Insights**: Identify key dependency patterns and architectural structure
2. **Coupling Analysis**: Identify high-coupling programs and tight coupling clusters
3. **Circular Dependencies**: Detect any circular dependency patterns
4. **Architectural Layers**: Identify potential architectural layers (presentation, business logic, data access)
5. **Microservice Boundaries**: Suggest natural boundaries for microservices based on coupling
6. **Risk Assessment**: Flag high-risk areas (tight coupling, circular deps, single points of failure)
7. **Migration Strategy**: Recommend decomposition approach for cloud migration

**OUTPUT FORMAT:**

Respond with ONLY a valid JSON object with this structure:

{{
  "dependency_patterns": {{
    "description": "Overall dependency pattern description",
    "key_observations": ["observation1", "observation2", ...]
  }},
  "coupling_analysis": {{
    "high_coupling_programs": [
      {{"program": "PROG001.cbl", "fan_in": 10, "fan_out": 5, "coupling_score": 0.85}}
    ],
    "coupling_clusters": [
      {{"cluster_name": "Order Processing", "programs": ["ORD001", "ORD002"], "internal_coupling": 0.9}}
    ]
  }},
  "circular_dependencies": [
    {{"cycle": ["PROG1", "PROG2", "PROG3", "PROG1"], "risk": "High", "recommendation": "Break cycle"}}
  ],
  "architectural_layers": [
    {{"layer": "Data Access", "programs": ["..."], "purpose": "..."}}
  ],
  "microservice_recommendations": [
    {{"service_name": "OrderService", "programs": ["..."], "justification": "..."}}
  ],
  "risk_assessment": {{
    "high_risk_areas": ["..."],
    "single_points_of_failure": ["..."],
    "refactoring_priorities": ["..."]
  }},
  "migration_strategy": {{
    "recommended_approach": "Strangler Fig pattern",
    "decomposition_order": ["service1", "service2", ...],
    "estimated_complexity": "Medium-High"
  }}
}}
"""

    return prompt


def call_bedrock(prompt: str) -> str:
    """Call AWS Bedrock with prompt"""
    try:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 10000,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())

        # Extract text from Claude response
        if 'content' in response_body and len(response_body['content']) > 0:
            return response_body['content'][0]['text']
        else:
            raise Exception("No content in Bedrock response")

    except Exception as e:
        print(f"Bedrock call failed: {str(e)}")
        raise


def update_status(status_key: str, status: str, phase: str, progress: int, message: str):
    """Update job status in S3"""
    try:
        # Read current status
        try:
            status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(status_response['Body'].read())
        except s3_client.exceptions.NoSuchKey:
            status_data = {}

        # Update fields
        status_data['state'] = status
        status_data['phase'] = phase
        status_data['progress'] = progress
        status_data['message'] = message
        status_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        # Write back
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status updated: {status} - {phase} ({progress}%) - {message}")

    except Exception as e:
        print(f"Failed to update status: {str(e)}")
