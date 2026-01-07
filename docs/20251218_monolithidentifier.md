# Monolith Identifier Flow

**Date:** December 18, 2025
**Status:** Implemented
**Version:** 1.0

---

## Overview

Monolith Identifier analyzes source code (COBOL or Java) to detect monolithic anti-patterns and provides business capability-driven decomposition recommendations. It complements Dependency Mapper by focusing on WHAT programs do (business responsibilities) rather than WHO they call (technical coupling).

---

## Purpose

1. **Pattern Detection** - Find God Objects, Big Ball of Mud, large programs
2. **Business Capability Analysis** - Identify what business functions each program handles
3. **Modularity Metrics** - Calculate cohesion, coupling, complexity, maintainability
4. **Decomposition Strategy** - Recommend microservice boundaries based on business domains
5. **Migration Planning** - Provide Strangler Fig pattern migration roadmap

---

## Difference from Dependency Mapper

| Aspect | Dependency Mapper | Monolith Identifier |
|--------|------------------|---------------------|
| **Focus** | Technical coupling (CALL, COPY, FILE I/O) | Business capabilities |
| **Question** | "Who calls who?" | "What does this program DO?" |
| **Services** | Many small services (technical clustering) | Fewer large services (business domains) |
| **Output** | Dependency graph, coupling metrics | Pattern detection, decomposition strategy |
| **Use Case** | Optimization, impact analysis | Architecture planning, modernization roadmap |

**Use BOTH together:**
- Dependency Mapper tells you technical relationships
- Monolith Identifier tells you business responsibilities
- Combined insights = better modernization plan

---

## Architecture

```
engines/monolith_identifier/
├── __init__.py
├── runner.py                          # Orchestrates the flow
├── analyzers/
│   ├── __init__.py
│   ├── static_analyzer.py             # COBOL static analysis (LOC, sections, GOTO, etc.)
│   └── java_analyzer.py               # Java static analysis (methods, classes, complexity)
└── generators/
    ├── __init__.py
    ├── pattern_detector.py            # GOD_OBJECT, BIG_BALL_OF_MUD, LARGE_PROGRAM
    ├── modularity_calculator.py       # Cohesion, coupling, complexity, maintainability
    ├── business_capability_analyzer.py # AI-powered business capability detection
    └── decomposition_strategist.py    # Microservice recommendations, migration plan

api/models/monolith_identifier.py      # Pydantic request/response models
api/routes/monolith_identifier.py      # API endpoints
```

---

## Flow Pipeline

```
Source Code (COBOL or Java)
         │
         ▼
┌─────────────────────────────────────┐
│  1. Static Analysis                 │
│  - LOC per program                  │
│  - Sections/methods count           │
│  - Paragraphs/functions count       │
│  - GOTO/complexity indicators       │
│  - PERFORM/call patterns            │
│  Output: static_analysis.json       │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  2. Pattern Detector                │
│  - GOD_OBJECT detection             │
│  - BIG_BALL_OF_MUD detection        │
│  - LARGE_PROGRAM detection          │
│  - TIGHT_COUPLING detection         │
│  - SPAGHETTI_CODE detection         │
│  Output: detected_patterns.json     │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  3. Modularity Calculator           │
│  - Cohesion score per program       │
│  - Coupling score per program       │
│  - Complexity score per program     │
│  - Maintainability index            │
│  - Classification (HIGH/MED/LOW)    │
│  Output: modularity_metrics.json    │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  4. Business Capability Analyzer    │
│  - Identify business domains        │
│  - Map programs to capabilities     │
│  - Detect responsibility overlap    │
│  - AI-enhanced analysis (optional)  │
│  Output: business_capabilities.json │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  5. Decomposition Strategist        │
│  - Recommend microservices          │
│  - Group by business capability     │
│  - Estimate extraction effort       │
│  - Generate migration roadmap       │
│  - Strangler Fig pattern plan       │
│  Output: decomposition_strategy.json│
└─────────────────────────────────────┘
```

---

## Pattern Detection Rules

### GOD_OBJECT
A single program/class with too many responsibilities.

**COBOL Detection:**
```
IF (loc > 5000 AND sections > 100 AND business_capabilities > 3):
    pattern = "GOD_OBJECT"
    severity = "HIGH"
```

**Java Detection:**
```
IF (loc > 3000 AND methods > 50 AND responsibilities > 3):
    pattern = "GOD_OBJECT"
    severity = "HIGH"
```

### BIG_BALL_OF_MUD
Tangled code with no clear structure.

**COBOL Detection:**
```
IF (goto_count > 10 AND cyclomatic_complexity > 50):
    pattern = "BIG_BALL_OF_MUD"
    severity = "HIGH"
```

**Java Detection:**
```
IF (cyclomatic_complexity > 50 AND coupling_score > 0.5):
    pattern = "BIG_BALL_OF_MUD"
    severity = "HIGH"
```

### LARGE_PROGRAM
Programs that are simply too large.

**COBOL Detection:**
```
IF (loc > 3000):
    pattern = "LARGE_PROGRAM"
    severity = "MEDIUM"
```

**Java Detection:**
```
IF (loc > 2000):
    pattern = "LARGE_PROGRAM"
    severity = "MEDIUM"
```

### TIGHT_COUPLING
Programs with too many dependencies.

```
IF (external_dependencies > 15):
    pattern = "TIGHT_COUPLING"
    severity = "MEDIUM"
```

### SPAGHETTI_CODE
Code with excessive branching and poor structure.

**COBOL Detection:**
```
IF (goto_count > 5 OR nested_ifs > 10):
    pattern = "SPAGHETTI_CODE"
    severity = "MEDIUM"
```

---

## Metrics Calculation

### Cohesion Score (0-1, higher is better)
Measures how focused a program is on a single responsibility.

```python
cohesion = 1 / business_capabilities_count
# 1 capability = 1.0 (perfect)
# 4 capabilities = 0.25 (poor)
```

### Coupling Score (0-1, lower is better)
Measures external dependencies.

```python
coupling = (calls_count + copies_count + imports_count) / total_programs
```

### Complexity Score (lower is better)
Based on structural complexity indicators.

**COBOL:**
```python
complexity = (goto_count * 2) + (perform_count * 0.5) + (sections * 0.1)
```

**Java:**
```python
complexity = (cyclomatic_complexity) + (nested_depth * 2) + (methods * 0.2)
```

### Maintainability Index (0-100, higher is better)
Combined score for overall maintainability.

```python
maintainability = 100 - (complexity * 0.5) - (coupling * 20) - ((1 - cohesion) * 30)
```

**Classification:**
- **HIGH**: > 70
- **MEDIUM**: 40-70
- **LOW**: < 40

---

## API Endpoints

### POST /monolithidentifier

Run monolith analysis on COBOL or Java source.

**Request:**
```json
{
  "scout_account_id": "EVH",
  "application_name": "TestApp01",
  "source_type": "cobol"
}
```

**Response:**
```json
{
  "success": true,
  "job_id": "mi_cobol_EVH_TestApp01_1734567890",
  "source_type": "cobol",
  "status": "completed",
  "source_path": "/path/to/source",
  "artifacts_path": "/path/to/artifacts",
  "duration_ms": 2345,
  "summary": {
    "static_analysis": { "total_programs": 20, "total_loc": 45000 },
    "patterns": { "god_objects": 2, "large_programs": 5, "spaghetti_code": 3 },
    "modularity": { "average_maintainability": 55.3, "low_maintainability_count": 4 },
    "business_capabilities": { "total_capabilities": 8 },
    "decomposition": { "recommended_services": 5, "total_effort_weeks": 24 }
  },
  "artifacts": {
    "static_analysis": "/path/to/static_analysis.json",
    "detected_patterns": "/path/to/detected_patterns.json",
    "modularity_metrics": "/path/to/modularity_metrics.json",
    "business_capabilities": "/path/to/business_capabilities.json",
    "decomposition_strategy": "/path/to/decomposition_strategy.json"
  }
}
```

### POST /monolithidentifier/compare

Compare COBOL and Java monolith analyses.

**Request:**
```json
{
  "scout_account_id": "EVH",
  "application_name": "TestApp01"
}
```

**Response:**
```json
{
  "success": true,
  "job_id": "mi_compare_EVH_TestApp01_1734567910",
  "status": "completed",
  "cobol_summary": { ... },
  "java_summary": { ... },
  "gaps": [
    {
      "type": "god_class_increase",
      "detail": "Java has 3 god classes vs 2 in COBOL",
      "severity": "warning"
    }
  ],
  "insights": [
    "Java maintains similar modularity structure to COBOL"
  ],
  "recommendations": [
    {
      "type": "refactor_god_classes",
      "detail": "Split MainProcessor class into domain services",
      "priority": "high"
    }
  ],
  "artifacts_path": "/path/to/comparison"
}
```

### GET /monolithidentifier/{job_id}/status

Get job status.

### GET /monolithidentifier/{job_id}/results

Get results overview with list of artifacts.

### GET /monolithidentifier/{job_id}/results/json/{filename}

Get specific JSON artifact.

---

## Output Reports

### 1. static_analysis.json

Raw metrics per program/class.

```json
{
  "programs": [
    {
      "program": "MAINPROG",
      "file_path": "/path/to/MAINPROG.CBL",
      "loc": 8500,
      "sections": 120,
      "paragraphs": 450,
      "perform_count": 320,
      "goto_count": 15,
      "call_count": 25,
      "copy_count": 12,
      "file_io_count": 8,
      "nested_if_depth": 6
    }
  ],
  "summary": {
    "total_programs": 20,
    "total_loc": 45000,
    "average_loc": 2250,
    "max_loc": 8500,
    "total_sections": 500,
    "total_goto": 45
  }
}
```

### 2. detected_patterns.json

Anti-patterns found in the codebase.

```json
{
  "patterns": [
    {
      "pattern_type": "GOD_OBJECT",
      "program": "MAINPROG",
      "severity": "HIGH",
      "confidence": 0.95,
      "indicators": [
        "LOC: 8500 (threshold: 5000)",
        "Sections: 120 (threshold: 100)",
        "Business capabilities: 4 (threshold: 3)"
      ],
      "recommendation": "Decompose into multiple services by business capability"
    },
    {
      "pattern_type": "SPAGHETTI_CODE",
      "program": "LEGACYPROC",
      "severity": "MEDIUM",
      "confidence": 0.85,
      "indicators": [
        "GOTO count: 15 (threshold: 5)",
        "Nested IF depth: 8 (threshold: 5)"
      ],
      "recommendation": "Refactor to eliminate GOTO statements and flatten conditionals"
    }
  ],
  "summary": {
    "god_objects": 2,
    "big_ball_of_mud": 1,
    "large_programs": 5,
    "tight_coupling": 3,
    "spaghetti_code": 4,
    "total_patterns": 15
  }
}
```

### 3. modularity_metrics.json

Modularity scores per program.

```json
{
  "by_program": [
    {
      "program": "MAINPROG",
      "loc": 8500,
      "cohesion_score": 0.25,
      "coupling_score": 0.38,
      "complexity_score": 85.2,
      "maintainability_index": 32.5,
      "classification": "LOW",
      "recommendations": [
        "Improve cohesion by extracting business capabilities",
        "Reduce coupling by using interfaces",
        "Reduce complexity by eliminating GOTO statements"
      ]
    }
  ],
  "overall": {
    "total_programs": 20,
    "average_cohesion": 0.65,
    "average_coupling": 0.22,
    "average_complexity": 35.5,
    "average_maintainability": 55.3,
    "high_maintainability_count": 8,
    "medium_maintainability_count": 8,
    "low_maintainability_count": 4
  }
}
```

### 4. business_capabilities.json

Business capabilities identified in the codebase.

```json
{
  "capabilities": [
    {
      "capability": "Customer Management",
      "description": "Customer data CRUD operations, validation, lookup",
      "programs": ["CUSTMGMT", "CUSTVAL", "MAINPROG"],
      "program_count": 3,
      "total_loc": 12000,
      "primary_program": "CUSTMGMT",
      "indicators": [
        "CUSTOMER-RECORD data structure",
        "VALIDATE-CUSTOMER paragraph",
        "Customer file I/O operations"
      ]
    },
    {
      "capability": "Order Processing",
      "description": "Order creation, validation, fulfillment",
      "programs": ["ORDPROC", "ORDVAL", "MAINPROG"],
      "program_count": 3,
      "total_loc": 10000,
      "primary_program": "ORDPROC",
      "indicators": [
        "ORDER-RECORD data structure",
        "PROCESS-ORDER paragraph",
        "Order file I/O operations"
      ]
    }
  ],
  "program_capability_map": {
    "MAINPROG": ["Customer Management", "Order Processing", "Reporting", "Data Validation"],
    "CUSTMGMT": ["Customer Management"],
    "ORDPROC": ["Order Processing"]
  },
  "summary": {
    "total_capabilities": 8,
    "programs_with_multiple_capabilities": 3,
    "max_capabilities_per_program": 4
  }
}
```

### 5. decomposition_strategy.json

Recommended microservices and migration plan.

```json
{
  "recommended_services": [
    {
      "service_name": "CustomerService",
      "business_capability": "Customer Management",
      "programs": ["CUSTMGMT", "CUSTVAL"],
      "extracted_from_god_objects": ["MAINPROG"],
      "total_loc": 5500,
      "extraction_complexity": "medium",
      "estimated_effort_weeks": 6,
      "dependencies": ["DataValidationService"],
      "shared_data": ["CUSTOMER-RECORD"]
    },
    {
      "service_name": "OrderService",
      "business_capability": "Order Processing",
      "programs": ["ORDPROC", "ORDVAL"],
      "extracted_from_god_objects": ["MAINPROG"],
      "total_loc": 4800,
      "extraction_complexity": "medium",
      "estimated_effort_weeks": 5,
      "dependencies": ["CustomerService", "InventoryService"],
      "shared_data": ["ORDER-RECORD", "CUSTOMER-RECORD"]
    }
  ],
  "god_object_decomposition": [
    {
      "program": "MAINPROG",
      "current_capabilities": ["Customer Management", "Order Processing", "Reporting", "Data Validation"],
      "recommended_split": [
        { "capability": "Customer Management", "target_service": "CustomerService" },
        { "capability": "Order Processing", "target_service": "OrderService" },
        { "capability": "Reporting", "target_service": "ReportingService" },
        { "capability": "Data Validation", "target_service": "DataValidationService" }
      ],
      "refactoring_complexity": "high",
      "estimated_effort_weeks": 12
    }
  ],
  "migration_strategy": {
    "approach": "Strangler Fig Pattern",
    "phases": [
      {
        "phase": 1,
        "name": "Foundation",
        "description": "Set up API gateway, extract DataValidationService (least dependencies)",
        "services": ["DataValidationService"],
        "effort_weeks": 4,
        "risk": "LOW"
      },
      {
        "phase": 2,
        "name": "Core Services",
        "description": "Extract CustomerService and OrderService",
        "services": ["CustomerService", "OrderService"],
        "effort_weeks": 11,
        "risk": "MEDIUM"
      },
      {
        "phase": 3,
        "name": "Remaining Services",
        "description": "Extract ReportingService and remaining functionality",
        "services": ["ReportingService", "InventoryService"],
        "effort_weeks": 9,
        "risk": "LOW"
      }
    ],
    "total_effort_weeks": 24,
    "estimated_timeline": "6 months"
  },
  "refactoring_priorities": [
    {
      "priority": 1,
      "program": "MAINPROG",
      "pattern": "GOD_OBJECT",
      "reason": "Contains 4 business capabilities, blocking service extraction",
      "action": "Decompose into separate programs before microservice extraction",
      "effort_weeks": 12
    }
  ],
  "summary": {
    "recommended_services_count": 5,
    "god_objects_to_decompose": 2,
    "total_effort_weeks": 24,
    "estimated_timeline": "6 months",
    "migration_approach": "Strangler Fig Pattern"
  }
}
```

---

## Source Paths

| Source Type | Path |
|-------------|------|
| COBOL | `{base}/code-transformation-v2/{account}/{app}/shared/uploads/{hash}/extracted/` |
| Java | `{base}/code-transformation-v2/{account}/{app}/code_analysis/generated/*/src/main/java/` |

---

## Output Paths

```
{base}/code-transformation-v2/{account}/{app}/monolith_identifier/
├── cobol/
│   └── artifacts/
│       ├── static_analysis.json
│       ├── detected_patterns.json
│       ├── modularity_metrics.json
│       ├── business_capabilities.json
│       └── decomposition_strategy.json
├── java/
│   └── artifacts/
│       └── (same files)
└── comparison/
    └── comparison_report.json
```

---

## Integration with Other Flows

### Prerequisites
- **Ingest** - Required for COBOL analysis (provides source files)
- **Code Analysis** - Required for Java analysis (provides generated Java)

### Complementary Flows
- **Dependency Mapper** - Run BOTH for complete picture:
  - Dependency Mapper: Technical coupling analysis
  - Monolith Identifier: Business capability analysis
  - Combined: Optimal microservice boundaries

### Downstream
- Reports feed into **Final Optimization** phase
- Decomposition strategy guides **Code Refactor** priorities

---

## Key Metrics Explained

| Metric | Description | Good | Bad |
|--------|-------------|------|-----|
| **Cohesion** | Focus on single responsibility | > 0.7 | < 0.4 |
| **Coupling** | External dependencies | < 0.2 | > 0.4 |
| **Complexity** | Structural complexity | < 30 | > 60 |
| **Maintainability** | Overall health (0-100) | > 70 | < 40 |

---

## Pattern Severity Levels

| Pattern | Severity | Impact |
|---------|----------|--------|
| GOD_OBJECT | HIGH | Blocks microservice extraction |
| BIG_BALL_OF_MUD | HIGH | Requires major refactoring |
| LARGE_PROGRAM | MEDIUM | Increases maintenance cost |
| TIGHT_COUPLING | MEDIUM | Complicates service boundaries |
| SPAGHETTI_CODE | MEDIUM | Reduces code quality |

---

## Notes

- This flow produces **reports only** - no code modifications
- Run both COBOL and Java analysis for full comparison
- God Objects should be refactored BEFORE microservice extraction
- Strangler Fig pattern provides low-risk migration path
- Combine with Dependency Mapper for complete architectural analysis
