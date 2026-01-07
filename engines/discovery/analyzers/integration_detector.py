"""
Integration Detector - Code Pattern Based

Detects mainframe integrations (CICS, DB2, MQ, VSAM, IMS) using
actual COBOL code patterns - NOT fragile AI response parsing.

DESIGN DECISION: Use regex on actual COBOL code for reliable detection.
AI is used only for business context enrichment, not detection.
"""

import re
import hashlib
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# =============================================================================
# Integration Pattern Definitions
# =============================================================================

INTEGRATION_PATTERNS = {
    'CICS': {
        'type': 'Transaction Manager',
        'patterns': [
            r'EXEC\s+CICS',
            r'DFHCOMMAREA',
            r'EIBCALEN',
            r'EIBTRNID',
            r'DFHRESP',
            r'CICS\s+SEND',
            r'CICS\s+RECEIVE',
            r'CICS\s+START',
            r'CICS\s+RETURN',
            r'CICS\s+XCTL',
            r'CICS\s+LINK',
            r'HANDLE\s+CONDITION',
        ],
        'description': 'IBM CICS transaction processing',
        'access_pattern': 'Online transaction processing (OLTP)',
        'aws_recommendation': {
            'aws_service': 'AWS Lambda + API Gateway or Amazon ECS',
            'migration_approach': 'Refactor to microservices with REST/GraphQL APIs',
            'estimated_effort_weeks': 8,
            'complexity': 'High',
            'rationale': 'CICS transactions map well to Lambda functions or containerized services'
        }
    },
    'DB2': {
        'type': 'Database',
        'patterns': [
            r'EXEC\s+SQL',
            r'SQLCODE',
            r'SQLSTATE',
            r'SQLCA',
            r'INCLUDE\s+SQLCA',
            r'DECLARE\s+\w+\s+CURSOR',
            r'FETCH\s+\w+\s+INTO',
            r'INSERT\s+INTO',
            r'UPDATE\s+\w+\s+SET',
            r'DELETE\s+FROM',
            r'SELECT\s+.+\s+FROM',
        ],
        'description': 'IBM DB2 relational database',
        'access_pattern': 'SQL database operations',
        'aws_recommendation': {
            'aws_service': 'Amazon RDS (PostgreSQL) or Amazon Aurora',
            'migration_approach': 'Schema migration with AWS DMS, application refactoring',
            'estimated_effort_weeks': 12,
            'complexity': 'High',
            'rationale': 'DB2 SQL is largely compatible with PostgreSQL/Aurora'
        }
    },
    'IMS_DB': {
        'type': 'Database',
        'patterns': [
            r'DL/I',
            r'DLI\s+CALL',
            r'GU\s+PCB',
            r'GN\s+PCB',
            r'GNP\s+PCB',
            r'GHU\s+PCB',
            r'GHN\s+PCB',
            r'ISRT\s+PCB',
            r'REPL\s+PCB',
            r'DLET\s+PCB',
            r'PCB\s+MASK',
            r'SSA\s+AREA',
        ],
        'description': 'IBM IMS hierarchical database',
        'access_pattern': 'Hierarchical database navigation',
        'aws_recommendation': {
            'aws_service': 'Amazon DocumentDB or Amazon DynamoDB',
            'migration_approach': 'Data model transformation to document/key-value, staged migration',
            'estimated_effort_weeks': 16,
            'complexity': 'High',
            'rationale': 'IMS hierarchical model maps to document databases'
        }
    },
    'IMS_TM': {
        'type': 'Transaction Manager',
        'patterns': [
            r'IMS\s+DC',
            r'MFS\s+FORMAT',
            r'MPP\s+REGION',
            r'BMP\s+REGION',
            r'IFP\s+REGION',
            r'CBLTDLI',
        ],
        'description': 'IBM IMS Transaction Manager',
        'access_pattern': 'IMS message processing',
        'aws_recommendation': {
            'aws_service': 'Amazon SQS + Lambda or Step Functions',
            'migration_approach': 'Message-driven architecture with event processing',
            'estimated_effort_weeks': 10,
            'complexity': 'High',
            'rationale': 'IMS TM patterns map to event-driven architectures'
        }
    },
    'MQ': {
        'type': 'Messaging',
        'patterns': [
            r'MQOPEN',
            r'MQCLOSE',
            r'MQPUT',
            r'MQPUT1',
            r'MQGET',
            r'MQINQ',
            r'MQSET',
            r'MQCONN',
            r'MQDISC',
            r'MQ\s+SERIES',
            r'CALL\s+\'MQOPEN\'',
            r'CALL\s+\'MQPUT\'',
            r'CALL\s+\'MQGET\'',
        ],
        'description': 'IBM MQ (WebSphere MQ / MQSeries) messaging',
        'access_pattern': 'Asynchronous message queuing',
        'aws_recommendation': {
            'aws_service': 'Amazon SQS or Amazon MQ',
            'migration_approach': 'Direct migration to SQS (simpler) or Amazon MQ (if JMS compatibility needed)',
            'estimated_effort_weeks': 4,
            'complexity': 'Low',
            'rationale': 'MQ patterns directly supported by Amazon SQS/MQ'
        }
    },
    'VSAM': {
        'type': 'File System',
        'patterns': [
            r'ORGANIZATION\s+IS\s+INDEXED',
            r'ORGANIZATION\s+IS\s+RELATIVE',
            r'ORGANIZATION\s+IS\s+SEQUENTIAL',
            r'RECORD\s+KEY\s+IS',
            r'ALTERNATE\s+RECORD\s+KEY',
            r'FILE\s+STATUS',
            r'VSAM',
            r'KSDS',
            r'RRDS',
            r'ESDS',
            r'ACCESS\s+MODE\s+IS\s+DYNAMIC',
            r'ACCESS\s+MODE\s+IS\s+RANDOM',
        ],
        'description': 'IBM VSAM (Virtual Storage Access Method) files',
        'access_pattern': 'Indexed/keyed file access',
        'aws_recommendation': {
            'aws_service': 'Amazon DynamoDB or Amazon RDS',
            'migration_approach': 'KSDS → DynamoDB (key-value), complex → RDS',
            'estimated_effort_weeks': 6,
            'complexity': 'Medium',
            'rationale': 'VSAM KSDS maps naturally to DynamoDB key-value model'
        }
    },
    'QSAM': {
        'type': 'File System',
        'patterns': [
            r'ORGANIZATION\s+IS\s+SEQUENTIAL',
            r'ACCESS\s+MODE\s+IS\s+SEQUENTIAL',
            r'QSAM',
            r'READ\s+\w+\s+INTO',
            r'WRITE\s+\w+\s+FROM',
            r'OPEN\s+INPUT',
            r'OPEN\s+OUTPUT',
            r'OPEN\s+I-O',
        ],
        'description': 'Sequential file processing (QSAM)',
        'access_pattern': 'Sequential file read/write',
        'aws_recommendation': {
            'aws_service': 'Amazon S3 + AWS Lambda',
            'migration_approach': 'Files to S3, processing via Lambda or Step Functions',
            'estimated_effort_weeks': 3,
            'complexity': 'Low',
            'rationale': 'Sequential files map directly to S3 objects'
        }
    },
    'JCL_BATCH': {
        'type': 'Batch Processing',
        'patterns': [
            r'//\w+\s+JOB',
            r'//\w+\s+EXEC\s+PGM',
            r'//\w+\s+DD\s+',
            r'SORT\s+FIELDS',
            r'MERGE\s+FIELDS',
            r'DFSORT',
            r'SYNCSORT',
        ],
        'description': 'JCL batch job processing',
        'access_pattern': 'Scheduled batch execution',
        'aws_recommendation': {
            'aws_service': 'AWS Step Functions + Lambda or AWS Batch',
            'migration_approach': 'Orchestrate batch workflows with Step Functions',
            'estimated_effort_weeks': 6,
            'complexity': 'Medium',
            'rationale': 'JCL job streams map to Step Functions state machines'
        }
    },
    'COBOL_CALL': {
        'type': 'Program Calls',
        'patterns': [
            r'CALL\s+[\'\"]\w+[\'\"]',
            r'CALL\s+IDENTIFIER',
            r'GOBACK',
            r'STOP\s+RUN',
        ],
        'description': 'COBOL program-to-program calls',
        'access_pattern': 'Subroutine/subprogram invocation',
        'aws_recommendation': {
            'aws_service': 'Lambda Layers or internal service calls',
            'migration_approach': 'Shared code as Lambda Layers, larger components as microservices',
            'estimated_effort_weeks': 2,
            'complexity': 'Low',
            'rationale': 'CALL statements become function calls or service invocations'
        }
    }
}


class IntegrationDetector:
    """
    Detect mainframe integrations from COBOL source code.

    Uses regex pattern matching on actual code - reliable and deterministic.
    AI enrichment is optional and only adds business context.
    """

    def __init__(self):
        self.patterns = INTEGRATION_PATTERNS
        # Compile regex patterns for performance
        self._compiled_patterns = {}
        for system, config in self.patterns.items():
            self._compiled_patterns[system] = [
                re.compile(p, re.IGNORECASE | re.MULTILINE)
                for p in config['patterns']
            ]

    def detect_from_directory(self, source_path: str) -> Dict[str, Any]:
        """
        Detect integrations from all COBOL files in directory.

        Returns aggregated integration points with program mappings.
        """
        source_dir = Path(source_path)

        # Find all COBOL files
        cobol_files = list(source_dir.rglob('*.cbl')) + list(source_dir.rglob('*.CBL'))
        cobol_files += list(source_dir.rglob('*.cob')) + list(source_dir.rglob('*.COB'))

        # Track integrations across all files
        all_detections: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'programs': [],
            'evidence': [],
            'match_count': 0
        })

        total_files = 0

        for file_path in cobol_files:
            # Skip junk files
            path_str = str(file_path)
            if '__MACOSX' in path_str or file_path.name.startswith('.'):
                continue

            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                relative_path = str(file_path.relative_to(source_dir))

                # Detect integrations in this file
                file_detections = self._detect_in_content(content)

                for system, detection in file_detections.items():
                    all_detections[system]['programs'].append(relative_path)
                    all_detections[system]['evidence'].extend(detection['evidence'][:3])  # Top 3
                    all_detections[system]['match_count'] += detection['match_count']

                total_files += 1

            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue

        # Build output
        integration_points = []
        integration_id_counter = 1

        for system, detection in all_detections.items():
            if detection['match_count'] > 0:
                config = self.patterns[system]

                integration_points.append({
                    'integration_id': f"int_{integration_id_counter:03d}",
                    'integration_type': config['type'],
                    'system_name': system.replace('_', ' '),
                    'description': config['description'],
                    'access_pattern': config['access_pattern'],
                    'detected_evidence': list(set(detection['evidence']))[:5],
                    'programs_using': sorted(list(set(detection['programs']))),
                    'match_count': detection['match_count'],
                    'modernization_recommendation': config['aws_recommendation']
                })

                integration_id_counter += 1

        # Sort by match count (most common first)
        integration_points.sort(key=lambda x: x['match_count'], reverse=True)

        # Calculate summary
        summary = self._calculate_summary(integration_points)

        return {
            'integration_points': integration_points,
            'summary': summary,
            'total_files_analyzed': total_files,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    def _detect_in_content(self, content: str) -> Dict[str, Dict[str, Any]]:
        """Detect integrations in a single file's content."""
        detections = {}

        for system, patterns in self._compiled_patterns.items():
            matches = []
            evidence = []

            for pattern in patterns:
                found = pattern.findall(content)
                if found:
                    matches.extend(found)
                    # Get context around matches
                    for match in pattern.finditer(content):
                        start = max(0, match.start() - 20)
                        end = min(len(content), match.end() + 20)
                        context = content[start:end].strip()
                        # Clean up context
                        context = ' '.join(context.split())[:80]
                        evidence.append(context)

            if matches:
                detections[system] = {
                    'match_count': len(matches),
                    'evidence': evidence[:5]  # Top 5 examples
                }

        return detections

    def _calculate_summary(self, integration_points: List[Dict]) -> Dict[str, Any]:
        """Calculate summary statistics."""
        total = len(integration_points)

        by_type = defaultdict(int)
        complexity_counts = {'High': 0, 'Medium': 0, 'Low': 0}

        for ip in integration_points:
            by_type[ip['integration_type']] += 1
            complexity = ip['modernization_recommendation']['complexity']
            complexity_counts[complexity] += 1

        return {
            'total_integration_points': total,
            'by_type': dict(by_type),
            'high_complexity_count': complexity_counts['High'],
            'medium_complexity_count': complexity_counts['Medium'],
            'low_complexity_count': complexity_counts['Low']
        }


def detect_integrations(source_path: str) -> Dict[str, Any]:
    """Convenience function to detect integrations."""
    detector = IntegrationDetector()
    return detector.detect_from_directory(source_path)
