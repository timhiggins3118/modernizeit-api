"""
Architecture Recommender V2 - Load V2 Reports Handler
Lambda: ArchitectureRecommenderV2LoadReports

Purpose: Load and consolidate all V2 analysis reports

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
- Reads from all 4 V2 flows
"""

import json
import boto3
from typing import Dict, Any

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Load V2 Reports - Consolidate all V2 analysis data

    Input:
    {
        "job_id": "ar2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "discovery_job_id": "dv2_job_...",
        "data_job_id": "da2_job_...",
        "code_job_id": "ca2_job_...",
        "refactor_job_id": "cr2_job_..."
    }

    Output:
    {
        "consolidated_data": {...},
        "sources_loaded": 4
    }
    """
    try:
        print("=" * 80)
        print("ARCHITECTURE RECOMMENDER V2 - LOAD V2 REPORTS")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        discovery_job_id = event['discovery_job_id']
        data_job_id = event['data_job_id']
        code_job_id = event['code_job_id']
        refactor_job_id = event['refactor_job_id']

        print(f"Job ID: {job_id}")
        print(f"Account: {scout_account_id}, App: {application_name}")

        base_path = f"{scout_account_id}/{application_name}"
        consolidated = {
            'discovery_v2': None,
            'data_analysis_v2': {},
            'code_analysis_v3': None,  # Nov 6, 2025: Updated to V3
            'refactor_v2': None
        }

        sources_loaded = 0

        # Load Discovery V2 report
        print(f"\nLoading Discovery V2 report...")
        discovery_key = f"{base_path}/discovery_v2/jobs/{discovery_job_id}/artifacts/ai_discovery_analysis.json"
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=discovery_key)
            consolidated['discovery_v2'] = json.loads(response['Body'].read().decode('utf-8'))
            print(f"✓ Discovery V2 loaded: {len(str(consolidated['discovery_v2']))} bytes")
            sources_loaded += 1
        except Exception as e:
            print(f"✗ Discovery V2 load failed: {str(e)}")

        # Load Data Analyzer V2 ERD
        print(f"\nLoading Data Analyzer V2 ERD...")
        erd_key = f"{base_path}/data_analysis_v2/jobs/{data_job_id}/artifacts/erd.json"
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=erd_key)
            consolidated['data_analysis_v2']['erd'] = json.loads(response['Body'].read().decode('utf-8'))
            print(f"✓ ERD loaded: {len(str(consolidated['data_analysis_v2']['erd']))} bytes")
        except Exception as e:
            print(f"✗ ERD load failed: {str(e)}")

        # Load Data Analyzer V2 Data Lineage
        print(f"\nLoading Data Analyzer V2 Data Lineage...")
        lineage_key = f"{base_path}/data_analysis_v2/jobs/{data_job_id}/artifacts/data_lineage.json"
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=lineage_key)
            consolidated['data_analysis_v2']['data_lineage'] = json.loads(response['Body'].read().decode('utf-8'))
            print(f"✓ Data Lineage loaded: {len(str(consolidated['data_analysis_v2']['data_lineage']))} bytes")
            sources_loaded += 1
        except Exception as e:
            print(f"✗ Data Lineage load failed: {str(e)}")

        # Load Code Analysis V3 report (Nov 6, 2025: Updated to read V3 outputs)
        print(f"\nLoading Code Analysis V3 report...")
        code_key = f"{base_path}/code_analysis_v3/jobs/{code_job_id}/artifacts/static_analysis.json"
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=code_key)
            consolidated['code_analysis_v3'] = json.loads(response['Body'].read().decode('utf-8'))
            print(f"✓ Code Analysis V3 loaded: {len(str(consolidated['code_analysis_v3']))} bytes")
            sources_loaded += 1
        except Exception as e:
            print(f"✗ Code Analysis V3 load failed: {str(e)}")

        # Load Refactor V2 recipes
        print(f"\nLoading Refactor V2 recipes...")
        refactor_key = f"{base_path}/code_refactor_v2/jobs/{refactor_job_id}/artifacts/refactor_recipes.json"
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=refactor_key)
            consolidated['refactor_v2'] = json.loads(response['Body'].read().decode('utf-8'))
            print(f"✓ Refactor V2 loaded: {len(str(consolidated['refactor_v2']))} bytes")
            sources_loaded += 1
        except Exception as e:
            print(f"✗ Refactor V2 load failed: {str(e)}")

        print(f"\nLoaded {sources_loaded}/4 V2 reports")

        # Write consolidated input
        consolidated_artifact = {
            'job_id': job_id,
            'source_jobs': {
                'discovery_v2': discovery_job_id,
                'data_analysis_v2': data_job_id,
                'code_analysis_v3': code_job_id,
                'refactor_v2': refactor_job_id
            },
            'consolidated_data': consolidated,
            'sources_loaded': sources_loaded
        }

        artifact_key = f"{base_path}/architecture_v2/jobs/{job_id}/artifacts/consolidated_input.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=artifact_key,
            Body=json.dumps(consolidated_artifact, indent=2),
            ContentType='application/json'
        )

        print(f"\nWrote consolidated input: s3://{BUCKET_NAME}/{artifact_key}")

        # Update status
        update_status(scout_account_id, application_name, job_id, {
            'phase': 'loading_reports',
            'progress': 20,
            'message': f'Loaded {sources_loaded}/4 V2 reports'
        })

        # Return minimal data (Step Functions has 256KB limit)
        return {
            'job_id': job_id,
            'sources_loaded': sources_loaded,
            'consolidated_input_s3': f"s3://{BUCKET_NAME}/{artifact_key}"
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


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
