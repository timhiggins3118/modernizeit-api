"""
Monolith Identifier Runner

Orchestrates the monolith identification flow:
1. Static analysis (COBOL or Java)
2. Pattern detection
3. Modularity calculation
4. Business capability analysis
5. Decomposition strategy generation
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from engines.monolith_identifier.analyzers.static_analyzer import COBOLStaticAnalyzer
from engines.monolith_identifier.analyzers.java_analyzer import JavaStaticAnalyzer
from engines.monolith_identifier.generators.pattern_detector import PatternDetector
from engines.monolith_identifier.generators.modularity_calculator import ModularityCalculator
from engines.monolith_identifier.generators.business_capability_analyzer import BusinessCapabilityAnalyzer
from engines.monolith_identifier.generators.decomposition_strategist import DecompositionStrategist
from db.repositories.monolith_identifier_repo import save_artifact_sync


@dataclass
class MonolithIdentifierResult:
    """Result of monolith identification."""
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


def run_monolith_identifier(
    source_path: str,
    output_dir: str,
    source_type: str = "cobol",
    job_id: Optional[str] = None,
    account_id: Optional[str] = None,
    application: Optional[str] = None,
    save_to_mongodb: bool = True,
) -> MonolithIdentifierResult:
    """
    Run monolith identification on source code.

    Args:
        source_path: Path to source directory (COBOL or Java)
        output_dir: Directory for output artifacts
        source_type: Type of source ("cobol" or "java")
        job_id: Optional job ID (generated if not provided)
        account_id: Customer account ID for MongoDB storage
        application: Application name for MongoDB storage
        save_to_mongodb: Whether to save artifacts to MongoDB

    Returns:
        MonolithIdentifierResult with artifacts and summary
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
        job_id = f"mi_job_{int(time.time())}"

    log(f"[Monolith Identifier] Starting job {job_id}")
    log(f"  Source: {source_path}")
    log(f"  Source type: {source_type}")

    # Create output directory
    output_path = Path(output_dir)
    artifacts_path = output_path / "artifacts"
    artifacts_path.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Static analysis
        log("[1/5] Running static analysis...")
        step_start = time.time()
        if source_type == "cobol":
            analyzer = COBOLStaticAnalyzer()
            analyzer.analyze_directory(source_path)
            static_analysis = analyzer.get_analysis_result()
        else:
            analyzer = JavaStaticAnalyzer()
            analyzer.analyze_directory(source_path)
            static_analysis = analyzer.get_analysis_result()
        log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")
        log(f"  Programs: {static_analysis['summary']['total_programs']}")

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

        # Step 2: Pattern detection
        log("[2/5] Detecting patterns...")
        step_start = time.time()
        pattern_detector = PatternDetector()
        patterns = pattern_detector.detect_patterns(static_analysis, source_type)
        log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")
        log(f"  Patterns: {patterns['summary']['total_patterns']} total")

        # Save patterns
        patterns_file = artifacts_path / "detected_patterns.json"
        patterns_data = {
            **patterns,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_job_id": job_id
        }
        _save_json(patterns_file, patterns_data)
        save_to_mongo("detected_patterns", patterns_data)

        # Step 3: Modularity calculation
        log("[3/5] Calculating modularity metrics...")
        step_start = time.time()
        modularity_calc = ModularityCalculator()
        modularity = modularity_calc.calculate(static_analysis, patterns, source_type)
        log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")
        log(f"  Avg maintainability: {modularity['overall']['average_maintainability']:.1f}")

        # Save modularity metrics
        modularity_file = artifacts_path / "modularity_metrics.json"
        modularity_data = {
            **modularity,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_job_id": job_id
        }
        _save_json(modularity_file, modularity_data)
        save_to_mongo("modularity_metrics", modularity_data)

        # Step 4: Business capability analysis
        log("[4/5] Analyzing business capabilities...")
        step_start = time.time()
        capability_analyzer = BusinessCapabilityAnalyzer()
        capabilities = capability_analyzer.analyze(static_analysis, source_type)
        log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")
        log(f"  Capabilities: {capabilities['summary']['total_capabilities']}")

        # Save business capabilities
        capabilities_file = artifacts_path / "business_capabilities.json"
        capabilities_data = {
            **capabilities,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_job_id": job_id
        }
        _save_json(capabilities_file, capabilities_data)
        save_to_mongo("business_capabilities", capabilities_data)

        # Step 5: Decomposition strategy
        log("[5/5] Generating decomposition strategy...")
        step_start = time.time()
        strategist = DecompositionStrategist()
        decomposition = strategist.strategize(
            static_analysis, patterns, modularity, capabilities, source_type
        )
        log(f"  Complete in {int((time.time() - step_start) * 1000)}ms")
        log(f"  Recommended services: {decomposition['summary']['recommended_services_count']}")

        # Save decomposition strategy
        decomposition_file = artifacts_path / "decomposition_strategy.json"
        decomposition_data = {
            **decomposition,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_job_id": job_id
        }
        _save_json(decomposition_file, decomposition_data)
        save_to_mongo("decomposition_strategy", decomposition_data)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)
        log(f"[Monolith Identifier] Complete in {duration_ms}ms")

        # Build summary
        summary = {
            "source_type": source_type,
            "static_analysis": static_analysis.get("summary", {}),
            "patterns": patterns.get("summary", {}),
            "modularity": modularity.get("overall", {}),
            "business_capabilities": capabilities.get("summary", {}),
            "decomposition": decomposition.get("summary", {})
        }

        # Build artifacts map
        artifacts = {
            "static_analysis": str(static_file),
            "detected_patterns": str(patterns_file),
            "modularity_metrics": str(modularity_file),
            "business_capabilities": str(capabilities_file),
            "decomposition_strategy": str(decomposition_file)
        }

        return MonolithIdentifierResult(
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

        return MonolithIdentifierResult(
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
