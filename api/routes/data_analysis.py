"""
Data Analysis API Routes

Analyzes COBOL data structures to generate:
- Entity-Relationship Diagrams (ERD)
- Data Lineage graphs
- Copybook dependencies
- Type mappings for database design
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from api.models.data_analysis import (
    DataAnalysisRequest,
    DataAnalysisResponse,
    DataAnalysisStatusResponse,
    DataAnalysisResultsResponse,
)
from config.settings import settings
from migrate_dynamodb.dynamodb_jobs import JobRecord, get_job, save_job
from engines.data_analysis.runner import run_data_analysis

router = APIRouter(prefix="/dataanalysis", tags=["data_analysis"])


@router.post(
    "",
    response_model=DataAnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Data Analysis",
    description="""
    Run data analysis on ingested COBOL source code.

    This endpoint:
    1. Extracts data structures using regex patterns (fast)
    2. Analyzes hierarchical structures using AST parsing
    3. Uses AI to identify business entities and relationships
    4. Generates ERD with entities and relationships
    5. Traces data lineage through programs
    6. Analyzes copybook dependencies

    Reports generated:
    - data_structures.json (regex extraction)
    - hierarchical_structures.json (AST analysis)
    - ai_data_analysis.json (AI analysis)
    - erd.json (combined ERD)
    - data_lineage.json (data flows)
    - copybook_analysis.json (copybook dependencies)
    """
)
async def run_analysis(request: DataAnalysisRequest) -> DataAnalysisResponse:
    """
    Run Data Analysis on COBOL source code.
    """
    try:
        # Find source path (COBOL from ingest)
        source_path = _find_source_path(
            request.scout_account_id,
            request.application_name
        )

        # Output directory for artifacts
        output_dir = (
            settings.base_local_path
            / "code-transformation-v2"
            / request.scout_account_id
            / request.application_name
            / "data_analysis"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate job ID
        job_id = f"da_{request.scout_account_id}_{request.application_name}_{int(datetime.now().timestamp())}"

        # Run the data analysis
        result = run_data_analysis(
            source_path=str(source_path),
            output_dir=str(output_dir),
            job_id=job_id,
            skip_ai=False,  # Enable AI analysis by default
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

        return DataAnalysisResponse(
            success=result.success,
            job_id=result.job_id,
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


@router.get(
    "/{job_id}/status",
    response_model=DataAnalysisStatusResponse,
    summary="Get Data Analysis job status"
)
async def get_data_analysis_status(job_id: str) -> DataAnalysisStatusResponse:
    """Get status of a Data Analysis job."""
    record = get_job(job_id)
    if record is None or record.flow_type != "dataanalysis":
        raise HTTPException(status_code=404, detail="Job not found")

    return DataAnalysisStatusResponse(
        job_id=record.job_id,
        flow_type=record.flow_type,
        status=record.status,
        artifacts_path=record.artifacts_path,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


@router.get(
    "/{job_id}/results",
    response_model=DataAnalysisResultsResponse,
    summary="Get Data Analysis results overview"
)
async def get_data_analysis_results(job_id: str) -> DataAnalysisResultsResponse:
    """
    Get overview of Data Analysis results.
    """
    record = get_job(job_id)
    if record is None or record.flow_type != "dataanalysis":
        raise HTTPException(status_code=404, detail="Job not found")

    artifacts_path = Path(record.artifacts_path)
    artifacts_dir = artifacts_path / "artifacts"

    result = DataAnalysisResultsResponse(
        job_id=record.job_id,
        status=record.status,
        artifacts_path=str(artifacts_path),
        json_artifacts=[],
        summary={},
    )

    # List JSON artifacts
    if artifacts_dir.exists():
        result.json_artifacts = sorted([f.name for f in artifacts_dir.glob("*.json")])

        # Load summary from ERD
        erd_file = artifacts_dir / "erd.json"
        if erd_file.exists():
            try:
                data = json.loads(erd_file.read_text())
                result.summary = {
                    'erd': data.get('summary', {}),
                }
            except json.JSONDecodeError:
                pass

        # Add data lineage summary
        lineage_file = artifacts_dir / "data_lineage.json"
        if lineage_file.exists():
            try:
                data = json.loads(lineage_file.read_text())
                result.summary['data_lineage'] = data.get('summary', {})
            except json.JSONDecodeError:
                pass

        # Add copybook summary
        copybook_file = artifacts_dir / "copybook_analysis.json"
        if copybook_file.exists():
            try:
                data = json.loads(copybook_file.read_text())
                result.summary['copybooks'] = data.get('summary', {})
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
    if record is None or record.flow_type != "dataanalysis":
        raise HTTPException(status_code=404, detail="Job not found")

    file_path = Path(record.artifacts_path) / "artifacts" / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Artifact not found: {filename}")

    try:
        content = json.loads(file_path.read_text())
        return JSONResponse(content=content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON in artifact")


@router.get(
    "/{job_id}/results/erd",
    summary="Get ERD (Entity-Relationship Diagram)"
)
async def get_erd(job_id: str):
    """Get the generated ERD."""
    return await get_json_artifact(job_id, "erd.json")


@router.get(
    "/{job_id}/results/lineage",
    summary="Get Data Lineage"
)
async def get_lineage(job_id: str):
    """Get the data lineage analysis."""
    return await get_json_artifact(job_id, "data_lineage.json")


@router.get(
    "/{job_id}/results/copybooks",
    summary="Get Copybook Analysis"
)
async def get_copybooks(job_id: str):
    """Get the copybook dependency analysis."""
    return await get_json_artifact(job_id, "copybook_analysis.json")


def _find_source_path(
    scout_account_id: str,
    application_name: str
) -> Path:
    """
    Find COBOL source path from ingest.

    Looks in: shared/uploads/{hash}/extracted/
    """
    base_path = (
        settings.base_local_path
        / "code-transformation-v2"
        / scout_account_id
        / application_name
    )

    # Look for COBOL in shared/uploads (from ingest)
    uploads_path = base_path / "shared" / "uploads"
    source_path = None

    if uploads_path.exists():
        # Find the extracted folder (hash-based directory)
        for hash_dir in uploads_path.iterdir():
            if hash_dir.is_dir() and not hash_dir.name.endswith('.json'):
                extracted = hash_dir / "extracted"
                if extracted.exists():
                    source_path = extracted
                    break

    # Fallback locations
    if not source_path or not source_path.exists():
        source_path = base_path / "ingest" / "source_files"
    if not source_path.exists():
        source_path = base_path / "source"
    if not source_path.exists():
        raise FileNotFoundError(
            f"COBOL source not found for {scout_account_id}/{application_name}. "
            "Run ingest first."
        )

    return source_path


def _save_job_record(
    job_id: str,
    request: DataAnalysisRequest,
    artifacts_path: str,
    status: str
) -> None:
    """Save job record to database."""
    now = datetime.utcnow()
    record = JobRecord(
        job_id=job_id,
        flow_type="dataanalysis",
        status=status,
        created_at=now,
        updated_at=now,
        artifacts_path=artifacts_path,
        input_json=json.dumps({
            "scout_account_id": request.scout_account_id,
            "application_name": request.application_name,
        })
    )
    save_job(record)
