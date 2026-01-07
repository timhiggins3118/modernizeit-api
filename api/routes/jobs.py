"""
Jobs listing API routes.

Provides endpoints for listing and querying job records.
"""

import json
from typing import Optional, List
from fastapi import APIRouter, Query
from pydantic import BaseModel

from migrate_dynamodb.dynamodb_jobs import list_jobs, JobRecord


router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobResponse(BaseModel):
    """Response model for a job record."""
    job_id: str
    flow_type: str
    status: str
    created_at: str
    updated_at: str
    account_id: Optional[str] = None
    application_name: Optional[str] = None


class JobListResponse(BaseModel):
    """Response model for job list."""
    jobs: List[JobResponse]
    total: int


def _job_to_response(record: JobRecord) -> JobResponse:
    """Convert a JobRecord to a JobResponse."""
    # Extract account_id and application_name from input_json
    account_id = None
    application_name = None
    try:
        input_data = json.loads(record.input_json)
        account_id = input_data.get('scout_account_id')
        application_name = input_data.get('application_name')
    except json.JSONDecodeError:
        pass

    return JobResponse(
        job_id=record.job_id,
        flow_type=record.flow_type,
        status=record.status,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
        account_id=account_id,
        application_name=application_name,
    )


@router.get("/list", response_model=JobListResponse)
async def get_jobs(
    account_id: Optional[str] = Query(default=None, description="Filter by account ID"),
    application_name: Optional[str] = Query(default=None, description="Filter by application name"),
    flow_type: Optional[str] = Query(default=None, description="Filter by flow type"),
    status: Optional[str] = Query(default="completed", description="Filter by status"),
    limit: int = Query(default=100, ge=1, le=500, description="Maximum number of jobs to return"),
) -> JobListResponse:
    """
    List jobs with optional filters.

    Returns jobs sorted by creation date (newest first).
    """
    records = list_jobs(
        account_id=account_id,
        application_name=application_name,
        flow_type=flow_type,
        status=status,
        limit=limit,
    )

    jobs = [_job_to_response(r) for r in records]

    return JobListResponse(jobs=jobs, total=len(jobs))


@router.get("/by-app/{account_id}/{application_name}", response_model=JobListResponse)
async def get_jobs_by_app(
    account_id: str,
    application_name: str,
    status: Optional[str] = Query(default="completed", description="Filter by status"),
) -> JobListResponse:
    """
    Get all jobs for a specific account and application.

    Groups jobs by flow_type, returning the most recent job for each type.
    """
    records = list_jobs(
        account_id=account_id,
        application_name=application_name,
        status=status,
        limit=500,
    )

    # Group by flow_type, keep only the most recent
    latest_by_type = {}
    for record in records:
        if record.flow_type not in latest_by_type:
            latest_by_type[record.flow_type] = record

    jobs = [_job_to_response(r) for r in latest_by_type.values()]

    return JobListResponse(jobs=jobs, total=len(jobs))
