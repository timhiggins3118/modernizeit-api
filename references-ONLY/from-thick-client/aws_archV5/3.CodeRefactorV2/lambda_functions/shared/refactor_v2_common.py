"""
Code Refactor V2 - Common Utilities

Provides shared job context and path helpers for all Refactor V2 Lambdas.
Mirrors the pattern used by Code Analysis V3 for consistency.

Usage:
    from shared.refactor_v2_common import get_refactor_job_context

    def lambda_handler(event, context):
        job_ctx = get_refactor_job_context(event)
        bucket = job_ctx.bucket_name
        job_root = job_ctx.job_root
        # ...
"""

import os
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class RefactorJobContext:
    """
    Job context for Code Refactor V2 workflows.

    Contains all the fields needed to locate S3 objects and construct paths.
    Mirrors the event structure used by Code Analysis V3.
    """
    scout_account_id: str
    application_name: str
    job_id: str
    source_hash: str
    bucket_name: str

    @property
    def job_root(self) -> str:
        """
        S3 prefix for this job's files.

        Pattern: code-transformation-v2/{scout_account_id}/{application_name}/code_refactor_v2/jobs/{job_id}

        Example:
            0U812/TestApp01/code_refactor_v2/jobs/rf2_job_0U812_TestApp01_1762439638_48cf051e
        """
        return f"{self.scout_account_id}/{self.application_name}/code_refactor_v2/jobs/{self.job_id}"

    @property
    def base_path(self) -> str:
        """
        Base S3 prefix for the account/application.

        Pattern: {scout_account_id}/{application_name}
        """
        return f"{self.scout_account_id}/{self.application_name}"

    @property
    def artifacts_prefix(self) -> str:
        """S3 prefix for job artifacts (outputs)."""
        return f"{self.job_root}/artifacts"

    @property
    def catalog_prefix(self) -> str:
        """S3 prefix for classified catalog."""
        return f"{self.base_path}/shared/catalogs/{self.source_hash}"

    @property
    def uploads_prefix(self) -> str:
        """S3 prefix for uploaded source files."""
        return f"{self.base_path}/shared/uploads/{self.source_hash}/extracted"

    def get_catalog_key(self) -> str:
        """Full S3 key for classified_catalog.json."""
        return f"{self.catalog_prefix}/classified_catalog.json"

    def get_file_key(self, file_path: str) -> str:
        """Full S3 key for a source file."""
        return f"{self.uploads_prefix}/{file_path}"

    def get_artifact_key(self, filename: str) -> str:
        """Full S3 key for an artifact file."""
        return f"{self.artifacts_prefix}/{filename}"

    def get_batch_key(self, batch_type: str, batch_id: int) -> str:
        """Full S3 key for a batch output file."""
        return f"{self.artifacts_prefix}/{batch_type}/batch_{batch_id}.json"


def get_refactor_job_context(event: Dict[str, Any]) -> RefactorJobContext:
    """
    Build RefactorJobContext from Lambda event.

    Mirrors the way Code Analysis V3 resolves job context:
    - Read scout_account_id, application_name, job_id, source_hash from event
    - Read bucket_name from environment or use default

    Args:
        event: Lambda event dict with job parameters

    Returns:
        RefactorJobContext with all fields populated

    Raises:
        ValueError: If required fields are missing from event
    """
    # Extract required fields from event
    job_id = event.get('job_id')
    scout_account_id = event.get('scout_account_id')
    application_name = event.get('application_name')
    source_hash = event.get('source_hash')

    # Validate required fields
    missing = []
    if not job_id:
        missing.append('job_id')
    if not scout_account_id:
        missing.append('scout_account_id')
    if not application_name:
        missing.append('application_name')
    if not source_hash:
        missing.append('source_hash')

    if missing:
        raise ValueError(f"Missing required fields in event: {', '.join(missing)}")

    # Get bucket name from environment or use default
    # This allows configuration without code changes
    bucket_name = os.environ.get('S3_BUCKET_NAME', 'code-transformation-v2')

    return RefactorJobContext(
        scout_account_id=scout_account_id,
        application_name=application_name,
        job_id=job_id,
        source_hash=source_hash,
        bucket_name=bucket_name
    )


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """
    Build standard error response.

    Args:
        status_code: HTTP status code
        message: Error message

    Returns:
        Dict with statusCode and body.error
    """
    return {
        'statusCode': status_code,
        'body': {
            'error': message
        }
    }
