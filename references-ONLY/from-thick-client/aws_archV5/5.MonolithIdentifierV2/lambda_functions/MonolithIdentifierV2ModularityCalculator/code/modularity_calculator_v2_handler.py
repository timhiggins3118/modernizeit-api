"""
Monolith Identifier V2 - Modularity Calculator Handler
Lambda: MonolithIdentifierV2ModularityCalculator

Purpose: Calculate coupling, cohesion, and modularity metrics

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
    Modularity Calculator - Calculate coupling/cohesion metrics

    Input:
    {
        "job_id": "miv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "programs": [...],
        "aggregate_metrics": {...}
    }
    """
    try:
        print("=" * 80)
        print("MONOLITH IDENTIFIER V2 - MODULARITY CALCULATOR")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        # Read static analysis and AI analysis
        static_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/static_monolith_analysis.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=static_key)
        static_data = json.loads(response['Body'].read().decode('utf-8'))

        ai_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/ai_pattern_analysis.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=ai_key)
        ai_data = json.loads(response['Body'].read().decode('utf-8'))

        programs = static_data.get('programs', [])
        print(f"Calculating metrics for {len(programs)} programs")

        # Calculate metrics for each program
        program_metrics = []
        total_coupling = 0
        total_cohesion = 0
        total_modularity = 0
        high_coupling_count = 0
        low_cohesion_count = 0

        for program in programs:
            metrics = calculate_program_metrics(program, programs, ai_data)
            program_metrics.append(metrics)

            total_coupling += metrics['efferent_coupling']
            total_cohesion += metrics['cohesion_score']
            total_modularity += metrics['modularity_score']

            if metrics['classification'] == 'high_coupling':
                high_coupling_count += 1
            if metrics['cohesion_score'] < 0.5:
                low_cohesion_count += 1

        avg_coupling = total_coupling / len(programs) if programs else 0
        avg_cohesion = total_cohesion / len(programs) if programs else 0
        avg_modularity = total_modularity / len(programs) if programs else 0

        print(f"\nAggregate Metrics:")
        print(f"  Average Coupling: {avg_coupling:.2f}")
        print(f"  Average Cohesion: {avg_cohesion:.2f}")
        print(f"  Average Modularity: {avg_modularity:.2f}")
        print(f"  High Coupling Programs: {high_coupling_count}")
        print(f"  Low Cohesion Programs: {low_cohesion_count}")

        # Create result
        result = {
            'programs': program_metrics,
            'aggregate_metrics': {
                'average_coupling': round(avg_coupling, 2),
                'average_cohesion': round(avg_cohesion, 2),
                'average_modularity': round(avg_modularity, 2),
                'high_coupling_count': high_coupling_count,
                'low_cohesion_count': low_cohesion_count
            }
        }

        # Write to S3
        artifact_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/modularity_metrics.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=artifact_key,
            Body=json.dumps(result, indent=2),
            ContentType='application/json'
        )

        print(f"\nWrote artifact: s3://{BUCKET_NAME}/{artifact_key}")

        # Update status
        update_status(scout_account_id, application_name, job_id, {
            'phase': 'modularity_calculated',
            'progress': 60,
            'message': f'Calculated modularity metrics for {len(programs)} programs'
        })

        return result

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def calculate_program_metrics(program: Dict[str, Any], all_programs: List[Dict[str, Any]], ai_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate coupling/cohesion metrics for a single program"""

    # Efferent Coupling (Ce): Number of programs this one depends on
    efferent_coupling = program.get('call_statements', 0)

    # Afferent Coupling (Ca): Estimate based on how many other programs might call this
    # (Simple heuristic: programs with many paragraphs are likely called more)
    afferent_coupling = min(program.get('paragraphs', 0) // 10, 5)

    # Instability: Ce / (Ca + Ce)
    total_coupling = efferent_coupling + afferent_coupling
    instability = efferent_coupling / total_coupling if total_coupling > 0 else 0

    # Abstractness: Based on copybook usage (programs with many copybooks are more abstract)
    copybooks_count = len(program.get('copybooks_used', []))
    abstractness = min(copybooks_count / 10, 1.0) if copybooks_count > 0 else 0

    # Distance from Main Sequence: |A + I - 1|
    distance_from_main_sequence = abs(abstractness + instability - 1)

    # Cohesion Score: Based on single responsibility
    # Higher cohesion if program is small and focused
    loc = program.get('loc', 0)
    if loc < 500:
        cohesion_score = 0.9
    elif loc < 2000:
        cohesion_score = 0.7
    elif loc < 5000:
        cohesion_score = 0.4
    else:
        cohesion_score = 0.2

    # Adjust cohesion based on AI analysis
    # If AI identified it as god program with multiple responsibilities, lower cohesion
    god_programs = ai_data.get('patterns_detected', {}).get('god_programs', [])
    for god_prog in god_programs:
        if god_prog.get('program') == program['program_name']:
            responsibilities = len(god_prog.get('responsibilities', []))
            if responsibilities > 1:
                cohesion_score *= (1.0 / responsibilities)
            break

    # Modularity Score: (1 - instability) * cohesion
    modularity_score = (1 - instability) * cohesion_score

    # Classification
    if efferent_coupling > 5 or afferent_coupling > 8:
        classification = 'high_coupling'
    elif efferent_coupling > 2 or afferent_coupling > 4:
        classification = 'medium_coupling'
    else:
        classification = 'low_coupling'

    return {
        'program': program['program_name'],
        'afferent_coupling': afferent_coupling,
        'efferent_coupling': efferent_coupling,
        'instability': round(instability, 2),
        'abstractness': round(abstractness, 2),
        'distance_from_main_sequence': round(distance_from_main_sequence, 2),
        'cohesion_score': round(cohesion_score, 2),
        'modularity_score': round(modularity_score, 2),
        'classification': classification
    }


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
