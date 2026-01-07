"""
Dependency Mapper V2 - Merge Static Analysis Handler
Lambda: DependencyMapperV2MergeStatic

Purpose: Merge all static analysis batch results into single artifact

V2 Design Principles:
- Standalone architecture (NO integration with other flows)
- Independent Lambda (NO code sharing)
- Event-driven architecture
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Merge Static Analysis Results

    Input (from Step Functions):
    {
        "job_id": "dmv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "total_batches": 5
    }

    Output:
    {
        "merged_file": "artifacts/static_analysis.json",
        "total_programs": 23,
        "total_dependencies": 156
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        total_batches = event['total_batches']

        print(f"Merging static analysis results for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'merging_static_analysis', 35, 'Merging static analysis results')

        # Read all batch results
        all_dependencies = []
        total_calls = 0
        total_copies = 0
        total_file_io = 0
        total_database = 0

        for batch_id in range(total_batches):
            batch_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/temp/batch_analysis/batch_{batch_id}.json"

            try:
                batch_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=batch_key)
                batch_data = json.loads(batch_response['Body'].read())

                dependencies = batch_data.get('dependencies_found', [])
                all_dependencies.extend(dependencies)

                # Count dependencies
                for dep in dependencies:
                    total_calls += len(dep.get('calls', []))
                    total_copies += len(dep.get('copies', []))
                    total_file_io += len(dep.get('file_io', []))
                    total_database += len(dep.get('database', []))

                print(f"Merged batch {batch_id}: {len(dependencies)} programs")

            except s3_client.exceptions.NoSuchKey:
                print(f"Warning: Batch {batch_id} not found, skipping")
                continue

        total_programs = len(all_dependencies)
        total_dependencies = total_calls + total_copies + total_file_io + total_database

        print(f"Merged {total_programs} programs with {total_dependencies} total dependencies")

        # Create merged static analysis artifact
        static_analysis = {
            'programs': all_dependencies,
            'summary': {
                'total_programs': total_programs,
                'total_dependencies': total_dependencies,
                'program_calls': total_calls,
                'copybook_dependencies': total_copies,
                'file_operations': total_file_io,
                'database_operations': total_database
            },
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id
        }

        # Save to S3
        output_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/static_analysis.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(static_analysis, indent=2),
            ContentType='application/json'
        )

        print(f"Saved static analysis to s3://{BUCKET_NAME}/{output_key}")

        # Update status
        update_status(status_key, 'running', 'static_analysis_complete', 40, f'Analyzed {total_programs} programs, found {total_dependencies} dependencies')

        return {
            'merged_file': f'artifacts/static_analysis.json',
            'total_programs': total_programs,
            'total_dependencies': total_dependencies
        }

    except Exception as e:
        print(f"ERROR in DependencyMapperV2MergeStatic: {str(e)}")
        import traceback
        traceback.print_exc()
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
        status_data['state'] = status
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
