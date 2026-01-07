"""
Ingest Engine Runner

Wraps the ingest_upload_handler with LocalLambdaExecutor for local execution.
This is the glue between the API layer and the Lambda code.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from api.models.execution import EngineResult
from api.models.ingest import IngestRequest, IngestResponse
from config.settings import settings
from execution.local_lambda_executor import LocalLambdaExecutor


def run_ingest(request: IngestRequest) -> EngineResult:
    """
    Execute the Ingest flow.

    This function:
    1. Builds the DOC-280 event format
    2. Creates a LocalLambdaExecutor pointing to the ingest handler
    3. Invokes the handler
    4. Saves job metadata to the jobs database
    5. Returns an EngineResult

    Args:
        request: IngestRequest with all required parameters

    Returns:
        EngineResult with success status, payload, and logs
    """
    start_time = time.time()

    # Determine working folder: use request value if provided, otherwise settings default
    working_folder = request.working_folder.strip() if request.working_folder else ""
    if not working_folder:
        working_folder = str(settings.base_local_path)

    # Build the event in DOC-280 format
    event = {
        "nodeId": "ingest-upload",
        "nodeType": "lambda.local.ingest.upload",
        "inputs": {},
        "workflowContext": {
            "scout_account_id": request.scout_account_id,
            "application_name": request.application_name,
            "zip_file_path": request.zip_file_path,
            "working_folder": working_folder,
            "generate_type_mappings": request.generate_type_mappings,
            "source_lang": request.source_lang,
            "target_lang": request.target_lang,
        },
        "config": {}
    }

    # Add optional fields if provided
    if request.source_hash:
        event["workflowContext"]["source_hash"] = request.source_hash
    if request.job_id:
        event["workflowContext"]["job_id"] = request.job_id

    # Get path to the ingest handler
    # The handler is in engines/ingest/ingest_upload_handler.py
    engines_path = Path(__file__).parent
    project_path = str(engines_path)

    # Create executor
    executor = LocalLambdaExecutor(
        project_path=project_path,
        handler="ingest_upload_handler.local_ingest_handler",
        working_folder=working_folder
    )

    # Invoke
    result = executor.invoke(event)

    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)

    # Extract job_id and source_hash from payload if successful
    job_id = None
    source_hash = None
    if result["success"] and result["payload"]:
        payload = result["payload"]
        # The handler returns {statusCode, headers, body}
        # body is a JSON string with the actual response
        if "body" in payload:
            try:
                body_data = json.loads(payload["body"])
                job_id = body_data.get("job_id")
                source_hash = body_data.get("source_hash")
            except (json.JSONDecodeError, TypeError):
                pass

    # Save job record to database if successful
    if result["success"] and job_id:
        _save_job_record(
            job_id=job_id,
            request=request,
            working_folder=working_folder,
            source_hash=source_hash
        )

    return EngineResult(
        success=result["success"],
        job_id=job_id,
        payload=result["payload"],
        logs=result["logs"],
        error=result["error"],
        duration_ms=duration_ms
    )


def _save_job_record(
    job_id: str,
    request: IngestRequest,
    working_folder: str,
    source_hash: Optional[str]
) -> None:
    """
    Save job record to the jobs database.

    Args:
        job_id: The job identifier
        request: Original ingest request
        working_folder: The resolved working folder path
        source_hash: Source hash from the ingest response
    """
    from migrate_dynamodb.dynamodb_jobs import JobRecord, save_job

    # Build artifacts path: working_folder/bucket/account/app
    # The ingest handler uses BUCKET_NAME = 'code-transformation-v2'
    bucket = "code-transformation-v2"
    artifacts_path = str(
        Path(working_folder) / bucket / request.scout_account_id / request.application_name
    )

    now = datetime.utcnow()
    record = JobRecord(
        job_id=job_id,
        flow_type="ingest",
        status="completed",
        created_at=now,
        updated_at=now,
        artifacts_path=artifacts_path,
        input_json=json.dumps({
            "scout_account_id": request.scout_account_id,
            "application_name": request.application_name,
            "zip_file_path": request.zip_file_path,
            "working_folder": working_folder,
            "generate_type_mappings": request.generate_type_mappings,
            "source_lang": request.source_lang,
            "target_lang": request.target_lang,
            "source_hash": source_hash,
        })
    )

    try:
        print(f"[runner.py] Saving job to DynamoDB: {job_id}, tenant: {request.scout_account_id}")
        save_job(record)
        print(f"[runner.py] Job saved successfully to DynamoDB: {job_id}")
    except Exception as e:
        print(f"[runner.py] ERROR: Failed to save job to DynamoDB: {job_id}")
        print(f"[runner.py] Exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def parse_ingest_response(result: EngineResult) -> Optional[IngestResponse]:
    """
    Parse the EngineResult payload into an IngestResponse.

    Args:
        result: EngineResult from run_ingest

    Returns:
        IngestResponse if successful, None if failed or couldn't parse
    """
    if not result.success or not result.payload:
        return None

    try:
        payload = result.payload
        body_str = payload.get("body", "{}")
        body = json.loads(body_str) if isinstance(body_str, str) else body_str

        return IngestResponse(
            job_id=body.get("job_id", ""),
            source_hash=body.get("source_hash", ""),
            duplicate=body.get("duplicate", False),
            file_count=body.get("file_count"),
            files_processed=body.get("files_processed"),
            paths=body.get("paths", {}),
            summary=body.get("summary")
        )
    except Exception:
        return None
