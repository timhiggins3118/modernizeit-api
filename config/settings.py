"""
Central configuration module for ModernizeIT API.

Provides a Settings class that reads configuration with the following priority:
1. Environment variables (optional override)
2. config/app_settings.json (primary config file)
3. Default fallbacks
"""

import json
import os
from pathlib import Path
from typing import Optional

from config.aws_local_creds import setup_local_aws_creds

# Set up local AWS credentials before any boto3 clients are created.
# Uses "default" profile since aws_creds/config and aws_creds/credentials use [default].
setup_local_creds_profile = "default"  # keep this in sync with aws_creds profile name
setup_local_aws_creds(profile_name=setup_local_creds_profile)

# Project root is the parent of the config/ directory
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings:
    """
    Application settings.

    Resolution order:
    1. Environment variables (optional override)
    2. config/app_settings.json
    3. Default values

    Supported settings:
    - base_local_path: Base path for all local outputs
    - bedrock_mode: "real" or "mock" (default: "real")
    - bedrock_region: AWS region for Bedrock (default: "us-east-1")
    - storage_mode: "local" or "s3" (default: "local")
    - s3_bucket: S3 bucket name for storage_mode="s3"
    - s3_prefix: S3 key prefix (default: "modernizeit_output")
    """

    def __init__(self):
        # Load config file once
        self._config_data = self._load_config_file()

        # Resolve all settings
        self.base_local_path = self._resolve_base_local_path()
        self.bedrock_mode = self._resolve_bedrock_mode()
        self.bedrock_region = self._resolve_bedrock_region()

        # MongoDB settings
        self.mongodb_uri = self._resolve_mongodb_uri()
        self.mongodb_database = self._resolve_mongodb_database()

        # Storage settings (local or S3)
        self.storage_mode = self._resolve_storage_mode()
        self.s3_bucket = self._resolve_s3_bucket()
        self.s3_prefix = self._resolve_s3_prefix()
        self.s3_region = self._resolve_s3_region()

        # Data provider settings (dynamodb, sqlite, mongodb)
        self.data_provider = self._resolve_data_provider()
        self.account_id = self._resolve_account_id()
        self.aws_region = self._resolve_aws_region()

    def _load_config_file(self) -> dict:
        """Load config/app_settings.json if it exists."""
        config_path = PROJECT_ROOT / "config" / "app_settings.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"[settings] Warning: Failed to load {config_path}: {e}")
        return {}

    def _resolve_base_local_path(self) -> Path:
        """
        Resolve base_local_path from env var, config file, or default.

        Returns:
            Resolved absolute Path for base_local_path
        """
        # Priority 1: Environment variable
        env_val = os.getenv("MODERNIZEIT_BASE_LOCAL_PATH")
        if env_val:
            return self._resolve_path(env_val)

        # Priority 2: Config file
        if "base_local_path" in self._config_data:
            return self._resolve_path(self._config_data["base_local_path"])

        # Priority 3: Default fallback
        return (PROJECT_ROOT / "output").resolve()

    def _resolve_bedrock_mode(self) -> str:
        """
        Resolve bedrock_mode from env var, config file, or default.

        Returns:
            "real" or "mock" (default: "real")
        """
        # Priority 1: Environment variable BEDROCK_MODE
        env_val = os.getenv("BEDROCK_MODE")
        if env_val:
            mode = env_val.lower().strip()
            if mode in ("real", "mock"):
                return mode
            print(f"[settings] Warning: Invalid BEDROCK_MODE '{env_val}', using 'real'")

        # Priority 2: Config file
        if "bedrock_mode" in self._config_data:
            mode = str(self._config_data["bedrock_mode"]).lower().strip()
            if mode in ("real", "mock"):
                return mode
            print(f"[settings] Warning: Invalid bedrock_mode in config, using 'real'")

        # Priority 3: Default to REAL (not mock!)
        return "real"

    def _resolve_bedrock_region(self) -> str:
        """
        Resolve bedrock_region from env var, config file, or default.

        Returns:
            AWS region string (default: "us-east-1")
        """
        # Priority 1: Environment variable BEDROCK_REGION
        env_val = os.getenv("BEDROCK_REGION")
        if env_val:
            return env_val.strip()

        # Priority 2: Config file
        if "bedrock_region" in self._config_data:
            return str(self._config_data["bedrock_region"]).strip()

        # Priority 3: Default
        return "us-east-1"

    def _resolve_data_provider(self) -> str:
        """
        Resolve data_provider from env var, config file, or default.

        Returns:
            "dynamodb", "sqlite", or "mongodb" (default: "dynamodb")
        """
        # Priority 1: Environment variable
        env_val = os.getenv("DATA_PROVIDER")
        if env_val:
            provider = env_val.lower().strip()
            if provider in ("dynamodb", "sqlite", "mongodb"):
                return provider
            print(f"[settings] Warning: Invalid DATA_PROVIDER '{env_val}', using 'dynamodb'")

        # Priority 2: Config file
        if "data_provider" in self._config_data:
            provider = str(self._config_data["data_provider"]).lower().strip()
            if provider in ("dynamodb", "sqlite", "mongodb"):
                return provider
            print(f"[settings] Warning: Invalid data_provider in config, using 'dynamodb'")

        # Priority 3: Default
        return "dynamodb"

    def _resolve_account_id(self) -> str:
        """
        Resolve account_id from env var, config file, or default.

        This is the account ID used for DynamoDB table prefixes.

        Returns:
            Account ID string (default: "341")
        """
        # Priority 1: Environment variable
        env_val = os.getenv("ACCOUNT_ID")
        if env_val:
            return env_val.strip()

        # Priority 2: Config file
        if "account_id" in self._config_data:
            return str(self._config_data["account_id"]).strip()

        # Priority 3: Default (the Live Portal account)
        return "341"

    def _resolve_aws_region(self) -> str:
        """
        Resolve aws_region from env var, config file, or default.

        Used for DynamoDB and other AWS services.

        Returns:
            AWS region string (default: "us-east-1")
        """
        # Priority 1: Environment variable
        env_val = os.getenv("AWS_REGION")
        if env_val:
            return env_val.strip()

        # Priority 2: Config file
        if "aws_region" in self._config_data:
            return str(self._config_data["aws_region"]).strip()

        # Priority 3: Default
        return "us-east-1"

    def _resolve_path(self, value: str) -> Path:
        """
        Resolve a path value (absolute or relative).

        Args:
            value: Path string from config or env var

        Returns:
            Resolved absolute Path
        """
        path = Path(value)
        if path.is_absolute():
            return path.expanduser().resolve()
        else:
            # Relative paths are resolved relative to PROJECT_ROOT
            return (PROJECT_ROOT / value).resolve()

    def _resolve_mongodb_uri(self) -> str:
        """
        Resolve MongoDB URI from env var, config file, or default.

        For Atlas: mongodb+srv://user:pass@cluster.mongodb.net
        For local: mongodb://localhost:27017

        Returns:
            MongoDB connection URI
        """
        # Priority 1: Environment variable
        env_val = os.getenv("MONGODB_URI")
        if env_val:
            return env_val.strip()

        # Priority 2: Config file
        if "mongodb_uri" in self._config_data:
            return str(self._config_data["mongodb_uri"]).strip()

        # Priority 3: Default (local)
        return "mongodb://localhost:27017"

    def _resolve_mongodb_database(self) -> str:
        """
        Resolve MongoDB database name from env var, config file, or default.

        Returns:
            Database name (default: "modernizeit")
        """
        # Priority 1: Environment variable
        env_val = os.getenv("MONGODB_DATABASE")
        if env_val:
            return env_val.strip()

        # Priority 2: Config file
        if "mongodb_database" in self._config_data:
            return str(self._config_data["mongodb_database"]).strip()

        # Priority 3: Default
        return "modernizeit"

    def _resolve_storage_mode(self) -> str:
        """
        Resolve storage_mode from env var, config file, or default.

        Returns:
            "local" or "s3" (default: "local")
        """
        # Priority 1: Environment variable
        env_val = os.getenv("STORAGE_MODE")
        if env_val:
            mode = env_val.lower().strip()
            if mode in ("local", "s3"):
                return mode
            print(f"[settings] Warning: Invalid STORAGE_MODE '{env_val}', using 'local'")

        # Priority 2: Config file
        if "storage_mode" in self._config_data:
            mode = str(self._config_data["storage_mode"]).lower().strip()
            if mode in ("local", "s3"):
                return mode
            print(f"[settings] Warning: Invalid storage_mode in config, using 'local'")

        # Priority 3: Default
        return "local"

    def _resolve_s3_bucket(self) -> Optional[str]:
        """
        Resolve S3 bucket name from env var or config file.

        Returns:
            S3 bucket name or None if not configured
        """
        # Priority 1: Environment variable
        env_val = os.getenv("S3_BUCKET")
        if env_val:
            return env_val.strip()

        # Priority 2: Config file
        if "s3_bucket" in self._config_data:
            return str(self._config_data["s3_bucket"]).strip()

        return None

    def _resolve_s3_prefix(self) -> str:
        """
        Resolve S3 key prefix from env var, config file, or default.

        Returns:
            S3 key prefix (default: "modernizeit_output")
        """
        # Priority 1: Environment variable
        env_val = os.getenv("S3_PREFIX")
        if env_val:
            return env_val.strip().strip("/")

        # Priority 2: Config file
        if "s3_prefix" in self._config_data:
            return str(self._config_data["s3_prefix"]).strip().strip("/")

        # Priority 3: Default
        return "modernizeit_output"

    def _resolve_s3_region(self) -> str:
        """
        Resolve S3 region from env var, config file, or default.

        Returns:
            AWS region for S3 (default: "us-east-1")
        """
        # Priority 1: Environment variable
        env_val = os.getenv("S3_REGION")
        if env_val:
            return env_val.strip()

        # Priority 2: Config file
        if "s3_region" in self._config_data:
            return str(self._config_data["s3_region"]).strip()

        # Priority 3: Default
        return "us-east-1"


# Singleton instance
settings = Settings()

# One-time startup log
print(f"[settings] base_local_path = {settings.base_local_path}")
print(f"[settings] bedrock_mode = {settings.bedrock_mode}")
print(f"[settings] bedrock_region = {settings.bedrock_region}")
print(f"[settings] mongodb_database = {settings.mongodb_database}")
print(f"[settings] storage_mode = {settings.storage_mode}")
if settings.storage_mode == "s3":
    print(f"[settings] s3_bucket = {settings.s3_bucket}")
    print(f"[settings] s3_prefix = {settings.s3_prefix}")
    print(f"[settings] s3_region = {settings.s3_region}")
print(f"[settings] data_provider = {settings.data_provider}")
print(f"[settings] account_id = {settings.account_id}")
print(f"[settings] aws_region = {settings.aws_region}")
# Don't log full URI (may contain credentials)
