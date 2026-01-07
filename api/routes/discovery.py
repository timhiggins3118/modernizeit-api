"""
Discovery API Routes

FastAPI router for discovery operations.
Follows AWS API Gateway contract pattern.

Provides executive-level analysis for C-suite decision makers:
- Integration detection
- Business process extraction
- ROI calculation with real industry formulas
- Migration roadmap generation
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Form, HTTPException, status
from fastapi.responses import JSONResponse

from api.models.discovery import (
    DiscoveryRequest,
    DiscoveryResponse,
    DiscoveryStatusResponse,
    CustomerInputs,
    ROIAnalysis,
    MigrationRoadmap
)
from api.models.execution import EngineResult
from config.settings import settings
from utils.storage_uploader import upload_to_s3_if_needed
from engines.discovery.runner import DiscoveryRunner

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post(
    "/analyze",
    response_model=DiscoveryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run discovery analysis",
    description="""
    Run comprehensive discovery analysis on COBOL source code.

    This endpoint:
    1. Detects integrations (CICS, DB2, MQ, VSAM, etc.) from code patterns
    2. Uses AI to identify business processes and data flows
    3. Calculates ROI using real industry benchmarks
    4. Generates a phased migration roadmap

    Input can be:
    - source_path: Path to existing COBOL source directory
    - ingest_job_id: Reference to a completed ingest job

    Customer-specific data (optional):
    - current_mips: Current mainframe MIPS
    - annual_mainframe_cost: Actual annual mainframe cost
    - cobol_developer_count: Number of COBOL developers
    - cobol_developer_salary: Average COBOL developer salary

    If customer data not provided, industry benchmarks are used.
    """
)
async def run_discovery_analysis(
    source_path: Optional[str] = Form(default=None, description="Path to COBOL source directory"),
    ingest_job_id: Optional[str] = Form(default=None, description="Ingest job ID to use as source"),
    scout_account_id: str = Form(..., description="Scout account identifier"),
    application_name: str = Form(..., description="Application name"),
    enable_ai: bool = Form(default=True, description="Enable AI-powered analysis (requires Bedrock)"),
    current_mips: Optional[int] = Form(default=None, description="Current mainframe MIPS"),
    annual_mainframe_cost: Optional[int] = Form(default=None, description="Actual annual mainframe cost"),
    cobol_developer_count: Optional[int] = Form(default=None, description="Number of COBOL developers"),
    cobol_developer_salary: Optional[int] = Form(default=None, description="Average COBOL developer salary"),
) -> DiscoveryResponse:
    """
    Execute discovery analysis.

    This is the local equivalent of POST /discovery/analyze in AWS API Gateway.
    """
    try:
        # Validate we have a source
        if not source_path and not ingest_job_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either source_path or ingest_job_id must be provided"
            )

        # If ingest_job_id provided, find the source path
        if ingest_job_id and not source_path:
            source_path = _get_source_path_from_ingest(ingest_job_id, scout_account_id, application_name)
            if not source_path:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Could not find source path for ingest job: {ingest_job_id}"
                )

        # Validate source path exists
        source_dir = Path(source_path)
        if not source_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source path does not exist: {source_path}"
            )

        # Build customer inputs if provided
        customer_inputs = {}
        if current_mips is not None:
            customer_inputs['current_mips'] = current_mips
        if annual_mainframe_cost is not None:
            customer_inputs['annual_mainframe_cost'] = annual_mainframe_cost
        if cobol_developer_count is not None:
            customer_inputs['cobol_developer_count'] = cobol_developer_count
        if cobol_developer_salary is not None:
            customer_inputs['cobol_developer_salary'] = cobol_developer_salary

        # Create output directory
        output_dir = (
            settings.base_local_path /
            "code-transformation-v2" /
            scout_account_id /
            application_name /
            "discovery"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run discovery
        runner = DiscoveryRunner(
            enable_ai=enable_ai,
            account_id=scout_account_id,
            application=application_name,
            save_to_mongodb=True,
        )
        results = runner.run(
            source_path=str(source_path),
            customer_inputs=customer_inputs if customer_inputs else None,
            output_dir=str(output_dir)
        )

        if results.get('status') == 'failed':
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": results.get('error', 'Discovery failed'),
                    "partial_results": {
                        k: v for k, v in results.items()
                        if k not in ['error', 'status']
                    }
                }
            )

        # Upload to S3 if account uses S3 storage
        upload_to_s3_if_needed(scout_account_id, application_name, "discovery")

        # Build response
        return DiscoveryResponse(
            success=True,
            job_id=f"discovery_{scout_account_id}_{application_name}_{results.get('started_at', '')[:10]}",
            status="completed",
            source_path=str(source_path),
            artifacts_path=str(output_dir),
            error=None,
            duration_ms=int(results.get('duration_seconds', 0) * 1000),
            summary={
                "executive_summary": results.get('executive_summary', {}),
                "integration_points": results.get('integration_points', {}),
                "business_processes": results.get('business_processes', {}),
                "api_patterns": results.get('api_patterns', {}),
                "roi_analysis": results.get('roi_analysis', {}),
                "migration_roadmap": results.get('migration_roadmap', {}),
            },
            artifacts={}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/roi/calculate",
    summary="Calculate ROI independently",
    description="""
    Calculate ROI using provided metrics and customer data.

    This endpoint allows ROI calculation without running full discovery.
    Useful for:
    - Quick estimates with different parameters
    - What-if analysis with varying assumptions
    - Updating ROI after customer provides actual data
    """
)
async def calculate_roi(
    total_loc: int = Form(..., description="Total lines of code"),
    total_files: int = Form(..., description="Total number of files"),
    high_complexity_files: int = Form(default=0, description="High complexity file count"),
    medium_complexity_files: int = Form(default=0, description="Medium complexity file count"),
    low_complexity_files: int = Form(default=0, description="Low complexity file count"),
    high_value_processes: int = Form(default=0, description="High value business processes"),
    medium_value_processes: int = Form(default=0, description="Medium value business processes"),
    low_value_processes: int = Form(default=0, description="Low value business processes"),
    current_mips: Optional[int] = Form(default=None, description="Current mainframe MIPS"),
    annual_mainframe_cost: Optional[int] = Form(default=None, description="Actual annual mainframe cost"),
    cobol_developer_count: int = Form(default=5, description="Number of COBOL developers"),
    cobol_developer_salary: int = Form(default=124681, description="Average COBOL developer salary"),
):
    """
    Calculate ROI with provided parameters.
    """
    from engines.discovery.generators.roi_calculator import (
        ROICalculator, CodeMetrics, ProcessMetrics
    )

    try:
        calculator = ROICalculator()

        code_metrics = CodeMetrics(
            total_loc=total_loc,
            total_files=total_files,
            high_complexity_files=high_complexity_files,
            medium_complexity_files=medium_complexity_files,
            low_complexity_files=low_complexity_files
        )

        process_metrics = ProcessMetrics(
            high_value_processes=high_value_processes,
            medium_value_processes=medium_value_processes,
            low_value_processes=low_value_processes,
            total_processes=high_value_processes + medium_value_processes + low_value_processes
        )

        customer_inputs = {
            'current_mips': current_mips,
            'annual_mainframe_cost': annual_mainframe_cost,
            'cobol_developer_count': cobol_developer_count,
            'cobol_developer_salary': cobol_developer_salary
        }

        # Empty integration points for standalone ROI
        integration_points = {'integration_points': []}

        result = calculator.calculate(
            code_metrics,
            process_metrics,
            integration_points,
            customer_inputs
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=result
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/results/{job_id}",
    summary="Get discovery results",
    description="Retrieve results of a completed discovery analysis."
)
async def get_discovery_results(
    job_id: str,
    section: Optional[str] = None
):
    """
    Get results of a discovery job.

    Args:
        job_id: Discovery job ID
        section: Optional specific section (roi_analysis, roadmap, etc.)

    Returns:
        Full discovery results or specific section
    """
    # Parse job_id to find output path
    # job_id format: discovery_{account}_{app}_{date}
    parts = job_id.split('_')
    if len(parts) < 4:
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
        "discovery"
    )

    if not output_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discovery results not found for job: {job_id}"
        )

    # Load results
    if section:
        # Load specific section
        section_file = output_dir / f"{section}.json"
        if not section_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Section not found: {section}"
            )
        content = json.loads(section_file.read_text())
        return JSONResponse(status_code=status.HTTP_200_OK, content=content)

    # Load all sections
    sections = [
        'discovery_summary',
        'integration_points',
        'business_processes',
        'api_patterns',
        'roi_analysis',
        'migration_roadmap'
    ]

    results = {}
    for s in sections:
        file_path = output_dir / f"{s}.json"
        if file_path.exists():
            try:
                results[s] = json.loads(file_path.read_text())
            except json.JSONDecodeError:
                results[s] = None
        else:
            results[s] = None

    return JSONResponse(status_code=status.HTTP_200_OK, content=results)


@router.get(
    "/assumptions",
    summary="Get ROI assumptions",
    description="Get the industry benchmarks and assumptions used for ROI calculations."
)
async def get_roi_assumptions():
    """
    Get ROI calculation assumptions.

    Returns all the industry benchmarks and their sources.
    This provides transparency for executive review.
    """
    from engines.discovery.utils.roi_config import DEFAULT_ROI_CONFIG, BENCHMARK_RANGES

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            'assumptions': DEFAULT_ROI_CONFIG.to_assumptions_dict(),
            'benchmarks': BENCHMARK_RANGES,
            'note': 'These are industry defaults. Provide customer-specific data for more accurate projections.'
        }
    )


def _get_source_path_from_ingest(
    job_id: str,
    account: str,
    app: str
) -> Optional[str]:
    """
    Get source path from an ingest job.

    Args:
        job_id: Ingest job ID
        account: Scout account ID
        app: Application name

    Returns:
        Path to source files or None
    """
    base_path = (
        settings.base_local_path /
        "code-transformation-v2" /
        account /
        app
    )

    # Look for COBOL in shared/uploads (from ingest)
    uploads_path = base_path / "shared" / "uploads"
    if uploads_path.exists():
        # Find the extracted folder (hash-based directory)
        for hash_dir in uploads_path.iterdir():
            if hash_dir.is_dir() and not hash_dir.name.endswith('.json'):
                extracted = hash_dir / "extracted"
                if extracted.exists():
                    return str(extracted)

    # Fallback to legacy locations
    legacy_path = base_path / "ingest" / "source_files"
    if legacy_path.exists():
        return str(legacy_path)

    source_path = base_path / "source"
    if source_path.exists():
        return str(source_path)

    return None
