"""
Discovery V2 - Business Process Extractor Handler
Lambda: DiscoveryV2BusinessProcessExtractor

Purpose: Extract and consolidate business processes from AI discovery analysis

V2 Design Principles:
- Runs in parallel with Integration Detector and API Pattern Analyzer
- Parses AI analysis to extract business processes
- Independent Lambda (NO code sharing)
"""

import json
import boto3
import re
from datetime import datetime, timezone
from typing import Dict, Any, List
from collections import defaultdict

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Extract Business Processes

    Input (from Step Functions - Parallel state):
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "business_processes_count": 5,
        "output_file": "s3://.../business_processes.json"
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Extracting business processes for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'business_extraction', 50, 'Extracting business processes')

        # Read AI discovery analysis
        ai_analysis_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/ai_discovery_analysis.json"

        try:
            ai_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=ai_analysis_key)
            ai_data = json.loads(ai_response['Body'].read())
        except s3_client.exceptions.NoSuchKey:
            raise Exception(f"AI analysis not found at s3://{BUCKET_NAME}/{ai_analysis_key}")

        # Extract business processes from all file analyses
        all_processes = []
        process_id_counter = 1

        for file_analysis in ai_data.get('file_analyses', []):
            file_path = file_analysis['file_path']
            analysis = file_analysis.get('analysis', {})

            # Parse business processes from raw analysis
            # NOTE: In production with Bedrock Agent, this would come structured
            # For now, parse from raw_analysis text

            raw_analysis = analysis.get('raw_analysis', '')

            # Simple extraction: Look for business process indicators
            processes = extract_business_processes_from_text(raw_analysis, file_path)

            for process in processes:
                process['process_id'] = f"bp_{process_id_counter:03d}"
                process_id_counter += 1
                all_processes.append(process)

        # Consolidate duplicate processes (same name across files)
        consolidated_processes = consolidate_processes(all_processes)

        # Calculate summary statistics
        summary = calculate_summary(consolidated_processes)

        # Create output
        output_data = {
            'business_processes': consolidated_processes,
            'summary': summary,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id
        }

        # Save to S3
        output_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/business_processes.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(output_data, indent=2),
            ContentType='application/json'
        )

        print(f"Saved business processes to s3://{BUCKET_NAME}/{output_key}")
        print(f"Extracted {len(consolidated_processes)} business processes")

        # Update status
        update_status(status_key, 'running', 'business_extraction', 55, f'Extracted {len(consolidated_processes)} business processes')

        return {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'business_processes_count': len(consolidated_processes),
            'output_file': f's3://{BUCKET_NAME}/{output_key}'
        }

    except Exception as e:
        print(f"ERROR in DiscoveryV2BusinessProcessExtractor: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def extract_business_processes_from_text(raw_analysis: str, file_path: str) -> List[Dict[str, Any]]:
    """
    Extract business processes from AI analysis text by parsing Claude's structured response
    """

    processes = []

    # Parse Business Processes section from AI analysis
    bp_section = extract_section(raw_analysis, r'\*\*Business Processes\*\*', r'\*\*Integration Points\*\*')

    if not bp_section:
        return []

    # Extract business capabilities (specific list items)
    capabilities = extract_bullet_items(bp_section, 'Business capabilities')

    # Extract business value
    business_value = extract_field_value(bp_section, r'Business value:\s*(\w+)')
    if not business_value:
        business_value = 'Low'

    # Extract complexity level
    complexity = extract_field_value(bp_section, r'Complexity level:\s*(\w+)')
    if not complexity:
        complexity = 'Medium'

    # Extract execution frequency
    execution_frequency = extract_field_value(bp_section, r'Execution frequency:\s*([\w\-]+)')
    if not execution_frequency:
        execution_frequency = 'Unknown'

    # Extract confidence score
    confidence_str = extract_field_value(bp_section, r'Confidence score:\s*(\d+)')
    confidence_score = int(confidence_str) if confidence_str else 50

    # Extract modernization insights for cloud readiness
    mod_section = extract_section(raw_analysis, r'\*\*Modernization Insights\*\*', r'(Actionable insights|$)')
    cloud_readiness = 0
    if mod_section:
        readiness_str = extract_field_value(mod_section, r'Cloud readiness.*?:\s*(\d+)')
        if readiness_str:
            cloud_readiness = int(readiness_str)

    # Extract AWS recommendations from modernization section
    aws_recommendations = []
    actionable_section = extract_section(raw_analysis, r'Actionable insights for AWS modernization strategy:', r'$')
    if actionable_section:
        aws_recommendations = extract_numbered_items(actionable_section)

    # Build process name from capabilities or filename
    if capabilities:
        process_name = capabilities[0].strip('*').strip()
        if len(process_name) > 60:
            process_name = process_name[:57] + '...'
        description = ' | '.join([c.strip('*').strip() for c in capabilities[:3]])
    else:
        # Fallback to filename-based naming
        base_name = file_path.split('/')[-1].replace('.cobol', '').replace('.cbl', '')
        process_name = f"{base_name} Program"
        description = f"Business logic in {file_path}"

    # Determine domain from capabilities
    domain = infer_domain_from_text(' '.join(capabilities) if capabilities else file_path)

    # Map business value to priority
    priority_map = {'High': 1, 'Medium': 2, 'Low': 3}
    modernization_priority = priority_map.get(business_value, 3)

    # Determine recommended approach based on value and complexity
    if business_value == 'High':
        if complexity == 'High':
            recommended_approach = 'Microservices with Event-Driven Architecture'
        else:
            recommended_approach = 'Microservice'
    elif complexity == 'Low':
        recommended_approach = 'Serverless Function (Lambda)'
    else:
        recommended_approach = 'Containerized Service (ECS/Fargate)'

    process = {
        'process_name': process_name,
        'description': description,
        'business_capabilities': capabilities,
        'business_value': business_value,
        'complexity': complexity,
        'execution_frequency': execution_frequency,
        'confidence_score': confidence_score,
        'cloud_readiness_score': cloud_readiness,
        'components_involved': [file_path],
        'business_domain': domain,
        'criticality': business_value,
        'modernization_priority': modernization_priority,
        'recommended_approach': recommended_approach,
        'aws_recommendations': aws_recommendations[:5]  # Top 5 recommendations
    }

    processes.append(process)
    return processes


def extract_section(text: str, start_pattern: str, end_pattern: str) -> str:
    """Extract text between two regex patterns"""
    try:
        start_match = re.search(start_pattern, text, re.IGNORECASE)
        if not start_match:
            return ""

        start_pos = start_match.end()
        end_match = re.search(end_pattern, text[start_pos:], re.IGNORECASE)

        if end_match:
            return text[start_pos:start_pos + end_match.start()]
        else:
            return text[start_pos:]
    except:
        return ""


def extract_field_value(text: str, pattern: str) -> str:
    """Extract field value using regex pattern"""
    try:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    except:
        pass
    return ""


def extract_bullet_items(text: str, header: str) -> List[str]:
    """Extract bullet point items under a specific header"""
    items = []
    try:
        # Find the header
        header_pattern = re.escape(header) + r'.*?:'
        header_match = re.search(header_pattern, text, re.IGNORECASE)
        if not header_match:
            return items

        # Extract text after header until next major section
        start_pos = header_match.end()
        section_text = text[start_pos:start_pos+500]  # Look ahead 500 chars

        # Find bullet items (*, -, or numbered)
        bullet_pattern = r'^\s*[\*\-]\s*(.+)$'
        for line in section_text.split('\n'):
            match = re.match(bullet_pattern, line)
            if match:
                item = match.group(1).strip()
                if item and len(item) > 3:  # Ignore very short items
                    items.append(item)
    except:
        pass

    return items


def extract_numbered_items(text: str) -> List[str]:
    """Extract numbered list items (1. 2. 3. etc)"""
    items = []
    try:
        # Find numbered items
        pattern = r'^\s*\d+\.\s*(.+)$'
        for line in text.split('\n'):
            match = re.match(pattern, line)
            if match:
                item = match.group(1).strip()
                if item and len(item) > 10:  # Only substantive items
                    items.append(item)
    except:
        pass

    return items


def infer_domain_from_text(text: str) -> str:
    """Infer business domain from text content"""
    text_lower = text.lower()

    domain_keywords = {
        'Customer Management': ['customer', 'client', 'account holder'],
        'Financial Services': ['payment', 'invoice', 'billing', 'account', 'transaction', 'payroll'],
        'Inventory & Supply Chain': ['inventory', 'stock', 'warehouse', 'shipping', 'procurement'],
        'Order Management': ['order', 'purchase', 'sales'],
        'Reporting & Analytics': ['report', 'analytics', 'dashboard'],
        'Human Resources': ['employee', 'hr', 'personnel', 'payroll'],
        'Data Processing': ['batch', 'file processing', 'data transformation']
    }

    for domain, keywords in domain_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            return domain

    return 'General Business Logic'


def consolidate_processes(all_processes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Consolidate duplicate processes with same name or similar business domain"""

    # Group by business domain (more meaningful than exact name match)
    grouped = defaultdict(list)
    for process in all_processes:
        domain = process.get('business_domain', 'General')
        grouped[domain].append(process)

    # Consolidate each group
    consolidated = []

    for domain, group in grouped.items():
        if len(group) == 1:
            # Single process in this domain
            consolidated.append(group[0])
        else:
            # Multiple processes in same domain - merge them
            merged = group[0].copy()

            # Combine components_involved
            all_components = []
            for proc in group:
                all_components.extend(proc.get('components_involved', []))
            merged['components_involved'] = sorted(list(set(all_components)))

            # Combine business capabilities
            all_capabilities = []
            for proc in group:
                all_capabilities.extend(proc.get('business_capabilities', []))
            merged['business_capabilities'] = list(set(all_capabilities))[:10]  # Top 10

            # Combine AWS recommendations (unique)
            all_recommendations = []
            for proc in group:
                all_recommendations.extend(proc.get('aws_recommendations', []))
            merged['aws_recommendations'] = list(set(all_recommendations))[:5]  # Top 5 unique

            # Use highest business value
            values = [p['business_value'] for p in group]
            if 'High' in values:
                merged['business_value'] = 'High'
                merged['criticality'] = 'High'
                merged['modernization_priority'] = 1
            elif 'Medium' in values:
                merged['business_value'] = 'Medium'
                merged['criticality'] = 'Medium'
                merged['modernization_priority'] = 2
            else:
                merged['business_value'] = 'Low'
                merged['criticality'] = 'Low'
                merged['modernization_priority'] = 3

            # Use highest confidence and cloud readiness scores
            merged['confidence_score'] = max([p.get('confidence_score', 0) for p in group])
            merged['cloud_readiness_score'] = max([p.get('cloud_readiness_score', 0) for p in group])

            # Use domain as process name
            merged['process_name'] = domain

            # Update description with component count
            comp_count = len(merged['components_involved'])
            cap_count = len(merged['business_capabilities'])
            merged['description'] = f"{domain} ({comp_count} programs, {cap_count} capabilities)"

            consolidated.append(merged)

    # Sort by modernization priority, then cloud readiness
    consolidated.sort(key=lambda x: (x.get('modernization_priority', 99), -x.get('cloud_readiness_score', 0)))

    # Assign process IDs
    for i, process in enumerate(consolidated):
        process['process_id'] = f"bp_{i+1:03d}"

    return consolidated


def calculate_summary(processes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate summary statistics"""

    total = len(processes)

    high_value = len([p for p in processes if p.get('business_value') == 'High'])
    medium_value = len([p for p in processes if p.get('business_value') == 'Medium'])
    low_value = len([p for p in processes if p.get('business_value') == 'Low'])

    real_time = len([p for p in processes if p.get('execution_frequency') == 'Real-time'])
    batch = len([p for p in processes if p.get('execution_frequency') in ['Batch', 'Daily', 'Weekly']])

    # Calculate average scores
    confidence_scores = [p.get('confidence_score', 0) for p in processes if p.get('confidence_score', 0) > 0]
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

    cloud_readiness_scores = [p.get('cloud_readiness_score', 0) for p in processes if p.get('cloud_readiness_score', 0) > 0]
    avg_cloud_readiness = sum(cloud_readiness_scores) / len(cloud_readiness_scores) if cloud_readiness_scores else 0

    # Count total capabilities and recommendations
    total_capabilities = sum([len(p.get('business_capabilities', [])) for p in processes])
    total_components = sum([len(p.get('components_involved', [])) for p in processes])

    return {
        'total_processes': total,
        'high_value_processes': high_value,
        'medium_value_processes': medium_value,
        'low_value_processes': low_value,
        'real_time_processes': real_time,
        'batch_processes': batch,
        'average_confidence_score': round(avg_confidence, 1),
        'average_cloud_readiness': round(avg_cloud_readiness, 1),
        'total_business_capabilities': total_capabilities,
        'total_components_analyzed': total_components
    }


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
