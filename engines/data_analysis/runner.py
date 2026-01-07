"""
Data Analysis Runner

Orchestrates the data analysis pipeline:
1. Regex extraction (Branch 1 - fast)
2. AST analysis (Branch 2 - structural)
3. AI analysis (Branch 3 - business context)
4. ERD generation (merge point)
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from engines.data_analysis.analyzers.regex_extractor import RegexDataExtractor
from engines.data_analysis.analyzers.ast_analyzer import ASTDataAnalyzer
from engines.data_analysis.analyzers.ai_analyzer import AIDataAnalyzer
from engines.data_analysis.generators.erd_generator import ERDGenerator
from db.repositories.data_analysis_repo import save_artifact_sync


@dataclass
class DataAnalysisResult:
    """Result of data analysis."""
    success: bool
    job_id: str
    status: str
    source_path: str
    artifacts_path: str
    error: Optional[str] = None
    duration_ms: int = 0
    summary: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)


def run_data_analysis(
    source_path: str,
    output_dir: str,
    job_id: Optional[str] = None,
    skip_ai: bool = False,
    account_id: Optional[str] = None,
    application: Optional[str] = None,
    save_to_mongodb: bool = True,
) -> DataAnalysisResult:
    """
    Run data analysis on COBOL source files.

    Args:
        source_path: Path to COBOL source directory
        output_dir: Directory for output artifacts
        job_id: Optional job ID (generated if not provided)
        skip_ai: Skip AI analysis (faster, less context)
        account_id: Customer account ID for MongoDB storage
        application: Application name for MongoDB storage
        save_to_mongodb: Whether to save artifacts to MongoDB

    Returns:
        DataAnalysisResult with artifacts and summary
    """
    start_time = time.time()

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
            print(f"  [MongoDB] Saved {artifact_type}")
        except Exception as e:
            print(f"  [MongoDB] WARNING: Failed to save {artifact_type}: {e}")

    # Generate job ID if not provided
    if not job_id:
        job_id = f"da_job_{int(time.time())}"

    # Create output directory
    output_path = Path(output_dir)
    artifacts_path = output_path / "artifacts"
    artifacts_path.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1: Regex extraction (Branch 1)
        print(f"[{job_id}] Step 1: Running regex extraction...")
        regex_extractor = RegexDataExtractor()
        regex_results = regex_extractor.extract_from_directory(source_path)

        # Save regex results
        regex_file = artifacts_path / "data_structures.json"
        regex_data = {
            **regex_results,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id
        }
        _save_json(regex_file, regex_data)
        save_to_mongo("data_structures", regex_data)
        print(f"[{job_id}] Regex extraction complete: {regex_results['summary']['total_data_items']} fields")

        # Step 2: AST analysis (Branch 2)
        print(f"[{job_id}] Step 2: Running AST analysis...")
        ast_analyzer = ASTDataAnalyzer()
        ast_results = ast_analyzer.analyze_directory(source_path)

        # Save AST results
        ast_file = artifacts_path / "hierarchical_structures.json"
        ast_data = {
            **ast_results,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_job_id': job_id
        }
        _save_json(ast_file, ast_data)
        save_to_mongo("hierarchical_structures", ast_data)
        print(f"[{job_id}] AST analysis complete: {ast_results['summary']['total_entities']} entities, {ast_results['summary']['total_relationships']} relationships")

        # Step 3: AI analysis (Branch 3) - optional
        ai_results = None
        if not skip_ai:
            print(f"[{job_id}] Step 3: Running AI analysis...")
            try:
                ai_analyzer = AIDataAnalyzer()
                ai_results = ai_analyzer.analyze_directory(
                    source_path,
                    regex_results=regex_results,
                    ast_results=ast_results
                )

                # Save AI results
                ai_file = artifacts_path / "ai_data_analysis.json"
                ai_data = {
                    **ai_results,
                    'generated_at': datetime.now(timezone.utc).isoformat(),
                    'source_job_id': job_id
                }
                _save_json(ai_file, ai_data)
                save_to_mongo("ai_data_analysis", ai_data)
                print(f"[{job_id}] AI analysis complete: {ai_results['summary']['total_entities']} entities identified")
            except Exception as e:
                print(f"[{job_id}] AI analysis skipped: {e}")
                ai_results = None
        else:
            print(f"[{job_id}] Step 3: AI analysis skipped (skip_ai=True)")

        # Step 4: ERD generation (merge point)
        print(f"[{job_id}] Step 4: Generating ERD...")
        erd_generator = ERDGenerator()
        erd, data_lineage, copybook_analysis = erd_generator.generate(
            regex_results=regex_results,
            ast_results=ast_results,
            ai_results=ai_results,
            job_id=job_id
        )

        # Save ERD
        erd_file = artifacts_path / "erd.json"
        _save_json(erd_file, erd)
        save_to_mongo("erd", erd)
        print(f"[{job_id}] ERD generated: {erd['summary']['total_entities']} entities, {erd['summary']['total_relationships']} relationships")

        # Save data lineage
        lineage_file = artifacts_path / "data_lineage.json"
        _save_json(lineage_file, data_lineage)
        save_to_mongo("data_lineage", data_lineage)
        print(f"[{job_id}] Data lineage: {data_lineage['summary']['total_flows']} flows")

        # Save copybook analysis
        copybook_file = artifacts_path / "copybook_analysis.json"
        _save_json(copybook_file, copybook_analysis)
        save_to_mongo("copybook_analysis", copybook_analysis)
        print(f"[{job_id}] Copybook analysis: {copybook_analysis['summary']['total_copybooks']} copybooks")

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Build summary
        summary = {
            'regex': regex_results.get('summary', {}),
            'ast': ast_results.get('summary', {}),
            'ai': ai_results.get('summary', {}) if ai_results else {},
            'erd': erd.get('summary', {}),
            'data_lineage': data_lineage.get('summary', {}),
            'copybooks': copybook_analysis.get('summary', {})
        }

        # Build artifacts map
        artifacts = {
            'data_structures': str(regex_file),
            'hierarchical_structures': str(ast_file),
            'erd': str(erd_file),
            'data_lineage': str(lineage_file),
            'copybook_analysis': str(copybook_file)
        }
        if ai_results:
            artifacts['ai_data_analysis'] = str(artifacts_path / "ai_data_analysis.json")

        print(f"[{job_id}] Data analysis complete in {duration_ms}ms")

        return DataAnalysisResult(
            success=True,
            job_id=job_id,
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

        return DataAnalysisResult(
            success=False,
            job_id=job_id,
            status="failed",
            source_path=source_path,
            artifacts_path=str(artifacts_path),
            error=str(e),
            duration_ms=duration_ms
        )


def _save_json(file_path: Path, data: Dict[str, Any]) -> None:
    """Save data as JSON file."""
    file_path.write_text(json.dumps(data, indent=2, default=str))
