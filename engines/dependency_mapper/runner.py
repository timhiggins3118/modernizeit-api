"""
Dependency Mapper Runner

Orchestrates the dependency mapping flow:
1. Static analysis (COBOL or Java)
2. Build dependency graph
3. Calculate coupling metrics
4. Assess risk
5. Detect microservice boundaries
6. Analyze impact
7. Generate reports
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from engines.dependency_mapper.analyzers.static_analyzer import StaticAnalyzer
from engines.dependency_mapper.analyzers.java_analyzer import JavaAnalyzer
from engines.dependency_mapper.generators.graph_builder import GraphBuilder
from engines.dependency_mapper.generators.coupling_calculator import CouplingCalculator
from engines.dependency_mapper.generators.risk_assessor import RiskAssessor
from engines.dependency_mapper.generators.microservice_detector import MicroserviceDetector
from engines.dependency_mapper.generators.impact_analyzer import ImpactAnalyzer
from db.repositories.dependency_mapper_repo import save_artifact_sync


@dataclass
class DependencyMapperResult:
    """Result of dependency mapping."""
    success: bool
    job_id: str
    source_type: str  # "cobol" or "java"
    status: str
    source_path: str
    artifacts_path: str
    error: Optional[str] = None
    duration_ms: int = 0
    summary: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)


def run_dependency_mapper(
    source_path: str,
    output_dir: str,
    source_type: str = "cobol",  # "cobol" or "java"
    job_id: Optional[str] = None,
    account_id: Optional[str] = None,
    application: Optional[str] = None,
    save_to_mongodb: bool = True,
) -> DependencyMapperResult:
    """
    Run dependency mapping on source code.

    Args:
        source_path: Path to source directory (COBOL or Java)
        output_dir: Directory for output artifacts
        source_type: Type of source ("cobol" or "java")
        job_id: Optional job ID (generated if not provided)
        account_id: Customer account ID for MongoDB storage
        application: Application name for MongoDB storage
        save_to_mongodb: Whether to save artifacts to MongoDB

    Returns:
        DependencyMapperResult with artifacts and summary
    """
    start_time = time.time()

    def log(msg: str):
        """Log with timestamp."""
        timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S')
        print(f"[{timestamp}] {msg}")

    def save_to_mongo(artifact_type: str, data: dict):
        """Save artifact to MongoDB if enabled."""
        if not save_to_mongodb or not account_id or not application:
            return
        try:
            save_artifact_sync(
                account_id=account_id,
                application=application,
                program="_application",
                artifact_type=artifact_type,
                job_id=job_id,
                data=data
            )
            log(f"  [MongoDB] Saved {artifact_type}")
        except Exception as e:
            log(f"  [MongoDB] WARNING: Failed to save {artifact_type}: {e}")

    # Generate job ID if not provided
    if not job_id:
        job_id = f"dm_job_{int(time.time())}"

    log(f"[Dependency Mapper] Starting job {job_id}")
    log(f"  Source: {source_path}")
    log(f"  Source type: {source_type}")

    # Create output directory
    output_path = Path(output_dir)
    artifacts_path = output_path / "artifacts"
    artifacts_path.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Static analysis
        log("[1/6] Running static analysis...")
        step_start = time.time()
        if source_type == "cobol":
            analyzer = StaticAnalyzer()
            analyzer.analyze_directory(source_path)
            static_analysis = analyzer.get_all_dependencies()
        else:
            analyzer = JavaAnalyzer()
            analyzer.analyze_directory(source_path)
            static_analysis = analyzer.get_all_dependencies()
        log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")

        # Save static analysis
        static_file = artifacts_path / "static_analysis.json"
        static_data = {
            **static_analysis,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_job_id": job_id,
            "source_type": source_type
        }
        _save_json(static_file, static_data)
        save_to_mongo("static_analysis", static_data)

        # Step 2: Build dependency graph
        log("[2/6] Building dependency graph...")
        step_start = time.time()
        graph_builder = GraphBuilder()
        if source_type == "cobol":
            graph = graph_builder.build_from_cobol(static_analysis)
        else:
            graph = graph_builder.build_from_java(static_analysis)
        log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")

        # Save dependency graph
        graph_file = artifacts_path / "dependency_graph.json"
        graph_data = {
            **graph,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_job_id": job_id
        }
        _save_json(graph_file, graph_data)
        save_to_mongo("dependency_graph", graph_data)

        # Step 3: Calculate coupling metrics
        log("[3/6] Calculating coupling metrics...")
        step_start = time.time()
        coupling_calc = CouplingCalculator()
        coupling_metrics = coupling_calc.calculate(graph)
        log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")

        # Save coupling metrics
        coupling_file = artifacts_path / "coupling_metrics.json"
        coupling_data = {
            **coupling_metrics,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_job_id": job_id
        }
        _save_json(coupling_file, coupling_data)
        save_to_mongo("coupling_metrics", coupling_data)

        # Step 4: Assess risk
        log("[4/6] Assessing risk...")
        step_start = time.time()
        risk_assessor = RiskAssessor()
        risk_assessment = risk_assessor.assess(graph, coupling_metrics)
        log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")

        # Save risk assessment
        risk_file = artifacts_path / "risk_assessment.json"
        risk_data = {
            **risk_assessment,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_job_id": job_id
        }
        _save_json(risk_file, risk_data)
        save_to_mongo("risk_assessment", risk_data)

        # Step 5: Detect microservice boundaries
        log("[5/6] Detecting microservice boundaries...")
        step_start = time.time()
        ms_detector = MicroserviceDetector()
        microservice_boundaries = ms_detector.detect(graph, coupling_metrics)
        log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")

        # Save microservice boundaries
        ms_file = artifacts_path / "microservice_boundaries.json"
        ms_data = {
            **microservice_boundaries,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_job_id": job_id
        }
        _save_json(ms_file, ms_data)
        save_to_mongo("microservice_boundaries", ms_data)

        # Step 6: Analyze impact
        log("[6/6] Analyzing impact...")
        step_start = time.time()
        impact_analyzer = ImpactAnalyzer()
        impact_analysis = impact_analyzer.analyze(graph)
        log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")

        # Save impact analysis
        impact_file = artifacts_path / "impact_analysis.json"
        impact_data = {
            **impact_analysis,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_job_id": job_id
        }
        _save_json(impact_file, impact_data)
        save_to_mongo("impact_analysis", impact_data)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        log(f"[Dependency Mapper] Complete in {duration_ms}ms")

        # Build summary
        summary = {
            "source_type": source_type,
            "static_analysis": static_analysis.get("summary", {}),
            "graph": graph.get("summary", {}),
            "coupling": coupling_metrics.get("overall", {}),
            "risk": risk_assessment.get("summary", {}),
            "microservices": microservice_boundaries.get("summary", {}),
            "impact": impact_analysis.get("summary", {})
        }

        # Build artifacts map
        artifacts = {
            "static_analysis": str(static_file),
            "dependency_graph": str(graph_file),
            "coupling_metrics": str(coupling_file),
            "risk_assessment": str(risk_file),
            "microservice_boundaries": str(ms_file),
            "impact_analysis": str(impact_file)
        }

        return DependencyMapperResult(
            success=True,
            job_id=job_id,
            source_type=source_type,
            status="completed",
            source_path=source_path,
            artifacts_path=str(artifacts_path),
            duration_ms=duration_ms,
            summary=summary,
            artifacts=artifacts
        )

    except Exception as e:
        import traceback
        traceback.print_exc()

        duration_ms = int((time.time() - start_time) * 1000)

        return DependencyMapperResult(
            success=False,
            job_id=job_id,
            source_type=source_type,
            status="failed",
            source_path=source_path,
            artifacts_path=str(artifacts_path),
            error=str(e),
            duration_ms=duration_ms
        )


def _save_json(file_path: Path, data: Dict[str, Any]):
    """Save data as JSON file."""
    file_path.write_text(json.dumps(data, indent=2, default=str))
