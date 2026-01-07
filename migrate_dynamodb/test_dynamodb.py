"""
Test script for DynamoDB modules.

Tests jobs and accounts CRUD operations.

Usage:
    python3 test_dynamodb.py
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from migrate_dynamodb.dynamodb_jobs import DynamoDBJobsProvider, JobRecord
from migrate_dynamodb.dynamodb_accounts import DynamoDBAccountsProvider, Account


def test_jobs():
    """Test jobs CRUD operations."""
    print("\n" + "="*60)
    print("TESTING JOBS MODULE")
    print("="*60)

    provider = DynamoDBJobsProvider()
    print(f"✓ Using table: {provider.table_name}")

    # Create test job
    job_id = "test_job_341_TestApp_20260106_test123"
    record = JobRecord(
        job_id=job_id,
        flow_type="code_analysis_v3",
        status="running",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        artifacts_path="s3://modernizeit-artifacts/341/TestApp/test",
        input_json=json.dumps({
            "scout_account_id": "341",
            "application_name": "TestApp",
            "files": ["test.cbl"]
        }),
        tenant_id="341",
        application_name="TestApp"
    )

    # Save job
    print(f"\n1. Saving job: {job_id}")
    try:
        provider.save_job(record)
        print("   ✓ Job saved successfully")
    except Exception as e:
        print(f"   ✗ Error saving job: {e}")
        return False

    # Get job
    print(f"\n2. Retrieving job: {job_id}")
    try:
        retrieved = provider.get_job(job_id, tenant_id="341")
        if retrieved:
            print(f"   ✓ Job retrieved successfully")
            print(f"   - Flow Type: {retrieved.flow_type}")
            print(f"   - Status: {retrieved.status}")
            print(f"   - Tenant: {retrieved.tenant_id}")
            print(f"   - Application: {retrieved.application_name}")
        else:
            print("   ✗ Job not found")
            return False
    except Exception as e:
        print(f"   ✗ Error retrieving job: {e}")
        return False

    # Update job status
    print(f"\n3. Updating job status to 'completed'")
    try:
        record.status = "completed"
        record.updated_at = datetime.utcnow()
        provider.save_job(record)
        print("   ✓ Job updated successfully")
    except Exception as e:
        print(f"   ✗ Error updating job: {e}")
        return False

    # List jobs
    print(f"\n4. Listing jobs for tenant 341")
    try:
        jobs = provider.list_jobs(account_id="341", limit=10)
        print(f"   ✓ Found {len(jobs)} jobs")
        for job in jobs[:3]:  # Show first 3
            print(f"   - {job.job_id} ({job.flow_type}) - {job.status}")
    except Exception as e:
        print(f"   ✗ Error listing jobs: {e}")
        return False

    # List by status
    print(f"\n5. Listing all 'completed' jobs")
    try:
        completed_jobs = provider.list_jobs(status="completed", limit=5)
        print(f"   ✓ Found {len(completed_jobs)} completed jobs")
    except Exception as e:
        print(f"   ✗ Error listing by status: {e}")
        return False

    print("\n✅ All jobs tests passed!\n")
    return True


def test_accounts():
    """Test accounts CRUD operations."""
    print("\n" + "="*60)
    print("TESTING ACCOUNTS MODULE")
    print("="*60)

    provider = DynamoDBAccountsProvider()
    print(f"✓ Using table: {provider.table_name}")

    # Create test account
    account = Account(
        account_id="341",
        name="Acme Corporation",
        description="Test account for development",
        is_default=True,
        storage_type="s3",
        s3_bucket="modernizeit-customer-341",
        s3_region="us-east-1",
        s3_prefix="cobol-files"
    )

    # Save account
    print(f"\n1. Saving account: {account.account_id}")
    try:
        provider.save_account(account)
        print("   ✓ Account saved successfully")
    except Exception as e:
        print(f"   ✗ Error saving account: {e}")
        return False

    # Get account
    print(f"\n2. Retrieving account: {account.account_id}")
    try:
        retrieved = provider.get_account("341")
        if retrieved:
            print(f"   ✓ Account retrieved successfully")
            print(f"   - Name: {retrieved.name}")
            print(f"   - S3 Bucket: {retrieved.s3_bucket}")
            print(f"   - S3 Region: {retrieved.s3_region}")
            print(f"   - S3 Prefix: {retrieved.s3_prefix}")
            print(f"   - Is Default: {retrieved.is_default}")
        else:
            print("   ✗ Account not found")
            return False
    except Exception as e:
        print(f"   ✗ Error retrieving account: {e}")
        return False

    # List accounts
    print(f"\n3. Listing all accounts")
    try:
        accounts = provider.list_accounts()
        print(f"   ✓ Found {len(accounts)} accounts")
        for acc in accounts[:3]:  # Show first 3
            print(f"   - {acc.account_id}: {acc.name} (bucket: {acc.s3_bucket})")
    except Exception as e:
        print(f"   ✗ Error listing accounts: {e}")
        return False

    # Get default account
    print(f"\n4. Getting default account")
    try:
        default = provider.get_default_account()
        if default:
            print(f"   ✓ Default account: {default.account_id} - {default.name}")
        else:
            print("   ⚠ No default account found")
    except Exception as e:
        print(f"   ✗ Error getting default account: {e}")
        return False

    print("\n✅ All accounts tests passed!\n")
    return True


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("DYNAMODB MODULES TEST SUITE")
    print("="*60)
    print(f"Testing against: {DynamoDBJobsProvider().table_name}")
    print(f"Region: {DynamoDBJobsProvider().region}")
    print("="*60)

    jobs_ok = test_jobs()
    accounts_ok = test_accounts()

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Jobs Module:     {'✅ PASS' if jobs_ok else '❌ FAIL'}")
    print(f"Accounts Module: {'✅ PASS' if accounts_ok else '❌ FAIL'}")
    print("="*60)

    if jobs_ok and accounts_ok:
        print("\n🎸 ALL TESTS PASSED! DynamoDB modules are ready to use.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED. Check errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
