# Architecture Questions - January 1, 2026

Questions to answer before building. Focus is **Portal/Cloud first**, desktop later.

---

## Storage Mode

**Current setting exists:**
```python
storage_mode = "local" | "s3"
```

**Question:** Is this enough, or do we need more granular control?

| Setting | Local | S3 |
|---------|-------|-----|
| Uploaded source files | `./uploads/` | `s3://bucket/uploads/` |
| Generated output | `./output/` | `s3://bucket/output/` |
| Analysis artifacts | `./artifacts/` | `s3://bucket/artifacts/` |

**Decision needed:** One toggle for all, or separate settings per file type?

---

## Source of Truth

**Question:** Where does the canonical data live?

| Scenario | Metadata | Files |
|----------|----------|-------|
| Portal only | DynamoDB | S3 |
| Desktop only | SQLite | Local |
| Both? | ??? | ??? |

**If user has both:**
- Do they share data?
- Is desktop a "offline cache" of cloud data?
- Or completely separate workspaces?

**Current thinking:** Keep them separate for now. Sync is Phase 2.

---

## Sync Option (Future)

**Question:** When we add sync, what does it look like?

Options:
1. **One-way push:** Desktop → Cloud (upload local work)
2. **One-way pull:** Cloud → Desktop (work offline)
3. **Two-way sync:** Conflict resolution nightmare

**Current thinking:** Start with one-way push. User explicitly "publishes" to cloud.

---

## Authentication Modes

**Question:** How does the provider know which auth to use?

| Mode | Auth Method |
|------|-------------|
| Portal (cloud) | IAM roles, no user creds |
| Desktop | User-provided AWS creds |
| Local-only | No AWS needed |

**Current thinking:** If `storage_mode=s3`, assume AWS auth is configured (env vars, IAM role, or creds file).

---

## Credentials Storage

**Question:** Where do AWS creds live?

| Deployment | Creds Location |
|------------|----------------|
| Portal on AWS | IAM role (no storage needed) |
| Portal on-prem | Environment variables or secrets manager |
| Desktop | SQLite `aws_credentials` table (current) |

**Current thinking:** Don't change. Each mode handles its own auth.

---

## File Size & Limits

**Question:** Do we need size limits or chunking?

| File Type | Typical Size | Concern |
|-----------|--------------|---------|
| COBOL source | 1-100 KB | None |
| Copybooks | 1-50 KB | None |
| Generated Java | 1-10 MB | Minor |
| Full analysis JSON | 10-100 MB | Could be large |
| Packaged output (zip) | 50-500 MB | S3 multipart? |

**Current thinking:** S3 handles large files fine. Set reasonable limits in API (100MB upload max?).

---

## Multi-Tenancy

**Question:** How do we separate customer data in S3?

Options:
1. **Bucket per account:** `s3://customer-341/`, `s3://customer-5600/`
2. **Prefix per account:** `s3://modernizeit/341/...`, `s3://modernizeit/5600/...`
3. **Single bucket, IAM policies:** Fine-grained access control

**Current thinking:** Prefix per account is simplest. Matches DynamoDB pattern (`341_applications`).

```
s3://modernizeit-data/
├── 341/
│   ├── uploads/
│   ├── output/
│   └── artifacts/
├── 5600/
│   ├── uploads/
│   └── ...
```

---

## Artifact Storage

**Question:** Keep MongoDB or move to S3?

| Option | Pros | Cons |
|--------|------|------|
| Keep MongoDB | Already works, good for queries | Another service to manage |
| Move to S3 | Simpler infra, just S3 | Harder to query, need metadata DB |
| S3 + DynamoDB | Files in S3, index in DynamoDB | More complex, but scalable |

**Current thinking:** S3 + DynamoDB for cloud. JSON files in S3, metadata/index in DynamoDB.

---

## API Contract

**Question:** Should API responses include S3 URLs or abstract paths?

Option A - Direct S3 URLs:
```json
{
  "file_url": "https://s3.amazonaws.com/bucket/341/uploads/file.cob"
}
```

Option B - Abstract paths (API serves files):
```json
{
  "file_path": "/api/files/341/uploads/file.cob"
}
```

Option C - Presigned URLs (secure, temporary):
```json
{
  "file_url": "https://s3...?signature=xxx&expires=3600"
}
```

**Current thinking:** Option C (presigned URLs) for downloads. API handles uploads directly.

---

## Settings We Need

Based on above, settings should include:

```python
# Storage
storage_mode: "local" | "s3"
s3_bucket: "modernizeit-data"
s3_region: "us-east-1"
local_storage_path: "./data"

# Data (metadata)
data_provider: "sqlite" | "dynamodb"
account_id: "341"

# Future
sync_enabled: false
sync_direction: "push" | "pull" | "bidirectional"
```

---

## Priority Order

For next week, focus on:

1. **S3 storage provider** - Upload/download files to S3
2. **Presigned URL generation** - Secure file access
3. **Wire up to existing flows** - Ingest, Code Analysis use S3

Desktop/SQLite/sync = Later.

---

## Unanswered (Park for Later)

- Offline mode for desktop
- Conflict resolution for sync
- PostgreSQL provider for on-prem
- Secrets manager integration
- File versioning in S3

---

*Status: QUESTIONS - Need decisions before building*
*Focus: Portal/Cloud first*
