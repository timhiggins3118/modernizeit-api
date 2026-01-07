# Code Analysis V3 - High-Level Design (HLD)

**Flow Name:** Code Analysis V3 (Per-File AI Analysis)
**Version:** V3 (Deployed November 2025)
**Status:** DEPLOYED - Testing/Production Hybrid
**Created:** November 6, 2025
**Purpose:** Per-file structural and AI analysis of COBOL source code

---

## ⚠️ CRITICAL KNOWN ISSUES

**This section documents KNOWN ISSUES with the current V3 implementation:**

### 🔴 Issue #1: Missing Business Logic Extraction (BLOCKING)

**Problem:** JavaGen V3 generates services with empty stubs instead of actual business logic.

**Root Cause:** Code Analysis V3 does NOT extract PROCEDURE DIVISION business logic with Java code equivalents.

**Impact:**
- Generated services contain only logger statements
- No actual business logic implementation
- JavaGen expects `paragraph_analysis[].java_method.code` field (doesn't exist)
- ServiceGeneratorV3 falls back to stub generation

**What's Missing:**
- PROCEDURE DIVISION paragraph extraction
- Paragraph → Java method mapping
- Java code generation for COBOL logic
- `java_method.code` field in static_analysis.json

**Affected Downstream Flows:**
- JavaGen V2 ❌
- JavaGen V3 ❌ (BROKEN - generates stubs only)

**Estimated Fix Effort:** 10-16 days (per user estimate)

**Fix Requires:**
- Update BedrockAnalyzerPerFileV3 prompt to request PROCEDURE DIVISION logic extraction
- Add Java code generation to AI analysis
- Update static_analysis.json schema to include `java_method.code`
- Test with JavaGen V3 to verify services have real code

---

### 🟡 Issue #2: V2 Compatibility Concerns

**Problem:** SummaryGeneratorV3 creates `static_analysis.json` in "V2-compatible format" but may be missing fields V2 flows expect.

**Impact:** Unknown - needs validation with all downstream V2 flows

**Questions:**
- Does V2 JavaGen work with V3 static_analysis.json?
- Are all V2 fields present?
- Does the schema match exactly?

---

### 🟡 Issue #3: Fargate Task Code Not Accessible

**Problem:** Large file analysis runs in Fargate containers, code not easily accessible for review.

**Impact:** Harder to debug issues with large files

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [API Endpoint](#api-endpoint)
4. [Step Functions Workflow](#step-functions-workflow)
5. [Lambda Functions](#lambda-functions)
6. [Fargate Processing](#fargate-processing)
7. [Data Structures](#data-structures)
8. [S3 Storage Layout](#s3-storage-layout)
9. [Integration Points](#integration-points)
10. [Current Implementation](#current-implementation)
11. [Known Limitations](#known-limitations)
12. [V5 Improvement Opportunities](#v5-improvement-opportunities)

---

## Overview

### Purpose

Code Analysis V3 is a **per-file analysis pipeline** that:

- Performs structural analysis using regex-based parser
- Performs AI-powered semantic analysis using AWS Bedrock
- Routes files to Lambda (small) or Fargate (large) based on file size
- Generates per-file analysis results
- Aggregates results into V2-compatible `static_analysis.json`
- Provides input for downstream JavaGen flows

### Key Characteristics

- **Per-File Processing:** Each COBOL file analyzed independently
- **Lambda + Fargate Hybrid:** Small files in Lambda, large files in Fargate
- **Docker-Based:** All 4 Lambdas are Docker images (ECR)
- **Parallel Processing:** Map state with concurrency limits (Lambda: 10, Fargate: 5)
- **V2 Compatible:** Generates static_analysis.json for downstream V2 flows
- **Step Functions Orchestration:** Complete workflow with error handling

### What Changed from V2

| Aspect | V2 | V3 |
|--------|----|----|
| **Processing Model** | Batch (all files together) | Per-file (individual analysis) |
| **Compute** | Lambda only | Lambda + Fargate |
| **File Size Limit** | ~50 KB | ~1 MB (Fargate) |
| **Parallelism** | Limited | High (Map state) |
| **Output Structure** | Single static_analysis.json | Per-file + aggregated |
| **Deployment** | ZIP | Docker (ECR) |

---

## Architecture

### High-Level Workflow

```
User Request (API Gateway)
    |
    | POST /codeanalysis3
    | {scout_account_id, application_name, source_hash}
    |
    V
┌─────────────────────────────────────────────────────────┐
│         CodeAnalysisWorkflowV3 (Step Functions)         │
└─────────────────────────────────────────────────────────┘
    |
    | STEP 1: Structural Analysis
    V
┌─────────────────────────────────────────────────────────┐
│  TreeSitterAnalyzerV3 (Lambda)                          │
│  - Parse ALL COBOL files with regex                     │
│  - Extract structure (sections, paragraphs, variables)  │
│  - Store file_analyses/{file}.json                      │
│  - Returns: job_id, total_files, successful_files       │
└─────────────────────────────────────────────────────────┘
    |
    | STEP 2: Route Files (Lambda vs Fargate)
    V
┌─────────────────────────────────────────────────────────┐
│  PrepareBedrockMapV3 (Lambda)                           │
│  - Read file_analyses/                                  │
│  - Calculate file sizes                                 │
│  - Route: < 100 KB → Lambda, > 100 KB → Fargate        │
│  - Returns: lambda_files[], fargate_files[]             │
└─────────────────────────────────────────────────────────┘
    |
    | STEP 3: Parallel AI Analysis
    V
┌──────────────────────────┬──────────────────────────────┐
│   Lambda Map             │      Fargate Map             │
│   (MaxConcurrency: 10)   │      (MaxConcurrency: 5)     │
│                          │                              │
│  ┌────────────────────┐  │  ┌────────────────────────┐  │
│  │ BedrockAnalyzer    │  │  │ ECS Fargate Task       │  │
│  │ PerFileV3          │  │  │ (bedrock-analyzer)     │  │
│  │                    │  │  │                        │  │
│  │ - Call Bedrock     │  │  │ - Call Bedrock         │  │
│  │ - Extract insights │  │  │ - Extract insights     │  │
│  │ - Store ai_analyses│  │  │ - Store ai_analyses    │  │
│  └────────────────────┘  │  └────────────────────────┘  │
└──────────────────────────┴──────────────────────────────┘
    |
    | STEP 4: Aggregate Results
    V
┌─────────────────────────────────────────────────────────┐
│  SummaryGeneratorV3 (Lambda)                            │
│  - Read file_analyses/ (structural)                     │
│  - Read ai_analyses/ (AI)                               │
│  - Merge per-file results                               │
│  - Generate static_analysis.json (V2 format)            │
│  - Generate structural_context.json                     │
└─────────────────────────────────────────────────────────┘
    |
    | STEP 5: Complete
    V
┌─────────────────────────────────────────────────────────┐
│  Analysis Complete (Pass)                               │
│  - Status: success                                      │
│  - Outputs available in S3                              │
└─────────────────────────────────────────────────────────┘
    |
    V
Downstream Flows (JavaGen V2/V3, etc.)
```

### Component Diagram

```
┌──────────────────────────────────────────────────────────┐
│                  API Gateway                             │
│  https://.../prod/codeanalysis3                          │
└───────────────────┬──────────────────────────────────────┘
                    |
                    | Trigger Execution
                    V
┌──────────────────────────────────────────────────────────┐
│          Step Functions: CodeAnalysisWorkflowV3          │
│                                                          │
│  States:                                                 │
│  1. TreeSitterAnalyzer (Task)                            │
│  2. CheckTreeSitterStatus (Choice)                       │
│  3. PrepareBedrockMap (Task)                             │
│  4. CheckFilesToAnalyze (Choice)                         │
│  5. ProcessFiles (Parallel)                              │
│     - LambdaMap (Map)                                    │
│     - FargateMap (Map)                                   │
│  6. GenerateSummary (Task)                               │
│  7. AnalysisComplete (Pass)                              │
│  8. AnalysisFailed (Fail)                                │
└───────────────────┬──────────────────────────────────────┘
                    |
       ┌────────────┴────────────┐
       |                         |
       V                         V
┌─────────────┐          ┌─────────────┐
│   Lambda    │          │   Fargate   │
│  Functions  │          │   Tasks     │
│             │          │             │
│ - TreeSitter│          │ - Large file│
│ - PrepareMap│          │   analysis  │
│ - Bedrock   │          │ - Bedrock AI│
│ - Summary   │          │             │
└──────┬──────┘          └──────┬──────┘
       |                        |
       └────────────┬───────────┘
                    |
                    V
       ┌────────────────────────┐
       │        S3 Bucket       │
       │  code-transformation-v2│
       │                        │
       │  {account}/{app}/      │
       │  code_analysis_v3/jobs/│
       └────────────────────────┘
```

---

## API Endpoint

### Endpoint Details

```
POST https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/codeanalysis3
```

**Method:** POST
**Content-Type:** `application/json`
**Authentication:** NONE (no API key required)
**Integration:** Step Functions StartExecution

### Request Parameters

```json
{
  "scout_account_id": "string (required)",
  "application_name": "string (required)",
  "source_hash": "string (optional - uses latest if not provided)"
}
```

### Response Format

**Success (HTTP 200):**
```json
{
  "executionArn": "arn:aws:states:us-east-1:376129851858:execution:CodeAnalysisWorkflowV3:api-triggered-1762447258-c754c54a",
  "startDate": "2025-11-06T16:40:58.123Z"
}
```

**Error (HTTP 400/500):**
```json
{
  "error": "Invalid request parameters"
}
```

---

## Step Functions Workflow

### Workflow Definition

**State Machine:** `CodeAnalysisWorkflowV3`
**ARN:** `arn:aws:states:us-east-1:376129851858:stateMachine:CodeAnalysisWorkflowV3`
**Type:** STANDARD
**Status:** ACTIVE
**Created:** November 4, 2025

### State Diagram

```
[START]
   |
   V
TreeSitterAnalyzer (Task)
   |
   | ✅ Success/Partial Success
   V
CheckTreeSitterStatus (Choice)
   |
   | ✅ status = "success" or "partial_success"
   V
PrepareBedrockMap (Task)
   |
   V
CheckFilesToAnalyze (Choice)
   |
   | ✅ lambda_files_count > 0 OR fargate_files_count > 0
   V
ProcessFiles (Parallel)
   |
   +--- Branch 1: LambdaMap (Map)
   |      |
   |      +-- CheckLambdaFiles (Choice)
   |      |
   |      +-- LambdaMap (Map - MaxConcurrency: 10)
   |            |
   |            +-- AnalyzeFileWithLambda (Task)
   |                  |
   |                  +-- BedrockAnalyzerPerFileV3
   |
   +--- Branch 2: FargateMap (Map)
          |
          +-- CheckFargateFiles (Choice)
          |
          +-- FargateMap (Map - MaxConcurrency: 5)
                |
                +-- AnalyzeFileWithFargate (Task)
                      |
                      +-- ECS RunTask (Fargate)
   |
   V
GenerateSummary (Task)
   |
   | ✅ Success
   V
AnalysisComplete (Pass)
   |
   V
[END]
```

### Error Handling

**Retry Strategy (all Lambda tasks):**
- Error Types: `Lambda.ServiceException`, `Lambda.AWSLambdaException`, `Lambda.SdkClientException`
- Max Attempts: 3
- Interval: 2 seconds
- Backoff Rate: 2x

**Catch Strategy:**
- All errors: `States.ALL` → AnalysisFailed

**Fargate Retry Strategy:**
- Error Types: `States.TaskFailed`
- Max Attempts: 2
- Interval: 5 seconds
- Backoff Rate: 2x

---

## Lambda Functions

### 1. TreeSitterAnalyzerV3

**Purpose:** Structural analysis of ALL COBOL files using regex-based parser.

**Runtime:** Docker Image (ECR)
**Image:** `376129851858.dkr.ecr.us-east-1.amazonaws.com/treesitter-analyzer-v3:raw-content`
**Memory:** 3008 MB
**Timeout:** 900 seconds (15 minutes)
**Handler:** (Docker ENTRYPOINT)

**What It Does:**
1. Reads source files from S3: `{account}/{app}/shared/uploads/{hash}/extracted/`
2. Reads classified_catalog.json to get list of COBOL files
3. For each COBOL file:
   - Parse with regex-based parser (NOT actual tree-sitter library)
   - Extract IDENTIFICATION DIVISION (program-id, author, date-written)
   - Extract ENVIRONMENT DIVISION (file-control, input-output)
   - Extract DATA DIVISION (file section, working-storage, linkage)
   - Extract PROCEDURE DIVISION structure (sections, paragraphs)
   - Calculate complexity metrics (LOC, cyclomatic complexity)
4. Store results: `code_analysis_v3/jobs/{job_id}/file_analyses/{filename}.json`
5. Return summary: job_id, total_files, successful_files, failed_files

**Input:**
```json
{
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076..."
}
```

**Output:**
```json
{
  "statusCode": 200,
  "body": {
    "status": "success",
    "job_id": "ca3_job_0U812_TestApp01_1762447258_c754c54a",
    "total_files": 21,
    "successful_files": 21,
    "failed_files": 0,
    "s3_paths": {
      "file_analyses": "s3://.../code_analysis_v3/jobs/{job_id}/file_analyses/"
    }
  }
}
```

**Key Files Generated:**
- `file_analyses/CMCMCL00.CBL.json` (structural analysis for CMCMCL00.CBL)
- `file_analyses/ADCPSH21.CBL.json` (structural analysis for ADCPSH21.CBL)
- etc.

**What's NOT Extracted:**
- ❌ PROCEDURE DIVISION business logic (paragraph code)
- ❌ COBOL → Java code mapping
- ❌ Data flow analysis
- ❌ Call graphs

---

### 2. PrepareBedrockMapV3

**Purpose:** Route files to Lambda or Fargate based on file size.

**Runtime:** Docker Image (ECR)
**Image:** `376129851858.dkr.ecr.us-east-1.amazonaws.com/prepare-bedrock-map-v3:jcl-fix`
**Memory:** (default)
**Timeout:** (default)

**What It Does:**
1. Reads file_analyses/ folder from TreeSitterAnalyzerV3
2. For each analyzed file:
   - Read file size from S3 metadata
   - Classify: < 100 KB → Lambda, >= 100 KB → Fargate
3. Build two arrays:
   - `lambda_files[]` - Files for Lambda processing
   - `fargate_files[]` - Files for Fargate processing
4. Return routing summary

**Routing Logic:**
```python
if file_size < 100_000:  # 100 KB
    lambda_files.append(file_info)
else:
    fargate_files.append(file_info)
```

**Input:**
```json
{
  "job_id": "ca3_job_0U812_TestApp01_1762447258_c754c54a",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076...",
  "total_files": 21,
  "successful_files": 21
}
```

**Output:**
```json
{
  "lambda_files": [
    {
      "job_id": "ca3_job_...",
      "file_name": "ADCPSH21.CBL",
      "scout_account_id": "0U812",
      "application_name": "TestApp01",
      "source_hash": "9ec86076...",
      "file_analysis_s3_key": "0U812/TestApp01/code_analysis_v3/jobs/.../file_analyses/ADCPSH21.CBL.json"
    }
  ],
  "fargate_files": [
    {
      "job_id": "ca3_job_...",
      "file_name": "CMCMCL00.CBL",
      "scout_account_id": "0U812",
      "application_name": "TestApp01",
      "source_hash": "9ec86076...",
      "file_analysis_s3_key": "0U812/TestApp01/code_analysis_v3/jobs/.../file_analyses/CMCMCL00.CBL.json"
    }
  ],
  "summary": {
    "lambda_files_count": 20,
    "fargate_files_count": 1
  }
}
```

**Why This Lambda Exists:**
- Lambda has 15-minute timeout limit
- Large files (> 500 KB) can take > 15 minutes to analyze with Bedrock
- Fargate has no timeout limit, can run for hours

---

### 3. BedrockAnalyzerPerFileV3

**Purpose:** AI-powered semantic analysis of SMALL files using AWS Bedrock.

**Runtime:** Docker Image (ECR)
**Image:** `376129851858.dkr.ecr.us-east-1.amazonaws.com/bedrock-analyzer-per-file-v3:raw-content-lambda`
**Memory:** (default)
**Timeout:** 900 seconds (15 minutes)

**What It Does:**
1. Receives file info from PrepareBedrockMapV3
2. Reads structural analysis: `file_analyses/{filename}.json`
3. Reads COBOL source file: `shared/uploads/{hash}/extracted/{filename}`
4. Calls AWS Bedrock (Claude Sonnet 3.5) with prompt
5. Parses Bedrock response
6. Stores AI analysis: `ai_analyses/{filename}_ai_analysis.json`

**Bedrock Configuration:**
- **Model:** Claude 3.5 Sonnet (`anthropic.claude-3-5-sonnet-20241022-v2:0`)
- **Max Tokens:** 4096
- **Temperature:** 0.0 (deterministic)

**Input (from Step Functions Map):**
```json
{
  "job_id": "ca3_job_...",
  "file_name": "ADCPSH21.CBL",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076...",
  "file_analysis_s3_key": "..."
}
```

**Output:**
```json
{
  "statusCode": 200,
  "body": {
    "status": "success",
    "file_name": "ADCPSH21.CBL",
    "ai_analysis_s3_key": "0U812/TestApp01/code_analysis_v3/jobs/.../ai_analyses/ADCPSH21.CBL_ai_analysis.json"
  }
}
```

**⚠️ CRITICAL ISSUE: Bedrock Prompt Analysis Required**

**What the prompt SHOULD ask for (but may not):**
- ✅ High-level purpose and functionality
- ✅ Data structures and file operations
- ✅ Complexity and maintainability assessment
- ❓ PROCEDURE DIVISION paragraph-by-paragraph analysis
- ❓ Java method code equivalents for each paragraph
- ❌ **NOT generating `java_method.code` field (CONFIRMED)**

**What's Missing (causes JavaGen stubs):**
```json
{
  "paragraph_analysis": [
    {
      "name": "1000-PROCESS-RECORDS",
      "purpose": "Process customer records",
      "java_method": {
        "name": "processRecords",
        "return_type": "void",
        "code": "// MISSING - causes stub generation"
      }
    }
  ]
}
```

**Actual Output (current):**
```json
{
  "paragraph_analysis": [
    {
      "name": "1000-PROCESS-RECORDS",
      "purpose": "Process customer records"
      // NO java_method.code field!
    }
  ]
}
```

---

### 4. SummaryGeneratorV3

**Purpose:** Aggregate all per-file analyses into V2-compatible `static_analysis.json`.

**Runtime:** Docker Image (ECR)
**Image:** `376129851858.dkr.ecr.us-east-1.amazonaws.com/summary-generator-v3:latest`
**Memory:** (default)
**Timeout:** (default)

**What It Does:**
1. Reads ALL `file_analyses/*.json` (structural)
2. Reads ALL `ai_analyses/*_ai_analysis.json` (AI)
3. Merges data for each file
4. Generates `static_analysis.json` in V2 format
5. Generates `structural_context.json` (full context)
6. Stores in `artifacts/` folder

**Input:**
```json
{
  "job_id": "ca3_job_0U812_TestApp01_1762447258_c754c54a",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076..."
}
```

**Output:**
```json
{
  "statusCode": 200,
  "body": {
    "status": "success",
    "artifacts": {
      "static_analysis": "s3://.../artifacts/static_analysis.json",
      "structural_context": "s3://.../artifacts/structural_context.json"
    }
  }
}
```

**Key Files Generated:**
- `artifacts/static_analysis.json` (85 KB) - V2-compatible, used by JavaGen
- `artifacts/structural_context.json` (3.1 MB) - Full context for debugging

**⚠️ V2 Compatibility Concerns:**

The V2 format should include:
```json
{
  "files": [
    {
      "name": "CMCMCL00.CBL",
      "structure": { ... },
      "paragraph_analysis": [
        {
          "name": "1000-PROCESS-RECORDS",
          "java_method": {
            "name": "processRecords",
            "code": "// EXPECTED BY JAVAGEN - MISSING!"
          }
        }
      ]
    }
  ]
}
```

**If `java_method.code` is missing:**
- JavaGen V3 ServiceGeneratorV3 generates stubs
- Services have only logger statements
- No actual business logic

---

## Fargate Processing

### Fargate Task Definition

**Task Definition:** `bedrock-analyzer-fargate:6`
**Cluster:** `code-analysis-cluster`
**Launch Type:** FARGATE
**Purpose:** AI analysis of LARGE files (> 100 KB)

### Configuration

**Networking:**
- VPC Subnets:
  - `subnet-05a88f702ca6880c9`
  - `subnet-07eca6716104acb0b`
- Security Group: `sg-03208a7865d2ff78e`
- Public IP: ENABLED (for Bedrock API access)

**Environment Variables (from Step Functions):**
- `JOB_ID` - Job identifier
- `FILE_NAME` - COBOL filename to analyze
- `SCOUT_ACCOUNT_ID` - Account ID
- `APPLICATION_NAME` - Application name
- `SOURCE_HASH` - Source hash
- `FILE_ANALYSIS_S3_KEY` - S3 path to structural analysis

### How It Works

1. Step Functions starts Fargate task (ECS RunTask.sync)
2. Task pulls Docker image from ECR
3. Runs same logic as BedrockAnalyzerPerFileV3
4. Calls Bedrock with longer timeout
5. Stores result: `ai_analyses/{filename}_ai_analysis.json`
6. Task exits
7. Step Functions continues

**Why Fargate:**
- Lambda 15-minute timeout too short for large files
- Fargate has no timeout limit
- Can allocate more memory/CPU
- Handles files up to several MB

**Limitations:**
- Slower startup (30-60 seconds)
- More expensive than Lambda
- Harder to debug (no direct code access)

---

## Data Structures

### 1. file_analyses/{filename}.json

**Purpose:** Structural analysis of single COBOL file.

**Location:** `{account}/{app}/code_analysis_v3/jobs/{job_id}/file_analyses/{filename}.json`

**Schema:**
```json
{
  "file_name": "string",
  "file_type": "COBOL_PROGRAM | COPYBOOK | JCL | etc.",
  "identification_division": {
    "program_id": "string",
    "author": "string",
    "date_written": "string",
    "date_compiled": "string"
  },
  "environment_division": {
    "configuration_section": {},
    "input_output_section": {
      "file_control": []
    }
  },
  "data_division": {
    "file_section": [],
    "working_storage_section": [],
    "linkage_section": []
  },
  "procedure_division": {
    "sections": [],
    "paragraphs": [
      {
        "name": "string",
        "line_start": "integer",
        "line_end": "integer",
        "statements_count": "integer"
      }
    ]
  },
  "metrics": {
    "lines_of_code": "integer",
    "comment_lines": "integer",
    "cyclomatic_complexity": "integer"
  }
}
```

**Example (partial):**
```json
{
  "file_name": "CMCMCL00.CBL",
  "file_type": "COBOL_PROGRAM",
  "identification_division": {
    "program_id": "CMCMCL00"
  },
  "procedure_division": {
    "paragraphs": [
      {
        "name": "1000-PROCESS-RECORDS",
        "line_start": 450,
        "line_end": 520,
        "statements_count": 35
      }
    ]
  }
}
```

**What's Included:**
- ✅ Program structure (divisions, sections)
- ✅ Data definitions (01-level, 05-level variables)
- ✅ Paragraph names and locations
- ✅ File operations (READ, WRITE, OPEN, CLOSE)
- ✅ Metrics (LOC, complexity)

**What's NOT Included:**
- ❌ Paragraph code/logic
- ❌ Java method equivalents
- ❌ Business logic extraction

---

### 2. ai_analyses/{filename}_ai_analysis.json

**Purpose:** AI-powered semantic analysis of single COBOL file.

**Location:** `{account}/{app}/code_analysis_v3/jobs/{job_id}/ai_analyses/{filename}_ai_analysis.json`

**Schema (expected, but may vary):**
```json
{
  "file_name": "string",
  "analysis_timestamp": "ISO 8601 timestamp",
  "model": "anthropic.claude-3-5-sonnet-20241022-v2:0",
  "purpose": "string (high-level summary)",
  "functionality": "string (detailed description)",
  "data_structures": {
    "file_section": [],
    "working_storage": [],
    "linkage": []
  },
  "paragraph_analysis": [
    {
      "name": "string",
      "purpose": "string",
      "complexity": "LOW | MEDIUM | HIGH",
      "java_method": {
        "name": "string",
        "return_type": "string",
        "parameters": [],
        "code": "string (MISSING!)"
      }
    }
  ],
  "recommendations": []
}
```

**⚠️ CRITICAL: `java_method.code` Field Status**

**Expected:**
```json
{
  "paragraph_analysis": [
    {
      "name": "1000-PROCESS-RECORDS",
      "java_method": {
        "name": "processRecords",
        "code": "public void processRecords() {\n    // Actual Java code here\n}"
      }
    }
  ]
}
```

**Actual (BROKEN):**
```json
{
  "paragraph_analysis": [
    {
      "name": "1000-PROCESS-RECORDS",
      "purpose": "Process customer records"
      // NO java_method.code field!
    }
  ]
}
```

**Impact:**
- ServiceGeneratorV3 checks for `java_method.code`
- If missing → generates stub:
```java
public void processRecords() {
    logger.info("TODO: Implement processRecords");
}
```

---

### 3. artifacts/static_analysis.json

**Purpose:** V2-compatible aggregated analysis for downstream flows.

**Location:** `{account}/{app}/code_analysis_v3/jobs/{job_id}/artifacts/static_analysis.json`

**Size:** ~85 KB (for 21-file project)

**Schema (V2 format):**
```json
{
  "version": "3.0",
  "generated_at": "ISO 8601 timestamp",
  "job_id": "string",
  "source_hash": "string",
  "summary": {
    "total_files": "integer",
    "total_lines_of_code": "integer",
    "average_complexity": "float"
  },
  "files": [
    {
      "name": "string",
      "type": "COBOL_PROGRAM | COPYBOOK | etc.",
      "structure": {
        // From file_analyses/{file}.json
      },
      "ai_insights": {
        // From ai_analyses/{file}_ai_analysis.json
      },
      "paragraph_analysis": [
        {
          "name": "string",
          "purpose": "string",
          "java_method": {
            "name": "string",
            "return_type": "string",
            "code": "string (MISSING!)"
          }
        }
      ]
    }
  ]
}
```

**Consumed By:**
- JavaGen V2 (java_generation_v2)
- JavaGen V3 (java_generation_v3) - ServiceGeneratorV3
- Architecture Recommender V2
- Other downstream V2 flows

**⚠️ JavaGen Dependency:**

JavaGen V3 ServiceGeneratorV3 reads `static_analysis.json` and looks for:
```python
for file in static_analysis['files']:
    for paragraph in file.get('paragraph_analysis', []):
        java_code = paragraph.get('java_method', {}).get('code', None)
        if java_code:
            # Use actual code
        else:
            # Generate stub (CURRENT BEHAVIOR)
```

---

### 4. artifacts/structural_context.json

**Purpose:** Complete structural context for debugging and analysis.

**Location:** `{account}/{app}/code_analysis_v3/jobs/{job_id}/artifacts/structural_context.json`

**Size:** ~3.1 MB (for 21-file project)

**Contents:**
- Complete file_analyses/ data for all files
- Complete ai_analyses/ data for all files
- Full COBOL source text for each file
- Cross-file relationships
- Call graphs (if extracted)

**Use Cases:**
- Debugging analysis issues
- Manual code review
- Training data for ML models
- Backup/archive

**NOT used by downstream flows** (too large)

---

## S3 Storage Layout

### Bucket Structure

```
code-transformation-v2/
└── {scout_account_id}/              # e.g., "0U812"
    └── {application_name}/          # e.g., "TestApp01"
        └── code_analysis_v3/
            └── jobs/
                └── {job_id}/        # e.g., ca3_job_0U812_TestApp01_1762447258_c754c54a
                    │
                    ├── file_analyses/
                    │   ├── CMCMCL00.CBL.json     (1 MB)
                    │   ├── ADCPSH21.CBL.json     (26 KB)
                    │   ├── CMCSCL50.CBL.json     (46 KB)
                    │   └── ... (21 files total)
                    │
                    ├── ai_analyses/
                    │   ├── CMCMCL00.CBL_ai_analysis.json
                    │   ├── ADCPSH21.CBL_ai_analysis.json
                    │   ├── CMCSCL50.CBL_ai_analysis.json
                    │   └── ... (21 files total)
                    │
                    └── artifacts/
                        ├── static_analysis.json       (85 KB - V2 format)
                        └── structural_context.json    (3.1 MB - full context)
```

### Path Patterns

**File Analyses:**
```
s3://code-transformation-v2/{account}/{app}/code_analysis_v3/jobs/{job_id}/file_analyses/{filename}.json
```

**AI Analyses:**
```
s3://code-transformation-v2/{account}/{app}/code_analysis_v3/jobs/{job_id}/ai_analyses/{filename}_ai_analysis.json
```

**Aggregated Artifacts:**
```
s3://code-transformation-v2/{account}/{app}/code_analysis_v3/jobs/{job_id}/artifacts/static_analysis.json
s3://code-transformation-v2/{account}/{app}/code_analysis_v3/jobs/{job_id}/artifacts/structural_context.json
```

### Job ID Format

**Pattern:**
```
ca3_job_{scout_account_id}_{application_name}_{unix_timestamp}_{uuid}
```

**Example:**
```
ca3_job_0U812_TestApp01_1762447258_c754c54a
```

**Components:**
- Prefix: `ca3_job_` (Code Analysis V3)
- Account: `0U812`
- Application: `TestApp01`
- Timestamp: `1762447258` (Unix epoch seconds)
- UUID: `c754c54a` (first 8 chars of UUID)

---

## Integration Points

### Upstream Dependencies

#### 1. Ingest Flow (REQUIRED)

**Reads From:**
- `{account}/{app}/shared/uploads/{hash}/extracted/` - COBOL source files
- `{account}/{app}/shared/catalogs/{hash}/classified_catalog.json` - File list
- `{account}/{app}/shared/type_mappings/{hash}/cobol_to_java.json` - Type mappings

**Why:**
- TreeSitterAnalyzerV3 needs source files to analyze
- PrepareBedrockMapV3 needs classified_catalog to know which files are COBOL
- Cannot run without Ingest completing first

### Downstream Consumers

#### 1. Java Generation V3 (java_generation_v3) - ⚠️ BROKEN

**Reads:**
- `code_analysis_v3/jobs/{job_id}/artifacts/static_analysis.json`

**Expects:**
```json
{
  "files": [
    {
      "paragraph_analysis": [
        {
          "java_method": {
            "code": "// EXPECTS THIS FIELD!"
          }
        }
      ]
    }
  ]
}
```

**Current Behavior:**
- Reads static_analysis.json
- Looks for `paragraph_analysis[].java_method.code`
- **Field is MISSING**
- Falls back to stub generation
- Services contain only logger statements

**Fix Required:**
- BedrockAnalyzerPerFileV3 must extract business logic
- Must generate `java_method.code` field
- SummaryGeneratorV3 must include in static_analysis.json

#### 2. Java Generation V2 (java_generation_v2) - ⚠️ UNKNOWN

**Compatibility:** Unknown - needs testing

**Questions:**
- Does V2 JavaGen work with V3 static_analysis.json?
- Does it expect `java_method.code` field?
- Or does it use different logic?

#### 3. Architecture Recommender V2 (architecture_recommender_v2)

**Reads:**
- `artifacts/static_analysis.json` (summary metrics)

**Uses:**
- File count
- Complexity metrics
- Program structure
- **Does NOT need business logic**

**Status:** ✅ Should work (metrics-based, not code-based)

#### 4. Other V2 Flows

**Flows that may consume static_analysis.json:**
- Code Refactor V2
- Dependency Mapper V2
- Monolith Identifier V2
- Data Analyzer V2

**Status:** ⚠️ Unknown - needs validation

---

## Current Implementation

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Lambda Runtime | Docker (Python base) | Custom images |
| AWS Services | Step Functions, Lambda, Fargate, Bedrock | Latest |
| Bedrock Model | Claude 3.5 Sonnet | anthropic.claude-3-5-sonnet-20241022-v2:0 |
| Container Registry | ECR | us-east-1 |
| Storage | S3 | code-transformation-v2 bucket |

### Lambda Configurations

| Function | Memory | Timeout | Package Type | Image Tag |
|----------|--------|---------|--------------|-----------|
| TreeSitterAnalyzerV3 | 3008 MB | 900s (15m) | Image | raw-content |
| PrepareBedrockMapV3 | Default | Default | Image | jcl-fix |
| BedrockAnalyzerPerFileV3 | Default | 900s (15m) | Image | raw-content-lambda |
| SummaryGeneratorV3 | Default | Default | Image | latest |

### Step Functions Configuration

| Setting | Value |
|---------|-------|
| Type | STANDARD |
| Logging | OFF |
| Tracing | Disabled |
| Execution Role | StepFunctionsExecutionRole |

### Performance Characteristics

**Small Project (< 10 files, < 100 KB each):**
- TreeSitter: 10-30 seconds
- PrepareMap: 2-5 seconds
- Lambda Map: 30-60 seconds (parallel)
- Summary: 5-10 seconds
- **Total: 1-2 minutes**

**Medium Project (20 files, mixed sizes):**
- TreeSitter: 30-60 seconds
- PrepareMap: 5-10 seconds
- Lambda Map: 1-3 minutes (parallel)
- Fargate Map: 5-15 minutes (parallel)
- Summary: 10-20 seconds
- **Total: 6-16 minutes**

**Large Project (100+ files, some > 1 MB):**
- TreeSitter: 2-5 minutes
- PrepareMap: 10-20 seconds
- Lambda Map: 5-10 minutes (parallel)
- Fargate Map: 30-60 minutes (parallel)
- Summary: 30-60 seconds
- **Total: 36-66 minutes**

### Concurrency Limits

| Component | Max Concurrency | Reason |
|-----------|----------------|--------|
| Lambda Map | 10 | Balance cost vs speed |
| Fargate Map | 5 | Fargate capacity limits |
| Bedrock API | Account-level limit | Throttling protection |

---

## Known Limitations

### 1. Missing Business Logic Extraction (CRITICAL)

**See "CRITICAL KNOWN ISSUES" section at top of document.**

### 2. Large File Timeout Risk

**Problem:** Even with Fargate, extremely large files (> 5 MB) may timeout Bedrock API calls.

**Impact:** Analysis fails for massive monolithic programs

**Workaround:** None currently

**Solution for V5:** Chunk large files, analyze in segments

### 3. No Call Graph Extraction

**Problem:** Code Analysis V3 does not extract CALL relationships between programs.

**Impact:**
- Cannot determine program dependencies
- Microservice decomposition harder
- Architecture recommendations less accurate

**Solution for V5:** Add CALL statement parsing, build dependency graph

### 4. No Data Flow Analysis

**Problem:** Does not track how data flows through paragraphs.

**Impact:**
- Cannot optimize data structures
- Harder to identify side effects
- Refactoring riskier

**Solution for V5:** Add data flow analysis to TreeSitterAnalyzerV3

### 5. Copybook Handling

**Problem:** Copybooks are analyzed as separate files, not expanded inline.

**Impact:**
- Data structure references incomplete
- Variable definitions may be missing
- Java entity generation may fail

**Solution for V5:** Expand copybooks before analysis

### 6. JCL Classification Issue

**Problem:** JCL files may be misclassified as "unknown" or analyzed as COBOL.

**Impact:** Wasted analysis effort, incorrect results

**Fix:** Tag says "jcl-fix" but may not be fully resolved

### 7. No Incremental Analysis

**Problem:** Re-running analysis re-processes ALL files, even unchanged ones.

**Impact:** Wasted time and cost

**Solution for V5:** Hash-based change detection, only analyze modified files

### 8. Bedrock Cost

**Problem:** Bedrock API calls are expensive (~$0.01-0.10 per file depending on size).

**Impact:** Large projects (1000+ files) can cost $10-100 per analysis

**Solution for V5:** Cache results, incremental analysis, optimize prompts

### 9. Docker Image Size

**Problem:** Lambda Docker images are large (500 MB - 2 GB).

**Impact:** Slow cold starts (10-30 seconds)

**Solution for V5:** Optimize images, use Lambda layers, cache dependencies

### 10. No Validation

**Problem:** No validation that Bedrock response is correct or complete.

**Impact:** Incorrect analysis may go undetected

**Solution for V5:** Add response validation, quality checks, confidence scores

---

## V5 Improvement Opportunities

### High Priority

#### 1. Fix Business Logic Extraction (BLOCKING)

**Problem:** Services have empty stubs (see "CRITICAL KNOWN ISSUES")

**Solution:**
1. Update BedrockAnalyzerPerFileV3 prompt:
```
For each paragraph in PROCEDURE DIVISION:
- Extract paragraph name
- Extract paragraph purpose
- Generate equivalent Java method:
  - Method name (camelCase)
  - Return type
  - Parameters
  - FULL Java code implementation

Return format:
{
  "paragraph_analysis": [
    {
      "name": "1000-PROCESS-RECORDS",
      "purpose": "Process customer records",
      "java_method": {
        "name": "processRecords",
        "return_type": "void",
        "parameters": [],
        "code": "public void processRecords() {\n    // Full implementation\n}"
      }
    }
  ]
}
```

2. Update SummaryGeneratorV3 to include `java_method.code` in static_analysis.json

3. Test with JavaGen V3 to verify services have real code

**Effort:** 10-16 days (per user estimate)

**Impact:** Fixes the #1 blocker for JavaGen V3

#### 2. Add Call Graph Extraction

**Problem:** No CALL relationship tracking

**Solution:**
- TreeSitterAnalyzerV3 parses CALL statements
- Extract: `CALL 'SUBPROGRAM' USING param1, param2`
- Build dependency graph
- Store in static_analysis.json: `call_graph[]`

**Benefits:**
- Microservice decomposition
- Dependency analysis
- Architecture recommendations

**Effort:** 3-5 days

#### 3. Incremental Analysis

**Problem:** Re-processes all files every time

**Solution:**
- Hash each source file
- Compare with previous analysis hashes
- Only analyze changed files
- Reuse cached results for unchanged files

**Benefits:**
- 10-100x faster re-analysis
- 10-100x cheaper
- Better developer experience

**Effort:** 5-7 days

### Medium Priority

#### 4. Copybook Expansion

**Problem:** Copybooks not expanded inline

**Solution:**
- TreeSitterAnalyzerV3 resolves COPY statements
- Loads copybook content
- Expands inline before analysis
- Tracks copybook dependencies

**Benefits:**
- Complete data structure visibility
- Better entity generation
- More accurate analysis

**Effort:** 7-10 days

#### 5. Data Flow Analysis

**Problem:** No data flow tracking

**Solution:**
- Analyze how variables are read/written
- Track data flow through paragraphs
- Identify side effects
- Generate data flow diagrams

**Benefits:**
- Better refactoring
- Identify hidden dependencies
- Optimize data structures

**Effort:** 10-14 days

#### 6. Bedrock Response Validation

**Problem:** No validation of AI output

**Solution:**
- Schema validation (JSON structure)
- Completeness checks (all expected fields)
- Code syntax validation (Java code compiles)
- Confidence scoring

**Benefits:**
- Catch errors early
- Improve quality
- Reduce JavaGen failures

**Effort:** 3-5 days

### Low Priority

#### 7. Cost Optimization

**Problem:** Bedrock API calls expensive

**Solution:**
- Optimize prompts (shorter = cheaper)
- Use Claude Haiku for simple files
- Batch small files into single prompt
- Cache frequently-seen patterns

**Benefits:**
- 50-80% cost reduction

**Effort:** 5-7 days

#### 8. Docker Image Optimization

**Problem:** Large images, slow cold starts

**Solution:**
- Multi-stage builds
- Remove unnecessary dependencies
- Use Lambda layers for common libs
- Pre-warm containers

**Benefits:**
- 5-10x faster cold starts
- Smaller images
- Lower costs

**Effort:** 3-5 days

#### 9. Real Tree-Sitter Parser

**Problem:** Currently using regex, not actual tree-sitter library

**Solution:**
- Use tree-sitter-cobol library
- Generate proper AST
- More accurate parsing
- Better error handling

**Benefits:**
- More accurate analysis
- Handles edge cases
- Industry-standard tooling

**Effort:** 7-10 days (learning curve)

#### 10. Streaming Responses

**Problem:** Large Bedrock responses can timeout

**Solution:**
- Use Bedrock streaming API
- Process response incrementally
- Store partial results
- Resume on failure

**Benefits:**
- Handle larger files
- Better progress tracking
- More resilient

**Effort:** 5-7 days

---

## Appendix

### A. Sample Job Execution (Nov 6, 2025)

**Execution ARN:** `arn:aws:states:us-east-1:376129851858:execution:CodeAnalysisWorkflowV3:api-triggered-1762447258-c754c54a`

**Input:**
```json
{
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74"
}
```

**Results:**
- **Total Files Analyzed:** 21
- **Lambda Files:** 20
- **Fargate Files:** 1 (CMCMCL00.CBL - 550 KB)
- **Duration:** ~8 minutes
- **Status:** SUCCESS

**Outputs:**
- 21 structural analyses (file_analyses/)
- 21 AI analyses (ai_analyses/)
- 1 static_analysis.json (85 KB)
- 1 structural_context.json (3.1 MB)

### B. File Size Distribution (Sample Project)

| File | Size | Route |
|------|------|-------|
| CMCMCL00.CBL | 550 KB | Fargate |
| DICPCC00.CBL | 22 KB | Lambda |
| CMCSCL50.CBL | 24 KB | Lambda |
| UTCSUL10.CBL | 20 KB | Lambda |
| ADCPSH21.CBL | 18 KB | Lambda |
| Others (16 files) | < 10 KB | Lambda |

### C. Bedrock API Costs (Estimated)

**Model:** Claude 3.5 Sonnet
**Pricing:** $3.00 per million input tokens, $15.00 per million output tokens

**Small File (< 10 KB):**
- Input: ~5,000 tokens
- Output: ~2,000 tokens
- Cost: $0.045 per file

**Medium File (50 KB):**
- Input: ~25,000 tokens
- Output: ~5,000 tokens
- Cost: $0.15 per file

**Large File (500 KB):**
- Input: ~250,000 tokens
- Output: ~20,000 tokens
- Cost: $1.05 per file

**21-File Project (Sample):**
- Total Cost: ~$2.00

**1000-File Project:**
- Total Cost: ~$50-100

### D. Comparison: V2 vs V3

| Aspect | V2 | V3 |
|--------|----|----|
| **Architecture** | Monolithic batch | Per-file pipeline |
| **Parallelism** | Low | High (Map state) |
| **File Size Limit** | ~50 KB | ~1 MB (Fargate) |
| **Lambda Timeout** | 15 minutes (all files) | 15 minutes (per file) |
| **Compute** | Lambda only | Lambda + Fargate |
| **Outputs** | Single JSON | Per-file + aggregated |
| **Deployment** | ZIP files | Docker images |
| **Incremental** | No | No (planned for V5) |
| **Cost** | Lower (fewer Bedrock calls) | Higher (per-file calls) |
| **Debugging** | Harder (single log stream) | Easier (per-file logs) |
| **Business Logic** | ❓ Unknown | ❌ Missing (BROKEN) |

---

**Document Status:** COMPLETE (with Known Issues documented)
**Last Updated:** November 6, 2025
**Author:** Claude Code (Van Halen mode)
**Version:** 1.0
**Known Issues:** 10 documented (1 CRITICAL)

**⚠️ CRITICAL: Code Analysis V3 does NOT extract PROCEDURE DIVISION business logic with Java code equivalents. This causes JavaGen V3 to generate services with empty stubs. Fix required before production use.**
