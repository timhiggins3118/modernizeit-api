"""
Business Process Extractor

Consolidates and enriches business processes from AI analysis.
Groups related processes, assigns priorities, recommends approaches.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List


# Domain keywords for classification
DOMAIN_KEYWORDS = {
    'Payroll Processing': ['payroll', 'salary', 'wage', 'deduction', 'tax', 'benefit'],
    'Customer Management': ['customer', 'client', 'account', 'member', 'subscriber'],
    'Financial Services': ['payment', 'invoice', 'billing', 'transaction', 'ledger', 'balance'],
    'Inventory Management': ['inventory', 'stock', 'warehouse', 'item', 'product', 'sku'],
    'Order Processing': ['order', 'purchase', 'sale', 'quote', 'fulfillment'],
    'Claims Processing': ['claim', 'policy', 'coverage', 'premium', 'adjudication'],
    'Human Resources': ['employee', 'hr', 'personnel', 'hire', 'termination'],
    'Reporting & Analytics': ['report', 'summary', 'analytics', 'dashboard', 'extract'],
    'Data Processing': ['batch', 'file', 'transform', 'load', 'etl', 'conversion']
}

# AWS recommendations by characteristics
AWS_RECOMMENDATIONS = {
    ('High', 'Real-time'): {
        'approach': 'Microservices with Event-Driven Architecture',
        'services': ['API Gateway', 'Lambda', 'EventBridge', 'DynamoDB']
    },
    ('High', 'Batch'): {
        'approach': 'Containerized Batch Processing',
        'services': ['AWS Batch', 'Step Functions', 'S3', 'RDS']
    },
    ('Medium', 'Real-time'): {
        'approach': 'Serverless API',
        'services': ['API Gateway', 'Lambda', 'RDS']
    },
    ('Medium', 'Batch'): {
        'approach': 'Serverless Batch',
        'services': ['Step Functions', 'Lambda', 'S3']
    },
    ('Low', 'Real-time'): {
        'approach': 'Simple Lambda Function',
        'services': ['Lambda', 'API Gateway']
    },
    ('Low', 'Batch'): {
        'approach': 'Scheduled Lambda',
        'services': ['EventBridge Scheduler', 'Lambda', 'S3']
    }
}


class BusinessProcessExtractor:
    """
    Extract and consolidate business processes from AI analysis.
    """

    def extract(self, ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract business processes from AI analysis results.

        Args:
            ai_analysis: Output from AIDiscoveryAnalyzer

        Returns:
            Consolidated business processes with recommendations
        """
        raw_processes = ai_analysis.get('business_processes', [])

        if not raw_processes:
            return self._empty_result()

        # Consolidate by domain
        consolidated = self._consolidate_by_domain(raw_processes)

        # Enrich with priorities and recommendations
        enriched = self._enrich_processes(consolidated)

        # Sort by priority
        enriched.sort(key=lambda x: (x['modernization_priority'], -x['confidence_score']))

        # Assign IDs
        for i, process in enumerate(enriched):
            process['process_id'] = f"bp_{i+1:03d}"

        # Calculate summary
        summary = self._calculate_summary(enriched)

        return {
            'business_processes': enriched,
            'summary': summary,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    def _consolidate_by_domain(self, processes: List[Dict]) -> List[Dict]:
        """
        Consolidate processes by business domain.

        Merges multiple files with same domain into single process.
        """
        by_domain = defaultdict(list)

        for proc in processes:
            domain = proc.get('business_domain', 'General Business Logic')
            by_domain[domain].append(proc)

        consolidated = []

        for domain, group in by_domain.items():
            if len(group) == 1:
                # Single process
                consolidated.append(group[0])
            else:
                # Merge multiple processes
                merged = self._merge_processes(domain, group)
                consolidated.append(merged)

        return consolidated

    def _merge_processes(self, domain: str, processes: List[Dict]) -> Dict:
        """Merge multiple processes into one consolidated process."""

        # Collect all source files
        all_files = []
        for proc in processes:
            if proc.get('source_file'):
                all_files.append(proc['source_file'])

        # Take highest business value
        values = [p.get('business_value', 'Low') for p in processes]
        if 'High' in values:
            business_value = 'High'
        elif 'Medium' in values:
            business_value = 'Medium'
        else:
            business_value = 'Low'

        # Take highest complexity
        complexities = [p.get('complexity', 'Low') for p in processes]
        if 'High' in complexities:
            complexity = 'High'
        elif 'Medium' in complexities:
            complexity = 'Medium'
        else:
            complexity = 'Low'

        # Determine frequency (Real-time takes precedence)
        frequencies = [p.get('execution_frequency', 'Batch') for p in processes]
        if 'Real-time' in frequencies:
            frequency = 'Real-time'
        else:
            frequency = frequencies[0]

        # Max confidence and cloud readiness
        confidence = max(p.get('confidence_score', 50) for p in processes)
        cloud_readiness = max(
            p.get('modernization_insights', {}).get('cloud_readiness_score', 50)
            for p in processes
        )

        # Combine descriptions
        descriptions = [p.get('description', '') for p in processes if p.get('description')]
        description = ' | '.join(descriptions[:3])

        return {
            'name': domain,
            'description': description or f"{domain} ({len(all_files)} programs)",
            'business_value': business_value,
            'complexity': complexity,
            'execution_frequency': frequency,
            'business_domain': domain,
            'confidence_score': confidence,
            'cloud_readiness_score': cloud_readiness,
            'components_involved': all_files
        }

    def _enrich_processes(self, processes: List[Dict]) -> List[Dict]:
        """Add priorities and AWS recommendations to processes."""

        enriched = []

        for proc in processes:
            business_value = proc.get('business_value', 'Medium')
            complexity = proc.get('complexity', 'Medium')
            frequency = proc.get('execution_frequency', 'Batch')

            # Determine priority (1=highest, 5=lowest)
            priority_map = {'High': 1, 'Medium': 2, 'Low': 3}
            base_priority = priority_map.get(business_value, 2)

            # Adjust for complexity (high complexity = lower priority for quick wins)
            if complexity == 'High' and business_value != 'High':
                base_priority += 1

            proc['modernization_priority'] = min(base_priority, 5)
            proc['criticality'] = business_value

            # Get AWS recommendation
            freq_key = 'Real-time' if frequency == 'Real-time' else 'Batch'
            rec_key = (business_value, freq_key)
            rec = AWS_RECOMMENDATIONS.get(rec_key, AWS_RECOMMENDATIONS[('Medium', 'Batch')])

            proc['recommended_approach'] = rec['approach']
            proc['aws_recommendations'] = rec['services']

            # Ensure required fields
            if 'components_involved' not in proc:
                proc['components_involved'] = [proc.get('source_file', 'unknown')]

            if 'cloud_readiness_score' not in proc:
                proc['cloud_readiness_score'] = 50

            enriched.append(proc)

        return enriched

    def _calculate_summary(self, processes: List[Dict]) -> Dict[str, Any]:
        """Calculate summary statistics."""
        total = len(processes)

        high_value = len([p for p in processes if p.get('business_value') == 'High'])
        medium_value = len([p for p in processes if p.get('business_value') == 'Medium'])
        low_value = len([p for p in processes if p.get('business_value') == 'Low'])

        real_time = len([p for p in processes if p.get('execution_frequency') == 'Real-time'])
        batch = total - real_time

        confidence_scores = [p.get('confidence_score', 0) for p in processes]
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0

        cloud_scores = [p.get('cloud_readiness_score', 0) for p in processes]
        avg_cloud = sum(cloud_scores) / len(cloud_scores) if cloud_scores else 0

        return {
            'total_processes': total,
            'high_value_processes': high_value,
            'medium_value_processes': medium_value,
            'low_value_processes': low_value,
            'real_time_processes': real_time,
            'batch_processes': batch,
            'average_confidence_score': round(avg_confidence, 1),
            'average_cloud_readiness': round(avg_cloud, 1)
        }

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result structure."""
        return {
            'business_processes': [],
            'summary': {
                'total_processes': 0,
                'high_value_processes': 0,
                'medium_value_processes': 0,
                'low_value_processes': 0,
                'real_time_processes': 0,
                'batch_processes': 0,
                'average_confidence_score': 0,
                'average_cloud_readiness': 0
            },
            'generated_at': datetime.now(timezone.utc).isoformat()
        }


def extract_business_processes(ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function to extract business processes."""
    extractor = BusinessProcessExtractor()
    return extractor.extract(ai_analysis)
