# Code Refactor V2 - AWS Download Log

**Downloaded:** November 6, 2025, 12:15 PM
**Purpose:** Capture CURRENT state of Code Refactor V2 flow for analysis and HLD creation
**Status:** ✅ COMPLETE
**Total Files:** 26
**Total Size:** 588 KB

---

## What Was Downloaded

### 1. Step Functions Workflow
- **Name:** CodeRefactorWorkflowV2
- **ARN:** `arn:aws:states:us-east-1:376129851858:stateMachine:CodeRefactorWorkflowV2`
- **Status:** ACTIVE
- **Created:** October 2, 2025
- **Files:**
  - `step_functions/CodeRefactorWorkflowV2.json` - Complete workflow definition

### 2. Sample Execution
- **Execution ARN:** `arn:aws:states:us-east-1:376129851858:execution:CodeRefactorWorkflowV2:execution-rf2_job_0U812_TestApp01_1762439638_48cf051e`
- **Job ID:** `rf2_job_0U812_TestApp01_1762439638_48cf051e`
- **Account:** 0U812
- **Application:** TestApp01
- **Files:**
  - `sample_outputs/execution_details.json` - Full execution details
  - `sample_outputs/execution_history.json` - Step-by-step execution history

### 3. Lambda Functions (6 total - ALL ZIP-based)

#### RefactorV2RegexPatternDetector
- **Purpose:** Detect refactoring patterns using regex
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Files:**
  - `lambda_functions/RefactorV2RegexPatternDetector/code/` - Lambda code
  - `lambda_functions/RefactorV2RegexPatternDetector/function_config.json`

#### RefactorV2ASTPatternDetector
- **Purpose:** Detect refactoring patterns using AST analysis
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Files:**
  - `lambda_functions/RefactorV2ASTPatternDetector/code/` - Lambda code
  - `lambda_functions/RefactorV2ASTPatternDetector/function_config.json`

#### RefactorV2PrepareRefactorBatches
- **Purpose:** Split files into batches for AI analysis
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Files:**
  - `lambda_functions/RefactorV2PrepareRefactorBatches/code/` - Lambda code
  - `lambda_functions/RefactorV2PrepareRefactorBatches/function_config.json`

#### RefactorV2BedrockAnalyzerBatch
- **Purpose:** AI-powered pattern detection per batch using Bedrock
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Files:**
  - `lambda_functions/RefactorV2BedrockAnalyzerBatch/code/` - Lambda code
  - `lambda_functions/RefactorV2BedrockAnalyzerBatch/function_config.json`

#### RefactorV2MergeRefactorBatches
- **Purpose:** Merge all AI pattern batch results
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Files:**
  - `lambda_functions/RefactorV2MergeRefactorBatches/code/` - Lambda code
  - `lambda_functions/RefactorV2MergeRefactorBatches/function_config.json`

#### RefactorV2RecipeGenerator
- **Purpose:** Generate refactoring recipes from all pattern sources
- **Package Type:** ZIP
- **Runtime:** Python 3.11
- **Files:**
  - `lambda_functions/RefactorV2RecipeGenerator/code/` - Lambda code
  - `lambda_functions/RefactorV2RecipeGenerator/function_config.json`

### 4. Sample Job Outputs (Production Run)
- **Job ID:** `rf2_job_0U812_TestApp01_1762439638_48cf051e`
- **Account:** 0U812
- **Application:** TestApp01
- **Location:** `s3://code-transformation-v2/0U812/TestApp01/code_refactor_v2/jobs/rf2_job_0U812_TestApp01_1762439638_48cf051e/`

#### Downloaded Artifacts:

##### artifacts/ (6 files + 5 batch files)
- **regex_patterns.json** (171 KB) - Patterns detected by regex
- **ast_patterns.json** (175 KB) - Patterns detected by AST analysis
- **ai_patterns.json** (8 KB) - Merged AI pattern results
- **refactor_recipes.json** (49 KB) - Generated refactoring recipes
- **ai_patterns/batch_0.json** (1.5 KB) - AI batch 0 results
- **ai_patterns/batch_1.json** (1.8 KB) - AI batch 1 results
- **ai_patterns/batch_2.json** (1.8 KB) - AI batch 2 results
- **ai_patterns/batch_3.json** (594 B) - AI batch 3 results
- **_KEEP** (marker file)

##### Job Metadata (2 files)
- **job_info.json** - Job metadata
- **status.json** - Job status tracking

---

## Workflow Architecture (High-Level)

```
CodeRefactorWorkflowV2
├── CaptureStartTime (Pass)
├── UpdateStatusRunning (S3 PutObject)
│
├── ParallelPatternDetection (Parallel - 3 branches)
│   ├── Branch 1: RegexPatternDetector (Lambda)
│   ├── Branch 2: ASTPatternDetector (Lambda)
│   └── Branch 3: AI Pattern Detection
│       ├── PrepareRefactorBatches (Lambda)
│       ├── RefactorAnalyzerMap (Map - MaxConcurrency: 40)
│       │   └── BedrockAnalyzerBatch (Lambda per batch)
│       └── MergeRefactorBatches (Lambda)
│
├── RecipeGenerator (Lambda)
├── UpdateStatusCompleted (S3 PutObject)
└── Success (Succeed)
```

---

## Key Observations

### 1. All Lambdas are ZIP-based
- NOT Docker images (unlike Code Analysis V3)
- Traditional ZIP deployment
- Python 3.11 runtime

### 2. Parallel Pattern Detection
- 3 detection methods run simultaneously:
  - Regex (fast, simple patterns)
  - AST (structural patterns)
  - AI (semantic patterns via Bedrock)
- Results merged into single recipe

### 3. Batch Processing for AI
- Files split into batches
- 4 batches processed in sample execution
- MaxConcurrency: 40 (high parallelism)
- Each batch analyzed by Bedrock

### 4. Sample Job Stats
- **Batches Processed:** 4
- **Total Artifacts:** 11 files (347 KB)
- **Largest Artifacts:**
  - ast_patterns.json (175 KB)
  - regex_patterns.json (171 KB)

---

## S3 Storage Pattern

```
code-transformation-v2/
└── {account_id}/
    └── {application_name}/
        └── code_refactor_v2/
            └── jobs/
                └── {job_id}/
                    ├── job_info.json
                    ├── status.json
                    └── artifacts/
                        ├── regex_patterns.json
                        ├── ast_patterns.json
                        ├── ai_patterns.json
                        ├── refactor_recipes.json
                        └── ai_patterns/
                            ├── batch_0.json
                            ├── batch_1.json
                            ├── batch_2.json
                            └── batch_3.json
```

**Job ID Pattern:**
```
rf2_job_{account}_{app}_{timestamp}_{uuid}
```

**Example:**
```
rf2_job_0U812_TestApp01_1762439638_48cf051e
```

---

## API Endpoint

```
POST https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/coderefactor2
```

**Request Body (expected):**
```json
{
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74"
}
```

---

## Next Steps

1. ✅ Download complete (6 Lambdas + sample outputs)
2. ⏳ Analyze Lambda code to understand pattern detection
3. ⏳ Understand refactoring recipes format
4. ⏳ Create detailed HLD
5. ⏳ Identify V5 improvements

---

**Downloaded from AWS Region:** us-east-1
**AWS Account:** 376129851858
**All files are READ-ONLY snapshots of deployed V2 flow**
**This is PRODUCTION V2 (serving 100+ users)**
