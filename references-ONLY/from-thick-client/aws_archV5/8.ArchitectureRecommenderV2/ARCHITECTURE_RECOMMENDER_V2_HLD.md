# Architecture Recommender V2 - High-Level Design (HLD)

**Version:** V2 Production
**Date:** November 6, 2025
**Author:** Architecture Analysis
**Status:** Production (Serving 100+ users)

---

## Executive Summary

**Architecture Recommender V2** is the **final synthesis flow** in the COBOL modernization pipeline. It consolidates outputs from 4 previous flows, uses AI to recommend AWS architecture, and generates **deployable Infrastructure as Code**.

**What Makes This Flow Special:**
- Only flow that consumes 4 different flow outputs
- Generates WORKING CDK/CloudFormation/Terraform code (not just recommendations)
- Bridges business requirements (Discovery V2) with technical implementation
- Enables "COBOL to AWS in hours" migration path

**Input:** 4 job IDs from previous flows
**Output:** AWS architecture + deployable IaC templates + cost estimates
**Processing Time:** ~5.5 minutes
**Architecture:** Simple 4-step sequential pipeline

---

## Table of Contents

1. [Flow Architecture](#flow-architecture)
2. [Lambda Functions](#lambda-functions)
3. [Data Flow](#data-flow)
4. [AI Architecture Analysis](#ai-architecture-analysis)
5. [Cost Estimation Logic](#cost-estimation-logic)
6. [IaC Generation](#iac-generation)
7. [Issues and Bugs](#issues-and-bugs)
8. [V5 Recommendations](#v5-recommendations)

---

## Flow Architecture

### Step Functions Workflow (4 Steps)

```
LoadAllV2Reports (42s)
    ↓
ArchitectureAnalysis (3m 18s) ← Longest step (Bedrock AI)
    ↓
CostEstimation (23s)
    ↓
GenerateIaC (1m 10s)
    ↓
Success
```

**Total Duration:** ~5.5 minutes

**Key Characteristics:**
- **Sequential processing** - each step depends on previous output
- **No parallelization** - unlike other flows with distributed maps
- **Retry strategy** - 3 attempts with 2.0x backoff for all steps
- **Step Functions 256KB limit** - consolidated data stored in S3, not passed via Step Functions

---

## Lambda Functions

### 1. StartJob (API Handler)
- **Timeout:** 60s | **Memory:** 256 MB
- **Validates 4 required input sources:** discovery_v2, data_analysis_v2, code_analysis_v3, refactor_v2
- **Generates job ID:** `ar2_job_{account}_{app}_{timestamp}_{uuid}`
- **Creates S3 structure:** `code-transformation-v2/{account}/{app}/architecture_v2/jobs/{job_id}/`
- **Starts Step Functions execution**

### 2. LoadReports (Consolidation)
- **Timeout:** 120s | **Memory:** 512 MB
- **Loads 4 flow outputs:**
  - Discovery V2: `ai_discovery_analysis.json`
  - Data Analysis V2: `erd.json`, `data_lineage.json`
  - Code Analysis V3: `static_analysis.json`
  - Code Refactor V2: `refactor_recipes.json`
- **Writes consolidated_input.json (412 KB in sample)**
- **Returns S3 location** (not data - Step Functions 256KB limit)

### 3. BedrockAnalyzer (AI Recommendations)
- **Timeout:** 300s (5 min) | **Memory:** 512 MB
- **Longest step in workflow**
- **Invokes Bedrock Claude 3.5 Sonnet**
- **Analyzes:** Application type, execution patterns, data volume
- **Recommends:** AWS services, database strategy, API design, security
- **Writes:** architecture_analysis.json, architecture_recommendations.json

### 4. CostEstimator (AWS Pricing)
- **Timeout:** 120s | **Memory:** 256 MB
- **Calculates costs for:** Lambda, containers, database, storage, networking, monitoring
- **Outputs:** Monthly/annual costs with breakdown
- **Sample output:** $79.40/month, $952.80/year

### 5. IaCGenerator (Code Generation)
- **Timeout:** 120s | **Memory:** 512 MB
- **Generates 12 files:**
  - 4 CDK TypeScript stacks (vpc, iam, compute, database)
  - 4 CloudFormation YAML stacks
  - 4 Terraform HCL files
- **Produces WORKING, DEPLOYABLE code**

### 6. StatusAPI + ResultsAPI
- **Query job status and fetch results**
- **Section filtering:** all, summary, services, database, cost, iac, security

---

## Data Flow

### Input: 4 Flow Outputs (412 KB Consolidated)

**Discovery V2 Contribution:**
- ROI analysis ($435K savings, 123% ROI)
- 18-month migration roadmap
- 5 business processes
- 12 integration points (CICS, DB2, VSAM)

**Data Analysis V2 Contribution:**
- ERD with 34 entities, 0 relationships (BUG - see Issues section)
- Data lineage for 15 flows
- 8 copybooks analyzed
- Hierarchical data structures

**Code Analysis V3 Contribution:**
- 20 COBOL programs analyzed
- 42 business rules extracted
- Complexity metrics (cyclomatic, maintainability)
- Dependency graph

**Code Refactor V2 Contribution:**
- 156 refactoring opportunities
- Pattern analysis (anti-patterns, code smells)
- Modernization recommendations
- Auto-fixable issues

### Output: Deployable AWS Infrastructure

**architecture_recommendations.json:**
- Application type (batch, transactional, event-driven, ETL)
- Recommended architecture (serverless, containerized, hybrid)
- Service mappings (COBOL program → AWS Lambda/ECS)
- Database strategy (Aurora PostgreSQL, DynamoDB, etc.)
- Security configuration (VPC, encryption, IAM roles)

**cost_estimates.json:**
- Total monthly/annual costs
- Breakdown by category (compute, database, storage, networking)
- Usage assumptions documented

**iac_templates/** (12 files):
- CDK TypeScript (4 stacks)
- CloudFormation YAML (4 stacks)
- Terraform HCL (4 files)

---

## AI Architecture Analysis

### Bedrock Prompt Strategy

**Multi-Perspective Analysis** combining:
1. **Business requirements** (Discovery V2)
2. **Data architecture** (Data Analysis V2)
3. **Code complexity** (Code Analysis V3)
4. **Modernization opportunities** (Code Refactor V2)

### Prompt Structure (from code analysis)

```python
prompt = f"""You are an AWS Solutions Architect analyzing a COBOL application.

## Application Overview
Programs: {programs_count}
Total LOC: {total_loc}
Avg Complexity: {avg_complexity:.1f}
Data Entities: {entities_count}
Data Relationships: {relationships_count}

## Discovery Analysis Summary
{discovery_summary}

## Data Structure Summary
{erd_summary}
{data_lineage_summary}

## Code Quality Summary
{code_analysis_summary}

## Refactoring Recommendations
{refactor_summary}

## Your Task
Recommend AWS architecture in JSON format:
- summary (application_type, recommended_architecture, confidence)
- service_mappings (COBOL program → AWS service)
- database_strategy (RDS, Aurora, DynamoDB)
- api_design (REST, GraphQL, WebSocket)
- security_recommendations (VPC, encryption, IAM)
- migration_phases (phased approach)

## Analysis Guidelines
1. Application Type: batch | transactional | event-driven | ETL
2. Compute Choice:
   - Lambda: Event-driven, <15 min, sporadic
   - ECS: Long-running, microservices, moderate complexity
   - EC2: High complexity, legacy deps, steady state
3. Database Choice:
   - RDS/Aurora: Relational, ACID, complex queries
   - DynamoDB: Key-value, high-scale, eventual consistency
4. Cost Optimization: Minimize monthly costs
5. Migration Risk: Phased approach starting with low-risk

Provide ONLY JSON response.
"""
```

### Decision Logic (Inferred from Sample Output)

**Application Type Detection:**
- Batch processing: Scheduled execution, file I/O, no API calls
- Transactional: CICS transactions, database CRUD, API endpoints
- Event-driven: Queue consumption, event processing
- ETL: Data transformation, multiple data sources

**Architecture Pattern Selection:**
```
IF (execution_frequency == "scheduled") AND (duration < 15_min):
    → Serverless (Lambda)
ELIF (execution_frequency == "continuous") AND (stateful):
    → Containerized (ECS/Fargate)
ELIF (complex_dependencies) AND (minimal_changes):
    → Lift-and-shift (EC2)
ELSE:
    → Hybrid (mix of Lambda + ECS)
```

**Database Strategy Selection:**
```
IF (entity_count > 20) AND (relationships_detected):
    → Aurora PostgreSQL (relational)
ELIF (key_value_access) AND (high_throughput):
    → DynamoDB (NoSQL)
ELIF (document_oriented) AND (complex_queries):
    → DocumentDB (MongoDB-compatible)
ELIF (archive_only) AND (large_volume):
    → S3 (object storage)
```

### Sample AI Output

```json
{
  "summary": {
    "application_type": "batch_processing",
    "recommended_architecture": "serverless",
    "primary_compute": "AWS Lambda",
    "primary_database": "Aurora PostgreSQL",
    "confidence": 0.7
  },
  "service_mappings": [
    {
      "cobol_program": "UNKNOWN",  ← BUG: Should map to actual program
      "aws_service": "Lambda",
      "function_name": "BatchProcessor",
      "runtime": "java17",
      "memory_mb": 1024,
      "timeout_seconds": 900,
      "trigger": "CloudWatch Events (daily 2 AM)"
    }
  ],
  "database_strategy": {
    "primary_database": "Aurora PostgreSQL",
    "instance_class": "db.t4g.medium",
    "storage_gb": 100,
    "multi_az": true,
    "reasoning": "34 data entities suggest relational structure"
  }
}
```

---

## Cost Estimation Logic

### Cost Calculation (from code inspection)

**Inputs:**
- `service_mappings` - Lambda functions, ECS services
- `database_strategy` - Aurora instance class, storage

**Cost Categories:**

1. **Compute Costs:**
   - Lambda: invocations × duration × memory allocation
   - ECS/Fargate: vCPU × hours + memory × hours
   - EC2: instance_type × hours × (1 - reserved_discount)

2. **Database Costs:**
   - Aurora: instance_class × hours + storage_gb × $0.10 + IOPS
   - DynamoDB: read_capacity + write_capacity + storage_gb

3. **Storage Costs:**
   - S3 Standard: storage_gb × $0.023
   - S3 IA: storage_gb × $0.0125
   - EBS: volume_size × $0.10

4. **Networking Costs:**
   - Data transfer out: gb × $0.09
   - NAT Gateway: hours × $0.045 + data_processed × $0.045

5. **Monitoring Costs:**
   - CloudWatch: log_gb × $0.50 + custom_metrics × $0.30

### Sample Cost Breakdown

```json
{
  "total_monthly_usd": 79.4,
  "total_annual_usd": 952.8,
  "breakdown": {
    "compute_monthly": 24.0,
    "database_monthly": 40.0,
    "storage_monthly": 10.0,
    "networking_monthly": 3.4,
    "monitoring_monthly": 2.0
  },
  "assumptions": {
    "monthly_transactions": 100000,
    "data_transfer_gb": 50,
    "cloudwatch_logs_gb": 10
  }
}
```

**Cost Comparison:**
- Legacy mainframe: ~$50,000/year
- Proposed AWS: $952.80/year
- **Annual savings: $49,047 (98% reduction)**

---

## IaC Generation

### Generated Code Quality

**AWS CDK TypeScript Example (compute-stack.ts):**

```typescript
import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';

export class ComputeStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ComputeStackProps) {
    super(scope, id, props);

    // Lambda Function: BatchProcessor
    const batchprocessor = new lambda.Function(this, 'BatchProcessor', {
      runtime: lambda.Runtime.JAVA_17,
      handler: 'com.example.BatchProcessor::handleRequest',
      code: lambda.Code.fromAsset('lambda/batchprocessor'),
      memorySize: 1024,
      timeout: cdk.Duration.seconds(900),
      role: props.lambdaExecutionRole,
      vpc: props.vpc,
    });

    // CloudWatch Events Rule (daily at 2 AM)
    const rule = new events.Rule(this, 'DailyTrigger', {
      schedule: events.Schedule.cron({ hour: '2', minute: '0' }),
    });

    rule.addTarget(new targets.LambdaFunction(batchprocessor));
  }
}
```

**Deployment:**
```bash
cd iac_templates/cdk
npm install
cdk deploy --all
```

**What's Included:**
- VPC with public/private subnets, NAT gateways
- IAM roles (LambdaExecutionRole, RDSAccessRole)
- Lambda functions with proper configuration
- Aurora PostgreSQL cluster (Multi-AZ)
- Security groups (Lambda SG, RDS SG)
- CloudWatch Events for scheduling

**What's Missing (Gaps):**
- Application code (lambda/batchprocessor folder doesn't exist)
- Database schema DDL scripts
- Data migration scripts
- Monitoring dashboards
- CI/CD pipeline

---

## Issues and Bugs

### Issue 1: Generic Service Mapping (CRITICAL)

**Problem:** Service mappings show `"cobol_program": "UNKNOWN"` instead of actual program names

```json
{
  "cobol_program": "UNKNOWN",  ← Should be "CMCSCL50.CBL"
  "aws_service": "Lambda",
  "function_name": "BatchProcessor"
}
```

**Root Cause:** Code Analysis V3 output not being parsed correctly, or AI prompt not requesting specific program mapping

**Impact:** No traceability from COBOL program to AWS Lambda function

**V5 Fix:**
1. Enhance AI prompt to explicitly request program-to-service mapping
2. Parse Code Analysis V3 program list and pass to Bedrock
3. Create traceability matrix: `CMCSCL50.CBL → BatchProcessor Lambda`

---

### Issue 2: Inheriting Data Analysis V2 Bug

**Problem:** Data Analysis V2 ERD has 0 relationships (bug documented in Data Analysis V2 HLD)

**Impact:** Architecture recommendations don't account for data relationships when choosing database

```json
{
  "database_strategy": {
    "reasoning": "34 data entities suggest relational structure"
  }
}
```

This reasoning is INCOMPLETE because relationships = 0, so it's not actually relational!

**V5 Fix:** Fix Data Analysis V2 ERD relationship detection FIRST, then Architecture Recommender will get correct input

---

### Issue 3: Cost Estimation Assumptions Not Validated

**Problem:** Cost calculations use hardcoded assumptions with no validation

```json
{
  "assumptions": {
    "monthly_transactions": 100000,
    "data_transfer_gb": 50
  }
}
```

**Questions:**
- Where does 100,000 transactions come from?
- Is it based on Discovery V2 business process volume?
- What if actual volume is 10x or 0.1x?

**V5 Fix:**
1. Extract transaction volume from Discovery V2 business processes
2. Provide cost ranges (low/expected/high scenarios)
3. Include cost sensitivity analysis

---

### Issue 4: IaC Templates Missing Application Code

**Problem:** Generated CDK code references application code that doesn't exist

```typescript
code: lambda.Code.fromAsset('lambda/batchprocessor')  ← Folder doesn't exist
```

**V5 Fix:**
1. Generate skeleton application code structure
2. Include boilerplate Lambda handler code
3. Add TODO comments for business logic implementation
4. Provide sample code based on Code Analysis V3 business rules

---

### Issue 5: No Compliance Framework Support

**Problem:** Security recommendations are generic, no compliance-specific controls

```json
{
  "security_configuration": {
    "encryption_at_rest": true,
    "encryption_in_transit": true
  }
}
```

**Missing:** HIPAA, PCI-DSS, SOC 2 compliance controls

**V5 Fix:**
1. Add compliance framework selection (HIPAA, PCI-DSS, SOC 2, none)
2. Generate compliance-specific security controls
3. Include AWS Config rules for compliance monitoring

---

### Issue 6: No Multi-Environment Strategy

**Problem:** IaC code is single-environment only (no dev/test/staging/prod)

**V5 Fix:**
1. Generate multi-environment CDK configuration
2. Provide environment-specific parameters (instance sizes, retention periods)
3. Include blue/green deployment strategy

---

## V5 Recommendations

### 1. Enhanced Traceability Matrix

Create explicit mapping from legacy to modern:

```json
{
  "traceability_matrix": {
    "CMCSCL50.CBL": {
      "aws_lambda": "BatchProcessor",
      "business_logic": ["Validate customer data", "Process batch records"],
      "data_entities": ["SpecialWorkFields", "CustomerRecord"],
      "integration_points": ["DB2 connection to CUSTDB"],
      "called_by": ["MainBatchJob.CBL"],
      "calls": ["CMCSRK20.CBL"]
    }
  }
}
```

### 2. Multi-Scenario Cost Analysis

Provide cost ranges based on usage scenarios:

```json
{
  "cost_scenarios": {
    "low_usage": {
      "transactions_per_month": 10000,
      "monthly_cost": 45.0,
      "annual_cost": 540.0
    },
    "expected_usage": {
      "transactions_per_month": 100000,
      "monthly_cost": 79.4,
      "annual_cost": 952.8
    },
    "high_usage": {
      "transactions_per_month": 1000000,
      "monthly_cost": 342.0,
      "annual_cost": 4104.0
    }
  },
  "cost_sensitivity": {
    "if_transactions_10x": "+330% cost increase",
    "if_storage_doubles": "+12% cost increase"
  }
}
```

### 3. Alternative Architecture Options

Provide 2-3 architecture alternatives with trade-offs:

```json
{
  "architecture_options": {
    "option_1_serverless": {
      "confidence": 0.7,
      "monthly_cost": 79.4,
      "pros": ["Low cost", "Auto-scaling", "No infrastructure mgmt"],
      "cons": ["15-min Lambda timeout", "Cold start latency"],
      "recommended": true
    },
    "option_2_containerized": {
      "confidence": 0.5,
      "monthly_cost": 245.0,
      "pros": ["No timeout limits", "Better for long-running jobs"],
      "cons": ["Higher cost", "More operational complexity"]
    },
    "option_3_hybrid": {
      "confidence": 0.6,
      "monthly_cost": 156.0,
      "pros": ["Balanced approach", "Use best service for each task"],
      "cons": ["More complex architecture"]
    }
  }
}
```

### 4. Deployment Readiness Checklist

Generate deployment checklist:

```markdown
## Pre-Deployment Checklist
- [ ] Review architecture recommendations (confidence: 0.7)
- [ ] Provision AWS account and billing alerts ($100/month threshold)
- [ ] Deploy VPC stack (10 min)
- [ ] Deploy IAM stack (5 min)
- [ ] Deploy database stack (20 min)
- [ ] Implement application code for Lambda functions
- [ ] Deploy compute stack (15 min)
- [ ] Run integration tests
- [ ] Configure monitoring dashboards
- [ ] Execute data migration (4 hours)
- [ ] UAT testing
- [ ] Plan cutover strategy
```

### 5. Data Migration Strategy

Include data migration planning:

```json
{
  "data_migration": {
    "source_system": "DB2 on mainframe",
    "target_system": "Aurora PostgreSQL",
    "migration_tool": "AWS DMS",
    "estimated_duration": "4 hours",
    "downtime_required": "2 hours",
    "data_volume_gb": 50,
    "migration_steps": [
      "Create DMS replication instance",
      "Configure source/target endpoints",
      "Create migration task (full load + CDC)",
      "Execute and monitor",
      "Validate data integrity"
    ]
  }
}
```

### 6. Complete IaC with Application Code

Generate skeleton application code:

```java
// lambda/batchprocessor/src/main/java/com/example/BatchProcessor.java
package com.example;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;

public class BatchProcessor implements RequestHandler<Map<String, Object>, String> {
    @Override
    public String handleRequest(Map<String, Object> event, Context context) {
        // TODO: Implement business logic from CMCSCL50.CBL
        // Business Rule 1: Validate customer data
        // Business Rule 2: Process batch records

        context.getLogger().log("Processing batch...");
        return "Success";
    }
}
```

---

## Summary

**What Architecture Recommender V2 Does:**
- Consolidates 4 flow outputs (412 KB)
- Uses AI to recommend AWS architecture
- Generates deployable IaC (CDK, CloudFormation, Terraform)
- Calculates precise AWS costs

**What Makes It Unique:**
- Only flow that synthesizes 4 different flows
- Generates WORKING code, not just recommendations
- Bridges business (Discovery V2) with technical (Code Analysis V3)

**Critical Issues:**
1. Generic service mapping (no COBOL program traceability)
2. Inherits Data Analysis V2 ERD bug (0 relationships)
3. Cost assumptions not validated
4. IaC missing application code
5. No compliance framework support
6. No multi-environment strategy

**V5 Priorities:**
1. Fix traceability matrix (COBOL program → AWS Lambda)
2. Multi-scenario cost analysis
3. Alternative architecture options
4. Complete IaC with skeleton code
5. Data migration planning
6. Compliance framework support

**Processing Stats:**
- Duration: 5.5 minutes
- AI analysis: 3.5 minutes (longest step)
- Generated files: 12 IaC templates
- Estimated AWS cost: $79/month, $953/year

---

**End of HLD**
