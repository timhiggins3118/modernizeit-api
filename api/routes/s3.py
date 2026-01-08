"""
S3 Routes - Bucket validation and creation
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import logging

from utils.s3_helper import S3Helper
from db.dynamodb import get_credentials as get_aws_credentials_from_dynamodb

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/s3", tags=["s3"])


class ValidateBucketRequest(BaseModel):
    """Request model for bucket validation"""
    bucket_name: str
    region: str = 'us-east-1'


class ValidateBucketResponse(BaseModel):
    """Response model for bucket validation"""
    success: bool
    exists: bool
    created: bool
    message: str
    bucket: str
    region: str


@router.post("/validate-bucket", response_model=ValidateBucketResponse)
async def validate_bucket(request: ValidateBucketRequest):
    """
    Validate S3 bucket exists, create if it doesn't

    This endpoint:
    1. Checks if AWS credentials exist in database
    2. Validates if bucket exists
    3. Creates bucket if it doesn't exist
    4. Returns success/failure status

    Args:
        request: ValidateBucketRequest with bucket_name and region

    Returns:
        ValidateBucketResponse with validation/creation status

    Raises:
        HTTPException: If AWS credentials not found or bucket validation fails
    """
    try:
        # Get AWS credentials from DynamoDB
        logger.info("Getting AWS credentials from DynamoDB")
        creds = get_aws_credentials_from_dynamodb()

        if not creds:
            raise HTTPException(
                status_code=400,
                detail="AWS credentials not configured. Please configure AWS credentials in Settings first."
            )

        # Validate bucket name
        bucket_name = request.bucket_name.strip()
        if not bucket_name:
            raise HTTPException(
                status_code=400,
                detail="Bucket name is required"
            )

        # Initialize S3 helper
        logger.info(f"Validating bucket '{bucket_name}' in region '{request.region}'")
        s3_helper = S3Helper(
            aws_access_key_id=creds['aws_access_key_id'],
            aws_secret_access_key=creds['aws_secret_access_key'],
            region=request.region
        )

        # Validate and create bucket if needed
        result = s3_helper.validate_and_create_bucket(bucket_name)

        logger.info(f"Bucket validation result: {result}")
        return ValidateBucketResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate bucket: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/credentials-configured")
async def check_credentials_configured():
    """
    Check if AWS credentials are configured

    Returns:
        dict with configured status
    """
    try:
        creds = get_aws_credentials_from_dynamodb()

        return {
            'configured': creds is not None,
            'region': creds['region'] if creds else None
        }
    except Exception as e:
        logger.error(f"Failed to check credentials: {e}")
        return {
            'configured': False,
            'region': None
        }


@router.get("/list-buckets")
async def list_buckets():
    """
    List all S3 buckets

    Returns:
        list of buckets

    Raises:
        HTTPException: If AWS credentials not found or listing fails
    """
    try:
        creds = get_aws_credentials_from_dynamodb()

        if not creds:
            raise HTTPException(
                status_code=400,
                detail="AWS credentials not configured. Please configure AWS credentials in Settings first."
            )

        s3_helper = S3Helper(
            aws_access_key_id=creds['aws_access_key_id'],
            aws_secret_access_key=creds['aws_secret_access_key'],
            region=creds['region']
        )

        buckets = s3_helper.list_buckets()
        return {
            'success': True,
            'buckets': buckets,
            'total': len(buckets)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list buckets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ListFilesRequest(BaseModel):
    """Request model for listing files"""
    bucket_name: str
    prefix: str = ''
    max_keys: int = 1000


@router.post("/list-files")
async def list_files(request: ListFilesRequest):
    """
    List files in S3 bucket

    Args:
        request: ListFilesRequest with bucket_name, prefix, max_keys

    Returns:
        dict with files and folders

    Raises:
        HTTPException: If AWS credentials not found or listing fails
    """
    try:
        creds = get_aws_credentials_from_dynamodb()

        if not creds:
            raise HTTPException(
                status_code=400,
                detail="AWS credentials not configured. Please configure AWS credentials in Settings first."
            )

        s3_helper = S3Helper(
            aws_access_key_id=creds['aws_access_key_id'],
            aws_secret_access_key=creds['aws_secret_access_key'],
            region=creds['region']
        )

        result = s3_helper.list_files(request.bucket_name, request.prefix, request.max_keys)
        return {
            'success': True,
            **result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class DeleteFileRequest(BaseModel):
    """Request model for deleting a file"""
    bucket_name: str
    key: str


@router.delete("/delete-file")
async def delete_file(request: DeleteFileRequest):
    """
    Delete a single file from S3 bucket

    Args:
        request: DeleteFileRequest with bucket_name and key

    Returns:
        dict with deletion status

    Raises:
        HTTPException: If AWS credentials not found or deletion fails
    """
    try:
        creds = get_aws_credentials_from_dynamodb()

        if not creds:
            raise HTTPException(
                status_code=400,
                detail="AWS credentials not configured. Please configure AWS credentials in Settings first."
            )

        s3_helper = S3Helper(
            aws_access_key_id=creds['aws_access_key_id'],
            aws_secret_access_key=creds['aws_secret_access_key'],
            region=creds['region']
        )

        result = s3_helper.delete_file(request.bucket_name, request.key)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class DeleteFolderRequest(BaseModel):
    """Request model for deleting a folder"""
    bucket_name: str
    prefix: str


@router.delete("/delete-folder")
async def delete_folder(request: DeleteFolderRequest):
    """
    Delete all files with a given prefix (folder)

    Args:
        request: DeleteFolderRequest with bucket_name and prefix

    Returns:
        dict with deletion status and count

    Raises:
        HTTPException: If AWS credentials not found or deletion fails
    """
    try:
        creds = get_aws_credentials_from_dynamodb()

        if not creds:
            raise HTTPException(
                status_code=400,
                detail="AWS credentials not configured. Please configure AWS credentials in Settings first."
            )

        s3_helper = S3Helper(
            aws_access_key_id=creds['aws_access_key_id'],
            aws_secret_access_key=creds['aws_secret_access_key'],
            region=creds['region']
        )

        result = s3_helper.delete_files_by_prefix(request.bucket_name, request.prefix)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class DeleteBucketRequest(BaseModel):
    """Request model for deleting a bucket"""
    bucket_name: str
    force: bool = False


@router.delete("/delete-bucket")
async def delete_bucket(request: DeleteBucketRequest):
    """
    Delete S3 bucket

    Args:
        request: DeleteBucketRequest with bucket_name and force flag

    Returns:
        dict with deletion status

    Raises:
        HTTPException: If AWS credentials not found or deletion fails
    """
    try:
        creds = get_aws_credentials_from_dynamodb()

        if not creds:
            raise HTTPException(
                status_code=400,
                detail="AWS credentials not configured. Please configure AWS credentials in Settings first."
            )

        s3_helper = S3Helper(
            aws_access_key_id=creds['aws_access_key_id'],
            aws_secret_access_key=creds['aws_secret_access_key'],
            region=creds['region']
        )

        result = s3_helper.delete_bucket(request.bucket_name, request.force)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete bucket: {e}")
        raise HTTPException(status_code=500, detail=str(e))
