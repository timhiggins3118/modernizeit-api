"""
Saved flows API routes.

Provides endpoints for saving, loading, listing, and deleting workflow configurations.
"""

import json
import hashlib
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from api.models.flows import (
    SaveFlowRequest,
    SaveFlowResponse,
    FlowListItem,
    FlowListResponse,
    FlowDetail,
    DeleteFlowResponse,
    UpdateFlowNameRequest,
    UpdateFlowNameResponse,
)
from migrate_dynamodb.dynamodb_flows import (
    SavedFlowRecord,
    save_flow,
    get_flow,
    list_flows,
    delete_flow,
    update_flow_name,
)
from migrate_dynamodb.dynamodb_jobs import get_job


router = APIRouter(prefix="/flows", tags=["flows"])


def _generate_flow_id(name: str, account_id: str, application_name: str) -> str:
    """Generate a unique flow ID based on name and context."""
    timestamp = datetime.now().isoformat()
    content = f"{name}_{account_id}_{application_name}_{timestamp}"
    hash_suffix = hashlib.sha256(content.encode()).hexdigest()[:8]
    return f"flow_{hash_suffix}"


def _determine_flow_status(job_mappings: dict) -> str:
    """
    Determine overall flow status based on job statuses.

    Returns: "completed", "running", "failed", or "not_run"
    """
    if not job_mappings:
        return "not_run"

    statuses = []
    for job_id in job_mappings.values():
        if job_id:
            job = get_job(job_id)
            if job:
                statuses.append(job.status)

    if not statuses:
        return "not_run"

    if any(s == "failed" for s in statuses):
        return "failed"
    if any(s == "running" for s in statuses):
        return "running"
    if all(s == "completed" for s in statuses):
        return "completed"

    return "not_run"


@router.post("/save", response_model=SaveFlowResponse)
async def save_workflow_flow(request: SaveFlowRequest) -> SaveFlowResponse:
    """
    Save a workflow flow configuration.

    Stores the complete ReactFlow state including nodes, edges, and job mappings.
    """
    # Generate unique flow ID
    flow_id = _generate_flow_id(request.name, request.account_id, request.application_name)

    # Create record
    now = datetime.now()
    record = SavedFlowRecord(
        id=flow_id,
        name=request.name,
        account_id=request.account_id,
        application_name=request.application_name,
        flow_data=json.dumps(request.flow_data),
        job_mappings=json.dumps(request.job_mappings or {}),
        created_at=now,
        updated_at=now,
    )

    # Save to database
    save_flow(record)

    return SaveFlowResponse(
        flow_id=flow_id,
        name=request.name,
        saved_at=now,
    )


@router.get("/list", response_model=FlowListResponse)
async def list_saved_flows(
    account_id: Optional[str] = Query(default=None, description="Filter by account ID")
) -> FlowListResponse:
    """
    List all saved flows, optionally filtered by account.

    Returns flows sorted by update time (newest first).
    """
    records = list_flows(account_id=account_id)

    flows = []
    for record in records:
        # Parse job mappings to determine status
        job_mappings = json.loads(record.job_mappings) if record.job_mappings else {}
        status = _determine_flow_status(job_mappings)

        # Count nodes
        flow_data = json.loads(record.flow_data)
        node_count = len(flow_data.get("nodes", []))

        flows.append(
            FlowListItem(
                id=record.id,
                name=record.name,
                account_id=record.account_id,
                application_name=record.application_name,
                created_at=record.created_at,
                updated_at=record.updated_at,
                status=status,
                node_count=node_count,
            )
        )

    return FlowListResponse(flows=flows, total=len(flows))


@router.get("/{flow_id}", response_model=FlowDetail)
async def get_saved_flow(flow_id: str) -> FlowDetail:
    """
    Get a saved flow by ID.

    Returns complete flow data including job statuses.
    """
    record = get_flow(flow_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Flow {flow_id} not found")

    # Parse stored data
    flow_data = json.loads(record.flow_data)
    job_mappings = json.loads(record.job_mappings) if record.job_mappings else {}

    # Fetch current job statuses
    job_statuses = {}
    for node_id, job_id in job_mappings.items():
        if job_id:
            job = get_job(job_id)
            if job:
                job_statuses[node_id] = job.status
            else:
                job_statuses[node_id] = "not_found"

    return FlowDetail(
        id=record.id,
        name=record.name,
        account_id=record.account_id,
        application_name=record.application_name,
        flow_data=flow_data,
        job_mappings=job_mappings,
        job_statuses=job_statuses,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.delete("/{flow_id}", response_model=DeleteFlowResponse)
async def delete_saved_flow(flow_id: str) -> DeleteFlowResponse:
    """
    Delete a saved flow by ID.
    """
    deleted = delete_flow(flow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Flow {flow_id} not found")

    return DeleteFlowResponse(deleted=True, flow_id=flow_id)


@router.patch("/{flow_id}/name", response_model=UpdateFlowNameResponse)
async def update_saved_flow_name(flow_id: str, request: UpdateFlowNameRequest) -> UpdateFlowNameResponse:
    """
    Update a flow's name.
    """
    updated = update_flow_name(flow_id, request.name)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Flow {flow_id} not found")

    return UpdateFlowNameResponse(
        updated=True,
        flow_id=flow_id,
        new_name=request.name,
    )
