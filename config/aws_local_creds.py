"""
AWS credentials setup for boto3.

Reads credentials from SQLite database (primary) or falls back to files.
Sets environment variables so boto3 uses these credentials.
"""

from pathlib import Path
import os


def setup_local_aws_creds(profile_name: str = "default") -> None:
    """
    Set up AWS credentials for boto3.

    Priority:
    1. Database (data/jobs.db -> aws_credentials table)
    2. Files (aws_creds/credentials) - legacy fallback

    Sets AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
    environment variables for boto3 to use.

    Note: profile_name kept for legacy file fallback only.
    Database stores only ONE set of credentials.
    """
    # Skip if already set externally (e.g., IAM roles, CI/CD)
    if os.environ.get("AWS_ACCESS_KEY_ID"):
        return

    # Try database first (single credentials, no profile)
    if _setup_from_database():
        return

    # Fall back to files (legacy)
    _setup_from_files(profile_name)


def _setup_from_database() -> bool:
    """
    Load credentials from database.

    Returns True if successful, False otherwise.
    """
    try:
        # Import here to avoid circular imports during startup
        from migrate_dynamodb.dynamodb_credentials import get_credentials

        creds = get_credentials()
        if creds is None:
            return False

        # Set environment variables for boto3
        os.environ["AWS_ACCESS_KEY_ID"] = creds.aws_access_key_id
        os.environ["AWS_SECRET_ACCESS_KEY"] = creds.aws_secret_access_key
        os.environ["AWS_DEFAULT_REGION"] = creds.region or "us-east-1"

        print("[aws_creds] Loaded from database")
        return True

    except Exception as e:
        # Database not ready or other error - fall through to files
        print(f"[aws_creds] Database load failed: {e}")
        return False


def _setup_from_files(profile_name: str) -> bool:
    """
    Load credentials from aws_creds/ files (legacy fallback).

    Returns True if successful, False otherwise.
    """
    base_dir = Path(__file__).resolve().parent.parent  # modernizeit-api/
    aws_creds_dir = base_dir / "aws_creds"
    credentials_file = aws_creds_dir / "credentials"
    config_file = aws_creds_dir / "config"

    if not credentials_file.exists():
        print("[aws_creds] No credentials found (database or files)")
        return False

    # Point boto3 to local files
    os.environ.setdefault("AWS_SHARED_CREDENTIALS_FILE", str(credentials_file))
    if config_file.exists():
        os.environ.setdefault("AWS_CONFIG_FILE", str(config_file))
    os.environ.setdefault("AWS_PROFILE", profile_name)

    print(f"[aws_creds] Loaded from files (profile: {profile_name})")
    return True
