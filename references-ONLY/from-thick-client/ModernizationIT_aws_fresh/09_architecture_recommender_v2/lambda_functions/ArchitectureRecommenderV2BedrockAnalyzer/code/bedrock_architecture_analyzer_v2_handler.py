"""
Architecture Recommender V2 - Bedrock Architecture Analyzer Handler
Lambda: ArchitectureRecommenderV2BedrockAnalyzer

Purpose: AI-powered AWS architecture analysis using Bedrock

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
- Uses AWS Bedrock Claude 3.5 Sonnet
"""

import json
import boto3
from typing import Dict, Any, List

s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

BUCKET_NAME = 'code-transformation-v2'
BEDROCK_MODEL_ID = 'anthropic.claude-3-5-sonnet-20240620-v1:0'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Bedrock Architecture Analyzer - AI-powered architecture recommendations

    Input:
    {
        "job_id": "ar2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "consolidated_data": {...}
    }

    Output:
    {
        "service_mappings": [...],
        "database_strategy": {...},
        "api_design": {...}
    }
    """
    try:
        print("=" * 80)
        print("ARCHITECTURE RECOMMENDER V2 - BEDROCK ANALYZER")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        # Read consolidated data from S3 (not passed via Step Functions due to 256KB limit)
        base_path = f"{scout_account_id}/{application_name}"
        consolidated_key = f"{base_path}/architecture_v2/jobs/{job_id}/artifacts/consolidated_input.json"

        print(f"Reading consolidated input from S3...")
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=consolidated_key)
        consolidated_artifact = json.loads(response['Body'].read().decode('utf-8'))
        consolidated_data = consolidated_artifact.get('consolidated_data', {})

        # Build comprehensive prompt
        prompt = build_architecture_prompt(consolidated_data)

        print(f"\nPrompt size: {len(prompt)} characters")
        print(f"Invoking Bedrock Claude 3.5 Sonnet...")

        # Call Bedrock
        ai_response = call_bedrock(prompt)

        print(f"✓ Bedrock response received: {len(ai_response)} characters")

        # Parse AI response
        architecture_analysis = parse_ai_response(ai_response)

        print(f"\nArchitecture Analysis:")
        print(f"  Application Type: {architecture_analysis.get('summary', {}).get('application_type', 'unknown')}")
        print(f"  Services Recommended: {len(architecture_analysis.get('service_mappings', []))}")
        print(f"  Database: {architecture_analysis.get('database_strategy', {}).get('primary_database', 'unknown')}")

        # Write artifact
        base_path = f"{scout_account_id}/{application_name}"
        artifact_key = f"{base_path}/architecture_v2/jobs/{job_id}/artifacts/architecture_analysis.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=artifact_key,
            Body=json.dumps(architecture_analysis, indent=2),
            ContentType='application/json'
        )

        print(f"\nWrote artifact: s3://{BUCKET_NAME}/{artifact_key}")

        # Update status
        update_status(scout_account_id, application_name, job_id, {
            'phase': 'ai_analysis',
            'progress': 40,
            'message': f'AI analyzed application, recommended {len(architecture_analysis.get("service_mappings", []))} services'
        })

        return architecture_analysis

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def build_architecture_prompt(consolidated_data: Dict[str, Any]) -> str:
    """Build comprehensive prompt for Bedrock"""

    # Extract key metrics (handle None values)
    discovery = consolidated_data.get('discovery_v2') or {}
    data_analysis = consolidated_data.get('data_analysis_v2') or {}
    code_analysis = consolidated_data.get('code_analysis_v2') or {}
    refactor = consolidated_data.get('refactor_v2') or {}

    # Safely extract data
    erd = data_analysis.get('erd', {})
    entities_count = len(erd.get('entities', [])) if isinstance(erd.get('entities'), list) else 0
    relationships_count = len(erd.get('relationships', [])) if isinstance(erd.get('relationships'), list) else 0

    programs_count = len(code_analysis.get('programs', [])) if isinstance(code_analysis.get('programs', []), list) else 0

    total_loc = 0
    avg_complexity = 0
    if isinstance(code_analysis.get('programs', []), list):
        programs = code_analysis.get('programs', [])
        if programs:
            total_loc = sum(p.get('loc', 0) for p in programs if isinstance(p, dict))
            complexities = [p.get('cyclomatic_complexity', 0) for p in programs if isinstance(p, dict) and p.get('cyclomatic_complexity')]
            avg_complexity = sum(complexities) / len(complexities) if complexities else 0

    prompt = f"""You are an AWS Solutions Architect analyzing a COBOL application for cloud modernization.

Based on comprehensive analysis from 4 different tools (Discovery, Data Analysis, Code Analysis, Refactoring), recommend the optimal AWS architecture.

## Application Overview

**Programs Analyzed:** {programs_count}
**Total Lines of Code:** {total_loc}
**Average Complexity:** {avg_complexity:.1f}
**Data Entities:** {entities_count}
**Data Relationships:** {relationships_count}

## Discovery Analysis Summary

{json.dumps(discovery.get('summary', {}), indent=2) if discovery else 'No discovery data available'}

## Data Structure Summary

**ERD Summary:**
{json.dumps(erd.get('summary', {}), indent=2) if erd else 'No ERD data available'}

**Data Lineage:**
{json.dumps(data_analysis.get('data_lineage', {}).get('summary', {}), indent=2) if data_analysis.get('data_lineage') else 'No lineage data available'}

## Code Quality Summary

{json.dumps(code_analysis.get('summary', {}), indent=2) if code_analysis else 'No code analysis data available'}

## Refactoring Recommendations

{json.dumps(refactor.get('summary', {}), indent=2) if refactor else 'No refactor data available'}

---

## Your Task

Analyze this COBOL application and provide AWS architecture recommendations in JSON format:

```json
{{
  "summary": {{
    "application_type": "batch_processing | transactional | event_driven | etl | mixed",
    "recommended_architecture": "serverless | containerized | hybrid | traditional",
    "confidence": 0.0-1.0,
    "key_characteristics": ["characteristic1", "characteristic2"]
  }},
  "service_mappings": [
    {{
      "cobol_program": "PROGRAM_NAME.cobol",
      "aws_service": "Lambda | ECS | EC2",
      "function_name": "ServiceName",
      "runtime": "java17 | python3.11 | nodejs20.x",
      "memory_mb": 512,
      "timeout_seconds": 300,
      "trigger": "CloudWatch Events | S3 | API Gateway | SQS",
      "confidence": 0.0-1.0,
      "reasoning": "Why this service is recommended"
    }}
  ],
  "database_strategy": {{
    "primary_database": "RDS PostgreSQL | Aurora PostgreSQL | DynamoDB | None",
    "instance_class": "db.t4g.medium",
    "storage_gb": 100,
    "multi_az": true,
    "confidence": 0.0-1.0,
    "reasoning": "Why this database is recommended",
    "migration_strategy": "AWS DMS | manual | scripts"
  }},
  "api_design": {{
    "required": true | false,
    "api_type": "REST | GraphQL | WebSocket | None",
    "authentication": "IAM | Cognito | API Key | None",
    "reasoning": "Why API is/isn't needed"
  }},
  "compute_summary": {{
    "lambda_functions": 0,
    "ecs_services": 0,
    "ec2_instances": 0
  }},
  "storage_strategy": {{
    "s3_buckets": [
      {{
        "name": "bucket-purpose",
        "purpose": "Input files | Output files | Archive",
        "storage_class": "S3 Standard | S3 IA | Glacier"
      }}
    ]
  }},
  "security_recommendations": {{
    "vpc_required": true | false,
    "encryption_at_rest": "AWS KMS | None",
    "encryption_in_transit": "TLS 1.2+ | None",
    "iam_roles_needed": ["LambdaExecutionRole", "ECSTaskRole"]
  }},
  "migration_phases": [
    {{
      "phase": 1,
      "name": "Phase name",
      "duration_weeks": 4,
      "risk": "low | medium | high",
      "tasks": ["task1", "task2"]
    }}
  ]
}}
```

## Analysis Guidelines

1. **Application Type:** Determine if batch, transactional, event-driven, or ETL based on execution patterns
2. **Compute Choice:**
   - Lambda: Event-driven, short-duration (<15 min), sporadic
   - ECS: Long-running, microservices, moderate complexity
   - EC2: High complexity, legacy dependencies, steady state
3. **Database Choice:**
   - RDS/Aurora: Relational data, ACID transactions, complex queries
   - DynamoDB: Key-value, high-scale reads, eventual consistency
4. **Cost Optimization:** Choose services that minimize monthly costs
5. **Migration Risk:** Recommend phased approach starting with low-risk components

Provide ONLY the JSON response, no additional commentary."""

    return prompt


def call_bedrock(prompt: str) -> str:
    """Call AWS Bedrock Claude 3.5 Sonnet"""
    try:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
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
        return response_body['content'][0]['text']

    except Exception as e:
        print(f"Bedrock error: {str(e)}")
        # Return minimal fallback
        return json.dumps({
            "summary": {
                "application_type": "unknown",
                "recommended_architecture": "hybrid",
                "confidence": 0.5
            },
            "service_mappings": [],
            "database_strategy": {
                "primary_database": "RDS PostgreSQL",
                "reasoning": "Default recommendation due to analysis error"
            },
            "api_design": {
                "required": false,
                "reasoning": "Unable to determine from analysis"
            }
        })


def parse_ai_response(ai_response: str) -> Dict[str, Any]:
    """Parse AI response into structured data"""
    try:
        # Try to extract JSON from response
        # Handle markdown code blocks
        if '```json' in ai_response:
            start = ai_response.find('```json') + 7
            end = ai_response.find('```', start)
            ai_response = ai_response[start:end].strip()
        elif '```' in ai_response:
            start = ai_response.find('```') + 3
            end = ai_response.find('```', start)
            ai_response = ai_response[start:end].strip()

        architecture_data = json.loads(ai_response)

        # Ensure required fields exist
        if 'summary' not in architecture_data:
            architecture_data['summary'] = {
                'application_type': 'unknown',
                'recommended_architecture': 'hybrid',
                'confidence': 0.5
            }

        if 'service_mappings' not in architecture_data:
            architecture_data['service_mappings'] = []

        if 'database_strategy' not in architecture_data:
            architecture_data['database_strategy'] = {
                'primary_database': 'RDS PostgreSQL',
                'reasoning': 'Default recommendation'
            }

        return architecture_data

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {str(e)}")
        # Return minimal fallback
        return {
            'summary': {
                'application_type': 'unknown',
                'recommended_architecture': 'hybrid',
                'confidence': 0.5
            },
            'service_mappings': [],
            'database_strategy': {
                'primary_database': 'RDS PostgreSQL',
                'reasoning': 'Fallback due to parse error'
            },
            'api_design': {
                'required': False,
                'reasoning': 'Unable to parse AI response'
            }
        }


def update_status(account_id: str, app_name: str, job_id: str, updates: Dict[str, Any]):
    """Update job status in S3"""
    try:
        status_key = f"{account_id}/{app_name}/architecture_v2/jobs/{job_id}/status.json"

        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
        status = json.loads(response['Body'].read().decode('utf-8'))

        status.update(updates)

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status, indent=2),
            ContentType='application/json'
        )

        print(f"Updated status: {updates}")

    except Exception as e:
        print(f"Error updating status: {str(e)}")
