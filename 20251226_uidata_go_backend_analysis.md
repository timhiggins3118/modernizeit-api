# UIData Go Backend Analysis

**Date:** December 26, 2025
**Status:** Analysis Complete
**Source:** `/Users/timhiggins/Desktop/pooja_modernizeit/uidata/`

---

## Overview

This is the **Go middleware/backend layer** that sits between the React UI (Scout-itAI) and the AWS Lambda APIs. It handles authentication, job tracking, file management, and proxies requests to AWS services.

---

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Go | 1.25.4 | Runtime |
| gorilla/mux | 1.8.1 | HTTP routing (implicit via net/http) |
| AWS SDK v2 | 1.40.0 | DynamoDB, S3, Bedrock |
| GORM | 1.31.1 | SQL Server ORM (legacy) |
| JWT | 5.3.0 | Authentication |
| InfluxDB Client | 2.14.0 | Time series (metrics) |

---

## Project Structure

```
uidata/
├── cmd/uidata/
│   └── main.go                    # Entry point (port 8086)
├── internal/
│   ├── api/handlers/              # 80+ HTTP handlers
│   │   ├── registerhandlers.go    # Route registration
│   │   ├── handlerApplicationManagement.go  # App/File CRUD (231KB!)
│   │   ├── handlerCodeTransform.go          # O&T transformation
│   │   ├── handlerApplicationCreator.go     # Java generation
│   │   ├── handlerQAAgent.go                # QA processing
│   │   ├── handlerJavaGenerationV3.go       # Java Gen V3
│   │   └── ... (75+ more handlers)
│   ├── service/
│   │   ├── application_service.go   # App/File business logic (103KB!)
│   │   ├── modernization_service.go # Job tracking
│   │   ├── analysis_history_service.go # Run history
│   │   └── ... (20+ services)
│   ├── model/
│   │   ├── types.go                 # Core types
│   │   └── analysis_history.go      # History models
│   ├── middleware/
│   │   ├── middleware.go            # CORS
│   │   ├── ratelimiter.go           # Rate limiting
│   │   └── requestid.go             # Request IDs
│   └── utils/
│       └── httpclient.go            # HTTP client helpers
├── services/                        # External service clients
├── pkg/
│   ├── auth/                        # JWT validation
│   └── config/                      # Configuration
├── claude.md                        # AI coding guidelines
└── *.md                             # Documentation (20+ files)
```

---

## Server Configuration

```go
// main.go
server := &http.Server{
    Addr:              ":8086",
    Handler:           handler,
    ReadHeaderTimeout: 10 * time.Second,
    WriteTimeout:      6 * time.Minute,  // Long for AI calls
    IdleTimeout:       120 * time.Second,
    MaxHeaderBytes:    1 << 20,          // 1 MB
}

// Rate limiting: 100 req/sec per account, burst 200
rateLimiter := middleware.NewRateLimiter(100, 200)
```

---

## AWS Integration

### Lambda API Gateways (Proxied)

| Base URL | Purpose |
|----------|---------|
| `https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod` | Analysis flows (Code, Data, Discovery, Refactor, etc.) |
| `https://msir2392qb.execute-api.us-east-1.amazonaws.com/prod` | Java Generation V2/V3 |

### DynamoDB Tables

| Table | Purpose | Key Schema |
|-------|---------|------------|
| `scout_applications` | Application records | `account_id` (PK), `application_id` (SK) |
| `scout_files` | File records with jobs | `account_id` (PK), `file_id` (SK) |
| `{account}_modernize` | Per-account job tracking | `job_id` (PK) |
| `analysis_history` | Run history | `application_id` (PK), `run_timestamp` (SK) |

### S3 Buckets

| Bucket | Purpose |
|--------|---------|
| `scoutitmodernization` | Uploaded files, generated code |
| `code-transformation-v2` | Analysis outputs |

---

## Authentication Pattern

All requests require:
1. `Authorization: Bearer {jwt_token}` - JWT validation
2. `X-Account-Id: {account_id}` - Multi-tenant isolation

```go
// Every handler starts with:
if err := auth.ValidateJWTToken(r); err != nil {
    w.WriteHeader(http.StatusUnauthorized)
    return
}

accountID := r.Header.Get("X-Account-Id")
if accountID == "" {
    w.WriteHeader(http.StatusBadRequest)
    json.NewEncoder(w).Encode(map[string]string{"error": "X-Account-Id header required"})
    return
}
```

---

## ModernizeIT API Routes

### Application Management

| Method | Endpoint | Handler | Purpose |
|--------|----------|---------|---------|
| POST | `/api/applications` | `handleApplicationOperations` | Create application |
| GET | `/api/applications` | `handleApplicationOperations` | List applications |
| GET | `/api/applications/{id}` | `handleApplicationByID` | Get application |
| PUT | `/api/applications/{id}` | `handleApplicationByID` | Update application |
| DELETE | `/api/applications/{id}` | `handleApplicationByID` | Delete application |

### File Management

| Method | Endpoint | Handler | Purpose |
|--------|----------|---------|---------|
| POST | `/api/applications/files/upload` | `handleFileUpload` | Upload file |
| GET | `/api/applications/files/list` | `handleListFiles` | List files in app |
| GET | `/api/files/urls` | `handleGetFileURLsByFileID` | Get S3 URLs |
| GET | `/api/files/codezip/url` | `handleGetCodeZipURL` | Get generated code URL |
| DELETE | `/api/applications/{appId}/files/{fileId}` | `handleFileRouter` | Delete file |

### Analysis Operations

| Method | Endpoint | Handler | Purpose |
|--------|----------|---------|---------|
| GET | `/api/applications/{id}/analyze` | `handleTriggerAnalysis` | Trigger all analyses |
| POST | `/api/analysis/status` | `handleAnalysisStatus` | Batch status check |
| GET | `/api/files/{id}/analysis` | `handleFileRouter` | Get analysis results |

### Code Transformation (O&T)

| Method | Endpoint | Handler | Purpose |
|--------|----------|---------|---------|
| POST | `/codetransform/upload` | `handleUpload` | Start transformation |
| GET | `/codetransform/status/{id}` | `handleStatus` | Check status |
| GET | `/codetransform/results/{id}` | `handleResults` | Get results |

### Application Creator (Java Generation)

| Method | Endpoint | Handler | Purpose |
|--------|----------|---------|---------|
| POST | `/app-creator/modernize` | `handleModernize` | Start code generation |
| GET | `/app-creator/status/{id}` | `handleStatus` | Check status |
| GET | `/app-creator/results/{id}` | `handleResults` | Get results + download URL |

### QA Agent

| Method | Endpoint | Handler | Purpose |
|--------|----------|---------|---------|
| POST | `/qa-agent/process-files` | `handleProcessFiles` | Run QA analysis |

### Portfolio & Dashboard

| Method | Endpoint | Handler | Purpose |
|--------|----------|---------|---------|
| GET | `/api/portfolio/summary` | `handleGetPortfolioSummary` | Dashboard metrics |
| GET | `/api/applications/{id}/analysis-history` | History handler | Run history |

---

## Data Models

### Application

```go
type Application struct {
    ApplicationID   string `json:"application_id"`
    AccountID       string `json:"account_id"`
    ApplicationName string `json:"application_name"`
    Description     string `json:"description,omitempty"`
    Technology      string `json:"technology,omitempty"`      // COBOL, Java
    CreatedAt       string `json:"created_at"`
    UpdatedAt       string `json:"updated_at"`
    Status          string `json:"status"`                    // active, archived
    FileCount       int    `json:"file_count"`

    // Analysis Job IDs
    CobolJobID         string `json:"cobol_job_id,omitempty"`
    DataJobID          string `json:"data_job_id,omitempty"`
    DiscoveryJobID     string `json:"discovery_job_id,omitempty"`
    RefactorJobID      string `json:"refactor_job_id,omitempty"`
    DependencyJobID    string `json:"dependency_job_id,omitempty"`
    MonolithJobID      string `json:"monolith_job_id,omitempty"`
    ArchitectureJobID  string `json:"architecture_job_id,omitempty"`

    // Status tracking
    CobolStatus        string `json:"cobol_status,omitempty"`
    DataStatus         string `json:"data_status,omitempty"`
    // ... (all status fields)

    OverallStatus      string `json:"overall_status,omitempty"`
    AnalysisStatus     string `json:"analysis_status,omitempty"`
}
```

### FileRecord

```go
type FileRecord struct {
    FileID         string `json:"file_id"`
    ApplicationID  string `json:"application_id"`
    AccountID      string `json:"account_id"`
    FileName       string `json:"file_name"`
    FileType       string `json:"file_type"`        // cobol, java
    FileSize       int64  `json:"file_size"`
    S3Path         string `json:"s3_path"`
    UploadedAt     string `json:"uploaded_at"`
    Status         string `json:"overall_status"`   // uploaded, analyzing, analyzed
    AnalysisStatus string `json:"analysis_status"`

    // Job IDs per analysis type
    COBOLJobID        string `json:"cobol_job_id,omitempty"`
    DataJobID         string `json:"data_job_id,omitempty"`
    DiscoveryJobID    string `json:"discovery_job_id,omitempty"`
    RefactorJobID     string `json:"refactor_job_id,omitempty"`
    DependencyJobID   string `json:"dependency_job_id,omitempty"`
    MonolithJobID     string `json:"monolith_job_id,omitempty"`
    ArchitectureJobID string `json:"architecture_job_id,omitempty"`

    // Pipeline statuses
    CobolStatus          string `json:"cobol_status,omitempty"`
    DataStatus           string `json:"data_status,omitempty"`
    DiscoveryStatus      string `json:"discovery_status,omitempty"`
    RefactorStatus       string `json:"refactor_status,omitempty"`
    DependencyStatus     string `json:"dependency_status,omitempty"`
    MonolithStatus       string `json:"monolith_status,omitempty"`
    ArchitectureStatus   string `json:"architecture_status,omitempty"`
    TransformStatus      string `json:"transform_status,omitempty"`
    JavaGenerationStatus string `json:"java_generation_status,omitempty"`
    QAStatus             string `json:"qa_status,omitempty"`
    CIStatus             string `json:"ci_status,omitempty"`

    // Generated artifacts
    CodeZip    string `json:"codezip,omitempty"`    // S3 URL to Java ZIP
    Complexity string `json:"complexity,omitempty"` // Low, Medium, High
    Platform   string `json:"platform,omitempty"`   // .NET, Java
}
```

### ModernizationRecord (Job Tracking)

```go
type ModernizationRecord struct {
    JobID           string            `json:"job_id"`
    AccountID       string            `json:"account_id"`
    ApplicationName string            `json:"application_name"`
    FileName        string            `json:"file_name"`
    S3Path          string            `json:"s3_path"`
    UploadedAt      string            `json:"uploaded_at"`
    Status          string            `json:"status"`
    AWSJobID        string            `json:"aws_job_id,omitempty"`
    JobType         string            `json:"job_type,omitempty"`
    TTL             int64             `json:"ttl,omitempty"`  // 90 days
    Metadata        map[string]string `json:"metadata,omitempty"`
}
```

---

## Key Implementation Patterns

### 1. Proxy Pattern to AWS

```go
// Example: Code Transform Upload
func (cts *CodeTransformService) handleUpload() http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // 1. Validate JWT and get account ID
        // 2. Parse request (JSON or multipart)
        // 3. Get file from DB if file_id provided
        // 4. Build request for AWS API
        // 5. Call AWS endpoint
        // 6. Save tracking record to DynamoDB
        // 7. Return response with job_id
    }
}
```

### 2. Background Job Completion Waiting

```go
// waitForJobCompletion polls AWS until job completes
go waitForJobCompletion(ctx, jobID, accountID, "cobol", appService, ...)
```

### 3. Multi-Tenant Table Pattern

```go
// Per-account tables for job tracking
tableName := fmt.Sprintf("%s_modernize", accountID)
```

### 4. Status Aggregation

```go
// Compute overall status from individual statuses
func (f *FileRecord) ComputeStatusSummary() FileStatusSummary {
    // Check all individual statuses
    // Return: analyzed, transformed, qaPassed, processing, failed
}
```

---

## AWS Lambda API Endpoints (Proxied)

### Analysis Flows (hzz9izcu47)

| Flow | Start | Status | Results |
|------|-------|--------|---------|
| Code Analysis V3 | POST `/codeanalysis3` | GET `/statusv3/{id}` | GET `/resultsv3/{id}` |
| Data Analysis V2 | POST `/dataanalysis2` | GET `/statusda2/{id}` | GET `/resultsda2/{id}` |
| Discovery V2 | POST `/discovery2` | GET `/statusdv2/{id}` | GET `/resultsdv2/{id}` |
| Refactor V2 | POST `/refactorv2` | GET `/statusrf2/{id}` | GET `/resultsrf2/{id}` |
| Dependency V2 | POST `/dependencymapperv2` | GET `/statusdmv2/{id}` | GET `/resultsdmv2/{id}` |
| Monolith V2 | POST `/monolithidentifierv2` | GET `/statusmiv2/{id}` | GET `/resultsmiv2/{id}` |
| Architecture V2 | POST `/startar2` | GET `/statusar2/{id}` | GET `/resultsar2/{id}` |

### Java Generation (msir2392qb)

| Flow | Start | Status | Results |
|------|-------|--------|---------|
| Java Gen V2 | POST `/startjgv2` | GET `/statusjgv2/{id}` | GET `/resultsjgv2/{id}` |

---

## Job ID Patterns

| Flow | Prefix | Example |
|------|--------|---------|
| Code Analysis V2 | `ca2_job_` | `ca2_job_5150_TestApp_1759534791_abc123` |
| Code Analysis V3 | `ca3_job_` | `ca3_job_5150_TestApp_1759534791_abc123` |
| Data Analysis | `da2_job_` | `da2_job_5150_TestApp_1759534864_def456` |
| Discovery | `dv2_job_` | `dv2_job_5150_TestApp_1759535100_jkl012` |
| Refactor | `rf2_job_` | `rf2_job_5150_TestApp_1759534864_def456` |
| Dependency | `dm2_job_` or `dmv2_job_` | `dmv2_job_5150_TestApp_1759535000_ghi789` |
| Monolith | `mi2_job_` or `miv2_job_` | `miv2_job_5150_TestApp_1759535200_mno345` |
| Architecture | `ar2_job_` | `ar2_job_5150_TestApp_1759535400_stu901` |
| Java Gen V2 | `jgv2_job_` | `jgv2_job_5150_TestApp_1759535500_vwx234` |
| QA Agent | `qa_agent_` | `qa_agent_5150_1759535600` |

---

## Comparison: Go Backend vs Our Python API

| Feature | Go Backend (uidata) | Our Python API (modernizeit-api) |
|---------|--------------------|---------------------------------|
| **Port** | 8086 | 8000 |
| **Auth** | JWT + X-Account-Id | None (local dev) |
| **Storage** | DynamoDB + S3 | SQLite + Local files |
| **Execution** | Proxy to AWS Lambda | Direct engine execution |
| **Multi-tenant** | Yes (per-account tables) | No (single user) |
| **App Management** | Full CRUD | Not implemented |
| **File Tracking** | DynamoDB with status | SQLite jobs table |
| **Job IDs** | AWS format | Local format |

---

## What We Need to Match

To connect our API to the React portal, we need:

### Must Have (High Priority)

| Endpoint | Our Status | Notes |
|----------|------------|-------|
| `POST /api/applications` | Missing | Create app |
| `GET /api/applications` | Missing | List apps |
| `GET /api/applications/{id}` | Missing | Get app |
| `GET /api/applications/files/list` | Missing | List files |
| `POST /api/analysis/status` | Missing | Batch status |
| `GET /api/portfolio/summary` | Missing | Dashboard |

### Already Have (Need Route Mapping)

| Their Route | Our Route | Action Needed |
|-------------|-----------|---------------|
| `/api/applications/files/upload` | `/ingest/upload` | Add route alias |
| `/api/files/{id}/analyze` | `/codeanalysis` | Add route alias |
| `/codetransform/upload` | `/coderefactor` | Add route alias |
| `/app-creator/modernize` | `/java-packaging/start` | Add route alias |
| `/qa-agent/process-files` | `/test-generation/smart` | Add route alias |

### Header Requirements

```python
# All routes need to accept:
X-Account-Id: {account_id}
Authorization: Bearer {jwt_token}  # Optional for local dev
```

---

## Integration Options

### Option A: Adapter Layer in Our API

Create `/uidata/*` routes that:
1. Accept their request format
2. Translate to our internal format
3. Call our engines
4. Translate response back

### Option B: Update Their React App

Modify `cobolModernizationService.ts` to:
1. Point to our API base URL
2. Use our endpoint naming
3. Handle our response format

### Option C: Hybrid

1. Add missing endpoints to our API (Application CRUD)
2. Add route aliases for existing endpoints
3. Support both formats during transition

---

## Files Reference

| File | Size | Purpose |
|------|------|---------|
| `handlerApplicationManagement.go` | 231KB | App/File CRUD, Analysis triggers |
| `application_service.go` | 103KB | Business logic |
| `handlerCodeTransform.go` | 40KB | O&T transformation |
| `handlerJavaGenerationV3.go` | 43KB | Java generation |
| `registerhandlers.go` | 14KB | Route registration |
| `handlerQAAgent.go` | 7KB | QA processing |
| `API_FLOW_RUNBOOK.md` | 24KB | Complete API documentation |

---

## Running the Go Backend

```bash
cd /Users/timhiggins/Desktop/pooja_modernizeit/uidata

# Build
go build -o bin/uidata cmd/uidata/main.go

# Run (needs AWS creds and env vars)
export DB_HOST_READ=...
export DB_USER=...
export DB_PASSWORD=...
export DB_NAME=...
export AWS_REGION=us-east-1

./bin/uidata
# Runs on http://localhost:8086
```

---

*Document created: December 26, 2025*
*Source: /Users/timhiggins/Desktop/pooja_modernizeit/uidata*
