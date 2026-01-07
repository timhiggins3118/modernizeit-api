"""
Discovery V2 - API Pattern Analyzer Handler
Lambda: DiscoveryV2APIPatternAnalyzer

Purpose: Analyze and classify API patterns (batch vs real-time vs event-driven)

V2 Design Principles:
- Runs in parallel with Business Process Extractor and Integration Detector
- Classifies execution patterns
- Recommends AWS architectures
- Independent Lambda (NO code sharing)
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List
from collections import Counter

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Analyze API Patterns

    Input (from Step Functions - Parallel state):
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "job_id": "dv2_job_5150_TestApp01_1759440123_a7b3c9d2",
        "primary_api_pattern": "batch_processing",
        "output_file": "s3://.../api_patterns.json"
    }
    """
    try:
        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Analyzing API patterns for job {job_id}")

        # Update status
        status_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/status.json"
        update_status(status_key, 'running', 'api_pattern_analysis', 75, 'Analyzing API patterns')

        # Read AI discovery analysis
        ai_analysis_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/ai_discovery_analysis.json"

        try:
            ai_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=ai_analysis_key)
            ai_data = json.loads(ai_response['Body'].read())
        except s3_client.exceptions.NoSuchKey:
            raise Exception(f"AI analysis not found at s3://{BUCKET_NAME}/{ai_analysis_key}")

        # Analyze API patterns from all file analyses
        all_patterns = []

        for file_analysis in ai_data.get('file_analyses', []):
            file_path = file_analysis['file_path']
            analysis = file_analysis.get('analysis', {})

            raw_analysis = analysis.get('raw_analysis', '')

            # Detect API pattern
            pattern = detect_api_pattern(raw_analysis, file_path)

            all_patterns.append({
                'file_path': file_path,
                'pattern': pattern['pattern_type'],
                'confidence': pattern['confidence'],
                'indicators': pattern['indicators'],
                'aws_recommendation': pattern['aws_recommendation']
            })

        # Determine primary pattern (most common)
        pattern_counts = Counter([p['pattern'] for p in all_patterns])
        primary_pattern = pattern_counts.most_common(1)[0][0] if pattern_counts else 'unknown'

        # Calculate distribution
        total_files = len(all_patterns)
        distribution = {
            pattern: count / total_files * 100
            for pattern, count in pattern_counts.items()
        }

        # Create output
        output_data = {
            'primary_api_pattern': primary_pattern,
            'pattern_distribution': distribution,
            'file_patterns': all_patterns,
            'summary': {
                'total_files_analyzed': total_files,
                'batch_processing_count': pattern_counts.get('batch_processing', 0),
                'real_time_transaction_count': pattern_counts.get('real_time_transaction', 0),
                'event_driven_count': pattern_counts.get('event_driven', 0),
                'hybrid_count': pattern_counts.get('hybrid', 0)
            },
            'aws_architecture_recommendation': recommend_aws_architecture(primary_pattern, pattern_counts),
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id
        }

        # Save to S3
        output_key = f"{scout_account_id}/{application_name}/discovery_v2/jobs/{job_id}/artifacts/api_patterns.json"

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(output_data, indent=2),
            ContentType='application/json'
        )

        print(f"Saved API patterns to s3://{BUCKET_NAME}/{output_key}")
        print(f"Primary pattern: {primary_pattern}")

        # Update status
        update_status(status_key, 'running', 'api_pattern_analysis', 80, f'API pattern: {primary_pattern}')

        return {
            'job_id': job_id,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'primary_api_pattern': primary_pattern,
            'output_file': f's3://{BUCKET_NAME}/{output_key}'
        }

    except Exception as e:
        print(f"ERROR in DiscoveryV2APIPatternAnalyzer: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def detect_api_pattern(raw_analysis: str, file_path: str) -> Dict[str, Any]:
    """Detect API pattern from AI analysis by parsing Claude's structured response"""

    # Extract API Pattern Analysis section
    api_section = extract_section(raw_analysis, r'\*\*API Pattern Analysis\*\*', r'\*\*Data Flow Mapping\*\*')

    if api_section:
        # Extract execution pattern from AI analysis
        pattern_type = extract_execution_pattern(api_section)

        # Extract AWS architecture recommendation
        aws_recommendation = extract_aws_architecture_recommendation(api_section)

        # Determine confidence based on pattern clarity
        confidence = determine_pattern_confidence(api_section, pattern_type)

        # Extract indicators
        indicators = extract_pattern_indicators(api_section)
    else:
        # Fallback to keyword-based detection
        pattern_type, confidence, indicators, aws_recommendation = fallback_pattern_detection(raw_analysis, file_path)

    return {
        'pattern_type': pattern_type,
        'confidence': confidence,
        'indicators': indicators,
        'aws_recommendation': aws_recommendation
    }


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


def extract_execution_pattern(api_section: str) -> str:
    """Extract execution pattern from API Pattern Analysis section"""
    lower_section = api_section.lower()

    # Check for explicit pattern classification
    if 'batch processing' in lower_section or 'batch' in lower_section and ('scheduled' in lower_section or 'file-driven' in lower_section):
        return 'batch_processing'
    elif 'real-time transaction' in lower_section or 'real-time' in lower_section:
        return 'real_time_transaction'
    elif 'event-driven' in lower_section or 'event' in lower_section and 'message' in lower_section:
        return 'event_driven'
    elif 'hybrid' in lower_section or 'mixed' in lower_section:
        return 'hybrid'
    else:
        return 'unknown'


def extract_aws_architecture_recommendation(api_section: str) -> str:
    """Extract AWS architecture recommendation from section"""
    # Look for "Recommended AWS architecture" line
    pattern = r'Recommended AWS architecture:?\s*(.+?)(?:\n|$)'
    match = re.search(pattern, api_section, re.IGNORECASE)

    if match:
        return match.group(1).strip()

    # Fallback: extract first AWS service mentioned
    aws_services = ['Lambda', 'API Gateway', 'Step Functions', 'EventBridge', 'AWS Batch', 'ECS', 'Fargate', 'SQS']
    for service in aws_services:
        if service.lower() in api_section.lower():
            return f"{service} architecture"

    return 'Cloud-native architecture'


def determine_pattern_confidence(api_section: str, pattern_type: str) -> int:
    """Determine confidence score based on pattern clarity"""
    if pattern_type == 'unknown':
        return 0

    # Check if pattern is explicitly mentioned
    pattern_keywords = {
        'batch_processing': ['batch', 'scheduled', 'nightly', 'daily'],
        'real_time_transaction': ['real-time', 'online', 'request/response', 'interactive'],
        'event_driven': ['event', 'message', 'trigger', 'async'],
        'hybrid': ['hybrid', 'mixed', 'both']
    }

    keywords = pattern_keywords.get(pattern_type, [])
    matches = sum(1 for kw in keywords if kw in api_section.lower())

    # Score: 40 base + 15 per keyword match (max 100)
    confidence = min(40 + (matches * 15), 100)

    return confidence


def extract_pattern_indicators(api_section: str) -> List[str]:
    """Extract pattern indicators from API section"""
    indicators = []
    lower_section = api_section.lower()

    indicator_map = {
        'batch_processing': ['batch', 'scheduled', 'file-driven'],
        'real_time_transaction': ['real-time', 'online', 'request/response'],
        'event_driven': ['event', 'message-triggered', 'async']
    }

    for pattern, keywords in indicator_map.items():
        if any(kw in lower_section for kw in keywords):
            indicators.append(pattern)

    return indicators if indicators else ['unknown']


def fallback_pattern_detection(raw_analysis: str, file_path: str) -> tuple:
    """Fallback keyword-based pattern detection"""
    lower_analysis = raw_analysis.lower()
    lower_file = file_path.lower()

    # Batch processing indicators
    batch_indicators = ['batch', 'daily', 'weekly', 'scheduled', 'nightly', 'report', 'file-driven']
    batch_score = sum(1 for indicator in batch_indicators if indicator in lower_analysis or indicator in lower_file)

    # Real-time transaction indicators
    realtime_indicators = ['cics', 'real-time', 'online', 'transaction', 'api', 'request', 'response', 'interactive']
    realtime_score = sum(1 for indicator in realtime_indicators if indicator in lower_analysis or indicator in lower_file)

    # Event-driven indicators
    event_indicators = ['mq', 'message', 'queue', 'event', 'trigger', 'async', 'asynchronous']
    event_score = sum(1 for indicator in event_indicators if indicator in lower_analysis or indicator in lower_file)

    # Determine pattern based on scores
    scores = {
        'batch_processing': batch_score,
        'real_time_transaction': realtime_score,
        'event_driven': event_score
    }

    max_score = max(scores.values())

    if max_score == 0:
        return 'unknown', 0, [], 'Further analysis required'
    elif list(scores.values()).count(max_score) > 1:
        indicators = [k for k, v in scores.items() if v == max_score]
        return 'hybrid', 60, indicators, 'Hybrid architecture (Step Functions + Lambda + EventBridge)'
    else:
        pattern_type = max(scores, key=scores.get)
        confidence = min(max_score * 20, 100)
        indicators = [pattern_type]

        if pattern_type == 'batch_processing':
            aws_recommendation = 'AWS Batch or Step Functions with scheduled EventBridge triggers'
        elif pattern_type == 'real_time_transaction':
            aws_recommendation = 'API Gateway + Lambda or ECS Fargate'
        elif pattern_type == 'event_driven':
            aws_recommendation = 'EventBridge + Lambda + SQS/SNS'
        else:
            aws_recommendation = 'Custom architecture'

        return pattern_type, confidence, indicators, aws_recommendation


def recommend_aws_architecture(primary_pattern: str, pattern_counts: Counter) -> Dict[str, Any]:
    """Recommend AWS architecture based on patterns"""

    if primary_pattern == 'batch_processing':
        return {
            'primary_service': 'AWS Batch',
            'supporting_services': ['EventBridge', 'Step Functions', 'S3'],
            'architecture_pattern': 'Scheduled batch processing with event-driven orchestration',
            'estimated_cost_monthly': '$500-2000 (based on compute hours)',
            'scalability': 'High',
            'complexity': 'Medium'
        }
    elif primary_pattern == 'real_time_transaction':
        return {
            'primary_service': 'API Gateway + Lambda',
            'supporting_services': ['RDS', 'DynamoDB', 'ElastiCache'],
            'architecture_pattern': 'Serverless REST API with managed databases',
            'estimated_cost_monthly': '$1000-5000 (based on request volume)',
            'scalability': 'Very High',
            'complexity': 'Medium'
        }
    elif primary_pattern == 'event_driven':
        return {
            'primary_service': 'EventBridge',
            'supporting_services': ['Lambda', 'SQS', 'SNS', 'Step Functions'],
            'architecture_pattern': 'Event-driven microservices with message queues',
            'estimated_cost_monthly': '$300-1500 (based on event volume)',
            'scalability': 'Very High',
            'complexity': 'High'
        }
    elif primary_pattern == 'hybrid':
        return {
            'primary_service': 'Step Functions',
            'supporting_services': ['Lambda', 'EventBridge', 'API Gateway', 'SQS'],
            'architecture_pattern': 'Hybrid orchestration supporting multiple patterns',
            'estimated_cost_monthly': '$1500-6000 (based on mixed workloads)',
            'scalability': 'High',
            'complexity': 'High'
        }
    else:
        return {
            'primary_service': 'Custom',
            'supporting_services': ['Lambda', 'ECS'],
            'architecture_pattern': 'Custom architecture - requires detailed analysis',
            'estimated_cost_monthly': 'TBD',
            'scalability': 'Medium',
            'complexity': 'Medium'
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
