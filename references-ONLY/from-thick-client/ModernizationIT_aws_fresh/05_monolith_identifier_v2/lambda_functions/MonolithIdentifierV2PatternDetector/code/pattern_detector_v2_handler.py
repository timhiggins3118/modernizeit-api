"""
Monolith Identifier V2 - Pattern Detector Handler
Lambda: MonolithIdentifierV2PatternDetector

Purpose: Detect specific monolithic anti-patterns

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
    Pattern Detector - Detect monolithic anti-patterns

    Input:
    {
        "job_id": "miv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "detected_patterns": {...},
        "summary": {...}
    }
    """
    try:
        print("=" * 80)
        print("MONOLITH IDENTIFIER V2 - PATTERN DETECTOR")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        # Read all previous analysis results
        static_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/static_monolith_analysis.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=static_key)
        static_data = json.loads(response['Body'].read().decode('utf-8'))

        ai_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/ai_pattern_analysis.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=ai_key)
        ai_data = json.loads(response['Body'].read().decode('utf-8'))

        modularity_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/modularity_metrics.json"
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=modularity_key)
        modularity_data = json.loads(response['Body'].read().decode('utf-8'))

        print("Detecting patterns...")

        # Detect patterns
        god_programs = detect_god_programs(static_data, ai_data)
        tight_coupling_programs = detect_tight_coupling(modularity_data)
        shared_data_hotspots = detect_shared_data_hotspots(static_data)
        database_bottlenecks = detect_database_bottlenecks(static_data)
        batch_monoliths = detect_batch_monoliths(static_data)
        spaghetti_code = detect_spaghetti_code(static_data, modularity_data)

        # Count severity
        critical_count = sum(1 for p in god_programs if p.get('severity') == 'critical')
        high_count = (
            sum(1 for p in god_programs if p.get('severity') == 'high') +
            len(tight_coupling_programs) +
            sum(1 for h in shared_data_hotspots if h.get('severity') == 'high')
        )
        medium_count = (
            len(database_bottlenecks) +
            len(batch_monoliths) +
            len(spaghetti_code)
        )

        total_patterns = critical_count + high_count + medium_count

        print(f"\nDetected Patterns:")
        print(f"  God Programs: {len(god_programs)}")
        print(f"  Tight Coupling: {len(tight_coupling_programs)}")
        print(f"  Shared Data Hotspots: {len(shared_data_hotspots)}")
        print(f"  Database Bottlenecks: {len(database_bottlenecks)}")
        print(f"  Batch Monoliths: {len(batch_monoliths)}")
        print(f"  Spaghetti Code: {len(spaghetti_code)}")
        print(f"\nSeverity:")
        print(f"  Critical: {critical_count}")
        print(f"  High: {high_count}")
        print(f"  Medium: {medium_count}")

        # Create result
        result = {
            'detected_patterns': {
                'god_programs': god_programs,
                'tight_coupling': tight_coupling_programs,
                'shared_data_hotspots': shared_data_hotspots,
                'circular_dependencies': [],  # Would need call graph for this
                'database_bottlenecks': database_bottlenecks,
                'batch_monoliths': batch_monoliths,
                'spaghetti_code': spaghetti_code
            },
            'summary': {
                'total_patterns': total_patterns,
                'critical': critical_count,
                'high': high_count,
                'medium': medium_count
            }
        }

        # Write to S3
        artifact_key = f"{scout_account_id}/{application_name}/monolith_identifier_v2/jobs/{job_id}/artifacts/detected_patterns.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=artifact_key,
            Body=json.dumps(result, indent=2),
            ContentType='application/json'
        )

        print(f"\nWrote artifact: s3://{BUCKET_NAME}/{artifact_key}")

        # Update status
        update_status(scout_account_id, application_name, job_id, {
            'phase': 'patterns_detected',
            'progress': 75,
            'message': f'Detected {total_patterns} monolithic patterns'
        })

        return result

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def detect_god_programs(static_data: Dict[str, Any], ai_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect god programs"""
    god_programs = []

    # From static analysis
    for program in static_data.get('programs', []):
        loc = program.get('loc', 0)
        complexity = program.get('cyclomatic_complexity', 0)

        if loc > 5000 or complexity > 100:
            severity = 'critical' if loc > 10000 else 'high'
            god_programs.append({
                'program': program['program_name'],
                'loc': loc,
                'complexity': complexity,
                'responsibilities': 1,  # Default
                'severity': severity
            })

    # Enhance with AI data
    ai_god_programs = ai_data.get('patterns_detected', {}).get('god_programs', [])
    for ai_god in ai_god_programs:
        # Find in existing list or add
        found = False
        for gp in god_programs:
            if gp['program'] == ai_god['program']:
                gp['responsibilities'] = len(ai_god.get('responsibilities', []))
                found = True
                break
        if not found:
            god_programs.append({
                'program': ai_god['program'],
                'loc': 0,
                'complexity': 0,
                'responsibilities': len(ai_god.get('responsibilities', [])),
                'severity': 'high'
            })

    return god_programs


def detect_tight_coupling(modularity_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect tight coupling"""
    tight_coupling = []

    for program in modularity_data.get('programs', []):
        if program.get('classification') == 'high_coupling':
            tight_coupling.append({
                'program': program['program'],
                'efferent_coupling': program['efferent_coupling'],
                'afferent_coupling': program['afferent_coupling'],
                'severity': 'high'
            })

    return tight_coupling


def detect_shared_data_hotspots(static_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect shared data hotspots (copybooks used by many programs)"""
    copybook_usage = {}

    for program in static_data.get('programs', []):
        for copybook in program.get('copybooks_used', []):
            if copybook not in copybook_usage:
                copybook_usage[copybook] = []
            copybook_usage[copybook].append(program['program_name'])

    hotspots = []
    for copybook, programs in copybook_usage.items():
        if len(programs) > 10:
            hotspots.append({
                'copybook': copybook,
                'used_by': len(programs),
                'programs': programs[:10],  # First 10
                'severity': 'high'
            })

    return hotspots


def detect_database_bottlenecks(static_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect database bottlenecks (programs with excessive SQL)"""
    bottlenecks = []

    for program in static_data.get('programs', []):
        db_ops = program.get('database_operations', 0)
        if db_ops > 20:
            bottlenecks.append({
                'program': program['program_name'],
                'database_operations': db_ops,
                'severity': 'medium'
            })

    return bottlenecks


def detect_batch_monoliths(static_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect batch monoliths (very large programs likely batch jobs)"""
    batch_monoliths = []

    for program in static_data.get('programs', []):
        if program.get('loc', 0) > 10000:
            batch_monoliths.append({
                'program': program['program_name'],
                'loc': program['loc'],
                'severity': 'medium'
            })

    return batch_monoliths


def detect_spaghetti_code(static_data: Dict[str, Any], modularity_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Detect spaghetti code (high complexity + low cohesion)"""
    spaghetti = []

    # Build lookup for modularity
    modularity_lookup = {p['program']: p for p in modularity_data.get('programs', [])}

    for program in static_data.get('programs', []):
        complexity = program.get('cyclomatic_complexity', 0)
        modularity = modularity_lookup.get(program['program_name'], {})
        cohesion = modularity.get('cohesion_score', 1.0)

        if complexity > 50 and cohesion < 0.4:
            spaghetti.append({
                'program': program['program_name'],
                'complexity': complexity,
                'cohesion': cohesion,
                'severity': 'medium'
            })

    return spaghetti


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
