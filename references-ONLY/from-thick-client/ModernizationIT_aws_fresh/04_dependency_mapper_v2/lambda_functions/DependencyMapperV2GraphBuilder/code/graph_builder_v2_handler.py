"""
Dependency Mapper V2 - Graph Builder Handler
Lambda: DependencyMapperV2GraphBuilder

Purpose: Build dependency graph from static + AI analysis

V2 Design Principles:
- Standalone architecture (NO integration with other flows)
- Independent Lambda (NO code sharing)
- Event-driven architecture
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List, Set

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Build Dependency Graph

    Input (from Step Functions):
    {
        "job_id": "dmv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "graph_built": true,
        "total_nodes": 45,
        "total_edges": 156,
        "cycles_detected": 2
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Building dependency graph for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'building_graph', 60, 'Building dependency graph')

        # Read static_analysis.json
        static_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/static_analysis.json"
        static_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=static_key)
        static_data = json.loads(static_response['Body'].read())

        programs = static_data.get('programs', [])

        # Build graph structure
        nodes = []
        edges = []
        node_ids = set()

        # Create nodes for programs and copybooks
        for program_data in programs:
            program = program_data['program']

            # Add program node
            if program not in node_ids:
                nodes.append({
                    'id': program,
                    'type': 'program',
                    'fan_in': 0,  # Will be calculated
                    'fan_out': len(program_data.get('calls', [])),
                    'lines_of_code': 0,  # Not available in static analysis
                    'complexity_score': 0  # Not available in static analysis
                })
                node_ids.add(program)

            # Add program call edges
            for call in program_data.get('calls', []):
                target = call['target']
                edges.append({
                    'from': program,
                    'to': target,
                    'type': call['type'],
                    'line_number': call['line']
                })

                # Ensure target program node exists
                if target not in node_ids:
                    nodes.append({
                        'id': target,
                        'type': 'program',
                        'fan_in': 0,
                        'fan_out': 0
                    })
                    node_ids.add(target)

            # Add copybook nodes and edges
            for copy in program_data.get('copies', []):
                copybook = copy['copybook']

                # Add copybook node if not exists
                if copybook not in node_ids:
                    nodes.append({
                        'id': copybook,
                        'type': 'copybook',
                        'used_by_count': 0,
                        'programs': []
                    })
                    node_ids.add(copybook)

                # Add edge
                edges.append({
                    'from': program,
                    'to': copybook,
                    'type': 'COPY',
                    'line_number': copy['line']
                })

        # Calculate fan-in for each node
        fan_in_counts = {}
        for edge in edges:
            target = edge['to']
            fan_in_counts[target] = fan_in_counts.get(target, 0) + 1

        for node in nodes:
            node_id = node['id']
            node['fan_in'] = fan_in_counts.get(node_id, 0)

        # Update copybook used_by_count and programs
        for node in nodes:
            if node['type'] == 'copybook':
                copybook_id = node['id']
                using_programs = [edge['from'] for edge in edges if edge['to'] == copybook_id and edge['type'] == 'COPY']
                node['used_by_count'] = len(using_programs)
                node['programs'] = using_programs

        # Detect cycles using DFS
        cycles = detect_cycles(nodes, edges)

        # Build graph summary
        total_nodes = len(nodes)
        total_edges = len(edges)
        max_depth = calculate_max_depth(nodes, edges)

        dependency_graph = {
            'nodes': nodes,
            'edges': edges,
            'summary': {
                'total_nodes': total_nodes,
                'total_edges': total_edges,
                'max_depth': max_depth,
                'cyclic_groups': len(cycles),
                'cycles': cycles
            },
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id
        }

        # Save to S3
        output_key = f"{scout_account_id}/{application_name}/dependency_mapper_v2/jobs/{job_id}/artifacts/dependency_graph.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(dependency_graph, indent=2),
            ContentType='application/json'
        )

        print(f"Saved dependency graph to s3://{BUCKET_NAME}/{output_key}")
        print(f"Graph: {total_nodes} nodes, {total_edges} edges, {len(cycles)} cycles")

        # Update status
        update_status(status_key, 'running', 'graph_built', 65, f'Graph built: {total_nodes} nodes, {total_edges} edges')

        return {
            'graph_built': True,
            'total_nodes': total_nodes,
            'total_edges': total_edges,
            'cycles_detected': len(cycles)
        }

    except Exception as e:
        print(f"ERROR in DependencyMapperV2GraphBuilder: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def detect_cycles(nodes: List[Dict], edges: List[Dict]) -> List[List[str]]:
    """Detect circular dependencies using DFS"""
    # Build adjacency list (only program-to-program edges)
    graph = {}
    for edge in edges:
        if edge['type'] in ['CALL', 'LINK', 'XCTL']:
            source = edge['from']
            target = edge['to']
            if source not in graph:
                graph[source] = []
            graph[source].append(target)

    # DFS to detect cycles
    cycles = []
    visited = set()
    rec_stack = []

    def dfs(node: str, path: List[str]):
        if node in rec_stack:
            # Found cycle
            cycle_start = rec_stack.index(node)
            cycle = rec_stack[cycle_start:] + [node]
            cycles.append(cycle)
            return

        if node in visited:
            return

        visited.add(node)
        rec_stack.append(node)

        if node in graph:
            for neighbor in graph[node]:
                dfs(neighbor, path + [neighbor])

        rec_stack.pop()

    # Run DFS from all program nodes
    program_nodes = [n['id'] for n in nodes if n['type'] == 'program']
    for node in program_nodes:
        if node not in visited:
            dfs(node, [node])

    return cycles


def calculate_max_depth(nodes: List[Dict], edges: List[Dict]) -> int:
    """Calculate maximum depth of dependency tree"""
    # Build adjacency list
    graph = {}
    for edge in edges:
        if edge['type'] in ['CALL', 'LINK', 'XCTL']:
            source = edge['from']
            target = edge['to']
            if source not in graph:
                graph[source] = []
            graph[source].append(target)

    # Find nodes with no incoming edges (roots)
    all_targets = set(edge['to'] for edge in edges if edge['type'] in ['CALL', 'LINK', 'XCTL'])
    all_sources = set(edge['from'] for edge in edges if edge['type'] in ['CALL', 'LINK', 'XCTL'])
    roots = all_sources - all_targets

    if not roots:
        return 0

    # BFS to find max depth
    max_depth = 0
    visited = set()

    def bfs_depth(start_node: str) -> int:
        queue = [(start_node, 0)]
        max_d = 0

        while queue:
            node, depth = queue.pop(0)

            if node in visited:
                continue

            visited.add(node)
            max_d = max(max_d, depth)

            if node in graph:
                for neighbor in graph[node]:
                    queue.append((neighbor, depth + 1))

        return max_d

    for root in roots:
        depth = bfs_depth(root)
        max_depth = max(max_depth, depth)

    return max_depth


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
