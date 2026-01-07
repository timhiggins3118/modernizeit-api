# ModernizeIT API Design Analysis

**Date:** December 17, 2025
**Status:** Analysis Complete - Ready for Design Discussion
**Author:** Claude (Senior Python Architect)

---

## Executive Summary

This document captures the analysis of:
1. Current AWS API contracts (Postman collections)
2. S3 output structure and artifacts
3. IBM watsonx Code Assistant reference
4. Existing modernizeit-api state

**Goal:** Design a new API layer that matches AWS outputs while being better designed.

---

## Part 1: The Three Applications

| App | Description | Status |
|-----|-------------|--------|
| **AWS App** | API Gateway → Step Functions → Lambdas | LIVE - Customers using |
| **Thick Client** | Desktop app with local Lambda execution | Existing |
| **CLI/POC** | modernizeit-cli - COBOL-to-Java proof of concept | Learnings captured |

**This API** will be the new backbone that:
- Matches AWS API contracts (backwards compatible)
- Runs locally without AWS
- Eventually powers Electron + React thick client
- Uses FastAPI + Claude for AI features

---

## Part 2: The 9 Flows

| # | Flow | Status | Description |
|---|------|--------|-------------|
| 1 | **Ingest** | Active | Unzip uploaded files, detect types, create catalogs |
| 2 | **Code Analysis** | Active | Parse COBOL structure, AI analysis |
| 3 | **Code Refactor** | Skip (Redo Later) | Find refactor patterns in COBOL |
| 4 | **Dependency Mapper** | Active | Map COBOL dependencies (CALL, COPY) |
| 5 | **Monolith Analysis** | Active | Identify monolith patterns |
| 6 | **Data Analyzer** | Maybe Skip | Data-focused analysis (may overlap with Ingest) |
| 7 | **Discovery** | Active | Business process discovery, RPI analysis |
| 8 | **Architecture Recommender** | Active | AWS architecture recommendations |
| 9 | **Application Creator** | Active | Generate Java from all flow outputs |

---

## Part 3: AWS API Contract (From Postman Collections)

### 3.1 Postman V2 Collection (`aws-workflow-v2.postman_collection.json`)

#### Flow 1: Ingest
```
POST /ingest/upload
  Body: multipart/form-data
    - file: <zip file>
    - scout_account_id: "0U812"
    - application_name: "TestApp01"
```

#### Flow 2: Code Analysis V2
```
POST /codeanalysis2
  Body: {"scout_account_id": "0U812", "application_name": "TestApp01"}

GET /statusv2/{job_id}
  Example: /statusv2/ca2_job_0U812_TestApp01_1762171676_f3a7c61d

GET /resultsv2/{job_id}
GET /resultsv2/{job_id}?section=summary
GET /resultsv2/{job_id}?section=analysis_text
```

#### Flow 3: Code Refactor V2
```
POST /coderefactor2
  Body: {"scout_account_id": "0U812", "application_name": "TestApp01"}

GET /statusrf2/{job_id}
GET /resultsrf2/{job_id}
GET /resultsrf2/{job_id}?section=analysis_text
```

#### Flow 4: Dependency Mapper V2
```
POST /dependencymapperv2
  Body: {"scout_account_id": "0U812", "application_name": "TestApp01"}

GET /statusdmv2/{job_id}
GET /resultsdmv2/{job_id}?section=all
GET /resultsdmv2/{job_id}?section=dependency_graph
GET /resultsdmv2/{job_id}?section=analysis_text
```

#### Flow 5: Monolith Identifier V2
```
POST /monolithidentifierv2
  Body: {"scout_account_id": "0U812", "application_name": "TestApp01"}

GET /statusmiv2/{job_id}
GET /resultsmiv2/{job_id}?section=static_analysis
GET /resultsmiv2/{job_id}?section=patterns
GET /resultsmiv2/{job_id}?section=analysis_text
```

#### Flow 6: Data Analyzer V2
```
POST /dataanalysis2
  Body: {"scout_account_id": "0U812", "application_name": "TestApp01"}

GET /statusda2/{job_id}
GET /resultsda2/{job_id}
GET /resultsda2/{job_id}?section=erd
GET /resultsda2/{job_id}?section=analysis_text
```

#### Flow 7: Discovery V2
```
POST /discovery2
  Body: {"scout_account_id": "0U812", "application_name": "TestApp01"}

GET /statusdv2/{job_id}
GET /resultsdv2/{job_id}
GET /resultsdv2/{job_id}?section=analysis_text
```

#### Flow 8: Architecture Recommender V2
```
POST /startar2
  Body: {"scout_account_id": "0U812", "application_name": "TestApp01"}

GET /statusar2/{job_id}
GET /resultsar2/{job_id}
GET /resultsar2/{job_id}?section=summary
GET /resultsar2/{job_id}?section=cost
GET /resultsar2/{job_id}?section=analysis_text
```

#### Flow 9: Application Creator (Java Gen V2)
```
POST /startjgv2
  Body: {"scout_account_id": "0U812", "application_name": "TestApp01"}

GET /statusjgv2/{job_id}
GET /resultsjgv2/{job_id}
```

### 3.2 Postman V3 Collection (`aws-workflow3.postman_collection.json`)

#### Code Analysis V3
```
POST /codeanalysis3
  Body: {"scout_account_id": "0U812", "application_name": "TestApp01"}

GET /statusv3/{job_id}
GET /resultsv3/{job_id}/{file_name}
  Example: /resultsv3/ca3_job_0U812_TestApp01_1762439063_c998bcd9/CMCMCL00.CBL
```

#### Java Generation V3 (3-Phase)
```
# Phase 1: Start Generation
POST /startjgv3
  Body: {"scout_account_id": "0U812", "application_name": "TestApp01"}

GET /statusjgv3/{job_id}

# Phase 2: Analysis
POST /analyzejgv3
  Body: {"job_id": "jgv3_job_...", "scout_account_id": "0U812", "application_name": "TestApp01"}

GET /statusanalyzejgv3/{job_id}

# Phase 3: Finalization
POST /finalizejgv3
  Body: {"job_id": "jgv3_job_...", "scout_account_id": "0U812", "application_name": "TestApp01"}

GET /resultsjgv3/{job_id}
```

---

## Part 4: Job ID Patterns

| Flow | Job ID Pattern | Example |
|------|----------------|---------|
| Ingest | `ingest_job_{account}_{app}_{timestamp}_{hash}` | `ingest_job_0U812_TestApp01_1762171676_f3a7c61d` |
| Code Analysis V2 | `ca2_job_{account}_{app}_{timestamp}_{hash}` | `ca2_job_0U812_TestApp01_1762171676_f3a7c61d` |
| Code Analysis V3 | `ca3_job_{account}_{app}_{timestamp}_{hash}` | `ca3_job_0U812_TestApp01_1762386684_bd1c9cb9` |
| Code Refactor V2 | `rf2_job_{account}_{app}_{timestamp}_{hash}` | `rf2_job_5150_TestApp01_1759415884_32f02ab8` |
| Dependency Mapper V2 | `dmv2_job_{account}_{app}_{timestamp}_{hash}` | `dmv2_job_5150_TestApp01_1759504109_b279b36e` |
| Monolith V2 | `miv2_job_{account}_{app}_{timestamp}_{hash}` | `miv2_job_5150_TestApp01_1759515630_f9fa1ca8` |
| Data Analyzer V2 | `da2_job_{account}_{app}_{timestamp}_{hash}` | `da2_job_5150_TestApp01_1759516999_d3ec203d` |
| Discovery V2 | `dv2_job_{account}_{app}_{timestamp}_{hash}` | `dv2_job_5150_TestApp01_1759493926_75ae5869` |
| Architecture V2 | `ar2_job_{account}_{app}_{timestamp}_{hash}` | `ar2_job_0U812_TestApp01_1762405045_68886275` |
| Java Gen V2 | `jgv2_job_{account}_{app}_{timestamp}_{hash}` | `jgv2_job_5150_TestApp01_1759705519_8ef89c0c` |
| Java Gen V3 | `jgv3_job_{account}_{app}_{timestamp}_{hash}` | `jgv3_job_0U812_TestApp01_1762440725_142a562d` |

---

## Part 5: S3 Output Structure

### 5.1 Top-Level Structure
```
code-transformation-v2/
└── {account_id}/                    # e.g., "0U812"
    └── {application_name}/          # e.g., "TestApp01"
        ├── shared/
        │   ├── uploads/             # Raw uploaded files
        │   └── catalogs/            # File catalogs from Ingest
        │       └── {source_hash}/
        ├── code_analysis_v2/
        │   └── jobs/{job_id}/
        ├── code_analysis_v3/
        │   └── jobs/{job_id}/
        ├── code_refactor_v2/
        │   └── jobs/{job_id}/
        ├── dependency_mapper_v2/
        │   └── jobs/{job_id}/
        ├── monolith_identifier_v2/
        │   └── jobs/{job_id}/
        ├── data_analysis_v2/
        │   └── jobs/{job_id}/
        ├── discovery_v2/
        │   └── jobs/{job_id}/
        ├── architecture_v2/
        │   └── jobs/{job_id}/
        └── java_generation_v3/
            └── jobs/{job_id}/
```

### 5.2 Job Folder Structure (Common Pattern)
```
{job_id}/
├── status.json              # Job status tracking
├── job_info.json            # Job metadata
├── artifacts/               # Output artifacts
│   ├── static_analysis.json
│   ├── {flow_specific}.json
│   └── ...
└── temp/                    # Intermediate files (optional)
    └── batch_analysis/
```

### 5.3 Key Artifacts by Flow

#### Discovery V2
```
artifacts/
├── business_processes.json
├── api_patterns.json
├── roi_analysis.json
├── migration_roadmap.json
├── integration_points.json
├── ai_discovery_analysis.json
└── ai_discovery_analysis/
    ├── batch_0.json
    ├── batch_1.json
    └── ...
```

#### Dependency Mapper V2
```
artifacts/
├── dependency_graph.json
├── microservice_boundaries.json
├── impact_analysis.json
├── risk_assessment.json
├── coupling_metrics.json
├── static_analysis.json
└── ai_dependency_analysis.json
```

#### Java Generation V3
```
artifacts/
├── ModernizedApplication/
│   ├── src/main/java/com/modernized/{app}/
│   │   ├── entities/
│   │   ├── services/
│   │   ├── repositories/
│   │   └── controllers/
│   ├── src/main/resources/
│   │   └── application.yml
│   ├── src/test/java/
│   ├── pom.xml
│   ├── Dockerfile
│   └── README.md
└── {job_id}_ModernizedApplication.zip
```

---

## Part 6: IBM watsonx Code Assistant Reference

### 6.1 Two-Tool Architecture
| Tool | Interface | Purpose |
|------|-----------|---------|
| Refactoring Assistant for IBM z/OS | Web browser | Dependency visualization, paragraph analysis, workbook creation |
| IBM watsonx Code Assistant for Z | VS Code extension | Java class/method generation from COBOL |

### 6.2 Key Features to Match

1. **Dependency Graph Visualization**
   - Node types: Programs, Copybooks, DB2 Tables, Queues, Screens
   - Edge types: CALL, COPY, DB access, MQ connections
   - Properties panel with incoming/outgoing references

2. **Paragraph Identification**
   - Extract logical units from COBOL programs
   - Rank by importance
   - Preview source code

3. **Workbook Concept**
   - Group related code blocks for selective conversion
   - Import/export configurations
   - Tag and organize work

4. **Name Mapping**
   - COBOL name → Java name mapping
   - Editable by user
   - Categories: programs, copybooks, tables

5. **Class Generation**
   - Programs → Service classes
   - Copybooks → DTOs
   - Tables → JPA Entities

6. **Method Generation**
   - Paragraphs → Java methods
   - AI-assisted implementation
   - User review and rating

### 6.3 IBM Generated Output Structure
```
demo/
├── Customer.java           # JPA Entity (from table)
├── CustomerRequest.java    # Service class (from program)
├── CustomerSecure.java     # JPA Entity
├── ErrorHandler.java       # Utility
├── JdbcConnection.java     # Utility
├── Policy.java             # JPA Entity
└── Request.java            # Base class
```

### 6.4 COBOL to Java Mappings (Reference)

| COBOL | Java |
|-------|------|
| `PIC X(n)` | `String` |
| `PIC 9(n)` | `int` / `long` |
| `PIC 9(n)V9(m)` | `BigDecimal` |
| `PIC S9(n) COMP` | `int` |
| `PIC S9(n) COMP-3` | `BigDecimal` |
| Program | Service class |
| Copybook | DTO/POJO |
| Paragraph | Method |
| EXEC SQL | JDBC PreparedStatement |
| EXEC CICS LINK | Service call |

---

## Part 7: Current modernizeit-api State

### 7.1 What's Working
| Component | Status | Notes |
|-----------|--------|-------|
| FastAPI App | ✅ | Clean entry point, CORS, health checks |
| Ingest Flow | ✅ | `POST /ingest/upload` - fully wired |
| Code Analysis V3 | ✅ | `POST /codeanalysis3` - 4 lambdas |
| Job Tracking | ✅ | SQLite DB (`db/jobs.py`) |
| LocalLambdaExecutor | ✅ | S3→filesystem redirection |
| AWS Creds | ✅ | Loads from `aws_creds/` |

### 7.2 Folder Structure
```
modernizeit-api/
├── main.py                    # FastAPI entry point
├── api/
│   ├── models/                # Pydantic models
│   └── routes/                # Ingest + CA3 routes
├── engines/
│   ├── ingest/                # Ingest engine
│   └── code_analysis_v3/      # CA3 engine with 4 lambdas
├── execution/                 # LocalLambdaExecutor
├── db/                        # SQLite job tracking
├── config/                    # Settings
├── tmp_code_analysis_flow/    # CRUFT - delete
├── tmp_java_generation_flow/  # Staged but not wired
├── dont_us/                   # CRUFT - delete
└── docs/                      # Documentation
```

### 7.3 Cleanup Needed
| Folder | Action | Reason |
|--------|--------|--------|
| `tmp_code_analysis_flow/` | DELETE | Redundant with engines/code_analysis_v3/lambdas/ |
| `tmp_code_analysis_flow.zip` | DELETE | Old staging artifact |
| `dont_us/` | DELETE | Old ingest reference files |
| `*_backup.py` files | CLEAN | 20+ backup versions in java_gen |

---

## Part 8: Target Stack

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend                          │
│         (Eventually Electron desktop app)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Backend                          │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Ingest  │  │   Code   │  │Dependency│  │  Java    │   │
│  │  Router  │  │ Analysis │  │  Mapper  │  │   Gen    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Engine Layer                            │   │
│  │  (Flow execution, Lambda orchestration)             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Storage Abstraction                        │   │
│  │  (S3-compatible API, local filesystem)              │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              AI Integration                          │   │
│  │  (Claude via Bedrock, local MCP servers)            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 9: Open Design Questions

### Q1: Clean Start vs Evolve?
- **Option A:** New `modernizeit-api-v2/` with clean architecture
- **Option B:** Clean up existing, add missing flows

### Q2: Flow Execution Pattern
- **Option A:** Direct Python execution (current approach)
- **Option B:** Worker queue with background jobs
- **Option C:** Async with progress callbacks

### Q3: Storage Abstraction
- **Option A:** Direct filesystem (current)
- **Option B:** S3-compatible interface (future AWS migration easy)

### Q4: AI Integration
- **Option A:** AWS Bedrock only
- **Option B:** Claude API direct
- **Option C:** Local MCP servers (future Electron stack)

### Q5: Which Flows First?
Priority order to implement:
1. Ingest (have it)
2. Code Analysis V3 (have it)
3. Dependency Mapper V2 (needed for graphs)
4. Discovery V2 (needed for business analysis)
5. Java Generation V3 (the big one)
6. Others as needed

---

## Part 10: Next Steps

1. [ ] **DECISION:** Clean start or evolve existing?
2. [ ] **DESIGN:** Finalize folder structure
3. [ ] **CLEANUP:** Remove cruft from existing
4. [ ] **IMPLEMENT:** Add missing flows in priority order
5. [ ] **TEST:** Verify AWS contract compatibility
6. [ ] **DOCUMENT:** API documentation with OpenAPI

---

## Appendix A: AWS Gateway Endpoints (Production)

| Gateway | Base URL |
|---------|----------|
| Main V2 | `https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod` |
| Java Gen V2 | `https://msir2392qb.execute-api.us-east-1.amazonaws.com/prod` |
| Java Gen V3 | `https://5h05yf71l0.execute-api.us-east-1.amazonaws.com/prod` |

---

## Appendix B: Common Request/Response Patterns

### Standard Start Request
```json
{
  "scout_account_id": "0U812",
  "application_name": "TestApp01"
}
```

### Standard Status Response
```json
{
  "job_id": "ca3_job_0U812_TestApp01_1762386684_bd1c9cb9",
  "status": "COMPLETED",
  "created_at": "2025-12-17T10:00:00Z",
  "updated_at": "2025-12-17T10:05:00Z"
}
```

### Standard Results Response
```json
{
  "job_id": "...",
  "flow_type": "codeanalysis3",
  "status": "completed",
  "artifacts_path": "/path/to/artifacts",
  "available_sections": ["summary", "structure", "files"]
}
```

---

*Document Status: Analysis Complete - Ready for Design Discussion*
