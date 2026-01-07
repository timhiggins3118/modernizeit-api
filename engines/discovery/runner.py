"""
Discovery Runner - Orchestrator

Coordinates all discovery components:
1. Integration Detection (code patterns)
2. AI Discovery Analysis (business context)
3. Business Process Extraction (consolidation)
4. API Pattern Analysis (architecture recommendations)
5. ROI Calculation (real industry formulas)
6. Roadmap Generation (phased migration plan)

DESIGN DECISION: Each component is independent and can be run separately.
The runner coordinates them for the full discovery flow.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .analyzers.integration_detector import IntegrationDetector
from .analyzers.ai_discovery_analyzer import AIDiscoveryAnalyzer
from .analyzers.business_process_extractor import BusinessProcessExtractor
from .analyzers.api_pattern_analyzer import APIPatternAnalyzer
from .generators.roi_calculator import ROICalculator, CodeMetrics, ProcessMetrics
from .generators.roadmap_generator import RoadmapGenerator
from .utils.roi_config import ROIConfig, DEFAULT_ROI_CONFIG
from db.repositories.discovery_repo import save_artifact_sync

logger = logging.getLogger(__name__)


class DiscoveryRunner:
    """
    Orchestrate complete discovery analysis.

    Runs all components in order, aggregating results into
    a comprehensive executive-ready report.
    """

    def __init__(
        self,
        roi_config: Optional[ROIConfig] = None,
        enable_ai: bool = True,
        max_files_for_ai: int = 50,
        account_id: Optional[str] = None,
        application: Optional[str] = None,
        save_to_mongodb: bool = True,
    ):
        """
        Initialize discovery runner.

        Args:
            roi_config: ROI calculation parameters (uses industry defaults if None)
            enable_ai: Enable AI-powered analysis (requires Bedrock)
            max_files_for_ai: Maximum files to send to AI (cost control)
            account_id: Customer account ID for MongoDB storage
            application: Application name for MongoDB storage
            save_to_mongodb: Whether to save artifacts to MongoDB
        """
        self.roi_config = roi_config or DEFAULT_ROI_CONFIG
        self.enable_ai = enable_ai
        self.max_files_for_ai = max_files_for_ai
        self.account_id = account_id
        self.application = application
        self.save_to_mongodb = save_to_mongodb

        # Initialize components
        self.integration_detector = IntegrationDetector()
        self.ai_analyzer = AIDiscoveryAnalyzer() if enable_ai else None
        self.process_extractor = BusinessProcessExtractor()
        self.api_analyzer = APIPatternAnalyzer()
        self.roi_calculator = ROICalculator(self.roi_config)
        self.roadmap_generator = RoadmapGenerator()

    def _save_to_mongo(self, artifact_type: str, data: dict, job_id: str):
        """Save artifact to MongoDB if enabled."""
        if not self.save_to_mongodb or not self.account_id or not self.application:
            return
        try:
            save_artifact_sync(
                account_id=self.account_id,
                application=self.application,
                program="_application",
                artifact_type=artifact_type,
                job_id=job_id,
                data=data
            )
            logger.info(f"[MongoDB] Saved {artifact_type}")
        except Exception as e:
            logger.warning(f"[MongoDB] Failed to save {artifact_type}: {e}")

    def run(
        self,
        source_path: str,
        code_analysis_results: Optional[Dict[str, Any]] = None,
        customer_inputs: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run complete discovery analysis.

        Args:
            source_path: Path to COBOL source directory
            code_analysis_results: Optional pre-existing code analysis (LOC, etc.)
            customer_inputs: Optional customer-specific data (overrides defaults)
            output_dir: Optional directory to save results

        Returns:
            Complete discovery results with all sections
        """
        logger.info(f"Starting discovery analysis for: {source_path}")
        start_time = datetime.now(timezone.utc)

        results = {
            'status': 'in_progress',
            'source_path': source_path,
            'started_at': start_time.isoformat()
        }

        try:
            # Step 1: Detect integrations from code patterns
            logger.info("Step 1: Detecting integrations...")
            integration_points = self.integration_detector.detect_from_directory(source_path)
            results['integration_points'] = integration_points
            logger.info(f"Found {len(integration_points.get('integration_points', []))} integration types")

            # Step 2: AI analysis (if enabled)
            if self.enable_ai and self.ai_analyzer:
                logger.info("Step 2: Running AI discovery analysis...")
                ai_analysis = self.ai_analyzer.analyze_directory(
                    source_path,
                    integration_points,
                    self.max_files_for_ai
                )
                results['ai_analysis'] = ai_analysis
                logger.info(f"AI analyzed {ai_analysis.get('summary', {}).get('total_files_analyzed', 0)} files")
            else:
                logger.info("Step 2: AI analysis disabled, using fallback")
                ai_analysis = self._get_fallback_ai_analysis(source_path)
                results['ai_analysis'] = ai_analysis

            # Step 3: Extract and consolidate business processes
            logger.info("Step 3: Extracting business processes...")
            business_processes = self.process_extractor.extract(ai_analysis)
            results['business_processes'] = business_processes
            logger.info(f"Extracted {len(business_processes.get('business_processes', []))} processes")

            # Step 4: Analyze API patterns
            logger.info("Step 4: Analyzing API patterns...")
            api_patterns = self.api_analyzer.analyze(
                business_processes,
                integration_points,
                ai_analysis
            )
            results['api_patterns'] = api_patterns
            logger.info(f"Primary pattern: {api_patterns.get('primary_api_pattern', 'unknown')}")

            # Step 5: Calculate ROI
            logger.info("Step 5: Calculating ROI...")
            code_metrics = self._get_code_metrics(source_path, code_analysis_results)
            process_metrics = self._get_process_metrics(business_processes)

            roi_analysis = self.roi_calculator.calculate(
                code_metrics,
                process_metrics,
                integration_points,
                customer_inputs
            )
            results['roi_analysis'] = roi_analysis
            logger.info(f"5-year ROI: {roi_analysis.get('headline_metrics', {}).get('five_year_roi_percent', 0):.0f}%")

            # Step 6: Generate roadmap
            logger.info("Step 6: Generating roadmap...")
            roadmap = self.roadmap_generator.generate(
                business_processes,
                integration_points,
                api_patterns,
                roi_analysis,
                customer_inputs
            )
            results['migration_roadmap'] = roadmap
            logger.info(f"Roadmap: {roadmap.get('timeline', {}).get('total_months', 0)} months")

            # Finalize
            end_time = datetime.now(timezone.utc)
            results['status'] = 'completed'
            results['completed_at'] = end_time.isoformat()
            results['duration_seconds'] = (end_time - start_time).total_seconds()

            # Create executive summary
            results['executive_summary'] = self._create_executive_summary(results)

            # Save if output directory specified
            if output_dir:
                self._save_results(results, output_dir)

            logger.info(f"Discovery completed in {results['duration_seconds']:.1f}s")
            return results

        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
            results['completed_at'] = datetime.now(timezone.utc).isoformat()
            return results

    def _get_code_metrics(
        self,
        source_path: str,
        code_analysis_results: Optional[Dict]
    ) -> CodeMetrics:
        """Get code metrics from analysis or estimate from files."""
        if code_analysis_results:
            summary = code_analysis_results.get('summary', {})
            return CodeMetrics(
                total_loc=summary.get('total_loc', 0),
                total_files=summary.get('total_files', 0),
                high_complexity_files=summary.get('high_complexity', 0),
                medium_complexity_files=summary.get('medium_complexity', 0),
                low_complexity_files=summary.get('low_complexity', 0)
            )

        # Estimate from file scan
        source_dir = Path(source_path)
        cobol_files = list(source_dir.rglob('*.cbl')) + list(source_dir.rglob('*.CBL'))
        cobol_files += list(source_dir.rglob('*.cob')) + list(source_dir.rglob('*.COB'))

        # Filter junk
        cobol_files = [
            f for f in cobol_files
            if '__MACOSX' not in str(f) and not f.name.startswith('.')
        ]

        total_loc = 0
        for f in cobol_files:
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                total_loc += len(content.split('\n'))
            except Exception:
                pass

        # Estimate complexity distribution
        file_count = len(cobol_files)

        return CodeMetrics(
            total_loc=total_loc,
            total_files=file_count,
            high_complexity_files=int(file_count * 0.2),
            medium_complexity_files=int(file_count * 0.5),
            low_complexity_files=int(file_count * 0.3)
        )

    def _get_process_metrics(self, business_processes: Dict) -> ProcessMetrics:
        """Extract process metrics from business process analysis."""
        summary = business_processes.get('summary', {})

        return ProcessMetrics(
            high_value_processes=summary.get('high_value_processes', 0),
            medium_value_processes=summary.get('medium_value_processes', 0),
            low_value_processes=summary.get('low_value_processes', 0),
            total_processes=summary.get('total_processes', 0)
        )

    def _get_fallback_ai_analysis(self, source_path: str) -> Dict[str, Any]:
        """Generate fallback analysis when AI is disabled."""
        source_dir = Path(source_path)
        cobol_files = list(source_dir.rglob('*.cbl')) + list(source_dir.rglob('*.CBL'))
        cobol_files += list(source_dir.rglob('*.cob')) + list(source_dir.rglob('*.COB'))

        # Filter junk
        cobol_files = [
            f for f in cobol_files
            if '__MACOSX' not in str(f) and not f.name.startswith('.')
        ]

        # Create basic process for each file
        processes = []
        for f in cobol_files[:50]:  # Limit
            processes.append({
                'name': f.stem.upper(),
                'description': f'Business logic in {f.name}',
                'business_value': 'Medium',
                'complexity': 'Medium',
                'execution_frequency': 'Batch',
                'business_domain': 'General Business Logic',
                'confidence_score': 30,
                'source_file': str(f.relative_to(source_dir))
            })

        return {
            'summary': {
                'total_files_analyzed': len(processes),
                'total_business_processes': len(processes),
                'total_data_flows': 0,
                'note': 'AI analysis disabled - using fallback'
            },
            'business_processes': processes,
            'data_flows': [],
            'file_analyses': []
        }

    def _create_executive_summary(self, results: Dict) -> Dict[str, Any]:
        """Create top-level executive summary."""
        roi = results.get('roi_analysis', {}).get('headline_metrics', {})
        roadmap = results.get('migration_roadmap', {})
        integrations = results.get('integration_points', {})
        processes = results.get('business_processes', {})

        return {
            'modernization_opportunity': {
                'total_investment': f"${roi.get('total_investment', 0):,}",
                'five_year_savings': f"${roi.get('five_year_savings', 0):,}",
                'roi_percent': f"{roi.get('five_year_roi_percent', 0):.0f}%",
                'payback_period': f"{roi.get('payback_months', 0)} months"
            },
            'scope': {
                'business_processes': processes.get('summary', {}).get('total_processes', 0),
                'integration_points': integrations.get('summary', {}).get('total_integration_points', 0),
                'high_value_processes': processes.get('summary', {}).get('high_value_processes', 0)
            },
            'timeline': {
                'total_duration': roadmap.get('timeline', {}).get('total_months', 0),
                'phases': len(roadmap.get('phases', []))
            },
            'key_recommendations': [
                f"Primary architecture: {results.get('api_patterns', {}).get('aws_architecture_recommendation', {}).get('architecture_pattern', 'Serverless')}",
                f"Start with {processes.get('summary', {}).get('low_value_processes', 0)} low-risk quick wins",
                f"Address {integrations.get('summary', {}).get('high_complexity_count', 0)} high-complexity integrations in Phase 4"
            ],
            'next_steps': [
                'Review ROI assumptions with finance',
                'Validate business process priorities with stakeholders',
                'Plan Phase 1 infrastructure setup'
            ]
        }

    def _save_results(self, results: Dict, output_dir: str):
        """Save results to output directory and MongoDB."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate a job_id for MongoDB
        job_id = f"disc_job_{int(datetime.now(timezone.utc).timestamp())}"

        # Save each section
        sections = [
            ('discovery_summary.json', 'discovery_summary', {
                'status': results.get('status'),
                'executive_summary': results.get('executive_summary'),
                'started_at': results.get('started_at'),
                'completed_at': results.get('completed_at'),
                'duration_seconds': results.get('duration_seconds')
            }),
            ('integration_points.json', 'integration_points', results.get('integration_points', {})),
            ('business_processes.json', 'business_processes', results.get('business_processes', {})),
            ('api_patterns.json', 'api_patterns', results.get('api_patterns', {})),
            ('roi_analysis.json', 'roi_analysis', results.get('roi_analysis', {})),
            ('migration_roadmap.json', 'migration_roadmap', results.get('migration_roadmap', {}))
        ]

        for filename, artifact_type, data in sections:
            filepath = output_path / filename
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            # Save to MongoDB
            self._save_to_mongo(artifact_type, data, job_id)

        logger.info(f"Results saved to: {output_path}")


def run_discovery(
    source_path: str,
    code_analysis_results: Optional[Dict[str, Any]] = None,
    customer_inputs: Optional[Dict[str, Any]] = None,
    output_dir: Optional[str] = None,
    enable_ai: bool = True,
    account_id: Optional[str] = None,
    application: Optional[str] = None,
    save_to_mongodb: bool = True,
) -> Dict[str, Any]:
    """
    Convenience function to run complete discovery.

    Args:
        source_path: Path to COBOL source directory
        code_analysis_results: Optional pre-existing code analysis
        customer_inputs: Optional customer-specific ROI data
        output_dir: Optional directory to save results
        enable_ai: Enable AI-powered analysis
        account_id: Customer account ID for MongoDB storage
        application: Application name for MongoDB storage
        save_to_mongodb: Whether to save artifacts to MongoDB

    Returns:
        Complete discovery results
    """
    runner = DiscoveryRunner(
        enable_ai=enable_ai,
        account_id=account_id,
        application=application,
        save_to_mongodb=save_to_mongodb,
    )
    return runner.run(
        source_path,
        code_analysis_results,
        customer_inputs,
        output_dir
    )
