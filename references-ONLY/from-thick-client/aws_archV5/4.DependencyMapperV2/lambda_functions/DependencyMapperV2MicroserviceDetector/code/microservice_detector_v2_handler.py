"""
Dependency Mapper V2 - Microservice Detector Handler
Lambda: DependencyMapperV2MicroserviceDetector

Purpose: Suggest microservice boundaries based on coupling analysis

V2 Design Principles:
- Standalone architecture (NO integration with other flows)
- Independent Lambda (NO code sharing)
- Event-driven architecture
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List, Set
from collections import defaultdict

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Detect Microservice Boundaries

    Input (from Step Functions):
    {
        "job_id": "dmv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "microservice_boundaries_detected": true,
        "suggested_services_count": 4
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Detecting microservice boundaries for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'detecting_services', 80, 'Detecting microservice boundaries')

        # Read dependency_graph.json
        graph_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/dependency_graph.json"
        graph_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=graph_key)
        graph_data = json.loads(graph_response['Body'].read())

        nodes = graph_data.get('nodes', [])
        edges = graph_data.get('edges', [])

        # Read coupling_metrics.json
        coupling_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/coupling_metrics.json"
        coupling_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=coupling_key)
        coupling_data = json.loads(coupling_response['Body'].read())

        program_metrics = coupling_data.get('by_program', [])

        # Use simple clustering algorithm based on call patterns
        # Programs that call each other frequently should be in same service
        clusters = cluster_programs(nodes, edges, program_metrics)

        # Build suggested services
        suggested_services = []
        for cluster_id, programs in clusters.items():
            if not programs:
                continue

            # Calculate internal vs external coupling
            internal_edges = 0
            external_edges = 0

            for edge in edges:
                if edge['type'] in ['CALL', 'LINK', 'XCTL']:
                    source = edge['from']
                    target = edge['to']

                    if source in programs and target in programs:
                        internal_edges += 1
                    elif source in programs or target in programs:
                        external_edges += 1

            total_edges = internal_edges + external_edges
            internal_coupling = internal_edges / total_edges if total_edges > 0 else 0
            external_coupling = external_edges / total_edges if total_edges > 0 else 0

            # Calculate cohesion score (average of program cohesion scores in cluster)
            cluster_cohesion = 0
            for program in programs:
                for metric in program_metrics:
                    if metric['program'] == program:
                        cluster_cohesion += metric.get('cohesion_score', 0)
                        break
            avg_cohesion = cluster_cohesion / len(programs) if programs else 0

            # Generate service name from first program
            first_program = programs[0].replace('.cobol', '').replace('.cbl', '')
            # Extract business domain hint from program name
            if 'ORD' in first_program.upper():
                service_name = 'OrderService'
            elif 'CUST' in first_program.upper():
                service_name = 'CustomerService'
            elif 'INV' in first_program.upper():
                service_name = 'InventoryService'
            elif 'BILL' in first_program.upper() or 'PAY' in first_program.upper():
                service_name = 'BillingService'
            elif 'SHIP' in first_program.upper():
                service_name = 'ShippingService'
            else:
                service_name = f'Service{cluster_id}'

            suggested_services.append({
                'service_name': service_name,
                'programs': programs,
                'program_count': len(programs),
                'internal_coupling': round(internal_coupling, 3),
                'external_coupling': round(external_coupling, 3),
                'cohesion_score': round(avg_cohesion, 3),
                'justification': f'High internal cohesion ({round(internal_coupling*100, 1)}%), low external coupling'
            })

        # Sort by program count (descending)
        suggested_services.sort(key=lambda x: x['program_count'], reverse=True)

        # Identify shared components (copybooks used by multiple services)
        shared_components = identify_shared_components(nodes, edges, clusters)

        microservice_boundaries = {
            'suggested_services': suggested_services,
            'shared_components': shared_components,
            'summary': {
                'total_services_suggested': len(suggested_services),
                'total_shared_components': len(shared_components)
            },
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id
        }

        # Save to S3
        output_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/microservice_boundaries.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(microservice_boundaries, indent=2),
            ContentType='application/json'
        )

        print(f"Saved microservice boundaries to s3://{BUCKET_NAME}/{output_key}")
        print(f"Suggested {len(suggested_services)} microservices")

        # Update status
        update_status(status_key, 'running', 'services_detected', 85, f'Suggested {len(suggested_services)} microservice boundaries')

        return {
            'microservice_boundaries_detected': True,
            'suggested_services_count': len(suggested_services)
        }

    except Exception as e:
        print(f"ERROR in DependencyMapperV2MicroserviceDetector: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def cluster_programs(nodes: List[Dict], edges: List[Dict], program_metrics: List[Dict]) -> Dict[int, List[str]]:
    """Simple clustering algorithm based on call patterns"""
    program_nodes = [n['id'] for n in nodes if n['type'] == 'program']

    # Build adjacency matrix
    adjacency = defaultdict(set)
    for edge in edges:
        if edge['type'] in ['CALL', 'LINK', 'XCTL']:
            source = edge['from']
            target = edge['to']
            adjacency[source].add(target)
            adjacency[target].add(source)  # Bidirectional for clustering

    # Simple clustering: programs that call each other are in same cluster
    visited = set()
    clusters = {}
    cluster_id = 0

    def dfs(program: str, cluster: Set[str]):
        if program in visited:
            return
        visited.add(program)
        cluster.add(program)

        # Visit neighbors (but limit depth to avoid huge clusters)
        for neighbor in list(adjacency.get(program, []))[:5]:  # Max 5 neighbors to avoid God programs
            if neighbor not in visited:
                dfs(neighbor, cluster)

    for program in program_nodes:
        if program not in visited:
            cluster = set()
            dfs(program, cluster)
            if cluster:
                clusters[cluster_id] = list(cluster)
                cluster_id += 1

    return clusters


def identify_shared_components(nodes: List[Dict], edges: List[Dict], clusters: Dict[int, List[str]]) -> List[Dict]:
    """Identify copybooks used by multiple services"""
    shared_components = []

    # Get copybooks
    copybooks = [n for n in nodes if n['type'] == 'copybook']

    for copybook in copybooks:
        copybook_id = copybook['id']

        # Find which programs use this copybook
        using_programs = [
            edge['from'] for edge in edges
            if edge['to'] == copybook_id and edge['type'] == 'COPY'
        ]

        # Find which services these programs belong to
        services_using = set()
        for program in using_programs:
            for cluster_id, cluster_programs in clusters.items():
                if program in cluster_programs:
                    services_using.add(cluster_id)

        # If used by multiple services, it's shared
        if len(services_using) >= 2:
            shared_components.append({
                'component': copybook_id,
                'component_type': 'copybook',
                'used_by_services_count': len(services_using),
                'used_by_programs_count': len(using_programs),
                'recommendation': 'Create shared library or duplicate to avoid cross-service dependencies'
            })

    # Sort by usage count (descending)
    shared_components.sort(key=lambda x: x['used_by_services_count'], reverse=True)

    return shared_components


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
