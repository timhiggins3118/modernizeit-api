# Discovery V2 - AWS Download Log

**Downloaded:** November 6, 2025, 2:45 PM
**Purpose:** Capture CURRENT state of Discovery V2 flow for analysis and HLD creation
**Status:** ✅ COMPLETE
**Total Files:** 23 (11 Lambdas + workflow + sample outputs)
**Total Size:** ~220 KB

---

## What Was Downloaded

### 1. Step Functions Workflow
- **Name:** DiscoveryWorkflowV2
- **ARN:** `arn:aws:states:us-east-1:376129851858:stateMachine:DiscoveryWorkflowV2`
- **Status:** ACTIVE
- **Created:** October 2025 (estimated)
- **Files:**
  - `step_functions/DiscoveryWorkflowV2.json` - Complete workflow definition

### 2. Sample Execution
- **Execution ARN:** `arn:aws:states:us-east-1:376129851858:execution:DiscoveryWorkflowV2:execution-dv2_job_0U812_TestApp01_1762440076_890f28c3`
- **Job ID:** `dv2_job_0U812_TestApp01_1762440076_890f28c3`
- **Account:** 0U812
- **Application:** TestApp01
- **Duration:** ~2 minutes 16 seconds (08:41:16 to 08:43:32)
- **Files:**
  - `sample_outputs/execution_details.json` - Full execution details

### 3. Lambda Functions (11 total - ALL ZIP-based)

#### DiscoveryV2StartJob
- **Purpose:** API Gateway handler - creates discovery job and starts Step Functions
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `start_discovery_v2_handler.lambda_handler`
- **Timeout:** 30 seconds
- **Memory:** 256 MB
- **Files:**
  - `lambda_functions/DiscoveryV2StartJob/code/` - Lambda code
  - `lambda_functions/DiscoveryV2StartJob/function_config.json`

#### DiscoveryV2PrepareDiscoveryBatches
- **Purpose:** Split COBOL files into batches for parallel AI discovery analysis
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `prepare_discovery_batches_v2_handler.lambda_handler`
- **Timeout:** 60 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/DiscoveryV2PrepareDiscoveryBatches/code/` - Lambda code
  - `lambda_functions/DiscoveryV2PrepareDiscoveryBatches/function_config.json`

#### DiscoveryV2BedrockAnalyzerBatch
- **Purpose:** AI-powered discovery analysis per batch using COBOLDiscoveryAnalystV2 agent
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `bedrock_discovery_analyzer_batch_v2_handler.lambda_handler`
- **Timeout:** 300 seconds (5 minutes)
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/DiscoveryV2BedrockAnalyzerBatch/code/` - Lambda code
  - `lambda_functions/DiscoveryV2BedrockAnalyzerBatch/function_config.json`

#### DiscoveryV2MergeDiscoveryBatches
- **Purpose:** Merge all AI batch results into single discovery analysis file
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `merge_discovery_batches_v2_handler.lambda_handler`
- **Timeout:** 60 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/DiscoveryV2MergeDiscoveryBatches/code/` - Lambda code
  - `lambda_functions/DiscoveryV2MergeDiscoveryBatches/function_config.json`

#### DiscoveryV2BusinessProcessExtractor
- **Purpose:** Extract and group business processes from AI analysis
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `business_process_extractor_v2_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/DiscoveryV2BusinessProcessExtractor/code/` - Lambda code
  - `lambda_functions/DiscoveryV2BusinessProcessExtractor/function_config.json`

#### DiscoveryV2IntegrationDetector
- **Purpose:** Detect integration points (CICS, DB2, VSAM, external systems)
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `integration_detector_v2_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/DiscoveryV2IntegrationDetector/code/` - Lambda code
  - `lambda_functions/DiscoveryV2IntegrationDetector/function_config.json`

#### DiscoveryV2APIPatternAnalyzer
- **Purpose:** Analyze API patterns and recommend AWS architectures
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `api_pattern_analyzer_v2_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/DiscoveryV2APIPatternAnalyzer/code/` - Lambda code
  - `lambda_functions/DiscoveryV2APIPatternAnalyzer/function_config.json`

#### DiscoveryV2ROICalculator
- **Purpose:** Calculate ROI, cost savings, payback period
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `roi_calculator_v2_handler.lambda_handler`
- **Timeout:** 60 seconds
- **Memory:** 512 MB
- **Files:**
  - `lambda_functions/DiscoveryV2ROICalculator/code/` - Lambda code
  - `lambda_functions/DiscoveryV2ROICalculator/function_config.json`

#### DiscoveryV2RoadmapGenerator
- **Purpose:** Generate phased migration roadmap (18-month plan)
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `roadmap_generator_v2_handler.lambda_handler`
- **Timeout:** 120 seconds
- **Memory:** 1024 MB
- **Files:**
  - `lambda_functions/DiscoveryV2RoadmapGenerator/code/` - Lambda code
  - `lambda_functions/DiscoveryV2RoadmapGenerator/function_config.json`

#### DiscoveryV2StatusAPI
- **Purpose:** API Gateway handler - returns discovery job status
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `discovery_status_v2_handler.lambda_handler`
- **Timeout:** 30 seconds
- **Memory:** 256 MB
- **Files:**
  - `lambda_functions/DiscoveryV2StatusAPI/code/` - Lambda code
  - `lambda_functions/DiscoveryV2StatusAPI/function_config.json`

#### DiscoveryV2ResultsAPI
- **Purpose:** API Gateway handler - returns discovery results with section filtering
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Handler:** `discovery_results_v2_handler.lambda_handler`
- **Timeout:** 30 seconds
- **Memory:** 256 MB
- **Files:**
  - `lambda_functions/DiscoveryV2ResultsAPI/code/` - Lambda code
  - `lambda_functions/DiscoveryV2ResultsAPI/function_config.json`

### 4. Sample Job Outputs (Production Run)
- **Job ID:** `dv2_job_0U812_TestApp01_1762440076_890f28c3`
- **Account:** 0U812
- **Application:** TestApp01
- **Source Hash:** `9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74`
- **Files Analyzed:** 20 COBOL files in 4 batches
- **Execution Duration:** ~2 minutes 16 seconds
- **Location:** `s3://code-transformation-v2/0U812/TestApp01/discovery_v2/jobs/dv2_job_0U812_TestApp01_1762440076_890f28c3/`

#### Downloaded Artifacts:

##### artifacts/ (10 files - 193 KB)
- **ai_discovery_analysis.json** (82 KB) - Merged AI discovery analysis (all batches)
- **business_processes.json** (8 KB) - Business process extraction (5 processes identified)
- **integration_points.json** (9 KB) - Integration point detection (CICS, DB2, VSAM)
- **api_patterns.json** (6 KB) - API pattern analysis and AWS recommendations
- **migration_roadmap.json** (8 KB) - 18-month phased migration plan
- **roi_analysis.json** (1.5 KB) - ROI calculation ($435K savings, 123% ROI)

##### artifacts/ai_discovery_analysis/ (4 files - 82 KB)
- **batch_0.json** (21 KB) - Batch 0 AI discovery analysis (5 files)
- **batch_1.json** (20 KB) - Batch 1 AI discovery analysis (5 files)
- **batch_2.json** (20 KB) - Batch 2 AI discovery analysis (5 files)
- **batch_3.json** (20 KB) - Batch 3 AI discovery analysis (5 files)

##### Job Metadata (2 files)
- **job_info.json** (493 B) - Job metadata
- **status.json** (192 B) - Job status tracking

---

## Workflow Architecture (High-Level)

```
DiscoveryWorkflowV2
├── CaptureStartTime (Pass)
├── UpdateStatusRunning (S3 PutObject)
│
├── PrepareDiscoveryBatches (Lambda)
│   └── Splits COBOL files into batches (batch size: 5 files)
│
├── CheckBatchCount (Choice)
│   └── Fail if no batches OR proceed to Map
│
├── DiscoveryAnalyzerMap (Map - DISTRIBUTED, MaxConcurrency: 40)
│   └── BedrockAnalyzerBatch (Lambda per batch)
│       └── AI discovery analysis using COBOLDiscoveryAnalystV2
│
├── MergeDiscoveryBatches (Lambda)
│   └── Merges all AI batch results
│
├── ParallelEnrichment (Parallel - 3 branches)
│   ├── Branch 1: BusinessProcessExtractor (Lambda)
│   │   └── Groups files into business processes
│   │
│   ├── Branch 2: IntegrationDetector (Lambda)
│   │   └── Identifies integration points (CICS, DB2, VSAM)
│   │
│   └── Branch 3: APIPatternAnalyzer (Lambda)
│       └── Analyzes API patterns and recommends AWS services
│
├── ROICalculator (Lambda)
│   └── Calculates ROI, cost savings, payback period
│
├── RoadmapGenerator (Lambda)
│   └── Generates phased migration roadmap
│
├── UpdateStatusCompleted (S3 PutObject)
└── Success (Succeed)
```

**Key Characteristics:**
- **Distributed Map:** Uses DISTRIBUTED mode for batch processing (not INLINE)
- **Parallel Enrichment:** 3 lambdas run simultaneously after AI merge
- **Sequential Business Logic:** ROI → Roadmap (roadmap depends on ROI)
- **Executive Output:** ROI analysis + migration plan = business case for C-suite

---

## Key Observations

### 1. All Lambdas are ZIP-based
- NOT Docker images (consistent with other V2 flows)
- Traditional ZIP deployment
- Python 3.11 runtime

### 2. AI Analysis is VERY Comprehensive
Each COBOL file gets analyzed across 6 dimensions:
1. **Business Processes** (25%) - Business value, complexity, execution frequency, confidence score
2. **Integration Points** (25%) - Database, transaction managers, messaging systems, file systems, external APIs
3. **API Pattern Analysis** (20%) - Execution pattern, recommended AWS architecture
4. **Data Flow Mapping** (15%) - Input sources, processing logic, output destinations
5. **External Dependencies** (10%) - Copybooks, called programs, required data files, database tables
6. **Modernization Insights** (5%) - Cloud readiness score, decoupling opportunities, microservices potential, technology replacements

### 3. Bedrock Agent: COBOLDiscoveryAnalystV2
- **Agent ID:** (Need to check Lambda code for exact ID)
- **Model:** anthropic.claude-3-5-sonnet-20240620-v1:0
- **Prompt:** Highly structured prompt asking for 6 specific analysis categories with percentage weights

### 4. Business Process Extraction
From sample data, identified **5 business processes:**
1. **General Business Logic** (7 programs, 10 capabilities) - Medium value, 95 cloud readiness
2. **Data Processing** (5 programs, 10 capabilities) - Medium value, 90 cloud readiness
3. **Financial Services** (2 programs, 6 capabilities) - Medium value, 85 cloud readiness
4. **Claims Processing** (4 programs, 12 capabilities) - High value
5. **Reporting** (2 programs, 8 capabilities) - Low value

### 5. Integration Point Detection
From sample data, detected **multiple integration points:**
- **CICS** (Transaction Manager) - 4 instances detected
- **DB2** (Database) - 5 instances detected
- **VSAM** (File System) - 2 instances detected
- **AWS Recommendations:** S3, RDS, Lambda, API Gateway, Step Functions

### 6. ROI Calculation (VERY DETAILED)
**Summary:**
- **Total 5-Year Savings:** $435,000
- **ROI:** 123.1%
- **Payback Period:** 7.7 months
- **Total Investment:** $195,000

**Breakdown:**
- **Development Cost Savings:** $80,000 (80% reduction using AI)
  - Traditional: $100K, AI-accelerated: $20K
- **Time Savings:** 80 days (4 months faster)
  - Traditional: 100 days, AI-accelerated: 20 days, 80% improvement
- **Infrastructure Savings:** $75,000 over 5 years ($15K/year)
  - Legacy: $50K/year, AWS: $35K/year, 30% reduction
- **Maintenance Savings:** $80,000 over 5 years ($16K/year)
  - Legacy: $40K/year, Modern: $24K/year, 40% reduction
- **Risk Reduction Value:** $200,000 (mainframe dependency, vendor lock-in, skills shortage)

### 7. Migration Roadmap (18-Month Phased Plan)
**Strategy:** Strangler Fig Pattern (incremental replacement)
**Total Cost:** $640,000
**Duration:** 18 months

**Phases:**
1. **Phase 1:** Foundation (CI/CD, Monitoring) - Months 1-3
2. **Phase 2:** Database Migration (DB2 → RDS) - Months 4-7
3. **Phase 3:** Application Modernization - Months 8-13
4. **Phase 4:** Integration Layer Modernization - Months 14-16
5. **Phase 5:** Final Cutover & Decommission - Months 17-18

Each phase includes:
- Components to migrate
- Modernization approach (Lambda, ECS, RDS, S3)
- Rationale
- Estimated effort (weeks)
- Estimated cost ($)
- Deliverables
- Success criteria
- Dependencies
- Risks with mitigations

### 8. Sample Job Stats (20 files)
- **Batches Processed:** 4 batches for AI discovery analysis
- **Total Artifacts:** 12 files (193 KB)
- **Largest Artifact:** ai_discovery_analysis.json (82 KB)
- **Execution Time:** ~2 minutes 16 seconds (very fast!)

### 9. API Integration
- **StartJob Lambda:** API Gateway → Step Functions trigger
- **StatusAPI Lambda:** Query job status with progress tracking (0-100%)
- **ResultsAPI Lambda:** Fetch discovery results with section filtering

### 10. Output Artifacts Summary
| Artifact | Size | Purpose |
|----------|------|---------|
| ai_discovery_analysis.json | 82 KB | Comprehensive AI analysis (merged) |
| business_processes.json | 8 KB | Business process grouping |
| integration_points.json | 9 KB | Integration point detection |
| api_patterns.json | 6 KB | API pattern recommendations |
| migration_roadmap.json | 8 KB | 18-month phased plan |
| roi_analysis.json | 1.5 KB | ROI calculation |
| batch_*.json | 82 KB | AI batch results (intermediate) |

### 11. Unique Features (vs Other Flows)
**Discovery V2 is COMPLETELY DIFFERENT from technical flows:**
- **Target Audience:** C-suite executives, business leaders, project sponsors
- **Purpose:** Make business case for modernization
- **Output:** ROI analysis, migration roadmap, business process inventory
- **Focus:** Strategic planning, not technical implementation
- **Value Prop:** Answers "Should we modernize?" and "How much will it cost/save?"

**Other flows (Code Analysis, Refactor, Data Analysis):**
- **Target Audience:** Developers, architects, technical leads
- **Purpose:** Technical implementation of modernization
- **Output:** Code, ERDs, refactor recipes, dependencies
- **Focus:** Technical execution
- **Value Prop:** Answers "How do we modernize?" and "What does the code do?"

---

## S3 Storage Pattern

```
code-transformation-v2/
└── {account_id}/
    └── {application_name}/
        ├── shared/
        │   └── uploads/{source_hash}/
        │       └── extracted/          # COBOL source files (INPUT)
        │
        └── discovery_v2/
            └── jobs/
                └── {job_id}/
                    ├── job_info.json
                    ├── status.json
                    └── artifacts/
                        ├── ai_discovery_analysis.json     # AI merged (82 KB)
                        ├── business_processes.json        # Business processes (8 KB)
                        ├── integration_points.json        # Integrations (9 KB)
                        ├── api_patterns.json              # API patterns (6 KB)
                        ├── migration_roadmap.json         # Roadmap (8 KB)
                        ├── roi_analysis.json              # ROI (1.5 KB)
                        └── ai_discovery_analysis/
                            ├── batch_0.json               # AI batch (21 KB)
                            ├── batch_1.json               # AI batch (20 KB)
                            ├── batch_2.json               # AI batch (20 KB)
                            └── batch_3.json               # AI batch (20 KB)
```

### Job ID Format
```
dv2_job_{scout_account_id}_{application_name}_{timestamp}_{uuid}
```

**Example:**
```
dv2_job_0U812_TestApp01_1762440076_890f28c3
```

**Components:**
- `dv2_job_` - Prefix (Discovery V2)
- `0U812` - Scout account ID
- `TestApp01` - Application name
- `1762440076` - Unix timestamp
- `890f28c3` - Short UUID (8 characters)

---

## API Endpoint

### Endpoint: /discovery2

**URL:** `https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/discovery2`

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
  "job_id": "dv2_job_0U812_TestApp01_1762440076_890f28c3",
  "status": "started"
}
```

---

## Next Steps

1. ✅ Download complete (11 Lambdas + workflow + sample outputs)
2. ⏳ Analyze Lambda code to understand discovery algorithms
3. ⏳ Understand ROI calculation methodology
4. ⏳ Understand roadmap generation logic
5. ⏳ Create detailed HLD
6. ⏳ Identify V5 improvements

---

**Downloaded from AWS Region:** us-east-1
**AWS Account:** 376129851858
**All files are READ-ONLY snapshots of deployed V2 flow**
**This is PRODUCTION V2 (serving 100+ users)**
