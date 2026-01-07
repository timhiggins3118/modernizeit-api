"""
Source Consolidator for Architecture Recommender

Loads and consolidates data from all 5 input sources:
1. Discovery - Business processes, ROI, integration points
2. Data Analysis - ERD, relationships, data lineage
3. Code Analysis - COBOL complexity, static analysis
4. Code Refactor - Modernization patterns, recipes
5. Java Code - Generated Java from Code Analysis

Each source provides different evidence for architecture decisions.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from api.models.architecture import JavaAnalysis
from engines.architecture.analyzers.java_analyzer import analyze_java_code


@dataclass
class DiscoveryData:
    """Data from Discovery flow."""
    has_data: bool = False
    integration_points: List[Dict[str, Any]] = field(default_factory=list)
    business_processes: List[Dict[str, Any]] = field(default_factory=list)
    api_patterns: Dict[str, Any] = field(default_factory=dict)
    roi_analysis: Dict[str, Any] = field(default_factory=dict)
    executive_summary: Dict[str, Any] = field(default_factory=dict)

    # Extracted facts for recommendations
    has_cics: bool = False
    has_db2: bool = False
    has_mq: bool = False
    has_vsam: bool = False
    primary_pattern: str = "unknown"  # real_time, batch, hybrid
    high_value_processes: int = 0
    batch_processes: int = 0
    real_time_processes: int = 0


@dataclass
class DataAnalysisData:
    """Data from Data Analysis flow."""
    has_data: bool = False
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    copybooks: List[Dict[str, Any]] = field(default_factory=list)
    data_lineage: Dict[str, Any] = field(default_factory=dict)

    # Extracted facts
    entity_count: int = 0
    relationship_count: int = 0
    has_complex_relationships: bool = False


@dataclass
class CodeAnalysisData:
    """Data from Code Analysis flow."""
    has_data: bool = False
    static_analysis: Dict[str, Any] = field(default_factory=dict)
    complexity_report: Dict[str, Any] = field(default_factory=dict)
    file_inventory: List[Dict[str, Any]] = field(default_factory=list)

    # Extracted facts
    total_loc: int = 0
    total_files: int = 0
    high_complexity_files: int = 0
    medium_complexity_files: int = 0
    low_complexity_files: int = 0
    average_complexity: float = 0.0


@dataclass
class CodeRefactorData:
    """Data from Code Refactor flow."""
    has_data: bool = False
    recipes: List[Dict[str, Any]] = field(default_factory=list)
    refactor_report: Dict[str, Any] = field(default_factory=dict)
    modernization_score: float = 0.0

    # Extracted facts
    total_recipes: int = 0
    applied_recipes: int = 0
    pending_recipes: int = 0


@dataclass
class ConsolidatedSources:
    """All 5 sources consolidated."""
    discovery: DiscoveryData = field(default_factory=DiscoveryData)
    data_analysis: DataAnalysisData = field(default_factory=DataAnalysisData)
    code_analysis: CodeAnalysisData = field(default_factory=CodeAnalysisData)
    code_refactor: CodeRefactorData = field(default_factory=CodeRefactorData)
    java_analysis: Optional[JavaAnalysis] = None

    sources_loaded: List[str] = field(default_factory=list)
    load_errors: Dict[str, str] = field(default_factory=dict)


class SourceConsolidator:
    """Consolidates data from all input sources."""

    def __init__(
        self,
        base_path: str,
        scout_account_id: str,
        application_name: str,
        java_source_path: Optional[str] = None
    ):
        """
        Initialize consolidator.

        Args:
            base_path: Base path for all flow outputs
            scout_account_id: Customer account ID
            application_name: Application name
            java_source_path: Optional explicit path to Java source
        """
        self.base_path = Path(base_path)
        self.account = scout_account_id
        self.app = application_name
        self.java_source_path = java_source_path

        # Standard output paths
        self.flow_base = self.base_path / "code-transformation-v2" / self.account / self.app

    def consolidate(self) -> ConsolidatedSources:
        """
        Load and consolidate all sources.

        Returns:
            ConsolidatedSources with all available data
        """
        result = ConsolidatedSources()

        # Load each source
        result.discovery = self._load_discovery()
        if result.discovery.has_data:
            result.sources_loaded.append("discovery")

        result.data_analysis = self._load_data_analysis()
        if result.data_analysis.has_data:
            result.sources_loaded.append("data_analysis")

        result.code_analysis = self._load_code_analysis()
        if result.code_analysis.has_data:
            result.sources_loaded.append("code_analysis")

        result.code_refactor = self._load_code_refactor()
        if result.code_refactor.has_data:
            result.sources_loaded.append("code_refactor")

        result.java_analysis = self._load_java_analysis()
        if result.java_analysis and result.java_analysis.files_analyzed > 0:
            result.sources_loaded.append("java")

        return result

    def _load_discovery(self) -> DiscoveryData:
        """Load Discovery flow outputs."""
        data = DiscoveryData()
        discovery_path = self.flow_base / "discovery"

        if not discovery_path.exists():
            return data

        try:
            # Load integration points
            ip_file = discovery_path / "integration_points.json"
            if ip_file.exists():
                ip_data = json.loads(ip_file.read_text())
                data.integration_points = ip_data.get('integration_points', [])

                # Extract integration types
                for ip in data.integration_points:
                    system = ip.get('system_name', '').upper()
                    if 'CICS' in system:
                        data.has_cics = True
                    if 'DB2' in system:
                        data.has_db2 = True
                    if 'MQ' in system:
                        data.has_mq = True
                    if 'VSAM' in system:
                        data.has_vsam = True

            # Load business processes
            bp_file = discovery_path / "business_processes.json"
            if bp_file.exists():
                bp_data = json.loads(bp_file.read_text())
                data.business_processes = bp_data.get('business_processes', [])

                # Count by value
                for bp in data.business_processes:
                    value = bp.get('business_value', '').lower()
                    freq = bp.get('execution_frequency', '').lower()

                    if value == 'high':
                        data.high_value_processes += 1
                    if 'batch' in freq:
                        data.batch_processes += 1
                    elif 'real' in freq or 'online' in freq:
                        data.real_time_processes += 1

            # Load API patterns
            ap_file = discovery_path / "api_patterns.json"
            if ap_file.exists():
                data.api_patterns = json.loads(ap_file.read_text())
                data.primary_pattern = data.api_patterns.get('primary_api_pattern', 'unknown')

            # Load ROI
            roi_file = discovery_path / "roi_analysis.json"
            if roi_file.exists():
                data.roi_analysis = json.loads(roi_file.read_text())

            # Load summary
            summary_file = discovery_path / "discovery_summary.json"
            if summary_file.exists():
                data.executive_summary = json.loads(summary_file.read_text())

            data.has_data = True

        except Exception as e:
            data.has_data = False

        return data

    def _load_data_analysis(self) -> DataAnalysisData:
        """Load Data Analysis flow outputs."""
        data = DataAnalysisData()
        da_path = self.flow_base / "data_analysis"

        if not da_path.exists():
            return data

        try:
            # Load ERD
            erd_file = da_path / "erd.json"
            if erd_file.exists():
                erd_data = json.loads(erd_file.read_text())
                data.entities = erd_data.get('entities', [])
                data.relationships = erd_data.get('relationships', [])
                data.entity_count = len(data.entities)
                data.relationship_count = len(data.relationships)

                # Check for complex relationships (many-to-many, etc.)
                for rel in data.relationships:
                    if rel.get('type') == 'many-to-many':
                        data.has_complex_relationships = True
                        break

            # Load copybooks
            cb_file = da_path / "copybooks.json"
            if cb_file.exists():
                cb_data = json.loads(cb_file.read_text())
                data.copybooks = cb_data.get('copybooks', [])

            # Load data lineage
            lineage_file = da_path / "data_lineage.json"
            if lineage_file.exists():
                data.data_lineage = json.loads(lineage_file.read_text())

            data.has_data = True

        except Exception as e:
            data.has_data = False

        return data

    def _load_code_analysis(self) -> CodeAnalysisData:
        """Load Code Analysis flow outputs."""
        data = CodeAnalysisData()

        # Try multiple possible paths
        possible_paths = [
            self.flow_base / "code_analysis",
            self.flow_base / "code_analysis_v3",
        ]

        ca_path = None
        for p in possible_paths:
            if p.exists():
                ca_path = p
                break

        if not ca_path:
            return data

        try:
            # Find most recent job
            jobs_path = ca_path / "jobs"
            if jobs_path.exists():
                jobs = sorted(jobs_path.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
                if jobs:
                    job_path = jobs[0]

                    # Load static analysis
                    static_file = job_path / "static_analysis.json"
                    if static_file.exists():
                        data.static_analysis = json.loads(static_file.read_text())

                    # Load complexity report
                    complexity_file = job_path / "complexity_report.json"
                    if complexity_file.exists():
                        data.complexity_report = json.loads(complexity_file.read_text())

                        # Extract complexity facts
                        summary = data.complexity_report.get('summary', {})
                        data.total_files = summary.get('total_files', 0)
                        data.total_loc = summary.get('total_loc', 0)
                        data.high_complexity_files = summary.get('high_complexity', 0)
                        data.medium_complexity_files = summary.get('medium_complexity', 0)
                        data.low_complexity_files = summary.get('low_complexity', 0)
                        data.average_complexity = summary.get('average_complexity', 0.0)

                    # Load file inventory
                    inventory_file = job_path / "file_inventory.json"
                    if inventory_file.exists():
                        inv_data = json.loads(inventory_file.read_text())
                        data.file_inventory = inv_data.get('files', [])

                    data.has_data = True

        except Exception as e:
            data.has_data = False

        return data

    def _load_code_refactor(self) -> CodeRefactorData:
        """Load Code Refactor flow outputs."""
        data = CodeRefactorData()
        cr_path = self.flow_base / "code_refactor"

        if not cr_path.exists():
            return data

        try:
            # Find most recent job
            jobs_path = cr_path / "jobs"
            if jobs_path.exists():
                jobs = sorted(jobs_path.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
                if jobs:
                    job_path = jobs[0]

                    # Load recipes
                    recipes_file = job_path / "refactor_recipes.json"
                    if recipes_file.exists():
                        recipes_data = json.loads(recipes_file.read_text())
                        data.recipes = recipes_data.get('recipes', [])
                        data.total_recipes = len(data.recipes)

                        # Count by status
                        for recipe in data.recipes:
                            if recipe.get('applied', False):
                                data.applied_recipes += 1
                            else:
                                data.pending_recipes += 1

                    # Load refactor report
                    report_file = job_path / "refactor_report.json"
                    if report_file.exists():
                        data.refactor_report = json.loads(report_file.read_text())
                        data.modernization_score = data.refactor_report.get('modernization_score', 0.0)

                    data.has_data = True

        except Exception as e:
            data.has_data = False

        return data

    def _load_java_analysis(self) -> Optional[JavaAnalysis]:
        """Load and analyze Java source code."""
        # Try explicit path first
        if self.java_source_path:
            java_path = Path(self.java_source_path)
            if java_path.exists():
                return analyze_java_code(str(java_path))

        # Try standard locations
        possible_paths = [
            self.flow_base / "code_analysis" / "generated",
            self.flow_base / "code_analysis_v3" / "generated",
            self.flow_base / "generated",
        ]

        # Also check jobs directories
        for base in [self.flow_base / "code_analysis", self.flow_base / "code_analysis_v3"]:
            jobs_path = base / "jobs"
            if jobs_path.exists():
                jobs = sorted(jobs_path.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
                if jobs:
                    possible_paths.append(jobs[0] / "generated")

        for path in possible_paths:
            if path.exists():
                analysis = analyze_java_code(str(path))
                if analysis.files_analyzed > 0:
                    return analysis

        return None


def consolidate_sources(
    base_path: str,
    scout_account_id: str,
    application_name: str,
    java_source_path: Optional[str] = None
) -> ConsolidatedSources:
    """
    Convenience function to consolidate all sources.

    Args:
        base_path: Base path for outputs
        scout_account_id: Account ID
        application_name: Application name
        java_source_path: Optional Java source path

    Returns:
        ConsolidatedSources
    """
    consolidator = SourceConsolidator(
        base_path=base_path,
        scout_account_id=scout_account_id,
        application_name=application_name,
        java_source_path=java_source_path
    )
    return consolidator.consolidate()
