# Dependency Mapper Flow

**Date:** December 18, 2025
**Status:** Implemented
**Version:** 1.0

---

## Overview

Dependency Mapper analyzes dependencies in source code (COBOL or Java) and produces reports for planning and optimization. It supports the dual-analysis architecture where both COBOL and Java are analyzed separately, then compared.

---

## Purpose

1. **COBOL Analysis** - Understand what the system WAS (business intent, program relationships)
2. **Java Analysis** - Understand what the system IS (current structure, class dependencies)
3. **Comparison** - Find gaps between COBOL intent and Java reality

---

## Architecture

```
engines/dependency_mapper/
├── __init__.py
├── runner.py                          # Orchestrates the flow
├── analyzers/
│   ├── __init__.py
│   ├── static_analyzer.py             # COBOL parser (CALL, COPY, FILE I/O)
│   └── java_analyzer.py               # Java parser (imports, inheritance, method calls)
└── generators/
    ├── __init__.py
    ├── graph_builder.py               # Builds nodes + edges graph
    ├── coupling_calculator.py         # Fan-in, fan-out, coupling metrics
    ├── risk_assessor.py               # God programs, single points of failure
    ├── microservice_detector.py       # Service boundary suggestions
    └── impact_analyzer.py             # Blast radius analysis

api/models/dependency_mapper.py        # Pydantic request/response models
api/routes/dependency_mapper.py        # API endpoints
```

---

## Flow Pipeline

```
Source Code (COBOL or Java)
         │
         ▼
┌─────────────────────────────────────┐
│  1. Static Analysis                 │
│  - COBOL: CALL, COPY, FILE I/O     │
│  - Java: imports, extends, calls    │
│  Output: static_analysis.json       │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  2. Graph Builder                   │
│  - Create nodes (programs/classes)  │
│  - Create edges (dependencies)      │
│  - Calculate fan-in / fan-out       │
│  Output: dependency_graph.json      │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  3. Coupling Calculator             │
│  - Coupling factor per program      │
│  - Cohesion score                   │
│  - Classification (HIGH/MED/LOW)    │
│  Output: coupling_metrics.json      │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  4. Risk Assessor                   │
│  - God programs (fan-out > 20)      │
│  - Single points of failure         │
│  - Circular dependencies            │
│  Output: risk_assessment.json       │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  5. Microservice Detector           │
│  - Group by coupling/cohesion       │
│  - Suggest service boundaries       │
│  - Identify shared components       │
│  Output: microservice_boundaries.json│
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  6. Impact Analyzer                 │
│  - Direct dependents                │
│  - Indirect dependents (transitive) │
│  - Blast radius per program         │
│  Output: impact_analysis.json       │
└─────────────────────────────────────┘
```

---

## API Endpoints

### POST /dependencymapper

Run dependency analysis on COBOL or Java source.

**Request:**
```json
{
  "scout_account_id": "EVH",
  "application_name": "TestApp01",
  "source_type": "cobol"  // or "java"
}
```

**Response:**
```json
{
  "success": true,
  "job_id": "dm_cobol_EVH_TestApp01_1734567890",
  "source_type": "cobol",
  "status": "completed",
  "source_path": "/path/to/source",
  "artifacts_path": "/path/to/artifacts",
  "duration_ms": 1234,
  "summary": {
    "static_analysis": { "total_programs": 20, "total_dependencies": 150 },
    "graph": { "total_nodes": 50, "total_edges": 150 },
    "coupling": { "average_coupling": 0.05, "high_coupling_count": 1 },
    "risk": { "high_risk_count": 2, "total_risk_items": 5 },
    "microservices": { "total_services_suggested": 8 },
    "impact": { "high_impact_count": 3 }
  },
  "artifacts": {
    "static_analysis": "/path/to/static_analysis.json",
    "dependency_graph": "/path/to/dependency_graph.json",
    "coupling_metrics": "/path/to/coupling_metrics.json",
    "risk_assessment": "/path/to/risk_assessment.json",
    "microservice_boundaries": "/path/to/microservice_boundaries.json",
    "impact_analysis": "/path/to/impact_analysis.json"
  }
}
```

### POST /dependencymapper/compare

Compare COBOL and Java dependency analyses. Uses existing analysis results based on account/app.

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
  "job_id": "dm_compare_EVH_TestApp01_1734567910",
  "status": "completed",
  "cobol_summary": { ... },
  "java_summary": { ... },
  "gaps": [
    {
      "type": "god_class_introduced",
      "detail": "Java has 2 high-risk classes vs 1 in COBOL",
      "severity": "warning"
    }
  ],
  "insights": [
    "Java generated more classes (25) than COBOL programs (20)"
  ],
  "recommendations": [
    {
      "type": "split_god_classes",
      "detail": "Use Code Refactor to split large classes",
      "priority": "high"
    }
  ],
  "artifacts_path": "/path/to/comparison"
}
```

### GET /dependencymapper/{job_id}/status

Get job status.

### GET /dependencymapper/{job_id}/results

Get results overview with list of artifacts.

### GET /dependencymapper/{job_id}/results/json/{filename}

Get specific JSON artifact.

---

## Output Reports

### 1. static_analysis.json

Raw dependency data per program/class.

```json
{
  "programs": [
    {
      "program": "PAYROLL",
      "file_path": "/path/to/PAYROLL.CBL",
      "calls": [
        { "target": "CALCULATE", "line": 150, "type": "CALL" }
      ],
      "copies": [
        { "copybook": "EMPLOYEE-REC", "line": 10 }
      ],
      "file_io": [
        { "operation": "READ", "file": "PAYFILE", "line": 200 }
      ],
      "database": [],
      "lines_of_code": 500
    }
  ],
  "summary": {
    "total_programs": 20,
    "total_calls": 45,
    "total_copies": 80,
    "total_file_io": 30,
    "total_dependencies": 155
  }
}
```

### 2. dependency_graph.json

Graph structure with nodes and edges.

```json
{
  "nodes": [
    {
      "id": "PAYROLL",
      "type": "program",
      "fan_in": 0,
      "fan_out": 15,
      "lines_of_code": 500,
      "complexity_score": 20
    },
    {
      "id": "EMPLOYEE-REC",
      "type": "copybook",
      "fan_in": 5,
      "used_by_count": 5,
      "programs": ["PAYROLL", "REPORTS", ...]
    }
  ],
  "edges": [
    {
      "from": "PAYROLL",
      "to": "CALCULATE",
      "type": "CALL",
      "line_number": 150
    }
  ],
  "summary": {
    "total_nodes": 50,
    "total_edges": 155,
    "program_count": 20,
    "copybook_count": 30
  }
}
```

### 3. coupling_metrics.json

Coupling analysis per program.

```json
{
  "by_program": [
    {
      "program": "MAINPROG",
      "fan_in": 0,
      "fan_out": 45,
      "coupling_factor": 0.35,
      "cohesion_score": 0.0,
      "classification": "High Coupling"
    }
  ],
  "overall": {
    "total_programs": 20,
    "average_fan_in": 2.5,
    "average_fan_out": 2.5,
    "average_coupling": 0.05,
    "high_coupling_count": 1,
    "medium_coupling_count": 3,
    "low_coupling_count": 16
  }
}
```

### 4. risk_assessment.json

Risk analysis identifying problem areas.

```json
{
  "god_programs": [
    {
      "program": "MAINPROG",
      "fan_out": 45,
      "risk": "Calls 45 other programs - too many responsibilities",
      "risk_level": "Medium-High",
      "recommendation": "Refactor to split responsibilities"
    }
  ],
  "single_points_of_failure": [
    {
      "program": "UTILITY",
      "fan_in": 15,
      "risk": "15 programs depend on this - single point of failure",
      "risk_level": "High",
      "recommendation": "Ensure comprehensive testing"
    }
  ],
  "circular_dependencies": [],
  "tight_coupling_areas": [],
  "summary": {
    "high_risk_count": 1,
    "medium_risk_count": 1,
    "total_risk_items": 2
  }
}
```

### 5. microservice_boundaries.json

Suggested service groupings.

```json
{
  "suggested_services": [
    {
      "service_name": "Service1",
      "programs": ["PAYROLL", "CALCULATE", "DEDUCTIONS"],
      "program_count": 3,
      "internal_coupling": 0.8,
      "external_coupling": 0.2,
      "cohesion_score": 0.85,
      "justification": "Strong internal cohesion (80%), well-defined boundary"
    }
  ],
  "shared_components": [
    {
      "component": "DATE-UTILS",
      "component_type": "copybook",
      "used_by_services_count": 4,
      "recommendation": "Create shared library"
    }
  ],
  "summary": {
    "total_services_suggested": 8,
    "total_shared_components": 5
  }
}
```

### 6. impact_analysis.json

Blast radius for each program.

```json
{
  "program_impact_map": {
    "UTILITY": {
      "program": "UTILITY",
      "direct_dependents": ["PROG1", "PROG2", ...],
      "direct_dependents_count": 15,
      "indirect_dependents": ["PROG20", ...],
      "indirect_dependents_count": 5,
      "total_impact_radius": 20,
      "risk_level": "High",
      "refactoring_recommendation": "Major impact - requires careful planning"
    }
  },
  "sorted_by_impact": [
    { "program": "UTILITY", "impact_radius": 20, "risk_level": "High" }
  ],
  "summary": {
    "total_programs": 20,
    "high_impact_count": 2,
    "medium_impact_count": 5,
    "low_impact_count": 13,
    "max_impact_radius": 20
  }
}
```

---

## Usage Examples

### Analyze COBOL Source

```bash
curl -X POST http://localhost:8000/dependencymapper \
  -H "Content-Type: application/json" \
  -d '{
    "scout_account_id": "EVH",
    "application_name": "TestApp01",
    "source_type": "cobol"
  }'
```

### Analyze Java Source

```bash
curl -X POST http://localhost:8000/dependencymapper \
  -H "Content-Type: application/json" \
  -d '{
    "scout_account_id": "EVH",
    "application_name": "TestApp01",
    "source_type": "java"
  }'
```

### Compare COBOL vs Java

```bash
curl -X POST http://localhost:8000/dependencymapper/compare \
  -H "Content-Type: application/json" \
  -d '{
    "scout_account_id": "EVH",
    "application_name": "TestApp01"
  }'
```

### Get Specific Report

```bash
curl http://localhost:8000/dependencymapper/dm_cobol_EVH_TestApp01_1734567890/results/json/dependency_graph.json
```

---

## Source Paths

| Source Type | Path |
|-------------|------|
| COBOL | `{base}/code-transformation-v2/{account}/{app}/ingest/source_files/` |
| Java | `{base}/code-transformation-v2/{account}/{app}/code_analysis/generated/*/src/main/java/` |

---

## Output Paths

```
{base}/code-transformation-v2/{account}/{app}/dependency_mapper/
├── cobol/
│   └── artifacts/
│       ├── static_analysis.json
│       ├── dependency_graph.json
│       ├── coupling_metrics.json
│       ├── risk_assessment.json
│       ├── microservice_boundaries.json
│       └── impact_analysis.json
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

### Downstream
- Reports feed into **Final Optimization** phase
- Comparison report identifies gaps for **Code Refactor**

---

## Key Metrics Explained

| Metric | Description | Threshold |
|--------|-------------|-----------|
| **Fan-in** | How many programs depend on this | High > 10 (SPOF risk) |
| **Fan-out** | How many programs this depends on | High > 20 (God program) |
| **Coupling Factor** | Normalized coupling (0-1) | High > 0.3 |
| **Cohesion Score** | Internal consistency (0-1) | Low < 0.5 |
| **Impact Radius** | Total affected programs | High > 10 |

---

## Notes

- This flow produces **reports only** - no code modifications
- Run both COBOL and Java analysis for full comparison
- Comparison report highlights gaps between business intent and implementation
- Reports inform the Final Optimization phase
