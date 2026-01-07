"""
Monolith Identifier V2 - Merge Static Analysis Handler
Lambda: MonolithIdentifierV2MergeStatic

Purpose: Merge all static analysis batch results

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
"""

import json
import boto3
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Merge Static Analysis - Combine all batch results

    Input:
    {
        "job_id": "miv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "total_batches": 9
    }

    Output:
    {
        "total_programs": 87,
        "total_loc": 245000,
        ...
    }
    """
    try:
        print("=" * 80)
        print("MONOLITH IDENTIFIER V2 - MERGE STATIC ANALYSIS")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        total_batches = event['total_batches']

        print(f"Job ID: {job_id}")
        print(f"Merging {total_batches} batches")

        # Read all batch files
        all_programs = []

        for batch_id in range(total_batches):
            batch_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/batches/static_batch_{batch_id}.json"

            try:
                response = s3_client.get_object(Bucket=BUCKET_NAME, Key=batch_key)
                batch_data = json.loads(response['Body'].read().decode('utf-8'))

                programs = batch_data.get('programs', [])
                all_programs.extend(programs)

                print(f"Batch {batch_id}: {len(programs)} programs")

            except Exception as e:
                print(f"WARNING: Could not read batch {batch_id}: {str(e)}")

        print(f"\nTotal programs merged: {len(all_programs)}")

        # Calculate aggregate statistics
        total_loc = sum(p.get('loc', 0) for p in all_programs)
        total_complexity = sum(p.get('cyclomatic_complexity', 0) for p in all_programs)

        avg_loc = total_loc // len(all_programs) if all_programs else 0
        avg_complexity = total_complexity // len(all_programs) if all_programs else 0

        # Count size distribution
        size_distribution = {
            'small': 0,
            'medium': 0,
            'large': 0,
            'god_programs': 0
        }

        for program in all_programs:
            category = program.get('size_category', 'unknown')
            if category in size_distribution:
                size_distribution[category] += 1

        print(f"\nSize Distribution:")
        print(f"  Small (< 500 LOC): {size_distribution['small']}")
        print(f"  Medium (500-2000): {size_distribution['medium']}")
        print(f"  Large (2000-5000): {size_distribution['large']}")
        print(f"  God Programs (> 5000): {size_distribution['god_programs']}")

        # Identify potential god programs
        potential_god_programs = [
            {
                'name': p['program_name'],
                'loc': p['loc'],
                'complexity': p['cyclomatic_complexity']
            }
            for p in all_programs
            if p.get('size_category') == 'god_program'
        ]

        # Sort by LOC descending
        potential_god_programs.sort(key=lambda x: x['loc'], reverse=True)

        print(f"\nGod Programs Detected: {len(potential_god_programs)}")

        # Create consolidated result
        result = {
            'total_programs': len(all_programs),
            'total_loc': total_loc,
            'average_loc': avg_loc,
            'average_complexity': avg_complexity,
            'size_distribution': size_distribution,
            'programs': all_programs,
            'potential_god_programs': potential_god_programs
        }

        # Write to S3
        artifact_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/static_monolith_analysis.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=artifact_key,
            Body=json.dumps(result, indent=2),
            ContentType='application/json'
        )

        print(f"\nWrote artifact: s3://{BUCKET_NAME}/{artifact_key}")

        # Update status
        update_status(scout_account_id, application_name, job_id, {
            'phase': 'static_analysis_complete',
            'progress': 30,
            'message': f'Analyzed {len(all_programs)} programs, found {len(potential_god_programs)} god programs'
        })

        return result

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def update_status(account_id: str, app_name: str, job_id: str, updates: Dict[str, Any]):
    """Update job status in S3"""
    try:
        status_key = f"{account_id}/{app_name}/monolith_identifier_v2/jobs/{job_id}/status.json"

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
