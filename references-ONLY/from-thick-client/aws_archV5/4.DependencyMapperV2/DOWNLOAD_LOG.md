# Dependency Mapper V2 - AWS Download Log

**Downloaded:** November 6, 2025, 1:25 PM
**Purpose:** Capture CURRENT state of Dependency Mapper V2 flow for analysis and HLD creation
**Status:** ✅ COMPLETE
**Total Files:** 24 (9 Lambdas + workflow + sample outputs)
**Total Size:** ~240 KB

---

## What Was Downloaded

### 1. Step Functions Workflow
- **Name:** DependencyMapperWorkflowV2
- **ARN:** `arn:aws:states:us-east-1:376129851858:stateMachine:DependencyMapperWorkflowV2`
- **Status:** ACTIVE
- **Created:** October 3, 2025
- **Files:**
  - `step_functions/DependencyMapperWorkflowV2.json` - Complete workflow definition

### 2. Sample Execution
- **Execution ARN:** `arn:aws:states:us-east-1:376129851858:execution:DependencyMapperWorkflowV2:execution-dmv2_job_0U812_TestApp01_1762439738_3581cb90`
- **Job ID:** `dmv2_job_0U812_TestApp01_1762439738_3581cb90`
- **Account:** 0U812
- **Application:** TestApp01
- **Duration:** 29 seconds (08:35:38 to 08:36:07)
- **Files:**
  - `sample_outputs/execution_details.json` - Full execution details

### 3. Lambda Functions (9 total - ALL ZIP-based)

#### DependencyMapperV2PrepareAnalysis
- **Purpose:** Prepare COBOL files for dependency analysis, create batches
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `prepare_analysis_v2_handler.lambda_handler`
- **Timeout:** 60 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/DependencyMapperV2PrepareAnalysis/code/` - Lambda code
  - `lambda_functions/DependencyMapperV2PrepareAnalysis/function_config.json`

#### DependencyMapperV2StaticParser
- **Purpose:** Static parsing of COBOL dependencies (CALL, COPY, FILE I/O)
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `static_parser_v2_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Code Size:** 331 lines
- **Files:**
  - `lambda_functions/DependencyMapperV2StaticParser/code/static_parser_v2_handler.py`
  - `lambda_functions/DependencyMapperV2StaticParser/function_config.json`

#### DependencyMapperV2MergeStatic
- **Purpose:** Merge all static analysis batch results
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `merge_static_v2_handler.lambda_handler`
- **Timeout:** 60 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/DependencyMapperV2MergeStatic/code/` - Lambda code
  - `lambda_functions/DependencyMapperV2MergeStatic/function_config.json`

#### DependencyMapperV2AIAnalyzer
- **Purpose:** AI-powered deep dependency analysis using Bedrock
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `ai_analyzer_v2_handler.lambda_handler`
- **Timeout:** 300 seconds (5 minutes)
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/DependencyMapperV2AIAnalyzer/code/` - Lambda code
  - `lambda_functions/DependencyMapperV2AIAnalyzer/function_config.json`

#### DependencyMapperV2GraphBuilder
- **Purpose:** Build dependency graph from static + AI analysis
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `graph_builder_v2_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Code Size:** 299 lines (approx)
- **Files:**
  - `lambda_functions/DependencyMapperV2GraphBuilder/code/graph_builder_v2_handler.py`
  - `lambda_functions/DependencyMapperV2GraphBuilder/function_config.json`

#### DependencyMapperV2CouplingCalculator
- **Purpose:** Calculate coupling metrics (fan-in, fan-out, coupling scores)
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `coupling_calculator_v2_handler.lambda_handler`
- **Timeout:** 90 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/DependencyMapperV2CouplingCalculator/code/` - Lambda code
  - `lambda_functions/DependencyMapperV2CouplingCalculator/function_config.json`

#### DependencyMapperV2RiskAssessor
- **Purpose:** Assess risk based on dependencies and complexity
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `risk_assessor_v2_handler.lambda_handler`
- **Timeout:** 90 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/DependencyMapperV2RiskAssessor/code/` - Lambda code
  - `lambda_functions/DependencyMapperV2RiskAssessor/function_config.json`

#### DependencyMapperV2MicroserviceDetector
- **Purpose:** Suggest microservice boundaries based on coupling analysis
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `microservice_detector_v2_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/DependencyMapperV2MicroserviceDetector/code/` - Lambda code
  - `lambda_functions/DependencyMapperV2MicroserviceDetector/function_config.json`

#### DependencyMapperV2ImpactAnalyzer
- **Purpose:** Calculate impact analysis for each program (blast radius)
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `impact_analyzer_v2_handler.lambda_handler`
- **Timeout:** 90 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/DependencyMapperV2ImpactAnalyzer/code/` - Lambda code
  - `lambda_functions/DependencyMapperV2ImpactAnalyzer/function_config.json`

### 4. Sample Job Outputs (Production Run)
- **Job ID:** `dmv2_job_0U812_TestApp01_1762439738_3581cb90`
- **Account:** 0U812
- **Application:** TestApp01
- **Source Hash:** `9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74`
- **Files Analyzed:** 20 COBOL files in 4 batches
- **Execution Duration:** 29 seconds
- **Location:** `s3://code-transformation-v2/0U812/TestApp01/dependency_mapper_v2/jobs/dmv2_job_0U812_TestApp01_1762439738_3581cb90/`

#### Downloaded Artifacts:

##### artifacts/ (7 files - 193.7 KB)
- **static_analysis.json** (42.3 KB) - Merged static dependency analysis
- **ai_dependency_analysis.json** (4.3 KB) - AI-generated insights
- **dependency_graph.json** (65 KB) - Complete dependency graph with nodes/edges
- **coupling_metrics.json** (9.5 KB) - Coupling scores per program
- **risk_assessment.json** (1.2 KB) - Risk analysis results
- **microservice_boundaries.json** (15.6 KB) - Suggested microservice boundaries
- **impact_analysis.json** (51.8 KB) - Impact/blast radius per program

##### temp/batch_analysis/ (4 files - 42.5 KB)
- **batch_0.json** (3.4 KB) - Static analysis batch 0 (5 files)
- **batch_1.json** (847 B) - Static analysis batch 1 (5 files)
- **batch_2.json** (3.4 KB) - Static analysis batch 2 (5 files)
- **batch_3.json** (34.9 KB) - Static analysis batch 3 (5 files - largest)

##### Job Metadata (2 files)
- **job_info.json** (449 B) - Job metadata
- **status.json** (193 B) - Job status tracking

---

## Workflow Architecture (High-Level)

```
DependencyMapperWorkflowV2
├── CaptureStartTime (Pass)
├── UpdateStatusRunning (S3 PutObject)
│
├── PrepareAnalysis (Lambda)
│   └── Creates 4 batches of 5 files each
│
├── StaticAnalysisMap (Map - MaxConcurrency: 40)
│   └── StaticParser (Lambda per batch)
│       └── Detects: CALL, COPY, FILE I/O, DATABASE
│
├── MergeStaticAnalysis (Lambda)
│   └── Combines all batch results
│
├── AIDeepAnalysis (Lambda)
│   └── Bedrock analysis for semantic dependencies
│
├── BuildDependencyGraph (Lambda)
│   └── Constructs nodes + edges graph
│
├── ParallelAnalysis (Parallel - 2 branches)
│   ├── CouplingCalculator (Lambda)
│   │   └── Calculates fan-in, fan-out, coupling scores
│   └── RiskAssessor (Lambda)
│       └── Assesses risk based on complexity
│
├── MicroserviceDetector (Lambda)
│   └── Suggests microservice boundaries
│
├── ImpactAnalyzer (Lambda)
│   └── Calculates blast radius per program
│
├── UpdateStatusCompleted (S3 PutObject)
└── Success (Succeed)
```

**Key Characteristics:**
- **Batch Processing:** Files split into batches for parallel static analysis
- **Multi-Phase:** Static → AI → Graph → Metrics → Services → Impact
- **Parallel Processing:** Coupling and Risk calculated simultaneously
- **MaxConcurrency:** 40 (high parallelism for static parsing)

---

## Key Observations

### 1. All Lambdas are ZIP-based
- NOT Docker images (unlike Code Analysis V3)
- Traditional ZIP deployment
- Python 3.11 runtime
- Single-file handlers

### 2. Multi-Phase Analysis Pipeline
- **Phase 1:** Static parsing (CALL, COPY, FILE I/O detection)
- **Phase 2:** AI analysis (semantic dependencies via Bedrock)
- **Phase 3:** Graph construction (nodes + edges)
- **Phase 4:** Parallel metrics (coupling + risk)
- **Phase 5:** Microservice detection
- **Phase 6:** Impact analysis

### 3. Rich Output Artifacts
- **dependency_graph.json:** Complete graph with nodes (programs) and edges (dependencies)
- **microservice_boundaries.json:** Suggested service boundaries with cohesion scores
- **coupling_metrics.json:** Overall and per-program coupling metrics
- **impact_analysis.json:** Blast radius / impact scores for each program
- **risk_assessment.json:** Risk classification

### 4. Sample Job Stats (20 files)
- **Batches Processed:** 4
- **Total Artifacts:** 13 files (227.4 KB)
- **Largest Artifacts:**
  - dependency_graph.json (65 KB)
  - impact_analysis.json (51.8 KB)
  - static_analysis.json (42.3 KB)
- **Execution Time:** 29 seconds

### 5. Dependency Detection Capabilities
From sample execution, StaticParser detects:
- **CALL statements:** Target program and line number
- **COPY statements:** Copybook name and line number
- **FILE I/O:** READ, WRITE, REWRITE, DELETE operations with file names
- **DATABASE:** Database operations (if any)

Example from batch 0:
- CMCSCL50.CBL has 16 COPY statements (STDPROCESS, DDS-*, etc.)
- CMCSRP00C.CBL has 1 CALL to CMCSRP00
- DICPCC00.CBL has 6 CALL statements and 6 FILE operations

### 6. Graph Structure
**Nodes:**
- id: File path
- type: "program"
- fan_in: Number of incoming dependencies
- fan_out: Number of outgoing dependencies
- lines_of_code: LOC count
- complexity_score: Complexity metric

**Edges:**
- from: Source program
- to: Target program/copybook
- type: CALL, COPY, or FILE_IO
- line_number: Where dependency occurs

### 7. Microservice Detection
Example Service:
- service_name: "Service16"
- programs: 6 programs grouped together
- internal_coupling: 0.125 (12.5%)
- external_coupling: 0.875 (87.5%)
- cohesion_score: 0.833 (83.3%)
- justification: "High internal cohesion, low external coupling"

### 8. Coupling Metrics
Overall stats for 48 programs:
- average_fan_in: 1.92
- average_fan_out: 1.92
- average_coupling: 0.022 (2.2%)
- high_coupling_count: 0
- medium_coupling_count: 1
- low_coupling_count: 47

---

## S3 Storage Pattern

```
code-transformation-v2/
└── {account_id}/
    └── {application_name}/
        └── dependency_mapper_v2/
            └── jobs/
                └── {job_id}/
                    ├── job_info.json
                    ├── status.json
                    ├── artifacts/
                    │   ├── static_analysis.json
                    │   ├── ai_dependency_analysis.json
                    │   ├── dependency_graph.json
                    │   ├── coupling_metrics.json
                    │   ├── risk_assessment.json
                    │   ├── microservice_boundaries.json
                    │   └── impact_analysis.json
                    └── temp/
                        └── batch_analysis/
                            ├── batch_0.json
                            ├── batch_1.json
                            ├── batch_2.json
                            └── batch_3.json
```

**Job ID Pattern:**
```
dmv2_job_{account}_{app}_{timestamp}_{uuid}
```

**Example:**
```
dmv2_job_0U812_TestApp01_1762439738_3581cb90
```

---

## API Endpoint

```
POST https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/dependencymapperv2
```

**Request Body:**
```json
{
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74"
}
```

---

## Workflow Integration

**Inputs Required:**
```json
{
  "job_id": "dmv2_job_...",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076..."
}
```

**Outputs Produced:**
- 7 analysis artifacts (dependency graph, microservices, coupling, impact, etc.)
- 4 temp batch files (intermediate static analysis)
- 2 metadata files (job_info, status)

---

## Next Steps

1. ✅ Download complete (9 Lambdas + workflow + sample outputs)
2. ⏳ Analyze Lambda code to understand algorithms
3. ⏳ Understand how microservice detection works
4. ⏳ Create detailed HLD
5. ⏳ Identify V5 improvements

---

**Downloaded from AWS Region:** us-east-1
**AWS Account:** 376129851858
**All files are READ-ONLY snapshots of deployed V2 flow**
**This is PRODUCTION V2 (serving 100+ users)**
