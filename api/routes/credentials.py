"""
AWS credentials API routes.

POST only - no GET for security.
"""

from fastapi import APIRouter, HTTPException

from api.models.credentials import AWSCredentialsRequest, AWSCredentialsResponse, AWSCredentialsStatusResponse
from db import AWSCredentials, save_credentials, get_credentials, init_db

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.post("", response_model=AWSCredentialsResponse)
async def save_aws_credentials(request: AWSCredentialsRequest) -> AWSCredentialsResponse:
    """
    Save AWS credentials to database.

    POST /credentials

    Only ONE set of credentials stored - overwrites existing.
    No GET endpoint - credentials are write-only for security.
    """
    try:
        # Ensure db is initialized
        init_db()

        creds = AWSCredentials(
            aws_access_key_id=request.aws_access_key_id,
            aws_secret_access_key=request.aws_secret_access_key,
            region=request.region,
            account_id=request.account_id,
            s3_bucket=request.s3_bucket
        )
        save_credentials(creds)

        return AWSCredentialsResponse(
            success=True,
            message="AWS credentials saved"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=AWSCredentialsStatusResponse)
async def check_credentials_status() -> AWSCredentialsStatusResponse:
    """
    Check if AWS credentials are configured.

    GET /credentials/status

    Returns whether credentials exist - no sensitive data returned.
    """
    try:
        init_db()
        creds = get_credentials()

        if creds is None:
            return AWSCredentialsStatusResponse(
                configured=False,
                message="AWS credentials not configured"
            )

        return AWSCredentialsStatusResponse(
            configured=True,
            message="AWS credentials configured"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
