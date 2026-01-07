"""
Code Refactor V2 - AI Configuration

Provides AI configuration for direct Bedrock model invocation.
Uses the same pattern as Code Analysis V3: bedrock-runtime.invoke_model()

For local execution, the config is read from environment variables.
For AWS Lambda execution, can be extended to read from DynamoDB/Parameter Store.

Usage:
    from shared.ai_config import get_ai_config

    def lambda_handler(event, context):
        ai_cfg = get_ai_config()
        # Use ai_cfg.model_id, ai_cfg.region, etc.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AIConfig:
    """
    AI configuration for direct Bedrock model invocation.

    Attributes:
        provider: AI provider name (e.g., "bedrock")
        region: AWS region for Bedrock
        model_id: Model ID for invoke_model calls
    """
    provider: str
    region: str
    model_id: str

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.model_id:
            logger.warning(
                "Bedrock model ID not configured. "
                "Set BEDROCK_MODEL_ID environment variable."
            )


# Default configuration values (same as Code Analysis V3)
DEFAULT_REGION = 'us-east-1'
DEFAULT_MODEL_ID = 'us.anthropic.claude-3-5-sonnet-20241022-v2:0'


def get_ai_config() -> AIConfig:
    """
    Load AI configuration from environment variables.

    Environment variables:
        AWS_REGION: AWS region (default: us-east-1)
        BEDROCK_MODEL_ID: Model ID for direct invocation

    Returns:
        AIConfig with all settings populated
    """
    config = AIConfig(
        provider='bedrock',
        region=os.environ.get('AWS_REGION', DEFAULT_REGION),
        model_id=os.environ.get('BEDROCK_MODEL_ID', DEFAULT_MODEL_ID)
    )

    logger.info(
        "AI config loaded for Refactor V2",
        extra={
            "provider": config.provider,
            "region": config.region,
            "model_id": config.model_id
        }
    )

    return config


def get_ai_config_from_db(
    scout_account_id: Optional[str] = None,
    application_name: Optional[str] = None
) -> AIConfig:
    """
    Load AI configuration from SQLite database.

    This is used for local execution where settings are stored in modernizeit.db.
    Falls back to environment variables if database is not available.

    Args:
        scout_account_id: Optional account ID for account-specific config
        application_name: Optional application name for app-specific config

    Returns:
        AIConfig with settings from database or environment fallback
    """
    try:
        # Try to import database manager for local execution
        from src.database.db_manager import get_db_manager

        db = get_db_manager()

        # Get region
        result = db.fetch_one(
            "SELECT value FROM settings WHERE key = ? AND category = ?",
            ("aws_region", "ai_config")
        )
        region = result['value'] if result else DEFAULT_REGION

        # Get model ID
        result = db.fetch_one(
            "SELECT value FROM settings WHERE key = ? AND category = ?",
            ("bedrock_model_id", "ai_config")
        )
        model_id = result['value'] if result else DEFAULT_MODEL_ID

        config = AIConfig(
            provider='bedrock',
            region=region,
            model_id=model_id
        )

        logger.info(
            "AI config loaded from database for Refactor V2",
            extra={
                "provider": config.provider,
                "region": config.region,
                "model_id": config.model_id,
                "source": "database"
            }
        )

        return config

    except ImportError:
        logger.info("Database not available, using environment config")
        return get_ai_config()
    except Exception as e:
        logger.warning(f"Failed to load AI config from database: {e}, using environment config")
        return get_ai_config()
