# Database Analysis - December 30, 2025

## Where The Data Lives

The 78 applications shown in the Live Portal are stored in **AWS DynamoDB**.

---

## DynamoDB Tables

From `uidata/create_dynamodb_tables.sh`:

```bash
# Tables are per-account
aws dynamodb create-table --table-name "${ACCOUNT_ID}_applications"
aws dynamodb create-table --table-name "${ACCOUNT_ID}_files"
aws dynamodb create-table --table-name "${ACCOUNT_ID}_analysis_history"
```

### Table Structure

| Table | Key | Purpose |
|-------|-----|---------|
| `{account}_applications` | `application_id` | App metadata (name, description, status, job IDs) |
| `{account}_files` | `file_id` | File records (COBOL files, S3 paths, analysis status) |
| `{account}_analysis_history` | `run_id` | Historical analysis runs |

### Application Schema (from application_service.go)
```go
type Application struct {
    ApplicationID   string   // app_sat122_1765626976
    AccountID       string   // 1762150037
    ApplicationName string   // "sat122"
    Description     string
    Technology      string   // "COBOL"
    CreatedAt       string
    UpdatedAt       string
    Status          string   // active, archived
    FileCount       int
    Tags            []string // ["COBOL", "JAVA"]

    // Job tracking
    CobolJobID      string
    CobolStatus     string
    DataJobID       string
    RefactorJobID   string
    // ... etc
}
```

### File Schema
```go
type FileRecord struct {
    FileID        string
    ApplicationID string
    FileName      string
    FileType      string   // cobol, java
    FileSize      int64
    S3Path        string   // S3 location
    UploadedAt    string
    Status        string   // uploaded, analyzing, analyzed

    // Job IDs per flow
    COBOLJobID    string
    DataJobID     string
    // ... etc
}
```

---

## File Storage

**S3 Bucket:** `scoutitmodernization`

```
s3://scoutitmodernization/
├── applications/
│   └── {app_id}/
│       └── files/
│           └── {filename}.cbl
└── code-transformation-v2/
    └── {account}/
        └── {app}/
            └── ... (analysis outputs)
```

---

## Current vs Our Stack

### Current (Live App)
```
Live UI → uidata (Go) → DynamoDB + S3
                      → AWS Lambdas (processing)
```

### Our Stack
```
Our FastAPI → SQLite (jobs.db) + Local filesystem
           → Local processing (our engines)
```

---

## Deployment Options

### Option A: Connect to DynamoDB
- Keep existing customer data (78 apps)
- Add AWS SDK to our FastAPI
- Pros: Zero data migration
- Cons: AWS dependency, need credentials

### Option B: Migrate to PostgreSQL/SQLite
- Create new database schema
- Import existing data (if needed)
- Pros: Local control, no AWS costs
- Cons: Need migration script

### Option C: Hybrid Adapters
- Support both DynamoDB and local storage
- Configuration switch for deployment target
- Pros: Flexible
- Cons: More code to maintain

---

## Decision Needed

**Question for tomorrow:**

Do we want to:
1. **Keep DynamoDB** - Preserve the 78 existing apps, need AWS access
2. **Fresh start with SQLite/PostgreSQL** - New database, existing apps stay in old system
3. **Migration** - Export DynamoDB data, import to our database

---

## What We Need To Build (Regardless of DB choice)

### Application Management
```python
# api/routes/applications.py
@router.get("/api/applications")
@router.post("/api/applications")
@router.get("/api/applications/{id}")
@router.put("/api/applications/{id}")
@router.delete("/api/applications/{id}")
```

### File Management
```python
# api/routes/files.py
@router.get("/api/applications/files/list")
@router.post("/api/applications/files/upload")
@router.get("/api/files/{id}")
@router.delete("/api/files/{id}")
```

### Database Schema (SQLite/PostgreSQL)
```sql
CREATE TABLE applications (
    application_id TEXT PRIMARY KEY,
    account_id TEXT,
    application_name TEXT,
    description TEXT,
    technology TEXT DEFAULT 'COBOL',
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    status TEXT DEFAULT 'active',
    file_count INTEGER DEFAULT 0
);

CREATE TABLE files (
    file_id TEXT PRIMARY KEY,
    application_id TEXT REFERENCES applications(application_id),
    file_name TEXT,
    file_type TEXT,
    file_size INTEGER,
    file_path TEXT,
    uploaded_at TIMESTAMP,
    status TEXT DEFAULT 'uploaded'
);
```

---

*Created: December 30, 2025*
