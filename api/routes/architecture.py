"""
Architecture Recommender API Routes

FastAPI router for architecture recommendation operations.
Provides evidence-based AWS architecture recommendations.

Endpoints:
- POST /architecture/analyze - Run full architecture analysis
- GET /architecture/{job_id}/status - Check job status
- GET /architecture/{job_id}/results - Get results overview
- GET /architecture/{job_id}/results/json/{filename} - Get specific JSON artifact
- GET /architecture/{job_id}/results/iac - Get IaC templates
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse

from api.models.architecture import (
    ArchitectureRequest,
    ArchitectureResponse,
    ArchitectureStatusResponse,
    ArchitectureSummary,
)
from config.settings import settings
from engines.architecture.runner import ArchitectureRunner
from utils.storage_uploader import upload_to_s3_if_needed

router = APIRouter(prefix="/architecture", tags=["architecture"])


@router.post(
    "/analyze",
    response_model=ArchitectureResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run architecture analysis",
    description="""
    Run comprehensive architecture analysis on completed flow outputs.

    This endpoint:
    1. Loads data from 5 sources (Discovery, Data Analysis, Code Analysis, Code Refactor, Java)
    2. Analyzes generated Java code for dependencies and patterns
    3. Cross-validates sources to build confidence
    4. Generates evidence-based AWS architecture recommendations
    5. Estimates costs based on actual code metrics
    6. Generates IaC templates (CDK)

    Input can reference completed jobs from other flows, or provide explicit paths.

    The analysis is evidence-based - every recommendation includes proof from the code.
    """
)
async def run_architecture_analysis(
    scout_account_id: str = Form(..., description="Scout account identifier"),
    application_name: str = Form(..., description="Application name"),
    source_path: Optional[str] = Form(default=None, description="Base path for flow outputs"),
    java_source_path: Optional[str] = Form(default=None, description="Path to generated Java code"),
    discovery_job_id: Optional[str] = Form(default=None, description="Discovery job ID"),
    data_analysis_job_id: Optional[str] = Form(default=None, description="Data Analysis job ID"),
    code_analysis_job_id: Optional[str] = Form(default=None, description="Code Analysis job ID"),
    code_refactor_job_id: Optional[str] = Form(default=None, description="Code Refactor job ID"),
    generate_iac: bool = Form(default=True, description="Generate IaC templates"),
) -> ArchitectureResponse:
    """
    Execute architecture analysis.

    This is the local equivalent of POST /architecture/analyze in AWS API Gateway.
    """
    try:
        # Determine base path
        if source_path:
            base_path = Path(source_path)
        else:
            base_path = settings.base_local_path

        # Validate base path exists
        if not base_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Base path does not exist: {base_path}"
            )

        # Create output directory
        output_dir = (
            base_path /
            "code-transformation-v2" /
            scout_account_id /
            application_name /
            "architecture"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run architecture analysis
        runner = ArchitectureRunner(
            base_path=str(base_path),
            scout_account_id=scout_account_id,
            application_name=application_name,
            output_dir=str(output_dir),
            java_source_path=java_source_path,
            generate_iac=generate_iac,
            save_to_mongodb=True,
        )
        results = runner.run()

        if results.get('status') == 'failed':
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": results.get('error', 'Architecture analysis failed'),
                    "duration_seconds": results.get('duration_seconds', 0)
                }
            )

        # Upload to S3 if account uses S3 storage
        upload_to_s3_if_needed(scout_account_id, application_name, "architecture")

        # Build job ID
        job_id = f"arch_{scout_account_id}_{application_name}_{results.get('generated_at', '')[:10]}"

        # Build response
        return ArchitectureResponse(
            success=True,
            job_id=job_id,
            status="completed",
            source_path=str(base_path),
            output_path=str(output_dir),
            duration_seconds=results.get('duration_seconds', 0),
            summary=ArchitectureSummary(**results.get('summary', {})),
            compute_recommendation=results.get('compute_recommendation', {}),
            database_recommendation=results.get('database_recommendation', {}),
            api_recommendation=results.get('api_recommendation', {}),
            storage_recommendation=results.get('storage_recommendation', {}),
            security_recommendation=results.get('security_recommendation', {}),
            cost_estimate=results.get('cost_estimate', {}),
            validation_report=results.get('validation_report', {}),
            warnings=results.get('warnings', []),
            traceability=results.get('traceability', {}),
            iac_templates=results.get('iac_templates'),
            migration_phases=results.get('migration_phases', []),
            java_analysis=results.get('java_analysis'),
            sources_used=results.get('sources_used', []),
            generated_at=results.get('generated_at', '')
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/{job_id}/status",
    response_model=ArchitectureStatusResponse,
    summary="Get architecture job status",
    description="Check the status of an architecture analysis job."
)
async def get_architecture_status(job_id: str) -> ArchitectureStatusResponse:
    """Get status of an architecture job."""
    # Parse job_id: arch_{account}_{app}_{date}
    parts = job_id.split('_')
    if len(parts) < 4 or parts[0] != 'arch':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job_id format: {job_id}"
        )

    account = parts[1]
    app = parts[2]

    output_dir = (
        settings.base_local_path /
        "code-transformation-v2" /
        account /
        app /
        "architecture"
    )

    if not output_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Architecture results not found for job: {job_id}"
        )

    # Check if results exist
    results_file = output_dir / "architecture_recommendations.json"
    if results_file.exists():
        status_val = "completed"
    else:
        status_val = "pending"

    import os
    stat = output_dir.stat()

    return ArchitectureStatusResponse(
        job_id=job_id,
        flow_type="architecture",
        status=status_val,
        output_path=str(output_dir),
        created_at=str(stat.st_ctime),
        updated_at=str(stat.st_mtime)
    )


@router.get(
    "/{job_id}/results",
    summary="Get architecture results",
    description="Retrieve results of a completed architecture analysis."
)
async def get_architecture_results(
    job_id: str,
    section: Optional[str] = None
):
    """
    Get results of an architecture job.

    Args:
        job_id: Architecture job ID
        section: Optional specific section (summary, cost_estimate, etc.)

    Returns:
        Full results or specific section
    """
    # Parse job_id
    parts = job_id.split('_')
    if len(parts) < 4 or parts[0] != 'arch':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job_id format: {job_id}"
        )

    account = parts[1]
    app = parts[2]

    output_dir = (
        settings.base_local_path /
        "code-transformation-v2" /
        account /
        app /
        "architecture"
    )

    if not output_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Architecture results not found for job: {job_id}"
        )

    # Load results
    if section:
        # Load specific section
        if section == "iac":
            return await get_iac_templates(job_id)

        section_file = output_dir / f"{section}.json"
        if not section_file.exists():
            # Try from main file
            main_file = output_dir / "architecture_recommendations.json"
            if main_file.exists():
                data = json.loads(main_file.read_text())
                if section in data:
                    return JSONResponse(
                        status_code=status.HTTP_200_OK,
                        content=data[section]
                    )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Section not found: {section}"
            )
        content = json.loads(section_file.read_text())
        return JSONResponse(status_code=status.HTTP_200_OK, content=content)

    # Load full results
    results_file = output_dir / "architecture_recommendations.json"
    if not results_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Results not found for job: {job_id}"
        )

    content = json.loads(results_file.read_text())
    return JSONResponse(status_code=status.HTTP_200_OK, content=content)


@router.get(
    "/{job_id}/results/json/{filename}",
    summary="Get specific JSON artifact",
    description="Retrieve a specific JSON artifact from architecture results."
)
async def get_architecture_artifact(job_id: str, filename: str):
    """Get a specific JSON artifact."""
    parts = job_id.split('_')
    if len(parts) < 4 or parts[0] != 'arch':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job_id format: {job_id}"
        )

    account = parts[1]
    app = parts[2]

    output_dir = (
        settings.base_local_path /
        "code-transformation-v2" /
        account /
        app /
        "architecture"
    )

    # Ensure filename ends with .json
    if not filename.endswith('.json'):
        filename = f"{filename}.json"

    file_path = output_dir / filename
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact not found: {filename}"
        )

    content = json.loads(file_path.read_text())
    return JSONResponse(status_code=status.HTTP_200_OK, content=content)


@router.get(
    "/{job_id}/results/iac",
    summary="Get IaC templates",
    description="Retrieve generated IaC templates."
)
async def get_iac_templates(job_id: str):
    """Get generated IaC templates."""
    parts = job_id.split('_')
    if len(parts) < 4 or parts[0] != 'arch':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job_id format: {job_id}"
        )

    account = parts[1]
    app = parts[2]

    iac_dir = (
        settings.base_local_path /
        "code-transformation-v2" /
        account /
        app /
        "architecture" /
        "iac_templates"
    )

    if not iac_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="IaC templates not found"
        )

    # List all templates
    templates = {}
    for file_path in iac_dir.glob("*.ts"):
        templates[file_path.name] = file_path.read_text()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "templates": templates,
            "files": list(templates.keys()),
            "output_path": str(iac_dir)
        }
    )


@router.get(
    "/{job_id}/results/iac/{filename}",
    summary="Get specific IaC template file",
    description="Download a specific IaC template file."
)
async def get_iac_template_file(job_id: str, filename: str):
    """Get a specific IaC template file."""
    parts = job_id.split('_')
    if len(parts) < 4 or parts[0] != 'arch':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job_id format: {job_id}"
        )

    account = parts[1]
    app = parts[2]

    file_path = (
        settings.base_local_path /
        "code-transformation-v2" /
        account /
        app /
        "architecture" /
        "iac_templates" /
        filename
    )

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {filename}"
        )

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="text/plain"
    )
