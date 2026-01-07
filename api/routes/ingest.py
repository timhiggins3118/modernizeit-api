"""
Ingest API Routes

FastAPI router for ingest operations.
Follows AWS API Gateway contract pattern.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from api.models.ingest import IngestRequest, IngestResponse, IngestStatusResponse
from api.models.execution import EngineResult
from config.settings import settings
from migrate_dynamodb.dynamodb_jobs import get_job
from migrate_dynamodb.dynamodb_accounts import get_account_s3_config
from engines.ingest.runner import run_ingest, parse_ingest_response
from utils.s3_helper import S3Helper, get_aws_credentials_from_db

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post(
    "/upload",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest source files",
    description="""
    Ingest source files (ZIP) into the system via multipart/form-data.

    This endpoint:
    1. Receives the ZIP file upload and form fields
    2. Saves the ZIP to disk under the configured base_local_path
    3. Extracts and catalogs all files
    4. Generates type mappings if COBOL is detected
    5. Creates job metadata and records the job in the database

    Files are stored at: {base_local_path}/code-transformation-v2/{account}/{app}/...
    """
)
async def upload_ingest(
    file: UploadFile = File(..., description="ZIP file containing source code"),
    scout_account_id: str = Form(..., description="Scout account identifier"),
    application_name: str = Form(..., description="Application name"),
    generate_type_mappings: bool = Form(default=True, description="Generate type mapping files"),
    source_lang: str = Form(default="cobol", description="Source language (cobol, cpp, etc.)"),
    target_lang: str = Form(default="java", description="Target language (java, dotnet, etc.)"),
) -> IngestResponse:
    """
    Execute ingest upload flow via multipart/form-data.

    This is the local equivalent of POST /ingest/upload in AWS API Gateway.
    Accepts a ZIP file upload along with form fields.
    """
    try:
        # Save uploaded file to disk under settings.base_local_path/uploads
        uploads_dir = settings.base_local_path / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)

        # Use the original filename from the upload
        filename = file.filename or "uploaded.zip"
        zip_path = uploads_dir / filename

        # Write the uploaded file to disk
        content = await file.read()
        with zip_path.open("wb") as f:
            f.write(content)

        # Build IngestRequest from form fields
        request = IngestRequest(
            scout_account_id=scout_account_id,
            application_name=application_name,
            zip_file_path=str(zip_path),
            working_folder=str(settings.base_local_path),
            generate_type_mappings=generate_type_mappings,
            source_lang=source_lang,
            target_lang=target_lang,
        )

        # Run the ingest engine
        result: EngineResult = run_ingest(request)

        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": result.error or "Ingest failed",
                    "logs": result.logs[-20:] if result.logs else []
                }
            )

        # Parse the response
        response = parse_ingest_response(result)
        if not response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Failed to parse ingest response",
                    "payload": result.payload,
                    "logs": result.logs[-20:] if result.logs else []
                }
            )

        # Upload to S3 if account uses S3 storage
        try:
            account_config = get_account_s3_config(scout_account_id)
            if account_config and account_config.get("storage_type") == "s3":
                # Get AWS credentials
                db_path = Path(__file__).parent.parent.parent / "data" / "jobs.db"
                aws_creds = get_aws_credentials_from_db(str(db_path))

                if aws_creds:
                    # Upload output folder to S3
                    s3_helper = S3Helper(
                        aws_access_key_id=aws_creds['aws_access_key_id'],
                        aws_secret_access_key=aws_creds['aws_secret_access_key'],
                        region=account_config.get('s3_region', 'us-east-1')
                    )

                    # Local path: {base_local_path}/code-transformation-v2/{account}/{app}
                    local_folder = settings.base_local_path / "code-transformation-v2" / scout_account_id / application_name

                    # S3 prefix: {s3_prefix}{account}/{app}/
                    s3_prefix = account_config.get('s3_prefix', '')
                    s3_key_prefix = f"{s3_prefix}{scout_account_id}/{application_name}/"

                    print(f"[S3 Upload] Uploading {local_folder} to s3://{account_config['s3_bucket']}/{s3_key_prefix}")

                    upload_result = s3_helper.upload_folder(
                        str(local_folder),
                        account_config['s3_bucket'],
                        s3_key_prefix
                    )

                    print(f"[S3 Upload] Success! Uploaded {upload_result['files_uploaded']} files")
        except Exception as e:
            # Log but don't fail the request - local files are already saved
            print(f"[S3 Upload] Warning: Failed to upload to S3: {e}")

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/jobs/{job_id}/status",
    response_model=IngestStatusResponse,
    summary="Get ingest job status",
    description="Check the status of an ingest job. For local execution, jobs complete synchronously."
)
async def get_ingest_status(job_id: str) -> IngestStatusResponse:
    """
    Get status of an ingest job.

    For local execution, ingest always completes synchronously,
    so this endpoint will return completed status if the job exists.

    In AWS, this would check Step Functions execution status.
    """
    # TODO: Implement job status lookup from local filesystem
    # For now, return a placeholder indicating sync execution
    return IngestStatusResponse(
        job_id=job_id,
        state="completed",
        progress=1.0,
        message="Local ingest jobs complete synchronously"
    )


@router.get(
    "/results/{job_id}",
    summary="Get ingest job results",
    description="Retrieve the results of a completed ingest job including catalogs and type mappings."
)
async def get_ingest_results(job_id: str):
    """
    Get results of an ingest job.

    Returns the job metadata and catalog information.

    Response includes:
    - job_id: The job identifier
    - status: Job status (completed, failed, etc.)
    - artifacts_path: Root path for job artifacts
    - file_catalog: Contents of file_catalog.json or null
    - classified_catalog: Contents of classified_catalog.json or null
    - type_mappings: Contents of cobol_to_java.json or null
    """
    # Look up job in database
    record = get_job(job_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )

    artifacts_path = Path(record.artifacts_path)

    # Try to find source_hash from input_json
    source_hash = None
    try:
        input_data = json.loads(record.input_json)
        source_hash = input_data.get("source_hash")
    except (json.JSONDecodeError, TypeError):
        pass

    # If source_hash not in input_json, try to discover from catalogs folder
    if not source_hash:
        source_hash = _discover_source_hash(artifacts_path)

    # Load catalog files
    file_catalog = None
    classified_catalog = None
    type_mappings = None

    if source_hash:
        # Paths follow ingest_upload_handler convention:
        # artifacts_path/shared/catalogs/{source_hash}/file_catalog.json
        # artifacts_path/shared/catalogs/{source_hash}/classified_catalog.json
        # artifacts_path/shared/type_mappings/{source_hash}/cobol_to_java.json
        catalog_dir = artifacts_path / "shared" / "catalogs" / source_hash
        type_mapping_dir = artifacts_path / "shared" / "type_mappings" / source_hash

        file_catalog = _load_json_file(catalog_dir / "file_catalog.json")
        classified_catalog = _load_json_file(catalog_dir / "classified_catalog.json")
        type_mappings = _load_json_file(type_mapping_dir / "cobol_to_java.json")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "job_id": record.job_id,
            "status": record.status,
            "artifacts_path": record.artifacts_path,
            "file_catalog": file_catalog,
            "classified_catalog": classified_catalog,
            "type_mappings": type_mappings
        }
    )


def _discover_source_hash(artifacts_path: Path) -> Optional[str]:
    """
    Discover source_hash by looking at the catalogs folder.

    Args:
        artifacts_path: Root artifacts path for the job

    Returns:
        Source hash string if found, None otherwise
    """
    catalogs_dir = artifacts_path / "shared" / "catalogs"
    if not catalogs_dir.exists():
        return None

    # List subdirectories - the first one should be the source_hash
    for item in catalogs_dir.iterdir():
        if item.is_dir():
            return item.name
    return None


def _load_json_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load and parse a JSON file.

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON content or None if file doesn't exist or parse fails
    """
    if not file_path.exists():
        return None
    try:
        return json.loads(file_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
