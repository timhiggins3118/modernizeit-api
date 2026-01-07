"""
Storage Uploader Utility

Helper to upload workflow output to S3 when account uses S3 storage.
"""

import logging
from pathlib import Path
from typing import Optional

from config.settings import settings
from migrate_dynamodb.dynamodb_accounts import get_account_s3_config
from utils.s3_helper import S3Helper, get_aws_credentials_from_db

logger = logging.getLogger(__name__)


def upload_to_s3_if_needed(
    scout_account_id: str,
    application_name: str,
    workflow_folder: str
) -> Optional[dict]:
    """
    Upload workflow output to S3 if account uses S3 storage.

    Args:
        scout_account_id: Account ID
        application_name: Application name
        workflow_folder: Workflow folder name (e.g., 'code_analysis', 'discovery')

    Returns:
        Upload result dict if uploaded, None if skipped

    Example:
        upload_to_s3_if_needed('0U812', 'TestApp', 'discovery')
        # Uploads: ./modernizeit_output/code-transformation-v2/0U812/TestApp/discovery/
        # To: s3://bucket/0U812/TestApp/discovery/
    """
    try:
        # Get account storage config
        account_config = get_account_s3_config(scout_account_id)

        if not account_config:
            logger.debug(f"Account '{scout_account_id}' not found, skipping S3 upload")
            return None

        if account_config.get("storage_type") != "s3":
            logger.debug(f"Account '{scout_account_id}' uses local storage, skipping S3 upload")
            return None

        # Get AWS credentials
        db_path = Path(__file__).parent.parent / "data" / "jobs.db"
        aws_creds = get_aws_credentials_from_db(str(db_path))

        if not aws_creds:
            logger.warning("AWS credentials not configured, skipping S3 upload")
            return None

        # Create S3 helper
        s3_helper = S3Helper(
            aws_access_key_id=aws_creds['aws_access_key_id'],
            aws_secret_access_key=aws_creds['aws_secret_access_key'],
            region=account_config.get('s3_region', 'us-east-1')
        )

        # Local path: {base_local_path}/code-transformation-v2/{account}/{app}/{workflow}/
        local_folder = (
            settings.base_local_path /
            "code-transformation-v2" /
            scout_account_id /
            application_name /
            workflow_folder
        )

        if not local_folder.exists():
            logger.warning(f"Local folder does not exist: {local_folder}")
            return None

        # S3 prefix: {s3_prefix}{account}/{app}/{workflow}/
        s3_prefix = account_config.get('s3_prefix', '')
        s3_key_prefix = f"{s3_prefix}{scout_account_id}/{application_name}/{workflow_folder}/"

        logger.info(f"[S3 Upload] Uploading {local_folder} to s3://{account_config['s3_bucket']}/{s3_key_prefix}")

        # Upload folder to S3
        result = s3_helper.upload_folder(
            str(local_folder),
            account_config['s3_bucket'],
            s3_key_prefix
        )

        logger.info(f"[S3 Upload] Success! Uploaded {result['files_uploaded']} files")
        return result

    except Exception as e:
        # Log but don't fail - local files are already saved
        logger.error(f"[S3 Upload] Failed to upload to S3: {e}")
        return None
