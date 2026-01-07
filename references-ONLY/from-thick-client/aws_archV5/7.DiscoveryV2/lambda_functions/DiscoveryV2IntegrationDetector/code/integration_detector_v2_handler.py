"""
Discovery V2 - Integration Detector Handler
Lambda: DiscoveryV2IntegrationDetector

Purpose: Detect and catalog all external system integration points

V2 Design Principles:
- Runs in parallel with Business Process Extractor and API Pattern Analyzer
- Detects DB2, CICS, MQ, VSAM, APIs, etc.
- Maps to AWS modernization strategies
- Independent Lambda (NO code sharing)
"""

import json
import boto3
import re
from datetime import datetime, timezone
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Detect Integration Points

    Input (from Step Functions - Parallel state):
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "integration_points_count": 8,
        "output_file": "s3://.../integration_points.json"
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Detecting integration points for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'integration_detection', 65, 'Detecting integration points')

        # Read AI discovery analysis
        ai_analysis_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/ai_discovery_analysis.json"

        try:
            ai_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=ai_analysis_key)
            ai_data = json.loads(ai_response['Body'].read())
        except s3_client.exceptions.NoSuchKey:
            raise Exception(f"AI analysis not found at s3://{BUCKET_NAME}/{ai_analysis_key}")

        # Detect integration points from all file analyses
        all_integrations = []
        integration_id_counter = 1

        for file_analysis in ai_data.get('file_analyses', []):
            file_path = file_analysis['file_path']
            analysis = file_analysis.get('analysis', {})

            # Parse integration points from raw analysis
            raw_analysis = analysis.get('raw_analysis', '')

            # Detect integration points
            integrations = detect_integrations_from_text(raw_analysis, file_path)

            for integration in integrations:
                integration['integration_id'] = f"int_{integration_id_counter:03d}"
                integration_id_counter += 1
                all_integrations.append(integration)

        # Consolidate duplicate integrations
        consolidated_integrations = consolidate_integrations(all_integrations)

        # Calculate summary
        summary = calculate_summary(consolidated_integrations)

        # Create output
        output_data = {
            'integration_points': consolidated_integrations,
            'summary': summary,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id
        }

        # Save to S3
        output_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/integration_points.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(output_data, indent=2),
            ContentType='application/json'
        )

        print(f"Saved integration points to s3://{BUCKET_NAME}/{output_key}")
        print(f"Detected {len(consolidated_integrations)} integration points")

        # Update status
        update_status(status_key, 'running', 'integration_detection', 70, f'Detected {len(consolidated_integrations)} integration points')

        return {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'integration_points_count': len(consolidated_integrations),
            'output_file': f's3://{BUCKET_NAME}/{output_key}'
        }

    except Exception as e:
        print(f"ERROR in DiscoveryV2IntegrationDetector: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def detect_integrations_from_text(raw_analysis: str, file_path: str) -> List[Dict[str, Any]]:
    """
    Detect integration points from AI analysis by parsing Claude's structured response
    """

    integrations = []

    # Parse Integration Points section from AI analysis
    int_section = extract_section(raw_analysis, r'\*\*Integration Points\*\*', r'\*\*API Pattern Analysis\*\*')

    if not int_section:
        return []

    # Extract each integration type
    integration_types = {
        'Database connections': 'Database',
        'Transaction managers': 'Transaction Manager',
        'Messaging systems': 'Messaging',
        'File systems': 'File System',
        'External APIs or web services': 'API'
    }

    for integration_label, integration_type in integration_types.items():
        # Extract detected systems for this type
        detected_systems = extract_integration_systems(int_section, integration_label)

        if detected_systems and detected_systems != ['None detected']:
            for system_name in detected_systems:
                # Extract AWS recommendation for this integration
                aws_recommendation = extract_aws_recommendation(int_section, system_name)

                # Determine complexity based on integration type
                complexity = determine_integration_complexity(integration_type, system_name)

                # Estimate effort
                effort_weeks = estimate_migration_effort(integration_type, complexity)

                # Determine access pattern
                access_pattern = determine_access_pattern(integration_type, raw_analysis)

                integration = {
                    'integration_type': integration_type,
                    'system_name': system_name,
                    'description': f"{system_name} {integration_type.lower()} integration",
                    'access_pattern': access_pattern,
                    'programs_using': [file_path],
                    'detected_in_analysis': True,
                    'modernization_recommendation': {
                        'aws_service': aws_recommendation if aws_recommendation else map_to_aws_service(system_name, integration_type),
                        'migration_approach': determine_migration_approach(integration_type, system_name),
                        'estimated_effort_weeks': effort_weeks,
                        'complexity': complexity
                    }
                }

                integrations.append(integration)

    return integrations


def extract_section(text: str, start_pattern: str, end_pattern: str) -> str:
    """Extract text between two regex patterns"""
    try:
        start_match = re.search(start_pattern, text, re.IGNORECASE)
        if not start_match:
            return ""

        start_pos = start_match.end()
        end_match = re.search(end_pattern, text[start_pos:], re.IGNORECASE)

        if end_match:
            return text[start_pos:start_pos + end_match.start()]
        else:
            return text[start_pos:]
    except:
        return ""


def extract_integration_systems(text: str, integration_label: str) -> List[str]:
    """Extract system names from integration points section"""
    systems = []
    try:
        # Find the line with this integration type
        pattern = re.escape(integration_label) + r':\s*(.+?)(?:\n|$)'
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            systems_text = match.group(1).strip()

            # Check for "None detected"
            if 'none detected' in systems_text.lower():
                return ['None detected']

            # Split by comma or "and"
            systems_list = re.split(r',\s*|\s+and\s+', systems_text)
            systems = [s.strip() for s in systems_list if s.strip()]
    except:
        pass

    return systems


def extract_aws_recommendation(text: str, system_name: str) -> str:
    """Extract AWS service recommendation from text"""
    # Look for AWS service mentioned near the system name
    try:
        # Search for common AWS service patterns
        aws_services = [
            'RDS', 'DynamoDB', 'S3', 'Lambda', 'API Gateway', 'SQS', 'SNS',
            'EventBridge', 'Step Functions', 'ECS', 'Fargate', 'Aurora'
        ]

        # Look in vicinity of system mention
        system_index = text.lower().find(system_name.lower())
        if system_index >= 0:
            context = text[max(0, system_index-200):min(len(text), system_index+400)]

            for service in aws_services:
                if service.lower() in context.lower():
                    return service
    except:
        pass

    return ""


def map_to_aws_service(system_name: str, integration_type: str) -> str:
    """Map legacy system to AWS service"""
    mappings = {
        'DB2': 'Amazon RDS PostgreSQL',
        'CICS': 'API Gateway + Lambda',
        'MQ': 'Amazon SQS',
        'VSAM': 'Amazon DynamoDB',
        'IMS': 'Amazon RDS',
        'QSAM': 'Amazon S3',
        'API': 'API Gateway'
    }

    # Check for exact match
    for key, value in mappings.items():
        if key.lower() in system_name.lower():
            return value

    # Fallback based on type
    type_mappings = {
        'Database': 'Amazon RDS',
        'File System': 'Amazon S3',
        'Messaging': 'Amazon SQS',
        'Transaction Manager': 'AWS Lambda',
        'API': 'API Gateway'
    }

    return type_mappings.get(integration_type, 'AWS Service')


def determine_integration_complexity(integration_type: str, system_name: str) -> str:
    """Determine migration complexity"""
    high_complexity = ['CICS', 'IMS DC', 'Custom', 'Mainframe']
    medium_complexity = ['DB2', 'MQ', 'IMS DB']

    if any(hc.lower() in system_name.lower() for hc in high_complexity):
        return 'High'
    elif any(mc.lower() in system_name.lower() for mc in medium_complexity):
        return 'Medium'
    else:
        return 'Low'


def estimate_migration_effort(integration_type: str, complexity: str) -> int:
    """Estimate migration effort in weeks"""
    effort_matrix = {
        ('Database', 'High'): 6,
        ('Database', 'Medium'): 4,
        ('Database', 'Low'): 2,
        ('Transaction Manager', 'High'): 8,
        ('Transaction Manager', 'Medium'): 6,
        ('Transaction Manager', 'Low'): 4,
        ('Messaging', 'High'): 4,
        ('Messaging', 'Medium'): 3,
        ('Messaging', 'Low'): 2,
        ('File System', 'High'): 3,
        ('File System', 'Medium'): 2,
        ('File System', 'Low'): 1,
        ('API', 'High'): 5,
        ('API', 'Medium'): 3,
        ('API', 'Low'): 2
    }

    return effort_matrix.get((integration_type, complexity), 4)


def determine_access_pattern(integration_type: str, raw_analysis: str) -> str:
    """Determine access pattern from analysis"""
    if 'asynchronous' in raw_analysis.lower() or 'async' in raw_analysis.lower():
        return 'Asynchronous'
    elif 'real-time' in raw_analysis.lower() or 'synchronous' in raw_analysis.lower():
        return 'Synchronous'
    elif integration_type in ['Messaging']:
        return 'Asynchronous'
    elif integration_type in ['Database', 'Transaction Manager']:
        return 'Synchronous'
    else:
        return 'Mixed'


def determine_migration_approach(integration_type: str, system_name: str) -> str:
    """Determine migration approach based on integration type"""
    approaches = {
        'DB2': 'AWS DMS + Schema Conversion Tool',
        'CICS': 'Microservices refactoring to REST APIs',
        'MQ': 'Message queue replacement with SQS/SNS',
        'VSAM': 'Data migration to DynamoDB or S3',
        'IMS': 'Database migration with AWS DMS',
        'QSAM': 'File migration to S3 with Lambda processing',
        'API': 'API Gateway integration'
    }

    for key, value in approaches.items():
        if key.lower() in system_name.lower():
            return value

    # Fallback
    type_approaches = {
        'Database': 'AWS Database Migration Service',
        'File System': 'Data migration to S3',
        'Messaging': 'Queue replacement with SQS',
        'Transaction Manager': 'Microservices refactoring',
        'API': 'API Gateway integration'
    }

    return type_approaches.get(integration_type, 'Cloud migration')


def consolidate_integrations(all_integrations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Consolidate duplicate integrations with same system"""

    # Group by system_name
    grouped = {}

    for integration in all_integrations:
        system_name = integration['system_name']

        if system_name not in grouped:
            grouped[system_name] = integration
        else:
            # Merge programs_using
            existing_programs = set(grouped[system_name]['programs_using'])
            new_programs = set(integration['programs_using'])
            grouped[system_name]['programs_using'] = list(existing_programs | new_programs)

    # Convert back to list
    consolidated = list(grouped.values())

    # Sort by complexity (High → Low)
    complexity_order = {'High': 0, 'Medium': 1, 'Low': 2}
    consolidated.sort(key=lambda x: complexity_order.get(x['modernization_recommendation']['complexity'], 99))

    # Assign integration IDs
    for i, integration in enumerate(consolidated):
        integration['integration_id'] = f"int_{i+1:03d}"

    return consolidated


def calculate_summary(integrations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate summary statistics"""

    total = len(integrations)

    by_type = {}
    for integration in integrations:
        int_type = integration['integration_type']
        by_type[int_type] = by_type.get(int_type, 0) + 1

    high_complexity = len([i for i in integrations if i['modernization_recommendation']['complexity'] == 'High'])
    medium_complexity = len([i for i in integrations if i['modernization_recommendation']['complexity'] == 'Medium'])
    low_complexity = len([i for i in integrations if i['modernization_recommendation']['complexity'] == 'Low'])

    total_effort_weeks = sum(i['modernization_recommendation']['estimated_effort_weeks'] for i in integrations)

    return {
        'total_integration_points': total,
        'by_type': by_type,
        'high_complexity_count': high_complexity,
        'medium_complexity_count': medium_complexity,
        'low_complexity_count': low_complexity,
        'total_migration_effort_weeks': total_effort_weeks
    }


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
        status_data['status'] = status
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
