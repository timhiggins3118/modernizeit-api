"""
S3 Helper - Validates and creates S3 buckets
"""
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class S3Helper:
    """Helper class for S3 bucket operations"""

    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str, region: str = 'us-east-1'):
        """
        Initialize S3 helper with AWS credentials

        Args:
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            region: AWS region (default: us-east-1)
        """
        self.region = region
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region
        )

    def bucket_exists(self, bucket_name: str) -> bool:
        """
        Check if S3 bucket exists

        Args:
            bucket_name: Name of the S3 bucket

        Returns:
            True if bucket exists, False otherwise
        """
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket '{bucket_name}' exists")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                logger.info(f"Bucket '{bucket_name}' does not exist")
                return False
            elif error_code == '403':
                logger.warning(f"Access denied to bucket '{bucket_name}'")
                raise Exception(f"Access denied to bucket '{bucket_name}'. Check AWS credentials permissions.")
            else:
                logger.error(f"Error checking bucket '{bucket_name}': {e}")
                raise

    def create_bucket(self, bucket_name: str) -> dict:
        """
        Create S3 bucket

        Args:
            bucket_name: Name of the S3 bucket

        Returns:
            dict with creation status
        """
        try:
            # For us-east-1, don't specify LocationConstraint
            if self.region == 'us-east-1':
                self.s3_client.create_bucket(Bucket=bucket_name)
            else:
                self.s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': self.region}
                )

            logger.info(f"Created bucket '{bucket_name}' in region '{self.region}'")
            return {
                'success': True,
                'message': f"Bucket '{bucket_name}' created successfully",
                'bucket': bucket_name,
                'region': self.region
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']

            if error_code == 'BucketAlreadyOwnedByYou':
                logger.info(f"Bucket '{bucket_name}' already owned by you")
                return {
                    'success': True,
                    'message': f"Bucket '{bucket_name}' already exists and is owned by you",
                    'bucket': bucket_name,
                    'region': self.region,
                    'already_exists': True
                }
            elif error_code == 'BucketAlreadyExists':
                logger.error(f"Bucket '{bucket_name}' already exists and is owned by someone else")
                raise Exception(f"Bucket name '{bucket_name}' is already taken by another AWS account. Choose a different name.")
            else:
                logger.error(f"Failed to create bucket '{bucket_name}': {error_message}")
                raise Exception(f"Failed to create bucket: {error_message}")

    def validate_and_create_bucket(self, bucket_name: str) -> dict:
        """
        Validate bucket exists, create if it doesn't

        Args:
            bucket_name: Name of the S3 bucket

        Returns:
            dict with validation/creation status
        """
        # Check if bucket exists
        if self.bucket_exists(bucket_name):
            return {
                'success': True,
                'exists': True,
                'created': False,
                'message': f"Bucket '{bucket_name}' already exists",
                'bucket': bucket_name,
                'region': self.region
            }

        # Create bucket if it doesn't exist
        result = self.create_bucket(bucket_name)
        return {
            'success': result['success'],
            'exists': False,
            'created': True,
            'message': result['message'],
            'bucket': bucket_name,
            'region': self.region
        }


    def list_buckets(self) -> list:
        """
        List all S3 buckets

        Returns:
            list of bucket dicts with name and creation_date
        """
        try:
            response = self.s3_client.list_buckets()
            buckets = []
            for bucket in response.get('Buckets', []):
                buckets.append({
                    'name': bucket['Name'],
                    'creation_date': bucket['CreationDate'].isoformat()
                })
            logger.info(f"Found {len(buckets)} buckets")
            return buckets
        except ClientError as e:
            logger.error(f"Failed to list buckets: {e}")
            raise Exception(f"Failed to list buckets: {e.response['Error']['Message']}")

    def list_files(self, bucket_name: str, prefix: str = '', max_keys: int = 1000) -> dict:
        """
        List files in S3 bucket

        Args:
            bucket_name: Name of the S3 bucket
            prefix: Filter by prefix (folder path)
            max_keys: Maximum number of objects to return

        Returns:
            dict with files and folders
        """
        try:
            params = {
                'Bucket': bucket_name,
                'MaxKeys': max_keys
            }
            if prefix:
                params['Prefix'] = prefix
                params['Delimiter'] = '/'

            response = self.s3_client.list_objects_v2(**params)

            files = []
            folders = []

            # Get files
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'].isoformat(),
                    'storage_class': obj.get('StorageClass', 'STANDARD')
                })

            # Get folders (common prefixes)
            for prefix_obj in response.get('CommonPrefixes', []):
                folders.append({
                    'prefix': prefix_obj['Prefix']
                })

            logger.info(f"Listed {len(files)} files and {len(folders)} folders in bucket '{bucket_name}' with prefix '{prefix}'")

            return {
                'bucket': bucket_name,
                'prefix': prefix,
                'files': files,
                'folders': folders,
                'is_truncated': response.get('IsTruncated', False),
                'total_files': len(files),
                'total_folders': len(folders)
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                raise Exception(f"Bucket '{bucket_name}' does not exist")
            else:
                logger.error(f"Failed to list files in bucket '{bucket_name}': {e}")
                raise Exception(f"Failed to list files: {e.response['Error']['Message']}")

    def delete_file(self, bucket_name: str, key: str) -> dict:
        """
        Delete a single file from S3 bucket

        Args:
            bucket_name: Name of the S3 bucket
            key: Object key to delete

        Returns:
            dict with deletion status
        """
        try:
            self.s3_client.delete_object(Bucket=bucket_name, Key=key)
            logger.info(f"Deleted file '{key}' from bucket '{bucket_name}'")
            return {
                'success': True,
                'message': f"File '{key}' deleted successfully",
                'bucket': bucket_name,
                'key': key
            }
        except ClientError as e:
            logger.error(f"Failed to delete file '{key}' from bucket '{bucket_name}': {e}")
            raise Exception(f"Failed to delete file: {e.response['Error']['Message']}")

    def delete_files_by_prefix(self, bucket_name: str, prefix: str) -> dict:
        """
        Delete all files with a given prefix (folder)

        Args:
            bucket_name: Name of the S3 bucket
            prefix: Prefix to delete (folder path)

        Returns:
            dict with deletion status and count
        """
        try:
            # List all objects with prefix
            response = self.s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

            objects_to_delete = response.get('Contents', [])
            if not objects_to_delete:
                return {
                    'success': True,
                    'message': f"No files found with prefix '{prefix}'",
                    'bucket': bucket_name,
                    'prefix': prefix,
                    'deleted_count': 0
                }

            # Delete objects in batches of 1000
            delete_keys = [{'Key': obj['Key']} for obj in objects_to_delete]

            if delete_keys:
                self.s3_client.delete_objects(
                    Bucket=bucket_name,
                    Delete={'Objects': delete_keys}
                )

            logger.info(f"Deleted {len(delete_keys)} files with prefix '{prefix}' from bucket '{bucket_name}'")

            return {
                'success': True,
                'message': f"Deleted {len(delete_keys)} files with prefix '{prefix}'",
                'bucket': bucket_name,
                'prefix': prefix,
                'deleted_count': len(delete_keys)
            }
        except ClientError as e:
            logger.error(f"Failed to delete files with prefix '{prefix}' from bucket '{bucket_name}': {e}")
            raise Exception(f"Failed to delete files: {e.response['Error']['Message']}")

    def upload_folder(self, local_folder: str, bucket_name: str, s3_prefix: str = '') -> dict:
        """
        Upload entire local folder to S3 bucket

        Args:
            local_folder: Local filesystem path to folder
            bucket_name: S3 bucket name
            s3_prefix: Optional S3 key prefix (e.g., 'production/')

        Returns:
            dict with upload status and file count
        """
        import os
        from pathlib import Path

        try:
            local_path = Path(local_folder)
            if not local_path.exists():
                raise Exception(f"Local folder does not exist: {local_folder}")

            uploaded_count = 0

            # Walk through all files in the folder
            for root, dirs, files in os.walk(local_path):
                for file in files:
                    local_file = Path(root) / file
                    # Get relative path from local_folder
                    relative_path = local_file.relative_to(local_path)
                    # Build S3 key
                    s3_key = str(Path(s3_prefix) / relative_path) if s3_prefix else str(relative_path)
                    # Normalize path separators for S3 (always use /)
                    s3_key = s3_key.replace('\\', '/')

                    # Upload file
                    self.s3_client.upload_file(
                        str(local_file),
                        bucket_name,
                        s3_key
                    )
                    uploaded_count += 1
                    logger.debug(f"Uploaded: {local_file} -> s3://{bucket_name}/{s3_key}")

            logger.info(f"Uploaded {uploaded_count} files from '{local_folder}' to s3://{bucket_name}/{s3_prefix}")

            return {
                'success': True,
                'message': f"Uploaded {uploaded_count} files to S3",
                'bucket': bucket_name,
                'prefix': s3_prefix,
                'files_uploaded': uploaded_count
            }
        except ClientError as e:
            logger.error(f"Failed to upload folder '{local_folder}' to S3: {e}")
            raise Exception(f"Failed to upload to S3: {e.response['Error']['Message']}")
        except Exception as e:
            logger.error(f"Failed to upload folder '{local_folder}' to S3: {e}")
            raise

    def delete_bucket(self, bucket_name: str, force: bool = False) -> dict:
        """
        Delete S3 bucket

        Args:
            bucket_name: Name of the S3 bucket
            force: If True, delete all objects first before deleting bucket

        Returns:
            dict with deletion status
        """
        try:
            if force:
                # Delete all objects first
                logger.info(f"Force deleting bucket '{bucket_name}' - removing all objects first")

                # List and delete all objects
                paginator = self.s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=bucket_name)

                delete_count = 0
                for page in pages:
                    objects = page.get('Contents', [])
                    if objects:
                        delete_keys = [{'Key': obj['Key']} for obj in objects]
                        self.s3_client.delete_objects(
                            Bucket=bucket_name,
                            Delete={'Objects': delete_keys}
                        )
                        delete_count += len(delete_keys)

                logger.info(f"Deleted {delete_count} objects from bucket '{bucket_name}'")

            # Delete the bucket
            self.s3_client.delete_bucket(Bucket=bucket_name)
            logger.info(f"Deleted bucket '{bucket_name}'")

            return {
                'success': True,
                'message': f"Bucket '{bucket_name}' deleted successfully",
                'bucket': bucket_name,
                'objects_deleted': delete_count if force else 0
            }
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                raise Exception(f"Bucket '{bucket_name}' does not exist")
            elif error_code == 'BucketNotEmpty':
                raise Exception(f"Bucket '{bucket_name}' is not empty. Use force=true to delete all objects first.")
            else:
                logger.error(f"Failed to delete bucket '{bucket_name}': {e}")
                raise Exception(f"Failed to delete bucket: {e.response['Error']['Message']}")


def get_aws_credentials_from_db(db_path: str) -> dict:
    """
    Get AWS credentials from SQLite database

    Args:
        db_path: Path to SQLite database

    Returns:
        dict with AWS credentials or None if not found
    """
    import sqlite3

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get AWS credentials from database
        cursor.execute("""
            SELECT aws_access_key_id, aws_secret_access_key, region
            FROM aws_credentials
            ORDER BY updated_at DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'aws_access_key_id': row[0],
                'aws_secret_access_key': row[1],
                'region': row[2] or 'us-east-1'
            }

        return None
    except Exception as e:
        logger.error(f"Failed to get AWS credentials from database: {e}")
        return None
