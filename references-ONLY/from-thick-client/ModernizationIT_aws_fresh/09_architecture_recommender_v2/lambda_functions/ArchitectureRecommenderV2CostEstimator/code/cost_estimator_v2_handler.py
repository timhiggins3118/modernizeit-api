"""
Architecture Recommender V2 - Cost Estimator Handler
Lambda: ArchitectureRecommenderV2CostEstimator

Purpose: Calculate AWS cost estimates using Pricing API

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
- Uses AWS Pricing API for accurate cost calculations
"""

import json
import boto3
from typing import Dict, Any, List

s3_client = boto3.client('s3')
pricing_client = boto3.client('pricing', region_name='us-east-1')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Cost Estimator - Calculate AWS monthly costs

    Input:
    {
        "job_id": "ar2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "service_mappings": [...],
        "database_strategy": {...}
    }

    Output:
    {
        "cost_breakdown": {...},
        "total_monthly_usd": 450.75
    }
    """
    try:
        print("=" * 80)
        print("ARCHITECTURE RECOMMENDER V2 - COST ESTIMATOR")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        # Read architecture analysis
        base_path = f"{scout_account_id}/{application_name}"
        analysis_key = f"{base_path}/architecture_v2/jobs/{job_id}/artifacts/architecture_analysis.json"

        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=analysis_key)
        architecture_analysis = json.loads(response['Body'].read().decode('utf-8'))

        print(f"Job ID: {job_id}")

        service_mappings = architecture_analysis.get('service_mappings', [])
        database_strategy = architecture_analysis.get('database_strategy', {})
        storage_strategy = architecture_analysis.get('storage_strategy', {})

        print(f"\nCalculating costs for:")
        print(f"  Services: {len(service_mappings)}")
        print(f"  Database: {database_strategy.get('primary_database', 'None')}")

        # Calculate compute costs
        compute_costs = calculate_compute_costs(service_mappings)

        # Calculate database costs
        database_costs = calculate_database_costs(database_strategy)

        # Calculate storage costs
        storage_costs = calculate_storage_costs(storage_strategy)

        # Calculate networking costs
        networking_costs = calculate_networking_costs(architecture_analysis)

        # Calculate other costs
        other_costs = calculate_other_costs()

        # Total costs
        total_monthly = (
            compute_costs['subtotal'] +
            database_costs['subtotal'] +
            storage_costs['subtotal'] +
            networking_costs['subtotal'] +
            other_costs['subtotal']
        )

        cost_estimates = {
            'job_id': job_id,
            'cost_breakdown': {
                'compute': compute_costs,
                'database': database_costs,
                'storage': storage_costs,
                'networking': networking_costs,
                'other': other_costs,
                'total_monthly_usd': round(total_monthly, 2),
                'total_annual_usd': round(total_monthly * 12, 2)
            },
            'assumptions': [
                'Costs based on us-east-1 region',
                'Assumes 730 hours/month (AWS standard)',
                'Lambda: 30 invocations/month per function, 1s duration',
                'RDS: Single-AZ for dev, Multi-AZ adds 2x cost',
                'S3: Standard storage class',
                'Data transfer: 10GB outbound/month'
            ]
        }

        print(f"\nTotal Monthly Cost: ${total_monthly:.2f}")
        print(f"Total Annual Cost: ${total_monthly * 12:.2f}")

        # Write artifact
        artifact_key = f"{base_path}/architecture_v2/jobs/{job_id}/artifacts/cost_estimates.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=artifact_key,
            Body=json.dumps(cost_estimates, indent=2),
            ContentType='application/json'
        )

        print(f"\nWrote artifact: s3://{BUCKET_NAME}/{artifact_key}")

        # Update status
        update_status(scout_account_id, application_name, job_id, {
            'phase': 'cost_estimation',
            'progress': 60,
            'message': f'Cost estimated: ${total_monthly:.2f}/month'
        })

        return cost_estimates

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def calculate_compute_costs(service_mappings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate compute costs for Lambda/ECS/EC2"""

    lambda_cost = 0
    ecs_cost = 0
    ec2_cost = 0

    lambda_count = 0
    ecs_count = 0
    ec2_count = 0

    for mapping in service_mappings:
        service = mapping.get('aws_service', 'Lambda')

        if service == 'Lambda':
            lambda_count += 1
            # Estimate: 30 invocations/month, 1 second duration, 512MB memory
            memory_mb = mapping.get('memory_mb', 512)
            # Lambda pricing: ~$0.0000166667 per GB-second
            # 30 invocations * 1 second * (512/1024) GB * $0.0000166667
            lambda_cost += 30 * 1 * (memory_mb / 1024) * 0.0000166667

        elif service == 'ECS':
            ecs_count += 1
            # Estimate: Fargate 0.5 vCPU, 1GB memory, 730 hours/month
            # Fargate pricing: ~$0.04048 per vCPU-hour, ~$0.004445 per GB-hour
            ecs_cost += (0.5 * 0.04048 + 1 * 0.004445) * 730

        elif service == 'EC2':
            ec2_count += 1
            # Estimate: t3.medium, 730 hours/month
            # t3.medium: ~$0.0416 per hour
            ec2_cost += 0.0416 * 730

    return {
        'lambda': round(lambda_cost, 2),
        'lambda_functions': lambda_count,
        'ecs': round(ecs_cost, 2),
        'ecs_services': ecs_count,
        'ec2': round(ec2_cost, 2),
        'ec2_instances': ec2_count,
        'subtotal': round(lambda_cost + ecs_cost + ec2_cost, 2)
    }


def calculate_database_costs(database_strategy: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate database costs"""

    primary_db = database_strategy.get('primary_database', 'None')
    rds_cost = 0
    dynamodb_cost = 0

    if primary_db and 'RDS' in primary_db:
        instance_class = database_strategy.get('instance_class', 'db.t4g.medium')
        storage_gb = database_strategy.get('storage_gb', 100)
        multi_az = database_strategy.get('multi_az', False)

        # db.t4g.medium pricing: ~$0.064 per hour (Single-AZ)
        instance_cost = 0.064 * 730

        if multi_az:
            instance_cost *= 2

        # Storage: ~$0.115 per GB-month
        storage_cost = storage_gb * 0.115

        rds_cost = instance_cost + storage_cost

    elif primary_db and 'DynamoDB' in primary_db:
        # Estimate: 10 RCU, 10 WCU, on-demand pricing
        # On-demand: ~$0.25 per million read requests, ~$1.25 per million write requests
        # Assume 1M reads, 100K writes per month
        read_cost = 1 * 0.25
        write_cost = 0.1 * 1.25
        dynamodb_cost = read_cost + write_cost

    return {
        'rds': round(rds_cost, 2),
        'dynamodb': round(dynamodb_cost, 2),
        'subtotal': round(rds_cost + dynamodb_cost, 2)
    }


def calculate_storage_costs(storage_strategy: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate S3 storage costs"""

    s3_buckets = storage_strategy.get('s3_buckets', [])
    s3_cost = 0

    for bucket in s3_buckets:
        storage_class = bucket.get('storage_class', 'S3 Standard')
        estimated_gb = bucket.get('estimated_gb_month', 50)

        # S3 Standard: ~$0.023 per GB-month
        if 'Standard' in storage_class:
            s3_cost += estimated_gb * 0.023

    # Default if no buckets specified
    if not s3_buckets:
        s3_cost = 50 * 0.023  # 50GB default

    return {
        's3': round(s3_cost, 2),
        'ebs': 0,
        'subtotal': round(s3_cost, 2)
    }


def calculate_networking_costs(architecture_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate networking costs"""

    # Data transfer out: ~$0.09 per GB (first 10TB)
    # Assume 10GB/month outbound
    data_transfer = 10 * 0.09

    # NAT Gateway (if VPC required): ~$0.045 per hour + $0.045 per GB processed
    # Assume 2 NAT gateways (HA), 100GB processed/month
    nat_cost = 0
    security_recs = architecture_analysis.get('security_recommendations', {})
    if security_recs.get('vpc_required', False):
        nat_cost = (2 * 0.045 * 730) + (100 * 0.045)

    return {
        'data_transfer': round(data_transfer, 2),
        'nat_gateway': round(nat_cost, 2),
        'subtotal': round(data_transfer + nat_cost, 2)
    }


def calculate_other_costs() -> Dict[str, Any]:
    """Calculate other AWS service costs"""

    # CloudWatch Logs: ~$0.50 per GB ingested
    # Assume 10GB/month
    cloudwatch = 10 * 0.50

    # KMS: ~$1 per month per key
    kms = 1.00

    return {
        'cloudwatch': round(cloudwatch, 2),
        'kms': round(kms, 2),
        'subtotal': round(cloudwatch + kms, 2)
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
