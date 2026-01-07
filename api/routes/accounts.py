"""
Accounts API routes.

Multi-tenant account management with S3 configuration.
Syncs account settings from UI (Electron/Portal) to API.
"""

from fastapi import APIRouter, HTTPException

from api.models.accounts import (
    AccountRequest,
    AccountResponse,
    AccountListResponse,
    AccountSyncResponse,
    AccountDeleteResponse,
    S3ConfigResponse
)
from migrate_dynamodb.dynamodb_accounts import (
    Account,
    init_accounts_table,
    save_account,
    get_account,
    list_accounts as get_all_accounts,
    delete_account,
    get_account_s3_config
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("/sync", response_model=AccountSyncResponse)
async def sync_account(request: AccountRequest) -> AccountSyncResponse:
    """
    Sync account settings from UI to API.

    POST /accounts/sync

    Called by Electron/Portal after saving account to local SQLite.
    Upserts account - creates if new, updates if exists.
    """
    try:
        # Ensure table exists
        init_accounts_table()

        account = Account(
            account_id=request.account_id,
            name=request.name,
            description=request.description,
            is_default=request.is_default,
            storage_type=request.storage_type,
            s3_bucket=request.s3_bucket,
            s3_region=request.s3_region,
            s3_prefix=request.s3_prefix
        )
        saved = save_account(account)

        return AccountSyncResponse(
            success=True,
            message=f"Account '{request.account_id}' synced successfully",
            account=AccountResponse(
                account_id=saved.account_id,
                name=saved.name,
                description=saved.description,
                is_default=saved.is_default,
                storage_type=saved.storage_type,
                s3_bucket=saved.s3_bucket,
                s3_region=saved.s3_region,
                s3_prefix=saved.s3_prefix,
                created_at=saved.created_at,
                updated_at=saved.updated_at
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=AccountListResponse)
async def list_accounts() -> AccountListResponse:
    """
    List all accounts.

    GET /accounts
    """
    try:
        init_accounts_table()
        accounts = get_all_accounts()

        return AccountListResponse(
            accounts=[
                AccountResponse(
                    account_id=a.account_id,
                    name=a.name,
                    description=a.description,
                    is_default=a.is_default,
                    storage_type=a.storage_type,
                    s3_bucket=a.s3_bucket,
                    s3_region=a.s3_region,
                    s3_prefix=a.s3_prefix,
                    created_at=a.created_at,
                    updated_at=a.updated_at
                )
                for a in accounts
            ],
            total=len(accounts)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account_by_id(account_id: str) -> AccountResponse:
    """
    Get a single account by ID.

    GET /accounts/{account_id}
    """
    try:
        init_accounts_table()
        account = get_account(account_id)

        if account is None:
            raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")

        return AccountResponse(
            account_id=account.account_id,
            name=account.name,
            description=account.description,
            is_default=account.is_default,
            storage_type=account.storage_type,
            s3_bucket=account.s3_bucket,
            s3_region=account.s3_region,
            s3_prefix=account.s3_prefix,
            created_at=account.created_at,
            updated_at=account.updated_at
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}/s3", response_model=S3ConfigResponse)
async def get_account_s3(account_id: str) -> S3ConfigResponse:
    """
    Get S3 configuration for an account.

    GET /accounts/{account_id}/s3

    Used by flows to determine S3 bucket/region/prefix for an account.
    """
    try:
        init_accounts_table()
        config = get_account_s3_config(account_id)

        if config is None:
            # Return empty config if account not found
            return S3ConfigResponse(
                account_id=account_id,
                configured=False
            )

        return S3ConfigResponse(
            account_id=account_id,
            storage_type=config["storage_type"],
            s3_bucket=config["s3_bucket"],
            s3_region=config["s3_region"],
            s3_prefix=config["s3_prefix"],
            configured=config["s3_bucket"] is not None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{account_id}", response_model=AccountDeleteResponse)
async def delete_account_by_id(account_id: str) -> AccountDeleteResponse:
    """
    Delete an account by ID.

    DELETE /accounts/{account_id}
    """
    try:
        init_accounts_table()
        deleted = delete_account(account_id)

        if not deleted:
            raise HTTPException(status_code=404, detail=f"Account '{account_id}' not found")

        return AccountDeleteResponse(
            success=True,
            message=f"Account '{account_id}' deleted"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
