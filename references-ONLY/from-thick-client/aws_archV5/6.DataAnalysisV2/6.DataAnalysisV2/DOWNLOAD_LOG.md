# Data Analysis V2 - AWS Download Log

**Downloaded:** November 6, 2025, 2:25 PM
**Purpose:** Capture CURRENT state of Data Analysis V2 flow for analysis and HLD creation
**Status:** ✅ COMPLETE
**Total Files:** 22 (9 Lambdas + workflow + sample outputs)
**Total Size:** ~590 KB

---

## What Was Downloaded

### 1. Step Functions Workflow
- **Name:** DataAnalysisWorkflowV2
- **ARN:** `arn:aws:states:us-east-1:376129851858:stateMachine:DataAnalysisWorkflowV2`
- **Status:** ACTIVE
- **Created:** October 2025 (estimated)
- **Files:**
  - `step_functions/DataAnalysisWorkflowV2.json` - Complete workflow definition

### 2. Sample Execution
- **Execution ARN:** `arn:aws:states:us-east-1:376129851858:execution:DataAnalysisWorkflowV2:execution-da2_job_0U812_TestApp01_1762439897_08497588`
- **Job ID:** `da2_job_0U812_TestApp01_1762439897_08497588`
- **Account:** 0U812
- **Application:** TestApp01
- **Duration:** ~2 minutes 13 seconds (08:38:17 to 08:40:30)
- **Files:**
  - `sample_outputs/execution_details.json` - Full execution details

### 3. Lambda Functions (9 total - ALL ZIP-based)

#### DataAnalysisV2StartJob
- **Purpose:** API Gateway handler - creates job and starts Step Functions
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `start_data_analysis_v2_handler.lambda_handler`
- **Timeout:** 30 seconds
- **Memory:** 256 MB
- **Files:**
  - `lambda_functions/DataAnalysisV2StartJob/code/` - Lambda code
  - `lambda_functions/DataAnalysisV2StartJob/function_config.json`

#### DataAnalysisV2PrepareDataBatches
- **Purpose:** Split COBOL files into batches for parallel AI data analysis
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `prepare_data_batches_v2_handler.lambda_handler`
- **Timeout:** 60 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/DataAnalysisV2PrepareDataBatches/code/` - Lambda code
  - `lambda_functions/DataAnalysisV2PrepareDataBatches/function_config.json`

#### DataAnalysisV2RegexDataExtractor
- **Purpose:** Regex-based extraction of COBOL data structures (FDs, copybooks)
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `regex_data_extractor_v2_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/DataAnalysisV2RegexDataExtractor/code/` - Lambda code
  - `lambda_functions/DataAnalysisV2RegexDataExtractor/function_config.json`

#### DataAnalysisV2ASTDataAnalyzer
- **Purpose:** AST-based COBOL data structure parsing
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `ast_data_analyzer_v2_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/DataAnalysisV2ASTDataAnalyzer/code/` - Lambda code
  - `lambda_functions/DataAnalysisV2ASTDataAnalyzer/function_config.json`

#### DataAnalysisV2BedrockAnalyzerBatch
- **Purpose:** AI-powered data structure analysis using Bedrock (per batch)
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `bedrock_data_analyzer_batch_v2_handler.lambda_handler`
- **Timeout:** 300 seconds (5 minutes)
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/DataAnalysisV2BedrockAnalyzerBatch/code/` - Lambda code
  - `lambda_functions/DataAnalysisV2BedrockAnalyzerBatch/function_config.json`

#### DataAnalysisV2MergeDataBatches
- **Purpose:** Merge all AI data analysis batch results
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `merge_data_batches_v2_handler.lambda_handler`
- **Timeout:** 60 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/DataAnalysisV2MergeDataBatches/code/` - Lambda code
  - `lambda_functions/DataAnalysisV2MergeDataBatches/function_config.json`

#### DataAnalysisV2ERDGenerator
- **Purpose:** Generate Entity Relationship Diagram (ERD) and data lineage
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `erd_generator_v2_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/DataAnalysisV2ERDGenerator/code/` - Lambda code
  - `lambda_functions/DataAnalysisV2ERDGenerator/function_config.json`

#### DataAnalysisV2StatusAPI
- **Purpose:** API Gateway handler - returns job status
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `data_status_v2_handler.lambda_handler`
- **Timeout:** 30 seconds
- **Memory:** 256 MB
- **Files:**
  - `lambda_functions/DataAnalysisV2StatusAPI/code/` - Lambda code
  - `lambda_functions/DataAnalysisV2StatusAPI/function_config.json`

#### DataAnalysisV2ResultsAPI
- **Purpose:** API Gateway handler - returns data analysis results
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `data_results_v2_handler.lambda_handler`
- **Timeout:** 30 seconds
- **Memory:** 256 MB
- **Files:**
  - `lambda_functions/DataAnalysisV2ResultsAPI/code/` - Lambda code
  - `lambda_functions/DataAnalysisV2ResultsAPI/function_config.json`

### 4. Sample Job Outputs (Production Run)
- **Job ID:** `da2_job_0U812_TestApp01_1762439897_08497588`
- **Account:** 0U812
- **Application:** TestApp01
- **Source Hash:** `9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74`
- **Files Analyzed:** 20 COBOL files in 4 batches
- **Execution Duration:** ~2 minutes 13 seconds
- **Location:** `s3://code-transformation-v2/0U812/TestApp01/data_analysis_v2/jobs/da2_job_0U812_TestApp01_1762439897_08497588/`

#### Downloaded Artifacts:

##### artifacts/ (7 files - 484 KB)
- **data_structures.json** (150 KB) - Extracted COBOL data structures (FDs, records, fields)
- **hierarchical_structures.json** (126 KB) - Hierarchical data relationships
- **erd.json** (125 KB) - Entity Relationship Diagram
- **ai_data_analysis.json** (52 KB) - AI-powered data structure analysis
- **copybook_analysis.json** (18 KB) - Copybook field analysis
- **data_lineage.json** (13 KB) - Data lineage tracking
- **_KEEP** (0 B) - Placeholder file

##### artifacts/ai_data_analysis/ (4 files - 53 KB)
- **batch_0.json** (14 KB) - Batch 0 AI analysis
- **batch_1.json** (13 KB) - Batch 1 AI analysis
- **batch_2.json** (13 KB) - Batch 2 AI analysis
- **batch_3.json** (13 KB) - Batch 3 AI analysis

##### Job Metadata (2 files)
- **job_info.json** (599 B) - Job metadata
- **status.json** (322 B) - Job status tracking

---

## Workflow Architecture (High-Level)

```
DataAnalysisWorkflowV2
├── CaptureStartTime (Pass)
├── UpdateStatusRunning (S3 PutObject)
│
├── ParallelDataAnalysis (Parallel)
│   ├── Branch 1: RegexDataExtractor (Lambda)
│   │   └── Extracts data structures using regex patterns
│   │
│   ├── Branch 2: ASTDataAnalyzer (Lambda)
│   │   └── Parses COBOL AST for hierarchical data structures
│   │
│   └── Branch 3: AI Data Analysis Chain
│       ├── PrepareDataBatches (Lambda)
│       │   └── Creates batches for parallel AI processing
│       │
│       ├── CheckBatchCount (Choice)
│       │   └── Skip if no batches OR proceed to Map
│       │
│       ├── DataAnalyzerMap (Map - Parallel, MaxConcurrency: 40)
│       │   └── BedrockAnalyzerBatch (Lambda per batch)
│       │       └── AI analysis of data structures using Bedrock
│       │
│       └── MergeDataBatches (Lambda)
│           └── Combines all AI batch results
│
├── UpdateStatusERDGeneration (S3 PutObject)
├── ERDGenerator (Lambda)
│   └── Generates ERD and data lineage from all sources
│
├── UpdateStatusCompleted (S3 PutObject)
└── Success (Succeed)
```

**Key Characteristics:**
- **Three Parallel Branches:** Regex, AST, and AI analysis run simultaneously
- **Batch Processing:** AI analysis uses Map state with 40 concurrent executions
- **Multi-Source Synthesis:** ERD combines regex, AST, and AI results
- **Rich Output:** ERD, data lineage, hierarchical structures, copybook analysis

---

## Key Observations

### 1. All Lambdas are ZIP-based
- NOT Docker images (consistent with other V2 flows)
- Traditional ZIP deployment
- Python 3.11 runtime

### 2. Three-Pronged Data Analysis
- **Regex Extraction:** Fast, pattern-based extraction (FDs, copybooks, records)
- **AST Analysis:** Deep hierarchical structure parsing
- **AI Analysis:** Bedrock Claude 3.5 Sonnet for semantic understanding

### 3. Parallel Execution Strategy
- All 3 data analyzers run in parallel (Parallel state)
- AI batches run with MaxConcurrency: 40
- Reduces total execution time significantly

### 4. Rich Output Artifacts (7 files)
- **data_structures.json:** All extracted data structures (150 KB)
- **hierarchical_structures.json:** Parent-child relationships (126 KB)
- **erd.json:** Complete ERD with entities and relationships (125 KB)
- **ai_data_analysis.json:** AI insights on data structures (52 KB)
- **copybook_analysis.json:** Copybook field mappings (18 KB)
- **data_lineage.json:** Data flow tracking (13 KB)

### 5. Sample Job Stats (20 files)
- **Batches Processed:** 4 batches for AI analysis
- **Total Artifacts:** 13 files (537 KB)
- **Largest Artifact:** data_structures.json (150 KB)
- **Execution Time:** ~2 minutes 13 seconds (very fast!)

### 6. API Integration
- **StartJob Lambda:** API Gateway → Step Functions trigger
- **StatusAPI Lambda:** Query job status
- **ResultsAPI Lambda:** Fetch analysis results with section filtering

### 7. Data Structure Extraction
From artifact keys, this flow extracts:
- File Definitions (FD) and record layouts
- Copybook structures and field mappings
- Hierarchical data relationships (OCCURS, REDEFINES)
- Data lineage (where data flows from/to)
- Entity-Relationship Diagram (ERD)

### 8. ERD Generation
The ERD Generator synthesizes all 3 sources:
- Regex data structures (fast extraction)
- AST hierarchical structures (deep parsing)
- AI data analysis (semantic understanding)
→ Creates unified ERD with entities, attributes, relationships

---

## S3 Storage Pattern

```
code-transformation-v2/
└── {account_id}/
    └── {application_name}/
        └── data_analysis_v2/
            └── jobs/
                └── {job_id}/
                    ├── job_info.json
                    ├── status.json
                    └── artifacts/
                        ├── data_structures.json
                        ├── hierarchical_structures.json
                        ├── erd.json
                        ├── ai_data_analysis.json
                        ├── copybook_analysis.json
                        ├── data_lineage.json
                        └── ai_data_analysis/
                            ├── batch_0.json
                            ├── batch_1.json
                            ├── batch_2.json
                            └── batch_3.json
```

**Job ID Pattern:**
```
da2_job_{account}_{app}_{timestamp}_{uuid}
```

**Example:**
```
da2_job_0U812_TestApp01_1762439897_08497588
```

---

## API Endpoint

### Endpoint: /dataanalysis2

**URL:** `https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/dataanalysis2`

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
  "job_id": "da2_job_0U812_TestApp01_1762439897_08497588",
  "status": "started"
}
```

---

## Workflow Integration

**Inputs Required:**
```json
{
  "job_id": "da2_job_...",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076..."
}
```

**Outputs Produced:**
- 7 analysis artifacts (data structures, ERD, lineage, AI analysis, copybook, hierarchical)
- 4 batch files (intermediate AI analysis)
- 2 metadata files (job_info, status)

---

## Next Steps

1. ✅ Download complete (9 Lambdas + workflow + sample outputs)
2. ⏳ Analyze Lambda code to understand data extraction algorithms
3. ⏳ Understand ERD generation logic (how 3 sources are synthesized)
4. ⏳ Create detailed HLD
5. ⏳ Identify V5 improvements

---

**Downloaded from AWS Region:** us-east-1
**AWS Account:** 376129851858
**All files are READ-ONLY snapshots of deployed V2 flow**
**This is PRODUCTION V2 (serving 100+ users)**
