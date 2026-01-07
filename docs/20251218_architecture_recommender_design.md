# Architecture Recommender - Our Design

**Date:** 2025-12-18
**Status:** Design Approved
**Purpose:** Evidence-based AWS architecture recommendations

---

## 1. Key Improvement Over Reference

**Reference:** Recommends infrastructure without looking at actual code
**Ours:** Analyzes generated Java + cross-validates with all sources = evidence-based recommendations

---

## 2. Input Sources (5 Total)

| Source | What We Get | Location |
|--------|-------------|----------|
| Discovery | Business processes, ROI, integration points | `discovery/` output |
| Data Analysis | ERD, relationships, data lineage | `data_analysis/` output |
| Code Analysis | COBOL complexity, static analysis | `code_analysis/` output |
| Code Refactor | Modernization patterns, recipes | `code_refactor/` output |
| **Java Code** | Generated Java from Code Analysis | `code_analysis/generated/` |

---

## 3. Java Code Analysis

### 3.1 What We Scan

**Dependencies (pom.xml / build.gradle):**
```python
DEPENDENCY_PATTERNS = {
    'database': {
        'postgresql': 'Aurora PostgreSQL',
        'mysql': 'Aurora MySQL',
        'oracle': 'RDS Oracle',
        'h2': 'In-memory only (dev)',
        'spring-data-jpa': 'JPA detected',
        'spring-data-jdbc': 'JDBC detected',
    },
    'web': {
        'spring-boot-starter-web': 'REST API',
        'spring-webflux': 'Reactive API',
    },
    'messaging': {
        'spring-cloud-aws-sqs': 'SQS integration',
        'spring-kafka': 'MSK/Kafka',
        'spring-jms': 'MQ migration needed',
    },
    'aws': {
        'aws-sdk': 'AWS SDK present',
        'aws-lambda-java': 'Lambda-ready',
    }
}
```

**Annotations:**
```python
ANNOTATION_PATTERNS = {
    '@RestController': 'REST endpoints → API Gateway',
    '@Controller': 'Web MVC → ECS/Fargate',
    '@Entity': 'JPA entities → Database required',
    '@Repository': 'Data access → Database required',
    '@Scheduled': 'Scheduled tasks → CloudWatch Events',
    '@SqsListener': 'SQS consumer → Lambda + SQS',
    '@KafkaListener': 'Kafka consumer → MSK + Lambda',
    '@Service': 'Business logic service',
    '@Component': 'Spring component',
}
```

**Package Structure:**
```python
# Count classes by type
service_classes = count_files('*Service.java')
controller_classes = count_files('*Controller.java')
repository_classes = count_files('*Repository.java')
batch_classes = count_files('*Batch*.java', '*Job*.java')
```

### 3.2 Java Analyzer Output

```json
{
  "java_analysis": {
    "build_tool": "maven",
    "framework": "spring-boot-3.2",
    "dependencies": {
      "database": ["postgresql:42.6.0", "spring-data-jpa:3.2.0"],
      "web": ["spring-boot-starter-web:3.2.0"],
      "messaging": [],
      "aws": ["aws-sdk-s3:2.20.0"]
    },
    "annotations_found": {
      "@RestController": 5,
      "@Entity": 12,
      "@Repository": 8,
      "@Scheduled": 2,
      "@Service": 15
    },
    "class_breakdown": {
      "controllers": 5,
      "services": 15,
      "repositories": 8,
      "entities": 12,
      "batch_jobs": 2
    },
    "entry_points": [
      {"class": "CustomerController", "endpoints": 4, "type": "REST"},
      {"class": "OrderController", "endpoints": 6, "type": "REST"},
      {"class": "BatchProcessor", "type": "SCHEDULED", "cron": "0 2 * * *"}
    ]
  }
}
```

---

## 4. Cross-Validation Logic

### 4.1 Agreement = High Confidence

| Check | Sources Agree? | Confidence |
|-------|----------------|------------|
| Database needed | Java has JPA + Data Analysis has entities | +0.3 |
| REST API needed | Java has @RestController + Discovery says "real-time" | +0.3 |
| Batch processing | Java has @Scheduled + Discovery says "batch" | +0.3 |
| File storage | Java has S3 SDK + COBOL has VSAM | +0.2 |

### 4.2 Conflict = Warning (Not Blocker)

```json
{
  "warnings": [
    {
      "type": "SOURCE_CONFLICT",
      "severity": "MEDIUM",
      "description": "Discovery indicates database usage, but no database dependencies in Java",
      "sources": {
        "discovery": "DB2 integration detected in COBOL",
        "java_analysis": "No JDBC/JPA dependencies found"
      },
      "possible_causes": [
        "Java generation did not include database layer",
        "Database access planned for later phase",
        "Data will be migrated to file-based (S3)"
      ],
      "recommendation": "Review Java generation or confirm file-based approach"
    }
  ]
}
```

### 4.3 Validation Rules

```python
VALIDATION_RULES = [
    {
        'name': 'database_consistency',
        'check': lambda: (
            java_has_jpa() == data_analysis_has_entities() or
            java_has_jdbc() == cobol_has_db2()
        ),
        'warning': 'Database mismatch between COBOL analysis and Java code'
    },
    {
        'name': 'api_consistency',
        'check': lambda: (
            java_has_rest_controllers() == discovery_says_realtime()
        ),
        'warning': 'API pattern mismatch'
    },
    {
        'name': 'messaging_consistency',
        'check': lambda: (
            java_has_messaging() == cobol_has_mq()
        ),
        'warning': 'Messaging pattern mismatch'
    }
]
```

---

## 5. Evidence-Based Recommendations

### 5.1 Recommendation Structure

```json
{
  "compute_recommendation": {
    "primary": {
      "service": "AWS Lambda",
      "runtime": "java17",
      "functions": [
        {
          "name": "CustomerService",
          "source_class": "com.example.CustomerController",
          "memory_mb": 1024,
          "timeout_seconds": 30,
          "trigger": "API Gateway"
        },
        {
          "name": "BatchProcessor",
          "source_class": "com.example.BatchProcessor",
          "memory_mb": 2048,
          "timeout_seconds": 900,
          "trigger": "CloudWatch Events (daily 2 AM)"
        }
      ],
      "confidence": 0.92,
      "evidence": [
        {"source": "java", "finding": "5 @RestController classes with 15 endpoints"},
        {"source": "java", "finding": "2 @Scheduled methods for batch processing"},
        {"source": "java", "finding": "No long-running processes detected"},
        {"source": "discovery", "finding": "Mixed real-time and batch workload"}
      ]
    },
    "alternative": {
      "service": "Amazon ECS/Fargate",
      "reason": "Consider if: high sustained traffic, need WebSocket, or prefer container-based deployment",
      "trade_offs": {
        "pros": ["No cold starts", "WebSocket support", "Easier local dev"],
        "cons": ["Higher base cost", "More operational overhead"]
      }
    }
  }
}
```

### 5.2 Database Recommendation

```json
{
  "database_recommendation": {
    "primary": {
      "service": "Aurora PostgreSQL",
      "instance_class": "db.t4g.medium",
      "storage_gb": 100,
      "multi_az": true,
      "confidence": 0.95,
      "evidence": [
        {"source": "java", "finding": "postgresql:42.6.0 dependency in pom.xml"},
        {"source": "java", "finding": "12 @Entity classes detected"},
        {"source": "java", "finding": "8 @Repository interfaces"},
        {"source": "data_analysis", "finding": "34 entities with 12 relationships in ERD"}
      ]
    },
    "alternative": {
      "service": "Amazon RDS PostgreSQL",
      "reason": "Consider if: simpler setup preferred, lower cost priority",
      "trade_offs": {
        "pros": ["Simpler", "Lower cost for small workloads"],
        "cons": ["Manual scaling", "Less performant at scale"]
      }
    }
  }
}
```

### 5.3 No Database Example

```json
{
  "database_recommendation": {
    "primary": {
      "service": "None",
      "confidence": 0.88,
      "evidence": [
        {"source": "java", "finding": "No JDBC/JPA dependencies in pom.xml"},
        {"source": "java", "finding": "No @Entity or @Repository annotations"},
        {"source": "cobol", "finding": "VSAM file-based processing only"}
      ],
      "alternative_storage": {
        "service": "Amazon S3",
        "reason": "VSAM files migrate naturally to S3 objects",
        "buckets": [
          {"name": "input-data", "purpose": "Input files"},
          {"name": "output-data", "purpose": "Processed output"},
          {"name": "archive", "storage_class": "S3 Glacier"}
        ]
      }
    }
  }
}
```

---

## 6. Decision Matrix

### 6.1 Compute Decision

```
┌─────────────────────────────────────────────────────────────────┐
│                      COMPUTE DECISION TREE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Java has @RestController?                                       │
│  ├── YES                                                         │
│  │   ├── Endpoint count > 20? → ECS/Fargate (microservice)      │
│  │   ├── Endpoint count > 5?  → Lambda (consider ECS alt)       │
│  │   └── Endpoint count ≤ 5   → Lambda                          │
│  │                                                               │
│  └── NO                                                          │
│      ├── Has @Scheduled?                                         │
│      │   ├── Duration > 15 min? → Step Functions + AWS Batch    │
│      │   └── Duration ≤ 15 min  → Lambda + CloudWatch Events    │
│      │                                                           │
│      ├── Has @SqsListener/@KafkaListener?                        │
│      │   └── Lambda + SQS/MSK trigger                           │
│      │                                                           │
│      └── Plain batch processing                                  │
│          └── Step Functions orchestration + Lambda               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Database Decision

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATABASE DECISION TREE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Java has JPA/JDBC dependencies?                                 │
│  ├── YES                                                         │
│  │   ├── Which driver?                                          │
│  │   │   ├── PostgreSQL → Aurora PostgreSQL                     │
│  │   │   ├── MySQL      → Aurora MySQL                          │
│  │   │   └── Other      → RDS (matching engine)                 │
│  │   │                                                           │
│  │   ├── Entity count > 20? → Aurora (scalability)              │
│  │   ├── Entity count > 5?  → Aurora or RDS                     │
│  │   └── Entity count ≤ 5   → RDS (cost-effective)              │
│  │                                                               │
│  └── NO database dependencies                                    │
│      ├── Data Analysis shows entities?                           │
│      │   └── WARNING: "Entities exist but no DB in Java"        │
│      │                                                           │
│      ├── COBOL has VSAM?                                         │
│      │   └── Recommend S3 for file storage                      │
│      │                                                           │
│      └── COBOL has DB2?                                          │
│          └── WARNING: "DB2 in COBOL but no DB in Java"          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.3 API Decision

```
┌─────────────────────────────────────────────────────────────────┐
│                        API DECISION TREE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Java has @RestController?                                       │
│  ├── YES → API Gateway + Lambda/ECS                             │
│  │   ├── Auth needed? (check @PreAuthorize, @Secured)           │
│  │   │   ├── YES → Cognito or IAM auth                          │
│  │   │   └── NO  → API Key or public                            │
│  │   │                                                           │
│  │   └── WebSocket needed? (@EnableWebSocket)                   │
│  │       ├── YES → API Gateway WebSocket or ALB                 │
│  │       └── NO  → API Gateway REST                             │
│  │                                                               │
│  └── NO @RestController                                          │
│      ├── Discovery says "real-time"?                             │
│      │   └── WARNING: "Discovery expects API but none in Java"  │
│      │                                                           │
│      └── No API required                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Output Artifacts

### 7.1 architecture_recommendations.json

```json
{
  "job_id": "ar_job_...",
  "generated_at": "2025-12-18T...",

  "summary": {
    "application_type": "hybrid",
    "primary_compute": "Lambda",
    "primary_database": "Aurora PostgreSQL",
    "api_required": true,
    "overall_confidence": 0.91
  },

  "compute_recommendation": { /* with evidence + alternative */ },
  "database_recommendation": { /* with evidence + alternative */ },
  "api_recommendation": { /* with evidence + alternative */ },
  "storage_recommendation": { /* S3 buckets */ },
  "security_recommendation": { /* VPC, encryption, IAM */ },

  "warnings": [ /* conflicts between sources */ ],

  "traceability": {
    "CustomerController.java": "customer-service Lambda",
    "OrderController.java": "order-service Lambda",
    "BatchProcessor.java": "batch-processor Lambda"
  },

  "migration_phases": [ /* phased approach */ ]
}
```

### 7.2 cost_estimates.json

```json
{
  "cost_breakdown": {
    "compute": {
      "service": "Lambda",
      "monthly_cost": 45.00,
      "calculation": {
        "functions": 3,
        "invocations_per_month": 500000,
        "avg_duration_ms": 200,
        "avg_memory_mb": 1024
      },
      "evidence": "Based on 15 REST endpoints from Java + Discovery transaction volume"
    },
    "database": {
      "service": "Aurora PostgreSQL",
      "monthly_cost": 85.00,
      "calculation": {
        "instance": "db.t4g.medium",
        "storage_gb": 100,
        "multi_az": true
      },
      "evidence": "Based on 12 @Entity classes + 34 ERD entities"
    }
  },
  "total_monthly": 156.00,
  "total_annual": 1872.00,
  "vs_mainframe_savings": "97% reduction"
}
```

### 7.3 validation_report.json

```json
{
  "validation_status": "PASSED_WITH_WARNINGS",
  "checks_passed": 8,
  "checks_warned": 1,
  "checks_failed": 0,

  "warnings": [
    {
      "check": "messaging_consistency",
      "message": "COBOL has MQ integration but no messaging in Java",
      "recommendation": "Consider adding SQS integration or confirm synchronous approach"
    }
  ],

  "confidence_breakdown": {
    "compute": 0.92,
    "database": 0.95,
    "api": 0.88,
    "overall": 0.91
  }
}
```

### 7.4 iac_templates/ (Blueprints)

Templates matched to actual Java structure:
- `vpc-stack.ts` - If VPC required
- `compute-stack.ts` - Lambda functions matching Java classes
- `database-stack.ts` - If database detected
- `api-stack.ts` - If REST controllers detected

---

## 8. Files to Create

```
engines/architecture/
├── __init__.py
├── runner.py                          # Main orchestrator
├── analyzers/
│   ├── __init__.py
│   ├── java_analyzer.py               # Scan pom.xml, annotations, structure
│   ├── source_consolidator.py         # Load 5 sources
│   └── cross_validator.py             # Check source agreement
├── recommenders/
│   ├── __init__.py
│   ├── compute_recommender.py         # Lambda vs ECS vs EC2
│   ├── database_recommender.py        # Aurora vs RDS vs DynamoDB vs None
│   ├── api_recommender.py             # API Gateway configuration
│   └── cost_estimator.py              # Evidence-based costs
├── generators/
│   ├── __init__.py
│   └── iac_generator.py               # CDK template generation
└── templates/
    └── cdk/                           # Template snippets

api/
├── models/
│   └── architecture.py                # Pydantic models
└── routes/
    └── architecture.py                # API endpoints
```

---

## 9. Summary

| Aspect | Reference | Our Design |
|--------|-----------|------------|
| Inputs | 4 flow outputs | 5 sources (+ Java code) |
| Evidence | None | Every recommendation has proof |
| Confidence | Generic 0.5-0.7 | Calculated 0.85-0.95 |
| Conflicts | Ignored | Flagged as warnings |
| Alternatives | None | Primary + Alternative for each |
| Traceability | "UNKNOWN" | Java class → Lambda mapping |
| Database | Always recommends | Only if dependencies exist |
| Costs | Hardcoded assumptions | Based on actual code metrics |

---

**Ready to build when you say go!**
