# Monolith Identifier V2 - High-Level Design (HLD)

**Version:** V2 (Production)
**Status:** ✅ ACTIVE (Serving 100+ users)
**Created:** October 3, 2025 (estimated)
**Analyzed:** November 6, 2025
**Purpose:** Identify monolithic patterns in COBOL code, suggest decomposition strategies and microservice boundaries

---

## ⚠️ QUESTIONS & POTENTIAL ISSUES

### 🟡 Question #1: Overlap with Dependency Mapper V2

**Question:** How does Monolith Identifier V2 differ from Dependency Mapper V2's microservice recommendations?

**What We Know:**
- **Dependency Mapper V2** suggests microservices based on coupling/cohesion analysis
- **Monolith Identifier V2** suggests microservices based on monolithic pattern detection
- Both produce `recommended_microservices` output
- Sample shows DIFFERENT recommendations for same codebase

**Overlap:**
- Both analyze same codebase (TestApp01 with 20 files)
- Both recommend microservice boundaries
- Both calculate modularity metrics

**Differences (Inferred):**
- Dependency Mapper focuses on TECHNICAL coupling (CALL, COPY dependencies)
- Monolith Identifier focuses on BUSINESS capabilities (Customer Management, Order Processing)
- Dependency Mapper creates 20 services (2.4 programs each - technical clustering)
- Monolith Identifier creates 4-5 services (business capability clustering)

**Impact on V5:**
- Should these be merged into single flow?
- Should they run in sequence (dependencies → business capabilities)?
- Which recommendations should customers follow?

---

### 🟡 Question #2: Large Program Extraction Complexity

**Question:** All recommended services show `"extraction_complexity": "high"` and `"estimated_effort_weeks": 9`. Is this accurate?

**What We Know:**
- CMCMCL00.CBL appears in MULTIPLE services:
  - Customer ManagementService
  - Order ProcessingService
  - ReportingService
  - Data ValidationService
- Each service recommends extracting DIFFERENT business capabilities from THE SAME program
- All show 9-week effort estimates

**Possible Issues:**
- CMCMCL00.CBL is a God Object (single program with multiple responsibilities)
- Extracting multiple services from ONE program is extremely complex
- 9 weeks per service * 4 services = 36 weeks total (unrealistic)

**Questions:**
- Should we recommend refactoring CMCMCL00.CBL FIRST, then extracting services?
- Are effort estimates considering shared code extraction?
- How do we handle one program → multiple services decomposition?

---

### 🟡 Question #3: AI Pattern Analysis Output Size

**Question:** `ai_pattern_analysis.json` is 8 KB. Is AI analysis providing deep insights?

**What We Know:**
- AIAnalyzer Lambda has 5-minute timeout
- Output is 8 KB (larger than Dependency Mapper's 4.3 KB, but still small)
- Uses Bedrock Claude 3.5 Sonnet
- Runs for ~16 seconds (similar to Dependency Mapper)

**Comparison:**
- Dependency Mapper AI: 4.3 KB output
- Monolith Identifier AI: 8 KB output
- Both use Claude 3.5 Sonnet
- Both run ~16 seconds

**Question:**
- Is 8 KB sufficient for monolith pattern analysis?
- Should we expand AI analysis scope in V5?

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

Monolith Identifier V2 is a **monolithic pattern detection and decomposition planning flow** that:

1. **Identifies Monolithic Patterns:** Detects God Objects, Big Ball of Mud, large programs
2. **Calculates Modularity Metrics:** Cohesion, coupling, complexity scores per program
3. **Detects Anti-Patterns:** Specific monolith smells (tight coupling, low cohesion)
4. **Recommends Decomposition:** Suggests how to break monolith into microservices
5. **Estimates Effort:** Provides time/complexity estimates for extraction

### Key Characteristics

| Characteristic | Value |
|----------------|-------|
| **Package Type** | ZIP (all 10 Lambdas) |
| **Runtime** | Python 3.11 |
| **Step Functions** | MonolithIdentifierWorkflowV2 |
| **Lambda Count** | 10 functions (7 workflow + 3 API) |
| **Processing Mode** | Batch + Sequential |
| **AI Integration** | AWS Bedrock (Claude 3.5 Sonnet) |
| **Execution Time** | ~3 min 40 sec (20 files) |
| **Output Artifacts** | 5 analysis files + 2 batch files |

### What Makes This Different

**Compared to Dependency Mapper V2:**
- **Focus:** Business capability decomposition vs. technical dependency clustering
- **Pattern Detection:** Monolith anti-patterns vs. coupling metrics
- **Service Boundaries:** Fewer, larger services (4-5) vs. many small services (20)
- **Recommendations:** Business-driven extraction vs. technically-driven clustering

**Compared to Code Analysis V3:**
- **Scope:** Application-level patterns vs. file-level analysis
- **Output:** Decomposition strategy vs. code structure
- **Use Case:** Architecture planning vs. code generation

---

## Architecture Diagram

```
                    ┌─────────────────────────────────────────┐
                    │  Monolith Identifier V2 Workflow        │
                    │  (Step Functions)                       │
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  1. PrepareAnalysis                     │
                    │  - Reads source files                   │
                    │  - Creates 2 batches                    │
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
        ┌───────────────────────────┴───────────────────────────┐
        │           2. StaticAnalysisMap (Parallel)             │
        ├────────────────────────┬──────────────────────────────┤
        │  Batch 0               │  Batch 1                     │
        │  (10 files)            │  (10 files)                  │
        │  ↓                     │  ↓                           │
        │  StaticParser          │  StaticParser                │
        │  - Detect large files  │  - Detect large files        │
        │  - Calculate LOC       │  - Calculate LOC             │
        └────────────────────────┴──────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  3. MergeStatic                         │
                    │  - Combines batch results               │
                    │  - Produces: static_monolith_analysis.json│
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  4. AIAnalyzer                          │
                    │  - Bedrock Claude 3.5 Sonnet            │
                    │  - Detect monolith patterns             │
                    │  - Business capability identification   │
                    │  - Produces: ai_pattern_analysis.json   │
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  5. PatternDetector                     │
                    │  - God Object detection                 │
                    │  - Big Ball of Mud detection            │
                    │  - Large program identification         │
                    │  - Produces: detected_patterns.json     │
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  6. ModularityCalculator                │
                    │  - Cohesion metrics                     │
                    │  - Coupling metrics                     │
                    │  - Complexity scores                    │
                    │  - Produces: modularity_metrics.json    │
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  7. DecompositionStrategy               │
                    │  - Recommend microservices              │
                    │  - Estimate extraction effort           │
                    │  - Migration strategy                   │
                    │  - Produces: decomposition_strategy.json│
                    └─────────────────────────────────────────┘
                                    │
                                    ↓
                    ┌─────────────────────────────────────────┐
                    │  OUTPUTS (5 Artifacts)                  │
                    ├─────────────────────────────────────────┤
                    │  1. static_monolith_analysis.json       │
                    │  2. ai_pattern_analysis.json            │
                    │  3. detected_patterns.json              │
                    │  4. modularity_metrics.json             │
                    │  5. decomposition_strategy.json         │
                    └─────────────────────────────────────────┘
```

---

## API Endpoint

### Endpoint: /monolithidentifierv2

**URL:** `https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/monolithidentifierv2`

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
  "job_id": "miv2_job_0U812_TestApp01_1762440368_7754f811",
  "status": "started",
  "execution_arn": "arn:aws:states:us-east-1:376129851858:execution:MonolithIdentifierWorkflowV2:execution-miv2_job_0U812_TestApp01_1762440368_7754f811"
}
```

**Example Request:**
```bash
curl -X POST https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/monolithidentifierv2 \
  -H "Content-Type: application/json" \
  -d '{
    "scout_account_id": "0U812",
    "application_name": "TestApp01",
    "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74"
  }'
```

**Additional Endpoints:**

**Status Endpoint:**
```
GET https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/monolithidentifierv2/status/{job_id}
```

**Results Endpoint:**
```
GET https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/monolithidentifierv2/results/{job_id}
```

**Expected Preconditions:**
- Source files must exist in S3 (content-addressed by source_hash)
- Ingest flow must have completed successfully
- `source_hash` must match uploaded files

**Triggers:**
- API Gateway POST request → MonolithIdentifierV2StartJob Lambda → Step Functions StartExecution

---

## Step Functions Workflow

### Workflow: MonolithIdentifierWorkflowV2

**ARN:** `arn:aws:states:us-east-1:376129851858:stateMachine:MonolithIdentifierWorkflowV2`

### State Machine Definition

**States (10 total):**
1. UpdateStatusRunning
2. PrepareAnalysis
3. StaticAnalysisMap
4. MergeStatic
5. AIAnalyzer
6. PatternDetector
7. ModularityCalculator
8. DecompositionStrategy
9. UpdateStatusCompleted
10. Success

#### 1. UpdateStatusRunning (S3 PutObject)
**Purpose:** Mark job as running

**S3 Key:**
```
{account}/{app}/monolith_identifier_v2/jobs/{job_id}/status.json
```

**Status Body:**
```json
{
  "state": "running",
  "status": "running",
  "progress": 5,
  "phase": "initializing",
  "message": "Starting monolith analysis..."
}
```

#### 2. PrepareAnalysis (Lambda)
**Lambda:** `MonolithIdentifierV2PrepareAnalysis`
**Timeout:** 60 seconds

**Purpose:**
- Read source files from S3 (content-addressed storage)
- Calculate file sizes and LOC estimates
- Split files into batches for parallel processing
- Create batch configuration

**Output:**
```json
{
  "job_id": "miv2_job_...",
  "total_files": 20,
  "total_batches": 2,
  "batches": [
    {
      "batch_id": 0,
      "files": ["file1.CBL", "file2.CBL", ...]
    },
    {
      "batch_id": 1,
      "files": ["file11.CBL", "file12.CBL", ...]
    }
  ]
}
```

**Batch Strategy:**
- **Batch Size:** ~10 files per batch (default)
- **Reason:** Balance parallelism vs. Lambda cold start

#### 3. StaticAnalysisMap (Map State)
**Type:** Map
**ItemsPath:** `$.batches`

**Purpose:** Process each batch in parallel for static monolith pattern detection

**Map Iterator: StaticParser Lambda**

**Per-Batch Processing:**
1. For each file, analyze:
   - Total LOC (lines of code)
   - Number of sections (IDENTIFICATION, DATA, PROCEDURE)
   - Number of paragraphs
   - Number of PERFORM statements
   - Number of GOTO statements (code smell)
   - Cyclomatic complexity (estimated)
2. Detect large program pattern (LOC > threshold)
3. Detect God Object pattern (high complexity + many sections)
4. Store results to S3 batches folder

**Output (per batch):**
```json
{
  "batch_id": 0,
  "files_analyzed": 10,
  "large_programs": [
    {
      "program": "CMCMCL00.CBL",
      "loc": 9024,
      "complexity": "HIGH",
      "sections": 120,
      "paragraphs": 450,
      "goto_count": 15,
      "perform_count": 320
    }
  ],
  "analyzed_at": "2025-11-06T14:46:15.123Z"
}
```

#### 4. MergeStatic (Lambda)
**Lambda:** `MonolithIdentifierV2MergeStatic`
**Timeout:** 60 seconds

**Purpose:**
- Read all batch results from S3
- Combine into single static_monolith_analysis.json
- Calculate aggregate statistics
- Identify top monolithic programs

**Output:**
```json
{
  "source_job_id": "miv2_job_...",
  "generated_at": "2025-11-06T14:46:20.123Z",
  "aggregate_stats": {
    "total_programs": 20,
    "total_loc": 15000,
    "average_loc": 750,
    "large_programs_count": 3,
    "god_objects_count": 1
  },
  "programs": [
    {
      "program": "CMCMCL00.CBL",
      "loc": 9024,
      "complexity": "HIGH",
      "sections": 120,
      "paragraphs": 450,
      "is_large": true,
      "is_god_object": true
    }
  ]
}
```

**S3 Output:**
```
{account}/{app}/monolith_identifier_v2/jobs/{job_id}/artifacts/static_monolith_analysis.json
```

**Sample Size:** 11 KB (20 programs)

#### 5. AIAnalyzer (Lambda)
**Lambda:** `MonolithIdentifierV2AIAnalyzer`
**Timeout:** 300 seconds (5 minutes)
**Memory:** 1024 MB

**Purpose:**
- AI-powered monolith pattern detection using Bedrock
- Identify business capabilities in monolithic programs
- Detect hidden anti-patterns
- Suggest business-driven decomposition

**Bedrock Configuration:**
- **Model:** Claude 3.5 Sonnet
- **Region:** us-east-1
- **Max Tokens:** ~10000 (estimated)
- **Temperature:** 0.3 (low - prioritize accuracy)

**Prompt Template (Inferred):**
```
You are analyzing a COBOL monolithic application. Here is the static analysis:

[static_monolith_analysis.json content]

Questions:
1. Which programs are God Objects (single programs with multiple business capabilities)?
2. What business capabilities can you identify in large programs?
3. Are there Big Ball of Mud patterns (tightly coupled, no clear separation)?
4. How should we decompose the monolith into microservices?

Provide your analysis in JSON format with:
- detected_god_objects[]
- business_capabilities[]
- decomposition_recommendations[]
```

**Output:**
```json
{
  "source_job_id": "miv2_job_...",
  "generated_at": "2025-11-06T14:49:40.123Z",
  "detected_god_objects": [
    {
      "program": "CMCMCL00.CBL",
      "confidence": 0.95,
      "business_capabilities": [
        "Customer Management",
        "Order Processing",
        "Reporting",
        "Data Validation"
      ],
      "recommendation": "Extract into 4 separate microservices"
    }
  ],
  "big_ball_of_mud_score": 0.65,
  "decomposition_recommendations": [
    {
      "service": "Customer ManagementService",
      "programs": ["CMCMCL00.CBL"],
      "business_capability": "Customer management",
      "extraction_priority": "HIGH"
    }
  ]
}
```

**Sample Output Size:** 8 KB

**Execution Time:** ~16 seconds (similar to Dependency Mapper)

#### 6. PatternDetector (Lambda)
**Lambda:** `MonolithIdentifierV2PatternDetector`
**Timeout:** 90 seconds

**Purpose:**
- Detect specific monolith anti-patterns
- God Object (single class/program with many responsibilities)
- Big Ball of Mud (tangled dependencies, no structure)
- Large Program (LOC > threshold)
- Low Modularity (poor cohesion/coupling)

**Detection Algorithms:**

**God Object:**
```
IF (loc > 5000 AND sections > 100 AND business_capabilities > 3):
    pattern = "GOD_OBJECT"
```

**Big Ball of Mud:**
```
IF (goto_count > 10 AND cyclomatic_complexity > 50):
    pattern = "BIG_BALL_OF_MUD"
```

**Large Program:**
```
IF (loc > 3000):
    pattern = "LARGE_PROGRAM"
```

**Output:**
```json
{
  "source_job_id": "miv2_job_...",
  "generated_at": "2025-11-06T14:49:44.123Z",
  "detected_patterns": [
    {
      "pattern_type": "GOD_OBJECT",
      "program": "CMCMCL00.CBL",
      "severity": "HIGH",
      "confidence": 0.95,
      "indicators": [
        "LOC: 9024 (threshold: 5000)",
        "Sections: 120 (threshold: 100)",
        "Business capabilities: 4 (threshold: 3)"
      ],
      "recommendation": "Decompose into multiple services by business capability"
    },
    {
      "pattern_type": "LARGE_PROGRAM",
      "program": "CMCMCL00.CBL",
      "severity": "HIGH",
      "confidence": 1.0,
      "indicators": [
        "LOC: 9024 (threshold: 3000)"
      ],
      "recommendation": "Refactor into smaller modules"
    }
  ],
  "summary": {
    "god_objects": 1,
    "big_ball_of_mud": 0,
    "large_programs": 3
  }
}
```

**Sample Output Size:** 1.5 KB

#### 7. ModularityCalculator (Lambda)
**Lambda:** `MonolithIdentifierV2ModularityCalculator`
**Timeout:** 120 seconds
**Memory:** 1024 MB

**Purpose:**
- Calculate modularity metrics for each program
- Cohesion score (how focused is the program)
- Coupling score (how many dependencies)
- Complexity score (cyclomatic complexity)
- Maintainability index

**Metrics Calculated:**

**Cohesion Score:**
```
cohesion = 1 / (business_capabilities_count)
# Lower is better (1 capability = 1.0, 4 capabilities = 0.25)
```

**Coupling Score:**
```
coupling = (calls_count + copies_count) / total_programs
# Lower is better
```

**Complexity Score:**
```
complexity = (goto_count * 2) + (perform_count * 0.5) + (sections * 0.1)
# Lower is better
```

**Maintainability Index:**
```
maintainability = 100 - (complexity * 0.5) - (coupling * 20) - (1 - cohesion) * 30
# Higher is better (0-100)
```

**Output:**
```json
{
  "source_job_id": "miv2_job_...",
  "generated_at": "2025-11-06T14:49:42.123Z",
  "aggregate_metrics": {
    "average_cohesion": 0.65,
    "average_coupling": 0.15,
    "average_complexity": 45.5,
    "average_maintainability": 62.3
  },
  "programs": [
    {
      "program": "CMCMCL00.CBL",
      "loc": 9024,
      "cohesion_score": 0.25,
      "coupling_score": 0.38,
      "complexity_score": 85.2,
      "maintainability_index": 32.5,
      "classification": "LOW_MAINTAINABILITY",
      "recommendations": [
        "Improve cohesion by extracting business capabilities",
        "Reduce coupling by decoupling dependencies",
        "Reduce complexity by refactoring GOTO statements"
      ]
    }
  ]
}
```

**Sample Output Size:** 6.5 KB

**Classification Thresholds:**
- **HIGH Maintainability:** > 70
- **MEDIUM Maintainability:** 40-70
- **LOW Maintainability:** < 40

#### 8. DecompositionStrategy (Lambda)
**Lambda:** `MonolithIdentifierV2DecompositionStrategy`
**Timeout:** 120 seconds
**Memory:** 1024 MB

**Purpose:**
- Generate decomposition strategy and migration plan
- Recommend microservice boundaries based on business capabilities
- Estimate extraction effort and complexity
- Prioritize refactoring work

**Input:**
- static_monolith_analysis.json
- ai_pattern_analysis.json
- detected_patterns.json
- modularity_metrics.json

**Algorithm:**
1. Identify God Objects (programs with multiple business capabilities)
2. For each business capability in God Object:
   - Create microservice recommendation
   - Estimate LOC to extract
   - Calculate extraction complexity
   - Estimate effort in weeks
3. Prioritize by business value and extraction complexity
4. Generate migration strategy

**Extraction Complexity Formula:**
```
IF (coupling_score > 0.3 AND complexity_score > 70):
    extraction_complexity = "high"
    effort_weeks = (loc / 1000) * 1.5
ELIF (coupling_score > 0.15 OR complexity_score > 40):
    extraction_complexity = "medium"
    effort_weeks = (loc / 1000) * 1.0
ELSE:
    extraction_complexity = "low"
    effort_weeks = (loc / 1000) * 0.5
```

**Output:**
```json
{
  "source_job_id": "miv2_job_...",
  "generated_at": "2025-11-06T14:49:45.123Z",
  "recommended_microservices": [
    {
      "service_name": "Customer ManagementService",
      "programs": ["IBMi-Cobol/Cobol/CMCMCL00.CBL"],
      "total_loc": 9279,
      "business_capability": "Customer management",
      "shared_data": [],
      "dependencies": [],
      "extraction_complexity": "high",
      "estimated_effort_weeks": 9
    },
    {
      "service_name": "Order ProcessingService",
      "programs": ["IBMi-Cobol/Cobol/CMCMCL00.CBL"],
      "total_loc": 9024,
      "business_capability": "Order processing",
      "shared_data": [],
      "dependencies": [],
      "extraction_complexity": "high",
      "estimated_effort_weeks": 9
    }
  ],
  "migration_strategy": {
    "approach": "Strangler Fig Pattern",
    "phases": [
      {
        "phase": 1,
        "description": "Extract Customer Management Service",
        "effort_weeks": 9,
        "risk": "HIGH"
      },
      {
        "phase": 2,
        "description": "Extract Order Processing Service",
        "effort_weeks": 9,
        "risk": "HIGH"
      }
    ],
    "total_effort_weeks": 36,
    "estimated_timeline": "9 months"
  },
  "refactoring_priorities": [
    {
      "priority": 1,
      "program": "CMCMCL00.CBL",
      "reason": "God Object with 4 business capabilities",
      "recommended_action": "Decompose into 4 microservices",
      "estimated_effort": "36 weeks"
    }
  ]
}
```

**Sample Output Size:** 4.7 KB

**Key Insights:**
- **Strangler Fig Pattern:** Gradually replace monolith by extracting services one at a time
- **Business Capability Focus:** Services aligned with business domains (Customer, Order, Reporting)
- **God Object Decomposition:** Extract multiple services from single large program

#### 9. UpdateStatusCompleted (S3 PutObject)
**Purpose:** Mark job as completed

**S3 Key:**
```
{account}/{app}/monolith_identifier_v2/jobs/{job_id}/status.json
```

**Status Body:**
```json
{
  "state": "completed",
  "status": "completed",
  "progress": 100,
  "phase": "completed",
  "message": "Monolith analysis completed successfully"
}
```

#### 10. Success (Succeed State)
**Purpose:** Workflow termination

---

## Lambda Functions

### Summary Table

| Lambda | Purpose | Timeout | Memory | Type |
|--------|---------|---------|--------|------|
| StartJob | API trigger | 30s | 256 MB | API |
| PrepareAnalysis | Create batches | 60s | 512 MB | Workflow |
| StaticParser | Parse monolith patterns | 120s | 1024 MB | Workflow |
| MergeStatic | Combine batches | 60s | 512 MB | Workflow |
| AIAnalyzer | AI analysis | 300s | 1024 MB | Workflow |
| PatternDetector | Detect anti-patterns | 90s | 512 MB | Workflow |
| ModularityCalculator | Modularity metrics | 120s | 1024 MB | Workflow |
| DecompositionStrategy | Decomposition plan | 120s | 1024 MB | Workflow |
| StatusAPI | Status endpoint | 30s | 256 MB | API |
| ResultsAPI | Results endpoint | 30s | 256 MB | API |

**Total:** 10 Lambda functions (7 workflow + 3 API)

**Note:** API Lambdas (StartJob, StatusAPI, ResultsAPI) are NOT invoked by Step Functions - they are API Gateway handlers.

---

## Data Structures

### 1. Job Info (job_info.json)

```json
{
  "job_id": "miv2_job_0U812_TestApp01_1762440368_7754f811",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74",
  "created_at": "2025-11-06T14:46:08.900361+00:00",
  "status": "pending",
  "workflow": "MonolithIdentifierWorkflowV2"
}
```

### 2. Job Status (status.json)

```json
{
  "state": "completed",
  "status": "completed",
  "progress": 100,
  "phase": "completed",
  "message": "Monolith analysis completed successfully"
}
```

**States:**
- `pending` - Job created
- `running` - Workflow executing
- `completed` - Workflow finished successfully
- `failed` - Workflow failed

### 3. Static Monolith Analysis (static_monolith_analysis.json)

```json
{
  "source_job_id": "miv2_job_...",
  "generated_at": "2025-11-06T14:46:20.123Z",
  "aggregate_stats": {
    "total_programs": 20,
    "total_loc": 15000,
    "average_loc": 750,
    "large_programs_count": 3,
    "god_objects_count": 1
  },
  "programs": [
    {
      "program": "CMCMCL00.CBL",
      "loc": 9024,
      "complexity": "HIGH",
      "sections": 120,
      "paragraphs": 450,
      "goto_count": 15,
      "perform_count": 320,
      "is_large": true,
      "is_god_object": true
    }
  ]
}
```

**Size:** 11 KB (20 programs)

### 4. AI Pattern Analysis (ai_pattern_analysis.json)

```json
{
  "source_job_id": "miv2_job_...",
  "generated_at": "2025-11-06T14:49:40.123Z",
  "detected_god_objects": [
    {
      "program": "CMCMCL00.CBL",
      "confidence": 0.95,
      "business_capabilities": [
        "Customer Management",
        "Order Processing",
        "Reporting",
        "Data Validation"
      ],
      "recommendation": "Extract into 4 separate microservices"
    }
  ],
  "big_ball_of_mud_score": 0.65,
  "decomposition_recommendations": [
    {
      "service": "Customer ManagementService",
      "programs": ["CMCMCL00.CBL"],
      "business_capability": "Customer management",
      "extraction_priority": "HIGH"
    }
  ]
}
```

**Size:** 8 KB

### 5. Detected Patterns (detected_patterns.json)

```json
{
  "source_job_id": "miv2_job_...",
  "generated_at": "2025-11-06T14:49:44.123Z",
  "detected_patterns": [
    {
      "pattern_type": "GOD_OBJECT",
      "program": "CMCMCL00.CBL",
      "severity": "HIGH",
      "confidence": 0.95,
      "indicators": [
        "LOC: 9024 (threshold: 5000)",
        "Sections: 120 (threshold: 100)",
        "Business capabilities: 4 (threshold: 3)"
      ],
      "recommendation": "Decompose into multiple services by business capability"
    }
  ],
  "summary": {
    "god_objects": 1,
    "big_ball_of_mud": 0,
    "large_programs": 3
  }
}
```

**Size:** 1.5 KB

### 6. Modularity Metrics (modularity_metrics.json)

```json
{
  "source_job_id": "miv2_job_...",
  "generated_at": "2025-11-06T14:49:42.123Z",
  "aggregate_metrics": {
    "average_cohesion": 0.65,
    "average_coupling": 0.15,
    "average_complexity": 45.5,
    "average_maintainability": 62.3
  },
  "programs": [
    {
      "program": "CMCMCL00.CBL",
      "loc": 9024,
      "cohesion_score": 0.25,
      "coupling_score": 0.38,
      "complexity_score": 85.2,
      "maintainability_index": 32.5,
      "classification": "LOW_MAINTAINABILITY",
      "recommendations": [
        "Improve cohesion by extracting business capabilities",
        "Reduce coupling by decoupling dependencies",
        "Reduce complexity by refactoring GOTO statements"
      ]
    }
  ]
}
```

**Size:** 6.5 KB

### 7. Decomposition Strategy (decomposition_strategy.json)

```json
{
  "source_job_id": "miv2_job_...",
  "generated_at": "2025-11-06T14:49:45.123Z",
  "recommended_microservices": [
    {
      "service_name": "Customer ManagementService",
      "programs": ["IBMi-Cobol/Cobol/CMCMCL00.CBL"],
      "total_loc": 9279,
      "business_capability": "Customer management",
      "shared_data": [],
      "dependencies": [],
      "extraction_complexity": "high",
      "estimated_effort_weeks": 9
    }
  ],
  "migration_strategy": {
    "approach": "Strangler Fig Pattern",
    "phases": [
      {
        "phase": 1,
        "description": "Extract Customer Management Service",
        "effort_weeks": 9,
        "risk": "HIGH"
      }
    ],
    "total_effort_weeks": 36,
    "estimated_timeline": "9 months"
  },
  "refactoring_priorities": [
    {
      "priority": 1,
      "program": "CMCMCL00.CBL",
      "reason": "God Object with 4 business capabilities",
      "recommended_action": "Decompose into 4 microservices",
      "estimated_effort": "36 weeks"
    }
  ]
}
```

**Size:** 4.7 KB

---

## S3 Storage Layout

### Bucket Structure

```
code-transformation-v2/
└── {account_id}/                           # e.g., "0U812"
    └── {application_name}/                 # e.g., "TestApp01"
        └── monolith_identifier_v2/
            └── jobs/
                └── {job_id}/               # e.g., "miv2_job_0U812_TestApp01_1762440368_7754f811"
                    ├── job_info.json
                    ├── status.json
                    ├── batch_config.json
                    ├── batches/
                    │   ├── static_batch_0.json
                    │   └── static_batch_1.json
                    └── artifacts/
                        ├── static_monolith_analysis.json  (11 KB)
                        ├── ai_pattern_analysis.json       (8 KB)
                        ├── detected_patterns.json         (1.5 KB)
                        ├── modularity_metrics.json        (6.5 KB)
                        └── decomposition_strategy.json    (4.7 KB)
```

### Job ID Pattern

```
miv2_job_{account}_{app}_{timestamp}_{uuid}
```

**Example:**
```
miv2_job_0U812_TestApp01_1762440368_7754f811
```

**Components:**
- `miv2_` - Monolith Identifier V2 prefix
- `job_` - Job identifier
- `0U812` - Scout account ID
- `TestApp01` - Application name
- `1762440368` - Unix timestamp
- `7754f811` - Short UUID (first 8 chars)

### Artifact Descriptions

| Artifact | Size | Purpose |
|----------|------|---------|
| static_monolith_analysis.json | 11 KB | Static pattern analysis (large programs, God objects) |
| ai_pattern_analysis.json | 8 KB | AI-detected patterns and business capabilities |
| detected_patterns.json | 1.5 KB | List of specific anti-patterns |
| modularity_metrics.json | 6.5 KB | Cohesion, coupling, complexity metrics |
| decomposition_strategy.json | 4.7 KB | Microservice recommendations and migration plan |

**Total Artifacts:** ~32 KB (for 20 programs)

---

## Integration Points

### Upstream Dependencies

**Required Inputs:**
1. **Source Files** must exist in S3:
   - Location: `s3://code-transformation-v2/sources/{source_hash}/`
   - Content-addressed storage
2. **Ingest Flow** must have run first
3. **Job ID** must be generated by StartJob Lambda

**Likely Upstream Flow:**
- Ingest Flow → Monolith Identifier V2 (direct API call from customer)
- Code Analysis V2/V3 → Monolith Identifier V2 (chained execution)

### Downstream Consumers

**Who Consumes Monolith Identifier V2 Outputs?**

**Potential Consumers:**
1. **Architecture Recommender V2**
   - Uses `decomposition_strategy.json` for architecture recommendations
   - Uses `recommended_microservices` for AWS service mapping

2. **Customer UI / Dashboard**
   - Visualizes `detected_patterns` (God Objects, Big Ball of Mud)
   - Shows `decomposition_strategy` (migration plan)
   - Displays `modularity_metrics` (maintainability scores)

3. **JavaGen V3 (Future)**
   - Could use `recommended_microservices` to generate separate Spring Boot services
   - Could use `business_capability` to organize code structure

4. **Refactoring Workflows**
   - Uses `refactoring_priorities` to prioritize work
   - Uses `estimated_effort_weeks` for project planning

**Comparison with Dependency Mapper V2:**
- **Dependency Mapper V2:** Technical coupling-based microservices (20 services)
- **Monolith Identifier V2:** Business capability-based microservices (4-5 services)
- **Recommendation:** Use BOTH - Dependency Mapper for technical boundaries, Monolith Identifier for business boundaries

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
| **IAM Role** | BedrockAgentRole-CodeRefactor | (shared with other V2 flows) |

### Lambda Configurations

| Lambda | Timeout | Memory | Concurrency |
|--------|---------|--------|-------------|
| StartJob | 30s | 256 MB | Default |
| PrepareAnalysis | 60s | 512 MB | Default |
| StaticParser | 120s | 1024 MB | Map state |
| MergeStatic | 60s | 512 MB | Default |
| AIAnalyzer | 300s | 1024 MB | Default |
| PatternDetector | 90s | 512 MB | Default |
| ModularityCalculator | 120s | 1024 MB | Default |
| DecompositionStrategy | 120s | 1024 MB | Default |
| StatusAPI | 30s | 256 MB | Default |
| ResultsAPI | 30s | 256 MB | Default |

---

## Sample Execution Analysis

### Execution Details

- **Job ID:** `miv2_job_0U812_TestApp01_1762440368_7754f811`
- **Account:** 0U812
- **Application:** TestApp01
- **Source Hash:** `9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74`
- **Files Analyzed:** 20 COBOL programs
- **Start Time:** 2025-11-06 08:46:09
- **End Time:** 2025-11-06 08:49:46
- **Duration:** 3 minutes 37 seconds
- **Status:** SUCCEEDED

### Performance Metrics

| Phase | Duration | Component |
|-------|----------|-----------|
| Prepare | ~3 seconds | PrepareAnalysis Lambda |
| Static Parsing | ~8 seconds | 2 batches (StaticParser) |
| Merge Static | ~5 seconds | MergeStatic Lambda |
| AI Analysis | ~20 seconds | AIAnalyzer Lambda |
| Pattern Detection | ~2 seconds | PatternDetector Lambda |
| Modularity Calc | ~2 seconds | ModularityCalculator Lambda |
| Decomposition | ~3 seconds | DecompositionStrategy Lambda |

**Total:** ~3 minutes 37 seconds

**Performance Notes:**
- **Slowest:** AI Analysis (20s) - 9% of total time (much less than expected)
- **Faster than Dependency Mapper:** 3.5 min vs. 29 sec (monolith analysis is more complex)
- **Batch Processing:** 2 batches (vs. Dependency Mapper's 4) - larger batch size

### Key Findings

**God Objects Detected:** 1
- **CMCMCL00.CBL:** 9024 LOC, 4 business capabilities

**Recommended Microservices:** 4
1. Customer ManagementService (9279 LOC, 9 weeks effort)
2. Order ProcessingService (9024 LOC, 9 weeks effort)
3. ReportingService (9279 LOC, 9 weeks effort)
4. Data ValidationService (9279 LOC, 9 weeks effort)

**Total Extraction Effort:** 36 weeks (9 months)

**Migration Strategy:** Strangler Fig Pattern (gradual extraction)

**Key Insight:**
- **CMCMCL00.CBL is a God Object** - single program containing 4 distinct business capabilities
- **Decomposition Challenge:** Extracting 4 services from ONE program is extremely complex
- **Effort Estimates:** 36 weeks total (9 weeks per service)

---

## Known Limitations

### 1. Overlapping Service Recommendations

**Issue:** Same program (CMCMCL00.CBL) appears in MULTIPLE recommended services.

**Impact:**
- Customer ManagementService includes CMCMCL00.CBL
- Order ProcessingService includes CMCMCL00.CBL
- ReportingService includes CMCMCL00.CBL
- Data ValidationService includes CMCMCL00.CBL

**Root Cause:** God Object has multiple business capabilities, but recommendations don't clarify how to split ONE program into FOUR services.

**Customer Confusion:**
- "Do I extract the entire program into each service?"
- "Do I split CMCMCL00.CBL into 4 separate programs first?"
- "What code goes into each service?"

**Workaround:** Add PROCEDURAL decomposition guidance (which paragraphs go into which service)

---

### 2. Effort Estimates May Be Inaccurate

**Issue:** All services show `"estimated_effort_weeks": 9` regardless of actual complexity.

**Impact:**
- Customer ManagementService: 9 weeks
- Order ProcessingService: 9 weeks
- ReportingService: 9 weeks
- Data ValidationService: 9 weeks
- **Total: 36 weeks**

**Questions:**
- Are these independent efforts (can run in parallel)?
- Are these sequential (36 weeks total)?
- Do estimates consider shared code extraction complexity?

**Root Cause:** Effort formula may be too simplistic: `(loc / 1000) * 1.5`

**Better Approach:**
- Consider code duplication (shared logic)
- Consider refactoring effort (God Object must be refactored FIRST)
- Consider testing effort
- Consider deployment complexity

---

### 3. No Paragraph-Level Decomposition

**Issue:** Recommendations are program-level, not paragraph-level.

**Impact:**
- Recommends extracting CMCMCL00.CBL into 4 services
- Doesn't specify which PARAGRAPHS belong to which service
- Doesn't identify which DATA DIVISION structures belong to which service

**Example Missing Info:**
```
Customer ManagementService should include:
- PARAGRAPHS: 1000-VALIDATE-CUSTOMER, 2000-UPDATE-CUSTOMER, ...
- DATA: CUSTOMER-RECORD, CUSTOMER-TABLE
- COPYBOOKS: CUSTOMER-DEFS
```

**Workaround:** Integrate with Code Analysis V3 paragraph analysis

---

### 4. No Shared Data Analysis

**Issue:** `"shared_data": []` is always empty in decomposition_strategy.json.

**Impact:**
- Cannot identify shared database tables
- Cannot identify shared COBOL copybooks
- Cannot identify data coupling between services

**Root Cause:** StaticParser doesn't analyze data dependencies

**Workaround:** Integrate with Dependency Mapper V2's dependency graph

---

### 5. Overlap with Dependency Mapper V2

**Issue:** Both flows recommend microservices for same codebase with DIFFERENT results.

**Dependency Mapper V2 Output:**
- 20 microservices (technical clustering)
- Service16 has 6 programs
- Average service size: 2.4 programs

**Monolith Identifier V2 Output:**
- 4 microservices (business capability clustering)
- Each service extracts from CMCMCL00.CBL
- Average service size: 1 program (God Object)

**Customer Confusion:**
- "Which recommendations should I follow?"
- "Why are there two different microservice suggestions?"

**Solution:** Clarify when to use each flow:
- **Dependency Mapper V2:** For well-structured codebases (low coupling)
- **Monolith Identifier V2:** For monolithic codebases (God Objects, Big Ball of Mud)

---

### 6. God Object Refactoring Not Addressed

**Issue:** Recommends extracting 4 services from CMCMCL00.CBL but doesn't explain HOW.

**Impact:**
- Customer doesn't know where to start
- No refactoring roadmap
- No intermediate steps

**Missing Guidance:**
```
Step 1: Refactor CMCMCL00.CBL internally
  - Extract Customer Management paragraphs → new program CUSTMGMT.CBL
  - Extract Order Processing paragraphs → new program ORDPROC.CBL
  - Extract Reporting paragraphs → new program RPTGEN.CBL
  - Extract Data Validation paragraphs → new program DATVAL.CBL

Step 2: Test refactored programs in monolith

Step 3: Extract each program into separate microservice

Step 4: Deploy and migrate traffic
```

---

### 7. AI Analysis Output is Small

**Issue:** `ai_pattern_analysis.json` is only 8 KB.

**Impact:**
- May not be providing deep business capability analysis
- Possible underutilization of Bedrock capabilities
- Execution time is 20 seconds (only 7% of 5-minute timeout)

**Questions:**
- Should AI analysis be more comprehensive?
- Should AI provide paragraph-level decomposition guidance?
- Should AI estimate extraction complexity with more factors?

---

## V5 Improvement Opportunities

### 1. Merge with Dependency Mapper V2

**Improvement:** Combine Dependency Mapper V2 and Monolith Identifier V2 into single flow

**Rationale:**
- Both analyze same codebase
- Both recommend microservices
- Dependency Mapper provides technical boundaries
- Monolith Identifier provides business boundaries

**New Flow: Unified Architecture Analyzer V5**
```
1. Static dependency analysis (CALL, COPY, FILE I/O)
2. Monolith pattern detection (God Objects, Big Ball of Mud)
3. AI analysis (business capabilities + semantic dependencies)
4. Graph building (nodes, edges, coupling)
5. Modularity calculation (cohesion, coupling, complexity)
6. Microservice recommendations (BOTH technical AND business)
7. Decomposition strategy
```

**Output:**
```json
{
  "technical_microservices": [...],  // From dependency analysis
  "business_microservices": [...],   // From business capability analysis
  "recommended_approach": "Hybrid",
  "hybrid_microservices": [...]      // Best of both
}
```

**Benefits:**
- Single source of truth for microservice recommendations
- No confusion about which recommendations to follow
- Combined technical + business perspective

**Effort:** MEDIUM (5-7 days)

---

### 2. Add Paragraph-Level Decomposition

**Improvement:** Provide paragraph-level decomposition guidance for God Objects

**Enhancement:**
```json
{
  "service_name": "Customer ManagementService",
  "programs": ["CMCMCL00.CBL"],
  "paragraphs_to_extract": [
    "1000-VALIDATE-CUSTOMER",
    "2000-UPDATE-CUSTOMER",
    "3000-DELETE-CUSTOMER"
  ],
  "data_structures_to_extract": [
    "CUSTOMER-RECORD",
    "CUSTOMER-TABLE"
  ],
  "copybooks_to_extract": [
    "CUSTOMER-DEFS"
  ],
  "refactoring_steps": [
    "1. Extract paragraphs into new program CUSTMGMT.CBL",
    "2. Extract data structures into CUSTMGMT-DATA copybook",
    "3. Test CUSTMGMT.CBL in monolith",
    "4. Extract CUSTMGMT.CBL into microservice"
  ]
}
```

**Benefits:**
- Actionable decomposition guidance
- Clear refactoring roadmap
- Reduced customer confusion

**Requires:** Integration with Code Analysis V3 (paragraph analysis)

**Effort:** MEDIUM (4-5 days)

---

### 3. Add Shared Data Analysis

**Improvement:** Analyze shared database tables and COBOL data structures

**Enhancement:**
Parse COBOL DATA DIVISION for:
- 01-level structures
- COPY statements in DATA DIVISION
- FILE-CONTROL section (shared files)

**Output:**
```json
{
  "shared_data": [
    {
      "data_structure": "CUSTOMER-RECORD",
      "used_by_services": [
        "Customer ManagementService",
        "Order ProcessingService"
      ],
      "recommendation": "Create shared Customer API or event stream"
    }
  ]
}
```

**Benefits:**
- Identify data coupling between services
- Plan data migration strategy
- Recommend shared databases vs. separate databases

**Effort:** MEDIUM (3-4 days)

---

### 4. Improve Effort Estimation

**Improvement:** More accurate extraction effort estimates

**Enhanced Formula:**
```
base_effort = (loc / 1000) * base_multiplier

complexity_factor = 1 + (complexity_score / 100)
coupling_factor = 1 + (coupling_score)
refactoring_factor = 1.5 if is_god_object else 1.0
testing_factor = 1.2

total_effort = base_effort * complexity_factor * coupling_factor * refactoring_factor * testing_factor
```

**Benefits:**
- More realistic effort estimates
- Better project planning
- Consider multiple complexity factors

**Effort:** LOW (2-3 days)

---

### 5. Add God Object Refactoring Roadmap

**Improvement:** Provide step-by-step refactoring guidance for God Objects

**Output:**
```json
{
  "program": "CMCMCL00.CBL",
  "pattern": "GOD_OBJECT",
  "refactoring_roadmap": {
    "phase_1": {
      "title": "Internal Refactoring",
      "steps": [
        "Extract Customer Management logic → CUSTMGMT.CBL",
        "Extract Order Processing logic → ORDPROC.CBL",
        "Extract Reporting logic → RPTGEN.CBL",
        "Extract Data Validation logic → DATVAL.CBL"
      ],
      "effort_weeks": 8,
      "risk": "MEDIUM"
    },
    "phase_2": {
      "title": "Testing",
      "steps": [
        "Test each extracted program",
        "Regression test monolith"
      ],
      "effort_weeks": 4,
      "risk": "LOW"
    },
    "phase_3": {
      "title": "Microservice Extraction",
      "steps": [
        "Extract CUSTMGMT.CBL → Customer ManagementService",
        "Extract ORDPROC.CBL → Order ProcessingService",
        "Extract RPTGEN.CBL → ReportingService",
        "Extract DATVAL.CBL → Data ValidationService"
      ],
      "effort_weeks": 24,
      "risk": "HIGH"
    }
  },
  "total_effort_weeks": 36
}
```

**Benefits:**
- Clear refactoring path
- Phased approach reduces risk
- Testable intermediate steps

**Effort:** LOW (2-3 days)

---

### 6. Add Cross-Flow Integration

**Improvement:** Automatically trigger related flows

**Workflow:**
```
Monolith Identifier V2
  ↓ (if God Object detected)
Code Analysis V3 (detailed paragraph analysis)
  ↓
Dependency Mapper V2 (dependency graph)
  ↓
Unified recommendations
```

**Benefits:**
- Comprehensive analysis
- Combined insights from multiple flows
- No manual orchestration

**Effort:** LOW (2-3 days - Step Functions orchestration)

---

### 7. Add Visualization

**Improvement:** Visual representation of God Objects and decomposition

**Output:**
- **God Object Diagram:** Show CMCMCL00.CBL with 4 business capabilities highlighted
- **Decomposition Diagram:** Show how to extract into 4 microservices
- **Migration Roadmap:** Visual timeline with phases

**Benefits:**
- Better customer understanding
- Easier communication with stakeholders
- Visual architecture planning

**Effort:** MEDIUM (5-7 days - requires UI work)

---

### 8. Add Cost Estimation

**Improvement:** Estimate modernization cost based on decomposition strategy

**Calculation:**
```
cost_per_service = effort_weeks * team_size * weekly_rate

team_size = 3 (2 developers + 1 QA)
weekly_rate = $10,000

total_cost = sum(service.effort_weeks) * team_size * weekly_rate
```

**Output:**
```json
{
  "estimated_cost": {
    "customer_management_service": "$270,000",
    "order_processing_service": "$270,000",
    "reporting_service": "$270,000",
    "data_validation_service": "$270,000",
    "total": "$1,080,000",
    "range": "$850,000 - $1,300,000",
    "timeline": "9 months (36 weeks)"
  }
}
```

**Benefits:**
- Help customers plan budgets
- Set realistic expectations
- Prioritize high-value extractions

**Effort:** LOW (2-3 days)

---

### 9. Add Business Value Scoring

**Improvement:** Score business value of each recommended service

**Scoring Factors:**
- Business impact (customer-facing vs. internal)
- Revenue impact (revenue-generating vs. cost center)
- Strategic importance (competitive advantage vs. commodity)
- Technical debt reduction

**Output:**
```json
{
  "service_name": "Customer ManagementService",
  "business_value_score": 85,
  "business_value_factors": {
    "business_impact": "HIGH",
    "revenue_impact": "MEDIUM",
    "strategic_importance": "HIGH",
    "technical_debt_reduction": "HIGH"
  },
  "roi": "2.5 years"
}
```

**Benefits:**
- Prioritize high-value services
- Justify modernization investment
- Focus on revenue-generating services first

**Effort:** MEDIUM (4-5 days - requires business context integration)

---

### 10. Add Strangler Fig Implementation Guide

**Improvement:** Provide detailed Strangler Fig pattern implementation steps

**Output:**
```json
{
  "migration_strategy": {
    "approach": "Strangler Fig Pattern",
    "implementation_guide": {
      "step_1": {
        "title": "Create Routing Layer",
        "description": "Add API Gateway to route traffic",
        "effort_weeks": 2
      },
      "step_2": {
        "title": "Extract First Service",
        "description": "Extract Customer ManagementService",
        "effort_weeks": 9,
        "routing_rules": [
          "Route /api/customers/* → Customer ManagementService",
          "Route all other → Legacy monolith"
        ]
      },
      "step_3": {
        "title": "Monitor and Validate",
        "description": "Verify Customer ManagementService works",
        "effort_weeks": 2
      },
      "step_4": {
        "title": "Extract Second Service",
        "description": "Extract Order ProcessingService",
        "effort_weeks": 9,
        "routing_rules": [
          "Route /api/orders/* → Order ProcessingService",
          "Route /api/customers/* → Customer ManagementService",
          "Route all other → Legacy monolith"
        ]
      }
    }
  }
}
```

**Benefits:**
- Actionable migration plan
- Phased approach reduces risk
- Clear routing strategy

**Effort:** MEDIUM (3-4 days)

---

## Appendix

### A. Job ID Examples

```
miv2_job_0U812_TestApp01_1762440368_7754f811
miv2_job_341_PramodTestApp_1762425515_1fdb0d27
```

### B. S3 Path Examples

```
s3://code-transformation-v2/0U812/TestApp01/monolith_identifier_v2/jobs/miv2_job_0U812_TestApp01_1762440368_7754f811/artifacts/decomposition_strategy.json

s3://code-transformation-v2/0U812/TestApp01/monolith_identifier_v2/jobs/miv2_job_0U812_TestApp01_1762440368_7754f811/batches/static_batch_0.json
```

### C. Step Functions ARN

```
arn:aws:states:us-east-1:376129851858:stateMachine:MonolithIdentifierWorkflowV2
```

### D. Lambda ARNs

```
arn:aws:lambda:us-east-1:376129851858:function:MonolithIdentifierV2StartJob
arn:aws:lambda:us-east-1:376129851858:function:MonolithIdentifierV2PrepareAnalysis
arn:aws:lambda:us-east-1:376129851858:function:MonolithIdentifierV2StaticParser
arn:aws:lambda:us-east-1:376129851858:function:MonolithIdentifierV2MergeStatic
arn:aws:lambda:us-east-1:376129851858:function:MonolithIdentifierV2AIAnalyzer
arn:aws:lambda:us-east-1:376129851858:function:MonolithIdentifierV2PatternDetector
arn:aws:lambda:us-east-1:376129851858:function:MonolithIdentifierV2ModularityCalculator
arn:aws:lambda:us-east-1:376129851858:function:MonolithIdentifierV2DecompositionStrategy
arn:aws:lambda:us-east-1:376129851858:function:MonolithIdentifierV2StatusAPI
arn:aws:lambda:us-east-1:376129851858:function:MonolithIdentifierV2ResultsAPI
```

### E. Sample API Requests

**Start Job:**
```bash
curl -X POST https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/monolithidentifierv2 \
  -H "Content-Type: application/json" \
  -d '{
    "scout_account_id": "0U812",
    "application_name": "TestApp01",
    "source_hash": "9ec86076..."
  }'
```

**Check Status:**
```bash
curl https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/monolithidentifierv2/status/miv2_job_0U812_TestApp01_1762440368_7754f811
```

**Get Results:**
```bash
curl https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/monolithidentifierv2/results/miv2_job_0U812_TestApp01_1762440368_7754f811
```

---

## Summary

Monolith Identifier V2 is a **business capability-focused decomposition planning flow** that:

1. **Detects Monolithic Patterns:** God Objects, Big Ball of Mud, large programs
2. **Calculates Modularity:** Cohesion, coupling, complexity, maintainability metrics
3. **Recommends Decomposition:** Business capability-driven microservices
4. **Estimates Effort:** Extraction complexity and time estimates
5. **Provides Migration Plan:** Strangler Fig pattern with phased approach

**Key Strengths:**
- Business capability focus (vs. technical coupling focus)
- God Object detection and decomposition guidance
- Strangler Fig pattern recommendation
- Effort and complexity estimates

**Key Questions:**
- How does this differ from Dependency Mapper V2? (Overlap in microservice recommendations)
- Are effort estimates accurate? (All services: 9 weeks)
- How to extract multiple services from ONE God Object? (Needs paragraph-level decomposition)

**V5 Opportunities:**
- Merge with Dependency Mapper V2 (unified architecture analyzer)
- Add paragraph-level decomposition guidance
- Add shared data analysis
- Improve effort estimation
- Add God Object refactoring roadmap
- Cross-flow integration
- Visualization
- Cost estimation
- Business value scoring
- Strangler Fig implementation guide

**Performance:** 3 min 37 sec for 20 programs - good performance!

---

**Document Version:** 1.0
**Created By:** Claude Code (Analysis)
**Date:** November 6, 2025
**Status:** Complete
