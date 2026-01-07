# Dependency Mapper V2 - High-Level Design (HLD)

**Version:** V2 (Production)
**Status:** ✅ ACTIVE (Serving 100+ users)
**Created:** October 3, 2025
**Analyzed:** November 6, 2025
**Purpose:** Analyze COBOL program dependencies, suggest microservice boundaries, calculate impact analysis

---

## ⚠️ QUESTIONS & POTENTIAL ISSUES

### 🟡 Question #1: Microservice Boundary Consumption

**Question:** What consumes `microservice_boundaries.json`? Is this used downstream?

**What We Know:**
- Output includes suggested microservice boundaries
- Services grouped by cohesion/coupling scores
- Rich justification for each service boundary
- No downstream flow references found yet

**Possible Consumers:**
- Architecture Recommender V2?
- Customer UI for manual review?
- JavaGen V3 for service decomposition?
- Future refactoring flows?

**Impact:** If not consumed:
- Is this just informational?
- Should V5 integrate this with architecture planning?

---

### 🟡 Question #2: AI Analysis Scope

**Question:** What does AIDeepAnalysis Lambda actually analyze beyond static parsing?

**What We Know:**
- AIDeepAnalysis Lambda exists (5-minute timeout)
- Output: `ai_dependency_analysis.json` (4.3 KB - small)
- Uses Bedrock Claude 3.5 Sonnet
- Runs AFTER static analysis is complete

**What's Unclear:**
- Does it find semantic dependencies (business logic relationships)?
- Does it validate static parser results?
- Does it add hidden dependencies not found by regex?
- Is 4.3 KB output meaningful or minimal?

**Impact on V5:**
- Should V5 enhance AI analysis?
- Is current AI analysis delivering value?

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Diagram](#architecture-diagram)
3. [API Endpoint](#api-endpoint)
4. [Step Functions Workflow](#step-functions-workflow)
5. [Lambda Functions](#lambda-functions)
6. [Data Structures](#data-structures)
7. [S3 Storage Layout](#s3-storage-layout)
8. [Integration Points](#integration-points)
9. [Current Implementation](#current-implementation)
10. [Sample Execution Analysis](#sample-execution-analysis)
11. [Known Limitations](#known-limitations)
12. [V5 Improvement Opportunities](#v5-improvement-opportunities)
13. [Appendix](#appendix)

---

## Overview

### Purpose

Dependency Mapper V2 is a **comprehensive dependency analysis and microservice planning flow** that:

1. **Analyzes COBOL Dependencies:** Detects CALL, COPY, FILE I/O, and DATABASE dependencies
2. **Builds Dependency Graph:** Creates nodes (programs) and edges (dependencies) graph
3. **Calculates Coupling Metrics:** Fan-in, fan-out, coupling scores per program
4. **Assesses Risk:** Identifies high-risk programs based on complexity and dependencies
5. **Detects Microservice Boundaries:** Suggests service boundaries using coupling/cohesion analysis
6. **Calculates Impact:** Determines blast radius for each program (impact analysis)

### Key Characteristics

| Characteristic | Value |
|----------------|-------|
| **Package Type** | ZIP (all 9 Lambdas) |
| **Runtime** | Python 3.11 |
| **Step Functions** | DependencyMapperWorkflowV2 |
| **Lambda Count** | 9 functions |
| **Processing Mode** | Batch + Parallel + Sequential |
| **MaxConcurrency** | 40 (for static parsing) |
| **AI Integration** | AWS Bedrock (Claude 3.5 Sonnet) |
| **Execution Time** | ~29 seconds (20 files) |
| **Output Artifacts** | 7 analysis files + 4 batch files |

### What Makes V2 Different

**Compared to Discovery Flow (V1):**
- **Focus:** Dependency analysis for modernization planning (not just documentation)
- **Outputs:** Microservice boundaries, coupling metrics, impact analysis
- **AI Integration:** Bedrock for semantic dependency detection
- **Graph-Based:** Constructs full dependency graph with nodes/edges
- **Actionable:** Provides concrete microservice boundary recommendations

**Compared to Code Analysis V3:**
- **Different Purpose:** Dependency analysis vs. code structure analysis
- **Graph Focus:** Builds inter-program dependency graph (not intra-file analysis)
- **Planning Tool:** Helps with architecture decisions (not code generation)

---

## Architecture Diagram

```
                    ┌─────────────────────────────────────────┐
                    │  Dependency Mapper V2 Workflow          │
                    │  (Step Functions)                       │
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  1. PrepareAnalysis                     │
                    │  - Reads source files                   │
                    │  - Creates 4 batches (5 files each)     │
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
        ┌───────────────────────────┴───────────────────────────┐
        │           2. StaticAnalysisMap (Parallel)             │
        │           MaxConcurrency: 40                          │
        ├───────────┬──────────┬──────────┬─────────────────────┤
        │  Batch 0  │  Batch 1 │  Batch 2 │  Batch 3            │
        │  (5 files)│ (5 files)│ (5 files)│ (5 files)           │
        │  ↓        │  ↓       │  ↓       │  ↓                  │
        │  Static   │  Static  │  Static  │  Static             │
        │  Parser   │  Parser  │  Parser  │  Parser             │
        └───────────┴──────────┴──────────┴─────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  3. MergeStaticAnalysis                 │
                    │  - Combines all batch results           │
                    │  - Produces: static_analysis.json       │
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  4. AIDeepAnalysis                      │
                    │  - Bedrock Claude 3.5 Sonnet            │
                    │  - Semantic dependency detection        │
                    │  - Produces: ai_dependency_analysis.json│
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  5. BuildDependencyGraph                │
                    │  - Creates nodes (programs)             │
                    │  - Creates edges (dependencies)         │
                    │  - Produces: dependency_graph.json      │
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
        ┌───────────────────────────┴───────────────────────────┐
        │         6. ParallelAnalysis (2 Branches)              │
        ├──────────────────────────────┬────────────────────────┤
        │  CouplingCalculator          │  RiskAssessor          │
        │  - Fan-in / Fan-out          │  - Risk classification │
        │  - Coupling scores           │  - Complexity analysis │
        │  - Produces:                 │  - Produces:           │
        │    coupling_metrics.json     │    risk_assessment.json│
        └──────────────────────────────┴────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  7. MicroserviceDetector                │
                    │  - Groups programs by cohesion/coupling │
                    │  - Suggests service boundaries          │
                    │  - Produces:                            │
                    │    microservice_boundaries.json         │
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  8. ImpactAnalyzer                      │
                    │  - Calculates blast radius              │
                    │  - Impact scores per program            │
                    │  - Produces: impact_analysis.json       │
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  OUTPUTS (7 Artifacts)                  │
                    ├─────────────────────────────────────────┤
                    │  1. static_analysis.json                │
                    │  2. ai_dependency_analysis.json         │
                    │  3. dependency_graph.json               │
                    │  4. coupling_metrics.json               │
                    │  5. risk_assessment.json                │
                    │  6. microservice_boundaries.json        │
                    │  7. impact_analysis.json                │
                    └─────────────────────────────────────────┘
```

---

## API Endpoint

### Endpoint: /dependencymapperv2

**URL:** `https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/dependencymapperv2`

**Method:** POST

**Request Body:**
```json
{
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74"
}
```

**Response:**
```json
{
  "job_id": "dmv2_job_0U812_TestApp01_1762439738_3581cb90",
  "status": "started",
  "execution_arn": "arn:aws:states:us-east-1:376129851858:execution:DependencyMapperWorkflowV2:execution-dmv2_job_0U812_TestApp01_1762439738_3581cb90"
}
```

**Example Request:**
```bash
curl -X POST https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/dependencymapperv2 \
  -H "Content-Type: application/json" \
  -d '{
    "scout_account_id": "0U812",
    "application_name": "TestApp01",
    "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74"
  }'
```

**Expected Preconditions:**
- Source files must exist in S3 (content-addressed by source_hash)
- Ingest flow must have completed successfully
- `source_hash` must match uploaded files

**Triggers:**
- API Gateway POST request → Lambda → Step Functions StartExecution

---

## Step Functions Workflow

### Workflow: DependencyMapperWorkflowV2

**ARN:** `arn:aws:states:us-east-1:376129851858:stateMachine:DependencyMapperWorkflowV2`

### State Machine Definition

#### 1. CaptureStartTime (Pass State)
**Purpose:** Capture workflow start timestamp

**Output:**
```json
{
  "workflow_metadata": {
    "started_at": "2025-11-06T14:35:38.739Z"
  }
}
```

#### 2. UpdateStatusRunning (S3 PutObject)
**Purpose:** Write job status to S3

**S3 Key Pattern:**
```
{account}/{app}/dependency_mapper_v2/jobs/{job_id}/status.json
```

**Status Body:**
```json
{
  "state": "running",
  "started_at": "2025-11-06T14:35:38.739Z",
  "phase": "initializing",
  "progress": 5,
  "message": "Starting dependency analysis..."
}
```

#### 3. PrepareAnalysis (Lambda)
**Lambda:** `DependencyMapperV2PrepareAnalysis`

**Purpose:**
- Read source files from S3 (content-addressed by source_hash)
- Split files into batches for parallel processing
- Create batch metadata

**Input:**
```json
{
  "job_id": "dmv2_job_...",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076..."
}
```

**Output:**
```json
{
  "job_id": "dmv2_job_...",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076...",
  "total_files": 20,
  "total_batches": 4,
  "batches": [
    {
      "batch_id": 0,
      "files": ["file1.CBL", "file2.CBL", "file3.CBL", "file4.CBL", "file5.CBL"]
    },
    ...
  ]
}
```

**Batch Strategy:**
- **Batch Size:** 5 files per batch (default)
- **Reason:** Balance parallelism vs. Lambda cold start overhead

#### 4. StaticAnalysisMap (Map State)
**Type:** Distributed Map
**MaxConcurrency:** 40
**ItemsPath:** `$.preparation.batches`

**Purpose:** Process each batch in parallel for static dependency parsing

**Map Iterator: StaticParser Lambda**

**Per-Batch Processing:**
1. Parse each file for dependencies:
   - CALL statements
   - COPY statements
   - FILE I/O operations
   - DATABASE operations
2. Store results to S3 temp folder

**Output (per batch):**
```json
{
  "batch_id": 0,
  "files_analyzed": 5,
  "dependencies_found": [
    {
      "program": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
      "calls": [],
      "copies": [
        {"copybook": "STDPROCESS", "line": 1},
        {"copybook": "DDS-CMFHCL00", "line": 89}
      ],
      "file_io": [
        {"operation": "READ", "file": "CMLHCL00-FILE", "line": 489}
      ],
      "database": []
    }
  ],
  "analyzed_at": "2025-11-06T14:35:42.395367+00:00"
}
```

**Retry Policy:**
- ErrorEquals: `["States.ALL"]`
- MaxAttempts: 3
- IntervalSeconds: 2
- BackoffRate: 2.0

#### 5. MergeStaticAnalysis (Lambda)
**Lambda:** `DependencyMapperV2MergeStatic`

**Purpose:**
- Combine all batch results
- De-duplicate dependencies
- Create unified static_analysis.json

**Input:**
```json
{
  "job_id": "dmv2_job_...",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "total_batches": 4
}
```

**Output:**
```json
{
  "merged_file": "s3://.../artifacts/static_analysis.json",
  "total_programs": 20
}
```

**S3 Output:**
```
{account}/{app}/dependency_mapper_v2/jobs/{job_id}/artifacts/static_analysis.json
```

#### 6. AIDeepAnalysis (Lambda)
**Lambda:** `DependencyMapperV2AIAnalyzer`
**Timeout:** 300 seconds (5 minutes)

**Purpose:**
- AI-powered semantic dependency detection using Bedrock
- Find hidden/implicit dependencies not detected by static parsing
- Validate static parser results

**Bedrock Configuration:**
- Model: Claude 3.5 Sonnet
- Region: us-east-1
- Max Tokens: ~10000 (estimated)

**Input:**
```json
{
  "job_id": "dmv2_job_...",
  "scout_account_id": "0U812",
  "application_name": "TestApp01"
}
```

**AI Analysis Questions (Inferred):**
- Are there semantic relationships between programs?
- Are there shared data structures that imply coupling?
- Are there business logic dependencies?

**Output:**
```
{account}/{app}/dependency_mapper_v2/jobs/{job_id}/artifacts/ai_dependency_analysis.json
```

**Sample Output Size:** 4.3 KB (relatively small - likely high-level insights)

#### 7. BuildDependencyGraph (Lambda)
**Lambda:** `DependencyMapperV2GraphBuilder`
**Timeout:** 120 seconds
**Memory:** 1024 MB

**Purpose:**
- Construct dependency graph from static + AI analysis
- Create nodes (programs) and edges (dependencies)
- Calculate fan-in and fan-out for each program

**Graph Structure:**

**Nodes:**
```json
{
  "id": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
  "type": "program",
  "fan_in": 2,
  "fan_out": 16,
  "lines_of_code": 0,
  "complexity_score": 0
}
```

**Edges:**
```json
{
  "from": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
  "to": "STDPROCESS",
  "type": "COPY",
  "line_number": 1
}
```

**Edge Types:**
- **CALL:** Program calls another program
- **COPY:** Program includes copybook
- **FILE_IO:** Program reads/writes file

**Output:**
```
{account}/{app}/dependency_mapper_v2/jobs/{job_id}/artifacts/dependency_graph.json
```

**Sample Output Size:** 65 KB (largest artifact)

#### 8. ParallelAnalysis (Parallel State)
**Type:** Parallel (2 branches run simultaneously)

##### Branch 1: CouplingCalculator
**Lambda:** `DependencyMapperV2CouplingCalculator`
**Timeout:** 90 seconds

**Purpose:**
- Calculate coupling metrics for each program
- Determine overall coupling statistics

**Metrics Calculated:**
- **Fan-In:** Number of programs that depend on this program
- **Fan-Out:** Number of programs this program depends on
- **Coupling Score:** Normalized coupling metric (0-1)
- **Coupling Classification:** HIGH, MEDIUM, LOW

**Output:**
```json
{
  "overall": {
    "total_programs": 48,
    "average_fan_in": 1.92,
    "average_fan_out": 1.92,
    "average_coupling": 0.022,
    "high_coupling_count": 0,
    "medium_coupling_count": 1,
    "low_coupling_count": 47
  },
  "by_program": {
    "CMCMCL00.CBL": {
      "fan_in": 0,
      "fan_out": 83,
      "coupling_score": 0.38,
      "classification": "MEDIUM"
    }
  }
}
```

##### Branch 2: RiskAssessor
**Lambda:** `DependencyMapperV2RiskAssessor`
**Timeout:** 90 seconds

**Purpose:**
- Assess risk based on dependencies and complexity
- Classify programs as HIGH, MEDIUM, LOW risk

**Risk Factors:**
- High fan-in (many dependents)
- High fan-out (many dependencies)
- Complexity score
- Lines of code

**Output:**
```json
{
  "risk_summary": {
    "high_risk_programs": 0,
    "medium_risk_programs": 3,
    "low_risk_programs": 17
  },
  "program_risks": {
    "CMCMCL00.CBL": {
      "risk_level": "MEDIUM",
      "factors": ["High fan-out (83)", "Complex logic"]
    }
  }
}
```

**Sample Output Size:** 1.2 KB (small - summary-focused)

#### 9. MicroserviceDetector (Lambda)
**Lambda:** `DependencyMapperV2MicroserviceDetector`
**Timeout:** 120 seconds
**Memory:** 1024 MB

**Purpose:**
- Suggest microservice boundaries based on coupling/cohesion analysis
- Group programs into services with high internal cohesion and low external coupling

**Algorithm (Inferred):**
1. Calculate cohesion between all program pairs
2. Apply clustering algorithm (likely community detection)
3. Evaluate service boundaries by:
   - Internal coupling (within service)
   - External coupling (between services)
   - Cohesion score
4. Generate justification for each service boundary

**Output:**
```json
{
  "suggested_services": [
    {
      "service_name": "Service16",
      "programs": [
        "UTCSNT10",
        "IMCSIR00",
        "CMCSRP73",
        "XACSCT00",
        "IBMi-Cobol/Cobol/CMCMCL00.CBL",
        "XACSCV00"
      ],
      "program_count": 6,
      "internal_coupling": 0.125,
      "external_coupling": 0.875,
      "cohesion_score": 0.833,
      "justification": "High internal cohesion (12.5%), low external coupling"
    }
  ],
  "shared_components": [
    {
      "component": "STDPROCESS",
      "used_by_services": ["Service1", "Service2", "Service16"],
      "recommendation": "Extract to shared library"
    }
  ],
  "summary": {
    "total_services": 20,
    "average_service_size": 2.4,
    "shared_components_count": 15
  }
}
```

**Sample Output Size:** 15.6 KB

**Key Insight:** Microservice detection provides actionable recommendations for decomposing monolithic COBOL into microservices.

#### 10. ImpactAnalyzer (Lambda)
**Lambda:** `DependencyMapperV2ImpactAnalyzer`
**Timeout:** 90 seconds

**Purpose:**
- Calculate impact/blast radius for each program
- Determine which programs would be affected if a program changes

**Algorithm:**
1. For each program, traverse dependency graph
2. Calculate transitive dependencies (direct + indirect)
3. Score impact based on:
   - Number of direct dependents
   - Number of transitive dependents
   - Criticality of dependents

**Output:**
```json
{
  "program_impact_map": {
    "CMCMCL00.CBL": {
      "direct_dependents": 0,
      "transitive_dependents": 0,
      "impact_score": 83,
      "blast_radius": "MEDIUM",
      "critical_dependents": []
    }
  },
  "sorted_by_impact": [
    {
      "program": "CMCMCL00.CBL",
      "impact_score": 83
    }
  ],
  "summary": {
    "high_impact_programs": 5,
    "medium_impact_programs": 8,
    "low_impact_programs": 7
  }
}
```

**Sample Output Size:** 51.8 KB (second largest artifact)

**Use Cases:**
- Change impact analysis: "If I modify program X, what else breaks?"
- Testing prioritization: Focus on high-impact programs
- Refactoring risk assessment

#### 11. UpdateStatusCompleted (S3 PutObject)
**Purpose:** Mark job as completed

**S3 Key:**
```
{account}/{app}/dependency_mapper_v2/jobs/{job_id}/status.json
```

**Status Body:**
```json
{
  "state": "completed",
  "started_at": "2025-11-06T14:35:38.739Z",
  "completed_at": "2025-11-06T14:36:07.363Z",
  "phase": "completed",
  "progress": 100,
  "message": "Dependency analysis completed successfully"
}
```

#### 12. Success (Succeed State)
**Purpose:** Workflow termination

---

## Lambda Functions

### Summary Table

| Lambda | Purpose | Timeout | Memory | Lines |
|--------|---------|---------|--------|-------|
| PrepareAnalysis | Create batches | 60s | 512 MB | ~200 |
| StaticParser | Parse dependencies | 120s | 1024 MB | 331 |
| MergeStatic | Combine batches | 60s | 512 MB | ~150 |
| AIAnalyzer | AI analysis | 300s | 1024 MB | ~300 |
| GraphBuilder | Build graph | 120s | 1024 MB | 299 |
| CouplingCalculator | Coupling metrics | 90s | 512 MB | ~250 |
| RiskAssessor | Risk assessment | 90s | 512 MB | ~200 |
| MicroserviceDetector | Service boundaries | 120s | 1024 MB | ~350 |
| ImpactAnalyzer | Impact analysis | 90s | 512 MB | ~250 |

**Total Lambda Code:** ~2300 lines (estimated)

### Detailed Lambda Descriptions

#### 1. DependencyMapperV2PrepareAnalysis

**Handler:** `prepare_analysis_v2_handler.lambda_handler`
**Runtime:** Python 3.11
**Timeout:** 60 seconds
**Memory:** 512 MB

**Responsibilities:**
1. Read source files from S3 (content-addressed storage)
2. Filter for COBOL files (.cbl, .CBL, .cob, .COB)
3. Split files into batches (default: 5 files per batch)
4. Create batch metadata with file paths
5. Write batch info to S3 temp folder

**Key Logic:**
```python
def lambda_handler(event, context):
    source_hash = event['source_hash']
    files = list_cobol_files_from_s3(source_hash)

    batches = []
    batch_size = 5
    for i in range(0, len(files), batch_size):
        batch = {
            'batch_id': i // batch_size,
            'files': files[i:i+batch_size]
        }
        batches.append(batch)

    return {
        'total_files': len(files),
        'total_batches': len(batches),
        'batches': batches
    }
```

**Output Example:**
```json
{
  "total_files": 20,
  "total_batches": 4,
  "batches": [
    {
      "batch_id": 0,
      "files": [
        "IBMi-Cobol/Cobol/STATUSCODE.CBL",
        "IBMi-Cobol/Cobol/CMCSCL50.CBL",
        "IBMi-Cobol/Cobol/UTCSDC00L.CBL",
        "IBMi-Cobol/Cobol/CMCSRP00C.CBL",
        "IBMi-Cobol/Cobol/ADCPSH21L.CBL"
      ]
    }
  ]
}
```

---

#### 2. DependencyMapperV2StaticParser

**Handler:** `static_parser_v2_handler.lambda_handler`
**Runtime:** Python 3.11
**Timeout:** 120 seconds
**Memory:** 1024 MB
**Code Size:** 331 lines

**Responsibilities:**
1. Parse COBOL source code for dependencies
2. Detect CALL statements (program-to-program calls)
3. Detect COPY statements (copybook inclusions)
4. Detect FILE I/O operations (READ, WRITE, REWRITE, DELETE)
5. Detect DATABASE operations (if any)
6. Write batch results to S3 temp folder

**Parsing Techniques:**
- **Regex-based:** Pattern matching for CALL, COPY, FILE verbs
- **Line-by-line:** Process COBOL source line by line
- **Comment handling:** Skip comment lines (*, / in column 7)

**CALL Detection:**
```regex
CALL\s+['"]([\w-]+)['"]
CALL\s+([\w-]+)
```

**COPY Detection:**
```regex
COPY\s+([\w-]+)
```

**FILE I/O Detection:**
```regex
READ\s+([\w-]+)
WRITE\s+([\w-]+)
REWRITE\s+([\w-]+)
DELETE\s+([\w-]+)
```

**Output (per file):**
```json
{
  "program": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
  "calls": [],
  "copies": [
    {"copybook": "STDPROCESS", "line": 1},
    {"copybook": "DDS-CMFHCL00", "line": 89}
  ],
  "file_io": [
    {"operation": "READ", "file": "CMLHCL00-FILE", "line": 489}
  ],
  "database": []
}
```

**Sample Results (from batch 0):**
- **STATUSCODE.CBL:** 4 FILE I/O operations (READ, WRITE, DELETE)
- **CMCSCL50.CBL:** 16 COPY statements, 7 FILE I/O operations
- **CMCSRP00C.CBL:** 1 CALL to CMCSRP00
- **DICPCC00.CBL:** 6 CALL statements, 13 COPY statements, 6 FILE operations

---

#### 3. DependencyMapperV2MergeStatic

**Handler:** `merge_static_v2_handler.lambda_handler`
**Runtime:** Python 3.11
**Timeout:** 60 seconds
**Memory:** 512 MB

**Responsibilities:**
1. Read all batch_*.json files from S3 temp folder
2. Combine into single static_analysis.json
3. De-duplicate dependencies (if same dependency found in multiple batches)
4. Add metadata (generated_at, source_job_id)

**Key Logic:**
```python
def lambda_handler(event, context):
    job_id = event['job_id']
    total_batches = event['total_batches']

    all_dependencies = []
    for batch_id in range(total_batches):
        batch_data = read_batch_from_s3(job_id, batch_id)
        all_dependencies.extend(batch_data['dependencies_found'])

    merged = {
        'source_job_id': job_id,
        'generated_at': datetime.utcnow().isoformat(),
        'programs': all_dependencies
    }

    write_to_s3(job_id, 'artifacts/static_analysis.json', merged)

    return {
        'merged_file': f's3://.../artifacts/static_analysis.json',
        'total_programs': len(all_dependencies)
    }
```

**Output File:**
```
{account}/{app}/dependency_mapper_v2/jobs/{job_id}/artifacts/static_analysis.json
```

**Sample Size:** 42.3 KB (20 programs analyzed)

---

#### 4. DependencyMapperV2AIAnalyzer

**Handler:** `ai_analyzer_v2_handler.lambda_handler`
**Runtime:** Python 3.11
**Timeout:** 300 seconds (5 minutes)
**Memory:** 1024 MB

**Responsibilities:**
1. Read static_analysis.json
2. Send to AWS Bedrock for AI analysis
3. Ask Claude to identify:
   - Semantic dependencies (business logic relationships)
   - Hidden dependencies not found by static parser
   - Shared data structures that imply coupling
   - Validation of static parser results
4. Write AI insights to ai_dependency_analysis.json

**Bedrock Configuration:**
- **Model:** Claude 3.5 Sonnet
- **Region:** us-east-1
- **Max Tokens:** ~8000-10000 (estimated)
- **Temperature:** 0.3 (low - prioritize accuracy)

**Prompt Template (Inferred):**
```
You are analyzing COBOL program dependencies. Here is the static analysis:

[static_analysis.json content]

Questions:
1. Are there semantic relationships between programs not captured by static analysis?
2. Do any programs share data structures that imply coupling?
3. Are there business logic dependencies?
4. Are the static parser results accurate?

Provide your analysis in JSON format.
```

**Output:**
```json
{
  "semantic_dependencies": [
    {
      "from": "CMCMCL00.CBL",
      "to": "CMCSCL50.CBL",
      "relationship": "Shared customer data structure",
      "confidence": 0.85
    }
  ],
  "hidden_dependencies": [],
  "validation": {
    "static_parser_accuracy": "HIGH",
    "issues_found": 0
  }
}
```

**Sample Output Size:** 4.3 KB (small - likely high-level insights only)

**Note:** Output is relatively small (4.3 KB), suggesting AI analysis is lightweight, not comprehensive semantic analysis.

---

#### 5. DependencyMapperV2GraphBuilder

**Handler:** `graph_builder_v2_handler.lambda_handler`
**Runtime:** Python 3.11
**Timeout:** 120 seconds
**Memory:** 1024 MB
**Code Size:** 299 lines

**Responsibilities:**
1. Read static_analysis.json and ai_dependency_analysis.json
2. Build graph data structure with nodes and edges
3. Calculate fan-in and fan-out for each node
4. Calculate complexity scores (if available)
5. Write dependency_graph.json

**Graph Construction:**

**Nodes = Programs:**
```python
nodes = {}
for program in static_analysis['programs']:
    nodes[program['program']] = {
        'id': program['program'],
        'type': 'program',
        'fan_in': 0,  # calculated later
        'fan_out': 0,  # calculated later
        'lines_of_code': 0,  # from source or analysis
        'complexity_score': 0
    }
```

**Edges = Dependencies:**
```python
edges = []
for program in static_analysis['programs']:
    # Add CALL edges
    for call in program['calls']:
        edges.append({
            'from': program['program'],
            'to': call['target'],
            'type': 'CALL',
            'line_number': call['line']
        })

    # Add COPY edges
    for copy in program['copies']:
        edges.append({
            'from': program['program'],
            'to': copy['copybook'],
            'type': 'COPY',
            'line_number': copy['line']
        })

    # Add FILE_IO edges (optional)
    for file_op in program['file_io']:
        edges.append({
            'from': program['program'],
            'to': file_op['file'],
            'type': 'FILE_IO',
            'line_number': file_op['line']
        })
```

**Fan-In/Fan-Out Calculation:**
```python
for edge in edges:
    # Increment fan-out for source node
    nodes[edge['from']]['fan_out'] += 1

    # Increment fan-in for target node (if exists in nodes)
    if edge['to'] in nodes:
        nodes[edge['to']]['fan_in'] += 1
```

**Output:**
```json
{
  "source_job_id": "dmv2_job_...",
  "generated_at": "2025-11-06T14:36:04.123Z",
  "summary": {
    "total_nodes": 48,
    "total_edges": 234
  },
  "nodes": [
    {
      "id": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
      "type": "program",
      "fan_in": 2,
      "fan_out": 16,
      "lines_of_code": 0,
      "complexity_score": 0
    }
  ],
  "edges": [
    {
      "from": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
      "to": "STDPROCESS",
      "type": "COPY",
      "line_number": 1
    }
  ]
}
```

**Sample Output Size:** 65 KB (largest artifact)

**Use Cases:**
- Visualize dependency graph in UI
- Calculate transitive dependencies
- Identify cyclic dependencies
- Find orphaned programs (fan-in = 0, fan-out = 0)

---

#### 6. DependencyMapperV2CouplingCalculator

**Handler:** `coupling_calculator_v2_handler.lambda_handler`
**Runtime:** Python 3.11
**Timeout:** 90 seconds
**Memory:** 512 MB

**Responsibilities:**
1. Read dependency_graph.json
2. Calculate coupling metrics for each program
3. Calculate overall coupling statistics
4. Classify programs by coupling level (HIGH, MEDIUM, LOW)

**Coupling Metric Formula:**
```
coupling_score = (fan_in + fan_out) / total_programs
```

**Classification Thresholds (Inferred):**
- **HIGH:** coupling_score > 0.15 (15%)
- **MEDIUM:** 0.05 < coupling_score ≤ 0.15
- **LOW:** coupling_score ≤ 0.05

**Calculation Logic:**
```python
def calculate_coupling(graph):
    total_programs = len(graph['nodes'])

    coupling_by_program = {}
    for node in graph['nodes']:
        coupling_score = (node['fan_in'] + node['fan_out']) / total_programs

        if coupling_score > 0.15:
            classification = 'HIGH'
        elif coupling_score > 0.05:
            classification = 'MEDIUM'
        else:
            classification = 'LOW'

        coupling_by_program[node['id']] = {
            'fan_in': node['fan_in'],
            'fan_out': node['fan_out'],
            'coupling_score': coupling_score,
            'classification': classification
        }

    # Calculate overall stats
    avg_fan_in = sum(n['fan_in'] for n in graph['nodes']) / total_programs
    avg_fan_out = sum(n['fan_out'] for n in graph['nodes']) / total_programs
    avg_coupling = sum(c['coupling_score'] for c in coupling_by_program.values()) / total_programs

    return {
        'overall': {
            'total_programs': total_programs,
            'average_fan_in': avg_fan_in,
            'average_fan_out': avg_fan_out,
            'average_coupling': avg_coupling,
            'high_coupling_count': count_high,
            'medium_coupling_count': count_medium,
            'low_coupling_count': count_low
        },
        'by_program': coupling_by_program
    }
```

**Output:**
```json
{
  "source_job_id": "dmv2_job_...",
  "generated_at": "2025-11-06T14:36:05.123Z",
  "overall": {
    "total_programs": 48,
    "average_fan_in": 1.92,
    "average_fan_out": 1.92,
    "average_coupling": 0.022,
    "high_coupling_count": 0,
    "medium_coupling_count": 1,
    "low_coupling_count": 47
  },
  "by_program": {
    "CMCMCL00.CBL": {
      "fan_in": 0,
      "fan_out": 83,
      "coupling_score": 0.38,
      "classification": "MEDIUM"
    }
  }
}
```

**Sample Results (20 programs):**
- **Average coupling:** 2.2% (very low - well-architected codebase)
- **High coupling:** 0 programs
- **Medium coupling:** 1 program (CMCMCL00.CBL with 83 fan-out)
- **Low coupling:** 47 programs

**Insight:** TestApp01 has very low coupling - good for microservice decomposition!

---

#### 7. DependencyMapperV2RiskAssessor

**Handler:** `risk_assessor_v2_handler.lambda_handler`
**Runtime:** Python 3.11
**Timeout:** 90 seconds
**Memory:** 512 MB

**Responsibilities:**
1. Read dependency_graph.json and coupling_metrics.json
2. Assess risk for each program based on:
   - High fan-in (many dependents - breaking changes impact many programs)
   - High fan-out (many dependencies - fragile, easy to break)
   - High complexity score
   - Large LOC count
3. Classify programs as HIGH, MEDIUM, LOW risk

**Risk Scoring Formula (Inferred):**
```
risk_score = (fan_in * 2) + (fan_out * 1) + (complexity_score * 3)
```

**Weights:**
- Fan-in weighted 2x (breaking changes are costly)
- Fan-out weighted 1x (fragility)
- Complexity weighted 3x (hard to maintain)

**Classification Thresholds:**
- **HIGH:** risk_score > 50
- **MEDIUM:** 20 < risk_score ≤ 50
- **LOW:** risk_score ≤ 20

**Output:**
```json
{
  "source_job_id": "dmv2_job_...",
  "generated_at": "2025-11-06T14:36:05.456Z",
  "risk_summary": {
    "high_risk_programs": 0,
    "medium_risk_programs": 3,
    "low_risk_programs": 17
  },
  "program_risks": {
    "CMCMCL00.CBL": {
      "risk_level": "MEDIUM",
      "risk_score": 35,
      "factors": [
        "High fan-out (83 dependencies)",
        "Complex business logic"
      ],
      "recommendations": [
        "Break into smaller modules",
        "Reduce dependencies"
      ]
    }
  }
}
```

**Sample Output Size:** 1.2 KB (small - summary-focused)

---

#### 8. DependencyMapperV2MicroserviceDetector

**Handler:** `microservice_detector_v2_handler.lambda_handler`
**Runtime:** Python 3.11
**Timeout:** 120 seconds
**Memory:** 1024 MB

**Responsibilities:**
1. Read dependency_graph.json and coupling_metrics.json
2. Apply clustering algorithm to group programs
3. Evaluate service boundaries by cohesion/coupling
4. Generate justification for each service
5. Identify shared components (copybooks used by multiple services)

**Algorithm (Inferred - likely Community Detection):**
1. **Calculate Cohesion Matrix:**
   - For each pair of programs, calculate shared dependencies
   - Cohesion = (shared_dependencies / total_dependencies)

2. **Apply Clustering:**
   - Use community detection algorithm (Louvain, Girvan-Newman, or similar)
   - Group programs with high internal cohesion

3. **Evaluate Service Quality:**
   - Internal coupling: Sum of edges within service / total internal pairs
   - External coupling: Sum of edges between services / total external pairs
   - Cohesion score: Internal coupling / (Internal + External coupling)

4. **Generate Services:**
   - Only keep services with:
     - Cohesion score > 0.7 (70%)
     - Program count > 1 (no single-program services)

**Output:**
```json
{
  "source_job_id": "dmv2_job_...",
  "generated_at": "2025-11-06T14:36:06.123Z",
  "suggested_services": [
    {
      "service_name": "Service16",
      "programs": [
        "UTCSNT10",
        "IMCSIR00",
        "CMCSRP73",
        "XACSCT00",
        "IBMi-Cobol/Cobol/CMCMCL00.CBL",
        "XACSCV00"
      ],
      "program_count": 6,
      "internal_coupling": 0.125,
      "external_coupling": 0.875,
      "cohesion_score": 0.833,
      "justification": "High internal cohesion (12.5%), low external coupling"
    }
  ],
  "shared_components": [
    {
      "component": "STDPROCESS",
      "type": "COPYBOOK",
      "used_by_services": ["Service1", "Service2", "Service16"],
      "usage_count": 15,
      "recommendation": "Extract to shared library"
    }
  ],
  "summary": {
    "total_services": 20,
    "average_service_size": 2.4,
    "shared_components_count": 15,
    "recommendation": "Consider consolidating small services for deployment efficiency"
  }
}
```

**Sample Output Size:** 15.6 KB

**Key Insights:**
- 20 suggested microservices for 48 programs (~2-3 programs per service)
- 15 shared components (copybooks) - should be extracted to common libraries
- High cohesion scores (0.8+) - good service boundaries

**Use Cases:**
- Architecture planning: Understand how to decompose monolith
- Refactoring roadmap: Prioritize which services to extract first
- Shared library planning: Identify common components

---

#### 9. DependencyMapperV2ImpactAnalyzer

**Handler:** `impact_analyzer_v2_handler.lambda_handler`
**Runtime:** Python 3.11
**Timeout:** 90 seconds
**Memory:** 512 MB

**Responsibilities:**
1. Read dependency_graph.json
2. For each program, calculate transitive dependencies (blast radius)
3. Score impact based on number of affected programs
4. Classify programs by impact level (HIGH, MEDIUM, LOW)

**Algorithm:**
1. **Calculate Direct Dependents:**
   - Count programs that directly call/copy this program
   - direct_dependents = fan_in

2. **Calculate Transitive Dependents:**
   - Use DFS/BFS to traverse graph in reverse
   - Find all programs that transitively depend on this program

3. **Calculate Impact Score:**
   ```
   impact_score = direct_dependents * 10 + transitive_dependents * 5
   ```

4. **Classification:**
   - **HIGH:** impact_score > 100 (change affects 10+ programs directly)
   - **MEDIUM:** 20 < impact_score ≤ 100
   - **LOW:** impact_score ≤ 20

**Output:**
```json
{
  "source_job_id": "dmv2_job_...",
  "generated_at": "2025-11-06T14:36:08.123Z",
  "program_impact_map": {
    "CMCMCL00.CBL": {
      "direct_dependents": 0,
      "transitive_dependents": 0,
      "impact_score": 83,
      "blast_radius": "MEDIUM",
      "critical_dependents": []
    },
    "STDPROCESS": {
      "direct_dependents": 15,
      "transitive_dependents": 45,
      "impact_score": 375,
      "blast_radius": "HIGH",
      "critical_dependents": [
        "CMCMCL00.CBL",
        "CMCSCL50.CBL",
        "ADCPSH21.CBL"
      ]
    }
  },
  "sorted_by_impact": [
    {"program": "STDPROCESS", "impact_score": 375},
    {"program": "CMCMCL00.CBL", "impact_score": 83}
  ],
  "summary": {
    "high_impact_programs": 5,
    "medium_impact_programs": 8,
    "low_impact_programs": 7
  }
}
```

**Sample Output Size:** 51.8 KB (second largest artifact)

**Use Cases:**
- **Change Impact Analysis:** "If I modify STDPROCESS, what breaks?"
  - Answer: 15 programs directly, 45 programs transitively (60 total)
- **Testing Prioritization:** Focus on high-impact programs first
- **Refactoring Risk Assessment:** Identify risky changes before starting

**Key Insight:** STDPROCESS copybook has high impact (375 score) - changes require extensive testing!

---

## Data Structures

### 1. Job Info (job_info.json)

```json
{
  "job_id": "dmv2_job_0U812_TestApp01_1762439738_3581cb90",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74",
  "created_at": "2025-11-06T14:35:38.535246+00:00",
  "workflow_execution_arn": "arn:aws:states:us-east-1:376129851858:execution:DependencyMapperWorkflowV2:execution-dmv2_job_0U812_TestApp01_1762439738_3581cb90",
  "status": "pending"
}
```

### 2. Job Status (status.json)

```json
{
  "state": "completed",
  "phase": "completed",
  "progress": 100,
  "message": "Dependency analysis completed successfully",
  "completed_at": "2025-11-06T14:36:07.363Z",
  "started_at": "2025-11-06T14:35:38.739Z"
}
```

**States:**
- `pending` - Job created
- `running` - Workflow executing
- `completed` - Workflow finished successfully
- `failed` - Workflow failed

### 3. Static Analysis (static_analysis.json)

```json
{
  "source_job_id": "dmv2_job_0U812_TestApp01_1762439738_3581cb90",
  "generated_at": "2025-11-06T14:35:45.123Z",
  "programs": [
    {
      "program": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
      "calls": [],
      "copies": [
        {"copybook": "STDPROCESS", "line": 1},
        {"copybook": "DDS-CMFHCL00", "line": 89}
      ],
      "file_io": [
        {"operation": "READ", "file": "CMLHCL00-FILE", "line": 489}
      ],
      "database": []
    }
  ]
}
```

**Size:** 42.3 KB (20 programs)

### 4. AI Dependency Analysis (ai_dependency_analysis.json)

```json
{
  "source_job_id": "dmv2_job_0U812_TestApp01_1762439738_3581cb90",
  "generated_at": "2025-11-06T14:36:02.123Z",
  "semantic_dependencies": [
    {
      "from": "CMCMCL00.CBL",
      "to": "CMCSCL50.CBL",
      "relationship": "Shared customer data structure",
      "confidence": 0.85
    }
  ],
  "hidden_dependencies": [],
  "validation": {
    "static_parser_accuracy": "HIGH",
    "issues_found": 0
  }
}
```

**Size:** 4.3 KB (small - lightweight insights)

### 5. Dependency Graph (dependency_graph.json)

```json
{
  "source_job_id": "dmv2_job_0U812_TestApp01_1762439738_3581cb90",
  "generated_at": "2025-11-06T14:36:04.123Z",
  "summary": {
    "total_nodes": 48,
    "total_edges": 234
  },
  "nodes": [
    {
      "id": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
      "type": "program",
      "fan_in": 2,
      "fan_out": 16,
      "lines_of_code": 0,
      "complexity_score": 0
    }
  ],
  "edges": [
    {
      "from": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
      "to": "STDPROCESS",
      "type": "COPY",
      "line_number": 1
    }
  ]
}
```

**Size:** 65 KB (largest artifact - complete graph)

**Node Properties:**
- `id`: Program file path
- `type`: Always "program"
- `fan_in`: Number of incoming dependencies
- `fan_out`: Number of outgoing dependencies
- `lines_of_code`: LOC count (often 0 - not calculated)
- `complexity_score`: Complexity metric (often 0 - not calculated)

**Edge Types:**
- `CALL`: Program-to-program call
- `COPY`: Copybook inclusion
- `FILE_IO`: File operation (optional)

### 6. Coupling Metrics (coupling_metrics.json)

```json
{
  "source_job_id": "dmv2_job_0U812_TestApp01_1762439738_3581cb90",
  "generated_at": "2025-11-06T14:36:05.123Z",
  "overall": {
    "total_programs": 48,
    "average_fan_in": 1.92,
    "average_fan_out": 1.92,
    "average_coupling": 0.022,
    "high_coupling_count": 0,
    "medium_coupling_count": 1,
    "low_coupling_count": 47
  },
  "by_program": {
    "CMCMCL00.CBL": {
      "fan_in": 0,
      "fan_out": 83,
      "coupling_score": 0.38,
      "classification": "MEDIUM"
    }
  }
}
```

**Size:** 9.5 KB

**Coupling Classifications:**
- **HIGH:** coupling_score > 0.15 (15%)
- **MEDIUM:** 0.05 < coupling_score ≤ 0.15
- **LOW:** coupling_score ≤ 0.05

### 7. Risk Assessment (risk_assessment.json)

```json
{
  "source_job_id": "dmv2_job_0U812_TestApp01_1762439738_3581cb90",
  "generated_at": "2025-11-06T14:36:05.456Z",
  "risk_summary": {
    "high_risk_programs": 0,
    "medium_risk_programs": 3,
    "low_risk_programs": 17
  },
  "program_risks": {
    "CMCMCL00.CBL": {
      "risk_level": "MEDIUM",
      "risk_score": 35,
      "factors": [
        "High fan-out (83 dependencies)",
        "Complex business logic"
      ],
      "recommendations": [
        "Break into smaller modules",
        "Reduce dependencies"
      ]
    }
  }
}
```

**Size:** 1.2 KB (small - summary-focused)

### 8. Microservice Boundaries (microservice_boundaries.json)

```json
{
  "source_job_id": "dmv2_job_0U812_TestApp01_1762439738_3581cb90",
  "generated_at": "2025-11-06T14:36:06.123Z",
  "suggested_services": [
    {
      "service_name": "Service16",
      "programs": [
        "UTCSNT10",
        "IMCSIR00",
        "CMCSRP73",
        "XACSCT00",
        "IBMi-Cobol/Cobol/CMCMCL00.CBL",
        "XACSCV00"
      ],
      "program_count": 6,
      "internal_coupling": 0.125,
      "external_coupling": 0.875,
      "cohesion_score": 0.833,
      "justification": "High internal cohesion (12.5%), low external coupling"
    }
  ],
  "shared_components": [
    {
      "component": "STDPROCESS",
      "type": "COPYBOOK",
      "used_by_services": ["Service1", "Service2", "Service16"],
      "usage_count": 15,
      "recommendation": "Extract to shared library"
    }
  ],
  "summary": {
    "total_services": 20,
    "average_service_size": 2.4,
    "shared_components_count": 15,
    "recommendation": "Consider consolidating small services for deployment efficiency"
  }
}
```

**Size:** 15.6 KB

**Service Quality Metrics:**
- **internal_coupling:** Coupling within service (lower is better)
- **external_coupling:** Coupling between services (higher is better)
- **cohesion_score:** internal / (internal + external) - higher is better (0-1)
- **Target cohesion:** > 0.7 (70%)

### 9. Impact Analysis (impact_analysis.json)

```json
{
  "source_job_id": "dmv2_job_0U812_TestApp01_1762439738_3581cb90",
  "generated_at": "2025-11-06T14:36:08.123Z",
  "program_impact_map": {
    "CMCMCL00.CBL": {
      "direct_dependents": 0,
      "transitive_dependents": 0,
      "impact_score": 83,
      "blast_radius": "MEDIUM",
      "critical_dependents": []
    }
  },
  "sorted_by_impact": [
    {"program": "STDPROCESS", "impact_score": 375},
    {"program": "CMCMCL00.CBL", "impact_score": 83}
  ],
  "summary": {
    "high_impact_programs": 5,
    "medium_impact_programs": 8,
    "low_impact_programs": 7
  }
}
```

**Size:** 51.8 KB (second largest)

**Impact Score Formula:**
```
impact_score = (direct_dependents * 10) + (transitive_dependents * 5)
```

**Blast Radius Classifications:**
- **HIGH:** impact_score > 100
- **MEDIUM:** 20 < impact_score ≤ 100
- **LOW:** impact_score ≤ 20

---

## S3 Storage Layout

### Bucket Structure

```
code-transformation-v2/
└── {account_id}/                           # e.g., "0U812"
    └── {application_name}/                 # e.g., "TestApp01"
        └── dependency_mapper_v2/
            └── jobs/
                └── {job_id}/               # e.g., "dmv2_job_0U812_TestApp01_1762439738_3581cb90"
                    ├── job_info.json
                    ├── status.json
                    ├── artifacts/
                    │   ├── static_analysis.json        (42 KB)
                    │   ├── ai_dependency_analysis.json (4 KB)
                    │   ├── dependency_graph.json       (65 KB - largest)
                    │   ├── coupling_metrics.json       (9 KB)
                    │   ├── risk_assessment.json        (1 KB)
                    │   ├── microservice_boundaries.json(16 KB)
                    │   └── impact_analysis.json        (52 KB)
                    └── temp/
                        └── batch_analysis/
                            ├── batch_0.json
                            ├── batch_1.json
                            ├── batch_2.json
                            └── batch_3.json
```

### Job ID Pattern

```
dmv2_job_{account}_{app}_{timestamp}_{uuid}
```

**Example:**
```
dmv2_job_0U812_TestApp01_1762439738_3581cb90
```

**Components:**
- `dmv2_` - Dependency Mapper V2 prefix
- `job_` - Job identifier
- `0U812` - Scout account ID
- `TestApp01` - Application name
- `1762439738` - Unix timestamp
- `3581cb90` - Short UUID (first 8 chars)

### Artifact Descriptions

| Artifact | Size | Purpose |
|----------|------|---------|
| static_analysis.json | 42 KB | CALL, COPY, FILE I/O dependencies |
| ai_dependency_analysis.json | 4 KB | AI-generated insights |
| dependency_graph.json | 65 KB | Complete graph (nodes + edges) |
| coupling_metrics.json | 9 KB | Coupling scores per program |
| risk_assessment.json | 1 KB | Risk classification |
| microservice_boundaries.json | 16 KB | Suggested service boundaries |
| impact_analysis.json | 52 KB | Blast radius per program |

**Total Artifacts:** ~189 KB (for 20 programs)

---

## Integration Points

### Upstream Dependencies

**Required Inputs:**
1. **Source Files** must exist in S3:
   - Location: `s3://code-transformation-v2/sources/{source_hash}/`
   - Content-addressed storage (same hash = same files)
2. **Ingest Flow** must have run first
3. **Job ID** must be generated by caller

**Likely Upstream Flow:**
- Code Analysis V2/V3 (after analysis, trigger dependency mapping)
- Manual trigger via Step Functions console
- Scheduled execution for monitoring

### Downstream Consumers

**Who Consumes Dependency Mapper V2 Outputs?**

**Potential Consumers:**
1. **Architecture Recommender V2**
   - Uses `microservice_boundaries.json` for architecture recommendations
   - Uses `coupling_metrics.json` for decomposition strategy

2. **Customer UI / Dashboard**
   - Visualizes `dependency_graph.json` (graph visualization)
   - Shows `impact_analysis.json` (change impact reports)
   - Displays `microservice_boundaries.json` (service boundaries)

3. **JavaGen V3 (Future)**
   - Could use `microservice_boundaries.json` to generate separate services
   - Could use `shared_components` to create common libraries

4. **Refactoring Workflows**
   - Uses `coupling_metrics.json` to prioritize refactoring
   - Uses `risk_assessment.json` to assess refactoring risk

**Question:** No clear downstream flow found yet. Need to investigate integration with other V2 flows.

---

## Current Implementation

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Runtime** | Python | 3.11 |
| **Orchestration** | AWS Step Functions | Standard workflows |
| **Compute** | AWS Lambda | ZIP-based (not Docker) |
| **Storage** | Amazon S3 | Standard storage class |
| **AI/ML** | AWS Bedrock | Claude 3.5 Sonnet |
| **IAM Role** | BedrockAgentRole-CodeRefactor | (shared with Code Refactor V2) |

### Lambda Configurations

| Lambda | Timeout | Memory | Concurrency |
|--------|---------|--------|-------------|
| PrepareAnalysis | 60s | 512 MB | Default |
| StaticParser | 120s | 1024 MB | 40 (via Map) |
| MergeStatic | 60s | 512 MB | Default |
| AIAnalyzer | 300s | 1024 MB | Default |
| GraphBuilder | 120s | 1024 MB | Default |
| CouplingCalculator | 90s | 512 MB | Default |
| RiskAssessor | 90s | 512 MB | Default |
| MicroserviceDetector | 120s | 1024 MB | Default |
| ImpactAnalyzer | 90s | 512 MB | Default |

### IAM Permissions

**Role:** `BedrockAgentRole-CodeRefactor` (shared with Code Refactor V2)

**Required Permissions:**
- `s3:GetObject` - Read source files and analysis results
- `s3:PutObject` - Write artifacts and status
- `s3:ListBucket` - List source files
- `bedrock:InvokeModel` - Call Claude 3.5 Sonnet
- `logs:CreateLogGroup` - CloudWatch Logs
- `logs:CreateLogStream` - CloudWatch Logs
- `logs:PutLogEvents` - CloudWatch Logs

---

## Sample Execution Analysis

### Execution Details

- **Job ID:** `dmv2_job_0U812_TestApp01_1762439738_3581cb90`
- **Account:** 0U812
- **Application:** TestApp01
- **Source Hash:** `9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74`
- **Files Analyzed:** 20 COBOL programs
- **Start Time:** 2025-11-06 08:35:38
- **End Time:** 2025-11-06 08:36:07
- **Duration:** 29 seconds
- **Status:** SUCCEEDED

### Performance Metrics

| Phase | Duration | Component |
|-------|----------|-----------|
| Prepare | ~2 seconds | PrepareAnalysis Lambda |
| Static Parsing | ~3 seconds | 4 batches in parallel (StaticParser) |
| Merge Static | ~1 second | MergeStatic Lambda |
| AI Analysis | ~16 seconds | AIAnalyzer Lambda |
| Graph Build | ~1 second | GraphBuilder Lambda |
| Parallel Analysis | ~2 seconds | CouplingCalculator + RiskAssessor |
| Microservice Detection | ~2 seconds | MicroserviceDetector Lambda |
| Impact Analysis | ~2 seconds | ImpactAnalyzer Lambda |

**Total:** 29 seconds

**Performance Notes:**
- **Fastest:** Merge (1s), Graph (1s)
- **Slowest:** AI Analysis (16s) - 55% of total time
- **Parallelism:** Static parsing benefits from MaxConcurrency: 40
- **Bottleneck:** AI Analysis (Bedrock invocation)

### Batch Processing Results

**Batch 0 (5 files):**
- STATUSCODE.CBL: 4 FILE I/O operations
- CMCSCL50.CBL: 16 COPY statements, 7 FILE I/O
- UTCSDC00L.CBL: No dependencies
- CMCSRP00C.CBL: 1 CALL
- ADCPSH21L.CBL: No dependencies

**Batch 3 (5 files - largest output):**
- CMCMCL00.CBL: 83 CALL statements, 140 COPY statements, 82 FILE I/O
  - **Largest program:** 12,500+ lines (estimated)
  - **Highest fan-out:** 83 dependencies
  - **Classification:** MEDIUM coupling

**Observation:** CMCMCL00.CBL is the central program with the most dependencies. Likely a mainline or controller program.

### Output Analysis

**Graph Statistics:**
- **Total Nodes:** 48 (20 programs + 28 copybooks)
- **Total Edges:** 234 dependencies
- **Average Fan-In:** 1.92
- **Average Fan-Out:** 1.92
- **Average Coupling:** 0.022 (2.2% - very low)

**Coupling Distribution:**
- **HIGH Coupling:** 0 programs
- **MEDIUM Coupling:** 1 program (CMCMCL00.CBL)
- **LOW Coupling:** 47 programs/copybooks

**Microservice Recommendations:**
- **Total Services:** 20 suggested services
- **Average Service Size:** 2.4 programs per service
- **Largest Service:** Service16 with 6 programs
- **Shared Components:** 15 copybooks (need common libraries)

**Impact Analysis:**
- **HIGH Impact:** 5 programs (STDPROCESS, etc.)
- **MEDIUM Impact:** 8 programs (including CMCMCL00.CBL)
- **LOW Impact:** 7 programs

**Key Findings:**
- **Well-Architected:** Average coupling of 2.2% is excellent
- **Good for Microservices:** Low coupling makes decomposition easier
- **Shared Library Needed:** 15 copybooks used across services
- **High-Impact Components:** STDPROCESS copybook has 375 impact score

---

## Known Limitations

### 1. No API Gateway Integration

**Issue:** No customer-facing API endpoint found.

**Impact:**
- Unclear how customers trigger Dependency Mapper V2
- May be internal-only tool
- No self-service workflow

**Workaround:** Direct Step Functions invocation or upstream flow integration

---

### 2. Lightweight AI Analysis

**Issue:** AI output is only 4.3 KB (small).

**Impact:**
- May not be providing deep semantic analysis
- Possible underutilization of Bedrock capabilities
- AI timeout is 5 minutes but execution takes 16 seconds (only 5% of budget)

**Questions:**
- Is AI analysis truly adding value?
- Should we expand AI analysis scope?

---

### 3. Missing LOC and Complexity Metrics

**Issue:** `lines_of_code` and `complexity_score` are often 0 in graph nodes.

**Impact:**
- Incomplete risk assessment
- Coupling metrics don't consider program size
- Impact analysis may be inaccurate

**Root Cause:** StaticParser doesn't calculate LOC or cyclomatic complexity

**Workaround:** Could integrate with Code Analysis V3 outputs

---

### 4. Static Parser Limitations

**Issue:** Regex-based parsing has known limitations.

**Limitations:**
- May miss dynamic CALL statements (CALL var-name)
- May miss conditional COPY statements
- No semantic understanding of business logic
- Cannot detect data-level coupling

**Example Missed Dependencies:**
```cobol
MOVE 'PROGRAM1' TO TARGET-PROGRAM.
CALL TARGET-PROGRAM.  ← Missed by regex parser
```

**Impact:** Dependency graph may be incomplete

---

### 5. No Cyclic Dependency Detection

**Issue:** No artifact shows cyclic dependencies.

**Impact:**
- Cannot identify circular dependencies (A → B → C → A)
- Missed opportunity for refactoring guidance

**Workaround:** Could add cycle detection to GraphBuilder

---

### 6. Small Service Sizes

**Issue:** Average service size is 2.4 programs (very small).

**Impact:**
- 20 microservices for 48 programs may be too granular
- Deployment overhead (20 services to manage)
- Inter-service communication overhead

**Recommendation:** Add service consolidation logic (merge services with < 3 programs)

---

### 7. No Database Dependency Analysis

**Issue:** `database` field is always empty in static_analysis.

**Impact:**
- Cannot identify which programs access which databases
- Missing critical coupling dimension
- Incomplete microservice boundaries (data coupling ignored)

**Root Cause:** StaticParser doesn't parse EXEC SQL statements

---

### 8. No Cross-Application Dependencies

**Issue:** Analysis is per-application only.

**Impact:**
- Cannot identify dependencies between applications
- Missed enterprise-level coupling analysis
- Incomplete impact analysis for shared components

**Workaround:** Run Dependency Mapper on all applications, then merge graphs

---

## V5 Improvement Opportunities

### 1. Add API Gateway Endpoint

**Improvement:** Create customer-facing API for Dependency Mapper V2

**Endpoint:**
```
POST /api/v5/dependency-analysis
```

**Benefits:**
- Self-service dependency analysis
- Integration with customer workflows
- Status polling via GET endpoint

**Effort:** LOW (1-2 days)

---

### 2. Enhance AI Analysis

**Improvement:** Expand AI analysis scope and depth

**Enhancements:**
- Detect semantic dependencies (business logic relationships)
- Find data-level coupling (shared data structures)
- Identify hidden dependencies (dynamic calls, conditional includes)
- Generate refactoring recommendations

**New Output:**
```json
{
  "semantic_dependencies": [...],
  "data_coupling": [
    {
      "shared_data": "CUSTOMER-RECORD",
      "programs": ["CMCMCL00.CBL", "CMCSCL50.CBL"],
      "recommendation": "Encapsulate in shared module"
    }
  ],
  "hidden_dependencies": [...],
  "refactoring_opportunities": [
    {
      "program": "CMCMCL00.CBL",
      "issue": "High fan-out (83 dependencies)",
      "recommendation": "Break into 3 smaller modules",
      "estimated_effort": "8 hours"
    }
  ]
}
```

**Benefits:**
- More valuable AI insights
- Actionable refactoring guidance
- Better microservice boundaries

**Effort:** MEDIUM (5-7 days)

---

### 3. Add LOC and Complexity Calculation

**Improvement:** Calculate lines of code and cyclomatic complexity in StaticParser

**Enhancements:**
- Count LOC (excluding comments and blank lines)
- Calculate cyclomatic complexity (IF, PERFORM, EVALUATE)
- Store in dependency_graph nodes
- Use in risk assessment and coupling calculation

**Benefits:**
- More accurate risk assessment
- Better coupling metrics (size-adjusted)
- Identify complex programs for refactoring

**Effort:** LOW (2-3 days)

---

### 4. Add Cyclic Dependency Detection

**Improvement:** Detect and report cyclic dependencies in GraphBuilder

**Algorithm:**
1. Run DFS on dependency graph
2. Detect back edges (cycles)
3. Extract all cycles
4. Report in new artifact: `cyclic_dependencies.json`

**Output:**
```json
{
  "cycles_found": 2,
  "cycles": [
    {
      "cycle_id": 1,
      "programs": ["A.CBL", "B.CBL", "C.CBL", "A.CBL"],
      "severity": "HIGH",
      "recommendation": "Break cycle by extracting common logic"
    }
  ]
}
```

**Benefits:**
- Identify circular dependencies (architectural smell)
- Guidance for breaking cycles
- Prevent infinite loops during refactoring

**Effort:** LOW (1-2 days)

---

### 5. Consolidate Small Services

**Improvement:** Add logic to MicroserviceDetector to merge small services

**Algorithm:**
1. Identify services with < 3 programs
2. Calculate coupling between small services
3. Merge services with high inter-service coupling
4. Target service size: 3-8 programs

**Benefits:**
- Reduce number of microservices (20 → ~10-12)
- Lower deployment overhead
- Easier to manage
- Still maintain good cohesion/coupling

**Effort:** LOW (2-3 days)

---

### 6. Add Database Dependency Parsing

**Improvement:** Parse EXEC SQL statements in StaticParser

**Detection:**
```cobol
EXEC SQL
    SELECT * FROM CUSTOMER
END-EXEC.
```

**Parse:**
- Table names (FROM clause)
- Operation type (SELECT, INSERT, UPDATE, DELETE)
- Line number

**Output:**
```json
{
  "database": [
    {
      "operation": "SELECT",
      "table": "CUSTOMER",
      "line": 450
    }
  ]
}
```

**Benefits:**
- Complete dependency picture (code + data)
- Better microservice boundaries (consider data coupling)
- Identify shared databases (need refactoring)

**Effort:** MEDIUM (3-4 days)

---

### 7. Cross-Application Dependency Analysis

**Improvement:** Analyze dependencies across applications

**Architecture:**
1. Run Dependency Mapper V2 on each application
2. New Lambda: `CrossAppDependencyAnalyzer`
3. Merge all dependency graphs
4. Identify cross-app dependencies
5. Generate enterprise-level impact analysis

**Output:**
```json
{
  "applications": ["TestApp01", "TestApp02", "TestApp03"],
  "cross_app_dependencies": [
    {
      "from": "TestApp01/CMCMCL00.CBL",
      "to": "TestApp02/SHAREDUTIL.CBL",
      "type": "CALL",
      "recommendation": "Extract to shared library"
    }
  ],
  "enterprise_impact": {
    "SHAREDUTIL.CBL": {
      "used_by_apps": 3,
      "impact_score": 500,
      "blast_radius": "ENTERPRISE-WIDE"
    }
  }
}
```

**Benefits:**
- Enterprise-level dependency visibility
- Identify shared components across apps
- Better impact analysis for shared code

**Effort:** MEDIUM (4-5 days)

---

### 8. Add Visualization API

**Improvement:** Create API to serve dependency graph for UI visualization

**Endpoints:**
```
GET /api/v5/dependency-analysis/{job_id}/graph
GET /api/v5/dependency-analysis/{job_id}/microservices
GET /api/v5/dependency-analysis/{job_id}/impact/{program}
```

**Response Formats:**
- **Graph:** D3.js-compatible JSON
- **Microservices:** Service boundaries with visual coordinates
- **Impact:** Highlighted sub-graph showing blast radius

**Benefits:**
- Customer UI can visualize dependencies
- Interactive exploration of dependency graph
- Better understanding of codebase structure

**Effort:** MEDIUM (5-7 days)

---

### 9. Integration with Architecture Recommender

**Improvement:** Automatically pass microservice_boundaries.json to Architecture Recommender V2

**Workflow:**
```
Dependency Mapper V2 → Architecture Recommender V2
```

**Integration:**
- Add Step Functions choice state: "If microservices found, trigger Architecture Recommender"
- Pass microservice boundaries as input
- Architecture Recommender generates deployment architecture

**Benefits:**
- End-to-end modernization flow
- From COBOL dependencies → Microservices → AWS architecture
- Automated recommendation pipeline

**Effort:** LOW (2-3 days)

---

### 10. Add Cost Estimation

**Improvement:** Estimate modernization cost based on dependency analysis

**Calculation:**
```
cost = (total_programs * base_cost_per_program) +
       (high_coupling_programs * complexity_premium) +
       (shared_components * refactoring_cost)
```

**Output:**
```json
{
  "estimated_cost": {
    "base_modernization": "$50,000",
    "complexity_premium": "$15,000",
    "shared_library_refactoring": "$10,000",
    "total": "$75,000",
    "range": "$60,000 - $90,000",
    "timeline": "3-4 months"
  },
  "cost_breakdown": {
    "per_program": "$2,500",
    "high_complexity_programs": 1,
    "shared_components": 15
  }
}
```

**Benefits:**
- Help customers plan budgets
- Set expectations for modernization effort
- Prioritize high-value refactoring

**Effort:** LOW (2-3 days)

---

## Appendix

### A. Job ID Examples

```
dmv2_job_0U812_TestApp01_1762439738_3581cb90
dmv2_job_341_PramodTestApp_1762425515_1fdb0d27
dmv2_job_341_PramodTestApp_1762425003_a109c2c8
```

### B. S3 Path Examples

```
s3://code-transformation-v2/0U812/TestApp01/dependency_mapper_v2/jobs/dmv2_job_0U812_TestApp01_1762439738_3581cb90/artifacts/dependency_graph.json

s3://code-transformation-v2/0U812/TestApp01/dependency_mapper_v2/jobs/dmv2_job_0U812_TestApp01_1762439738_3581cb90/temp/batch_analysis/batch_0.json
```

### C. Step Functions ARN

```
arn:aws:states:us-east-1:376129851858:stateMachine:DependencyMapperWorkflowV2
```

### D. Lambda ARNs

```
arn:aws:lambda:us-east-1:376129851858:function:DependencyMapperV2PrepareAnalysis
arn:aws:lambda:us-east-1:376129851858:function:DependencyMapperV2StaticParser
arn:aws:lambda:us-east-1:376129851858:function:DependencyMapperV2MergeStatic
arn:aws:lambda:us-east-1:376129851858:function:DependencyMapperV2AIAnalyzer
arn:aws:lambda:us-east-1:376129851858:function:DependencyMapperV2GraphBuilder
arn:aws:lambda:us-east-1:376129851858:function:DependencyMapperV2CouplingCalculator
arn:aws:lambda:us-east-1:376129851858:function:DependencyMapperV2RiskAssessor
arn:aws:lambda:us-east-1:376129851858:function:DependencyMapperV2MicroserviceDetector
arn:aws:lambda:us-east-1:376129851858:function:DependencyMapperV2ImpactAnalyzer
```

### E. Sample Execution Commands

**Start Execution:**
```bash
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:376129851858:stateMachine:DependencyMapperWorkflowV2 \
  --name "execution-dmv2_job_TEST_APP_$(date +%s)_$(uuidgen | cut -c1-8)" \
  --input '{
    "job_id": "dmv2_job_TEST_APP_'$(date +%s)'_'$(uuidgen | cut -c1-8)'",
    "scout_account_id": "TEST",
    "application_name": "APP",
    "source_hash": "abc123..."
  }'
```

**Check Status:**
```bash
aws stepfunctions describe-execution \
  --execution-arn arn:aws:states:us-east-1:376129851858:execution:DependencyMapperWorkflowV2:execution-dmv2_job_TEST_APP_123_abc
```

**Download Artifacts:**
```bash
aws s3 cp \
  s3://code-transformation-v2/TEST/APP/dependency_mapper_v2/jobs/dmv2_job_TEST_APP_123_abc/artifacts/ \
  ./artifacts/ \
  --recursive
```

---

## Summary

Dependency Mapper V2 is a **comprehensive, multi-phase dependency analysis flow** that:

1. **Parses COBOL Dependencies:** Static parsing of CALL, COPY, FILE I/O
2. **Enhances with AI:** Bedrock analysis for semantic dependencies
3. **Builds Dependency Graph:** Complete graph with nodes/edges, fan-in/fan-out
4. **Calculates Metrics:** Coupling scores, risk assessment
5. **Suggests Microservices:** Service boundaries based on cohesion/coupling
6. **Analyzes Impact:** Blast radius for each program

**Key Strengths:**
- Multi-phase pipeline (static → AI → graph → metrics → services → impact)
- Parallel processing (MaxConcurrency: 40)
- Rich output artifacts (7 analysis files)
- Actionable recommendations (microservice boundaries, impact scores)

**Key Questions:**
- How is this triggered? (No API Gateway found)
- What consumes microservice_boundaries.json?
- Is AI analysis delivering value? (only 4.3 KB output)

**V5 Opportunities:**
- Add API Gateway endpoint
- Enhance AI analysis depth
- Add LOC/complexity calculation
- Detect cyclic dependencies
- Parse database dependencies
- Cross-application analysis
- Integration with Architecture Recommender

**Performance:** 29 seconds for 20 programs - excellent!

---

**Document Version:** 1.0
**Created By:** Claude Code (Analysis)
**Date:** November 6, 2025
**Status:** Complete
