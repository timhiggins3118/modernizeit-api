# ModernizeIT Flow Architecture Design

**Version:** 1.0
**Date:** December 18, 2025
**Status:** Design Phase

---

## Overview

This document describes the multi-phase architecture for COBOL to Java transformation. The key insight is that analysis flows run **twice** - once against COBOL (for understanding) and once against generated Java (for optimization) - producing comparison reports that inform the final optimization phase.

---

## Architecture Diagram

```
COBOL Source
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 1: GENERATE                                      │
│  Code Analysis → Base Java                              │
│                                                         │
│  Input:  COBOL source files                             │
│  Output: Initial Java application                       │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 2: INITIAL REFACTOR                              │
│  Code Refactor → Improved Java                          │
│                                                         │
│  Input:  Base Java from Phase 1                         │
│  Output: Refactored Java (class extraction, renaming)   │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 3: DEEP ANALYSIS (REPORTS ONLY - NO CODE CHANGES)│
│                                                         │
│  ┌──────────────────┐    ┌──────────────────┐          │
│  │ COBOL Analysis   │    │ Java Analysis    │          │
│  │                  │    │                  │          │
│  │ - Dependency Map │    │ - Dependency Map │          │
│  │ - Monolith ID    │    │ - Monolith ID    │          │
│  │ - Data Analysis  │    │ - Data Analysis  │          │
│  │ - Discovery      │    │ - Discovery      │          │
│  │                  │    │                  │          │
│  │ Purpose:         │    │ Purpose:         │          │
│  │ Understand what  │    │ Understand what  │          │
│  │ the system WAS   │    │ the system IS    │          │
│  └────────┬─────────┘    └────────┬─────────┘          │
│           │                       │                     │
│           └───────────┬───────────┘                     │
│                       ▼                                 │
│              COMPARISON REPORTS                         │
│              (COBOL vs Java analysis)                   │
│                                                         │
│              - What gaps exist?                         │
│              - What patterns changed?                   │
│              - What optimizations needed?               │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  PHASE 4: FINAL OPTIMIZATION                            │
│  Java Generation V2 (uses ALL reports)                  │
│                                                         │
│  Input:  - Refactored Java from Phase 2                 │
│          - All COBOL analysis reports                   │
│          - All Java analysis reports                    │
│          - Comparison reports                           │
│                                                         │
│  Output: Optimized Java Application                     │
└─────────────────────────────────────────────────────────┘
```

---

## Phase Details

### Phase 1: Generate (Code Analysis)

**Purpose:** Create initial Java application from COBOL source.

**API:** `POST /codeanalysis`

**Input:**
- COBOL source files (from Ingest)

**Output:**
- Base Java application
- Semantic models (ERD, data model, etc.)

**Notes:**
- This is the foundation - creates working Java from COBOL
- May not be perfect - that's what subsequent phases fix

---

### Phase 2: Initial Refactor (Code Refactor)

**Purpose:** Apply immediate improvements to generated Java.

**API:**
- `POST /coderefactor` (analyze mode - generates recipes)
- `POST /coderefactor/transform` (apply recipes)

**Input:**
- Base Java from Phase 1

**Output:**
- Refactored Java (class extraction, naming modernization, etc.)
- Refactor reports

**Notes:**
- Makes Java more maintainable
- Extracts services from god classes
- Modernizes naming conventions

---

### Phase 3: Deep Analysis (Reports Only)

**Purpose:** Gather intelligence from both COBOL and Java perspectives. **NO CODE CHANGES** in this phase - reports only.

#### Analysis Flows

| Flow | COBOL Analysis | Java Analysis |
|------|----------------|---------------|
| **Dependency Mapper** | Program CALL/COPY dependencies, microservice boundaries | Class dependencies, package structure |
| **Monolith Identifier** | God programs, tight coupling | God classes, circular dependencies |
| **Data Analysis** | Copybook structures, file I/O | Data classes, entity relationships |
| **Discovery** | Business logic documentation | API documentation, method contracts |

#### APIs (Each runs twice - COBOL and Java)

| Flow | COBOL API | Java API |
|------|-----------|----------|
| Dependency Mapper | `POST /dependencymapper/cobol` | `POST /dependencymapper/java` |
| Monolith Identifier | `POST /monolithidentifier/cobol` | `POST /monolithidentifier/java` |
| Data Analysis | `POST /dataanalysis/cobol` | `POST /dataanalysis/java` |
| Discovery | `POST /discovery/cobol` | `POST /discovery/java` |

#### Comparison Reports

After both COBOL and Java analysis complete, generate comparison reports:

```json
{
  "comparison_type": "dependency_mapper",
  "cobol_analysis": {
    "total_programs": 20,
    "god_programs": 1,
    "suggested_services": 5
  },
  "java_analysis": {
    "total_classes": 25,
    "god_classes": 2,
    "current_packages": 3
  },
  "gaps": [
    {
      "type": "god_class_introduced",
      "detail": "COBOL had 1 god program, Java has 2 god classes",
      "recommendation": "Split PayrollCalculationService into domain services"
    },
    {
      "type": "missing_service_boundary",
      "detail": "COBOL analysis suggested 5 services, Java has 3 packages",
      "recommendation": "Consider extracting Claims and Payments into separate packages"
    }
  ],
  "insights": [
    "Java structure diverged from COBOL business domains",
    "Utility functions consolidated better in Java than COBOL",
    "Data access patterns simplified in Java"
  ]
}
```

---

### Phase 4: Final Optimization

**Purpose:** Use ALL gathered intelligence to produce the optimal Java application.

**API:** `POST /javageneration/optimize`

**Input:**
- Refactored Java from Phase 2
- All COBOL analysis reports (Phase 3)
- All Java analysis reports (Phase 3)
- Comparison reports (Phase 3)

**Output:**
- Final optimized Java application

**What this phase does:**
1. Reviews all reports
2. Identifies remaining issues
3. Applies final optimizations based on combined intelligence
4. Produces production-ready Java

**Key Principle:** More information = Better final Java

---

## Flow Summary Table

| Phase | Flow | Modifies Code? | Output |
|-------|------|----------------|--------|
| 1 | Code Analysis | YES | Base Java |
| 2 | Code Refactor | YES | Improved Java |
| 3 | Dependency Mapper (COBOL) | NO | Reports only |
| 3 | Dependency Mapper (Java) | NO | Reports only |
| 3 | Monolith Identifier (COBOL) | NO | Reports only |
| 3 | Monolith Identifier (Java) | NO | Reports only |
| 3 | Data Analysis (COBOL) | NO | Reports only |
| 3 | Data Analysis (Java) | NO | Reports only |
| 3 | Discovery (COBOL) | NO | Reports only |
| 3 | Discovery (Java) | NO | Reports only |
| 3 | Comparison Reports | NO | Reports only |
| 4 | Final Optimization | YES | Final Java |

---

## Key Design Principles

1. **Dual Analysis:** Every analysis flow runs twice - once on COBOL, once on Java
2. **Reports First:** Phase 3 produces reports only - no code modifications
3. **Comparison Insight:** Gap analysis between COBOL and Java reveals optimization opportunities
4. **Information Accumulation:** Each phase adds intelligence for the final optimization
5. **Separation of Concerns:** Analysis is separate from transformation

---

## Why This Architecture?

### The Problem
- COBOL analysis tells us what the system WAS (business intent)
- Java analysis tells us what the system IS (current reality)
- Neither alone is sufficient

### The Solution
- Run both analyses
- Compare results
- Use combined intelligence for optimal output

### The Benefit
- Java application can be DIFFERENT from COBOL (modernized, restructured)
- But we don't lose the business knowledge embedded in COBOL
- Final Java is informed by both perspectives

---

## Next Steps

1. Design Dependency Mapper API (COBOL + Java modes)
2. Design Monolith Identifier API (COBOL + Java modes)
3. Design Data Analysis API (COBOL + Java modes)
4. Design Discovery API (COBOL + Java modes)
5. Design Comparison Report generator
6. Design Final Optimization API

---

## Open Questions

1. Should comparison reports be generated automatically or on-demand?
2. Should Phase 4 be automatic or require human review of reports first?
3. What's the minimum set of reports needed for Phase 4?
4. Should there be a UI for reviewing comparison reports?
