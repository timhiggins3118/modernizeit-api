"""
Discovery V2 - Roadmap Generator Handler
Lambda: DiscoveryV2RoadmapGenerator

Purpose: Generate phased migration roadmap with dependencies, effort estimates, and risks

V2 Design Principles:
- Reads all previous analysis artifacts
- Creates actionable phased roadmap
- Independent Lambda (NO code sharing)
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate Migration Roadmap

    Input (from Step Functions):
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "total_phases": 5,
        "output_file": "s3://.../migration_roadmap.json"
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Generating migration roadmap for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'roadmap_generation', 95, 'Generating migration roadmap')

        # Read all analysis artifacts
        artifacts_prefix = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/"

        business_processes = read_json_file(f"{artifacts_prefix}business_processes.json")
        integration_points = read_json_file(f"{artifacts_prefix}integration_points.json")
        api_patterns = read_json_file(f"{artifacts_prefix}api_patterns.json")
        roi_analysis = read_json_file(f"{artifacts_prefix}roi_analysis.json")

        # Generate phased roadmap
        roadmap_data = generate_roadmap(
            business_processes=business_processes,
            integration_points=integration_points,
            api_patterns=api_patterns,
            roi_analysis=roi_analysis
        )

        roadmap_data['generated_at'] = datetime.now(timezone.utc).isoformat()
        roadmap_data['source_job_id'] = job_id

        # Save to S3
        output_key = f"{artifacts_prefix}migration_roadmap.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(roadmap_data, indent=2),
            ContentType='application/json'
        )

        print(f"Saved migration roadmap to s3://{BUCKET_NAME}/{output_key}")
        print(f"Total phases: {len(roadmap_data['phases'])}, Duration: {roadmap_data['overall_duration_months']} months")

        # Update status
        update_status(status_key, 'running', 'roadmap_generation', 98, f'Roadmap generated: {len(roadmap_data["phases"])} phases')

        return {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'total_phases': len(roadmap_data['phases']),
            'output_file': f's3://{BUCKET_NAME}/{output_key}'
        }

    except Exception as e:
        print(f"ERROR in DiscoveryV2RoadmapGenerator: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def generate_roadmap(business_processes: Dict, integration_points: Dict, api_patterns: Dict, roi_analysis: Dict) -> Dict[str, Any]:
    """Generate phased migration roadmap"""

    # Extract data
    processes = business_processes.get('business_processes', [])
    integrations = integration_points.get('integration_points', [])
    primary_pattern = api_patterns.get('primary_api_pattern', 'unknown')

    # Sort processes by modernization priority
    sorted_processes = sorted(processes, key=lambda x: x.get('modernization_priority', 99))

    # Create phases
    phases = []

    # Phase 1: Foundation & Quick Wins (Low complexity, isolated components)
    phase1_components = [
        p for p in sorted_processes
        if p.get('business_value') in ['Low', 'Medium'] and
        p.get('execution_frequency') in ['Batch', 'Daily', 'Weekly']
    ][:2]  # Max 2 components

    if phase1_components:
        phases.append({
            'phase': 1,
            'name': 'Foundation & Quick Wins',
            'duration_months': 3,
            'start_month': 1,
            'end_month': 3,
            'components': [
                {
                    'component': comp['process_name'],
                    'programs': comp.get('components_involved', []),
                    'modernization_approach': comp.get('recommended_approach', 'Serverless Function'),
                    'rationale': 'Low complexity, isolated, good learning opportunity',
                    'estimated_effort_weeks': 4,
                    'estimated_cost_usd': 35000
                }
                for comp in phase1_components
            ],
            'deliverables': [
                'Initial AWS infrastructure setup',
                'CI/CD pipeline established',
                'Monitoring and logging infrastructure',
                'Team training on AWS services'
            ],
            'success_criteria': [
                'Components running successfully on AWS',
                'Performance equal or better than legacy',
                'Cost savings validated'
            ],
            'dependencies': [],
            'risks': [
                {
                    'risk': 'Team learning curve with AWS',
                    'mitigation': 'AWS training, hands-on workshops, pair programming',
                    'severity': 'Low'
                }
            ],
            'cost_usd': len(phase1_components) * 35000
        })

    # Phase 2: Database Migration (Required for subsequent phases)
    db_integrations = [i for i in integrations if i.get('integration_type') == 'Database']

    if db_integrations:
        phases.append({
            'phase': 2,
            'name': 'Database Migration',
            'duration_months': 4,
            'start_month': 4,
            'end_month': 7,
            'components': [
                {
                    'component': f"{integ['system_name']} Migration",
                    'modernization_approach': integ['modernization_recommendation']['aws_service'],
                    'rationale': 'Foundational for subsequent application migrations',
                    'estimated_effort_weeks': integ['modernization_recommendation']['estimated_effort_weeks'],
                    'estimated_cost_usd': integ['modernization_recommendation']['estimated_effort_weeks'] * 10000
                }
                for integ in db_integrations
            ],
            'deliverables': [
                'Schema migrated to AWS managed database',
                'Data migrated with validation',
                'Dual-write pattern for transition period',
                'Rollback plan tested'
            ],
            'success_criteria': [
                'Data integrity validated (100% match)',
                'Query performance equal or better',
                'Zero data loss during migration'
            ],
            'dependencies': ['Phase 1 CI/CD pipeline'],
            'risks': [
                {
                    'risk': 'Data inconsistency during migration',
                    'mitigation': 'Dual-write pattern with reconciliation process',
                    'severity': 'High'
                }
            ],
            'cost_usd': sum(integ['modernization_recommendation']['estimated_effort_weeks'] * 10000 for integ in db_integrations)
        })

    # Phase 3: Core Transaction Processing (High-value real-time processes)
    phase3_components = [
        p for p in sorted_processes
        if p.get('business_value') == 'High' and
        p.get('execution_frequency') == 'Real-time'
    ][:3]  # Max 3 components

    if phase3_components:
        phases.append({
            'phase': 3,
            'name': 'Core Transaction Processing',
            'duration_months': 6,
            'start_month': 8,
            'end_month': 13,
            'components': [
                {
                    'component': comp['process_name'],
                    'programs': comp.get('components_involved', []),
                    'modernization_approach': 'API Gateway + Lambda or ECS Fargate',
                    'rationale': 'High-value, business critical functionality',
                    'estimated_effort_weeks': 12,
                    'estimated_cost_usd': 140000
                }
                for comp in phase3_components
            ],
            'deliverables': [
                'Core APIs deployed and tested',
                'Load testing completed',
                'Legacy integration maintained (strangler pattern)',
                'Security audit passed'
            ],
            'success_criteria': [
                'API response time < 200ms (p99)',
                'Zero data corruption',
                '100% functional parity with legacy'
            ],
            'dependencies': ['Phase 2 database migration'],
            'risks': [
                {
                    'risk': 'Performance degradation under load',
                    'mitigation': 'Extensive load testing, auto-scaling configured',
                    'severity': 'Medium'
                }
            ],
            'cost_usd': len(phase3_components) * 140000
        })

    # Phase 4: Integration Layer (CICS, MQ, etc.)
    non_db_integrations = [i for i in integrations if i.get('integration_type') != 'Database']

    if non_db_integrations:
        phases.append({
            'phase': 4,
            'name': 'Integration Layer Modernization',
            'duration_months': 3,
            'start_month': 14,
            'end_month': 16,
            'components': [
                {
                    'component': f"{integ['system_name']} Replacement",
                    'modernization_approach': integ['modernization_recommendation']['aws_service'],
                    'rationale': 'Eliminate mainframe dependencies',
                    'estimated_effort_weeks': integ['modernization_recommendation']['estimated_effort_weeks'],
                    'estimated_cost_usd': integ['modernization_recommendation']['estimated_effort_weeks'] * 10000
                }
                for integ in non_db_integrations
            ],
            'deliverables': [
                'Legacy integrations replaced with AWS services',
                'Message queues migrated to SQS/SNS',
                'Transaction processing on AWS'
            ],
            'success_criteria': [
                'All integration points functional',
                'No dependency on mainframe middleware',
                'Performance maintained'
            ],
            'dependencies': ['Phase 3 core APIs'],
            'risks': [
                {
                    'risk': 'Integration compatibility issues',
                    'mitigation': 'Thorough integration testing, adapter pattern if needed',
                    'severity': 'Medium'
                }
            ],
            'cost_usd': sum(integ['modernization_recommendation']['estimated_effort_weeks'] * 10000 for integ in non_db_integrations)
        })

    # Phase 5: Decommissioning & Optimization
    phases.append({
        'phase': 5,
        'name': 'Mainframe Decommissioning & Optimization',
        'duration_months': 2,
        'start_month': 17,
        'end_month': 18,
        'components': [
            {
                'component': 'Mainframe Decommissioning',
                'modernization_approach': 'Complete migration validation and cutover',
                'rationale': 'Realize full cost savings',
                'estimated_effort_weeks': 4,
                'estimated_cost_usd': 40000
            },
            {
                'component': 'AWS Cost Optimization',
                'modernization_approach': 'Right-sizing, Reserved Instances, Savings Plans',
                'rationale': 'Maximize ROI',
                'estimated_effort_weeks': 2,
                'estimated_cost_usd': 20000
            }
        ],
        'deliverables': [
            'Mainframe fully decommissioned',
            'All workloads on AWS',
            'Cost optimization implemented',
            'Documentation completed'
        ],
        'success_criteria': [
            'Zero workloads on mainframe',
            'Cost savings targets met',
            'Performance SLAs met',
            'Team fully trained on AWS'
        ],
        'dependencies': ['Phase 4 integration layer'],
        'risks': [
            {
                'risk': 'Unexpected legacy dependencies',
                'mitigation': 'Comprehensive dependency mapping, gradual cutover',
                'severity': 'Low'
            }
        ],
        'cost_usd': 60000
    })

    # Calculate totals
    total_duration = max([p['end_month'] for p in phases]) if phases else 0
    total_cost = sum([p['cost_usd'] for p in phases])

    return {
        'recommended_approach': 'Phased Hybrid Migration (Strangler Fig Pattern)',
        'overall_duration_months': total_duration,
        'total_estimated_cost_usd': total_cost,
        'migration_strategy': 'Incrementally replace legacy components while maintaining system availability',
        'phases': phases,
        'success_factors': [
            'Executive sponsorship and committed budget',
            'Dedicated modernization team',
            'AWS expertise (in-house or consulting)',
            'Comprehensive testing at each phase',
            'Change management and user training',
            'Continuous monitoring and optimization'
        ],
        'key_risks': [
            {
                'category': 'Technical',
                'description': 'Unforeseen technical complexities',
                'mitigation': 'Proof of concept for high-risk components, agile approach'
            },
            {
                'category': 'Organizational',
                'description': 'Resistance to change',
                'mitigation': 'Change management program, stakeholder engagement'
            },
            {
                'category': 'Financial',
                'description': 'Budget overruns',
                'mitigation': 'Phased approach allows stopping/adjusting, contingency buffer'
            }
        ]
    }


def read_json_file(s3_key: str) -> Dict[str, Any]:
    """Read JSON file from S3"""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        return json.loads(response['Body'].read())
    except s3_client.exceptions.NoSuchKey:
        print(f"WARNING: File not found: {s3_key}")
        return {}
    except Exception as e:
        print(f"ERROR reading {s3_key}: {str(e)}")
        return {}


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
