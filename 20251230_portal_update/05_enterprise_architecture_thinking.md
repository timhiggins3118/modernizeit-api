# Enterprise Architecture Thinking - January 1, 2026

## The Problem

Our current setup is desktop-focused. To go enterprise, we need to support multiple deployment modes without rewriting everything.

---

## Current State

| Data Type | Current Storage | Limitation |
|-----------|-----------------|------------|
| Job tracking | SQLite | Single user, local only |
| AWS credentials | SQLite | Local only |
| App/File metadata | DynamoDB (read) | Cloud only |
| Analysis artifacts | MongoDB | Requires MongoDB server |
| Actual COBOL/Java files | Local filesystem | Not shareable |

---

## Deployment Scenarios

### Scenario 1: Desktop (Thick Client / Electron)
- Single user on their machine
- Everything local
- No cloud dependency required
- **SQLite + Local filesystem = Perfect**

### Scenario 2: Portal (Cloud / Multi-user)
- Multiple users via web
- Shared data
- Scalable storage
- **DynamoDB + S3 = Enterprise**

### Scenario 3: On-Prem Enterprise
- Company doesn't want cloud
- Need database server
- **PostgreSQL + NFS/MinIO = Self-hosted**

---

## The Solution: Provider Pattern

We already started this with `data_provider`. Extend it to ALL storage concerns.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      API Layer                          │
│                   (FastAPI Routes)                      │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  Provider Interfaces                    │
│   (Abstract contracts - WHAT operations are available)  │
├─────────────┬─────────────┬─────────────┬───────────────┤
│    Data     │   Storage   │    Jobs     │   Artifacts   │
│  Provider   │  Provider   │  Provider   │   Provider    │
└──────┬──────┴──────┬──────┴──────┬──────┴───────┬───────┘
       │             │             │              │
       ▼             ▼             ▼              ▼
┌─────────────────────────────────────────────────────────┐
│              Implementations (HOW)                      │
├─────────────┬─────────────┬─────────────┬───────────────┤
│ • SQLite    │ • Local FS  │ • SQLite    │ • MongoDB     │
│ • DynamoDB  │ • S3        │ • DynamoDB  │ • S3          │
│ • Postgres  │ • MinIO     │ • Postgres  │ • Postgres    │
└─────────────┴─────────────┴─────────────┴───────────────┘
```

### Provider Types

| Provider | Purpose | Desktop | Cloud | On-Prem |
|----------|---------|---------|-------|---------|
| **Data** | App/file metadata | SQLite | DynamoDB | Postgres |
| **Storage** | Actual file content | Local FS | S3 | MinIO/NFS |
| **Jobs** | Job tracking/status | SQLite | DynamoDB | Postgres |
| **Artifacts** | Analysis results | SQLite/JSON | S3 | Postgres |

---

## Proposed File Structure

```
db/
├── models.py                    # Shared data models (done)
│
├── base_provider.py             # Data provider interface (done)
├── dynamodb_provider.py         # DynamoDB implementation (done)
├── sqlite_provider.py           # SQLite implementation (TODO)
│
├── base_storage_provider.py     # File storage interface (TODO)
├── local_storage_provider.py    # Local filesystem (TODO)
├── s3_storage_provider.py       # AWS S3 (TODO)
│
├── base_job_provider.py         # Job tracking interface (TODO)
├── sqlite_job_provider.py       # Current jobs.py refactored (TODO)
├── dynamodb_job_provider.py     # DynamoDB jobs (TODO)
│
├── base_artifact_provider.py    # Artifact storage interface (TODO)
├── mongodb_artifact_provider.py # Current MongoDB repos (TODO)
├── s3_artifact_provider.py      # S3 artifact storage (TODO)
│
└── provider_factory.py          # Factory for all providers (extend)
```

---

## Configuration

### Environment Variables / Config File

```python
# config/app_settings.json

{
  # Desktop Mode
  "data_provider": "sqlite",
  "storage_provider": "local",
  "job_provider": "sqlite",
  "artifact_provider": "sqlite",

  # OR Cloud Mode
  "data_provider": "dynamodb",
  "storage_provider": "s3",
  "job_provider": "dynamodb",
  "artifact_provider": "s3",

  # Provider-specific settings
  "account_id": "341",
  "aws_region": "us-east-1",
  "s3_bucket": "modernizeit-files",
  "sqlite_path": "./data/modernizeit.db"
}
```

### Preset Modes (Convenience)

```python
# Could add preset modes for simplicity
DEPLOYMENT_MODE = "desktop"  # Sets all providers to local/sqlite
DEPLOYMENT_MODE = "cloud"    # Sets all providers to AWS
DEPLOYMENT_MODE = "custom"   # Manual provider selection
```

---

## What SQLite Stays For

SQLite is **not going away**. It's perfect for:

1. **Desktop/Electron app** - No server needed, just works
2. **Development** - Easy to reset, inspect, test
3. **Single-user scenarios** - Consultants, demos, POCs
4. **Offline mode** - Works without internet

The key is **SQLite is an OPTION, not a limitation.**

---

## S3 Integration Points

Where S3 matters for enterprise:

| What | Current | With S3 |
|------|---------|---------|
| Uploaded COBOL files | Local `uploads/` folder | `s3://bucket/uploads/` |
| Generated Java files | Local `output/` folder | `s3://bucket/output/` |
| Analysis JSON results | MongoDB | `s3://bucket/artifacts/` |
| Job logs | Local files | `s3://bucket/logs/` |
| Downloadable packages | Local zip | S3 presigned URL |

### S3 Benefits
- Unlimited storage
- Multi-user access
- Versioning
- Lifecycle policies (auto-archive old jobs)
- Pre-signed URLs for secure downloads

---

## Migration Path

### Phase 1 (Done)
- [x] Data provider interface
- [x] DynamoDB provider (read-only)
- [x] Provider factory
- [x] Settings integration

### Phase 2 (Next)
- [ ] SQLite data provider (for desktop parity)
- [ ] Storage provider interface
- [ ] Local storage provider
- [ ] S3 storage provider

### Phase 3 (Later)
- [ ] Refactor jobs.py into job provider pattern
- [ ] Refactor MongoDB repos into artifact provider pattern
- [ ] Add PostgreSQL providers for on-prem

### Phase 4 (Polish)
- [ ] Deployment mode presets
- [ ] Migration tools (SQLite ↔ DynamoDB)
- [ ] Health checks per provider

---

## Open Questions

1. **Artifact storage** - Keep MongoDB or move to S3 + metadata DB?
2. **File references** - Store S3 keys in DynamoDB, or full URLs?
3. **Offline sync** - If desktop user goes offline, how to sync later?
4. **Multi-tenancy** - One S3 bucket with prefixes, or bucket per account?
5. **Credentials** - AWS Secrets Manager for cloud, SQLite for desktop?

---

## Decision Needed

Before building more providers:

**What's the priority deployment target for next week?**

- A) Desktop-first (SQLite provider priority)
- B) Cloud-first (S3 provider priority)
- C) Both (parallel development)

---

*Created: January 1, 2026*
*Status: THINKING - Not yet implementing*
