#!/usr/bin/env python3
"""
Code Refactor V2 - Results API Handler V2
Returns refactoring recipes with optional section filtering
"""

import json
import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    Return refactor recipes for a job
    GET /resultsrf2/{job_id}
    GET /resultsrf2/{job_id}?section=summary
    """

    try:
        # Extract job_id from path parameters
        job_id = event.get('pathParameters', {}).get('job_id')

        if not job_id:
            return error_response(400, 'Missing job_id')

        # Parse job_id: rf2_job_{account}_{app}_{timestamp}_{uuid}
        parts = job_id.split('_')

        if len(parts) < 6 or parts[0] != 'rf2' or parts[1] != 'job':
            return error_response(400, 'Invalid job_id format')

        scout_account_id = parts[2]

        # Find timestamp (second to last)
        timestamp_idx = -2
        application_name = '_'.join(parts[3:timestamp_idx])

        base_path = f"{scout_account_id}/{application_name}/code_refactor_v2/jobs/{job_id}"

        # Read refactor_recipes.json
        recipes_key = f"{base_path}/artifacts/refactor_recipes.json"

        try:
            recipes_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=recipes_key)
            recipes_data = json.loads(recipes_response['Body'].read().decode('utf-8'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return error_response(404, f'Results not found for job: {job_id}. Recipe generation may still be in progress.')
            raise

        # Check for section filter
        section_filter = None
        query_params = event.get('queryStringParameters')
        if query_params and 'section' in query_params:
            section_filter = query_params['section']

        # If section filter specified, return only that section
        if section_filter:
            # Special handling for analysis_text - generate markdown report
            if section_filter == 'analysis_text':
                markdown_report = generate_markdown_report(recipes_data, job_id)

                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'job_id': job_id,
                        'data': markdown_report
                    }, indent=2)
                }

            available_sections = ['summary', 'recipes', 'dependencies', 'pattern_sources_used']

            if section_filter not in available_sections:
                return error_response(400, f'Invalid section. Available: {", ".join(available_sections)}')

            section_data = recipes_data.get(section_filter)

            if section_data is None:
                return error_response(404, f'Section "{section_filter}" not found')

            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'job_id': job_id,
                    'section': section_filter,
                    'data': section_data
                })
            }

        # Return complete results
        response_data = {
            'job_id': job_id,
            'recipe_generated_at': recipes_data.get('generated_at'),
            'report_location': recipes_key,
            'recipe_data': recipes_data,
            'available_sections': ['summary', 'recipes', 'dependencies', 'pattern_sources_used']
        }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data)
        }

    except Exception as e:
        print(f"Error retrieving results: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f'Internal error: {str(e)}')


def generate_markdown_report(recipes_data, job_id):
    """
    Generate markdown report from refactor recipes
    Formats V2 structured data into V1-style markdown report
    """
    lines = []

    # Header
    lines.append("# COBOL Code Refactoring Analysis Report")
    lines.append("")
    lines.append(f"**Job ID:** {job_id}")
    lines.append(f"**Generated:** {recipes_data.get('generated_at', 'N/A')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary section
    summary = recipes_data.get('summary', {})
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Recipes:** {summary.get('total_recipes', 0)}")
    lines.append(f"- **High Confidence:** {summary.get('high_confidence_count', 0)}")
    lines.append(f"- **Medium Confidence:** {summary.get('medium_confidence_count', 0)}")
    lines.append(f"- **Low Confidence:** {summary.get('low_confidence_count', 0)}")
    lines.append("")
    lines.append(f"- **High Risk:** {summary.get('high_risk_count', 0)}")
    lines.append(f"- **Medium Risk:** {summary.get('medium_risk_count', 0)}")
    lines.append(f"- **Low Risk:** {summary.get('low_risk_count', 0)}")
    lines.append("")

    # Pattern sources
    pattern_sources = recipes_data.get('pattern_sources_used', [])
    if pattern_sources:
        lines.append("**Pattern Sources Used:**")
        for source in pattern_sources:
            lines.append(f"- {source}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Individual recipes
    recipes = recipes_data.get('recipes', [])
    if recipes:
        lines.append("## Refactoring Recommendations")
        lines.append("")

        for idx, recipe in enumerate(recipes, 1):
            lines.append(f"### Recipe {idx}: {recipe.get('type', 'Unknown')}")
            lines.append("")
            lines.append(f"**Target:** {recipe.get('target', 'N/A')}")
            lines.append(f"**Pattern Detected:** {recipe.get('pattern_detected', 'N/A')}")
            lines.append(f"**Confidence:** {recipe.get('confidence', 'N/A')}")
            lines.append(f"**Risk Level:** {recipe.get('risk_level', 'N/A')}")
            lines.append("")

            # Rationale
            rationale = recipe.get('rationale', '')
            if rationale:
                lines.append("**Rationale:**")
                lines.append("")
                lines.append(rationale)
                lines.append("")

            # Transformation details if present
            transformation = recipe.get('transformation', {})
            if transformation:
                lines.append("**Transformation:**")
                lines.append("")
                lines.append(f"- **From:** {transformation.get('from', 'N/A')}")
                lines.append(f"- **To:** {transformation.get('to', 'N/A')}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # Dependencies section
    dependencies = recipes_data.get('dependencies', {})
    if dependencies:
        lines.append("## Dependencies Analysis")
        lines.append("")

        internal_deps = dependencies.get('internal', [])
        if internal_deps:
            lines.append("### Internal Dependencies")
            for dep in internal_deps:
                lines.append(f"- {dep}")
            lines.append("")

        external_deps = dependencies.get('external', [])
        if external_deps:
            lines.append("### External Dependencies")
            for dep in external_deps:
                lines.append(f"- {dep}")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by Cobalt ETL Studio - Code Refactor V2*")

    return "\n".join(lines)


def error_response(status_code, message):
    """Return error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': message})
    }
