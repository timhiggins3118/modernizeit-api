"""
Monolith Identifier V2 - Decomposition Strategy Handler
Lambda: MonolithIdentifierV2DecompositionStrategy

Purpose: Generate microservice decomposition recommendations

V2 Design Principles:
- Standalone architecture
- Independent Lambda (NO code sharing)
"""

import json
import boto3
from typing import Dict, Any, List
from collections import defaultdict

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Decomposition Strategy - Generate microservice recommendations

    Input:
    {
        "job_id": "miv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "recommended_microservices": [...],
        "refactoring_priorities": [...],
        "migration_strategy": {...}
    }
    """
    try:
        print("=" * 80)
        print("MONOLITH IDENTIFIER V2 - DECOMPOSITION STRATEGY")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        # Read all analysis results
        static_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/static_monolith_analysis.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=static_key)
        static_data = json.loads(response['Body'].read().decode('utf-8'))

        ai_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/ai_pattern_analysis.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=ai_key)
        ai_data = json.loads(response['Body'].read().decode('utf-8'))

        modularity_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/modularity_metrics.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=modularity_key)
        modularity_data = json.loads(response['Body'].read().decode('utf-8'))

        patterns_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/detected_patterns.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=patterns_key)
        patterns_data = json.loads(response['Body'].read().decode('utf-8'))

        print("Generating decomposition strategy...")

        # Generate microservice recommendations
        recommended_microservices = generate_microservice_boundaries(static_data, ai_data)

        # Generate refactoring priorities
        refactoring_priorities = generate_refactoring_priorities(patterns_data, modularity_data)

        # Generate migration strategy
        migration_strategy = generate_migration_strategy(recommended_microservices, refactoring_priorities)

        print(f"\nRecommendations:")
        print(f"  Microservices: {len(recommended_microservices)}")
        print(f"  Refactoring Priorities: {len(refactoring_priorities)}")
        print(f"  Migration Phases: {len(migration_strategy.get('phases', []))}")

        # Create result
        result = {
            'recommended_microservices': recommended_microservices,
            'refactoring_priorities': refactoring_priorities,
            'migration_strategy': migration_strategy
        }

        # Write to S3
        artifact_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/decomposition_strategy.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=artifact_key,
            Body=json.dumps(result, indent=2),
            ContentType='application/json'
        )

        print(f"\nWrote artifact: s3://{BUCKET_NAME}/{artifact_key}")

        # Update status to completed
        update_status(scout_account_id, application_name, job_id, {
            'state': 'completed',
            'status': 'completed',
            'phase': 'completed',
            'progress': 100,
            'message': 'Monolith analysis completed successfully'
        })

        return result

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def generate_microservice_boundaries(static_data: Dict[str, Any], ai_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate microservice boundary recommendations"""
    microservices = []

    # Group programs by business function (use AI responsibilities as hints)
    function_groups = defaultdict(list)

    # If AI identified god programs with multiple responsibilities, split those
    god_programs = ai_data.get('patterns_detected', {}).get('god_programs', [])
    for god_prog in god_programs:
        responsibilities = god_prog.get('responsibilities', [])
        program_name = god_prog['program']

        # Find program details
        program = next((p for p in static_data.get('programs', []) if p['program_name'] == program_name), None)
        if not program:
            continue

        # Create a microservice for each responsibility
        for responsibility in responsibilities:
            function_groups[responsibility].append(program_name)

    # For non-god programs, group by shared copybooks (data affinity)
    copybook_groups = defaultdict(list)
    for program in static_data.get('programs', []):
        copybooks = program.get('copybooks_used', [])
        if copybooks:
            # Use first copybook as grouping key
            key = copybooks[0]
            copybook_groups[key].append(program['program_name'])

    # Generate microservice recommendations
    service_id = 1

    # From function groups
    for function, programs in function_groups.items():
        if programs:
            total_loc = sum(
                p.get('loc', 0)
                for p in static_data.get('programs', [])
                if p['program_name'] in programs
            )

            microservices.append({
                'service_name': f"{function.replace('_', ' ').title()}Service",
                'programs': programs,
                'total_loc': total_loc,
                'business_capability': function,
                'shared_data': [],
                'dependencies': [],
                'extraction_complexity': 'high' if total_loc > 5000 else 'medium',
                'estimated_effort_weeks': max(4, total_loc // 1000)
            })
            service_id += 1

    # From copybook groups (if not already in function groups)
    for copybook, programs in copybook_groups.items():
        if len(programs) >= 3:  # At least 3 programs share this data
            # Check if already in microservices
            already_included = any(
                set(programs) & set(ms['programs'])
                for ms in microservices
            )

            if not already_included:
                total_loc = sum(
                    p.get('loc', 0)
                    for p in static_data.get('programs', [])
                    if p['program_name'] in programs
                )

                microservices.append({
                    'service_name': f"{copybook.replace('-', '')}Service",
                    'programs': programs[:5],  # Limit to first 5
                    'total_loc': total_loc,
                    'business_capability': f'Data management for {copybook}',
                    'shared_data': [copybook],
                    'dependencies': [],
                    'extraction_complexity': 'low',
                    'estimated_effort_weeks': max(2, total_loc // 2000)
                })
                service_id += 1

    return microservices[:10]  # Limit to top 10 recommendations


def generate_refactoring_priorities(patterns_data: Dict[str, Any], modularity_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate prioritized list of refactoring targets"""
    priorities = []
    rank = 1

    # Priority 1: God programs (critical severity)
    god_programs = patterns_data.get('detected_patterns', {}).get('god_programs', [])
    for gp in god_programs:
        if gp.get('severity') == 'critical':
            priorities.append({
                'rank': rank,
                'program': gp['program'],
                'reason': f"God program - {gp['loc']} LOC, {gp['responsibilities']} responsibilities",
                'action': f"Split into {gp['responsibilities']} microservices",
                'estimated_effort_weeks': max(12, gp['loc'] // 500),
                'risk': 'high'
            })
            rank += 1

    # Priority 2: Tight coupling (high severity)
    tight_coupling = patterns_data.get('detected_patterns', {}).get('tight_coupling', [])
    for tc in tight_coupling:
        priorities.append({
            'rank': rank,
            'program': tc['program'],
            'reason': f"High coupling - {tc['efferent_coupling']} dependencies",
            'action': 'Introduce message queue or event bus',
            'estimated_effort_weeks': 6,
            'risk': 'medium'
        })
        rank += 1

    # Priority 3: Shared data hotspots
    shared_data = patterns_data.get('detected_patterns', {}).get('shared_data_hotspots', [])
    for sd in shared_data:
        priorities.append({
            'rank': rank,
            'program': sd['copybook'],
            'reason': f"Shared data - used by {sd['used_by']} programs",
            'action': f"Extract {sd['copybook']} data service",
            'estimated_effort_weeks': 8,
            'risk': 'medium'
        })
        rank += 1

    return priorities[:15]  # Top 15 priorities


def generate_migration_strategy(microservices: List[Dict[str, Any]], priorities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate phased migration strategy"""

    # Phase 1: Low-risk, low-complexity services
    phase1_services = [
        ms for ms in microservices
        if ms.get('extraction_complexity') == 'low'
    ][:2]

    # Phase 2: Medium-complexity services
    phase2_services = [
        ms for ms in microservices
        if ms.get('extraction_complexity') == 'medium'
    ][:3]

    # Phase 3: High-complexity services
    phase3_services = [
        ms for ms in microservices
        if ms.get('extraction_complexity') == 'high'
    ][:2]

    phases = []

    if phase1_services:
        phases.append({
            'phase': 1,
            'services': [ms['service_name'] for ms in phase1_services],
            'duration_weeks': sum(ms.get('estimated_effort_weeks', 4) for ms in phase1_services),
            'risk': 'low'
        })

    if phase2_services:
        phases.append({
            'phase': 2,
            'services': [ms['service_name'] for ms in phase2_services],
            'duration_weeks': sum(ms.get('estimated_effort_weeks', 6) for ms in phase2_services),
            'risk': 'medium'
        })

    if phase3_services:
        phases.append({
            'phase': 3,
            'services': [ms['service_name'] for ms in phase3_services],
            'duration_weeks': sum(ms.get('estimated_effort_weeks', 12) for ms in phase3_services),
            'risk': 'high'
        })

    total_duration = sum(p['duration_weeks'] for p in phases)
    total_effort = sum(ms.get('estimated_effort_weeks', 0) for ms in microservices)

    return {
        'approach': 'Strangler Fig Pattern',
        'description': 'Incrementally extract microservices from monolith',
        'phases': phases,
        'total_duration_weeks': total_duration,
        'total_effort_weeks': total_effort
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
