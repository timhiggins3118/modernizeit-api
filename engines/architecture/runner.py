"""
Architecture Recommender Runner

Main orchestrator for the Architecture Recommender flow.
Coordinates all analyzers, recommenders, and generators.

Flow:
1. Load sources (5 total)
2. Analyze Java code
3. Cross-validate sources
4. Generate recommendations (compute, database, API)
5. Estimate costs
6. Generate IaC templates
7. Build traceability
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from api.models.architecture import (
    ArchitectureSummary,
    StorageRecommendation,
    SecurityRecommendation,
    Traceability,
    ServiceMapping,
    MigrationPhase,
    S3Bucket,
    Evidence,
)
from engines.architecture.analyzers.source_consolidator import (
    SourceConsolidator,
    ConsolidatedSources,
)
from engines.architecture.analyzers.cross_validator import CrossValidator
from engines.architecture.recommenders.compute_recommender import ComputeRecommender
from engines.architecture.recommenders.database_recommender import DatabaseRecommender
from engines.architecture.recommenders.api_recommender import APIRecommender
from engines.architecture.recommenders.cost_estimator import CostEstimator
from engines.architecture.generators.iac_generator import IaCGenerator
from db.repositories.architecture_repo import save_artifact_sync


class ArchitectureRunner:
    """Main orchestrator for Architecture Recommender."""

    def __init__(
        self,
        base_path: str,
        scout_account_id: str,
        application_name: str,
        output_dir: Optional[str] = None,
        java_source_path: Optional[str] = None,
        generate_iac: bool = True,
        save_to_mongodb: bool = True,
    ):
        """
        Initialize runner.

        Args:
            base_path: Base path for all flow outputs
            scout_account_id: Customer account ID
            application_name: Application name
            output_dir: Optional explicit output directory
            java_source_path: Optional explicit Java source path
            generate_iac: Whether to generate IaC templates
            save_to_mongodb: Whether to save artifacts to MongoDB
        """
        self.base_path = Path(base_path)
        self.account = scout_account_id
        self.app = application_name
        self.java_source_path = java_source_path
        self.generate_iac_flag = generate_iac
        self.save_to_mongodb = save_to_mongodb

        # Set output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = (
                self.base_path /
                "code-transformation-v2" /
                self.account /
                self.app /
                "architecture"
            )

        # Results
        self.sources: Optional[ConsolidatedSources] = None
        self.start_time: float = 0
        self.end_time: float = 0

    def _log(self, msg: str):
        """Log with timestamp."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] {msg}")

    def _save_to_mongo(self, artifact_type: str, data: dict, job_id: str):
        """Save artifact to MongoDB if enabled."""
        if not self.save_to_mongodb:
            return
        try:
            save_artifact_sync(
                account_id=self.account,
                application=self.app,
                program="_application",
                artifact_type=artifact_type,
                job_id=job_id,
                data=data
            )
            self._log(f"  [MongoDB] Saved {artifact_type}")
        except Exception as e:
            self._log(f"  [MongoDB] WARNING: Failed to save {artifact_type}: {e}")

    def run(self) -> Dict[str, Any]:
        """
        Run the complete Architecture Recommender flow.

        Returns:
            Dictionary with all results
        """
        self.start_time = time.time()

        self._log(f"[Architecture Recommender] Starting")
        self._log(f"  Account: {self.account}")
        self._log(f"  Application: {self.app}")

        try:
            # Create output directory
            self.output_dir.mkdir(parents=True, exist_ok=True)

            # 1. Load and consolidate sources
            self._log("[1/8] Loading and consolidating sources...")
            step_start = time.time()
            self.sources = self._load_sources()
            self._log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")
            self._log(f"  Sources loaded: {', '.join(self.sources.sources_loaded)}")

            # 2. Cross-validate sources
            self._log("[2/8] Cross-validating sources...")
            step_start = time.time()
            validation_report = self._validate_sources()
            self._log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")

            # 3. Generate recommendations
            self._log("[3/8] Generating compute recommendation...")
            step_start = time.time()
            compute_rec = self._recommend_compute()
            self._log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")
            self._log(f"  Service: {compute_rec.service.value}")

            self._log("[4/8] Generating database recommendation...")
            step_start = time.time()
            database_rec = self._recommend_database()
            self._log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")
            self._log(f"  Service: {database_rec.service.value}")

            self._log("[5/8] Generating API/storage/security recommendations...")
            step_start = time.time()
            api_rec = self._recommend_api()
            storage_rec = self._recommend_storage()
            security_rec = self._recommend_security()
            self._log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")

            # 4. Estimate costs
            self._log("[6/8] Estimating costs...")
            step_start = time.time()
            cost_estimate = self._estimate_costs(compute_rec, database_rec, api_rec)
            self._log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")
            self._log(f"  Monthly estimate: ${cost_estimate.total_monthly:.2f}")

            # 5. Build traceability
            self._log("[7/8] Building traceability...")
            step_start = time.time()
            traceability = self._build_traceability(compute_rec)
            self._log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")

            # 6. Generate IaC templates
            iac_output = None
            if self.generate_iac_flag:
                self._log("[8/8] Generating IaC templates...")
                step_start = time.time()
                iac_output = self._generate_iac(
                    compute_rec, database_rec, api_rec, storage_rec, security_rec
                )
                self._log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")
            else:
                self._log("[8/8] Skipping IaC generation (disabled)")

            # Define migration phases
            migration_phases = self._define_migration_phases(
                compute_rec, database_rec, api_rec
            )

            # Build summary
            summary = self._build_summary(
                compute_rec, database_rec, api_rec, cost_estimate, validation_report
            )

            self.end_time = time.time()
            duration_ms = int((self.end_time - self.start_time) * 1000)
            self._log(f"[Architecture Recommender] Complete in {duration_ms}ms")

            # Build final result
            result = {
                'status': 'completed',
                'summary': summary.model_dump(),
                'compute_recommendation': compute_rec.model_dump(),
                'database_recommendation': database_rec.model_dump(),
                'api_recommendation': api_rec.model_dump(),
                'storage_recommendation': storage_rec.model_dump() if storage_rec else None,
                'security_recommendation': security_rec.model_dump() if security_rec else None,
                'cost_estimate': cost_estimate.model_dump(),
                'validation_report': validation_report.model_dump(),
                'warnings': [w.model_dump() for w in validation_report.warnings],
                'traceability': traceability.model_dump(),
                'iac_templates': iac_output.model_dump() if iac_output else None,
                'migration_phases': [p.model_dump() for p in migration_phases],
                'java_analysis': self.sources.java_analysis.model_dump() if self.sources.java_analysis else None,
                'sources_used': self.sources.sources_loaded,
                'duration_seconds': self.end_time - self.start_time,
                'generated_at': datetime.now().isoformat(),
            }

            # Save results
            self._save_results(result)

            return result

        except Exception as e:
            self.end_time = time.time()
            return {
                'status': 'failed',
                'error': str(e),
                'duration_seconds': self.end_time - self.start_time,
            }

    def _load_sources(self) -> ConsolidatedSources:
        """Load all 5 sources."""
        consolidator = SourceConsolidator(
            base_path=str(self.base_path),
            scout_account_id=self.account,
            application_name=self.app,
            java_source_path=self.java_source_path
        )
        return consolidator.consolidate()

    def _validate_sources(self):
        """Cross-validate sources."""
        validator = CrossValidator(self.sources)
        return validator.validate()

    def _recommend_compute(self):
        """Generate compute recommendation."""
        recommender = ComputeRecommender(self.sources)
        return recommender.recommend()

    def _recommend_database(self):
        """Generate database recommendation."""
        recommender = DatabaseRecommender(self.sources)
        return recommender.recommend()

    def _recommend_api(self):
        """Generate API recommendation."""
        recommender = APIRecommender(self.sources)
        return recommender.recommend()

    def _recommend_storage(self) -> Optional[StorageRecommendation]:
        """Generate storage recommendation."""
        discovery = self.sources.discovery

        if discovery.has_data and discovery.has_vsam:
            return StorageRecommendation(
                buckets=[
                    S3Bucket(
                        name_suffix="input",
                        purpose="Input files from VSAM migration",
                        storage_class="STANDARD"
                    ),
                    S3Bucket(
                        name_suffix="output",
                        purpose="Processed output files",
                        storage_class="STANDARD"
                    ),
                    S3Bucket(
                        name_suffix="archive",
                        purpose="Long-term archive",
                        storage_class="GLACIER",
                        lifecycle_days=90
                    ),
                ],
                efs_required=False,
                confidence=0.85,
                evidence=[
                    Evidence(
                        source="discovery",
                        finding="VSAM file processing detected"
                    )
                ]
            )

        return None

    def _recommend_security(self) -> SecurityRecommendation:
        """Generate security recommendation."""
        return SecurityRecommendation(
            vpc_required=True,
            private_subnets=True,
            nat_gateway=True,
            encryption_at_rest=True,
            encryption_in_transit=True,
            secrets_manager=True,
            waf_required=False,
            confidence=0.90,
            evidence=[
                Evidence(
                    source="default",
                    finding="Standard security best practices applied"
                )
            ]
        )

    def _estimate_costs(self, compute, database, api):
        """Estimate costs based on recommendations."""
        estimator = CostEstimator(
            sources=self.sources,
            compute=compute,
            database=database,
            api=api
        )
        return estimator.estimate()

    def _build_traceability(self, compute) -> Traceability:
        """Build traceability from Java to AWS."""
        mappings = []

        for func in compute.functions:
            mappings.append(ServiceMapping(
                java_class=func.source_class,
                java_package=f"com.{self.app.replace('-', '')}",
                aws_service="Lambda" if compute.service.value == "AWS Lambda" else "ECS",
                aws_resource_name=func.name,
                entry_type=func.trigger
            ))

        return Traceability(
            mappings=mappings,
            unmapped_classes=[]
        )

    def _generate_iac(self, compute, database, api, storage, security):
        """Generate IaC templates."""
        generator = IaCGenerator(
            output_dir=str(self.output_dir),
            application_name=self.app,
            sources=self.sources,
            compute=compute,
            database=database,
            api=api,
            storage=storage,
            security=security
        )
        return generator.generate()

    def _define_migration_phases(self, compute, database, api) -> List[MigrationPhase]:
        """Define migration phases."""
        phases = []

        # Phase 1: Infrastructure
        phases.append(MigrationPhase(
            phase=1,
            name="Infrastructure Setup",
            description="Deploy VPC, networking, and security resources",
            components=["VPC", "Subnets", "Security Groups", "IAM Roles"],
            estimated_effort_weeks=2,
            dependencies=[]
        ))

        # Phase 2: Database (if needed)
        if database.service.value != "None":
            phases.append(MigrationPhase(
                phase=2,
                name="Database Migration",
                description=f"Deploy {database.service.value} and migrate data",
                components=[database.service.value, "Schema", "Data Migration"],
                estimated_effort_weeks=3,
                dependencies=["Infrastructure Setup"]
            ))

        # Phase 3: Compute
        compute_components = [f.name for f in compute.functions] if compute.functions else ["Application"]
        phases.append(MigrationPhase(
            phase=len(phases) + 1,
            name="Application Deployment",
            description=f"Deploy application to {compute.service.value}",
            components=compute_components,
            estimated_effort_weeks=2,
            dependencies=["Infrastructure Setup"] + (["Database Migration"] if database.service.value != "None" else [])
        ))

        # Phase 4: API (if needed)
        if api.required:
            phases.append(MigrationPhase(
                phase=len(phases) + 1,
                name="API Gateway Setup",
                description="Configure API Gateway and integrations",
                components=["API Gateway", "Routes", "Authorizers"],
                estimated_effort_weeks=1,
                dependencies=["Application Deployment"]
            ))

        # Phase 5: Testing and Cutover
        phases.append(MigrationPhase(
            phase=len(phases) + 1,
            name="Testing and Cutover",
            description="End-to-end testing and production cutover",
            components=["Integration Tests", "Performance Tests", "Cutover Plan"],
            estimated_effort_weeks=2,
            dependencies=[p.name for p in phases]
        ))

        return phases

    def _build_summary(self, compute, database, api, cost_estimate, validation_report) -> ArchitectureSummary:
        """Build executive summary."""
        # Determine application type
        java = self.sources.java_analysis
        has_api = api.required
        has_batch = False

        if java:
            for entry in java.entry_points:
                if entry.entry_type == "SCHEDULED":
                    has_batch = True

        if has_api and has_batch:
            app_type = "hybrid"
        elif has_api:
            app_type = "api-driven"
        elif has_batch:
            app_type = "batch-processing"
        else:
            app_type = "event-driven"

        return ArchitectureSummary(
            application_type=app_type,
            primary_compute=compute.service.value,
            primary_database=database.service.value if database.service.value != "None" else None,
            api_required=api.required,
            overall_confidence=validation_report.confidence_breakdown.get('overall', 0.75),
            estimated_monthly_cost=cost_estimate.total_monthly
        )

    def _save_results(self, result: Dict[str, Any]) -> None:
        """Save all results to files and MongoDB."""
        # Generate job ID for MongoDB
        job_id = f"arch_job_{int(time.time())}"

        # Main recommendations file
        recommendations_file = self.output_dir / "architecture_recommendations.json"
        recommendations_file.write_text(json.dumps(result, indent=2, default=str))
        self._save_to_mongo("architecture_recommendations", result, job_id)

        # Summary file
        summary_data = result.get('summary', {})
        summary_file = self.output_dir / "architecture_summary.json"
        summary_file.write_text(json.dumps(summary_data, indent=2))
        self._save_to_mongo("architecture_summary", summary_data, job_id)

        # Cost estimates file
        cost_data = result.get('cost_estimate', {})
        cost_file = self.output_dir / "cost_estimates.json"
        cost_file.write_text(json.dumps(cost_data, indent=2))
        self._save_to_mongo("cost_estimates", cost_data, job_id)

        # Validation report
        validation_data = result.get('validation_report', {})
        validation_file = self.output_dir / "validation_report.json"
        validation_file.write_text(json.dumps(validation_data, indent=2))
        self._save_to_mongo("validation_report", validation_data, job_id)

        # Traceability file
        trace_data = result.get('traceability', {})
        trace_file = self.output_dir / "traceability.json"
        trace_file.write_text(json.dumps(trace_data, indent=2))
        self._save_to_mongo("traceability", trace_data, job_id)

        # Java analysis file
        if result.get('java_analysis'):
            java_data = result.get('java_analysis', {})
            java_file = self.output_dir / "java_analysis.json"
            java_file.write_text(json.dumps(java_data, indent=2))
            self._save_to_mongo("java_analysis", java_data, job_id)


def run_architecture_recommender(
    base_path: str,
    scout_account_id: str,
    application_name: str,
    output_dir: Optional[str] = None,
    java_source_path: Optional[str] = None,
    generate_iac: bool = True,
    save_to_mongodb: bool = True,
) -> Dict[str, Any]:
    """
    Convenience function to run Architecture Recommender.

    Args:
        base_path: Base path for outputs
        scout_account_id: Account ID
        application_name: Application name
        output_dir: Optional output directory
        java_source_path: Optional Java source path
        generate_iac: Whether to generate IaC
        save_to_mongodb: Whether to save artifacts to MongoDB

    Returns:
        Results dictionary
    """
    runner = ArchitectureRunner(
        base_path=base_path,
        scout_account_id=scout_account_id,
        application_name=application_name,
        output_dir=output_dir,
        java_source_path=java_source_path,
        generate_iac=generate_iac,
        save_to_mongodb=save_to_mongodb,
    )
    return runner.run()
