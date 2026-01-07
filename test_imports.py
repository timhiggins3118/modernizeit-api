#!/usr/bin/env python3
"""Quick test to verify DynamoDB imports work."""

print("Testing DynamoDB imports...")

try:
    from migrate_dynamodb.dynamodb_jobs import save_job, get_job, list_jobs, JobRecord
    print("✅ dynamodb_jobs imports successful")
except Exception as e:
    print(f"❌ dynamodb_jobs import failed: {e}")
    exit(1)

try:
    from migrate_dynamodb.dynamodb_accounts import (
        save_account, get_account, list_accounts,
        get_account_s3_config, Account
    )
    print("✅ dynamodb_accounts imports successful")
except Exception as e:
    print(f"❌ dynamodb_accounts import failed: {e}")
    exit(1)

try:
    from main import app
    print("✅ FastAPI app imports successful")

    routes_count = len([r for r in app.routes if hasattr(r, 'path')])
    print(f"✅ API has {routes_count} routes registered")

except Exception as e:
    print(f"❌ FastAPI app import failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n🎸 All imports successful! API ready to rock!")
