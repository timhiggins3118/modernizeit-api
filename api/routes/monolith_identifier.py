"""
Monolith Identifier API Routes

Analyzes source code for monolithic anti-patterns and provides
decomposition recommendations.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from api.models.monolith_identifier import (
    MonolithIdentifierRequest,
    MonolithIdentifierResponse,
    MonolithIdentifierStatusResponse,
    MonolithIdentifierResultsResponse,
    MonolithComparisonRequest,
    MonolithComparisonResponse,
)
from config.settings import settings
from migrate_dynamodb.dynamodb_jobs import JobRecord, get_job, save_job
from engines.monolith_identifier.runner import run_monolith_identifier

router = APIRouter(prefix="/monolithidentifier", tags=["monolith_identifier"])


@router.post(
    "",
    response_model=MonolithIdentifierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Monolith Identifier Analysis",
    description="""
    Run monolith identification on COBOL or Java source code.

    This endpoint:
    1. Analyzes source files for monolithic indicators
    2. Detects anti-patterns (God Objects, Big Ball of Mud, etc.)
    3. Calculates modularity metrics (cohesion, coupling, complexity)
    4. Identifies business capabilities
    5. Generates decomposition strategy with migration roadmap
    6. Outputs JSON reports

    Source types:
    - "cobol": Analyze COBOL source from ingest
    - "java": Analyze generated Java from code_analysis

    Reports generated:
    - static_analysis.json
    - detected_patterns.json
    - modularity_metrics.json
    - business_capabilities.json
    - decomposition_strategy.json
    """
)
async def run_monolith_analysis(request: MonolithIdentifierRequest) -> MonolithIdentifierResponse:
    """
    Run Monolith Identifier on source code.
    """
    try:
        # Find source path based on source_type
        source_path = _find_source_path(
            request.scout_account_id,
            request.application_name,
            request.source_type
        )

        # Output directory for artifacts
        output_dir = (
            settings.base_local_path
            / "code-transformation-v2"
            / request.scout_account_id
            / request.application_name
            / "monolith_identifier"
            / request.source_type
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate job ID
        job_id = f"mi_{request.source_type}_{request.scout_account_id}_{request.application_name}_{int(datetime.now().timestamp())}"

        # Run the monolith identifier
        result = run_monolith_identifier(
            source_path=str(source_path),
            output_dir=str(output_dir),
            source_type=request.source_type,
            job_id=job_id,
            account_id=request.scout_account_id,
            application=request.application_name,
            save_to_mongodb=True,
        )

        # Save job record
        _save_job_record(
            job_id=result.job_id,
            request=request,
            artifacts_path=str(output_dir),
            status="completed" if result.success else "failed"
        )

        return MonolithIdentifierResponse(
            success=result.success,
            job_id=result.job_id,
            source_type=result.source_type,
            status=result.status,
            source_path=result.source_path,
            artifacts_path=result.artifacts_path,
            error=result.error,
            duration_ms=result.duration_ms,
            summary=result.summary,
            artifacts=result.artifacts
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/compare",
    response_model=MonolithComparisonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compare COBOL vs Java Analysis",
    description="""
    Generate comparison report between COBOL and Java monolith analysis.

    Uses scout_account_id and application_name to find existing analysis results.

    Requires:
    - Run monolith identifier with source_type='cobol' first
    - Run monolith identifier with source_type='java' first

    Produces:
    - Gap analysis (differences between COBOL and Java patterns)
    - Insights (observations about the transformation)
    - Recommendations (suggested improvements)
    """
)
async def compare_analyses(request: MonolithComparisonRequest) -> MonolithComparisonResponse:
    """
    Compare COBOL and Java monolith analyses.
    """
    try:
        # Load COBOL analysis
        cobol_path = (
            settings.base_local_path
            / "code-transformation-v2"
            / request.scout_account_id
            / request.application_name
            / "monolith_identifier"
            / "cobol"
            / "artifacts"
        )

        # Load Java analysis
        java_path = (
            settings.base_local_path
            / "code-transformation-v2"
            / request.scout_account_id
            / request.application_name
            / "monolith_identifier"
            / "java"
            / "artifacts"
        )

        if not cobol_path.exists():
            raise FileNotFoundError(
                f"COBOL analysis not found. Run monolith identifier with source_type='cobol' first."
            )

        if not java_path.exists():
            raise FileNotFoundError(
                f"Java analysis not found. Run monolith identifier with source_type='java' first."
            )

        # Load summaries
        cobol_summary = _load_summary(cobol_path)
        java_summary = _load_summary(java_path)

        # Generate comparison
        gaps, insights, recommendations = _generate_comparison(cobol_summary, java_summary)

        # Save comparison report
        comparison_path = (
            settings.base_local_path
            / "code-transformation-v2"
            / request.scout_account_id
            / request.application_name
            / "monolith_identifier"
            / "comparison"
        )
        comparison_path.mkdir(parents=True, exist_ok=True)

        comparison_file = comparison_path / "comparison_report.json"
        comparison_data = {
            "cobol_summary": cobol_summary,
            "java_summary": java_summary,
            "gaps": gaps,
            "insights": insights,
            "recommendations": recommendations,
            "generated_at": datetime.now().isoformat()
        }
        comparison_file.write_text(json.dumps(comparison_data, indent=2))

        job_id = f"mi_compare_{request.scout_account_id}_{request.application_name}_{int(datetime.now().timestamp())}"

        return MonolithComparisonResponse(
            success=True,
            job_id=job_id,
            status="completed",
            cobol_summary=cobol_summary,
            java_summary=java_summary,
            gaps=gaps,
            insights=insights,
            recommendations=recommendations,
            artifacts_path=str(comparison_path)
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{job_id}/status",
    response_model=MonolithIdentifierStatusResponse,
    summary="Get Monolith Identifier job status"
)
async def get_monolith_identifier_status(job_id: str) -> MonolithIdentifierStatusResponse:
    """Get status of a Monolith Identifier job."""
    record = get_job(job_id)
    if record is None or record.flow_type != "monolithidentifier":
        raise HTTPException(status_code=404, detail="Job not found")

    return MonolithIdentifierStatusResponse(
        job_id=record.job_id,
        flow_type=record.flow_type,
        status=record.status,
        artifacts_path=record.artifacts_path,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


@router.get(
    "/{job_id}/results",
    response_model=MonolithIdentifierResultsResponse,
    summary="Get Monolith Identifier results overview"
)
async def get_monolith_identifier_results(job_id: str) -> MonolithIdentifierResultsResponse:
    """
    Get overview of Monolith Identifier results.
    """
    record = get_job(job_id)
    if record is None or record.flow_type != "monolithidentifier":
        raise HTTPException(status_code=404, detail="Job not found")

    artifacts_path = Path(record.artifacts_path)
    artifacts_dir = artifacts_path / "artifacts"

    # Parse source_type from job_id
    source_type = "cobol" if "_cobol_" in job_id else "java"

    result = MonolithIdentifierResultsResponse(
        job_id=record.job_id,
        status=record.status,
        source_type=source_type,
        artifacts_path=str(artifacts_path),
        json_artifacts=[],
        summary={},
    )

    # List JSON artifacts
    if artifacts_dir.exists():
        result.json_artifacts = sorted([f.name for f in artifacts_dir.glob("*.json")])

        # Load summary from decomposition strategy
        summary_file = artifacts_dir / "decomposition_strategy.json"
        if summary_file.exists():
            try:
                data = json.loads(summary_file.read_text())
                result.summary = data.get("summary", {})
            except json.JSONDecodeError:
                pass

    return result


@router.get(
    "/{job_id}/results/json/{filename}",
    summary="Get specific JSON artifact"
)
async def get_json_artifact(job_id: str, filename: str):
    """Get a specific JSON artifact by filename."""
    record = get_job(job_id)
    if record is None or record.flow_type != "monolithidentifier":
        raise HTTPException(status_code=404, detail="Job not found")

    file_path = Path(record.artifacts_path) / "artifacts" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact not found: {filename}")

    try:
        content = json.loads(file_path.read_text())
        return JSONResponse(content=content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON in artifact")


def _find_source_path(
    scout_account_id: str,
    application_name: str,
    source_type: str
) -> Path:
    """
    Find source path based on source type.

    For COBOL: shared/uploads/{hash}/extracted/ (from ingest)
    For Java: code_analysis/generated/.../src/main/java
    """
    base_path = (
        settings.base_local_path
        / "code-transformation-v2"
        / scout_account_id
        / application_name
    )

    if source_type == "cobol":
        # Look for COBOL in shared/uploads (from ingest)
        uploads_path = base_path / "shared" / "uploads"
        source_path = None

        if uploads_path.exists():
            # Find the extracted folder (hash-based directory)
            for hash_dir in uploads_path.iterdir():
                if hash_dir.is_dir() and not hash_dir.name.endswith('.json'):
                    extracted = hash_dir / "extracted"
                    if extracted.exists():
                        # Look for COBOL files in extracted directory
                        source_path = extracted
                        break

        # Fallback to other locations
        if not source_path or not source_path.exists():
            source_path = base_path / "ingest" / "source_files"
        if not source_path.exists():
            source_path = base_path / "source"
        if not source_path.exists():
            raise FileNotFoundError(
                f"COBOL source not found for {scout_account_id}/{application_name}. "
                "Run ingest first."
            )
    else:
        # Look for Java in code_analysis output
        code_analysis_path = base_path / "code_analysis" / "generated"
        if not code_analysis_path.exists():
            raise FileNotFoundError(
                f"Java source not found for {scout_account_id}/{application_name}. "
                "Run code_analysis first."
            )

        # Find the Java source directory
        java_dirs = []
        for gen_folder in code_analysis_path.iterdir():
            if gen_folder.is_dir():
                java_src = gen_folder / "src" / "main" / "java"
                if java_src.exists():
                    java_dirs.append(java_src)

        if not java_dirs:
            raise FileNotFoundError(
                f"Java source not found in {code_analysis_path}. "
                "Run code_analysis first."
            )

        source_path = java_dirs[0]  # Use first found

    return source_path


def _load_summary(artifacts_path: Path) -> Dict[str, Any]:
    """Load summary data from artifacts."""
    summary = {}

    # Load patterns summary
    patterns_file = artifacts_path / "detected_patterns.json"
    if patterns_file.exists():
        data = json.loads(patterns_file.read_text())
        summary["patterns"] = data.get("summary", {})

    # Load modularity summary
    modularity_file = artifacts_path / "modularity_metrics.json"
    if modularity_file.exists():
        data = json.loads(modularity_file.read_text())
        summary["modularity"] = data.get("overall", {})

    # Load capabilities summary
    capabilities_file = artifacts_path / "business_capabilities.json"
    if capabilities_file.exists():
        data = json.loads(capabilities_file.read_text())
        summary["capabilities"] = data.get("summary", {})

    # Load decomposition summary
    decomposition_file = artifacts_path / "decomposition_strategy.json"
    if decomposition_file.exists():
        data = json.loads(decomposition_file.read_text())
        summary["decomposition"] = data.get("summary", {})

    return summary


def _generate_comparison(
    cobol_summary: Dict[str, Any],
    java_summary: Dict[str, Any]
) -> tuple:
    """Generate comparison between COBOL and Java analyses."""
    gaps = []
    insights = []
    recommendations = []

    # Compare God Objects
    cobol_gods = cobol_summary.get("patterns", {}).get("god_objects", 0)
    java_gods = java_summary.get("patterns", {}).get("god_objects", 0)

    if java_gods > cobol_gods:
        gaps.append({
            "type": "god_class_increase",
            "detail": f"Java has {java_gods} God Classes vs {cobol_gods} God Objects in COBOL",
            "severity": "warning"
        })
        recommendations.append({
            "type": "refactor_god_classes",
            "detail": "Split God Classes following Single Responsibility Principle",
            "priority": "high"
        })
    elif java_gods < cobol_gods:
        insights.append(f"Java transformation successfully reduced God Objects from {cobol_gods} to {java_gods}")

    # Compare maintainability
    cobol_maint = cobol_summary.get("modularity", {}).get("average_maintainability", 0)
    java_maint = java_summary.get("modularity", {}).get("average_maintainability", 0)

    if java_maint < cobol_maint * 0.8:
        gaps.append({
            "type": "maintainability_decrease",
            "detail": f"Java maintainability ({java_maint:.1f}) is lower than COBOL ({cobol_maint:.1f})",
            "severity": "warning"
        })
        recommendations.append({
            "type": "improve_maintainability",
            "detail": "Apply code quality improvements to generated Java",
            "priority": "medium"
        })
    elif java_maint > cobol_maint * 1.1:
        insights.append(f"Java has improved maintainability ({java_maint:.1f}) vs COBOL ({cobol_maint:.1f})")

    # Compare capabilities
    cobol_caps = cobol_summary.get("capabilities", {}).get("total_capabilities", 0)
    java_caps = java_summary.get("capabilities", {}).get("total_capabilities", 0)

    if cobol_caps != java_caps:
        insights.append(
            f"COBOL has {cobol_caps} business capabilities, Java has {java_caps}"
        )

    # Compare recommended services
    cobol_services = cobol_summary.get("decomposition", {}).get("recommended_services_count", 0)
    java_services = java_summary.get("decomposition", {}).get("recommended_services_count", 0)

    if cobol_services != java_services:
        insights.append(
            f"COBOL suggests {cobol_services} services, Java suggests {java_services} - "
            "consider aligning decomposition approach"
        )

    # Add general insights
    if not gaps:
        insights.append("Java structure closely matches COBOL monolith characteristics")

    return gaps, insights, recommendations


def _save_job_record(
    job_id: str,
    request: MonolithIdentifierRequest,
    artifacts_path: str,
    status: str
) -> None:
    """Save job record to database."""
    now = datetime.utcnow()
    record = JobRecord(
        job_id=job_id,
        flow_type="monolithidentifier",
        status=status,
        created_at=now,
        updated_at=now,
        artifacts_path=artifacts_path,
        input_json=json.dumps({
            "scout_account_id": request.scout_account_id,
            "application_name": request.application_name,
            "source_type": request.source_type,
        })
    )
    save_job(record)
