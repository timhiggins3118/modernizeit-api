# S3 Management - Full CRUD Operations

## Overview

The ModernizeIT platform provides complete S3 bucket and object management through the API. This includes:
- **Create**: Automatically validate and create S3 buckets
- **Read**: List buckets, list files/folders in buckets
- **Update**: (Future) Update bucket settings, move files
- **Delete**: Delete files, folders, and buckets

This eliminates the need for manual S3 management through AWS Console.

## How It Works

### Flow
1. **User creates/updates account** with S3 storage type in the UI
2. **UI validates form** (bucket name format, region, etc.)
3. **UI calls API** to validate/create bucket: `POST /s3/validate-bucket`
4. **API checks AWS credentials** exist in database
5. **API validates bucket** using boto3:
   - If bucket exists → returns success
   - If bucket doesn't exist → creates it automatically
   - If error (permissions, name taken, etc.) → returns error
6. **UI shows result** to user
7. **Account is saved** to database

### Prerequisites
- **AWS Credentials must be configured** in Settings before creating S3 accounts
- Credentials must have `s3:CreateBucket`, `s3:ListBucket` permissions

## API Endpoint

### `POST /s3/validate-bucket`

Validates if S3 bucket exists, creates if it doesn't.

**Request:**
```json
{
  "bucket_name": "code-transformation-tims-test",
  "region": "us-east-1"
}
```

**Response (Success - Bucket Created):**
```json
{
  "success": true,
  "exists": false,
  "created": true,
  "message": "Bucket 'code-transformation-tims-test' created successfully",
  "bucket": "code-transformation-tims-test",
  "region": "us-east-1"
}
```

**Response (Success - Bucket Already Exists):**
```json
{
  "success": true,
  "exists": true,
  "created": false,
  "message": "Bucket 'code-transformation-tims-test' already exists",
  "bucket": "code-transformation-tims-test",
  "region": "us-east-1"
}
```

**Response (Error - No AWS Credentials):**
```json
{
  "detail": "AWS credentials not configured. Please configure AWS credentials in Settings first."
}
```

**Response (Error - Bucket Name Taken):**
```json
{
  "detail": "Bucket name 'code-transformation-tims-test' is already taken by another AWS account. Choose a different name."
}
```

## Implementation Files

### Backend (modernizeit-api)
- **`utils/s3_helper.py`** - S3Helper class with boto3 logic
  - `bucket_exists()` - Check if bucket exists
  - `create_bucket()` - Create S3 bucket
  - `validate_and_create_bucket()` - Main validation/creation flow
  - `get_aws_credentials_from_db()` - Get creds from SQLite

- **`api/routes/s3.py`** - FastAPI router
  - `POST /s3/validate-bucket` - Main endpoint
  - `GET /s3/credentials-configured` - Check if AWS creds configured

- **`main.py`** - Router registration

### Frontend (modernizeit-ui)
- **`src/components/landing/ManageAccountsModal.jsx`**
  - Updated `handleSave()` to call S3 validation before saving
  - Shows error if bucket validation fails
  - Shows success message in console logs

## Error Handling

### No AWS Credentials
If AWS credentials are not configured in Settings:
- API returns 400 error
- UI shows: "S3 bucket validation failed: AWS credentials not configured. Please configure AWS credentials in Settings first."
- Account is NOT saved

### Bucket Name Taken
If bucket name is already owned by another AWS account:
- API returns 500 error
- UI shows: "S3 bucket validation failed: Bucket name 'xxx' is already taken by another AWS account. Choose a different name."
- Account is NOT saved

### Permission Denied
If AWS credentials don't have permission to create buckets:
- API returns 500 error with AWS error message
- UI shows the error
- Account is NOT saved

### Bucket Already Exists (Your Account)
If bucket already exists and is owned by you:
- API returns success with `exists: true, created: false`
- Account is saved successfully
- No error shown to user

## Testing

### Test Flow
1. **Start API server:**
   ```bash
   cd modernizeit-api
   source .venv/bin/activate
   uvicorn main:app --reload
   ```

2. **Configure AWS credentials** in Settings (must be done first)

3. **Create account with S3 storage:**
   - Go to Manage Accounts
   - Add Account tab
   - Enter Account ID: TEST123
   - Enter Account Name: Test Account
   - Select Storage Type: AWS S3
   - Enter S3 Bucket: code-transformation-test-unique-name
   - Select S3 Region: US East (N. Virginia)
   - Click Create

4. **Check console logs** for validation results

5. **Verify in AWS Console** that bucket was created

### Manual API Testing
```bash
# Check if credentials configured
curl http://localhost:8000/s3/credentials-configured

# Validate/create bucket
curl -X POST http://localhost:8000/s3/validate-bucket \
  -H "Content-Type: application/json" \
  -d '{"bucket_name": "code-transformation-test-123", "region": "us-east-1"}'
```

## AWS Permissions Required

AWS credentials must have these IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:ListBucket",
        "s3:HeadBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "*"
    }
  ]
}
```

## Notes

- **Bucket names must be globally unique** across all AWS accounts
- **Buckets are created in the specified region** (except us-east-1 which is default)
- **No public access** - buckets are created with default ACLs (private)
- **Bucket lifecycle** - buckets are NOT deleted when accounts are deleted (manual cleanup required)
- **Cost** - Empty S3 buckets have no storage cost, only request costs when used

---

## Complete S3 API Reference

### List Buckets

`GET /s3/list-buckets`

List all S3 buckets in the AWS account.

**Response:**
```json
{
  "success": true,
  "buckets": [
    {
      "name": "code-transformation-v2",
      "creation_date": "2025-01-04T10:30:00Z"
    },
    {
      "name": "code-transformation-tims-test",
      "creation_date": "2025-01-04T15:45:00Z"
    }
  ],
  "total": 2
}
```

---

### List Files

`POST /s3/list-files`

List files and folders in an S3 bucket.

**Request:**
```json
{
  "bucket_name": "code-transformation-tims-test",
  "prefix": "0U812/",
  "max_keys": 1000
}
```

**Response:**
```json
{
  "success": true,
  "bucket": "code-transformation-tims-test",
  "prefix": "0U812/",
  "files": [
    {
      "key": "0U812/shared/uploads/source.zip",
      "size": 1048576,
      "last_modified": "2025-01-04T16:00:00Z",
      "storage_class": "STANDARD"
    }
  ],
  "folders": [
    {
      "prefix": "0U812/shared/"
    },
    {
      "prefix": "0U812/code_analysis_v3/"
    }
  ],
  "is_truncated": false,
  "total_files": 1,
  "total_folders": 2
}
```

---

### Delete File

`DELETE /s3/delete-file`

Delete a single file from S3 bucket.

**Request:**
```json
{
  "bucket_name": "code-transformation-tims-test",
  "key": "0U812/shared/uploads/old-file.zip"
}
```

**Response:**
```json
{
  "success": true,
  "message": "File '0U812/shared/uploads/old-file.zip' deleted successfully",
  "bucket": "code-transformation-tims-test",
  "key": "0U812/shared/uploads/old-file.zip"
}
```

---

### Delete Folder

`DELETE /s3/delete-folder`

Delete all files with a given prefix (folder).

**Request:**
```json
{
  "bucket_name": "code-transformation-tims-test",
  "prefix": "0U812/old-project/"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Deleted 25 files with prefix '0U812/old-project/'",
  "bucket": "code-transformation-tims-test",
  "prefix": "0U812/old-project/",
  "deleted_count": 25
}
```

---

### Delete Bucket

`DELETE /s3/delete-bucket`

Delete an S3 bucket. Use `force: true` to delete all objects first.

**Request (Empty Bucket):**
```json
{
  "bucket_name": "code-transformation-old-bucket",
  "force": false
}
```

**Request (Force Delete - Remove All Objects First):**
```json
{
  "bucket_name": "code-transformation-old-bucket",
  "force": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Bucket 'code-transformation-old-bucket' deleted successfully",
  "bucket": "code-transformation-old-bucket",
  "objects_deleted": 150
}
```

**Error (Bucket Not Empty):**
```json
{
  "detail": "Bucket 'code-transformation-old-bucket' is not empty. Use force=true to delete all objects first."
}
```

---

## Testing CRUD Operations

### List All Buckets
```bash
curl http://localhost:8000/s3/list-buckets
```

### List Files in Bucket
```bash
curl -X POST http://localhost:8000/s3/list-files \
  -H "Content-Type: application/json" \
  -d '{"bucket_name": "code-transformation-v2", "prefix": "0U812/"}'
```

### Delete Single File
```bash
curl -X DELETE http://localhost:8000/s3/delete-file \
  -H "Content-Type: application/json" \
  -d '{"bucket_name": "code-transformation-v2", "key": "0U812/test.txt"}'
```

### Delete Folder (All Files with Prefix)
```bash
curl -X DELETE http://localhost:8000/s3/delete-folder \
  -H "Content-Type: application/json" \
  -d '{"bucket_name": "code-transformation-v2", "prefix": "0U812/old-data/"}'
```

### Delete Empty Bucket
```bash
curl -X DELETE http://localhost:8000/s3/delete-bucket \
  -H "Content-Type: application/json" \
  -d '{"bucket_name": "code-transformation-old", "force": false}'
```

### Force Delete Bucket (Delete All Objects First)
```bash
curl -X DELETE http://localhost:8000/s3/delete-bucket \
  -H "Content-Type: application/json" \
  -d '{"bucket_name": "code-transformation-old", "force": true}'
```

---

## Future Enhancements

- [ ] Add bucket lifecycle policies (auto-delete old files)
- [ ] Add bucket versioning configuration
- [ ] Add encryption configuration (SSE-S3 or SSE-KMS)
- [ ] Add bucket tagging for cost tracking
- [ ] Add bucket deletion on account delete (with confirmation)
- [ ] Add bucket validation on workflow execution (retry mechanism)
- [ ] Add file/folder move/copy operations
- [ ] Add file download/upload endpoints
- [ ] Add presigned URL generation for direct uploads
