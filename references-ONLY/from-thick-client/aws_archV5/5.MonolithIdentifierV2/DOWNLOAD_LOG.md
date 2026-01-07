# Monolith Identifier V2 - AWS Download Log

**Downloaded:** November 6, 2025, 2:10 PM
**Purpose:** Capture CURRENT state of Monolith Identifier V2 flow for analysis and HLD creation
**Status:** ✅ COMPLETE
**Total Files:** 22 (10 Lambdas + workflow + sample outputs)
**Total Size:** ~50 KB

---

## What Was Downloaded

### 1. Step Functions Workflow
- **Name:** MonolithIdentifierWorkflowV2
- **ARN:** `arn:aws:states:us-east-1:376129851858:stateMachine:MonolithIdentifierWorkflowV2`
- **Status:** ACTIVE
- **Created:** October 3, 2025 (estimated)
- **Files:**
  - `step_functions/MonolithIdentifierWorkflowV2.json` - Complete workflow definition

### 2. Sample Execution
- **Execution ARN:** `arn:aws:states:us-east-1:376129851858:execution:MonolithIdentifierWorkflowV2:execution-miv2_job_0U812_TestApp01_1762440368_7754f811`
- **Job ID:** `miv2_job_0U812_TestApp01_1762440368_7754f811`
- **Account:** 0U812
- **Application:** TestApp01
- **Duration:** ~3 minutes 40 seconds (08:46:09 to 08:49:46)
- **Files:**
  - `sample_outputs/execution_details.json` - Full execution details

### 3. Lambda Functions (10 total - ALL ZIP-based)

#### MonolithIdentifierV2StartJob
- **Purpose:** API Gateway handler - creates job and starts Step Functions
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `start_job_handler.lambda_handler`
- **Timeout:** 30 seconds
- **Memory:** 256 MB
- **Files:**
  - `lambda_functions/MonolithIdentifierV2StartJob/code/` - Lambda code
  - `lambda_functions/MonolithIdentifierV2StartJob/function_config.json`

#### MonolithIdentifierV2PrepareAnalysis
- **Purpose:** Prepare COBOL files for monolith analysis, create batches
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `prepare_analysis_handler.lambda_handler`
- **Timeout:** 60 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/MonolithIdentifierV2PrepareAnalysis/code/` - Lambda code
  - `lambda_functions/MonolithIdentifierV2PrepareAnalysis/function_config.json`

#### MonolithIdentifierV2StaticParser
- **Purpose:** Static parsing for monolith patterns (large programs, God objects, etc.)
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `static_parser_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/MonolithIdentifierV2StaticParser/code/` - Lambda code
  - `lambda_functions/MonolithIdentifierV2StaticParser/function_config.json`

#### MonolithIdentifierV2MergeStatic
- **Purpose:** Merge all static analysis batch results
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `merge_static_handler.lambda_handler`
- **Timeout:** 60 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/MonolithIdentifierV2MergeStatic/code/` - Lambda code
  - `lambda_functions/MonolithIdentifierV2MergeStatic/function_config.json`

#### MonolithIdentifierV2AIAnalyzer
- **Purpose:** AI-powered monolith pattern detection using Bedrock
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `ai_analyzer_handler.lambda_handler`
- **Timeout:** 300 seconds (5 minutes)
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/MonolithIdentifierV2AIAnalyzer/code/` - Lambda code
  - `lambda_functions/MonolithIdentifierV2AIAnalyzer/function_config.json`

#### MonolithIdentifierV2PatternDetector
- **Purpose:** Detect specific monolith anti-patterns (God Object, Big Ball of Mud, etc.)
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `pattern_detector_handler.lambda_handler`
- **Timeout:** 90 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/MonolithIdentifierV2PatternDetector/code/` - Lambda code
  - `lambda_functions/MonolithIdentifierV2PatternDetector/function_config.json`

#### MonolithIdentifierV2ModularityCalculator
- **Purpose:** Calculate modularity metrics (cohesion, coupling, complexity)
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `modularity_calculator_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/MonolithIdentifierV2ModularityCalculator/code/` - Lambda code
  - `lambda_functions/MonolithIdentifierV2ModularityCalculator/function_config.json`

#### MonolithIdentifierV2DecompositionStrategy
- **Purpose:** Generate decomposition strategy and microservice recommendations
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `decomposition_strategy_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/MonolithIdentifierV2DecompositionStrategy/code/` - Lambda code
  - `lambda_functions/MonolithIdentifierV2DecompositionStrategy/function_config.json`

#### MonolithIdentifierV2StatusAPI
- **Purpose:** API Gateway handler - returns job status
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `status_api_handler.lambda_handler`
- **Timeout:** 30 seconds
- **Memory:** 256 MB
- **Files:**
  - `lambda_functions/MonolithIdentifierV2StatusAPI/code/` - Lambda code
  - `lambda_functions/MonolithIdentifierV2StatusAPI/function_config.json`

#### MonolithIdentifierV2ResultsAPI
- **Purpose:** API Gateway handler - returns analysis results
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `results_api_handler.lambda_handler`
- **Timeout:** 30 seconds
- **Memory:** 256 MB
- **Files:**
  - `lambda_functions/MonolithIdentifierV2ResultsAPI/code/` - Lambda code
  - `lambda_functions/MonolithIdentifierV2ResultsAPI/function_config.json`

### 4. Sample Job Outputs (Production Run)
- **Job ID:** `miv2_job_0U812_TestApp01_1762440368_7754f811`
- **Account:** 0U812
- **Application:** TestApp01
- **Source Hash:** `9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74`
- **Files Analyzed:** 20 COBOL files in 2 batches
- **Execution Duration:** ~3 minutes 40 seconds
- **Location:** `s3://code-transformation-v2/0U812/TestApp01/monolith_identifier_v2/jobs/miv2_job_0U812_TestApp01_1762440368_7754f811/`

#### Downloaded Artifacts:

##### artifacts/ (5 files - 32 KB)
- **static_monolith_analysis.json** (11 KB) - Static monolith pattern analysis
- **ai_pattern_analysis.json** (8 KB) - AI-detected monolith patterns
- **detected_patterns.json** (1.5 KB) - List of detected anti-patterns
- **modularity_metrics.json** (6.5 KB) - Modularity scores per program
- **decomposition_strategy.json** (4.7 KB) - Decomposition recommendations

##### batches/ (2 files - 11 KB)
- **static_batch_0.json** (4 KB) - Batch 0 static analysis
- **static_batch_1.json** (6.8 KB) - Batch 1 static analysis

##### Job Metadata (3 files)
- **batch_config.json** (1.5 KB) - Batch configuration
- **job_info.json** (334 B) - Job metadata
- **status.json** (159 B) - Job status tracking

---

## Workflow Architecture (High-Level)

```
MonolithIdentifierWorkflowV2
├── CaptureStartTime (Pass)
├── UpdateStatusRunning (S3 PutObject)
│
├── PrepareAnalysis (Lambda)
│   └── Creates batches for parallel processing
│
├── StaticAnalysisMap (Map - Parallel)
│   └── StaticParser (Lambda per batch)
│       └── Detects monolith patterns (large programs, God objects)
│
├── MergeStaticAnalysis (Lambda)
│   └── Combines batch results
│
├── AIPatternAnalysis (Lambda)
│   └── Bedrock AI analysis for monolith patterns
│
├── PatternDetector (Lambda)
│   └── Detects specific anti-patterns (God Object, Big Ball of Mud, etc.)
│
├── ModularityCalculator (Lambda)
│   └── Calculates cohesion, coupling, complexity metrics
│
├── DecompositionStrategy (Lambda)
│   └── Generates decomposition recommendations
│
├── UpdateStatusCompleted (S3 PutObject)
└── Success (Succeed)
```

**Key Characteristics:**
- **Multi-phase:** Static → AI → Pattern Detection → Modularity → Decomposition
- **Batch Processing:** Files split into batches for parallel static analysis
- **AI Integration:** Bedrock Claude 3.5 Sonnet for pattern detection
- **Actionable Output:** Decomposition strategy with microservice recommendations

---

## Key Observations

### 1. All Lambdas are ZIP-based
- NOT Docker images (consistent with other V2 flows)
- Traditional ZIP deployment
- Python 3.11 runtime

### 2. Multi-Phase Analysis Pipeline
- **Phase 1:** Static parsing (detect large programs, God objects)
- **Phase 2:** AI analysis (Bedrock pattern detection)
- **Phase 3:** Pattern detection (specific anti-patterns)
- **Phase 4:** Modularity calculation (cohesion, coupling metrics)
- **Phase 5:** Decomposition strategy (microservice recommendations)

### 3. Rich Output Artifacts
- **static_monolith_analysis.json:** Static pattern analysis
- **ai_pattern_analysis.json:** AI-detected patterns
- **detected_patterns.json:** Specific anti-patterns
- **modularity_metrics.json:** Modularity scores
- **decomposition_strategy.json:** Decomposition recommendations

### 4. Sample Job Stats (20 files)
- **Batches Processed:** 2
- **Total Artifacts:** 10 files (43.8 KB)
- **Largest Artifact:** static_monolith_analysis.json (11 KB)
- **Execution Time:** ~3 minutes 40 seconds

### 5. API Integration
- **StartJob Lambda:** API Gateway → Step Functions trigger
- **StatusAPI Lambda:** Query job status
- **ResultsAPI Lambda:** Fetch analysis results

### 6. Monolith Pattern Detection
From artifact keys, this flow detects:
- God Object pattern (large programs with many responsibilities)
- Big Ball of Mud (tightly coupled spaghetti code)
- Large programs (LOC threshold)
- Low modularity (poor cohesion/coupling)

### 7. Decomposition Strategy Output
Contains:
- `migration_strategy` - How to decompose monolith
- `recommended_microservices` - Suggested service boundaries
- `refactoring_priorities` - What to refactor first

### 8. Modularity Metrics
Contains:
- `aggregate_metrics` - Overall codebase metrics
- `programs` - Per-program modularity scores

---

## S3 Storage Pattern

```
code-transformation-v2/
└── {account_id}/
    └── {application_name}/
        └── monolith_identifier_v2/
            └── jobs/
                └── {job_id}/
                    ├── job_info.json
                    ├── status.json
                    ├── batch_config.json
                    ├── batches/
                    │   ├── static_batch_0.json
                    │   └── static_batch_1.json
                    └── artifacts/
                        ├── static_monolith_analysis.json
                        ├── ai_pattern_analysis.json
                        ├── detected_patterns.json
                        ├── modularity_metrics.json
                        └── decomposition_strategy.json
```

**Job ID Pattern:**
```
miv2_job_{account}_{app}_{timestamp}_{uuid}
```

**Example:**
```
miv2_job_0U812_TestApp01_1762440368_7754f811
```

---

## API Endpoint

```
POST https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/monolithidentifierv2
```

**Request Body (expected):**
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
  "status": "started"
}
```

---

## Workflow Integration

**Inputs Required:**
```json
{
  "job_id": "miv2_job_...",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076..."
}
```

**Outputs Produced:**
- 5 analysis artifacts (monolith patterns, modularity, decomposition)
- 2 batch files (intermediate static analysis)
- 3 metadata files (job_info, status, batch_config)

---

## Next Steps

1. ✅ Download complete (10 Lambdas + workflow + sample outputs)
2. ⏳ Analyze Lambda code to understand pattern detection algorithms
3. ⏳ Understand decomposition strategy format
4. ⏳ Create detailed HLD
5. ⏳ Identify V5 improvements

---

**Downloaded from AWS Region:** us-east-1
**AWS Account:** 376129851858
**All files are READ-ONLY snapshots of deployed V2 flow**
**This is PRODUCTION V2 (serving 100+ users)**
