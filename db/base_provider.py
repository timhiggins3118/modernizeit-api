"""
Base Provider Interface - Abstract contract for all data providers.

All storage backends (SQLite, DynamoDB, MongoDB, PostgreSQL, etc.)
must implement this interface.

This allows swapping backends without changing API code.

Created: December 31, 2025
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from db.models import Application, FileRecord, PortfolioSummary


# =============================================================================
# BASE PROVIDER INTERFACE
# =============================================================================

class BaseDataProvider(ABC):
    """
    Abstract base class for data providers.

    All providers must implement these methods.
    API code works with this interface, not concrete implementations.

    Usage:
        provider = get_provider()  # Factory returns correct implementation
        apps = provider.list_applications()
    """

    # =========================================================================
    # CONNECTION / STATUS
    # =========================================================================

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to the data store.

        Returns:
            Dict with:
                - connected: bool
                - provider: str (e.g., "dynamodb", "sqlite")
                - details: dict with backend-specific info
        """
        pass

    @abstractmethod
    def get_provider_info(self) -> Dict[str, Any]:
        """
        Get provider metadata.

        Returns:
            Dict with provider name, version, capabilities, etc.
        """
        pass

    # =========================================================================
    # APPLICATIONS - READ
    # =========================================================================

    @abstractmethod
    def list_applications(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Application]:
        """
        List all applications.

        Args:
            limit: Max number to return
            offset: Number to skip (for pagination)

        Returns:
            List of Application objects
        """
        pass

    @abstractmethod
    def get_application(self, application_id: str) -> Optional[Application]:
        """
        Get a single application by ID.

        Args:
            application_id: The application ID

        Returns:
            Application or None if not found
        """
        pass

    @abstractmethod
    def find_application_by_name(self, name: str) -> Optional[Application]:
        """
        Find application by name.

        Args:
            name: Application name to search for

        Returns:
            Application or None if not found
        """
        pass

    # =========================================================================
    # APPLICATIONS - WRITE (implement when ready)
    # =========================================================================

    @abstractmethod
    def create_application(self, application: Application) -> str:
        """
        Create a new application.

        Args:
            application: Application to create

        Returns:
            The created application ID
        """
        pass

    @abstractmethod
    def update_application(self, application: Application) -> bool:
        """
        Update an existing application.

        Args:
            application: Application with updated fields

        Returns:
            True if updated, False if not found
        """
        pass

    @abstractmethod
    def delete_application(self, application_id: str) -> bool:
        """
        Delete an application.

        Args:
            application_id: ID of application to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    # =========================================================================
    # FILES - READ
    # =========================================================================

    @abstractmethod
    def list_files(
        self,
        application_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[FileRecord]:
        """
        List files, optionally filtered by application.

        Args:
            application_id: Filter by application (optional)
            limit: Max number to return

        Returns:
            List of FileRecord objects
        """
        pass

    @abstractmethod
    def get_file(self, file_id: str) -> Optional[FileRecord]:
        """
        Get a single file by ID.

        Args:
            file_id: The file ID

        Returns:
            FileRecord or None if not found
        """
        pass

    @abstractmethod
    def find_files_by_name(
        self,
        file_name: str,
        application_id: Optional[str] = None
    ) -> List[FileRecord]:
        """
        Find files by name (supports partial match).

        Args:
            file_name: File name to search for
            application_id: Optional application filter

        Returns:
            List of matching FileRecord objects
        """
        pass

    # =========================================================================
    # FILES - WRITE (implement when ready)
    # =========================================================================

    @abstractmethod
    def create_file(self, file_record: FileRecord) -> str:
        """
        Create a new file record.

        Args:
            file_record: FileRecord to create

        Returns:
            The created file ID
        """
        pass

    @abstractmethod
    def update_file(self, file_record: FileRecord) -> bool:
        """
        Update an existing file record.

        Args:
            file_record: FileRecord with updated fields

        Returns:
            True if updated, False if not found
        """
        pass

    @abstractmethod
    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file record.

        Args:
            file_id: ID of file to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    # =========================================================================
    # AGGREGATIONS
    # =========================================================================

    @abstractmethod
    def get_portfolio_summary(self) -> PortfolioSummary:
        """
        Get aggregated portfolio statistics.

        Returns:
            PortfolioSummary with totals, averages, etc.
        """
        pass

    @abstractmethod
    def get_application_with_files(
        self,
        application_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get application with all its files.

        Args:
            application_id: Application ID

        Returns:
            Dict with 'application' and 'files' keys, or None
        """
        pass
