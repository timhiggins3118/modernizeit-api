"""
Monolith Identifier V2 - AI Analyzer Handler
Lambda: MonolithIdentifierV2AIAnalyzer

Purpose: AI-powered monolith pattern detection using AWS Bedrock

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
- Uses Bedrock Claude 3.5 Sonnet
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
    AI Analyzer - Detect monolith patterns using AI

    Input:
    {
        "job_id": "miv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "analyzed_programs": 20,
        "patterns_detected": {...}
    }
    """
    try:
        print("=" * 80)
        print("MONOLITH IDENTIFIER V2 - AI ANALYZER")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        # Read static analysis results
        static_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/static_monolith_analysis.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=static_key)
        static_data = json.loads(response['Body'].read().decode('utf-8'))

        programs = static_data.get('programs', [])
        print(f"Total programs: {len(programs)}")

        # Filter out programs with errors
        valid_programs = [p for p in programs if 'error' not in p and p.get('loc', 0) > 0]
        print(f"Valid programs (no errors): {len(valid_programs)}")

        # Select top programs for AI analysis (largest and most complex)
        # Limit to top 20 to control costs and time
        programs_for_ai = sorted(
            valid_programs,
            key=lambda p: (p.get('loc', 0) * p.get('cyclomatic_complexity', 1)),
            reverse=True
        )[:20]

        print(f"Selecting {len(programs_for_ai)} programs for AI analysis")

        # Analyze patterns with AI
        god_programs = []
        tight_coupling = []
        shared_data_issues = []

        for program in programs_for_ai:
            print(f"\nAnalyzing: {program['program_name']}")

            # Build prompt
            prompt = build_analysis_prompt(program)

            # Call Bedrock
            ai_response = call_bedrock(prompt)

            # Parse response
            analysis = parse_ai_response(program, ai_response)

            if analysis['is_god_program']:
                god_programs.append(analysis['god_program_data'])

            if analysis['has_tight_coupling']:
                tight_coupling.append(analysis['coupling_data'])

            if analysis['has_shared_data_issues']:
                shared_data_issues.append(analysis['shared_data'])

        print(f"\nAI Analysis Complete:")
        print(f"  God Programs: {len(god_programs)}")
        print(f"  Tight Coupling: {len(tight_coupling)}")
        print(f"  Shared Data Issues: {len(shared_data_issues)}")

        # Create result
        result = {
            'analyzed_programs': len(programs_for_ai),
            'patterns_detected': {
                'god_programs': god_programs,
                'tight_coupling': tight_coupling,
                'shared_data_issues': shared_data_issues
            }
        }

        # Write to S3
        artifact_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/ai_pattern_analysis.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=artifact_key,
            Body=json.dumps(result, indent=2),
            ContentType='application/json'
        )

        print(f"\nWrote artifact: s3://{BUCKET_NAME}/{artifact_key}")

        # Update status
        update_status(scout_account_id, application_name, job_id, {
            'phase': 'ai_analysis_complete',
            'progress': 50,
            'message': f'AI analyzed {len(programs_for_ai)} programs'
        })

        return result

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def build_analysis_prompt(program: Dict[str, Any]) -> str:
    """Build prompt for AI analysis"""
    return f"""Analyze this COBOL program for monolithic architecture anti-patterns:

Program: {program.get('program_name', 'Unknown')}
Lines of Code: {program.get('loc', 0)}
Cyclomatic Complexity: {program.get('cyclomatic_complexity', 0)}
Call Statements: {program.get('call_statements', 0)}
Copybooks Used: {', '.join(program.get('copybooks_used', []))}
File Operations: {program.get('file_operations', 0)}
Database Operations: {program.get('database_operations', 0)}

Please analyze and respond in JSON format:
{{
  "is_god_program": boolean,
  "responsibilities": ["responsibility1", "responsibility2", ...],
  "has_tight_coupling": boolean,
  "coupling_issues": "description",
  "has_shared_data_issues": boolean,
  "shared_data_concerns": "description",
  "recommendation": "how to decompose this program",
  "confidence": 0.0-1.0
}}

Focus on:
1. Does this program handle multiple unrelated business functions? (God Program)
2. Is it tightly coupled with excessive dependencies?
3. Does it use shared data structures that create coupling?
4. How should it be decomposed into smaller services?"""


def call_bedrock(prompt: str) -> str:
    """Call AWS Bedrock Claude 3.5 Sonnet"""
    try:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
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
        return "{}"


def parse_ai_response(program: Dict[str, Any], ai_response: str) -> Dict[str, Any]:
    """Parse AI response into structured data"""
    try:
        # Try to extract JSON from response
        ai_data = json.loads(ai_response)

        result = {
            'is_god_program': ai_data.get('is_god_program', False),
            'has_tight_coupling': ai_data.get('has_tight_coupling', False),
            'has_shared_data_issues': ai_data.get('has_shared_data_issues', False)
        }

        if result['is_god_program']:
            result['god_program_data'] = {
                'program': program['program_name'],
                'responsibilities': ai_data.get('responsibilities', []),
                'recommendation': ai_data.get('recommendation', ''),
                'ai_confidence': ai_data.get('confidence', 0.5)
            }
        else:
            result['god_program_data'] = None

        if result['has_tight_coupling']:
            result['coupling_data'] = {
                'program': program['program_name'],
                'coupling_issues': ai_data.get('coupling_issues', ''),
                'recommendation': ai_data.get('recommendation', '')
            }
        else:
            result['coupling_data'] = None

        if result['has_shared_data_issues']:
            result['shared_data'] = {
                'program': program['program_name'],
                'concerns': ai_data.get('shared_data_concerns', ''),
                'copybooks': program.get('copybooks_used', [])
            }
        else:
            result['shared_data'] = None

        return result

    except json.JSONDecodeError:
        # Fallback if AI doesn't return valid JSON
        return {
            'is_god_program': False,
            'has_tight_coupling': False,
            'has_shared_data_issues': False,
            'god_program_data': None,
            'coupling_data': None,
            'shared_data': None
        }


def update_status(account_id: str, app_name: str, job_id: str, updates: Dict[str, Any]):
    """Update job status in S3"""
    try:
        status_key = f"{account_id}/{app_name}/monolith_identifier_v2/jobs/{job_id}/status.json"

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
