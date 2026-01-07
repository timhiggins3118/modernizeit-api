"""
Pydantic models for AWS credentials API.
"""

from pydantic import BaseModel
from typing import Optional


class AWSCredentialsRequest(BaseModel):
    """Request model for saving AWS credentials."""
    aws_access_key_id: str
    aws_secret_access_key: str
    region: str = "us-east-1"
    account_id: Optional[str] = None
    s3_bucket: Optional[str] = None


class AWSCredentialsResponse(BaseModel):
    """Response model for credentials operations."""
    success: bool
    message: str


class AWSCredentialsStatusResponse(BaseModel):
    """Response model for credentials status check."""
    configured: bool
    message: str
