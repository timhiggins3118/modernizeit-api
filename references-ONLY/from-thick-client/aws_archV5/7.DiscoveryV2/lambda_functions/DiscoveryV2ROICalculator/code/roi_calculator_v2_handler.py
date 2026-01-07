"""
Discovery V2 - ROI Calculator Handler
Lambda: DiscoveryV2ROICalculator

Purpose: Calculate ROI for modernization including cost savings, time savings, productivity gains

V2 Design Principles:
- Reads business_processes.json, integration_points.json, api_patterns.json
- Calculates financial metrics
- Independent Lambda (NO code sharing)
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Calculate ROI

    Input (from Step Functions):
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "total_savings_5_years": 2500000,
        "output_file": "s3://.../roi_analysis.json"
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Calculating ROI for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'roi_calculation', 85, 'Calculating ROI metrics')

        # Read business processes, integrations, and API patterns
        artifacts_prefix = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/"

        business_processes = read_json_file(f"{artifacts_prefix}business_processes.json")
        integration_points = read_json_file(f"{artifacts_prefix}integration_points.json")
        api_patterns = read_json_file(f"{artifacts_prefix}api_patterns.json")

        # Read AI analysis for total files
        ai_analysis = read_json_file(f"{artifacts_prefix}ai_discovery_analysis.json")
        total_files = ai_analysis.get('summary', {}).get('total_files_analyzed', 0)

        # Calculate ROI metrics
        roi_data = calculate_roi(
            total_files=total_files,
            business_processes=business_processes,
            integration_points=integration_points,
            api_patterns=api_patterns
        )

        roi_data['generated_at'] = datetime.now(timezone.utc).isoformat()
        roi_data['source_job_id'] = job_id

        # Save to S3
        output_key = f"{artifacts_prefix}roi_analysis.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(roi_data, indent=2),
            ContentType='application/json'
        )

        print(f"Saved ROI analysis to s3://{BUCKET_NAME}/{output_key}")
        print(f"Total 5-year savings: ${roi_data['summary']['total_savings_5_years']:,}")

        # Update status
        update_status(status_key, 'running', 'roi_calculation', 90, f'ROI calculated: ${roi_data["summary"]["total_savings_5_years"]:,} over 5 years')

        return {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'total_savings_5_years': roi_data['summary']['total_savings_5_years'],
            'output_file': f's3://{BUCKET_NAME}/{output_key}'
        }

    except Exception as e:
        print(f"ERROR in DiscoveryV2ROICalculator: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def calculate_roi(total_files: int, business_processes: Dict, integration_points: Dict, api_patterns: Dict) -> Dict[str, Any]:
    """Calculate comprehensive ROI metrics"""

    # Constants (based on industry averages)
    TRADITIONAL_COST_PER_FILE = 5000  # Traditional rewrite cost per file
    AI_ACCELERATED_COST_PER_FILE = 1000  # AI-accelerated cost per file
    TRADITIONAL_DAYS_PER_FILE = 5  # Traditional development days per file
    AI_ACCELERATED_DAYS_PER_FILE = 1  # AI-accelerated days per file
    DEVELOPER_DAY_COST = 800  # Cost per developer day
    MAINTENANCE_COST_REDUCTION_PERCENT = 40  # % reduction in annual maintenance
    LEGACY_MAINTENANCE_COST_PER_FILE = 2000  # Annual legacy maintenance cost per file
    INFRASTRUCTURE_SAVINGS_PERCENT = 30  # % savings on AWS vs mainframe
    LEGACY_INFRASTRUCTURE_COST = 50000  # Annual legacy infrastructure cost (estimate)

    # 1. Cost Savings
    traditional_development_cost = total_files * TRADITIONAL_COST_PER_FILE
    ai_accelerated_development_cost = total_files * AI_ACCELERATED_COST_PER_FILE
    development_cost_savings = traditional_development_cost - ai_accelerated_development_cost

    # 2. Time Savings
    traditional_development_days = total_files * TRADITIONAL_DAYS_PER_FILE
    ai_accelerated_development_days = total_files * AI_ACCELERATED_DAYS_PER_FILE
    time_savings_days = traditional_development_days - ai_accelerated_development_days
    time_savings_months = time_savings_days / 20  # Assuming 20 working days per month

    # 3. Infrastructure Savings (5-year projection)
    annual_legacy_infrastructure = LEGACY_INFRASTRUCTURE_COST
    annual_aws_infrastructure = annual_legacy_infrastructure * (1 - INFRASTRUCTURE_SAVINGS_PERCENT / 100)
    annual_infrastructure_savings = annual_legacy_infrastructure - annual_aws_infrastructure
    infrastructure_savings_5_years = annual_infrastructure_savings * 5

    # 4. Maintenance Savings (5-year projection)
    annual_legacy_maintenance = total_files * LEGACY_MAINTENANCE_COST_PER_FILE
    annual_modern_maintenance = annual_legacy_maintenance * (1 - MAINTENANCE_COST_REDUCTION_PERCENT / 100)
    annual_maintenance_savings = annual_legacy_maintenance - annual_modern_maintenance
    maintenance_savings_5_years = annual_maintenance_savings * 5

    # 5. Productivity Gains
    high_value_processes = len([p for p in business_processes.get('business_processes', []) if p.get('business_value') == 'High'])
    productivity_gain_percent = min(high_value_processes * 5, 50)  # Cap at 50%
    annual_productivity_value = 100000  # Baseline annual value
    annual_productivity_gain = annual_productivity_value * (productivity_gain_percent / 100)
    productivity_gains_5_years = annual_productivity_gain * 5

    # 6. Risk Reduction Value
    high_complexity_integrations = integration_points.get('summary', {}).get('high_complexity_count', 0)
    risk_reduction_value = high_complexity_integrations * 50000  # Value per risk mitigated

    # Total Savings (5-year)
    total_savings_5_years = (
        development_cost_savings +
        infrastructure_savings_5_years +
        maintenance_savings_5_years +
        productivity_gains_5_years +
        risk_reduction_value
    )

    # ROI Percentage
    total_investment = ai_accelerated_development_cost + (annual_aws_infrastructure * 5)
    roi_percent = ((total_savings_5_years - total_investment) / total_investment * 100) if total_investment > 0 else 0

    # Payback Period (months)
    monthly_savings = (annual_infrastructure_savings + annual_maintenance_savings + annual_productivity_gain) / 12
    payback_months = (ai_accelerated_development_cost / monthly_savings) if monthly_savings > 0 else 0

    return {
        'summary': {
            'total_savings_5_years': int(total_savings_5_years),
            'roi_percent': round(roi_percent, 1),
            'payback_period_months': round(payback_months, 1),
            'total_investment': int(total_investment)
        },
        'development_cost_analysis': {
            'traditional_approach_cost': int(traditional_development_cost),
            'ai_accelerated_approach_cost': int(ai_accelerated_development_cost),
            'cost_savings': int(development_cost_savings),
            'savings_percent': round((development_cost_savings / traditional_development_cost * 100), 1)
        },
        'time_savings_analysis': {
            'traditional_development_days': int(traditional_development_days),
            'ai_accelerated_development_days': int(ai_accelerated_development_days),
            'time_savings_days': int(time_savings_days),
            'time_savings_months': round(time_savings_months, 1),
            'time_to_market_improvement_percent': round((time_savings_days / traditional_development_days * 100), 1)
        },
        'infrastructure_savings_analysis': {
            'annual_legacy_cost': int(annual_legacy_infrastructure),
            'annual_aws_cost': int(annual_aws_infrastructure),
            'annual_savings': int(annual_infrastructure_savings),
            'savings_5_years': int(infrastructure_savings_5_years),
            'savings_percent': INFRASTRUCTURE_SAVINGS_PERCENT
        },
        'maintenance_savings_analysis': {
            'annual_legacy_maintenance': int(annual_legacy_maintenance),
            'annual_modern_maintenance': int(annual_modern_maintenance),
            'annual_savings': int(annual_maintenance_savings),
            'savings_5_years': int(maintenance_savings_5_years),
            'reduction_percent': MAINTENANCE_COST_REDUCTION_PERCENT
        },
        'productivity_gains_analysis': {
            'high_value_business_processes': high_value_processes,
            'productivity_gain_percent': productivity_gain_percent,
            'annual_productivity_gain': int(annual_productivity_gain),
            'productivity_gains_5_years': int(productivity_gains_5_years)
        },
        'risk_analysis': {
            'high_complexity_integrations': high_complexity_integrations,
            'risk_reduction_value': int(risk_reduction_value),
            'risk_mitigation_description': 'Reduction in mainframe dependency risks, vendor lock-in, and skills shortage'
        }
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
