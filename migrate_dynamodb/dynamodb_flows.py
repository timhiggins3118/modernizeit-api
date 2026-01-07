"""
DynamoDB Saved Flows Module - Complete Implementation

Stores workflow configurations with tenant isolation in DynamoDB.
Replaces db/flows.py SQLite with DynamoDB single-table design.
"""

import os
import boto3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from botocore.exceptions import ClientError


@dataclass
class SavedFlowRecord:
    """
    Saved flow record dataclass.

    Stores a complete workflow configuration including:
    - ReactFlow canvas state (nodes, edges)
    - Job IDs associated with each node
    - Account/application context
    """
    id: str
    name: str
    account_id: str
    application_name: str
    flow_data: str  # JSON string of ReactFlow state
    job_mappings: str  # JSON string of {node_id: job_id}
    created_at: datetime
    updated_at: datetime


class DynamoDBFlowsProvider:
    """
    DynamoDB provider for saved flows with tenant isolation.

    Storage Pattern:
    - PK: TENANT#{tenant_id}
    - SK: FLOW#{flow_id}
    - entity_type: flow
    """

    def __init__(self, table_name: str = None, region: str = None):
        self.table_name = table_name or os.getenv("DYNAMODB_TABLE_NAME", "modernizeit-dev-data")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.table = self.dynamodb.Table(self.table_name)

    def _make_pk(self, tenant_id: str) -> str:
        """Create partition key."""
        return f"TENANT#{tenant_id}"

    def _make_sk(self, flow_id: str) -> str:
        """Create sort key."""
        return f"FLOW#{flow_id}"

    def save_flow(self, record: SavedFlowRecord) -> None:
        """
        Save a flow record to DynamoDB.

        Args:
            record: SavedFlowRecord to save
        """
        pk = self._make_pk(record.account_id)
        sk = self._make_sk(record.id)

        item = {
            'PK': pk,
            'SK': sk,
            'entity_type': 'flow',
            'flow_id': record.id,
            'tenant_id': record.account_id,
            'name': record.name,
            'account_id': record.account_id,
            'application_name': record.application_name,
            'flow_data': record.flow_data,
            'job_mappings': record.job_mappings or '',
            'created_at': record.created_at.isoformat() if isinstance(record.created_at, datetime) else record.created_at,
            'updated_at': record.updated_at.isoformat() if isinstance(record.updated_at, datetime) else record.updated_at,
        }

        try:
            self.table.put_item(Item=item)
        except ClientError as e:
            raise Exception(f"Failed to save flow: {e}")

    def get_flow(self, flow_id: str, tenant_id: str = None) -> Optional[SavedFlowRecord]:
        """
        Get a saved flow by ID.

        Args:
            flow_id: Flow ID to retrieve
            tenant_id: Tenant ID (defaults to env ACCOUNT_ID)

        Returns:
            SavedFlowRecord if found, None otherwise
        """
        if not tenant_id:
            tenant_id = os.getenv("ACCOUNT_ID", "341")

        pk = self._make_pk(tenant_id)
        sk = self._make_sk(flow_id)

        try:
            response = self.table.get_item(Key={'PK': pk, 'SK': sk})

            if 'Item' not in response:
                return None

            item = response['Item']

            return SavedFlowRecord(
                id=item['flow_id'],
                name=item['name'],
                account_id=item['account_id'],
                application_name=item['application_name'],
                flow_data=item['flow_data'],
                job_mappings=item.get('job_mappings', ''),
                created_at=datetime.fromisoformat(item['created_at']),
                updated_at=datetime.fromisoformat(item['updated_at']),
            )

        except ClientError as e:
            raise Exception(f"Failed to get flow: {e}")

    def list_flows(
        self,
        account_id: Optional[str] = None,
        application_name: Optional[str] = None,
        limit: int = 100
    ) -> List[SavedFlowRecord]:
        """
        List saved flows for a tenant.

        Args:
            account_id: Filter by account ID (defaults to env ACCOUNT_ID)
            application_name: Filter by application name
            limit: Maximum number of flows to return

        Returns:
            List of SavedFlowRecord objects
        """
        if not account_id:
            account_id = os.getenv("ACCOUNT_ID", "341")

        pk = self._make_pk(account_id)

        try:
            # Query by partition key with sort key beginning with FLOW#
            response = self.table.query(
                KeyConditionExpression='PK = :pk AND begins_with(SK, :sk)',
                ExpressionAttributeValues={
                    ':pk': pk,
                    ':sk': 'FLOW#'
                },
                Limit=limit
            )

            flows = []
            for item in response.get('Items', []):
                flow = SavedFlowRecord(
                    id=item['flow_id'],
                    name=item['name'],
                    account_id=item['account_id'],
                    application_name=item['application_name'],
                    flow_data=item['flow_data'],
                    job_mappings=item.get('job_mappings', ''),
                    created_at=datetime.fromisoformat(item['created_at']),
                    updated_at=datetime.fromisoformat(item['updated_at']),
                )

                # Filter by application_name if specified
                if application_name and flow.application_name != application_name:
                    continue

                flows.append(flow)

            return flows

        except ClientError as e:
            raise Exception(f"Failed to list flows: {e}")

    def delete_flow(self, flow_id: str, tenant_id: str = None) -> bool:
        """
        Delete a saved flow.

        Args:
            flow_id: Flow ID to delete
            tenant_id: Tenant ID (defaults to env ACCOUNT_ID)

        Returns:
            True if deleted, False if not found
        """
        if not tenant_id:
            tenant_id = os.getenv("ACCOUNT_ID", "341")

        pk = self._make_pk(tenant_id)
        sk = self._make_sk(flow_id)

        try:
            response = self.table.delete_item(
                Key={'PK': pk, 'SK': sk},
                ReturnValues='ALL_OLD'
            )
            return 'Attributes' in response
        except ClientError as e:
            raise Exception(f"Failed to delete flow: {e}")

    def update_flow_name(self, flow_id: str, new_name: str, tenant_id: str = None) -> bool:
        """
        Update a flow's name.

        Args:
            flow_id: Flow ID to update
            new_name: New name for the flow
            tenant_id: Tenant ID (defaults to env ACCOUNT_ID)

        Returns:
            True if updated, False if not found
        """
        if not tenant_id:
            tenant_id = os.getenv("ACCOUNT_ID", "341")

        pk = self._make_pk(tenant_id)
        sk = self._make_sk(flow_id)

        try:
            response = self.table.update_item(
                Key={'PK': pk, 'SK': sk},
                UpdateExpression='SET #name = :name, updated_at = :updated_at',
                ExpressionAttributeNames={'#name': 'name'},
                ExpressionAttributeValues={
                    ':name': new_name,
                    ':updated_at': datetime.utcnow().isoformat()
                },
                ReturnValues='ALL_NEW'
            )
            return 'Attributes' in response
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return False
            raise Exception(f"Failed to update flow name: {e}")


# Global provider instance
_provider = None


def _get_provider() -> DynamoDBFlowsProvider:
    """Get or create the global provider instance."""
    global _provider
    if _provider is None:
        _provider = DynamoDBFlowsProvider()
    return _provider


# Compatibility functions (match db/flows.py API)
def init_db() -> None:
    """Initialize flows table (DynamoDB table already exists)."""
    pass  # Table created externally


def save_flow(record: SavedFlowRecord) -> None:
    """Save a flow record (compatibility function)."""
    _get_provider().save_flow(record)


def get_flow(flow_id: str) -> Optional[SavedFlowRecord]:
    """Get a saved flow by ID (compatibility function)."""
    return _get_provider().get_flow(flow_id)


def list_flows(
    account_id: Optional[str] = None,
    application_name: Optional[str] = None,
    limit: int = 100
) -> List[SavedFlowRecord]:
    """List saved flows (compatibility function)."""
    return _get_provider().list_flows(account_id, application_name, limit)


def delete_flow(flow_id: str) -> bool:
    """Delete a saved flow (compatibility function)."""
    return _get_provider().delete_flow(flow_id)


def update_flow_name(flow_id: str, new_name: str) -> bool:
    """Update a flow's name (compatibility function)."""
    return _get_provider().update_flow_name(flow_id, new_name)
