# Ingest Flow - AWS Download Log

**Downloaded:** November 6, 2025, 11:45 AM
**Purpose:** Capture CURRENT state of production Ingest flow for V5 HLD creation
**Status:** ✅ COMPLETE

---

## What Was Downloaded

### 1. Lambda Functions (1)
- **IngestUploadHandlerv2**
  - Location: `lambda_functions/IngestUploadHandlerv2/`
  - Code: `ingest_upload_handler.py`
  - Config: `function_config.json`
  - Runtime: Python 3.9
  - Size: 5,608 bytes
  - Handler: `ingest_upload_handler.lambda_handler`

### 2. API Gateway Configuration
- Location: `api_gateway/`
- Files:
  - `ingest_resources.json` - Resource definitions for `/ingest/upload`
  - `ingest_method_POST.json` - POST method configuration with Lambda integration

### 3. IAM Roles
- Location: `iam_roles/`
- Files:
  - `BedrockAgentRole-CodeRefactor.json` - Shared role used by Ingest Lambda
  - Contains: Role definition, attached policies, inline policies list

### 4. Step Functions
- Location: `step_functions/`
- Files:
  - `NO_STEP_FUNCTIONS.json` - Note documenting this flow doesn't use Step Functions

### 5. Sample Outputs
- Location: `sample_outputs/`
- Files from actual production run (0U812/TestApp01):
  - `file_catalog.json` - Complete file listing with sizes and paths
  - `classified_catalog.json` - Files classified by type (COBOL, copybook, JCL, etc.)
  - `cobol_to_java.json` - COBOL PIC → SQL → Java type mappings
  - `metadata.json` - Upload metadata (hash, timestamp, account info)

---

## S3 Storage Pattern Observed

```
code-transformation-v2/
└── {account_id}/
    └── {application_name}/
        └── shared/
            ├── uploads/{sha256_hash}/
            │   └── extracted/
            │       └── {original_folder_structure}/
            │           └── {source_files}
            ├── catalogs/{sha256_hash}/
            │   ├── file_catalog.json
            │   └── classified_catalog.json
            └── type_mappings/{sha256_hash}/
                ├── cobol_to_java.json
                └── metadata.json
```

**Key Insight:** Uses content-addressed storage with SHA-256 hashing for deduplication.

---

## API Endpoint

```
POST https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/ingest/upload
```

**API Gateway ID:** `hzz9izcu47`
**Resource ID:** `v58pre` (for `/ingest/upload`)
**Integration:** AWS_PROXY to Lambda
**Timeout:** 29 seconds (API Gateway)
**Auth:** NONE (no API key required)

---

## Next Steps

1. ✅ Download complete
2. ⏳ Analyze Lambda handler code
3. ⏳ Document data flow
4. ⏳ Create detailed HLD
5. ⏳ Identify V5 improvements

---

**Downloaded from AWS Region:** us-east-1
**AWS Account:** 376129851858
**All files are READ-ONLY snapshots of production**
