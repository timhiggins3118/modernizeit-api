"""
Pydantic models for saved flows API.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class SaveFlowRequest(BaseModel):
    """Request model for saving a flow."""
    name: str = Field(..., description="User-defined name for the flow")
    account_id: str = Field(..., description="Scout account ID")
    application_name: str = Field(..., description="Application name")
    flow_data: Dict[str, Any] = Field(..., description="ReactFlow state (nodes, edges)")
    job_mappings: Optional[Dict[str, str]] = Field(default=None, description="Mapping of node IDs to job IDs")


class SaveFlowResponse(BaseModel):
    """Response model for save flow operation."""
    flow_id: str = Field(..., description="Unique flow ID")
    name: str
    saved_at: datetime


class FlowListItem(BaseModel):
    """Summary information for a saved flow in list view."""
    id: str
    name: str
    account_id: str
    application_name: str
    created_at: datetime
    updated_at: datetime
    status: str = Field(..., description="Overall status: completed, running, failed, or not_run")
    node_count: int = Field(default=0, description="Number of nodes in the flow")


class FlowListResponse(BaseModel):
    """Response model for list flows operation."""
    flows: List[FlowListItem]
    total: int


class FlowDetail(BaseModel):
    """Detailed flow information including all data."""
    id: str
    name: str
    account_id: str
    application_name: str
    flow_data: Dict[str, Any]
    job_mappings: Dict[str, str]
    job_statuses: Dict[str, str] = Field(default_factory=dict, description="Current status of each job")
    created_at: datetime
    updated_at: datetime


class DeleteFlowResponse(BaseModel):
    """Response model for delete flow operation."""
    deleted: bool
    flow_id: str


class UpdateFlowNameRequest(BaseModel):
    """Request model for updating a flow's name."""
    name: str = Field(..., description="New name for the flow")


class UpdateFlowNameResponse(BaseModel):
    """Response model for update flow name operation."""
    updated: bool
    flow_id: str
    new_name: str
