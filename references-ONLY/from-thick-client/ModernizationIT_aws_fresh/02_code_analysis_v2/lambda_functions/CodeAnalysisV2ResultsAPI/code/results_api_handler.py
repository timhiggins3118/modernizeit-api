#!/usr/bin/env python3
"""
Code Analysis V2 - Results API Handler
Returns analysis results with optional section filtering
"""

import json
import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    GET /resultsv2/{job_id}
    GET /resultsv2/{job_id}?section=<section_name>

    Returns complete analysis results or specific section
    """

    try:
        # Extract job_id from path parameters
        job_id = event.get('pathParameters', {}).get('job_id')

        # Extract section from query parameters (optional)
        section = event.get('queryStringParameters', {}).get('section') if event.get('queryStringParameters') else None

        if not job_id:
            return error_response(400, 'Missing job_id in path')

        # Parse job_id to extract account and app
        # Format: ca2_job_{account}_{app}_{timestamp}_{uuid}
        parts = job_id.split('_')
        if len(parts) < 5 or parts[0] != 'ca2' or parts[1] != 'job':
            return error_response(400, f'Invalid job_id format: {job_id}')

        scout_account_id = parts[2]
        timestamp_idx = -2
        application_name = '_'.join(parts[3:timestamp_idx])

        print(f"Results request for job: {job_id}, section: {section}")

        # Read static_analysis.json from artifacts
        artifacts_key = f"{scout_account_id}/{application_name}/code_analysis_v2/jobs/{job_id}/artifacts/static_analysis.json"

        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=artifacts_key)
            analysis_data = json.loads(response['Body'].read().decode('utf-8'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return error_response(404, f'Results not found for job: {job_id}. Analysis may still be in progress.')
            raise

        # If section is specified, return only that section
        if section:
            # Special handling for analysis_text - concatenate all files
            if section == 'analysis_text':
                combined_analysis = []

                if 'files' in analysis_data and isinstance(analysis_data['files'], list):
                    for file_data in analysis_data['files']:
                        if 'ai_analysis' in file_data and 'analysis_text' in file_data['ai_analysis']:
                            program_id = file_data.get('program_id', 'Unknown')
                            analysis_text = file_data['ai_analysis']['analysis_text']

                            combined_analysis.append(f"# COBOL Code Analysis for {program_id}\n\n{analysis_text}")

                # Join all analyses with separator
                full_analysis = "\n\n---\n\n".join(combined_analysis)

                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'job_id': job_id,
                        'data': full_analysis
                    }, indent=2)
                }

            # Direct section access for other sections
            if section in analysis_data:
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'job_id': job_id,
                        'data': analysis_data[section]
                    }, indent=2)
                }
            else:
                return error_response(404, f'Section "{section}" not found in results. Available sections: {", ".join(analysis_data.keys())}')

        # Return complete results with metadata
        response_data = {
            'job_id': job_id,
            'analysis_completed_at': analysis_data.get('generated_at'),
            'report_location': artifacts_key,
            'report_data': analysis_data,
            'available_sections': list(analysis_data.keys()),
            'summary': analysis_data.get('summary', {})
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data, indent=2)
        }

    except Exception as e:
        print(f"Error getting job results: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Internal server error: {str(e)}")


def error_response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': message})
    }
