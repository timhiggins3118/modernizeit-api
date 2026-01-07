"""
DynamoDB Jobs Module - Complete Implementation

Replaces db/jobs.py SQLite implementation with DynamoDB.
Uses professional single-table design with tenant isolation.

Table: modernizeit-dev-data
  PK: TENANT#{tenant_id}
  SK: JOB#{job_id}

Created: January 6, 2026
"""

import boto3
import os
import json
from boto3.dynamodb.conditions import Key, Attr
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class JobRecord:
    """
    Job record dataclass - matches SQLite version.

    Stores metadata about a job execution.
    """
    job_id: str
    flow_type: str  # e.g. "ingest", "code_analysis_v3"
    status: str  # "running", "completed", "failed"
    created_at: datetime
    updated_at: datetime
    artifacts_path: str  # S3 path or local path to artifacts
    input_json: str  # JSON string of original request

    # Additional fields for DynamoDB
    tenant_id: Optional[str] = None  # Extracted from input_json
    application_name: Optional[str] = None  # Extracted from input_json


class DynamoDBJobsProvider:
    """
    DynamoDB implementation for job tracking.

    Drop-in replacement for db/jobs.py SQLite functions.

    Usage:
        provider = DynamoDBJobsProvider()
        provider.init_db()  # Ensures table exists
        provider.save_job(record)
        job = provider.get_job(job_id)
    """

    def __init__(
        self,
        table_name: str = None,
        region: str = None
    ):
        """
        Initialize the DynamoDB jobs provider.

        Args:
            table_name: DynamoDB table name (defaults to env var DYNAMODB_TABLE_NAME)
            region: AWS region (defaults to env var AWS_REGION or us-east-1)
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

    def _make_pk(self, tenant_id: str) -> str:
        """Create partition key: TENANT#{tenant_id}"""
        return f"TENANT#{tenant_id}"

    def _make_sk(self, job_id: str) -> str:
        """Create sort key: JOB#{job_id}"""
        return f"JOB#{job_id}"

    def _extract_tenant_from_input(self, input_json: str) -> str:
        """Extract tenant ID from input JSON."""
        try:
            data = json.loads(input_json)
            return data.get('scout_account_id', data.get('account_id', '341'))
        except:
            return '341'  # Default tenant

    def _extract_app_from_input(self, input_json: str) -> Optional[str]:
        """Extract application name from input JSON."""
        try:
            data = json.loads(input_json)
            return data.get('application_name')
        except:
            return None

    def init_db(self) -> None:
        """
        Initialize the database.

        Verifies table exists. For DynamoDB, table should already exist.
        This is a no-op for compatibility with SQLite version.
        """
        try:
            # Just verify table exists
            self.table.table_status
        except Exception as e:
            print(f"[dynamodb_jobs] Warning: Table {self.table_name} may not exist: {e}")

    def save_job(self, record: JobRecord) -> None:
        """
        Save a job record to DynamoDB.

        Args:
            record: JobRecord to save
        """
        # Extract tenant_id and app from input_json if not set
        if not record.tenant_id:
            record.tenant_id = self._extract_tenant_from_input(record.input_json)
        if not record.application_name:
            record.application_name = self._extract_app_from_input(record.input_json)

        pk = self._make_pk(record.tenant_id)
        sk = self._make_sk(record.job_id)

        item = {
            'PK': pk,
            'SK': sk,
            'entity_type': 'job',
            'job_id': record.job_id,
            'tenant_id': record.tenant_id,
            'flow_type': record.flow_type,
            'job_status': record.status,  # GSI key
            'created_at': record.created_at.isoformat(),
            'updated_at': record.updated_at.isoformat(),
            'artifacts_path': record.artifacts_path,
            'input_json': record.input_json,
        }

        if record.application_name:
            item['application_name'] = record.application_name

        self.table.put_item(Item=item)

    def get_job(self, job_id: str, tenant_id: str = None) -> Optional[JobRecord]:
        """
        Fetch a job record by job_id.

        Args:
            job_id: The job identifier to look up
            tenant_id: Tenant ID (required for DynamoDB, optional for compatibility)

        Returns:
            JobRecord if found, None otherwise
        """
        # If tenant_id not provided, try to extract from job_id pattern
        if not tenant_id:
            # Job IDs have format: {flow}_job_{account}_{app}_{timestamp}_{hash}
            # Example: ingest_job_Tims-Test-moderizeit_TimsTestApp_1767800931_c1259f08
            parts = job_id.split('_')
            if len(parts) >= 3 and parts[1] == 'job':
                # New format: {flow}_job_{account}_...
                tenant_id = parts[2]  # Account is third part (index 2)
            elif len(parts) >= 2:
                # Fallback: assume account is second part (old format)
                tenant_id = parts[1]
            else:
                tenant_id = os.getenv("ACCOUNT_ID", "341")

        pk = self._make_pk(tenant_id)
        sk = self._make_sk(job_id)

        try:
            response = self.table.get_item(
                Key={'PK': pk, 'SK': sk}
            )

            if 'Item' not in response:
                return None

            item = response['Item']
            return JobRecord(
                job_id=item['job_id'],
                flow_type=item['flow_type'],
                status=item['job_status'],
                created_at=datetime.fromisoformat(item['created_at']),
                updated_at=datetime.fromisoformat(item['updated_at']),
                artifacts_path=item['artifacts_path'],
                input_json=item['input_json'],
                tenant_id=item.get('tenant_id'),
                application_name=item.get('application_name')
            )
        except Exception as e:
            print(f"[dynamodb_jobs] Error getting job {job_id}: {e}")
            return None

    def list_jobs(
        self,
        account_id: Optional[str] = None,
        application_name: Optional[str] = None,
        flow_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[JobRecord]:
        """
        List job records with optional filters.

        Args:
            account_id: Filter by account ID (tenant ID)
            application_name: Filter by application name
            flow_type: Filter by flow type
            status: Filter by status
            limit: Maximum number of records to return

        Returns:
            List of JobRecord objects matching the filters
        """
        results = []

        if account_id:
            # Query specific tenant's jobs
            pk = self._make_pk(account_id)

            query_params = {
                'KeyConditionExpression': Key('PK').eq(pk) & Key('SK').begins_with('JOB#'),
                'Limit': limit
            }

            # Add filter expressions
            filter_expressions = []
            if flow_type:
                filter_expressions.append(Attr('flow_type').eq(flow_type))
            if status:
                filter_expressions.append(Attr('job_status').eq(status))
            if application_name:
                filter_expressions.append(Attr('application_name').eq(application_name))

            if filter_expressions:
                combined_filter = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    combined_filter = combined_filter & expr
                query_params['FilterExpression'] = combined_filter

            response = self.table.query(**query_params)
            items = response.get('Items', [])

        elif status:
            # Use GSI to query by status across all tenants
            query_params = {
                'IndexName': 'StatusIndex',
                'KeyConditionExpression': Key('job_status').eq(status),
                'Limit': limit
            }

            # Add filter expressions
            filter_expressions = []
            if flow_type:
                filter_expressions.append(Attr('flow_type').eq(flow_type))
            if application_name:
                filter_expressions.append(Attr('application_name').eq(application_name))

            if filter_expressions:
                combined_filter = filter_expressions[0]
                for expr in filter_expressions[1:]:
                    combined_filter = combined_filter & expr
                query_params['FilterExpression'] = combined_filter

            try:
                response = self.table.query(**query_params)
                items = response.get('Items', [])
            except Exception as e:
                print(f"[dynamodb_jobs] Error querying StatusIndex: {e}")
                items = []

        else:
            # Scan (expensive - avoid in production)
            print("[dynamodb_jobs] Warning: Scanning table without partition key - expensive!")
            scan_params = {'Limit': limit}

            filter_expressions = []
            filter_expressions.append(Attr('entity_type').eq('job'))
            if flow_type:
                filter_expressions.append(Attr('flow_type').eq(flow_type))
            if application_name:
                filter_expressions.append(Attr('application_name').eq(application_name))

            combined_filter = filter_expressions[0]
            for expr in filter_expressions[1:]:
                combined_filter = combined_filter & expr
            scan_params['FilterExpression'] = combined_filter

            response = self.table.scan(**scan_params)
            items = response.get('Items', [])

        # Convert items to JobRecords
        for item in items:
            try:
                record = JobRecord(
                    job_id=item['job_id'],
                    flow_type=item['flow_type'],
                    status=item['job_status'],
                    created_at=datetime.fromisoformat(item['created_at']),
                    updated_at=datetime.fromisoformat(item['updated_at']),
                    artifacts_path=item['artifacts_path'],
                    input_json=item['input_json'],
                    tenant_id=item.get('tenant_id'),
                    application_name=item.get('application_name')
                )
                results.append(record)
            except Exception as e:
                print(f"[dynamodb_jobs] Error parsing item: {e}")
                continue

        return results[:limit]


# ============================================================================
# Compatibility Functions (match db/jobs.py API)
# ============================================================================

_provider = None

def _get_provider() -> DynamoDBJobsProvider:
    """Get or create singleton provider instance."""
    global _provider
    if _provider is None:
        _provider = DynamoDBJobsProvider()
    return _provider


def init_db() -> None:
    """Initialize the database (compatibility function)."""
    _get_provider().init_db()


def save_job(record: JobRecord) -> None:
    """Save a job record (compatibility function)."""
    _get_provider().save_job(record)


def get_job(job_id: str) -> Optional[JobRecord]:
    """Get a job record (compatibility function)."""
    return _get_provider().get_job(job_id)


def list_jobs(
    account_id: Optional[str] = None,
    application_name: Optional[str] = None,
    flow_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
) -> List[JobRecord]:
    """List jobs (compatibility function)."""
    return _get_provider().list_jobs(
        account_id=account_id,
        application_name=application_name,
        flow_type=flow_type,
        status=status,
        limit=limit
    )
