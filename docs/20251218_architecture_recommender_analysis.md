# Architecture Recommender V2 - Reference Analysis

**Date:** 2025-12-18
**Status:** Analysis Only
**Purpose:** Understand before building

---

## 1. Executive Summary

**Architecture Recommender V2** is the **final synthesis flow** - it consolidates outputs from 4 previous flows and generates:
- AWS architecture recommendations
- Deployable Infrastructure as Code (CDK/CloudFormation/Terraform)
- Cost estimates

**Key Insight:** This is the only flow that doesn't analyze COBOL directly - it synthesizes outputs from Discovery, Data Analysis, Code Analysis, and Code Refactor.

---

## 2. Architecture Overview

### 2.1 Pipeline Flow (4 Steps, Sequential)

```
INPUT: 4 Job IDs from previous flows
        │
        ▼
┌─────────────────────────────────────┐
│  1. LoadAllV2Reports (42s)          │ Load and consolidate 4 flow outputs
│     ↓ consolidated_input.json       │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  2. BedrockAnalyzer (3m 18s)        │ AI recommends AWS architecture
│     ↓ architecture_analysis.json    │ LONGEST STEP (Bedrock Claude)
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  3. CostEstimator (23s)             │ Calculate AWS costs using Pricing API
│     ↓ cost_estimates.json           │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  4. IaCGenerator (1m 10s)           │ Generate CDK/CloudFormation/Terraform
│     ↓ 12 IaC template files         │
└─────────────────────────────────────┘
        │
        ▼
OUTPUT: architecture_recommendations.json + iac_templates/
```

**Total Duration:** ~5.5 minutes

---

## 3. Lambda Functions (7 total)

| Lambda | Purpose | Timeout | Memory |
|--------|---------|---------|--------|
| StartJob | Validate inputs, start workflow | 60s | 256 MB |
| LoadReports | Load 4 flow outputs, consolidate | 120s | 512 MB |
| BedrockAnalyzer | AI architecture analysis | 300s | 512 MB |
| CostEstimator | AWS cost calculation | 120s | 256 MB |
| IaCGenerator | Generate CDK/CF/Terraform | 120s | 512 MB |
| StatusAPI | Get job status | 30s | 256 MB |
| ResultsAPI | Get results | 30s | 256 MB |

---

## 4. Input: 4 Previous Flow Outputs

### Required Job IDs
```json
{
  "discovery_job_id": "dv2_job_...",    // Discovery V2
  "data_job_id": "da2_job_...",          // Data Analysis V2
  "code_job_id": "ca3_job_...",          // Code Analysis V3
  "refactor_job_id": "cr2_job_..."       // Code Refactor V2
}
```

### Consolidated Input (412 KB in sample)

**From Discovery V2:**
- `ai_discovery_analysis.json`
- Business processes, ROI projections, roadmap

**From Data Analysis V2:**
- `erd.json` - Entity-Relationship Diagram
- `data_lineage.json` - Data flow tracing

**From Code Analysis V3:**
- `static_analysis.json` - Complexity, LOC, dependencies

**From Code Refactor V2:**
- `refactor_recipes.json` - Modernization opportunities

---

## 5. Output Artifacts

### 5.1 architecture_recommendations.json (Primary Output)

```json
{
  "summary": {
    "application_type": "batch_processing | transactional | event_driven | etl",
    "recommended_architecture": "serverless | containerized | hybrid",
    "confidence": 0.7,
    "key_characteristics": ["batch-oriented", "data-centric"]
  },
  "service_mappings": [
    {
      "cobol_program": "UNKNOWN",         // BUG: Should be actual program name
      "aws_service": "Lambda",
      "function_name": "BatchProcessor",
      "runtime": "java17",
      "memory_mb": 1024,
      "timeout_seconds": 900,
      "trigger": "CloudWatch Events"
    }
  ],
  "database_strategy": {
    "primary_database": "Aurora PostgreSQL",
    "instance_class": "db.t4g.medium",
    "storage_gb": 100,
    "multi_az": true,
    "migration_strategy": "AWS DMS"
  },
  "api_design": {
    "required": false,
    "api_type": "None",
    "authentication": "None"
  },
  "storage_strategy": {
    "s3_buckets": [
      {"name": "input-files", "storage_class": "S3 Standard"},
      {"name": "output-files", "storage_class": "S3 Standard"},
      {"name": "archive", "storage_class": "S3 IA"}
    ]
  },
  "security_architecture": {
    "vpc_required": true,
    "encryption_at_rest": "AWS KMS",
    "encryption_in_transit": "TLS 1.2+",
    "iam_roles_needed": ["LambdaExecutionRole", "RDSAccessRole"]
  },
  "migration_phases": [
    {
      "phase": 1,
      "name": "Data Migration",
      "duration_weeks": 4,
      "risk": "medium"
    }
  ]
}
```

### 5.2 cost_estimates.json

```json
{
  "cost_breakdown": {
    "compute": {
      "lambda": 0.0,
      "ecs": 0,
      "ec2": 0,
      "subtotal": 0.0
    },
    "database": {
      "rds": 0,
      "dynamodb": 0,
      "subtotal": 0
    },
    "storage": {
      "s3": 2.3,
      "subtotal": 2.3
    },
    "networking": {
      "data_transfer": 0.9,
      "nat_gateway": 70.2,
      "subtotal": 71.1
    },
    "other": {
      "cloudwatch": 5.0,
      "kms": 1.0,
      "subtotal": 6.0
    },
    "total_monthly_usd": 79.4,
    "total_annual_usd": 952.8
  },
  "assumptions": [
    "Costs based on us-east-1 region",
    "Lambda: 30 invocations/month per function, 1s duration",
    "Data transfer: 10GB outbound/month"
  ]
}
```

### 5.3 IaC Templates (12 files)

**CDK TypeScript (4 stacks):**
- `vpc-stack.ts` - VPC with public/private subnets, NAT gateways, flow logs
- `iam-stack.ts` - Lambda execution role, RDS access role
- `compute-stack.ts` - Lambda functions with CloudWatch triggers
- `database-stack.ts` - Aurora PostgreSQL with Multi-AZ

**CloudFormation YAML (4 stacks):** Same structure

**Terraform HCL (4 files):** Same structure

---

## 6. Code Analysis

### 6.1 LoadReports Handler

**Path:** `lambda_functions/ArchitectureRecommenderV2LoadReports/code/load_v2_reports_handler.py`

**What it does:**
1. Loads 4 files from S3:
   - Discovery: `ai_discovery_analysis.json`
   - Data Analysis: `erd.json`, `data_lineage.json`
   - Code Analysis: `static_analysis.json`
   - Refactor: `refactor_recipes.json`
2. Consolidates into single `consolidated_input.json`
3. Returns S3 location (not data - Step Functions 256KB limit)

**Good:** Handles missing files gracefully
**Issue:** No validation of content structure

### 6.2 Bedrock Analyzer Handler

**Path:** `lambda_functions/ArchitectureRecommenderV2BedrockAnalyzer/code/bedrock_architecture_analyzer_v2_handler.py`

**Prompt Structure:**
```
You are an AWS Solutions Architect analyzing a COBOL application.

## Application Overview
Programs: {count}, LOC: {total}, Complexity: {avg}

## Discovery Analysis Summary
{discovery_summary}

## Data Structure Summary
{erd_summary}

## Code Quality Summary
{code_analysis_summary}

## Refactoring Recommendations
{refactor_summary}

Provide JSON recommendations for:
- service_mappings
- database_strategy
- api_design
- storage_strategy
- security_recommendations
- migration_phases
```

**Decision Logic (from HLD):**
```
IF execution_frequency == "scheduled" AND duration < 15_min:
    → Serverless (Lambda)
ELIF execution_frequency == "continuous" AND stateful:
    → Containerized (ECS/Fargate)
ELIF complex_dependencies AND minimal_changes:
    → Lift-and-shift (EC2)
ELSE:
    → Hybrid (Lambda + ECS)
```

### 6.3 Cost Estimator Handler

**Path:** `lambda_functions/ArchitectureRecommenderV2CostEstimator/code/cost_estimator_v2_handler.py`

**Good:** Uses AWS Pricing API with fallbacks
**Issue:** Hardcoded assumptions (30 invocations/month, 10GB transfer)

**Cost Categories:**
| Category | Calculation |
|----------|-------------|
| Lambda | invocations × duration × memory × $0.0000166667/GB-sec |
| Fargate | (vCPU × $0.04048 + GB × $0.004445) × 730 hrs |
| EC2 | $0.0416/hr × 730 hrs (t3.medium) |
| RDS | $0.064/hr × 730 hrs + $0.115/GB storage |
| S3 | $0.023/GB |
| NAT Gateway | $0.045/hr × 730 + $0.045/GB processed |

### 6.4 IaC Generator Handler

**Path:** `lambda_functions/ArchitectureRecommenderV2IaCGenerator/code/iac_generator_v2_handler.py`

**What it generates:**
1. VPC Stack - 2 AZs, NAT gateways, flow logs
2. IAM Stack - Lambda/ECS execution roles
3. Compute Stack - Lambda functions with CloudWatch triggers
4. Database Stack - Aurora PostgreSQL

**Good:** Generates working CDK code
**Issue:** References non-existent application code (`lambda/batchprocessor`)

---

## 7. Issues Found

### Issue 1: Generic Service Mapping (CRITICAL)

```json
{
  "cobol_program": "UNKNOWN",  // Should be "CMCSCL50.CBL"
  "aws_service": "Lambda"
}
```

**Impact:** No traceability from COBOL program to AWS Lambda
**Fix:** Pass program list from Code Analysis, map each program explicitly

### Issue 2: Cost Assumptions Not Data-Driven

```json
{
  "assumptions": [
    "Lambda: 30 invocations/month per function"  // Where does 30 come from?
  ]
}
```

**Impact:** Cost estimates may be wildly off
**Fix:** Derive transaction volume from Discovery business processes

### Issue 3: Database Cost = $0 in Sample

```json
"database": {
  "rds": 0,
  "subtotal": 0
}
```

**Issue:** RDS is recommended but cost is $0
**Cause:** Calculation bug in reference implementation

### Issue 4: IaC References Non-Existent Code

```typescript
code: lambda.Code.fromAsset('lambda/batchprocessor')  // Folder doesn't exist
```

**Impact:** CDK deploy will fail
**Fix:** Generate skeleton application code or document as TODO

### Issue 5: No Compliance Framework

Security is generic:
```json
{
  "encryption_at_rest": "AWS KMS",
  "encryption_in_transit": "TLS 1.2+"
}
```

**Missing:** HIPAA, PCI-DSS, SOC 2 specific controls

### Issue 6: Single Environment Only

No multi-environment strategy (dev/staging/prod)

---

## 8. API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/architecture` | POST | Start architecture recommendation job |
| `/architecture/{job_id}/status` | GET | Get job status |
| `/architecture/{job_id}/results` | GET | Get all results |
| `/architecture/{job_id}/results?section=summary` | GET | Get specific section |
| `/architecture/{job_id}/results?section=iac` | GET | Get IaC templates |

### Request
```json
{
  "scout_account_id": "EVH",
  "application_name": "TestApp01",
  "discovery_job_id": "dv2_job_...",
  "data_job_id": "da2_job_...",
  "code_job_id": "ca3_job_...",
  "refactor_job_id": "cr2_job_..."
}
```

### Response
```json
{
  "job_id": "ar2_job_EVH_TestApp01_1734567890_a7b3c9d2",
  "status": "pending",
  "workflow_execution_arn": "arn:aws:states:..."
}
```

---

## 9. Relationship to Other Flows

```
┌──────────────┐
│ Discovery V2 │──────┐
└──────────────┘      │
                      │
┌──────────────┐      │
│Data Analysis │──────┼──▶ ┌─────────────────────────┐
└──────────────┘      │    │ Architecture Recommender│
                      │    │                         │
┌──────────────┐      │    │  Synthesizes 4 flows    │
│Code Analysis │──────┤    │  into AWS architecture  │
└──────────────┘      │    │  + deployable IaC       │
                      │    └─────────────────────────┘
┌──────────────┐      │
│Code Refactor │──────┘
└──────────────┘
```

---

## 10. What We Already Have vs What We Need

### Already Implemented in Our API

| Flow | Status | Our Outputs |
|------|--------|-------------|
| Discovery | Done | `roi_analysis.json`, `migration_roadmap.json`, etc. |
| Data Analysis | Done | `erd.json`, `data_lineage.json`, `copybook_analysis.json` |
| Code Analysis | Done | Via V3 flow |
| Code Refactor | Done | `refactor_recipes.json`, analysis report |

### What Architecture Recommender Needs

1. **Input Consolidation** - Load outputs from our 4 implemented flows
2. **AI Architecture Analysis** - Use Bedrock to recommend AWS services
3. **Cost Estimation** - Use AWS Pricing API (or fallback prices)
4. **IaC Generation** - Generate CDK/CloudFormation templates

---

## 11. Recommendations for Our Implementation

### 11.1 Fix Service Mapping

Map each COBOL program to specific AWS service:

```python
service_mappings = []
for program in code_analysis['programs']:
    mapping = {
        'cobol_program': program['name'],  # Actual name
        'complexity': program['complexity'],
        'aws_service': recommend_service(program),
        'function_name': sanitize_name(program['name'])
    }
    service_mappings.append(mapping)
```

### 11.2 Data-Driven Cost Assumptions

Derive from Discovery:
```python
# From Discovery business processes
high_value_processes = discovery['business_processes']['high_value']
transaction_volume = estimate_transactions(high_value_processes)

# Use for cost calculation
lambda_invocations = transaction_volume / 30  # per month
```

### 11.3 Fix Database Cost Calculation

```python
if 'PostgreSQL' in database_strategy['primary_database']:
    instance_cost = rds_price_per_hour * 730
    storage_cost = storage_gb * 0.115
    rds_cost = instance_cost + storage_cost  # Not 0!
```

### 11.4 Generate Skeleton Application Code

```java
// lambda/batchprocessor/src/main/java/com/example/BatchProcessor.java
public class BatchProcessor implements RequestHandler<...> {
    @Override
    public String handleRequest(...) {
        // TODO: Implement business logic from CMCSCL50.CBL
        // Extracted rules from Code Analysis:
        // - Rule 1: Validate customer data
        // - Rule 2: Process batch records
        return "Success";
    }
}
```

### 11.5 Multi-Scenario Cost Analysis

```json
{
  "cost_scenarios": {
    "low_usage": {"monthly": 45, "annual": 540},
    "expected_usage": {"monthly": 79, "annual": 952},
    "high_usage": {"monthly": 342, "annual": 4104}
  }
}
```

---

## 12. Files to Create

```
engines/architecture/
├── __init__.py
├── runner.py                      # Main orchestrator
├── consolidators/
│   ├── __init__.py
│   └── flow_consolidator.py       # Load and merge 4 flow outputs
├── analyzers/
│   ├── __init__.py
│   └── architecture_analyzer.py   # AI-powered recommendations
├── generators/
│   ├── __init__.py
│   ├── cost_estimator.py          # AWS cost calculation
│   └── iac_generator.py           # CDK/CloudFormation generation
└── templates/
    ├── cdk/                       # CDK TypeScript templates
    └── cloudformation/            # CloudFormation YAML templates

api/
├── models/
│   └── architecture.py            # Pydantic models
└── routes/
    └── architecture.py            # API endpoints
```

---

## 13. Summary

**What Architecture Recommender Does:**
- Consolidates 4 flow outputs (412 KB)
- Uses AI to recommend AWS architecture
- Generates deployable IaC (CDK, CloudFormation, Terraform)
- Calculates AWS costs

**Critical Issues to Fix:**
1. Service mapping shows "UNKNOWN" instead of program names
2. Cost assumptions are hardcoded (30 invocations/month)
3. Database cost calculation bug ($0)
4. IaC references non-existent application code
5. No compliance framework support
6. Single environment only

**Estimated Build Time:** Medium
- Most logic is synthesis/generation, not analysis
- Can reuse our existing flow outputs directly
- IaC templates are mostly string generation

---

## 14. Our Design Decision

**See:** `20251218_architecture_recommender_design.md` for full design.

### Key Improvements Over Reference

| Aspect | Reference | Our Design |
|--------|-----------|------------|
| Inputs | 4 flow outputs | 5 sources (+ Java code analysis) |
| Evidence | None | Every recommendation has proof |
| Confidence | Generic 0.5-0.7 | Calculated 0.85-0.95 |
| Conflicts | Ignored | Flagged as warnings |
| Alternatives | None | Primary + Alternative for each |
| Traceability | "UNKNOWN" | Java class → Lambda mapping |
| Database | Always recommends | Only if dependencies exist |
| Costs | Hardcoded assumptions | Based on actual code metrics |

### Design Approved: 2025-12-18

---

**End of Analysis**
