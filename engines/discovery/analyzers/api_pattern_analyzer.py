"""
API Pattern Analyzer

Analyzes execution patterns (batch vs real-time vs event-driven)
and recommends AWS architecture.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List


# Pattern indicators in COBOL code
PATTERN_INDICATORS = {
    'batch_processing': {
        'code_patterns': [
            'SORT', 'MERGE', 'OPEN INPUT', 'OPEN OUTPUT',
            'READ', 'WRITE', 'REWRITE', 'START', 'DELETE'
        ],
        'jcl_patterns': ['JOB', 'EXEC PGM', 'DD '],
        'weight': 1.0
    },
    'real_time_transaction': {
        'code_patterns': [
            'EXEC CICS', 'RECEIVE', 'SEND', 'RETURN',
            'XCTL', 'LINK', 'DFHCOMMAREA'
        ],
        'weight': 1.5  # Higher weight - CICS is strong indicator
    },
    'event_driven': {
        'code_patterns': [
            'MQGET', 'MQPUT', 'MQ', 'TRIGGER',
            'EXEC IMS', 'GU PCB'
        ],
        'weight': 1.2
    },
    'database_centric': {
        'code_patterns': [
            'EXEC SQL', 'SELECT', 'INSERT', 'UPDATE', 'DELETE',
            'CURSOR', 'FETCH'
        ],
        'weight': 0.8  # Database alone doesn't determine pattern
    }
}

# AWS architecture recommendations by pattern
AWS_ARCHITECTURES = {
    'real_time_transaction': {
        'primary_service': 'Amazon API Gateway + AWS Lambda',
        'supporting_services': ['Amazon DynamoDB', 'Amazon RDS', 'AWS WAF', 'Amazon CloudWatch'],
        'architecture_pattern': 'Serverless Microservices',
        'estimated_cost_monthly': '$500 - $5,000 (depending on transaction volume)',
        'scalability': 'Auto-scaling, handles millions of requests',
        'complexity': 'Medium',
        'rationale': 'CICS transactions map well to Lambda functions behind API Gateway'
    },
    'batch_processing': {
        'primary_service': 'AWS Step Functions + AWS Batch',
        'supporting_services': ['Amazon S3', 'AWS Lambda', 'Amazon EventBridge', 'Amazon RDS'],
        'architecture_pattern': 'Serverless Batch Orchestration',
        'estimated_cost_monthly': '$200 - $2,000 (depending on batch volume)',
        'scalability': 'Auto-scaling compute with AWS Batch',
        'complexity': 'Low',
        'rationale': 'JCL job streams map to Step Functions state machines'
    },
    'event_driven': {
        'primary_service': 'Amazon EventBridge + AWS Lambda',
        'supporting_services': ['Amazon SQS', 'Amazon SNS', 'Amazon DynamoDB', 'AWS Step Functions'],
        'architecture_pattern': 'Event-Driven Architecture',
        'estimated_cost_monthly': '$300 - $3,000 (depending on event volume)',
        'scalability': 'Highly scalable, decoupled components',
        'complexity': 'Medium',
        'rationale': 'MQ/IMS messaging maps to EventBridge and SQS'
    },
    'hybrid': {
        'primary_service': 'Amazon ECS/Fargate + API Gateway',
        'supporting_services': ['AWS Step Functions', 'Amazon SQS', 'Amazon RDS', 'Amazon S3'],
        'architecture_pattern': 'Hybrid Containerized Architecture',
        'estimated_cost_monthly': '$1,000 - $10,000 (depending on complexity)',
        'scalability': 'Auto-scaling containers',
        'complexity': 'High',
        'rationale': 'Mixed workloads benefit from containerized services'
    }
}


class APIPatternAnalyzer:
    """
    Analyze API/execution patterns from COBOL code and integrations.
    """

    def analyze(
        self,
        business_processes: Dict[str, Any],
        integration_points: Dict[str, Any],
        ai_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze execution patterns and recommend AWS architecture.

        Args:
            business_processes: From BusinessProcessExtractor
            integration_points: From IntegrationDetector
            ai_analysis: From AIDiscoveryAnalyzer

        Returns:
            API pattern analysis with AWS recommendations
        """
        # Count pattern indicators
        pattern_scores = self._score_patterns(
            business_processes,
            integration_points,
            ai_analysis
        )

        # Determine primary pattern
        primary_pattern, distribution = self._determine_primary_pattern(pattern_scores)

        # Get file-level pattern details
        pattern_details = self._get_pattern_details(business_processes)

        # Get AWS recommendation
        aws_rec = AWS_ARCHITECTURES.get(primary_pattern, AWS_ARCHITECTURES['hybrid'])

        return {
            'primary_api_pattern': primary_pattern,
            'pattern_distribution': distribution,
            'pattern_details': pattern_details,
            'aws_architecture_recommendation': aws_rec,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    def _score_patterns(
        self,
        business_processes: Dict,
        integration_points: Dict,
        ai_analysis: Dict
    ) -> Dict[str, float]:
        """Calculate scores for each pattern type."""
        scores = {
            'batch_processing': 0.0,
            'real_time_transaction': 0.0,
            'event_driven': 0.0
        }

        # Score from integrations (most reliable)
        integrations = integration_points.get('integration_points', [])
        for ip in integrations:
            system = ip.get('system_name', '').upper()
            match_count = ip.get('match_count', 1)

            if 'CICS' in system:
                scores['real_time_transaction'] += match_count * 2
            elif 'MQ' in system or 'IMS' in system:
                scores['event_driven'] += match_count * 1.5
            elif any(x in system for x in ['VSAM', 'QSAM', 'JCL']):
                scores['batch_processing'] += match_count

        # Score from business processes
        processes = business_processes.get('business_processes', [])
        for proc in processes:
            freq = proc.get('execution_frequency', 'Batch')
            if freq == 'Real-time':
                scores['real_time_transaction'] += 2
            elif freq in ['Daily', 'Weekly', 'Monthly', 'Batch']:
                scores['batch_processing'] += 1

        return scores

    def _determine_primary_pattern(
        self,
        scores: Dict[str, float]
    ) -> tuple:
        """Determine primary pattern and distribution."""
        total = sum(scores.values())

        if total == 0:
            # Default to batch if no indicators
            return 'batch_processing', {
                'batch_processing': 100.0,
                'real_time_transaction': 0.0,
                'event_driven': 0.0
            }

        # Calculate distribution
        distribution = {
            pattern: round((score / total) * 100, 1)
            for pattern, score in scores.items()
        }

        # Determine primary
        primary = max(scores, key=scores.get)

        # Check for hybrid (no clear winner)
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[0] > 0:
            ratio = sorted_scores[1] / sorted_scores[0]
            if ratio > 0.7:  # Second place is within 70% of first
                primary = 'hybrid'
                distribution['hybrid'] = distribution.get('hybrid', 0)

        return primary, distribution

    def _get_pattern_details(self, business_processes: Dict) -> List[Dict]:
        """Get pattern details by file/process."""
        details = []

        for proc in business_processes.get('business_processes', []):
            freq = proc.get('execution_frequency', 'Unknown')
            pattern = 'batch_processing'
            if freq == 'Real-time':
                pattern = 'real_time_transaction'

            details.append({
                'process_name': proc.get('name', 'Unknown'),
                'pattern': pattern,
                'frequency': freq,
                'components': proc.get('components_involved', [])[:5]
            })

        return details


def analyze_api_patterns(
    business_processes: Dict[str, Any],
    integration_points: Dict[str, Any],
    ai_analysis: Dict[str, Any]
) -> Dict[str, Any]:
    """Convenience function for API pattern analysis."""
    analyzer = APIPatternAnalyzer()
    return analyzer.analyze(business_processes, integration_points, ai_analysis)
