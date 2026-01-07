"""
DynamoDB AWS Credentials Module - Complete Implementation

Stores AWS credentials with tenant isolation in DynamoDB.
Replaces db/aws_credentials.py SQLite with DynamoDB single-table design.

SECURITY: Uses DynamoDB encryption at rest. Consider AWS Secrets Manager for production.
"""

import os
import boto3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from botocore.exceptions import ClientError


@dataclass
class AWSCredentials:
    """AWS credentials record."""
    aws_access_key_id: str
    aws_secret_access_key: str
    region: str = "us-east-1"
    account_id: Optional[str] = None
    s3_bucket: Optional[str] = None
    profile_name: str = "default"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DynamoDBCredentialsProvider:
    """
    DynamoDB provider for AWS credentials with tenant isolation.

    Storage Pattern:
    - PK: TENANT#{tenant_id}
    - SK: CRED#{profile_name}
    - entity_type: credential
    """

    def __init__(self, table_name: str = None, region: str = None):
        self.table_name = table_name or os.getenv("DYNAMODB_TABLE_NAME", "modernizeit-dev-data")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.table = self.dynamodb.Table(self.table_name)

    def _make_pk(self, tenant_id: str) -> str:
        """Create partition key."""
        return f"TENANT#{tenant_id}"

    def _make_sk(self, profile_name: str) -> str:
        """Create sort key."""
        return f"CRED#{profile_name}"

    def save_credentials(self, creds: AWSCredentials, tenant_id: str = None) -> None:
        """
        Save AWS credentials for a tenant.

        Args:
            creds: AWS credentials to save
            tenant_id: Tenant ID (defaults to creds.account_id or env ACCOUNT_ID)
        """
        if not tenant_id:
            tenant_id = creds.account_id or os.getenv("ACCOUNT_ID", "341")

        pk = self._make_pk(tenant_id)
        sk = self._make_sk(creds.profile_name)

        now = datetime.utcnow()
        if not creds.created_at:
            creds.created_at = now
        creds.updated_at = now

        item = {
            'PK': pk,
            'SK': sk,
            'entity_type': 'credential',
            'tenant_id': tenant_id,
            'profile_name': creds.profile_name,
            'aws_access_key_id': creds.aws_access_key_id,
            'aws_secret_access_key': creds.aws_secret_access_key,  # Encrypted at rest
            'region': creds.region,
            'account_id': creds.account_id,
            's3_bucket': creds.s3_bucket,
            'created_at': creds.created_at.isoformat() if isinstance(creds.created_at, datetime) else creds.created_at,
            'updated_at': creds.updated_at.isoformat() if isinstance(creds.updated_at, datetime) else creds.updated_at,
        }

        try:
            self.table.put_item(Item=item)
        except ClientError as e:
            raise Exception(f"Failed to save credentials: {e}")

    def get_credentials(self, tenant_id: str = None, profile_name: str = "default") -> Optional[AWSCredentials]:
        """
        Get AWS credentials for a tenant.

        Args:
            tenant_id: Tenant ID (defaults to env ACCOUNT_ID)
            profile_name: Profile name (default: "default")

        Returns:
            AWSCredentials if found, None otherwise
        """
        if not tenant_id:
            tenant_id = os.getenv("ACCOUNT_ID", "341")

        pk = self._make_pk(tenant_id)
        sk = self._make_sk(profile_name)

        try:
            response = self.table.get_item(Key={'PK': pk, 'SK': sk})

            if 'Item' not in response:
                return None

            item = response['Item']

            return AWSCredentials(
                aws_access_key_id=item['aws_access_key_id'],
                aws_secret_access_key=item['aws_secret_access_key'],
                region=item.get('region', 'us-east-1'),
                account_id=item.get('account_id'),
                s3_bucket=item.get('s3_bucket'),
                profile_name=item.get('profile_name', 'default'),
                created_at=datetime.fromisoformat(item['created_at']) if item.get('created_at') else None,
                updated_at=datetime.fromisoformat(item['updated_at']) if item.get('updated_at') else None,
            )

        except ClientError as e:
            raise Exception(f"Failed to get credentials: {e}")

    def delete_credentials(self, tenant_id: str = None, profile_name: str = "default") -> bool:
        """
        Delete AWS credentials for a tenant.

        Args:
            tenant_id: Tenant ID
            profile_name: Profile name

        Returns:
            True if deleted, False if not found
        """
        if not tenant_id:
            tenant_id = os.getenv("ACCOUNT_ID", "341")

        pk = self._make_pk(tenant_id)
        sk = self._make_sk(profile_name)

        try:
            response = self.table.delete_item(
                Key={'PK': pk, 'SK': sk},
                ReturnValues='ALL_OLD'
            )
            return 'Attributes' in response
        except ClientError as e:
            raise Exception(f"Failed to delete credentials: {e}")


# Global provider instance
_provider = None


def _get_provider() -> DynamoDBCredentialsProvider:
    """Get or create the global provider instance."""
    global _provider
    if _provider is None:
        _provider = DynamoDBCredentialsProvider()
    return _provider


# Compatibility functions (match db/aws_credentials.py API)
def init_aws_credentials_table() -> None:
    """Initialize credentials table (DynamoDB table already exists)."""
    pass  # Table created externally


def save_credentials(creds: AWSCredentials, tenant_id: str = None) -> None:
    """Save AWS credentials (compatibility function)."""
    _get_provider().save_credentials(creds, tenant_id)


def get_credentials(tenant_id: str = None, profile_name: str = "default") -> Optional[AWSCredentials]:
    """Get AWS credentials (compatibility function)."""
    return _get_provider().get_credentials(tenant_id, profile_name)


def delete_credentials(tenant_id: str = None, profile_name: str = "default") -> bool:
    """Delete AWS credentials (compatibility function)."""
    return _get_provider().delete_credentials(tenant_id, profile_name)
