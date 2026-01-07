"""
DynamoDB Accounts Module - Complete Implementation

Replaces db/accounts.py SQLite implementation with DynamoDB.
Stores per-tenant configuration (S3 buckets, regions, etc.).

Table: modernizeit-dev-data
  PK: TENANT#{account_id}
  SK: ACCOUNT#{account_id}

Created: January 6, 2026
"""

import boto3
import os
from boto3.dynamodb.conditions import Key, Attr
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List


@dataclass
class Account:
    """
    Account record with S3 configuration - matches SQLite version.

    Each tenant can have their own S3 bucket configuration.
    """
    account_id: str
    name: str
    description: Optional[str] = None
    is_default: bool = False
    # Storage Configuration
    storage_type: str = "s3"  # 's3' or 'local'
    # S3 Storage Configuration (used when storage_type = 's3')
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"
    s3_prefix: str = ""
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DynamoDBAccountsProvider:
    """
    DynamoDB implementation for account/tenant management.

    Drop-in replacement for db/accounts.py SQLite functions.

    Usage:
        provider = DynamoDBAccountsProvider()
        provider.save_account(account)
        account = provider.get_account(account_id)
    """

    def __init__(
        self,
        table_name: str = None,
        region: str = None
    ):
        """
        Initialize the DynamoDB accounts provider.

        Args:
            table_name: DynamoDB table name
            region: AWS region
        """
        self.table_name = table_name or os.getenv("DYNAMODB_TABLE_NAME", "modernizeit-dev-data")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self._dynamodb = None

    @property
    def dynamodb(self):
        """Lazy-load DynamoDB resource."""
        if self._dynamodb is None:
            self._dynamodb = boto3.resource('dynamodb', region_name=self.region)
        return self._dynamodb

    @property
    def table(self):
        """Get the DynamoDB table resource."""
        return self.dynamodb.Table(self.table_name)

    def _make_pk(self, account_id: str) -> str:
        """Create partition key: TENANT#{account_id}"""
        return f"TENANT#{account_id}"

    def _make_sk(self, account_id: str) -> str:
        """Create sort key: ACCOUNT#{account_id}"""
        return f"ACCOUNT#{account_id}"

    def init_accounts_table(self) -> None:
        """
        Initialize accounts table (compatibility function).

        For DynamoDB, table should already exist. This is a no-op.
        """
        try:
            self.table.table_status
        except Exception as e:
            print(f"[dynamodb_accounts] Warning: Table {self.table_name} may not exist: {e}")

    def save_account(self, account: Account) -> None:
        """
        Save an account record to DynamoDB.

        Args:
            account: Account object to save
        """
        pk = self._make_pk(account.account_id)
        sk = self._make_sk(account.account_id)

        now = datetime.utcnow()
        if not account.created_at:
            account.created_at = now
        account.updated_at = now

        item = {
            'PK': pk,
            'SK': sk,
            'entity_type': 'account',
            'account_id': account.account_id,
            'name': account.name,
            'is_default': account.is_default,
            'storage_type': account.storage_type,
            's3_region': account.s3_region,
            's3_prefix': account.s3_prefix,
            'created_at': account.created_at.isoformat(),
            'updated_at': account.updated_at.isoformat(),
        }

        if account.description:
            item['description'] = account.description
        if account.s3_bucket:
            item['s3_bucket'] = account.s3_bucket

        self.table.put_item(Item=item)

    def get_account(self, account_id: str) -> Optional[Account]:
        """
        Get an account by ID.

        Args:
            account_id: Account ID to look up

        Returns:
            Account object if found, None otherwise
        """
        pk = self._make_pk(account_id)
        sk = self._make_sk(account_id)

        try:
            response = self.table.get_item(
                Key={'PK': pk, 'SK': sk}
            )

            if 'Item' not in response:
                return None

            item = response['Item']
            return Account(
                account_id=item['account_id'],
                name=item['name'],
                description=item.get('description'),
                is_default=item.get('is_default', False),
                storage_type=item.get('storage_type', 's3'),
                s3_bucket=item.get('s3_bucket'),
                s3_region=item.get('s3_region', 'us-east-1'),
                s3_prefix=item.get('s3_prefix', ''),
                created_at=datetime.fromisoformat(item['created_at']) if 'created_at' in item else None,
                updated_at=datetime.fromisoformat(item['updated_at']) if 'updated_at' in item else None
            )
        except Exception as e:
            print(f"[dynamodb_accounts] Error getting account {account_id}: {e}")
            return None

    def list_accounts(self) -> List[Account]:
        """
        List all accounts.

        Returns:
            List of Account objects
        """
        results = []

        # Scan for all account entities
        scan_params = {
            'FilterExpression': Attr('entity_type').eq('account')
        }

        try:
            response = self.table.scan(**scan_params)
            items = response.get('Items', [])

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                scan_params['ExclusiveStartKey'] = response['LastEvaluatedKey']
                response = self.table.scan(**scan_params)
                items.extend(response.get('Items', []))

            for item in items:
                try:
                    account = Account(
                        account_id=item['account_id'],
                        name=item['name'],
                        description=item.get('description'),
                        is_default=item.get('is_default', False),
                        storage_type=item.get('storage_type', 's3'),
                        s3_bucket=item.get('s3_bucket'),
                        s3_region=item.get('s3_region', 'us-east-1'),
                        s3_prefix=item.get('s3_prefix', ''),
                        created_at=datetime.fromisoformat(item['created_at']) if 'created_at' in item else None,
                        updated_at=datetime.fromisoformat(item['updated_at']) if 'updated_at' in item else None
                    )
                    results.append(account)
                except Exception as e:
                    print(f"[dynamodb_accounts] Error parsing account: {e}")
                    continue

        except Exception as e:
            print(f"[dynamodb_accounts] Error listing accounts: {e}")

        return results

    def get_default_account(self) -> Optional[Account]:
        """
        Get the default account.

        Returns:
            Default Account object if found, None otherwise
        """
        accounts = self.list_accounts()
        for account in accounts:
            if account.is_default:
                return account
        return None

    def delete_account(self, account_id: str) -> bool:
        """
        Delete an account.

        Args:
            account_id: Account ID to delete

        Returns:
            True if deleted, False otherwise
        """
        pk = self._make_pk(account_id)
        sk = self._make_sk(account_id)

        try:
            self.table.delete_item(
                Key={'PK': pk, 'SK': sk}
            )
            return True
        except Exception as e:
            print(f"[dynamodb_accounts] Error deleting account {account_id}: {e}")
            return False


# ============================================================================
# Compatibility Functions (match db/accounts.py API)
# ============================================================================

_provider = None

def _get_provider() -> DynamoDBAccountsProvider:
    """Get or create singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = DynamoDBAccountsProvider()
    return _provider


def init_accounts_table() -> None:
    """Initialize accounts table (compatibility function)."""
    _get_provider().init_accounts_table()


def save_account(account: Account) -> None:
    """Save an account (compatibility function)."""
    _get_provider().save_account(account)


def get_account(account_id: str) -> Optional[Account]:
    """Get an account (compatibility function)."""
    return _get_provider().get_account(account_id)


def list_accounts() -> List[Account]:
    """List all accounts (compatibility function)."""
    return _get_provider().list_accounts()


def get_default_account() -> Optional[Account]:
    """Get default account (compatibility function)."""
    return _get_provider().get_default_account()


def delete_account(account_id: str) -> bool:
    """Delete an account (compatibility function)."""
    return _get_provider().delete_account(account_id)


def get_account_s3_config(account_id: str) -> Optional[dict]:
    """
    Get S3 configuration for an account (compatibility function).

    Args:
        account_id: The account ID

    Returns:
        Dict with storage_type, s3_bucket, s3_region, s3_prefix or None if not found
    """
    account = get_account(account_id)
    if account is None:
        return None
    return {
        "storage_type": account.storage_type,
        "s3_bucket": account.s3_bucket,
        "s3_region": account.s3_region,
        "s3_prefix": account.s3_prefix
    }
