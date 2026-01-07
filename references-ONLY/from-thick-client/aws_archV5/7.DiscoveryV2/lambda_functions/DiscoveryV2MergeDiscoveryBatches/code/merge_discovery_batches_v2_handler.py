"""
Discovery V2 - Merge Discovery Batches Handler
Lambda: DiscoveryV2MergeDiscoveryBatches

Purpose: Merge AI discovery analysis from all batches into single file

V2 Design Principles:
- Reads all batch_{N}.json files
- Combines into ai_discovery_analysis.json
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
    Merge Discovery Batches

    Input (from Step Functions):
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "source_hash": "21a056...",
        "total_batches": 5
    }

    Output:
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "total_files_analyzed": 23,
        "successful_analyses": 23,
        "failed_analyses": 0,
        "merged_file": "s3://...ai_discovery_analysis.json"
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        total_batches = event['total_batches']

        print(f"Merging {total_batches} batches for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'merging_batches', 35, f'Merging {total_batches} analysis batches')

        # Read all batch files
        batch_prefix = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/ai_discovery_analysis/"

        all_file_analyses = []
        total_successful = 0
        total_failed = 0

        for batch_id in range(total_batches):
            batch_key = f"{batch_prefix}batch_{batch_id}.json"

            try:
                batch_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=batch_key)
                batch_data = json.loads(batch_response['Body'].read())

                # Extract results from this batch
                for result in batch_data.get('results', []):
                    all_file_analyses.append({
                        'file_path': result['file_path'],
                        'file_size': result.get('file_size'),
                        'analysis': result.get('analysis'),
                        'error': result.get('error'),
                        'analyzed_at': result.get('analyzed_at'),
                        'model': result.get('model'),
                        'agent': result.get('agent')
                    })

                    if result.get('analysis'):
                        total_successful += 1
                    else:
                        total_failed += 1

                print(f"Merged batch {batch_id}: {len(batch_data.get('results', []))} files")

            except s3_client.exceptions.NoSuchKey:
                print(f"WARNING: Batch {batch_id} not found at {batch_key}")
                total_failed += 1
                continue

        # Create merged output
        merged_data = {
            'job_id': job_id,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_batches': total_batches,
                'total_files_analyzed': len(all_file_analyses),
                'successful_analyses': total_successful,
                'failed_analyses': total_failed
            },
            'file_analyses': all_file_analyses
        }

        # Save merged file
        merged_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/ai_discovery_analysis.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=merged_key,
            Body=json.dumps(merged_data, indent=2),
            ContentType='application/json'
        )

        print(f"Saved merged analysis to s3://{BUCKET_NAME}/{merged_key}")
        print(f"Total files: {len(all_file_analyses)} (successful: {total_successful}, failed: {total_failed})")

        # Update status
        update_status(status_key, 'running', 'ai_discovery_analysis', 40, f'AI analysis completed: {total_successful}/{len(all_file_analyses)} files')

        # Return summary
        return {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'total_files_analyzed': len(all_file_analyses),
            'successful_analyses': total_successful,
            'failed_analyses': total_failed,
            'merged_file': f's3://{BUCKET_NAME}/{merged_key}'
        }

    except Exception as e:
        print(f"ERROR in DiscoveryV2MergeDiscoveryBatches: {str(e)}")
        import traceback
        traceback.print_exc()

        # Update status to failed
        try:
            status_key = f"{event['scout_account_id']}/{event['application_name']}/discovery_v2/jobs/{event['job_id']}/status.json"
            update_status(status_key, 'failed', 'merge_failed', 0, f'Failed to merge batches: {str(e)}')
        except:
            pass

        raise


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

        if status == 'failed':
            status_data['failed_at'] = datetime.now(timezone.utc).isoformat()

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
