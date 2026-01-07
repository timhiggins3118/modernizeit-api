"""
SQLite to DynamoDB Migration Script

Migrates all existing jobs and accounts from SQLite to DynamoDB.
Preserves all metadata, timestamps, and S3 configurations.

Usage:
    python3 migrate_dynamodb/migrate_from_sqlite.py

Created: January 6, 2026
"""

import sys
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import SQLite modules directly to avoid db package __init__ issues
import importlib.util

# Load jobs module
jobs_spec = importlib.util.spec_from_file_location("sqlite_jobs", str(Path(__file__).parent.parent / "db" / "jobs.py"))
sqlite_jobs = importlib.util.module_from_spec(jobs_spec)
jobs_spec.loader.exec_module(sqlite_jobs)

# Load accounts module
accounts_spec = importlib.util.spec_from_file_location("sqlite_accounts", str(Path(__file__).parent.parent / "db" / "accounts.py"))
sqlite_accounts = importlib.util.module_from_spec(accounts_spec)
accounts_spec.loader.exec_module(sqlite_accounts)

from migrate_dynamodb.dynamodb_jobs import DynamoDBJobsProvider, JobRecord
from migrate_dynamodb.dynamodb_accounts import DynamoDBAccountsProvider, Account


def migrate_jobs():
    """Migrate all jobs from SQLite to DynamoDB."""
    print("\n" + "="*60)
    print("MIGRATING JOBS FROM SQLITE TO DYNAMODB")
    print("="*60)

    # Initialize providers
    sqlite_provider = sqlite_jobs
    dynamo_provider = DynamoDBJobsProvider()

    print(f"\n📖 Reading jobs from SQLite: {sqlite_jobs._get_db_path()}")

    # Get all jobs from SQLite
    all_jobs = sqlite_provider.list_jobs(limit=10000)
    print(f"   ✓ Found {len(all_jobs)} jobs to migrate")

    if len(all_jobs) == 0:
        print("   ⚠ No jobs to migrate")
        return 0, 0

    print(f"\n💾 Writing to DynamoDB: {dynamo_provider.table_name}")

    migrated = 0
    failed = 0

    for idx, job in enumerate(all_jobs, 1):
        try:
            # Extract tenant_id from input_json
            try:
                input_data = json.loads(job.input_json)
                tenant_id = input_data.get('scout_account_id', input_data.get('account_id', '341'))
                application_name = input_data.get('application_name')
            except:
                tenant_id = '341'
                application_name = None

            # Create DynamoDB record with tenant info
            dynamo_record = JobRecord(
                job_id=job.job_id,
                flow_type=job.flow_type,
                status=job.status,
                created_at=job.created_at,
                updated_at=job.updated_at,
                artifacts_path=job.artifacts_path,
                input_json=job.input_json,
                tenant_id=tenant_id,
                application_name=application_name
            )

            # Save to DynamoDB
            dynamo_provider.save_job(dynamo_record)
            migrated += 1

            if idx % 10 == 0:
                print(f"   Progress: {idx}/{len(all_jobs)} jobs migrated...")

        except Exception as e:
            print(f"   ✗ Error migrating job {job.job_id}: {e}")
            failed += 1
            continue

    print(f"\n✅ Jobs migration complete!")
    print(f"   - Migrated: {migrated}")
    print(f"   - Failed: {failed}")

    return migrated, failed


def migrate_accounts():
    """Migrate all accounts from SQLite to DynamoDB."""
    print("\n" + "="*60)
    print("MIGRATING ACCOUNTS FROM SQLITE TO DYNAMODB")
    print("="*60)

    # Initialize providers
    sqlite_provider = sqlite_accounts
    dynamo_provider = DynamoDBAccountsProvider()

    print(f"\n📖 Reading accounts from SQLite: {sqlite_accounts._get_db_path()}")

    # Get all accounts from SQLite
    all_accounts = sqlite_provider.get_all_accounts()
    print(f"   ✓ Found {len(all_accounts)} accounts to migrate")

    if len(all_accounts) == 0:
        print("   ⚠ No accounts to migrate")
        return 0, 0

    print(f"\n💾 Writing to DynamoDB: {dynamo_provider.table_name}")

    migrated = 0
    failed = 0

    for account in all_accounts:
        try:
            # Create DynamoDB account (same dataclass structure)
            dynamo_account = Account(
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

            # Save to DynamoDB
            dynamo_provider.save_account(dynamo_account)
            migrated += 1

            print(f"   ✓ Migrated account: {account.account_id} ({account.name})")
            if account.s3_bucket:
                print(f"      - S3 Bucket: {account.s3_bucket}")
                print(f"      - S3 Region: {account.s3_region}")
                print(f"      - S3 Prefix: {account.s3_prefix}")

        except Exception as e:
            print(f"   ✗ Error migrating account {account.account_id}: {e}")
            failed += 1
            continue

    print(f"\n✅ Accounts migration complete!")
    print(f"   - Migrated: {migrated}")
    print(f"   - Failed: {failed}")

    return migrated, failed


def verify_migration():
    """Verify migration by comparing counts."""
    print("\n" + "="*60)
    print("VERIFYING MIGRATION")
    print("="*60)

    # Check SQLite
    sqlite_jobs_count = len(sqlite_jobs.list_jobs(limit=10000))
    sqlite_accounts_count = len(sqlite_accounts.get_all_accounts())

    # Check DynamoDB
    dynamo_jobs_provider = DynamoDBJobsProvider()
    dynamo_accounts_provider = DynamoDBAccountsProvider()

    # Get all jobs from DynamoDB (scan across all tenants)
    dynamo_jobs_count = len(dynamo_jobs_provider.list_jobs(limit=10000))
    dynamo_accounts_count = len(dynamo_accounts_provider.list_accounts())

    print(f"\n📊 Record Counts:")
    print(f"   SQLite Jobs:      {sqlite_jobs_count}")
    print(f"   DynamoDB Jobs:    {dynamo_jobs_count}")
    print(f"   SQLite Accounts:  {sqlite_accounts_count}")
    print(f"   DynamoDB Accounts: {dynamo_accounts_count}")

    jobs_match = sqlite_jobs_count == dynamo_jobs_count
    accounts_match = sqlite_accounts_count == dynamo_accounts_count

    if jobs_match and accounts_match:
        print("\n✅ Verification PASSED - All records migrated!")
        return True
    else:
        print("\n⚠️ Verification FAILED - Counts don't match!")
        if not jobs_match:
            print(f"   Jobs mismatch: SQLite={sqlite_jobs_count}, DynamoDB={dynamo_jobs_count}")
        if not accounts_match:
            print(f"   Accounts mismatch: SQLite={sqlite_accounts_count}, DynamoDB={dynamo_accounts_count}")
        return False


def main():
    """Run the full migration."""
    print("\n" + "="*60)
    print("SQLITE → DYNAMODB MIGRATION")
    print("="*60)
    print("Date: January 6, 2026")
    print("Source: SQLite (data/jobs.db)")
    print("Target: DynamoDB (modernizeit-dev-data)")
    print("="*60)

    try:
        # Migrate accounts first (needed for tenant isolation)
        accounts_migrated, accounts_failed = migrate_accounts()

        # Migrate jobs
        jobs_migrated, jobs_failed = migrate_jobs()

        # Verify migration
        verified = verify_migration()

        # Summary
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        print(f"Accounts Migrated: {accounts_migrated}")
        print(f"Accounts Failed:   {accounts_failed}")
        print(f"Jobs Migrated:     {jobs_migrated}")
        print(f"Jobs Failed:       {jobs_failed}")
        print(f"Verification:      {'✅ PASSED' if verified else '❌ FAILED'}")
        print("="*60)

        if accounts_failed == 0 and jobs_failed == 0 and verified:
            print("\n🎸 MIGRATION COMPLETE! Rock on! Your data is now in DynamoDB.")
            return 0
        else:
            print("\n⚠️ Migration completed with errors. Check logs above.")
            return 1

    except Exception as e:
        print(f"\n❌ FATAL ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
