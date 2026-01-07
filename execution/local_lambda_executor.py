"""
LocalLambdaExecutor v2

Clean implementation following DOC-280 Section 5.
Includes DOC-380 Section 4.2 Pattern B for local S3 redirection.

Executes Lambda-style code projects locally:
- Loads handler from project path
- Invokes with event
- Captures return value, logs, errors
- Redirects S3 calls to local filesystem (Pattern B monkeypatch)
"""

import importlib.util
import json
import logging
import os
import sys
import traceback
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3

logger = logging.getLogger(__name__)


# =============================================================================
# DOC-380 Section 4.2 - Pattern B: Local S3 Client (Monkeypatch)
# =============================================================================

class BodyWrapper:
    """
    Wrapper for S3 object body to match boto3 get_object response shape.
    Per DOC-380 Section 4.2.
    """
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class S3Exceptions:
    """
    Mock S3 exceptions to match boto3 client.exceptions pattern.
    Lambda code often uses: s3_client.exceptions.NoSuchKey
    """
    class NoSuchKey(Exception):
        pass

    class NoSuchBucket(Exception):
        pass


class LocalS3Client:
    """
    Local S3 client that redirects S3 operations to local filesystem.
    Per DOC-380 Section 4.2 Pattern B.

    Maps S3 keys to local paths:
        local_path = <working_folder> / <bucket> / Key
    """

    def __init__(self, bucket: str, working_folder: str):
        self.bucket = bucket
        self.working_folder = Path(working_folder)
        self.exceptions = S3Exceptions()  # Mimic boto3 client.exceptions

    def _local_path(self, key: str) -> Path:
        """Map S3 key to local filesystem path"""
        return self.working_folder / self.bucket / key

    def put_object(self, Bucket: str, Key: str, Body: bytes, **kwargs) -> Dict[str, Any]:
        """Write object to local filesystem"""
        path = self._local_path(Key)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Handle different Body types
        if isinstance(Body, bytes):
            path.write_bytes(Body)
        elif isinstance(Body, str):
            path.write_text(Body)
        else:
            # Try to read if it's a file-like object
            path.write_bytes(Body.read() if hasattr(Body, 'read') else bytes(Body))

        return {'ETag': '"local"', 'VersionId': 'local'}

    def get_object(self, Bucket: str, Key: str, **kwargs) -> Dict[str, Any]:
        """Read object from local filesystem"""
        path = self._local_path(Key)

        if not path.exists():
            # Raise error similar to boto3
            from botocore.exceptions import ClientError
            raise ClientError(
                {'Error': {'Code': 'NoSuchKey', 'Message': f'The specified key does not exist: {Key}'}},
                'GetObject'
            )

        data = path.read_bytes()
        return {
            'Body': BodyWrapper(data),
            'ContentLength': len(data),
            'ContentType': 'application/octet-stream'
        }

    def list_objects_v2(self, Bucket: str, Prefix: str = "", **kwargs) -> Dict[str, Any]:
        """List objects with given prefix from local filesystem"""
        base_path = self.working_folder / self.bucket

        if Prefix:
            search_path = base_path / Prefix
        else:
            search_path = base_path

        contents = []

        if search_path.exists():
            if search_path.is_file():
                # Prefix points to a file
                rel_path = search_path.relative_to(base_path)
                contents.append({'Key': str(rel_path)})
            else:
                # Prefix points to a directory - list all files recursively
                for file_path in search_path.rglob('*'):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(base_path)
                        contents.append({'Key': str(rel_path)})

        return {
            'Contents': contents,
            'KeyCount': len(contents),
            'IsTruncated': False
        }

    def delete_object(self, Bucket: str, Key: str, **kwargs) -> Dict[str, Any]:
        """Delete object from local filesystem"""
        path = self._local_path(Key)

        if path.exists():
            path.unlink()

        return {'DeleteMarker': False, 'VersionId': 'local'}

    def head_object(self, Bucket: str, Key: str, **kwargs) -> Dict[str, Any]:
        """Get object metadata from local filesystem"""
        path = self._local_path(Key)

        if not path.exists():
            from botocore.exceptions import ClientError
            raise ClientError(
                {'Error': {'Code': '404', 'Message': 'Not Found'}},
                'HeadObject'
            )

        stat = path.stat()
        return {
            'ContentLength': stat.st_size,
            'ContentType': 'application/octet-stream',
            'LastModified': datetime.fromtimestamp(stat.st_mtime)
        }

    def get_paginator(self, operation_name: str):
        """Return a paginator for the given operation"""
        if operation_name == 'list_objects_v2':
            return LocalS3Paginator(self, operation_name)
        raise NotImplementedError(f"Paginator not implemented for: {operation_name}")


class LocalS3Paginator:
    """Simple paginator for local S3 client"""

    def __init__(self, client: 'LocalS3Client', operation_name: str):
        self.client = client
        self.operation_name = operation_name

    def paginate(self, **kwargs) -> List[Dict[str, Any]]:
        """Return paginated results as a list of pages"""
        if self.operation_name == 'list_objects_v2':
            # Get all results in one page
            result = self.client.list_objects_v2(**kwargs)
            return [result]
        return []


# =============================================================================
# LocalLambdaExecutor
# =============================================================================

class LocalLambdaExecutor:
    """
    Execute Lambda code locally.

    Per DOC-280 Section 5.2, this executor:
    1. Loads the handler module from project_path
    2. Invokes the handler with event
    3. Returns success, payload, logs, error

    Per DOC-380 Section 4.2 Pattern B:
    - Monkeypatches boto3.client("s3") to redirect to local filesystem
    - Restores original boto3.client after execution
    """

    def __init__(
        self,
        project_path: str,
        handler: str = "handler.lambda_handler",
        runtime: str = "python3.11",
        timeout_seconds: int = 300,
        environment: Optional[Dict[str, str]] = None,
        working_folder: Optional[str] = None
    ):
        """
        Initialize the executor.

        Args:
            project_path: Path to Lambda project (relative or absolute)
            handler: Handler reference (e.g., "handler.lambda_handler")
            runtime: Python runtime (for info only)
            timeout_seconds: Execution timeout
            environment: Environment variables to set
            working_folder: Base folder for local storage (S3 redirection)
        """
        self.project_path = project_path
        self.handler = handler
        self.runtime = runtime
        self.timeout_seconds = timeout_seconds
        self.environment = environment or {}
        self.working_folder = working_folder
        self.execution_logs: List[str] = []

        # Store original boto3.client for restoration
        self._original_boto3_client = None

    def invoke(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invoke the Lambda handler with the given event.

        Args:
            event: Lambda event payload

        Returns:
            {
                "success": bool,
                "payload": dict | None,
                "logs": list[str],
                "error": str | None
            }
        """
        self.execution_logs = []
        self._log(f"Invoking Lambda: {self.project_path}")
        self._log(f"Handler: {self.handler}")

        try:
            # Set up environment
            self._setup_environment()

            # Patch boto3 for local S3 (DOC-380 Pattern B)
            self._patch_boto3_s3()

            # Parse handler reference
            module_name, func_name = self._parse_handler(self.handler)

            # Load handler module
            handler_func = self._load_handler(module_name, func_name)

            # Create mock Lambda context
            context = self._create_context()

            # Invoke handler
            self._log(f"Executing handler with event: {json.dumps(event, default=str)[:500]}...")
            result = handler_func(event, context)

            # Parse result
            if isinstance(result, dict):
                payload = result
            else:
                payload = {"result": result}

            self._log(f"Handler completed successfully")

            return {
                "success": True,
                "payload": payload,
                "logs": self.execution_logs,
                "error": None
            }

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            self._log(f"Handler failed: {error_msg}")
            self._log(traceback.format_exc())

            return {
                "success": False,
                "payload": None,
                "logs": self.execution_logs,
                "error": error_msg
            }

        finally:
            # Restore boto3.client (DOC-380 Pattern B - must always restore)
            self._restore_boto3_s3()
            # Restore environment
            self._cleanup_environment()

    def _patch_boto3_s3(self):
        """
        Monkeypatch boto3.client to redirect S3 calls to local filesystem
        and provide credentials for Bedrock calls.
        Per DOC-380 Section 4.2 Pattern B.

        This patching:
        - Is clearly contained within LocalLambdaExecutor
        - Is reversible via _restore_boto3_s3()
        - Affects boto3.client("s3") calls -> LocalS3Client
        - Affects boto3.client("bedrock-runtime") calls -> uses aws_creds/credentials
        """
        if not self.working_folder:
            self._log("No working_folder set, skipping S3 patch")
            return

        # Store original for restoration
        self._original_boto3_client = boto3.client

        # Default bucket name
        bucket = os.environ.get('LOCAL_S3_BUCKET', 'code-transformation-v2')
        working_folder = self.working_folder

        self._log(f"Patching boto3.client for local mode")
        self._log(f"  S3 Bucket: {bucket}")
        self._log(f"  Working folder: {working_folder}")

        # Load AWS credentials for Bedrock access
        aws_creds = self._load_aws_credentials()
        if aws_creds:
            self._log(f"  Bedrock credentials loaded from aws_creds/credentials")
        else:
            self._log(f"  Bedrock credentials: using default boto3 chain")

        # Create the patched client function
        original_client = self._original_boto3_client

        def patched_client(service_name, *args, **kwargs):
            if service_name == 's3':
                return LocalS3Client(bucket=bucket, working_folder=working_folder)
            elif service_name in ('bedrock-runtime', 'bedrock-agent-runtime'):
                # Use loaded credentials for Bedrock
                if aws_creds:
                    # Ensure region is set
                    if 'region_name' not in kwargs:
                        kwargs['region_name'] = aws_creds.get('region', 'us-east-1')
                    return original_client(
                        service_name,
                        *args,
                        aws_access_key_id=aws_creds['access_key'],
                        aws_secret_access_key=aws_creds['secret_key'],
                        **kwargs
                    )
                else:
                    return original_client(service_name, *args, **kwargs)
            # For all other services, use original boto3.client
            return original_client(service_name, *args, **kwargs)

        # Apply the patch
        boto3.client = patched_client

    def _load_aws_credentials(self) -> Optional[Dict[str, str]]:
        """
        Load AWS credentials from database (primary) or files (fallback).
        """
        # Try database first
        try:
            from migrate_dynamodb.dynamodb_credentials import get_credentials

            creds = get_credentials()
            if creds:
                return {
                    'access_key': creds.aws_access_key_id,
                    'secret_key': creds.aws_secret_access_key,
                    'region': creds.region or 'us-east-1'
                }
        except Exception as e:
            self._log(f"Warning: Could not load credentials from database: {e}")

        # Fall back to files (legacy)
        from pathlib import Path
        local_creds = Path("aws_creds/credentials")
        if not local_creds.exists():
            repo_root = Path(__file__).parent.parent
            local_creds = repo_root / "aws_creds" / "credentials"

        if local_creds.exists():
            try:
                with open(local_creds, 'r') as f:
                    lines = f.readlines()
                    aws_access_key_id = None
                    aws_secret_access_key = None
                    region = 'us-east-1'

                    for line in lines:
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()

                            if key == 'aws_access_key_id':
                                aws_access_key_id = value
                            elif key == 'aws_secret_access_key':
                                aws_secret_access_key = value
                            elif key == 'region':
                                region = value

                    if aws_access_key_id and aws_secret_access_key:
                        return {
                            'access_key': aws_access_key_id,
                            'secret_key': aws_secret_access_key,
                            'region': region
                        }
            except Exception as e:
                self._log(f"Warning: Could not load aws_creds/credentials: {e}")

        return None

    def _restore_boto3_s3(self):
        """
        Restore original boto3.client after Lambda execution.
        Per DOC-380 Section 4.2 Pattern B.
        """
        if self._original_boto3_client is not None:
            boto3.client = self._original_boto3_client
            self._original_boto3_client = None
            self._log("Restored original boto3.client")

    def _log(self, message: str):
        """Add a log entry"""
        timestamp = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        self.execution_logs.append(log_entry)
        logger.debug(log_entry)

    def _parse_handler(self, handler: str) -> tuple:
        """Parse handler reference into module and function names"""
        parts = handler.rsplit('.', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid handler format: {handler}. Expected 'module.function'")
        return parts[0], parts[1]

    def _setup_environment(self):
        """Set up environment variables and Python path"""
        # Store original values
        self._original_env = {}
        self._original_path = sys.path.copy()

        # Set environment variables
        for key, value in self.environment.items():
            self._original_env[key] = os.environ.get(key)
            os.environ[key] = value

        # Set working folder for S3 redirection
        if self.working_folder:
            self._original_env['LOCAL_STORAGE_PATH'] = os.environ.get('LOCAL_STORAGE_PATH')
            os.environ['LOCAL_STORAGE_PATH'] = self.working_folder

        # Add project path to Python path
        project_abs = self._resolve_project_path()
        if project_abs not in sys.path:
            sys.path.insert(0, project_abs)
            self._log(f"Added to sys.path: {project_abs}")

    def _cleanup_environment(self):
        """Restore original environment"""
        # Restore environment variables
        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        # Restore Python path
        sys.path = self._original_path

    def _resolve_project_path(self) -> str:
        """Resolve project path to absolute path"""
        path = Path(self.project_path)

        if path.is_absolute():
            return str(path)

        # Try relative to current working directory
        cwd_path = Path.cwd() / path
        if cwd_path.exists():
            return str(cwd_path)

        # Try relative to this file's directory
        module_dir = Path(__file__).parent.parent
        repo_path = module_dir / path
        if repo_path.exists():
            return str(repo_path)

        raise FileNotFoundError(f"Project path not found: {self.project_path}")

    def _load_handler(self, module_name: str, func_name: str):
        """Load the handler function from the module"""
        project_abs = self._resolve_project_path()

        # Build module path
        module_file = os.path.join(project_abs, f"{module_name}.py")
        if not os.path.exists(module_file):
            raise FileNotFoundError(f"Handler module not found: {module_file}")

        self._log(f"Loading module: {module_file}")

        # Load module dynamically
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if not spec or not spec.loader:
            raise ImportError(f"Failed to load module spec: {module_file}")

        module = importlib.util.module_from_spec(spec)

        # Add to sys.modules to handle relative imports
        sys.modules[module_name] = module

        # Execute the module
        spec.loader.exec_module(module)

        # Get handler function
        if not hasattr(module, func_name):
            raise AttributeError(f"Handler function '{func_name}' not found in module")

        return getattr(module, func_name)

    def _create_context(self):
        """Create a mock Lambda context object"""
        return MockLambdaContext(
            function_name=self.handler,
            timeout_seconds=self.timeout_seconds
        )

    def get_logs(self) -> List[str]:
        """Get execution logs"""
        return self.execution_logs


class MockLambdaContext:
    """Mock AWS Lambda context object"""

    def __init__(self, function_name: str, timeout_seconds: int = 300):
        self.function_name = function_name
        self.function_version = "$LATEST"
        self.invoked_function_arn = f"arn:aws:lambda:local:000000000000:function:{function_name}"
        self.memory_limit_in_mb = 512
        self.aws_request_id = f"local-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        self.log_group_name = f"/aws/lambda/{function_name}"
        self.log_stream_name = f"{datetime.utcnow().strftime('%Y/%m/%d')}/[$LATEST]{self.aws_request_id}"
        self._timeout_seconds = timeout_seconds
        self._start_time = datetime.utcnow()

    def get_remaining_time_in_millis(self) -> int:
        """Get remaining execution time in milliseconds"""
        elapsed = (datetime.utcnow() - self._start_time).total_seconds()
        remaining = max(0, self._timeout_seconds - elapsed)
        return int(remaining * 1000)
