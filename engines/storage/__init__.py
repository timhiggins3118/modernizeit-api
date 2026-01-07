"""
Storage Module - Abstraction for file storage (local filesystem or S3).

Provides a unified interface for reading files regardless of where they're stored.
This allows the same code to work in local development (filesystem) and
production (S3) without changes.

Usage:
    from engines.storage import get_storage_provider

    storage = get_storage_provider()  # Returns LocalStorage or S3Storage based on config

    # List files
    files = storage.list_files("path/to/dir", "*.cbl")

    # Read a file
    content = storage.read_file("path/to/file.cbl")

    # Search files
    results = storage.search_files("path/to/dir", "CUSTOMER-FILE", "*.cbl")
"""

from .base import StorageProvider, FileInfo, SearchResult
from .local import LocalStorage
from .s3 import S3Storage
from .factory import get_storage_provider

__all__ = [
    "StorageProvider",
    "FileInfo",
    "SearchResult",
    "LocalStorage",
    "S3Storage",
    "get_storage_provider",
]
