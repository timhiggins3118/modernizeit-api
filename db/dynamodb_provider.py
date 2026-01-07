"""
DynamoDB Data Provider - AWS DynamoDB implementation.

Professional single-table design for ModernizeIT.

Table: modernizeit-dev-data (or modernizeit-prod-data)
  - PK: TENANT#{tenant_id}
  - SK: {ENTITY_TYPE}#{entity_id}

Supports: Jobs, Accounts, Credentials, Flow Executions

Created: December 31, 2025
Updated: January 6, 2026 - Single-table design
"""

import boto3
import os
from boto3.dynamodb.conditions import Key, Attr
from typing import Any, Dict, List, Optional
from datetime import datetime

from db.base_provider import BaseDataProvider
from db.models import Application, FileRecord, PortfolioSummary


class DynamoDBProvider(BaseDataProvider):
    """
    DynamoDB implementation of the data provider.

    Uses professional single-table design with tenant isolation.

    Usage:
        provider = DynamoDBProvider(
            tenant_id="341",
            table_name="modernizeit-dev-data"
        )
        apps = provider.list_applications()
    """

    def __init__(
        self,
        tenant_id: str = None,
        table_name: str = None,
        region: str = "us-east-1"
    ):
        """
        Initialize the DynamoDB provider.

        Args:
            tenant_id: Tenant/account ID (e.g., "341") - defaults to env var ACCOUNT_ID
            table_name: DynamoDB table name - defaults to env var DYNAMODB_TABLE_NAME
            region: AWS region (default: us-east-1)
        """
        self.tenant_id = tenant_id or os.getenv("ACCOUNT_ID", "341")
        self.table_name = table_name or os.getenv("DYNAMODB_TABLE_NAME", "modernizeit-dev-data")
        self.region = region
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

    def _make_pk(self, entity_type: str = None) -> str:
        """Create partition key: TENANT#{tenant_id}"""
        return f"TENANT#{self.tenant_id}"

    def _make_sk(self, entity_type: str, entity_id: str) -> str:
        """Create sort key: {ENTITY_TYPE}#{entity_id}"""
        return f"{entity_type.upper()}#{entity_id}"

    # =========================================================================
    # CONNECTION / STATUS
    # =========================================================================

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to DynamoDB."""
        result = {
            "connected": False,
            "provider": "dynamodb",
            "account_id": self.account_id,
            "region": self.region,
            "tables": {}
        }

        try:
            # Check applications table
            apps_table = self.dynamodb.Table(self._applications_table)
            apps_count = apps_table.scan(Select='COUNT')['Count']
            result["tables"]["applications"] = {
                "name": self._applications_table,
                "count": apps_count
            }

            # Check files table
            try:
                files_table = self.dynamodb.Table(self._files_table)
                files_count = files_table.scan(Select='COUNT')['Count']
                result["tables"]["files"] = {
                    "name": self._files_table,
                    "count": files_count
                }
            except Exception as e:
                result["tables"]["files"] = {
                    "name": self._files_table,
                    "error": str(e)
                }

            result["connected"] = True

        except Exception as e:
            result["error"] = str(e)

        return result

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider metadata."""
        return {
            "provider": "dynamodb",
            "version": "1.0.0",
            "account_id": self.account_id,
            "region": self.region,
            "tables": {
                "applications": self._applications_table,
                "files": self._files_table
            },
            "capabilities": {
                "read": True,
                "write": False,  # Not implemented yet
                "delete": False  # Not implemented yet
            }
        }

    # =========================================================================
    # APPLICATIONS - READ
    # =========================================================================

    def list_applications(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Application]:
        """List all applications."""
        table = self.dynamodb.Table(self._applications_table)

        scan_kwargs = {}
        if limit:
            scan_kwargs['Limit'] = limit

        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])

        # Handle pagination if no limit
        while 'LastEvaluatedKey' in response and not limit:
            response = table.scan(
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        applications = [self._item_to_application(item) for item in items]

        # Handle offset (skip)
        if offset:
            applications = applications[offset:]

        return applications

    def get_application(self, application_id: str) -> Optional[Application]:
        """Get a single application by ID."""
        table = self.dynamodb.Table(self._applications_table)

        response = table.get_item(Key={'application_id': application_id})
        item = response.get('Item')

        return self._item_to_application(item) if item else None

    def find_application_by_name(self, name: str) -> Optional[Application]:
        """Find application by name."""
        table = self.dynamodb.Table(self._applications_table)

        response = table.scan(
            FilterExpression=Attr('application_name').eq(name)
        )
        items = response.get('Items', [])

        return self._item_to_application(items[0]) if items else None

    def _item_to_application(self, item: Dict[str, Any]) -> Application:
        """Convert DynamoDB item to Application model."""
        app = Application.from_dict(item)
        app.account_id = self.account_id
        return app

    # =========================================================================
    # APPLICATIONS - WRITE (NOT IMPLEMENTED)
    # =========================================================================

    def create_application(self, application: Application) -> str:
        """Create application - NOT IMPLEMENTED."""
        raise NotImplementedError("DynamoDB write operations not yet implemented")

    def update_application(self, application: Application) -> bool:
        """Update application - NOT IMPLEMENTED."""
        raise NotImplementedError("DynamoDB write operations not yet implemented")

    def delete_application(self, application_id: str) -> bool:
        """Delete application - NOT IMPLEMENTED."""
        raise NotImplementedError("DynamoDB write operations not yet implemented")

    # =========================================================================
    # FILES - READ
    # =========================================================================

    def list_files(
        self,
        application_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[FileRecord]:
        """List files, optionally filtered by application."""
        table = self.dynamodb.Table(self._files_table)

        scan_kwargs = {}
        if limit:
            scan_kwargs['Limit'] = limit
        if application_id:
            scan_kwargs['FilterExpression'] = Attr('application_id').eq(application_id)

        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])

        # Handle pagination if no limit
        while 'LastEvaluatedKey' in response and not limit:
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
            response = table.scan(**scan_kwargs)
            items.extend(response.get('Items', []))

        return [self._item_to_file(item) for item in items]

    def get_file(self, file_id: str) -> Optional[FileRecord]:
        """Get a single file by ID."""
        table = self.dynamodb.Table(self._files_table)

        response = table.get_item(Key={'file_id': file_id})
        item = response.get('Item')

        return self._item_to_file(item) if item else None

    def find_files_by_name(
        self,
        file_name: str,
        application_id: Optional[str] = None
    ) -> List[FileRecord]:
        """Find files by name (contains match)."""
        table = self.dynamodb.Table(self._files_table)

        filter_expr = Attr('file_name').contains(file_name)
        if application_id:
            filter_expr = filter_expr & Attr('application_id').eq(application_id)

        response = table.scan(FilterExpression=filter_expr)
        items = response.get('Items', [])

        return [self._item_to_file(item) for item in items]

    def _item_to_file(self, item: Dict[str, Any]) -> FileRecord:
        """Convert DynamoDB item to FileRecord model."""
        file_rec = FileRecord.from_dict(item)
        file_rec.account_id = self.account_id
        return file_rec

    # =========================================================================
    # FILES - WRITE (NOT IMPLEMENTED)
    # =========================================================================

    def create_file(self, file_record: FileRecord) -> str:
        """Create file - NOT IMPLEMENTED."""
        raise NotImplementedError("DynamoDB write operations not yet implemented")

    def update_file(self, file_record: FileRecord) -> bool:
        """Update file - NOT IMPLEMENTED."""
        raise NotImplementedError("DynamoDB write operations not yet implemented")

    def delete_file(self, file_id: str) -> bool:
        """Delete file - NOT IMPLEMENTED."""
        raise NotImplementedError("DynamoDB write operations not yet implemented")

    # =========================================================================
    # AGGREGATIONS
    # =========================================================================

    def get_portfolio_summary(self) -> PortfolioSummary:
        """Get aggregated portfolio statistics."""
        apps = self.list_applications()

        total_apps = len(apps)
        total_files = 0
        total_progress = 0
        near_completion = 0
        by_status: Dict[str, int] = {}

        for app in apps:
            # Count files
            if app.file_count:
                total_files += app.file_count

            # Sum progress
            if app.progress is not None:
                total_progress += app.progress
                if app.progress >= 75:
                    near_completion += 1

            # Count by status
            status = app.status or "Starting"
            by_status[status] = by_status.get(status, 0) + 1

        avg_progress = round(total_progress / total_apps) if total_apps > 0 else 0

        return PortfolioSummary(
            total_applications=total_apps,
            total_files=total_files,
            avg_progress=avg_progress,
            near_completion=near_completion,
            by_status=by_status
        )

    def get_application_with_files(
        self,
        application_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get application with all its files."""
        app = self.get_application(application_id)
        if not app:
            return None

        files = self.list_files(application_id=application_id)

        return {
            "application": app.to_dict(),
            "files": [f.to_dict() for f in files]
        }
