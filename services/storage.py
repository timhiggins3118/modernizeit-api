"""
Storage Service

Abstracts file storage operations for both local filesystem and S3.
Provides a unified interface for reading, writing, listing, and copying files.

Usage:
    from services.storage import storage_service

    # List files
    files = storage_service.list_files("account/app/code_analysis/generated", pattern="*.java")

    # Read file
    content = storage_service.read_file("account/app/code_analysis/generated/IFPR321.java")

    # Write file
    storage_service.write_file("account/app/workspace/java/IFPR321.java", content)

    # Copy directory
    storage_service.copy_directory("account/app/code_analysis/generated", "account/app/workspace/java")
"""

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
import fnmatch

from config.settings import settings


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def list_files(self, path: str, pattern: str = "*", recursive: bool = True) -> List[str]:
        """List files at path matching pattern."""
        pass

    @abstractmethod
    def list_directories(self, path: str) -> List[str]:
        """List subdirectories at path."""
        pass

    @abstractmethod
    def read_file(self, path: str) -> str:
        """Read file content as string."""
        pass

    @abstractmethod
    def read_file_bytes(self, path: str) -> bytes:
        """Read file content as bytes."""
        pass

    @abstractmethod
    def write_file(self, path: str, content: str) -> None:
        """Write string content to file."""
        pass

    @abstractmethod
    def write_file_bytes(self, path: str, content: bytes) -> None:
        """Write bytes content to file."""
        pass

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        pass

    @abstractmethod
    def directory_exists(self, path: str) -> bool:
        """Check if directory exists."""
        pass

    @abstractmethod
    def copy_file(self, src: str, dst: str) -> None:
        """Copy a single file."""
        pass

    @abstractmethod
    def copy_directory(self, src: str, dst: str) -> None:
        """Copy entire directory recursively."""
        pass

    @abstractmethod
    def delete_file(self, path: str) -> None:
        """Delete a file."""
        pass

    @abstractmethod
    def delete_directory(self, path: str) -> None:
        """Delete directory recursively."""
        pass

    @abstractmethod
    def get_file_info(self, path: str) -> dict:
        """Get file metadata (size, modified time, etc.)."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_path: Path):
        self.base_path = base_path

    def _resolve_path(self, path: str) -> Path:
        """Resolve relative path to absolute path."""
        return self.base_path / "code-transformation-v2" / path

    def list_files(self, path: str, pattern: str = "*", recursive: bool = True) -> List[str]:
        """List files at path matching pattern."""
        full_path = self._resolve_path(path)
        if not full_path.exists():
            return []

        files = []
        if recursive:
            for root, dirs, filenames in os.walk(full_path):
                for filename in filenames:
                    if fnmatch.fnmatch(filename, pattern):
                        file_path = Path(root) / filename
                        # Return relative path from the requested path
                        rel_path = file_path.relative_to(full_path)
                        files.append(str(rel_path))
        else:
            for item in full_path.iterdir():
                if item.is_file() and fnmatch.fnmatch(item.name, pattern):
                    files.append(item.name)

        return sorted(files)

    def list_directories(self, path: str) -> List[str]:
        """List subdirectories at path."""
        full_path = self._resolve_path(path)
        if not full_path.exists():
            return []

        dirs = []
        for item in full_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                dirs.append(item.name)

        return sorted(dirs)

    def read_file(self, path: str) -> str:
        """Read file content as string.

        Tries multiple encodings to handle mainframe COBOL files.
        """
        full_path = self._resolve_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Try common encodings for mainframe/COBOL files
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]

        for encoding in encodings:
            try:
                return full_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue

        # Last resort: read as bytes and decode with error replacement
        return full_path.read_bytes().decode("utf-8", errors="replace")

    def read_file_bytes(self, path: str) -> bytes:
        """Read file content as bytes."""
        full_path = self._resolve_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return full_path.read_bytes()

    def write_file(self, path: str, content: str) -> None:
        """Write string content to file."""
        full_path = self._resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    def write_file_bytes(self, path: str, content: bytes) -> None:
        """Write bytes content to file."""
        full_path = self._resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)

    def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        full_path = self._resolve_path(path)
        return full_path.is_file()

    def directory_exists(self, path: str) -> bool:
        """Check if directory exists."""
        full_path = self._resolve_path(path)
        return full_path.is_dir()

    def copy_file(self, src: str, dst: str) -> None:
        """Copy a single file."""
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {src}")
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)

    def copy_directory(self, src: str, dst: str) -> None:
        """Copy entire directory recursively."""
        src_path = self._resolve_path(src)
        dst_path = self._resolve_path(dst)
        if not src_path.exists():
            raise FileNotFoundError(f"Source directory not found: {src}")
        # Remove destination if exists
        if dst_path.exists():
            shutil.rmtree(dst_path)
        shutil.copytree(src_path, dst_path)

    def delete_file(self, path: str) -> None:
        """Delete a file."""
        full_path = self._resolve_path(path)
        if full_path.exists():
            full_path.unlink()

    def delete_directory(self, path: str) -> None:
        """Delete directory recursively."""
        full_path = self._resolve_path(path)
        if full_path.exists():
            shutil.rmtree(full_path)

    def get_file_info(self, path: str) -> dict:
        """Get file metadata."""
        full_path = self._resolve_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        stat = full_path.stat()
        return {
            "path": path,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_file": full_path.is_file(),
            "is_dir": full_path.is_dir(),
        }


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend."""

    def __init__(self, bucket: str, prefix: str, region: str):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.region = region
        self._client = None

    @property
    def client(self):
        """Lazy-load S3 client."""
        if self._client is None:
            import boto3
            self._client = boto3.client("s3", region_name=self.region)
        return self._client

    def _resolve_key(self, path: str) -> str:
        """Resolve relative path to S3 key."""
        if self.prefix:
            return f"{self.prefix}/{path}"
        return path

    def list_files(self, path: str, pattern: str = "*", recursive: bool = True) -> List[str]:
        """List files at path matching pattern."""
        prefix = self._resolve_key(path)
        if not prefix.endswith("/"):
            prefix += "/"

        files = []
        paginator = self.client.get_paginator("list_objects_v2")

        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    # Get relative path from the requested path
                    rel_path = key[len(prefix):]
                    if not rel_path:
                        continue

                    # Filter by pattern
                    filename = rel_path.split("/")[-1]
                    if fnmatch.fnmatch(filename, pattern):
                        if recursive or "/" not in rel_path:
                            files.append(rel_path)
        except Exception as e:
            print(f"[S3] Error listing files: {e}")
            return []

        return sorted(files)

    def list_directories(self, path: str) -> List[str]:
        """List subdirectories at path (S3 uses CommonPrefixes)."""
        prefix = self._resolve_key(path)
        if not prefix.endswith("/"):
            prefix += "/"

        dirs = set()
        try:
            paginator = self.client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix, Delimiter="/"):
                # CommonPrefixes contains the "directories"
                for cp in page.get("CommonPrefixes", []):
                    dir_name = cp["Prefix"][len(prefix):].rstrip("/")
                    if dir_name and not dir_name.startswith('.'):
                        dirs.add(dir_name)
        except Exception as e:
            print(f"[S3] Error listing directories: {e}")
            return []

        return sorted(dirs)

    def read_file(self, path: str) -> str:
        """Read file content as string.

        Tries multiple encodings to handle mainframe COBOL files.
        """
        content = self.read_file_bytes(path)

        # Try common encodings for mainframe/COBOL files
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]

        for encoding in encodings:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue

        # Last resort: decode with error replacement
        return content.decode("utf-8", errors="replace")

    def read_file_bytes(self, path: str) -> bytes:
        """Read file content as bytes."""
        key = self._resolve_key(path)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except self.client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"File not found: {path}")
        except Exception as e:
            raise IOError(f"Error reading file {path}: {e}")

    def write_file(self, path: str, content: str) -> None:
        """Write string content to file."""
        self.write_file_bytes(path, content.encode("utf-8"))

    def write_file_bytes(self, path: str, content: bytes) -> None:
        """Write bytes content to file."""
        key = self._resolve_key(path)
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        except Exception as e:
            raise IOError(f"Error writing file {path}: {e}")

    def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        key = self._resolve_key(path)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except:
            return False

    def directory_exists(self, path: str) -> bool:
        """Check if 'directory' exists (has any objects with prefix)."""
        prefix = self._resolve_key(path)
        if not prefix.endswith("/"):
            prefix += "/"
        try:
            response = self.client.list_objects_v2(
                Bucket=self.bucket, Prefix=prefix, MaxKeys=1
            )
            return response.get("KeyCount", 0) > 0
        except:
            return False

    def copy_file(self, src: str, dst: str) -> None:
        """Copy a single file within S3."""
        src_key = self._resolve_key(src)
        dst_key = self._resolve_key(dst)
        try:
            self.client.copy_object(
                Bucket=self.bucket,
                CopySource={"Bucket": self.bucket, "Key": src_key},
                Key=dst_key,
            )
        except Exception as e:
            raise IOError(f"Error copying {src} to {dst}: {e}")

    def copy_directory(self, src: str, dst: str) -> None:
        """Copy entire directory recursively within S3."""
        src_prefix = self._resolve_key(src)
        dst_prefix = self._resolve_key(dst)

        if not src_prefix.endswith("/"):
            src_prefix += "/"
        if not dst_prefix.endswith("/"):
            dst_prefix += "/"

        # Delete destination first
        self._delete_prefix(dst_prefix)

        # Copy all objects
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=src_prefix):
            for obj in page.get("Contents", []):
                src_key = obj["Key"]
                rel_path = src_key[len(src_prefix):]
                dst_key = dst_prefix + rel_path
                self.client.copy_object(
                    Bucket=self.bucket,
                    CopySource={"Bucket": self.bucket, "Key": src_key},
                    Key=dst_key,
                )

    def delete_file(self, path: str) -> None:
        """Delete a file."""
        key = self._resolve_key(path)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as e:
            print(f"[S3] Error deleting file {path}: {e}")

    def delete_directory(self, path: str) -> None:
        """Delete directory recursively."""
        prefix = self._resolve_key(path)
        if not prefix.endswith("/"):
            prefix += "/"
        self._delete_prefix(prefix)

    def _delete_prefix(self, prefix: str) -> None:
        """Delete all objects with given prefix."""
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if objects:
                self.client.delete_objects(
                    Bucket=self.bucket, Delete={"Objects": objects}
                )

    def get_file_info(self, path: str) -> dict:
        """Get file metadata."""
        key = self._resolve_key(path)
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
            return {
                "path": path,
                "size": response["ContentLength"],
                "modified": response["LastModified"].timestamp(),
                "is_file": True,
                "is_dir": False,
            }
        except self.client.exceptions.NoSuchKey:
            raise FileNotFoundError(f"File not found: {path}")


class StorageService:
    """
    Storage service with backend abstraction.

    Automatically selects local or S3 backend based on settings.
    """

    def __init__(self):
        self._backend: Optional[StorageBackend] = None

    @property
    def backend(self) -> StorageBackend:
        """Get the configured storage backend (lazy initialization)."""
        if self._backend is None:
            if settings.storage_mode == "s3":
                if not settings.s3_bucket:
                    raise ValueError("S3 bucket not configured. Set s3_bucket in settings.")
                self._backend = S3StorageBackend(
                    bucket=settings.s3_bucket,
                    prefix=settings.s3_prefix,
                    region=settings.s3_region,
                )
                print(f"[storage] Using S3 backend: s3://{settings.s3_bucket}/{settings.s3_prefix}")
            else:
                self._backend = LocalStorageBackend(base_path=settings.base_local_path)
                print(f"[storage] Using local backend: {settings.base_local_path}")
        return self._backend

    # Delegate all methods to backend

    def list_files(self, path: str, pattern: str = "*", recursive: bool = True) -> List[str]:
        return self.backend.list_files(path, pattern, recursive)

    def list_directories(self, path: str) -> List[str]:
        return self.backend.list_directories(path)

    def read_file(self, path: str) -> str:
        return self.backend.read_file(path)

    def read_file_bytes(self, path: str) -> bytes:
        return self.backend.read_file_bytes(path)

    def write_file(self, path: str, content: str) -> None:
        return self.backend.write_file(path, content)

    def write_file_bytes(self, path: str, content: bytes) -> None:
        return self.backend.write_file_bytes(path, content)

    def file_exists(self, path: str) -> bool:
        return self.backend.file_exists(path)

    def directory_exists(self, path: str) -> bool:
        return self.backend.directory_exists(path)

    def copy_file(self, src: str, dst: str) -> None:
        return self.backend.copy_file(src, dst)

    def copy_directory(self, src: str, dst: str) -> None:
        return self.backend.copy_directory(src, dst)

    def delete_file(self, path: str) -> None:
        return self.backend.delete_file(path)

    def delete_directory(self, path: str) -> None:
        return self.backend.delete_directory(path)

    def get_file_info(self, path: str) -> dict:
        return self.backend.get_file_info(path)


# Singleton instance
storage_service = StorageService()
