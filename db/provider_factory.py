"""
Provider Factory - Returns the appropriate data provider based on configuration.

Usage:
    from db.provider_factory import get_provider

    provider = get_provider()
    apps = provider.list_applications()

The factory reads from settings to determine which backend to use:
    - DATA_PROVIDER = "dynamodb"  -> DynamoDBProvider
    - DATA_PROVIDER = "sqlite"    -> SQLiteProvider (future)
    - DATA_PROVIDER = "mongodb"   -> MongoDBProvider (future)

Created: December 31, 2025
"""

from typing import Optional

from db.base_provider import BaseDataProvider


# Cache the provider instance (singleton per config)
_provider_instance: Optional[BaseDataProvider] = None


def get_provider(
    provider_type: Optional[str] = None,
    account_id: Optional[str] = None,
    **kwargs
) -> BaseDataProvider:
    """
    Get the configured data provider.

    Args:
        provider_type: Override provider type (default: from settings)
        account_id: Override account ID (default: from settings)
        **kwargs: Additional provider-specific arguments

    Returns:
        BaseDataProvider implementation

    Raises:
        ValueError: If provider type is not supported
    """
    global _provider_instance

    # Import settings here to avoid circular imports
    from config.settings import settings

    # Determine provider type
    p_type = provider_type or getattr(settings, 'data_provider', 'dynamodb')
    acct_id = account_id or getattr(settings, 'account_id', '341')

    # Check if we can reuse cached instance
    if _provider_instance is not None:
        # If same config, return cached
        info = _provider_instance.get_provider_info()
        if info.get('provider') == p_type:
            if p_type == 'dynamodb' and info.get('account_id') == acct_id:
                return _provider_instance

    # Create new provider based on type
    if p_type == 'dynamodb':
        from db.dynamodb_provider import DynamoDBProvider
        region = kwargs.get('region', getattr(settings, 'aws_region', 'us-east-1'))
        _provider_instance = DynamoDBProvider(account_id=acct_id, region=region)

    elif p_type == 'local' or p_type == 'sqlite':
        from db.local_provider import LocalProvider
        db_path = kwargs.get('db_path', None)
        _provider_instance = LocalProvider(account_id=acct_id, db_path=db_path)

    elif p_type == 'mongodb':
        # Future implementation
        raise NotImplementedError("MongoDB provider not yet implemented")

    else:
        raise ValueError(f"Unknown provider type: {p_type}")

    return _provider_instance


def reset_provider():
    """
    Reset the cached provider instance.

    Useful for testing or when changing configuration.
    """
    global _provider_instance
    _provider_instance = None


def get_provider_for_account(account_id: str, **kwargs) -> BaseDataProvider:
    """
    Get a provider for a specific account (bypasses cache).

    Useful when you need to access a different account's data.

    Args:
        account_id: The account ID
        **kwargs: Additional provider arguments

    Returns:
        BaseDataProvider for the specified account
    """
    from config.settings import settings

    p_type = kwargs.get('provider_type', getattr(settings, 'data_provider', 'dynamodb'))

    if p_type == 'dynamodb':
        from db.dynamodb_provider import DynamoDBProvider
        region = kwargs.get('region', getattr(settings, 'aws_region', 'us-east-1'))
        return DynamoDBProvider(account_id=account_id, region=region)

    elif p_type == 'local' or p_type == 'sqlite':
        from db.local_provider import LocalProvider
        db_path = kwargs.get('db_path', None)
        return LocalProvider(account_id=account_id, db_path=db_path)

    else:
        raise ValueError(f"Unknown provider type: {p_type}")
