"""
Architecture Recommender V2 - Results API Handler
Lambda: ArchitectureRecommenderV2ResultsAPI

Purpose: API handler for retrieving architecture recommendations

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
- Supports section filtering
"""

import json
import boto3
from typing import Dict, Any

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Results API Handler

    Input (from API Gateway):
    {
        "pathParameters": {
            "job_id": "ar2_job_5150_TestApp01_..."
        },
        "queryStringParameters": {
            "section": "services | database | cost | iac | security | all"
        }
    }

    Output:
    {
        "statusCode": 200,
        "body": "{...}"
    }
    """
    try:
        print("=" * 80)
        print("ARCHITECTURE RECOMMENDER V2 - RESULTS API")
        print("=" * 80)

        # Get job_id from path parameters
        path_params = event.get('pathParameters', {})
        job_id = path_params.get('job_id')

        if not job_id:
            return error_response(400, 'Missing job_id in path')

        print(f"Job ID: {job_id}")

        # Parse job_id
        parts = job_id.split('_')
        if len(parts) < 6 or not job_id.startswith('ar2_job_'):
            return error_response(400, 'Invalid job_id format')

        scout_account_id = parts[2]
        timestamp_idx = -2
        application_name = '_'.join(parts[3:timestamp_idx])

        print(f"Account: {scout_account_id}, App: {application_name}")

        # Read recommendations
        recommendations_key = f"{scout_account_id}/{application_name}/architecture_v2/jobs/{job_id}/artifacts/architecture_recommendations.json"

        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=recommendations_key)
            recommendations = json.loads(response['Body'].read().decode('utf-8'))
        except s3_client.exceptions.NoSuchKey:
            return error_response(404, f'Results not found for job: {job_id}. Architecture analysis may still be in progress.')

        # Check for section filter
        section_filter = None
        query_params = event.get('queryStringParameters')
        if query_params and 'section' in query_params:
            section_filter = query_params['section']

        print(f"Section filter: {section_filter if section_filter else 'all'}")

        # If section filter specified, return only that section
        if section_filter and section_filter != 'all':
            # Special handling for analysis_text - generate comprehensive markdown report
            if section_filter == 'analysis_text':
                markdown_report = generate_architecture_report(recommendations, job_id)

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

            available_sections = ['services', 'database', 'cost', 'iac', 'security', 'summary']

            if section_filter not in available_sections:
                return error_response(400, f'Invalid section. Available: {", ".join(available_sections)}')

            if section_filter == 'services':
                section_data = {
                    'service_mappings': recommendations.get('service_mappings', []),
                    'compute_summary': recommendations.get('compute_summary', {})
                }
            elif section_filter == 'database':
                section_data = recommendations.get('database_strategy', {})
            elif section_filter == 'cost':
                section_data = recommendations.get('cost_breakdown', {})
            elif section_filter == 'iac':
                section_data = recommendations.get('infrastructure_as_code', {})
            elif section_filter == 'security':
                section_data = recommendations.get('security_architecture', {})
            elif section_filter == 'summary':
                section_data = {
                    'summary': recommendations.get('summary', {}),
                    'migration_phases': recommendations.get('migration_phases', []),
                    'cost_total': recommendations.get('cost_breakdown', {}).get('total_monthly_usd', 0)
                }
            else:
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
                }, indent=2)
            }

        # Return complete recommendations
        response_data = {
            'job_id': job_id,
            'generated_at': recommendations.get('generated_at'),
            'recommendations': recommendations,
            'available_sections': ['services', 'database', 'cost', 'iac', 'security', 'summary', 'all']
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
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        return error_response(500, f'Internal server error: {str(e)}')


def generate_architecture_report(recommendations: Dict[str, Any], job_id: str) -> str:
    """
    Generate comprehensive architecture recommendations report in markdown format
    Includes service mappings, database strategy, cost breakdown, IaC, and migration plan
    """
    lines = []

    # Header
    lines.append("# AWS Architecture Recommendations Report")
    lines.append("")
    lines.append(f"**Job ID:** {job_id}")
    lines.append(f"**Generated:** {recommendations.get('generated_at', 'N/A')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    summary = recommendations.get('summary', {})
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- **Application Type:** {summary.get('application_type', 'N/A')}")
    lines.append(f"- **Recommended Architecture:** {summary.get('recommended_architecture', 'N/A')}")
    lines.append(f"- **Confidence:** {summary.get('confidence', 'N/A')}")
    lines.append("")

    key_characteristics = summary.get('key_characteristics', [])
    if key_characteristics:
        lines.append("**Key Characteristics:**")
        for char in key_characteristics:
            lines.append(f"- {char}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Service Mappings
    service_mappings = recommendations.get('service_mappings', [])
    if service_mappings:
        lines.append("## AWS Service Mappings")
        lines.append("")
        lines.append(f"**{len(service_mappings)} COBOL Program(s) Mapped to AWS Services**")
        lines.append("")

        for idx, mapping in enumerate(service_mappings, 1):
            cobol_program = mapping.get('cobol_program', 'Unknown')
            aws_service = mapping.get('aws_service', 'N/A')
            function_name = mapping.get('function_name', 'N/A')
            runtime = mapping.get('runtime', 'N/A')
            memory_mb = mapping.get('memory_mb', 'N/A')
            timeout_seconds = mapping.get('timeout_seconds', 'N/A')
            trigger = mapping.get('trigger', 'N/A')
            confidence = mapping.get('confidence', 'N/A')
            reasoning = mapping.get('reasoning', 'N/A')

            lines.append(f"### Mapping {idx}: {cobol_program}")
            lines.append("")
            lines.append(f"- **AWS Service:** {aws_service}")
            lines.append(f"- **Function Name:** {function_name}")
            lines.append(f"- **Runtime:** {runtime}")
            lines.append(f"- **Memory:** {memory_mb} MB")
            lines.append(f"- **Timeout:** {timeout_seconds} seconds")
            lines.append(f"- **Trigger:** {trigger}")
            lines.append(f"- **Confidence:** {confidence}")
            lines.append("")
            lines.append(f"**Reasoning:** {reasoning}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Compute Summary
    compute_summary = recommendations.get('compute_summary', {})
    if compute_summary:
        lines.append("## Compute Resource Summary")
        lines.append("")
        lines.append(f"- **Lambda Functions:** {compute_summary.get('lambda_functions', 0)}")
        lines.append(f"- **ECS Services:** {compute_summary.get('ecs_services', 0)}")
        lines.append(f"- **EC2 Instances:** {compute_summary.get('ec2_instances', 0)}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Database Strategy
    db_strategy = recommendations.get('database_strategy', {})
    if db_strategy:
        lines.append("## Database Strategy")
        lines.append("")
        lines.append(f"- **Primary Database:** {db_strategy.get('primary_database', 'N/A')}")
        lines.append(f"- **Instance Class:** {db_strategy.get('instance_class', 'N/A')}")
        lines.append(f"- **Storage:** {db_strategy.get('storage_gb', 'N/A')} GB")
        lines.append(f"- **Multi-AZ:** {'Yes' if db_strategy.get('multi_az', False) else 'No'}")
        lines.append(f"- **Confidence:** {db_strategy.get('confidence', 'N/A')}")
        lines.append(f"- **Migration Strategy:** {db_strategy.get('migration_strategy', 'N/A')}")
        lines.append("")
        lines.append(f"**Reasoning:** {db_strategy.get('reasoning', 'N/A')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # API Design
    api_design = recommendations.get('api_design', {})
    if api_design:
        lines.append("## API Design")
        lines.append("")
        lines.append(f"- **API Required:** {'Yes' if api_design.get('required', False) else 'No'}")
        lines.append(f"- **API Type:** {api_design.get('api_type', 'N/A')}")
        lines.append(f"- **Authentication:** {api_design.get('authentication', 'N/A')}")
        lines.append("")
        lines.append(f"**Reasoning:** {api_design.get('reasoning', 'N/A')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Storage Strategy
    storage_strategy = recommendations.get('storage_strategy', {})
    if storage_strategy:
        s3_buckets = storage_strategy.get('s3_buckets', [])
        if s3_buckets:
            lines.append("## Storage Strategy")
            lines.append("")
            lines.append(f"**{len(s3_buckets)} S3 Bucket(s) Required**")
            lines.append("")

            for bucket in s3_buckets:
                bucket_name = bucket.get('name', 'Unknown')
                purpose = bucket.get('purpose', 'N/A')
                storage_class = bucket.get('storage_class', 'N/A')

                lines.append(f"### {bucket_name}")
                lines.append(f"- **Purpose:** {purpose}")
                lines.append(f"- **Storage Class:** {storage_class}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # Security Architecture
    security_arch = recommendations.get('security_architecture', {})
    if security_arch:
        lines.append("## Security Architecture")
        lines.append("")
        lines.append(f"- **VPC Required:** {'Yes' if security_arch.get('vpc_required', False) else 'No'}")
        lines.append(f"- **Encryption at Rest:** {security_arch.get('encryption_at_rest', 'N/A')}")
        lines.append(f"- **Encryption in Transit:** {security_arch.get('encryption_in_transit', 'N/A')}")
        lines.append("")

        iam_roles = security_arch.get('iam_roles_needed', [])
        if iam_roles:
            lines.append("**IAM Roles Needed:**")
            for role in iam_roles:
                lines.append(f"- {role}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Migration Phases
    migration_phases = recommendations.get('migration_phases', [])
    if migration_phases:
        lines.append("## Migration Roadmap")
        lines.append("")
        lines.append(f"**{len(migration_phases)} Phase Migration Plan**")
        lines.append("")

        total_weeks = sum(phase.get('duration_weeks', 0) for phase in migration_phases)
        lines.append(f"**Total Duration:** {total_weeks} weeks (~{total_weeks/4:.1f} months)")
        lines.append("")

        for phase in migration_phases:
            phase_num = phase.get('phase', 'N/A')
            phase_name = phase.get('name', 'Unknown')
            duration_weeks = phase.get('duration_weeks', 0)
            risk = phase.get('risk', 'N/A')
            tasks = phase.get('tasks', [])

            lines.append(f"### Phase {phase_num}: {phase_name}")
            lines.append("")
            lines.append(f"- **Duration:** {duration_weeks} weeks")
            lines.append(f"- **Risk Level:** {risk}")
            lines.append("")

            if tasks:
                lines.append("**Tasks:**")
                for task in tasks:
                    lines.append(f"- {task}")
                lines.append("")

        lines.append("---")
        lines.append("")

    # Infrastructure as Code
    iac = recommendations.get('infrastructure_as_code', {})
    if iac:
        lines.append("## Infrastructure as Code")
        lines.append("")
        lines.append(f"**Format:** {iac.get('format', 'N/A')}")
        lines.append("")

        artifacts = iac.get('artifacts', [])
        if artifacts:
            lines.append("**Artifacts:**")
            for artifact in artifacts:
                lines.append(f"- `{artifact}`")
            lines.append("")

        deployment_instructions = iac.get('deployment_instructions', 'N/A')
        lines.append(f"**Deployment:** {deployment_instructions}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Cost Breakdown
    cost_breakdown = recommendations.get('cost_breakdown', {})
    if cost_breakdown:
        lines.append("## Cost Analysis")
        lines.append("")

        total_monthly = cost_breakdown.get('total_monthly_usd', 0)
        total_annual = cost_breakdown.get('total_annual_usd', 0)

        lines.append(f"**Total Monthly Cost:** ${total_monthly:,.2f} USD")
        lines.append(f"**Total Annual Cost:** ${total_annual:,.2f} USD")
        lines.append("")

        # Compute costs
        compute = cost_breakdown.get('compute', {})
        if compute:
            lines.append("### Compute Costs")
            lines.append(f"- Lambda: ${compute.get('lambda', 0):,.2f} ({compute.get('lambda_functions', 0)} functions)")
            lines.append(f"- ECS: ${compute.get('ecs', 0):,.2f} ({compute.get('ecs_services', 0)} services)")
            lines.append(f"- EC2: ${compute.get('ec2', 0):,.2f} ({compute.get('ec2_instances', 0)} instances)")
            lines.append(f"- **Subtotal:** ${compute.get('subtotal', 0):,.2f}")
            lines.append("")

        # Database costs
        database = cost_breakdown.get('database', {})
        if database:
            lines.append("### Database Costs")
            lines.append(f"- RDS: ${database.get('rds', 0):,.2f}")
            lines.append(f"- DynamoDB: ${database.get('dynamodb', 0):,.2f}")
            lines.append(f"- **Subtotal:** ${database.get('subtotal', 0):,.2f}")
            lines.append("")

        # Storage costs
        storage = cost_breakdown.get('storage', {})
        if storage:
            lines.append("### Storage Costs")
            lines.append(f"- S3: ${storage.get('s3', 0):,.2f}")
            lines.append(f"- EBS: ${storage.get('ebs', 0):,.2f}")
            lines.append(f"- **Subtotal:** ${storage.get('subtotal', 0):,.2f}")
            lines.append("")

        # Networking costs
        networking = cost_breakdown.get('networking', {})
        if networking:
            lines.append("### Networking Costs")
            lines.append(f"- Data Transfer: ${networking.get('data_transfer', 0):,.2f}")
            lines.append(f"- NAT Gateway: ${networking.get('nat_gateway', 0):,.2f}")
            lines.append(f"- **Subtotal:** ${networking.get('subtotal', 0):,.2f}")
            lines.append("")

        # Other costs
        other = cost_breakdown.get('other', {})
        if other:
            lines.append("### Other Costs")
            lines.append(f"- CloudWatch: ${other.get('cloudwatch', 0):,.2f}")
            lines.append(f"- KMS: ${other.get('kms', 0):,.2f}")
            lines.append(f"- **Subtotal:** ${other.get('subtotal', 0):,.2f}")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by Cobalt ETL Studio - Architecture Recommender V2*")

    return "\n".join(lines)


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Build error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': message})
    }
