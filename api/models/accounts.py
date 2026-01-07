"""
Pydantic models for Accounts API.

Multi-tenant account management with S3 configuration.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AccountRequest(BaseModel):
    """Request model for creating/updating an account."""
    account_id: str = Field(..., description="Unique account identifier (e.g., '0U812')")
    name: str = Field(..., description="Display name for the account")
    description: Optional[str] = Field(None, description="Optional description")
    is_default: bool = Field(False, description="Whether this is the default account")
    # Storage Configuration
    storage_type: str = Field("s3", description="Storage type: 's3' or 'local'")
    # S3 Configuration (used when storage_type = 's3')
    s3_bucket: Optional[str] = Field(None, description="S3 bucket name for this account")
    s3_region: str = Field("us-east-1", description="AWS region for S3")
    s3_prefix: str = Field("", description="S3 key prefix (e.g., 'production/')")


class AccountResponse(BaseModel):
    """Response model for a single account."""
    account_id: str
    name: str
    description: Optional[str] = None
    is_default: bool = False
    storage_type: str = "s3"
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"
    s3_prefix: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AccountListResponse(BaseModel):
    """Response model for listing accounts."""
    accounts: List[AccountResponse]
    total: int


class AccountSyncResponse(BaseModel):
    """Response model for sync operations."""
    success: bool
    message: str
    account: Optional[AccountResponse] = None


class AccountDeleteResponse(BaseModel):
    """Response model for delete operations."""
    success: bool
    message: str


class S3ConfigResponse(BaseModel):
    """Response model for S3 configuration lookup."""
    account_id: str
    storage_type: str = "s3"
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"
    s3_prefix: str = ""
    configured: bool = False
