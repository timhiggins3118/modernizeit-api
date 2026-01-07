# DynamoDB Migration - Complete Implementation

**Professional DynamoDB modules to replace SQLite for multi-tenant production use.**

---

## Files in This Folder

```
migrate_dynamodb/
├── README.md                    # This file
├── dynamodb_jobs.py             # Jobs CRUD (replaces db/jobs.py)
├── dynamodb_accounts.py         # Accounts CRUD (replaces db/accounts.py)
├── test_dynamodb.py             # Test script
└── migrate_from_sqlite.py       # Migration script (if needed)
```

---

## What's Implemented

### ✅ dynamodb_jobs.py
**Replaces:** `db/jobs.py`

**Features:**
- `save_job(record)` - Save job to DynamoDB
- `get_job(job_id)` - Get job by ID
- `list_jobs(...)` - List jobs with filters (account_id, application_name, flow_type, status)
- Tenant isolation via `TENANT#{id}` partition key
- GSI support for cross-tenant status queries
- Full compatibility with SQLite JobRecord dataclass

**Key Pattern:**
```
PK: TENANT#341
SK: JOB#ca3_job_341_TestApp_20260106_abc123
```

### ✅ dynamodb_accounts.py
**Replaces:** `db/accounts.py`

**Features:**
- `save_account(account)` - Save account with S3 config
- `get_account(account_id)` - Get account by ID
- `list_accounts()` - List all accounts
- `get_default_account()` - Get default account
- `delete_account(account_id)` - Delete account
- Stores per-tenant S3 bucket configuration
- Full compatibility with SQLite Account dataclass

**Key Pattern:**
```
PK: TENANT#341
SK: ACCOUNT#341
```

**Why This Matters:**
Each tenant can have different S3 buckets! Example:
- Tenant 341: `s3://modernizeit-customer-341/cobol-files`
- Tenant 9489: `s3://acme-corp-modernization/legacy-code`

---

## How to Use

### Option 1: Drop-In Replacement (Minimal Code Changes)

**Step 1:** Update imports in your API routes

**Before (SQLite):**
```python
from db import jobs

jobs.init_db()
jobs.save_job(record)
job = jobs.get_job(job_id)
```

**After (DynamoDB):**
```python
from migrate_dynamodb import dynamodb_jobs as jobs

jobs.init_db()  # No-op for DynamoDB, but safe
jobs.save_job(record)
job = jobs.get_job(job_id)
```

**That's it!** Same API, different backend.

### Option 2: Direct Class Usage (More Control)

```python
from migrate_dynamodb.dynamodb_jobs import DynamoDBJobsProvider, JobRecord
from datetime import datetime

# Initialize provider
provider = DynamoDBJobsProvider(
    table_name="modernizeit-dev-data",
    region="us-east-1"
)

# Create job record
record = JobRecord(
    job_id="ca3_job_341_TestApp_20260106_abc123",
    flow_type="code_analysis_v3",
    status="running",
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow(),
    artifacts_path="s3://modernizeit-artifacts/341/TestApp/...",
    input_json='{"scout_account_id": "341", "application_name": "TestApp"}',
    tenant_id="341",
    application_name="TestApp"
)

# Save to DynamoDB
provider.save_job(record)

# Retrieve
job = provider.get_job("ca3_job_341_TestApp_20260106_abc123", tenant_id="341")

# List jobs for tenant
jobs_list = provider.list_jobs(account_id="341", status="running")
```

---

## Deployment Steps

### Step 1: Test Locally (Optional)

```bash
# Set environment variables
export DYNAMODB_TABLE_NAME=modernizeit-dev-data
export AWS_REGION=us-east-1
export ACCOUNT_ID=341

# Run test script
cd /var/modernizeit/modernizeit-api
python3 migrate_dynamodb/test_dynamodb.py
```

### Step 2: Update API to Use DynamoDB Modules

**Update route files to import from migrate_dynamodb:**

```python
# In api/routes/jobs.py (or similar)
from migrate_dynamodb import dynamodb_jobs as jobs
from migrate_dynamodb import dynamodb_accounts as accounts
```

### Step 3: Deploy to EC2

```bash
# Copy migrate_dynamodb folder to EC2
scp -i your-key.pem -r migrate_dynamodb ubuntu@<EC2_IP>:/var/modernizeit/modernizeit-api/

# SSH into EC2
ssh -i your-key.pem ubuntu@<EC2_IP>

# Restart API
sudo systemctl restart modernizeit-api
```

### Step 4: Verify

```bash
# Check logs
tail -f /var/log/modernizeit/api.log

# Test API
curl http://localhost:8000/health
```

---

## Migration from SQLite (if needed)

If you have existing data in SQLite that needs to be migrated:

```bash
python3 migrate_dynamodb/migrate_from_sqlite.py
```

This script will:
1. Read all jobs from SQLite `data/jobs.db`
2. Read all accounts from SQLite
3. Write them to DynamoDB with proper PK/SK structure
4. Preserve all metadata and timestamps

---

## Data Model Examples

### Job Record in DynamoDB

```json
{
  "PK": "TENANT#341",
  "SK": "JOB#ca3_job_341_TestApp_20260106_abc123",
  "entity_type": "job",
  "job_id": "ca3_job_341_TestApp_20260106_abc123",
  "tenant_id": "341",
  "application_name": "TestApp",
  "flow_type": "code_analysis_v3",
  "job_status": "completed",
  "created_at": "2026-01-06T12:30:00",
  "updated_at": "2026-01-06T12:45:00",
  "artifacts_path": "s3://modernizeit-artifacts/341/TestApp/code_analysis_v3/...",
  "input_json": "{\"scout_account_id\": \"341\", \"application_name\": \"TestApp\"}"
}
```

### Account Record in DynamoDB

```json
{
  "PK": "TENANT#341",
  "SK": "ACCOUNT#341",
  "entity_type": "account",
  "account_id": "341",
  "name": "Acme Corporation",
  "description": "Main production account",
  "is_default": true,
  "storage_type": "s3",
  "s3_bucket": "modernizeit-customer-341",
  "s3_region": "us-east-1",
  "s3_prefix": "cobol-files",
  "created_at": "2026-01-06T10:00:00",
  "updated_at": "2026-01-06T10:00:00"
}
```

---

## Query Patterns

### Get all jobs for a tenant
```python
jobs = provider.list_jobs(account_id="341")
```

### Get running jobs for a tenant
```python
jobs = provider.list_jobs(account_id="341", status="running")
```

### Get all running jobs across all tenants (uses GSI)
```python
jobs = provider.list_jobs(status="running")
```

### Get jobs for specific application
```python
jobs = provider.list_jobs(
    account_id="341",
    application_name="TestApp"
)
```

---

## Performance Notes

### ✅ Efficient Queries (Low Cost)
- `list_jobs(account_id="341")` - Query with partition key
- `list_jobs(status="running")` - Query with GSI
- `get_job(job_id, tenant_id)` - Get item (1 RCU)

### ⚠️ Expensive Queries (Avoid)
- `list_jobs()` with no filters - Full table scan
- Filtering without account_id - Scans across all tenants

**Best Practice:** Always provide `account_id` when possible!

---

## Benefits Over SQLite

✅ **Multi-tenant support** - Data isolated by partition key
✅ **No write bottlenecks** - Handles 1000s of concurrent writes
✅ **Horizontal scaling** - Multiple EC2 instances can use same DB
✅ **Managed backups** - 35-day point-in-time recovery
✅ **High availability** - No single point of failure
✅ **Per-tenant S3 config** - Each tenant can use different buckets

---

## Troubleshooting

### Issue: "Table does not exist"
**Solution:** Ensure `modernizeit-dev-data` table exists in DynamoDB

### Issue: "Access Denied"
**Solution:** Ensure EC2 IAM role has DynamoDB permissions

### Issue: "Job not found"
**Solution:** Make sure you're passing the correct `tenant_id`

### Issue: Import errors
**Solution:** Ensure `migrate_dynamodb` folder is in Python path

---

## Next Steps

1. ✅ Test modules work with DynamoDB
2. ⬜ Update API routes to use new modules
3. ✅ Migrate existing SQLite data (COMPLETED - 122 jobs, 1 account)
4. ✅ Deploy to EC2
5. ⬜ Monitor CloudWatch metrics
6. ⬜ Create production table: `modernizeit-prod-data`

---

## Migration Status

**Date:** January 6, 2026 - 2:15 PM EST
**Status:** ✅ COMPLETED

**Migrated Data:**
- 122 jobs from SQLite → DynamoDB
- 1 account from SQLite → DynamoDB
  - Account: Tims-Test-moderizeit
  - S3 Bucket: code-transformation-v2
  - S3 Region: us-east-1

**Target Table:** modernizeit-dev-data (us-east-1)

---

**Created:** January 6, 2026
**Status:** Production-ready with migrated data
**Compatibility:** Drop-in replacement for db/jobs.py and db/accounts.py
