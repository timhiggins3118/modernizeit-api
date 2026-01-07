"""
Code Analysis API Routes

Full COBOL analysis pipeline - JSON artifacts, graphs, Java generation.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse

from api.models.code_analysis import (
    CodeAnalysisRequest,
    CodeAnalysisResponse,
    CodeAnalysisStatusResponse,
)
from config.settings import settings
from migrate_dynamodb.dynamodb_jobs import JobRecord, get_job, save_job
from engines.code_analysis.runner import run_code_analysis

router = APIRouter(prefix="/codeanalysis", tags=["code_analysis"])


@router.post(
    "",
    response_model=CodeAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Code Analysis",
    description="""
    Run the full COBOL analysis pipeline.

    This endpoint:
    1. Locates COBOL files from ingest artifacts (by source_hash or latest)
    2. Runs tree-sitter parsing (zero-loss line inventory)
    3. Builds semantic models (DATA, PROCEDURE, FILE divisions)
    4. Generates Java code and Maven project (optional)
    5. Generates dependency graphs (optional)
    6. Saves all JSON artifacts to reports/

    The flow runs synchronously - returns when complete.
    """
)
async def start_code_analysis(request: CodeAnalysisRequest) -> CodeAnalysisResponse:
    """
    Run Code Analysis on ingested COBOL files.
    """
    try:
        # Find source files from ingest
        source_path = _find_source_path(
            request.scout_account_id,
            request.application_name,
            request.source_hash
        )

        # Output directory for this analysis
        output_dir = (
            settings.base_local_path
            / "code-transformation-v2"
            / request.scout_account_id
            / request.application_name
            / "code_analysis"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run the analysis
        result = run_code_analysis(
            source_path=str(source_path),
            output_dir=str(output_dir),
            main_program=request.main_program,
            generate_java=request.generate_java,
            generate_graphs=request.generate_graphs,
            account_id=request.scout_account_id,
            application=request.application_name,
            save_to_mongodb=True,
        )

        # Save job record
        if result.success:
            _save_job_record(
                job_id=result.job_id,
                request=request,
                artifacts_path=str(output_dir),
                status="completed"
            )
        else:
            _save_job_record(
                job_id=result.job_id,
                request=request,
                artifacts_path=str(output_dir),
                status="failed"
            )

        return CodeAnalysisResponse(
            success=result.success,
            job_id=result.job_id,
            status=result.status,
            artifacts_path=result.artifacts_path,
            main_program=result.main_program,
            base_name=result.base_name,
            error=result.error,
            duration_ms=result.duration_ms,
            summary=result.summary,
            artifacts=result.artifacts,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{job_id}/status",
    response_model=CodeAnalysisStatusResponse,
    summary="Get Code Analysis job status"
)
async def get_code_analysis_status(job_id: str) -> CodeAnalysisStatusResponse:
    """Get status of a Code Analysis job."""
    record = get_job(job_id)
    if record is None or record.flow_type != "codeanalysis":
        raise HTTPException(status_code=404, detail="Job not found")

    return CodeAnalysisStatusResponse(
        job_id=record.job_id,
        flow_type=record.flow_type,
        status=record.status,
        artifacts_path=record.artifacts_path,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


@router.get(
    "/{job_id}/results",
    summary="Get Code Analysis results overview"
)
async def get_code_analysis_results(job_id: str):
    """
    Get overview of Code Analysis results.

    Returns available artifacts and summary stats.
    """
    record = get_job(job_id)
    if record is None or record.flow_type != "codeanalysis":
        raise HTTPException(status_code=404, detail="Job not found")

    artifacts_path = Path(record.artifacts_path)
    reports_dir = artifacts_path / "reports"
    generated_dir = artifacts_path / "generated"

    result = {
        "job_id": record.job_id,
        "status": record.status,
        "artifacts_path": str(artifacts_path),
        "json_artifacts": [],
        "graphs": [],
        "java_project": None,
    }

    # List JSON artifacts
    if reports_dir.exists():
        result["json_artifacts"] = sorted([f.name for f in reports_dir.glob("*.json")])

        # List graphs
        graphs_dir = reports_dir / "graphs"
        if graphs_dir.exists():
            result["graphs"] = sorted([f.name for f in graphs_dir.glob("*.png")])

    # Check for Java project
    if generated_dir.exists():
        projects = list(generated_dir.iterdir())
        if projects:
            result["java_project"] = projects[0].name

    return result


@router.get(
    "/{job_id}/results/json/{filename}",
    summary="Get specific JSON artifact"
)
async def get_json_artifact(job_id: str, filename: str):
    """Get a specific JSON artifact by filename."""
    record = get_job(job_id)
    if record is None or record.flow_type != "codeanalysis":
        raise HTTPException(status_code=404, detail="Job not found")

    file_path = Path(record.artifacts_path) / "reports" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact not found: {filename}")

    try:
        content = json.loads(file_path.read_text())
        return JSONResponse(content=content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON in artifact")


@router.get(
    "/{job_id}/results/graphs/{filename}",
    summary="Get graph image"
)
async def get_graph(job_id: str, filename: str):
    """Get a graph PNG file."""
    record = get_job(job_id)
    if record is None or record.flow_type != "codeanalysis":
        raise HTTPException(status_code=404, detail="Job not found")

    file_path = Path(record.artifacts_path) / "reports" / "graphs" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Graph not found: {filename}")

    return FileResponse(file_path, media_type="image/png")


def _find_source_path(
    scout_account_id: str,
    application_name: str,
    source_hash: Optional[str] = None
) -> Path:
    """
    Find the path to extracted COBOL source files.

    Uses source_hash if provided, otherwise finds latest from ingest.
    """
    base_path = (
        settings.base_local_path
        / "code-transformation-v2"
        / scout_account_id
        / application_name
        / "shared"
    )

    if source_hash:
        # Use specific source hash
        source_path = base_path / "uploads" / source_hash / "extracted"
        if not source_path.exists():
            raise FileNotFoundError(f"Source not found for hash: {source_hash}")
        return source_path

    # Find latest
    latest_file = base_path / "uploads" / "latest.json"
    if not latest_file.exists():
        raise FileNotFoundError(
            f"No ingest found for {scout_account_id}/{application_name}. "
            "Run ingest first."
        )

    try:
        latest_data = json.loads(latest_file.read_text())
        source_hash = latest_data.get("source_hash")
        if not source_hash:
            raise FileNotFoundError("latest.json missing source_hash")
    except json.JSONDecodeError:
        raise FileNotFoundError("Invalid latest.json")

    source_path = base_path / "uploads" / source_hash / "extracted"
    if not source_path.exists():
        raise FileNotFoundError(f"Source not found for latest hash: {source_hash}")

    return source_path


def _save_job_record(
    job_id: str,
    request: CodeAnalysisRequest,
    artifacts_path: str,
    status: str
) -> None:
    """Save job record to database."""
    now = datetime.utcnow()
    record = JobRecord(
        job_id=job_id,
        flow_type="codeanalysis",
        status=status,
        created_at=now,
        updated_at=now,
        artifacts_path=artifacts_path,
        input_json=json.dumps({
            "scout_account_id": request.scout_account_id,
            "application_name": request.application_name,
            "source_hash": request.source_hash,
            "main_program": request.main_program,
            "generate_java": request.generate_java,
            "generate_graphs": request.generate_graphs,
        })
    )
    save_job(record)
