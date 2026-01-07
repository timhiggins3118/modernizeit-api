"""
Dependency Mapper API Routes

Analyzes dependencies in COBOL or Java source code.
Produces reports for planning and optimization.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from api.models.dependency_mapper import (
    DependencyMapperRequest,
    DependencyMapperResponse,
    DependencyMapperStatusResponse,
    DependencyMapperResultsResponse,
    ComparisonRequest,
    ComparisonResponse,
)
from config.settings import settings
from migrate_dynamodb.dynamodb_jobs import JobRecord, get_job, save_job
from engines.dependency_mapper.runner import run_dependency_mapper

router = APIRouter(prefix="/dependencymapper", tags=["dependency_mapper"])


@router.post(
    "",
    response_model=DependencyMapperResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Dependency Mapper Analysis",
    description="""
    Run dependency mapping on COBOL or Java source code.

    This endpoint:
    1. Analyzes source files for dependencies
    2. Builds dependency graph (nodes + edges)
    3. Calculates coupling metrics
    4. Assesses risk (god programs, single points of failure)
    5. Detects microservice boundaries
    6. Analyzes impact (blast radius)
    7. Generates JSON reports

    Source types:
    - "cobol": Analyze COBOL source from ingest
    - "java": Analyze generated Java from code_analysis

    Reports generated:
    - static_analysis.json
    - dependency_graph.json
    - coupling_metrics.json
    - risk_assessment.json
    - microservice_boundaries.json
    - impact_analysis.json
    """
)
async def run_dependency_analysis(request: DependencyMapperRequest) -> DependencyMapperResponse:
    """
    Run Dependency Mapper on source code.
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
            / "dependency_mapper"
            / request.source_type
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate job ID
        job_id = f"dm_{request.source_type}_{request.scout_account_id}_{request.application_name}_{int(datetime.now().timestamp())}"

        # Run the dependency mapper
        result = run_dependency_mapper(
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

        return DependencyMapperResponse(
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
    response_model=ComparisonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compare COBOL vs Java Analysis",
    description="""
    Generate comparison report between COBOL and Java dependency analysis.

    Uses scout_account_id and application_name to find existing analysis results.

    Requires:
    - Run dependency mapper with source_type='cobol' first
    - Run dependency mapper with source_type='java' first

    Produces:
    - Gap analysis (differences between COBOL and Java)
    - Insights (observations about the transformation)
    - Recommendations (suggested improvements)
    """
)
async def compare_analyses(request: ComparisonRequest) -> ComparisonResponse:
    """
    Compare COBOL and Java dependency analyses.
    """
    try:
        # Load COBOL analysis
        cobol_path = (
            settings.base_local_path
            / "code-transformation-v2"
            / request.scout_account_id
            / request.application_name
            / "dependency_mapper"
            / "cobol"
            / "artifacts"
        )

        # Load Java analysis
        java_path = (
            settings.base_local_path
            / "code-transformation-v2"
            / request.scout_account_id
            / request.application_name
            / "dependency_mapper"
            / "java"
            / "artifacts"
        )

        if not cobol_path.exists():
            raise FileNotFoundError(
                f"COBOL analysis not found. Run dependency mapper with source_type='cobol' first."
            )

        if not java_path.exists():
            raise FileNotFoundError(
                f"Java analysis not found. Run dependency mapper with source_type='java' first."
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
            / "dependency_mapper"
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

        job_id = f"dm_compare_{request.scout_account_id}_{request.application_name}_{int(datetime.now().timestamp())}"

        return ComparisonResponse(
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
    response_model=DependencyMapperStatusResponse,
    summary="Get Dependency Mapper job status"
)
async def get_dependency_mapper_status(job_id: str) -> DependencyMapperStatusResponse:
    """Get status of a Dependency Mapper job."""
    record = get_job(job_id)
    if record is None or record.flow_type != "dependencymapper":
        raise HTTPException(status_code=404, detail="Job not found")

    return DependencyMapperStatusResponse(
        job_id=record.job_id,
        flow_type=record.flow_type,
        status=record.status,
        artifacts_path=record.artifacts_path,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


@router.get(
    "/{job_id}/results",
    response_model=DependencyMapperResultsResponse,
    summary="Get Dependency Mapper results overview"
)
async def get_dependency_mapper_results(job_id: str) -> DependencyMapperResultsResponse:
    """
    Get overview of Dependency Mapper results.
    """
    record = get_job(job_id)
    if record is None or record.flow_type != "dependencymapper":
        raise HTTPException(status_code=404, detail="Job not found")

    artifacts_path = Path(record.artifacts_path)
    artifacts_dir = artifacts_path / "artifacts"

    # Parse source_type from job_id
    source_type = "cobol" if "_cobol_" in job_id else "java"

    result = DependencyMapperResultsResponse(
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

        # Load summary from coupling metrics
        summary_file = artifacts_dir / "coupling_metrics.json"
        if summary_file.exists():
            try:
                data = json.loads(summary_file.read_text())
                result.summary = data.get("overall", {})
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
    if record is None or record.flow_type != "dependencymapper":
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

    # Load graph summary
    graph_file = artifacts_path / "dependency_graph.json"
    if graph_file.exists():
        data = json.loads(graph_file.read_text())
        summary["graph"] = data.get("summary", {})

    # Load coupling summary
    coupling_file = artifacts_path / "coupling_metrics.json"
    if coupling_file.exists():
        data = json.loads(coupling_file.read_text())
        summary["coupling"] = data.get("overall", {})

    # Load risk summary
    risk_file = artifacts_path / "risk_assessment.json"
    if risk_file.exists():
        data = json.loads(risk_file.read_text())
        summary["risk"] = data.get("summary", {})

    # Load microservice summary
    ms_file = artifacts_path / "microservice_boundaries.json"
    if ms_file.exists():
        data = json.loads(ms_file.read_text())
        summary["microservices"] = data.get("summary", {})

    return summary


def _generate_comparison(
    cobol_summary: Dict[str, Any],
    java_summary: Dict[str, Any]
) -> tuple:
    """Generate comparison between COBOL and Java analyses."""
    gaps = []
    insights = []
    recommendations = []

    # Compare program/class counts
    cobol_count = cobol_summary.get("graph", {}).get("program_count", 0)
    java_count = java_summary.get("graph", {}).get("program_count", 0)

    if java_count > cobol_count:
        gaps.append({
            "type": "class_explosion",
            "detail": f"Java has {java_count} classes vs {cobol_count} COBOL programs",
            "severity": "info"
        })
        insights.append(f"Java generated more classes ({java_count}) than COBOL programs ({cobol_count})")

    # Compare coupling
    cobol_coupling = cobol_summary.get("coupling", {}).get("average_coupling", 0)
    java_coupling = java_summary.get("coupling", {}).get("average_coupling", 0)

    if java_coupling > cobol_coupling * 1.5:
        gaps.append({
            "type": "coupling_increase",
            "detail": f"Java coupling ({java_coupling:.3f}) is higher than COBOL ({cobol_coupling:.3f})",
            "severity": "warning"
        })
        recommendations.append({
            "type": "reduce_coupling",
            "detail": "Consider extracting common functionality to reduce coupling",
            "priority": "medium"
        })

    # Compare god programs
    cobol_gods = cobol_summary.get("risk", {}).get("high_risk_count", 0)
    java_gods = java_summary.get("risk", {}).get("high_risk_count", 0)

    if java_gods > cobol_gods:
        gaps.append({
            "type": "god_class_introduced",
            "detail": f"Java has {java_gods} high-risk classes vs {cobol_gods} in COBOL",
            "severity": "warning"
        })
        recommendations.append({
            "type": "split_god_classes",
            "detail": "Use Code Refactor to split large classes",
            "priority": "high"
        })

    # Compare microservice boundaries
    cobol_services = cobol_summary.get("microservices", {}).get("total_services_suggested", 0)
    java_services = java_summary.get("microservices", {}).get("total_services_suggested", 0)

    if cobol_services != java_services:
        insights.append(
            f"COBOL suggests {cobol_services} services, Java structure shows {java_services} - "
            "consider aligning package structure"
        )

    # Add general insights
    if not gaps:
        insights.append("Java structure closely matches COBOL architecture")

    return gaps, insights, recommendations


def _save_job_record(
    job_id: str,
    request: DependencyMapperRequest,
    artifacts_path: str,
    status: str
) -> None:
    """Save job record to database."""
    now = datetime.utcnow()
    record = JobRecord(
        job_id=job_id,
        flow_type="dependencymapper",
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
