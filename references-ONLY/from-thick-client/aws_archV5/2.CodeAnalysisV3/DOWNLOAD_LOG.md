# Code Analysis V3 - AWS Download Log

**Downloaded:** November 6, 2025, 12:00 PM
**Purpose:** Capture CURRENT state of Code Analysis V3 flow for analysis and HLD creation
**Status:** ✅ COMPLETE
**Total Files:** 68
**Total Size:** 5.8 MB

---

## What Was Downloaded

### 1. Step Functions Workflow
- **Name:** CodeAnalysisWorkflowV3
- **ARN:** `arn:aws:states:us-east-1:376129851858:stateMachine:CodeAnalysisWorkflowV3`
- **Status:** ACTIVE
- **Created:** November 4, 2025
- **Files:**
  - `step_functions/CodeAnalysisWorkflowV3.json` - Complete workflow definition

### 2. Sample Execution
- **Execution ARN:** `arn:aws:states:us-east-1:376129851858:execution:CodeAnalysisWorkflowV3:api-triggered-1762447258-c754c54a`
- **Account:** 0U812
- **Application:** TestApp01
- **Files:**
  - `sample_outputs/execution_details.json` - Full execution details
  - `sample_outputs/execution_history.json` - Step-by-step execution history

### 3. Lambda Functions (4 total - ALL Docker images)

#### TreeSitterAnalyzerV3
- **Purpose:** Structural analysis of COBOL files using regex parser
- **Package Type:** Docker Image (ECR)
- **Image:** `376129851858.dkr.ecr.us-east-1.amazonaws.com/treesitter-analyzer-v3:raw-content`
- **Runtime:** Python in Docker
- **Memory:** 3008 MB
- **Timeout:** 900 seconds (15 minutes)
- **Last Modified:** November 5, 2025
- **Files:**
  - `lambda_functions/TreeSitterAnalyzerV3/code/` - Extracted code
  - `lambda_functions/TreeSitterAnalyzerV3/function_config.json`

#### PrepareBedrockMapV3
- **Purpose:** Routes files to Lambda or Fargate based on size
- **Package Type:** Docker Image (ECR)
- **Image:** `376129851858.dkr.ecr.us-east-1.amazonaws.com/prepare-bedrock-map-v3:jcl-fix`
- **Runtime:** Python in Docker
- **Files:**
  - `lambda_functions/PrepareBedrockMapV3/code/` - Extracted code
  - `lambda_functions/PrepareBedrockMapV3/function_config.json`

#### BedrockAnalyzerPerFileV3
- **Purpose:** AI analysis of small files using Bedrock
- **Package Type:** Docker Image (ECR)
- **Image:** `376129851858.dkr.ecr.us-east-1.amazonaws.com/bedrock-analyzer-per-file-v3:raw-content-lambda`
- **Runtime:** Python in Docker
- **Files:**
  - `lambda_functions/BedrockAnalyzerPerFileV3/code/` - Extracted code
  - `lambda_functions/BedrockAnalyzerPerFileV3/function_config.json`

#### SummaryGeneratorV3
- **Purpose:** Aggregates all analysis results into V2-compatible format
- **Package Type:** Docker Image (ECR)
- **Image:** `376129851858.dkr.ecr.us-east-1.amazonaws.com/summary-generator-v3:latest`
- **Runtime:** Python in Docker
- **Files:**
  - `lambda_functions/SummaryGeneratorV3/code/` - Extracted code
  - `lambda_functions/SummaryGeneratorV3/function_config.json`

### 4. Fargate Task (for large files)
- **Task Definition:** `bedrock-analyzer-fargate:6`
- **Cluster:** `code-analysis-cluster`
- **Launch Type:** FARGATE
- **Purpose:** AI analysis of large files (> 100 KB)
- **Note:** Code NOT downloaded (runs in Fargate, not Lambda)

### 5. Sample Job Outputs (Production Run)
- **Job ID:** `ca3_job_0U812_TestApp01_1762447258_c754c54a`
- **Account:** 0U812
- **Application:** TestApp01
- **Files Analyzed:** 21 files (20 COBOL + 1 CLP)
- **Location:** `s3://code-transformation-v2/0U812/TestApp01/code_analysis_v3/jobs/ca3_job_0U812_TestApp01_1762447258_c754c54a/`

#### Downloaded Artifacts:

##### ai_analyses/ (21 files)
Per-file AI analysis from Bedrock:
- CMCMCL00.CBL_ai_analysis.json (550 KB file - largest)
- ADCPSH21.CBL_ai_analysis.json
- ADCPSH21L.CBL_ai_analysis.json
- CMCSCL50.CBL_ai_analysis.json
- CMCSCL50C.CBL_ai_analysis.json
- CMCSCL50L.CBL_ai_analysis.json
- CMCSRP00C.CBL_ai_analysis.json
- CMCSRP00L.CBL_ai_analysis.json
- DATEFLIP.CBL_ai_analysis.json
- DICPCC00.CBL_ai_analysis.json
- DIPWCC00.CBL_ai_analysis.json
- DIPWCC01.CBL_ai_analysis.json
- STATUSCODE.CBL_ai_analysis.json
- UTCSC101L.CBL_ai_analysis.json
- UTCSDC00C.CBL_ai_analysis.json
- UTCSDC00L.CBL_ai_analysis.json
- UTCSUL10.CBL_ai_analysis.json
- UTCSUL10L.CBL_ai_analysis.json
- UTXSFS00.CLP_ai_analysis.json
- UTXSFS00L.CBL_ai_analysis.json
- XACSCC00L.CBL_ai_analysis.json

##### file_analyses/ (21 files)
Per-file structural analysis from TreeSitter:
- CMCMCL00.CBL.json (1 MB - largest)
- ADCPSH21.CBL.json
- ADCPSH21L.CBL.json
- CMCSCL50.CBL.json
- CMCSCL50C.CBL.json
- CMCSCL50L.CBL.json
- CMCSRP00C.CBL.json
- CMCSRP00L.CBL.json
- DATEFLIP.CBL.json
- DICPCC00.CBL.json
- DIPWCC00.CBL.json
- DIPWCC01.CBL.json
- STATUSCODE.CBL.json
- UTCSC101L.CBL.json
- UTCSDC00C.CBL.json
- UTCSDC00L.CBL.json
- UTCSUL10.CBL.json
- UTCSUL10L.CBL.json
- UTXSFS00.CLP.json
- UTXSFS00L.CBL.json
- XACSCC00L.CBL.json

##### artifacts/ (2 files)
Aggregated outputs:
- **static_analysis.json** (85 KB) - V2-compatible combined analysis
- **structural_context.json** (3.1 MB) - Complete structural context

---

## Workflow Architecture (High-Level)

```
CodeAnalysisWorkflowV3
├── TreeSitterAnalyzerV3 (Lambda)
│   └── Structural analysis of ALL files
│
├── CheckTreeSitterStatus (Choice)
│   └── Verify success before continuing
│
├── PrepareBedrockMapV3 (Lambda)
│   └── Route files: Lambda (< 100 KB) vs Fargate (> 100 KB)
│
├── CheckFilesToAnalyze (Choice)
│   └── Verify files need AI analysis
│
├── ProcessFiles (Parallel)
│   ├── LambdaMap (Map - MaxConcurrency: 10)
│   │   └── BedrockAnalyzerPerFileV3 (Lambda)
│   │       └── AI analysis of small files
│   │
│   └── FargateMap (Map - MaxConcurrency: 5)
│       └── ECS Fargate Task
│           └── AI analysis of large files
│
├── GenerateSummary (Lambda)
│   └── SummaryGeneratorV3
│       └── Aggregate results → static_analysis.json
│
└── AnalysisComplete (Pass)
    └── Workflow success
```

---

## Key Observations

### 1. ALL Lambdas are Docker Images
- NOT ZIP-based deployments
- Code stored in ECR (Elastic Container Registry)
- Downloaded using `docker pull` + `docker cp`
- Requires ECR authentication

### 2. Per-File Analysis Architecture
- Each COBOL file gets:
  - 1 structural analysis (TreeSitter)
  - 1 AI analysis (Bedrock)
- Results stored in separate folders:
  - `file_analyses/{filename}.json` (structural)
  - `ai_analyses/{filename}_ai_analysis.json` (AI)

### 3. Lambda vs Fargate Routing
- Small files (< 100 KB) → Lambda (fast, cheap)
- Large files (> 100 KB) → Fargate (more memory, longer timeout)
- Routing done by PrepareBedrockMapV3

### 4. V2 Compatibility
- SummaryGeneratorV3 creates `static_analysis.json` in V2 format
- Downstream flows (JavaGen V2/V3) expect V2 format
- This is the "bridge" between V3 analysis and V2 consumers

### 5. Sample Job Stats
- **21 files analyzed:**
  - 20 COBOL (.CBL)
  - 1 CLP (IBM i Control Language)
- **Largest file:** CMCMCL00.CBL (550 KB)
- **Total artifacts:** 4.4 MB

---

## S3 Storage Pattern

```
code-transformation-v2/
└── {account_id}/
    └── {application_name}/
        └── code_analysis_v3/
            └── jobs/
                └── {job_id}/
                    ├── ai_analyses/
                    │   └── {filename}_ai_analysis.json
                    ├── file_analyses/
                    │   └── {filename}.json
                    └── artifacts/
                        ├── static_analysis.json
                        └── structural_context.json
```

**Job ID Pattern:**
```
ca3_job_{account}_{app}_{timestamp}_{uuid}
```

**Example:**
```
ca3_job_0U812_TestApp01_1762447258_c754c54a
```

---

## API Endpoint

```
POST https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/codeanalysis3
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

## Next Steps

1. ✅ Download complete (4 Lambdas + sample outputs)
2. ⏳ Read Lambda code to understand logic
3. ⏳ Analyze sample outputs to see data structure
4. ⏳ Identify the business logic extraction gap
5. ⏳ Create detailed HLD
6. ⏳ Document V5 improvements

---

**Downloaded from AWS Region:** us-east-1
**AWS Account:** 376129851858
**All files are READ-ONLY snapshots of deployed V3 flow**
**This is the CURRENT production V3 (deployed Nov 5, 2025)**
