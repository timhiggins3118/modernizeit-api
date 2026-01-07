#!/usr/bin/env python3
"""
Data Analyzer V2 - Results API Handler
Returns ERD and data analysis results with optional section filtering
GET /resultsda2/{job_id}?section=erd
"""

import json
import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    Return data analysis results for a job
    GET /resultsda2/{job_id}
    GET /resultsda2/{job_id}?section=erd
    """

    try:
        job_id = event.get('pathParameters', {}).get('job_id')

        if not job_id:
            return error_response(400, 'Missing job_id')

        # Parse job_id: da2_job_{account}_{app}_{timestamp}_{uuid}
        parts = job_id.split('_')

        if len(parts) < 6 or parts[0] != 'da2' or parts[1] != 'job':
            return error_response(400, 'Invalid job_id format')

        scout_account_id = parts[2]
        timestamp_idx = -2
        application_name = '_'.join(parts[3:timestamp_idx])

        base_path = f"{scout_account_id}/{application_name}"
        job_path = f"{base_path}/data_analysis_v2/jobs/{job_id}"

        # Read all result files
        erd_key = f"{job_path}/artifacts/erd.json"
        lineage_key = f"{job_path}/artifacts/data_lineage.json"
        copybook_key = f"{job_path}/artifacts/copybook_analysis.json"

        try:
            erd_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=erd_key)
            erd_data = json.loads(erd_response['Body'].read().decode('utf-8'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return error_response(404, f'Results not found for job: {job_id}. ERD generation may still be in progress.')
            raise

        lineage_data = {}
        try:
            lineage_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=lineage_key)
            lineage_data = json.loads(lineage_response['Body'].read().decode('utf-8'))
        except ClientError:
            pass

        copybook_data = {}
        try:
            copybook_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=copybook_key)
            copybook_data = json.loads(copybook_response['Body'].read().decode('utf-8'))
        except ClientError:
            pass

        # Check for section filter
        section_filter = None
        query_params = event.get('queryStringParameters')
        if query_params and 'section' in query_params:
            section_filter = query_params['section']

        # If section filter specified, return only that section
        if section_filter:
            # Special handling for analysis_text - generate comprehensive markdown report
            if section_filter == 'analysis_text':
                markdown_report = generate_data_analysis_report(erd_data, lineage_data, copybook_data, job_id)

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

            available_sections = ['erd', 'data_lineage', 'copybooks', 'summary']

            if section_filter not in available_sections:
                return error_response(400, f'Invalid section. Available: {", ".join(available_sections)}')

            if section_filter == 'erd':
                section_data = erd_data
            elif section_filter == 'data_lineage':
                section_data = lineage_data
            elif section_filter == 'copybooks':
                section_data = copybook_data
            elif section_filter == 'summary':
                section_data = {
                    'entities': erd_data.get('summary', {}),
                    'lineage_flows': lineage_data.get('summary', {}),
                    'copybooks': copybook_data.get('summary', {})
                }
            else:
                return error_response(404, f'Section "{section_filter}" not found')

            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'job_id': job_id,
                    'section': section_filter,
                    'data': section_data
                })
            }

        # Return complete results
        response_data = {
            'job_id': job_id,
            'analysis_completed_at': erd_data.get('generated_at'),
            'report_location': erd_key,
            'report_data': {
                'erd': erd_data,
                'data_lineage': lineage_data,
                'copybook_analysis': copybook_data
            },
            'available_sections': ['erd', 'data_lineage', 'copybooks', 'summary']
        }

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(response_data)
        }

    except Exception as e:
        print(f"Error retrieving results: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f'Internal error: {str(e)}')


def generate_data_analysis_report(erd_data, lineage_data, copybook_data, job_id):
    """
    Generate comprehensive data analysis report in markdown format
    Includes ERD, relationships, data lineage, and copybook analysis
    """
    lines = []

    # Header
    lines.append("# COBOL Data Analysis Report")
    lines.append("")
    lines.append(f"**Job ID:** {job_id}")
    lines.append(f"**Generated:** {erd_data.get('generated_at', 'N/A')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")

    erd_summary = erd_data.get('summary', {})
    lineage_summary = lineage_data.get('summary', {}) if lineage_data else {}
    copybook_summary = copybook_data.get('summary', {}) if copybook_data else {}

    lines.append(f"- **Total Entities:** {erd_summary.get('total_entities', 0)}")
    lines.append(f"- **Total Relationships:** {erd_summary.get('total_relationships', 0)}")
    lines.append(f"- **Data Lineage Flows:** {lineage_summary.get('total_flows', 0)}")
    lines.append(f"- **Copybooks Analyzed:** {copybook_summary.get('total_copybooks', 0)}")
    lines.append("")

    # Confidence distribution
    confidence_dist = erd_summary.get('confidence_distribution', {})
    if confidence_dist:
        lines.append("**Confidence Distribution:**")
        lines.append(f"- High: {confidence_dist.get('high', 0)}")
        lines.append(f"- Medium: {confidence_dist.get('medium', 0)}")
        lines.append(f"- Low: {confidence_dist.get('low', 0)}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Entity Relationship Diagram
    entities = erd_data.get('entities', [])
    if entities:
        lines.append("## Entity Relationship Diagram")
        lines.append("")
        lines.append(f"**{len(entities)} Entities Discovered**")
        lines.append("")

        for entity in entities:
            entity_name = entity.get('entity_name', 'Unknown')
            business_purpose = entity.get('business_purpose', 'N/A')
            confidence = entity.get('confidence_score', 'N/A')
            source_files = entity.get('source_files', [])

            lines.append(f"### {entity_name}")
            lines.append("")
            lines.append(f"**Business Purpose:** {business_purpose}")
            lines.append(f"**Confidence:** {confidence}")
            lines.append(f"**Source Files:** {', '.join(source_files) if source_files else 'N/A'}")
            lines.append("")

            # Attributes
            attributes = entity.get('attributes', [])
            if attributes:
                lines.append("**Attributes:**")
                lines.append("")
                lines.append("| Attribute | Data Type | Business Meaning | COBOL Field |")
                lines.append("|-----------|-----------|------------------|-------------|")

                for attr in attributes:
                    attr_name = attr.get('attribute_name', 'N/A')
                    data_type = attr.get('data_type', 'N/A')
                    business_meaning = attr.get('business_meaning', 'N/A')
                    cobol_field = attr.get('cobol_field_mapping', 'N/A')

                    lines.append(f"| {attr_name} | {data_type} | {business_meaning} | {cobol_field} |")

                lines.append("")

            lines.append("---")
            lines.append("")

    # Relationships
    relationships = erd_data.get('relationships', [])
    if relationships:
        lines.append("## Entity Relationships")
        lines.append("")
        lines.append(f"**{len(relationships)} Relationships Identified**")
        lines.append("")

        for idx, rel in enumerate(relationships, 1):
            from_entity = rel.get('from_entity', 'N/A')
            to_entity = rel.get('to_entity', 'N/A')
            relationship_type = rel.get('relationship_type', 'N/A')
            cardinality = rel.get('cardinality', 'N/A')
            business_rule = rel.get('business_rule', 'N/A')

            lines.append(f"### Relationship {idx}: {from_entity} → {to_entity}")
            lines.append("")
            lines.append(f"- **Type:** {relationship_type}")
            lines.append(f"- **Cardinality:** {cardinality}")
            lines.append(f"- **Business Rule:** {business_rule}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Data Lineage
    if lineage_data:
        flows = lineage_data.get('flows', [])
        if flows:
            lines.append("## Data Lineage Analysis")
            lines.append("")
            lines.append(f"**{len(flows)} Data Flows Traced**")
            lines.append("")

            for flow in flows:
                flow_id = flow.get('flow_id', 'N/A')
                source = flow.get('source', {})
                destination = flow.get('destination', {})
                transformations = flow.get('transformations', [])

                lines.append(f"### Flow: {flow_id}")
                lines.append("")
                lines.append(f"**Source:** {source.get('file', 'N/A')} - {source.get('field', 'N/A')}")
                lines.append(f"**Destination:** {destination.get('file', 'N/A')} - {destination.get('field', 'N/A')}")
                lines.append("")

                if transformations:
                    lines.append("**Transformations:**")
                    for trans in transformations:
                        trans_type = trans.get('type', 'N/A')
                        description = trans.get('description', 'N/A')
                        lines.append(f"- **{trans_type}:** {description}")
                    lines.append("")

                lines.append("---")
                lines.append("")

    # Copybook Analysis
    if copybook_data:
        copybooks = copybook_data.get('copybooks', [])
        if copybooks:
            lines.append("## Copybook Analysis")
            lines.append("")
            lines.append(f"**{len(copybooks)} Copybooks Analyzed**")
            lines.append("")

            for copybook in copybooks:
                copybook_name = copybook.get('name', 'Unknown')
                purpose = copybook.get('purpose', 'N/A')
                used_by = copybook.get('used_by', [])
                fields = copybook.get('fields', [])

                lines.append(f"### {copybook_name}")
                lines.append("")
                lines.append(f"**Purpose:** {purpose}")
                lines.append(f"**Used By:** {', '.join(used_by) if used_by else 'N/A'}")
                lines.append("")

                if fields:
                    lines.append("**Fields:**")
                    for field in fields:
                        field_name = field.get('name', 'N/A')
                        field_type = field.get('type', 'N/A')
                        lines.append(f"- `{field_name}` ({field_type})")
                    lines.append("")

                lines.append("---")
                lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by Cobalt ETL Studio - Data Analysis V2*")

    return "\n".join(lines)


def error_response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps({'error': message})
    }
