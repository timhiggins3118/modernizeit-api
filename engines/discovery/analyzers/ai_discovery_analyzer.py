"""
AI Discovery Analyzer - Business Context Discovery

Uses the unified BedrockAgent for AI-powered business context discovery.

Features:
- Business process identification
- Data flow analysis
- Modernization insights
- Parallel processing for performance
"""

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from engines.ai import BedrockAgent


class AIDiscoveryAnalyzer:
    """
    AI-powered discovery analysis.

    Uses BedrockAgent for all AI interactions.
    """

    def __init__(
        self,
        max_workers: int = 4,
        log_fn: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize AI Discovery analyzer.

        Args:
            max_workers: Maximum concurrent Bedrock calls (default 4)
            log_fn: Optional logging function (default: print)
        """
        self.max_workers = max_workers
        self.log_fn = log_fn or print
        self.agent = BedrockAgent.create(
            purpose="discovery",
            max_workers=max_workers,
            log_fn=log_fn
        )

    def analyze_directory(
        self,
        source_path: str,
        integration_results: Optional[Dict] = None,
        max_files: int = 50
    ) -> Dict[str, Any]:
        """
        Analyze COBOL files for business context.

        Uses parallel Bedrock calls for better performance.

        Args:
            source_path: Path to COBOL source directory
            integration_results: Pre-detected integrations (from IntegrationDetector)
            max_files: Maximum files to analyze (for cost control)

        Returns:
            AI discovery analysis with business processes, data flows, etc.
        """
        source_dir = Path(source_path)
        start_time = time.time()

        # Find COBOL files
        cobol_files = list(source_dir.rglob('*.cbl')) + list(source_dir.rglob('*.CBL'))
        cobol_files += list(source_dir.rglob('*.cob')) + list(source_dir.rglob('*.COB'))

        # Filter junk
        cobol_files = [
            f for f in cobol_files
            if '__MACOSX' not in str(f) and not f.name.startswith('.')
        ]

        # Limit for cost control
        cobol_files = cobol_files[:max_files]

        total_files = len(cobol_files)
        self.log_fn(f"[AI Discovery] Found {total_files} COBOL files to analyze")

        # Prepare file data
        file_data_list = []
        for file_path in cobol_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                relative_path = str(file_path.relative_to(source_dir))

                # Truncate large files
                if len(content) > 15000:
                    content = content[:15000] + "\n... [truncated]"

                file_data_list.append({
                    'content': content,
                    'relative_path': relative_path,
                    'file_path': file_path
                })
            except Exception as e:
                self.log_fn(f"[AI Discovery] Error reading {file_path}: {e}")

        # Process files in parallel using BedrockAgent
        results = self.agent.invoke_batch(
            items=file_data_list,
            prompt_fn=lambda fd: self._build_discovery_prompt(fd['relative_path'], fd['content']),
            item_id_fn=lambda fd: fd['relative_path'],
            parse_json=True,
            progress_prefix="[AI Discovery]"
        )

        # Collect results
        file_analyses = []
        all_business_processes = []
        all_data_flows = []

        for result in results:
            if result.success and result.result:
                analysis = result.result
                file_analyses.append({
                    'file_path': result.item_id,
                    'analysis': analysis,
                    'analyzed_at': datetime.now(timezone.utc).isoformat()
                })

                # Collect business processes
                if analysis.get('business_process'):
                    bp = analysis['business_process']
                    bp['source_file'] = result.item_id
                    all_business_processes.append(bp)

                # Collect data flows
                if analysis.get('data_flows'):
                    for df in analysis['data_flows']:
                        df['source_file'] = result.item_id
                        all_data_flows.append(df)

        duration_ms = int((time.time() - start_time) * 1000)
        success_count = sum(1 for r in results if r.success)

        return {
            'summary': {
                'total_files_analyzed': len(file_analyses),
                'total_business_processes': len(all_business_processes),
                'total_data_flows': len(all_data_flows),
                'success_count': success_count,
                'total_files': total_files,
                'duration_ms': duration_ms
            },
            'file_analyses': file_analyses,
            'business_processes': all_business_processes,
            'data_flows': all_data_flows,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }

    def _build_discovery_prompt(self, file_path: str, content: str) -> str:
        """Build structured JSON prompt for discovery analysis."""
        return f"""Analyze this COBOL program for modernization discovery.
Return ONLY valid JSON (no markdown, no explanation).

File: {file_path}

COBOL Code:
{content}

Return this exact JSON structure:
{{
    "business_process": {{
        "name": "string - concise business process name (e.g., 'Customer Account Validation')",
        "description": "string - what this program does in business terms",
        "business_value": "High|Medium|Low",
        "complexity": "High|Medium|Low",
        "execution_frequency": "Real-time|Batch|Daily|Weekly|Monthly",
        "business_domain": "string - domain like 'Financial Services', 'Customer Management', etc.",
        "confidence_score": 0-100
    }},
    "data_flows": [
        {{
            "flow_name": "string - descriptive name",
            "source": "string - input source (file, database, screen, etc.)",
            "source_type": "file|database|screen|message|api",
            "destination": "string - output destination",
            "destination_type": "file|database|screen|message|api",
            "transformation": "string - what transformation happens",
            "business_impact": "string - why this matters"
        }}
    ],
    "modernization_insights": {{
        "cloud_readiness_score": 0-100,
        "recommended_approach": "Rehost|Replatform|Refactor|Rearchitect|Replace",
        "key_challenges": ["string - challenge 1", "string - challenge 2"],
        "quick_wins": ["string - quick win 1", "string - quick win 2"]
    }}
}}

Important:
- Use actual content from the code, not generic descriptions
- Be specific about business function based on variable names, file names, procedures
- Return ONLY the JSON, no other text"""


def analyze_with_ai(
    source_path: str,
    integration_results: Optional[Dict] = None,
    max_files: int = 50
) -> Dict[str, Any]:
    """Convenience function for AI discovery analysis."""
    analyzer = AIDiscoveryAnalyzer()
    return analyzer.analyze_directory(source_path, integration_results, max_files)
