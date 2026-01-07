# Ingest Flow - High-Level Design (HLD)

**Flow Name:** Ingest / File Upload
**Version:** V2 (Production)
**Status:** LIVE - 100+ Users
**Created:** November 6, 2025
**Purpose:** Entry point for COBOL modernization pipeline

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [API Endpoint](#api-endpoint)
4. [Lambda Handler Flow](#lambda-handler-flow)
5. [Data Structures](#data-structures)
6. [S3 Storage Layout](#s3-storage-layout)
7. [Integration Points](#integration-points)
8. [Current Implementation](#current-implementation)
9. [Known Limitations](#known-limitations)
10. [V5 Improvement Opportunities](#v5-improvement-opportunities)

---

## Overview

### Purpose

The Ingest flow is the **entry point** for the entire Cobalt ETL Studio modernization pipeline. It:

- Accepts ZIP or single file uploads containing COBOL source code
- Uses content-addressed storage with SHA-256 hashing
- Prevents duplicate uploads through hash-based deduplication
- Classifies files by type (COBOL, copybook, JCL, SQL, etc.)
- Generates COBOL→Java type mapping templates
- Stores files in standardized S3 structure for downstream flows

### Key Characteristics

- **Single Lambda:** No Step Functions orchestration needed
- **Fast:** Typical execution time: 2-30 seconds (depending on ZIP size)
- **Idempotent:** Duplicate uploads detected and handled gracefully
- **Stateless:** Each invocation is independent
- **Content-Addressed:** SHA-256 ensures data integrity and deduplication

---

## Architecture

### Components

```
┌─────────────┐
│   Client    │
│  (Browser/  │
│   Postman)  │
└──────┬──────┘
       │
       │ POST /ingest/upload
       │ multipart/form-data
       │
┌──────▼────────────────────────────────────────┐
│         API Gateway                           │
│  ID: hzz9izcu47                              │
│  Resource: /ingest/upload (v58pre)           │
│  Integration: AWS_PROXY                      │
│  Timeout: 29s                                │
└──────┬────────────────────────────────────────┘
       │
       │ Lambda Invocation
       │ (with base64-encoded body)
       │
┌──────▼────────────────────────────────────────┐
│   IngestUploadHandlerv2 (Lambda)             │
│   Runtime: Python 3.9                        │
│   Memory: 512 MB                             │
│   Timeout: 60s                               │
│   Handler: ingest_upload_handler.lambda_handler │
└──────┬────────────────────────────────────────┘
       │
       │ S3 Put Operations
       │
┌──────▼────────────────────────────────────────┐
│   S3 Bucket: code-transformation-v2          │
│   /{account}/{app}/shared/                   │
│     - uploads/{hash}/                        │
│     - catalogs/{hash}/                       │
│     - type_mappings/{hash}/                  │
│   /{account}/{app}/ingest/jobs/{job_id}/     │
└──────┬────────────────────────────────────────┘
       │
       │ Files ready for downstream
       │
┌──────▼────────────────────────────────────────┐
│   Downstream Flows                           │
│   - Discovery                                │
│   - Code Analysis V2                         │
│   - Code Refactor V2                         │
│   - etc.                                     │
└──────────────────────────────────────────────┘
```

### IAM Role

**Role Name:** `BedrockAgentRole-CodeRefactor`
**ARN:** `arn:aws:iam::376129851858:role/BedrockAgentRole-CodeRefactor`

**Attached Policies:**
- `AWSLambdaBasicExecutionRole` - CloudWatch Logs access

**Relevant Inline Policies:**
- `S3AccessCodeTransformationV2` - Read/write access to code-transformation-v2 bucket
- `BedrockAndS3Access` - Additional S3 permissions

**Note:** This is a shared IAM role used across multiple V2 flows. Only S3 permissions are used by Ingest.

---

## API Endpoint

### Endpoint Details

```
POST https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/ingest/upload
```

**Method:** POST
**Content-Type:** `multipart/form-data`
**Authentication:** NONE (no API key required)
**Timeout:** 29 seconds (API Gateway limit)
**Integration:** AWS_PROXY to Lambda (passes request directly)

### Request Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | ZIP archive or single COBOL file |
| `scout_account_id` | Text | Yes | Customer account identifier (e.g., "0U812") |
| `application_name` | Text | Yes | Application name (e.g., "TestApp01") |
| `automate_flow` | Text | No | "true" to trigger downstream flows automatically |

### Response Format

**Success (HTTP 201):**
```json
{
  "job_id": "ingest_job_0U812_TestApp01_1731778790_9ec86076",
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74",
  "duplicate": false,
  "paths": {
    "upload_root": "s3://code-transformation-v2/0U812/TestApp01/shared/uploads/9ec860.../",
    "extracted": "s3://code-transformation-v2/0U812/TestApp01/shared/uploads/9ec860.../extracted/",
    "catalogs": "s3://code-transformation-v2/0U812/TestApp01/shared/catalogs/9ec860.../",
    "latest_pointer": "s3://code-transformation-v2/0U812/TestApp01/shared/uploads/latest.json"
  },
  "automate_flow": false,
  "next": [
    "POST /discovery/jobs",
    "POST /code_analyze/jobs",
    "POST /transform/jobs"
  ]
}
```

**Duplicate Upload (HTTP 200):**
```json
{
  "job_id": "ingest_job_0U812_TestApp01_1731778999_9ec86076",
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74",
  "duplicate": true,
  "paths": { ... },
  "automate_flow": false,
  "next": []
}
```

**Error (HTTP 400/500):**
```json
{
  "error": "Missing required field: file"
}
```

---

## Lambda Handler Flow

### Main Flow (lambda_handler)

```
1. Parse API Gateway Event
   ├─ Extract Content-Type header
   ├─ Validate multipart/form-data
   └─ Call parse_multipart_form_data()

2. Validate Required Fields
   ├─ Check: file (File)
   ├─ Check: scout_account_id (Text)
   └─ Check: application_name (Text)

3. Extract Form Data
   ├─ file_data (bytes)
   ├─ scout_account_id (string)
   ├─ application_name (string)
   └─ automate_flow (boolean, default: false)

4. Compute Content Hash
   ├─ SHA-256 hash of file content
   └─ source_hash = hashlib.sha256(file_content).hexdigest()

5. Generate Job ID
   └─ Pattern: ingest_job_{account}_{app}_{timestamp}_{hash[:8]}
   └─ Example: ingest_job_0U812_TestApp01_1731778790_9ec86076

6. Check for Duplicate Upload
   ├─ Check if S3 key exists: {account}/{app}/shared/uploads/{hash}/extracted/
   ├─ If EXISTS: Return success response (duplicate=true)
   └─ If NOT EXISTS: Continue to step 7

7. Process Upload (ZIP or Single File)
   ├─ IF filename.endswith('.zip'):
   │  ├─ Store original: {upload_path}/uploaded_application_files.zip
   │  ├─ Extract ZIP: zipfile.ZipFile(io.BytesIO(file_content))
   │  └─ Store each extracted file: {upload_path}/extracted/{original_path}
   │
   └─ ELSE (single file):
      └─ Store file: {upload_path}/extracted/{filename}

8. Generate Catalogs
   ├─ file_catalog.json (raw file list with sizes)
   └─ classified_catalog.json (files grouped by type)

9. Generate Type Mappings (if COBOL detected)
   ├─ IF classified_catalog['summary']['cobol'] > 0:
   │  ├─ Generate cobol_to_java.json (PIC → SQL/Java type mapping template)
   │  └─ Generate metadata.json (source_hash, detected_languages, file counts)
   └─ Store in: {account}/{app}/shared/type_mappings/{hash}/

10. Update Latest Pointer
    └─ Store: {account}/{app}/shared/uploads/latest.json
    └─ Contains: {"source_hash": "...", "updated_at": "..."}

11. Create Job Metadata
    ├─ job_info.json (job details, inputs, timestamps)
    └─ status.json (state: "completed", progress: 1.0)
    └─ Store in: {account}/{app}/ingest/jobs/{job_id}/

12. Return Success Response
    └─ HTTP 201 with job_id, source_hash, S3 paths
```

### Multipart Form Data Parsing (parse_multipart_form_data)

**Challenge:** API Gateway base64-encodes binary uploads, which can corrupt ZIP files if not handled correctly.

**Solution:**
```python
1. Extract boundary from Content-Type header
2. Detect if body is base64-encoded (isBase64Encoded flag)
3. Decode base64 if needed: base64.b64decode(body)
4. Split body on boundary markers (--{boundary})
5. For each part:
   ├─ Split headers from content (look for \r\n\r\n)
   ├─ Parse Content-Disposition header
   ├─ Extract field_name and filename (if present)
   ├─ If filename exists: Store as binary (file upload)
   └─ If no filename: Decode as UTF-8 text (form field)
6. Return form_data dictionary
```

**Key Implementation Detail:**
- File content is kept as **raw bytes** (NOT decoded to UTF-8)
- Trailing CRLF (\r\n) is stripped from content
- ZIP magic bytes (0x504B) are validated

### File Classification Logic (generate_classified_catalog)

Files are classified by extension:

| Category | Extensions | Storage Key |
|----------|-----------|-------------|
| `cobol` | .cbl, .cobol, .cob | `classifications.cobol[]` |
| `copybook` | .cpy, .copy | `classifications.copybook[]` |
| `jcl` | .jcl, .jbc, .job | `classifications.jcl[]` |
| `sql` | .sql, .ddl | `classifications.sql[]` |
| `config` | .json, .xml, .yaml, .yml, .properties | `classifications.config[]` |
| `documentation` | .txt, .md | `classifications.documentation[]` |
| `unknown` | (all others) | `classifications.unknown[]` |

**Example:**
- `CMCMCL00.CBL` → `cobol`
- `UTXSFS00.CLP` → `unknown` (CLP not recognized)
- `README.md` → `documentation`

---

## Data Structures

### 1. file_catalog.json

**Purpose:** Complete listing of all extracted files with metadata.

**Location:** `{account}/{app}/shared/catalogs/{hash}/file_catalog.json`

**Schema:**
```json
{
  "source_hash": "string (SHA-256)",
  "generated_at": "ISO 8601 timestamp",
  "total_files": "integer",
  "total_size": "integer (bytes)",
  "files": [
    {
      "path": "string (relative path from ZIP root)",
      "size": "integer (bytes)",
      "content_type": "string (MIME type)"
    }
  ]
}
```

**Example:**
```json
{
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74",
  "generated_at": "2025-11-06T16:39:50.221360+00:00",
  "total_files": 21,
  "total_size": 659502,
  "files": [
    {
      "path": "IBMi-Cobol/Cobol/CMCMCL00.CBL",
      "size": 550724,
      "content_type": "application/octet-stream"
    },
    {
      "path": "IBMi-Cobol/CLP/UTXSFS00.CLP",
      "size": 5911,
      "content_type": "application/octet-stream"
    }
  ]
}
```

**Usage:**
- Downstream flows read this to discover all uploaded files
- Used by Code Analysis V2 to determine which files to analyze
- Provides file size metrics for progress tracking

### 2. classified_catalog.json

**Purpose:** Files grouped by type (COBOL, copybook, JCL, etc.) with summary counts.

**Location:** `{account}/{app}/shared/catalogs/{hash}/classified_catalog.json`

**Schema:**
```json
{
  "source_hash": "string (SHA-256)",
  "generated_at": "ISO 8601 timestamp",
  "classifications": {
    "cobol": ["array of file paths"],
    "copybook": ["array of file paths"],
    "jcl": ["array of file paths"],
    "sql": ["array of file paths"],
    "config": ["array of file paths"],
    "documentation": ["array of file paths"],
    "unknown": ["array of file paths"]
  },
  "summary": {
    "cobol": "integer",
    "copybook": "integer",
    "jcl": "integer",
    "sql": "integer",
    "config": "integer",
    "documentation": "integer",
    "unknown": "integer"
  }
}
```

**Example:**
```json
{
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74",
  "generated_at": "2025-11-06T16:39:50.221412+00:00",
  "classifications": {
    "cobol": [
      "IBMi-Cobol/Cobol/CMCMCL00.CBL",
      "IBMi-Cobol/Cobol/CMCSCL50.CBL"
    ],
    "copybook": [],
    "jcl": [],
    "sql": [],
    "config": [],
    "documentation": [],
    "unknown": ["IBMi-Cobol/CLP/UTXSFS00.CLP"]
  },
  "summary": {
    "cobol": 20,
    "copybook": 0,
    "jcl": 0,
    "sql": 0,
    "config": 0,
    "documentation": 0,
    "unknown": 1
  }
}
```

**Usage:**
- Discovery flow uses this to understand application composition
- Code Analysis V2 uses `cobol[]` array to determine which files to analyze
- Architecture Recommender uses summary counts for recommendations

### 3. cobol_to_java.json

**Purpose:** Template for COBOL PIC clause → SQL/Java type mappings.

**Location:** `{account}/{app}/shared/type_mappings/{hash}/cobol_to_java.json`

**Important:** This is a **TEMPLATE**, not actual mappings extracted from the code. It provides guidance for downstream analysis phases.

**Schema:**
```json
{
  "version": "string",
  "source_language": "string",
  "target_language": "string",
  "mappings": {
    "{category}": {
      "description": "string",
      "detection_rules": ["array of rules"],
      "sql_type": "string",
      "java_type": "string",
      "examples": ["array of PIC clause examples"]
    }
  },
  "default_mapping": {
    "sql_type": "string",
    "java_type": "string"
  },
  "generated_at": "ISO 8601 timestamp",
  "source_hash": "string (SHA-256)"
}
```

**Categories:**
- `numeric_with_decimal` → DECIMAL / BigDecimal
- `numeric_integer` → INTEGER / Integer
- `alphanumeric` → VARCHAR / String
- `date` → DATE / LocalDate

**Example:**
```json
{
  "version": "1.0",
  "source_language": "COBOL",
  "target_language": "Java",
  "mappings": {
    "numeric_with_decimal": {
      "description": "Numeric fields with decimal places",
      "detection_rules": [
        "contains 'V' (implied decimal point)",
        "contains '.' (explicit decimal point)"
      ],
      "sql_type": "DECIMAL",
      "java_type": "BigDecimal",
      "examples": ["9(7)V99", "S9(5)V9(2)"]
    }
  },
  "default_mapping": {
    "sql_type": "VARCHAR",
    "java_type": "String"
  }
}
```

**Usage:**
- Code Analysis V2 uses this as reference when extracting data structures
- Java Generation V2/V3 uses this to map COBOL types to Java types
- Not meant to be modified - it's a static template

### 4. metadata.json

**Purpose:** Metadata about generated type mappings.

**Location:** `{account}/{app}/shared/type_mappings/{hash}/metadata.json`

**Schema:**
```json
{
  "source_hash": "string (SHA-256)",
  "generated_at": "ISO 8601 timestamp",
  "mappings_created": ["array of mapping filenames"],
  "detected_languages": ["array of language names"],
  "cobol_file_count": "integer"
}
```

**Example:**
```json
{
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74",
  "generated_at": "2025-11-06T16:39:50.322063+00:00",
  "mappings_created": ["cobol_to_java.json"],
  "detected_languages": ["cobol"],
  "cobol_file_count": 20
}
```

### 5. latest.json

**Purpose:** Pointer to most recent upload for this account/app.

**Location:** `{account}/{app}/shared/uploads/latest.json`

**Schema:**
```json
{
  "source_hash": "string (SHA-256)",
  "updated_at": "ISO 8601 timestamp"
}
```

**Usage:**
- Allows downstream flows to automatically find latest upload without knowing hash
- Simplifies API calls (don't need to pass source_hash explicitly)

### 6. job_info.json

**Purpose:** Job metadata for tracking this ingest operation.

**Location:** `{account}/{app}/ingest/jobs/{job_id}/job_info.json`

**Schema:**
```json
{
  "job_id": "string (job identifier)",
  "function": "string (always 'ingest')",
  "scout_account_id": "string",
  "application_name": "string",
  "created_at": "ISO 8601 timestamp",
  "source_hash": "string (SHA-256)",
  "inputs": {
    "automate_flow": "boolean"
  }
}
```

### 7. status.json

**Purpose:** Job status for tracking completion.

**Location:** `{account}/{app}/ingest/jobs/{job_id}/status.json`

**Schema:**
```json
{
  "state": "string (completed, failed, in_progress)",
  "started_at": "ISO 8601 timestamp",
  "finished_at": "ISO 8601 timestamp",
  "progress": "float (0.0 - 1.0)",
  "message": "string"
}
```

---

## S3 Storage Layout

### Bucket Structure

```
code-transformation-v2/
└── {scout_account_id}/              # e.g., "0U812"
    └── {application_name}/          # e.g., "TestApp01"
        │
        ├── shared/                  # Content-addressed storage (by hash)
        │   │
        │   ├── uploads/
        │   │   ├── {source_hash}/
        │   │   │   ├── uploaded_application_files.zip  # Original ZIP (if uploaded)
        │   │   │   └── extracted/                      # Extracted files
        │   │   │       └── {original_folder_structure}/
        │   │   │           ├── CMCMCL00.CBL
        │   │   │           ├── CMCSCL50.CBL
        │   │   │           └── ...
        │   │   │
        │   │   └── latest.json      # Pointer to most recent hash
        │   │
        │   ├── catalogs/
        │   │   └── {source_hash}/
        │   │       ├── file_catalog.json
        │   │       └── classified_catalog.json
        │   │
        │   └── type_mappings/
        │       └── {source_hash}/
        │           ├── cobol_to_java.json
        │           └── metadata.json
        │
        └── ingest/                  # Job-specific metadata
            └── jobs/
                └── {job_id}/        # e.g., ingest_job_0U812_TestApp01_1731778790_9ec86076
                    ├── job_info.json
                    └── status.json
```

### Path Patterns

**Uploaded Files:**
```
s3://code-transformation-v2/{account}/{app}/shared/uploads/{hash}/extracted/{file_path}
```

**Catalogs:**
```
s3://code-transformation-v2/{account}/{app}/shared/catalogs/{hash}/file_catalog.json
s3://code-transformation-v2/{account}/{app}/shared/catalogs/{hash}/classified_catalog.json
```

**Type Mappings:**
```
s3://code-transformation-v2/{account}/{app}/shared/type_mappings/{hash}/cobol_to_java.json
s3://code-transformation-v2/{account}/{app}/shared/type_mappings/{hash}/metadata.json
```

**Job Metadata:**
```
s3://code-transformation-v2/{account}/{app}/ingest/jobs/{job_id}/job_info.json
s3://code-transformation-v2/{account}/{app}/ingest/jobs/{job_id}/status.json
```

### Content-Addressed Storage

**Why SHA-256 Hashing?**
1. **Deduplication:** Same content always produces same hash
2. **Integrity:** Detects file corruption
3. **Caching:** Duplicate uploads skip processing
4. **Immutability:** Content never changes (hash = identifier)

**Example:**
```
Source File: IBMi-Cobol.zip
SHA-256: 9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74

Upload 1: Stored at shared/uploads/9ec86076.../
Upload 2 (same file): Skipped storage, returns existing path
Upload 3 (different file): New hash, stored at shared/uploads/{new_hash}.../
```

---

## Integration Points

### Upstream Dependencies

**NONE** - Ingest is the entry point for the modernization pipeline.

### Downstream Consumers

#### 1. Discovery Flow (step0_discovery)

**Reads:**
- `shared/uploads/{hash}/extracted/` - All source files
- `shared/catalogs/{hash}/classified_catalog.json` - File classification

**Purpose:**
- Analyze application structure
- Extract business logic metadata
- Generate application profile

#### 2. Code Analysis V2 (02_code_analysis_v2)

**Reads:**
- `shared/uploads/{hash}/extracted/` - COBOL files
- `shared/catalogs/{hash}/file_catalog.json` - List of files to analyze
- `shared/catalogs/{hash}/classified_catalog.json` - COBOL file list
- `shared/type_mappings/{hash}/cobol_to_java.json` - Type mapping reference

**Produces:**
- `code_analysis_v2/jobs/{ca2_job_id}/artifacts/static_analysis.json`
- Per-file analysis results

**Purpose:**
- Tree-sitter structural analysis
- Bedrock AI semantic analysis
- ERD generation
- Complexity metrics

#### 3. Code Refactor V2 (code_refactor)

**Reads:**
- Output from Code Analysis V2

**Purpose:**
- Refactor COBOL code
- Modernize patterns
- Optimize structure

#### 4. Java Generation V2/V3 (java_generation_v2, java_generation_v3)

**Reads:**
- `shared/uploads/{hash}/extracted/` - Original COBOL files
- `shared/type_mappings/{hash}/cobol_to_java.json` - Type mapping template
- Output from Code Analysis V2 (static_analysis.json, ERD.json)

**Produces:**
- Spring Boot application (Java)
- Docker configuration
- Database schema

**Purpose:**
- Transform COBOL → Java
- Generate entities, services, controllers
- Create runnable Spring Boot app

#### 5. Other V2 Flows

- **Dependency Mapper V2:** Analyzes file dependencies
- **Monolith Identifier V2:** Identifies monolithic components
- **Data Analyzer V2:** Analyzes data structures
- **Architecture Recommender V2:** Recommends target architecture

### API Response Contract

The `"next"` field in the success response lists available downstream endpoints:

```json
{
  "next": [
    "POST /discovery/jobs",
    "POST /code_analyze/jobs",
    "POST /transform/jobs"
  ]
}
```

**If automate_flow=true:**
- `"next"` array is empty
- Downstream flows are triggered automatically (future feature)

---

## Current Implementation

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Lambda Runtime | Python | 3.9 |
| AWS SDK | Boto3 | (included in Lambda runtime) |
| ZIP Handling | zipfile (stdlib) | - |
| Hashing | hashlib (stdlib) | - |
| Base64 Encoding | base64 (stdlib) | - |

### Lambda Configuration

| Setting | Value |
|---------|-------|
| Function Name | IngestUploadHandlerv2 |
| Runtime | python3.9 |
| Memory | 512 MB |
| Timeout | 60 seconds |
| Ephemeral Storage | 512 MB |
| Architecture | x86_64 |
| Handler | ingest_upload_handler.lambda_handler |
| Code Size | 5,608 bytes (uncompressed) |
| Package Type | Zip |

### Performance Characteristics

| Upload Size | File Count | Typical Duration |
|-------------|-----------|------------------|
| < 1 MB | < 10 files | 2-5 seconds |
| 1-5 MB | 10-100 files | 5-15 seconds |
| 5-10 MB | 100-500 files | 15-30 seconds |
| 10+ MB | 500+ files | 30-60 seconds |

**Note:** API Gateway has a 10 MB payload limit.

### Error Handling

| Error Type | HTTP Status | Response |
|------------|-------------|----------|
| Missing field | 400 | `{"error": "Missing required field: {field}"}` |
| Invalid content type | 400 | `{"error": "Content-Type must be multipart/form-data"}` |
| Empty file | 400 | `{"error": "File content is empty"}` |
| S3 error | 500 | `{"error": "Internal server error: {details}"}` |
| Unexpected exception | 500 | `{"error": "Internal server error: {details}"}` |

### Logging

**CloudWatch Log Group:** `/aws/lambda/IngestUploadHandlerv2`

**Log Events:**
- Request context (API Gateway request ID)
- Content-Type header value
- File size and hash
- ZIP validation (magic bytes check)
- Extracted file count
- S3 operations
- Catalog generation
- Type mapping generation
- Job ID creation
- Success/failure messages
- Full stack traces on errors

---

## Known Limitations

### 1. File Size Limits

**API Gateway Limit:** 10 MB maximum payload size

**Impact:**
- Large COBOL projects (> 10 MB) cannot be uploaded in single ZIP
- Workaround: Split into multiple ZIPs, upload separately

**Potential Solutions for V5:**
- Use S3 pre-signed URLs for direct upload (bypasses API Gateway)
- Implement multipart upload for large files
- Support S3 bucket trigger (upload directly to S3)

### 2. File Type Detection

**Current:** Simple extension-based classification (.cbl, .cpy, .jcl)

**Limitations:**
- CLP files classified as "unknown" (not recognized)
- No content-based detection (magic bytes, file headers)
- Case-sensitive extension matching (though `.lower()` is used)

**Impact:**
- Non-standard file extensions may be misclassified
- Downstream flows may miss files

**Potential Solutions for V5:**
- Add content-based detection using magic bytes
- Support configurable extension mappings
- Add "custom" classification category

### 3. No Virus Scanning

**Current:** No virus/malware scanning on uploads

**Risk:** Malicious files could be uploaded to S3

**Potential Solutions for V5:**
- Integrate ClamAV Lambda layer
- Use AWS GuardDuty for S3 malware scanning
- Implement file type whitelist

### 4. No Progress Tracking

**Current:** Upload is synchronous (blocks until complete)

**Limitations:**
- No progress updates for large uploads
- Client times out if upload takes > 29 seconds (API Gateway timeout)

**Potential Solutions for V5:**
- Asynchronous processing with progress updates via WebSocket
- Break upload into chunks with progress callback
- Use S3 multipart upload with progress tracking

### 5. No Validation

**Current:** No validation of COBOL syntax or file structure

**Limitations:**
- Invalid COBOL files are stored without detection
- Errors only discovered in downstream flows

**Potential Solutions for V5:**
- Basic syntax validation during upload
- Tree-sitter parsing to verify structure
- Early error detection before downstream processing

### 6. No Rollback

**Current:** If Lambda fails mid-execution, partial S3 state may exist

**Limitations:**
- Extracted files may be stored without catalogs
- Job metadata may be missing
- No cleanup of partial uploads

**Potential Solutions for V5:**
- Transactional S3 operations (store all or nothing)
- Cleanup Lambda to remove partial uploads
- State machine to track upload lifecycle

### 7. Python 3.9 (Outdated)

**Current:** Python 3.9 runtime (released October 2020)

**Limitations:**
- Python 3.9 reaches end-of-life October 2025
- Missing modern Python features (3.10+ match/case, 3.11 perf improvements)

**Potential Solutions for V5:**
- Upgrade to Python 3.12 or 3.13
- Containerize with custom runtime (Docker)

### 8. No Compression Optimization

**Current:** Files stored as-is (no re-compression)

**Limitations:**
- Storage costs for large projects
- Slower downloads for downstream flows

**Potential Solutions for V5:**
- Re-compress extracted files with optimal settings
- Use S3 Intelligent-Tiering for cost optimization
- Implement caching layer (ElastiCache)

---

## V5 Improvement Opportunities

### High Priority

#### 1. Large File Support (S3 Pre-Signed URLs)

**Problem:** 10 MB API Gateway limit blocks large projects

**Solution:**
```
1. Client requests pre-signed URL from API
2. API returns S3 pre-signed URL (PUT)
3. Client uploads directly to S3 (no size limit)
4. S3 event notification triggers IngestUploadHandlerv2
5. Lambda processes file from S3 (same logic as current)
```

**Benefits:**
- No size limit (up to 5 TB with multipart upload)
- Faster uploads (direct to S3, no Lambda proxy)
- Lower API Gateway costs

**Complexity:** Medium

#### 2. Enhanced File Classification

**Problem:** CLP and other non-standard extensions are "unknown"

**Solution:**
```python
ENHANCED_CLASSIFICATIONS = {
    'cobol': ['.cbl', '.cobol', '.cob'],
    'copybook': ['.cpy', '.copy'],
    'jcl': ['.jcl', '.jbc', '.job'],
    'sql': ['.sql', '.ddl'],
    'config': ['.json', '.xml', '.yaml', '.yml', '.properties'],
    'documentation': ['.txt', '.md'],
    'clp': ['.clp'],           # IBM i Control Language
    'rpg': ['.rpg', '.rpgle'],  # IBM i RPG
    'dds': ['.dds'],            # IBM i DDS
    'custom': []                # User-defined
}
```

**Benefits:**
- Better classification for IBM i projects
- Downstream flows can handle all file types
- User-configurable classifications

**Complexity:** Low

#### 3. Async Processing with Progress Tracking

**Problem:** No visibility into upload progress for large files

**Solution:**
```
1. Client uploads to S3 pre-signed URL (with multipart upload)
2. Client receives job_id immediately
3. Lambda processes asynchronously
4. Status updates written to S3: status.json (progress: 0.0 → 1.0)
5. Client polls status endpoint or receives WebSocket updates
```

**Benefits:**
- Handles uploads > 10 MB
- Real-time progress updates
- Better user experience

**Complexity:** High

#### 4. Python 3.12+ Upgrade

**Problem:** Python 3.9 is outdated, reaches EOL soon

**Solution:**
- Upgrade to Python 3.12 or 3.13
- Test all functionality (zipfile, hashlib, boto3)
- Update deployment scripts

**Benefits:**
- Modern language features
- Performance improvements (3.11: 25% faster, 3.12: 10% faster)
- Security updates

**Complexity:** Low

### Medium Priority

#### 5. Basic COBOL Syntax Validation

**Problem:** Invalid COBOL files discovered late in pipeline

**Solution:**
```python
def validate_cobol_syntax(file_content):
    """Basic COBOL validation"""
    required_divisions = [
        b'IDENTIFICATION DIVISION',
        b'ENVIRONMENT DIVISION',
        b'DATA DIVISION',
        b'PROCEDURE DIVISION'
    ]

    for division in required_divisions:
        if division not in file_content:
            return False, f"Missing {division.decode()}"

    return True, "Valid"
```

**Benefits:**
- Early error detection
- Faster feedback loop
- Reduced wasted downstream processing

**Complexity:** Medium

#### 6. Compression Optimization

**Problem:** Large storage costs for unoptimized files

**Solution:**
- Re-compress extracted files with gzip (level 9)
- Store compressed versions alongside originals
- Downstream flows decompress on-demand

**Benefits:**
- 50-80% storage cost reduction
- Faster downloads for downstream flows
- S3 Intelligent-Tiering cost optimization

**Complexity:** Medium

#### 7. Virus Scanning

**Problem:** No malware detection

**Solution:**
- Integrate ClamAV Lambda layer
- Scan all uploads before storage
- Quarantine suspicious files

**Benefits:**
- Security compliance
- Protection against malicious uploads
- Audit trail

**Complexity:** Medium

### Low Priority

#### 8. Metadata Extraction

**Problem:** No COBOL metadata extracted during upload

**Solution:**
- Extract PROGRAM-ID from IDENTIFICATION DIVISION
- Extract FD entries for file structures
- Extract 01-level entries for data structures
- Store in `metadata_extract.json`

**Benefits:**
- Faster downstream processing
- Pre-populated catalog
- Better search/discovery

**Complexity:** High

#### 9. Multi-Language Support

**Problem:** Only COBOL is supported

**Solution:**
- Add type mappings for other languages:
  - C++ → Java
  - FORTRAN → Python
  - PL/I → Java
- Detect language from file content
- Generate language-specific catalogs

**Benefits:**
- Platform expansion
- Multi-language modernization projects
- Reusable architecture

**Complexity:** High

#### 10. Transactional S3 Operations

**Problem:** Partial uploads leave incomplete state

**Solution:**
- Use S3 Object Lock or DynamoDB for transactional tracking
- Store all artifacts atomically
- Cleanup Lambda for failed uploads

**Benefits:**
- Consistency guarantee
- No orphaned files
- Easier debugging

**Complexity:** High

---

## Appendix

### A. Example curl Command

```bash
curl -X POST \
  'https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/ingest/upload' \
  -F 'file=@/path/to/IBMi-Cobol.zip' \
  -F 'scout_account_id=0U812' \
  -F 'application_name=TestApp01' \
  -F 'automate_flow=false'
```

### B. Example Python Client

```python
import requests

url = 'https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/ingest/upload'

files = {
    'file': open('/path/to/IBMi-Cobol.zip', 'rb')
}

data = {
    'scout_account_id': '0U812',
    'application_name': 'TestApp01',
    'automate_flow': 'false'
}

response = requests.post(url, files=files, data=data)
print(response.json())
```

### C. Supported File Extensions

```python
SUPPORTED_EXTENSIONS = [
    '.cbl', '.cobol', '.cob',    # COBOL
    '.cpy', '.copy',              # Copybooks
    '.jcl', '.jbc', '.job',       # JCL
    '.sql', '.ddl',               # SQL
    '.txt', '.md',                # Documentation
    '.json', '.xml', '.properties', '.yaml', '.yml',  # Config
    '.zip'                        # Archives
]
```

### D. Job ID Format

**Pattern:**
```
ingest_job_{scout_account_id}_{application_name}_{unix_timestamp}_{hash_prefix}
```

**Example:**
```
ingest_job_0U812_TestApp01_1731778790_9ec86076
```

**Components:**
- Prefix: `ingest_job_`
- Account: `0U812`
- Application: `TestApp01`
- Timestamp: `1731778790` (Unix epoch seconds)
- Hash: `9ec86076` (first 8 chars of SHA-256)

---

**Document Status:** COMPLETE
**Last Updated:** November 6, 2025
**Author:** Claude Code (Van Halen mode)
**Version:** 1.0
