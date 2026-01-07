"""
Artifacts Download API Routes

Generic download endpoint for job artifacts across all flow types.
"""

import zipfile
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import tempfile
import shutil

from migrate_dynamodb.dynamodb_jobs import get_job

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get(
    "/download/{job_id}",
    summary="Download Job Artifacts",
    description="Download all artifacts for a completed job as a ZIP file."
)
async def download_artifacts(job_id: str):
    """
    Download artifacts for any completed job.

    Creates a ZIP file containing all output artifacts from the job.
    Works for Code Analysis, Code Refactor, Smart Tests, Java Packaging, etc.
    """
    # Get job record
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Check if completed
    if record.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed (status: {record.status})"
        )

    # Check artifacts path exists
    artifacts_path = Path(record.artifacts_path)
    if not artifacts_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Artifacts directory not found"
        )

    # Check if directory has content
    if not any(artifacts_path.iterdir()):
        raise HTTPException(
            status_code=404,
            detail="No artifacts found in directory"
        )

    # Create temporary ZIP file
    temp_dir = Path(tempfile.gettempdir())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"{record.flow_type}_{job_id}_{timestamp}.zip"
    zip_path = temp_dir / zip_filename

    try:
        # Create ZIP containing all artifacts
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in artifacts_path.rglob('*'):
                if file_path.is_file():
                    # Add file with relative path to preserve directory structure
                    arcname = file_path.relative_to(artifacts_path)
                    zipf.write(file_path, arcname)

        # Return ZIP file
        return FileResponse(
            path=str(zip_path),
            media_type="application/zip",
            filename=zip_filename,
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )

    except Exception as e:
        # Clean up temp file if it exists
        if zip_path.exists():
            zip_path.unlink()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create ZIP file: {str(e)}"
        )
