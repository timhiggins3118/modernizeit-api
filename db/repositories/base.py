"""
Base repository interface.

Defines the contract that all repository implementations must follow.
This allows swapping storage backends (MongoDB → DynamoDB) without
changing the calling code.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseArtifactRepository(ABC):
    """
    Abstract base class for artifact storage.

    All storage backends (MongoDB, DynamoDB, etc.) must implement this interface.
    """

    @abstractmethod
    async def save_artifact(
        self,
        account_id: str,
        application: str,
        program: str,
        artifact_type: str,
        job_id: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Save an artifact to storage.

        Args:
            account_id: Customer account ID (e.g., "EVH")
            application: Application name (e.g., "TestApp01")
            program: Program name (e.g., "IFPR321") or "_application" for app-wide
            artifact_type: Type of artifact (e.g., "summary", "line_inventory")
            job_id: Job ID that generated this artifact
            data: Raw artifact data (dict)

        Returns:
            Unique identifier for the saved artifact
        """
        pass

    @abstractmethod
    async def get_artifact(
        self,
        account_id: str,
        application: str,
        program: str,
        artifact_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific artifact.

        Args:
            account_id: Customer account ID
            application: Application name
            program: Program name or "_application"
            artifact_type: Type of artifact

        Returns:
            Artifact document or None if not found
        """
        pass

    @abstractmethod
    async def get_artifacts(
        self,
        account_id: str,
        application: str,
        program: Optional[str] = None,
        artifact_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query artifacts with optional filters.

        Args:
            account_id: Customer account ID
            application: Application name
            program: Optional program filter
            artifact_type: Optional artifact type filter

        Returns:
            List of matching artifact documents
        """
        pass

    @abstractmethod
    async def delete_artifacts(
        self,
        account_id: str,
        application: str,
        program: Optional[str] = None
    ) -> int:
        """
        Delete artifacts.

        Args:
            account_id: Customer account ID
            application: Application name
            program: Optional program filter (if None, deletes all for app)

        Returns:
            Number of artifacts deleted
        """
        pass

    @abstractmethod
    async def list_programs(
        self,
        account_id: str,
        application: str
    ) -> List[str]:
        """
        List all programs that have artifacts.

        Args:
            account_id: Customer account ID
            application: Application name

        Returns:
            List of program names
        """
        pass

    @abstractmethod
    async def list_artifact_types(
        self,
        account_id: str,
        application: str,
        program: str
    ) -> List[str]:
        """
        List all artifact types for a program.

        Args:
            account_id: Customer account ID
            application: Application name
            program: Program name

        Returns:
            List of artifact type names
        """
        pass
