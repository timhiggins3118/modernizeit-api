"""
Code Refactor Runner

Orchestrates the refactoring analysis and transformation pipeline.

Two-phase architecture:
1. ANALYZE: Rule-based detection + AI interpretation -> Reports
2. TRANSFORM: Apply approved changes -> New Java files

This runner handles Phase 1 (Analyze) completely.
Phase 2 (Transform) is stubbed for future implementation.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings
from db.repositories.code_refactor_repo import save_artifact_sync


@dataclass
class CodeRefactorResult:
    """Result of code refactoring run."""
    success: bool
    job_id: str
    phase: str  # "analyze" or "transform"
    status: str
    java_file: str
    class_name: str
    artifacts_path: str
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    duration_ms: int = 0
    summary: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)


def run_code_refactor(
    java_file: str,
    output_dir: str,
    semantic_models_path: Optional[str] = None,
    mode: str = "analyze",  # "analyze", "transform", or "full"
    use_ai: bool = True,
    recipes_to_apply: Optional[List[str]] = None,
    account_id: Optional[str] = None,
    application: Optional[str] = None,
    save_to_mongodb: bool = True,
) -> CodeRefactorResult:
    """
    Run the code refactoring pipeline.

    Args:
        java_file: Path to generated Java file to analyze/refactor
        output_dir: Directory for output artifacts
        semantic_models_path: Path to code_analysis models (data_model.json, etc.)
        mode: "analyze" (Phase 1), "transform" (Phase 2), or "full" (both)
        use_ai: Whether to use Bedrock AI for analysis
        recipes_to_apply: Specific recipe IDs to apply (transform mode only)
        account_id: Customer account ID for MongoDB storage
        application: Application name for MongoDB storage
        save_to_mongodb: Whether to save artifacts to MongoDB (default: True)

    Returns:
        CodeRefactorResult with job details and artifact paths
    """
    start_time = time.time()
    logs: List[str] = []

    def log(msg: str):
        logs.append(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}")
        print(msg)

    def save_to_mongo(program: str, artifact_type: str, data: dict, job_id: str):
        """Save artifact to MongoDB if enabled."""
        if not save_to_mongodb or not account_id or not application:
            return
        try:
            save_artifact_sync(
                account_id=account_id,
                application=application,
                program=program,
                artifact_type=artifact_type,
                job_id=job_id,
                data=data
            )
            log(f"  [MongoDB] Saved {program}/{artifact_type}")
        except Exception as e:
            log(f"  [MongoDB] WARNING: Failed to save {artifact_type}: {e}")

    # Generate job ID
    timestamp = int(time.time())
    job_id = f"rf_job_{timestamp}"

    try:
        java_path = Path(java_file)
        output_path = Path(output_dir)

        if not java_path.exists():
            raise FileNotFoundError(f"Java file not found: {java_file}")

        # Create output directories
        artifacts_dir = output_path / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        logs_dir = output_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        log(f"Java file: {java_path}")
        log(f"Output: {output_path}")
        log(f"Mode: {mode}")

        # Import components
        from engines.code_refactor.analyzers.rule_analyzer import RuleAnalyzer
        from engines.code_refactor.analyzers.ai_analyzer import AIAnalyzer
        from engines.code_refactor.generators.report_generator import ReportGenerator

        artifacts: Dict[str, str] = {}
        summary: Dict[str, Any] = {}

        # ========== PHASE 1: ANALYZE ==========
        if mode in ("analyze", "full"):
            log("\n=== PHASE 1: ANALYZE ===")

            # Step 1: Rule-based analysis
            log("[1/3] Running rule-based analysis...")
            rule_analyzer = RuleAnalyzer(semantic_models_path)
            rule_results = rule_analyzer.analyze(str(java_path))
            log(f"  Patterns detected: {len(rule_results.patterns)}")
            log(f"  High severity: {rule_results.summary.get('high_severity', 0)}")

            # Step 2: AI analysis
            if use_ai:
                log("[2/3] Running AI analysis (Bedrock Claude)...")
                ai_start = time.time()
                ai_analyzer = AIAnalyzer()

                # Read Java content for context (first 500 lines)
                java_content = java_path.read_text()
                java_lines = java_content.split('\n')[:500]
                java_sample = '\n'.join(java_lines)
                log(f"  Java context: {len(java_lines)} lines")

                # Load semantic context if available
                semantic_context = None
                if semantic_models_path:
                    semantic_context = _load_semantic_context(semantic_models_path)
                    log(f"  Semantic context: loaded")

                try:
                    log(f"  Calling Bedrock API...")
                    ai_results = ai_analyzer.analyze(
                        rule_results,
                        java_content=java_sample,
                        semantic_context=semantic_context,
                    )
                    ai_duration = int((time.time() - ai_start) * 1000)
                    log(f"  AI analysis complete in {ai_duration}ms")
                    log(f"  Recommendations: {len(ai_results.recommendations)}")
                except Exception as e:
                    ai_duration = int((time.time() - ai_start) * 1000)
                    log(f"  AI analysis failed after {ai_duration}ms, using fallback: {e}")
                    ai_results = ai_analyzer.analyze_without_bedrock(rule_results)
                    log(f"  Fallback recommendations: {len(ai_results.recommendations)}")
            else:
                log("[2/3] Skipping AI analysis (disabled)")
                ai_analyzer = AIAnalyzer()
                ai_results = ai_analyzer.analyze_without_bedrock(rule_results)

            # Step 3: Generate reports
            log("[3/3] Generating reports...")
            report_generator = ReportGenerator(str(artifacts_dir))

            report_files = report_generator.generate_full_report(
                rule_results,
                ai_results,
                job_id,
            )
            artifacts.update(report_files)

            # Generate recipe file
            recipes_path = report_generator.generate_recipe_file(
                rule_results,
                ai_results,
                job_id,
            )
            artifacts["refactor_recipes"] = recipes_path
            log(f"  Generated {len(report_files) + 1} report files")

            # Save artifacts to MongoDB
            class_name = java_path.stem

            # Save refactor_report
            refactor_report_path = Path(report_files["report_json"])
            if refactor_report_path.exists():
                with open(refactor_report_path) as f:
                    save_to_mongo(class_name, "refactor_report", json.load(f), job_id)

            # Save rule_patterns
            rule_patterns_path = Path(report_files["rule_patterns"])
            if rule_patterns_path.exists():
                with open(rule_patterns_path) as f:
                    save_to_mongo(class_name, "rule_patterns", json.load(f), job_id)

            # Save ai_analysis
            ai_analysis_path = Path(report_files["ai_analysis"])
            if ai_analysis_path.exists():
                with open(ai_analysis_path) as f:
                    save_to_mongo(class_name, "ai_analysis", json.load(f), job_id)

            # Save refactor_recipes
            recipes_file = Path(recipes_path)
            if recipes_file.exists():
                with open(recipes_file) as f:
                    save_to_mongo(class_name, "refactor_recipes", json.load(f), job_id)

            # Build summary
            summary = {
                "phase": "analyze",
                "patterns_detected": len(rule_results.patterns),
                "recommendations": len(ai_results.recommendations),
                "high_severity": rule_results.summary.get("high_severity", 0),
                "high_priority": ai_results.summary.get("high_priority", 0),
                "overall_recommendation": ai_results.summary.get("top_recommendations", [])[:3],
                "metrics": rule_results.metrics,
            }

        # ========== PHASE 2: TRANSFORM ==========
        if mode in ("transform", "full"):
            log("\n=== PHASE 2: TRANSFORM ===")
            log("Transform phase not yet implemented (Phase 2)")
            log("Use the refactor_recipes.json to guide manual or future automated transforms")

            # Placeholder for future implementation
            summary["transform_status"] = "not_implemented"
            summary["transform_message"] = (
                "Phase 2 (Transform) will apply approved recipes to generate modernized Java. "
                "For now, use the analysis reports to guide manual refactoring."
            )

        # Write execution log
        log_file = logs_dir / "execution_log.json"
        execution_log_data = {
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
            "mode": mode,
            "java_file": str(java_path),
            "logs": logs,
        }
        with open(log_file, 'w') as f:
            json.dump(execution_log_data, f, indent=2)
        artifacts["execution_log"] = str(log_file)

        # Save execution log to MongoDB
        save_to_mongo(java_path.stem, "execution_log", execution_log_data, job_id)

        # Build result
        duration_ms = int((time.time() - start_time) * 1000)

        result = CodeRefactorResult(
            success=True,
            job_id=job_id,
            phase=mode,
            status="completed",
            java_file=str(java_path),
            class_name=java_path.stem,
            artifacts_path=str(output_path),
            logs=logs,
            duration_ms=duration_ms,
            summary=summary,
            artifacts=artifacts,
        )

        log(f"\nRefactor analysis complete in {duration_ms}ms")
        return result

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        return CodeRefactorResult(
            success=False,
            job_id=job_id,
            phase=mode,
            status="failed",
            java_file=java_file,
            class_name=Path(java_file).stem if java_file else "unknown",
            artifacts_path=str(output_dir),
            error=str(e),
            logs=logs,
            duration_ms=duration_ms,
        )


def _load_semantic_context(models_path: str) -> Optional[Dict[str, Any]]:
    """Load semantic models from code_analysis output."""
    context = {}
    models_dir = Path(models_path)

    if not models_dir.exists():
        return None

    # Load data model
    data_models = list(models_dir.glob("*_data_model.json"))
    if data_models:
        with open(data_models[0]) as f:
            context["data_model"] = json.load(f)

    # Load procedure model
    proc_models = list(models_dir.glob("*_procedure_model.json"))
    if proc_models:
        with open(proc_models[0]) as f:
            context["procedure_model"] = json.load(f)

    return context if context else None


def get_refactor_status(job_id: str, artifacts_path: str) -> Dict[str, Any]:
    """
    Get status of a refactor job.

    Args:
        job_id: Job identifier
        artifacts_path: Path to job artifacts

    Returns:
        Status dictionary
    """
    artifacts_dir = Path(artifacts_path) / "artifacts"
    logs_dir = Path(artifacts_path) / "logs"

    status = {
        "job_id": job_id,
        "status": "unknown",
        "artifacts": [],
    }

    # Check for completion
    if (artifacts_dir / "refactor_report.json").exists():
        status["status"] = "completed"

        # List artifacts
        for f in artifacts_dir.glob("*.json"):
            status["artifacts"].append(f.name)
        for f in artifacts_dir.glob("*.md"):
            status["artifacts"].append(f.name)

        # Load summary
        report_path = artifacts_dir / "refactor_report.json"
        with open(report_path) as f:
            report = json.load(f)
            status["summary"] = report.get("summary", {})

    elif (logs_dir / "execution_log.json").exists():
        status["status"] = "in_progress"

    return status
