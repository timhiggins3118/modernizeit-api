# ModernizeIT System Architecture - High Level Design

**Created:** December 30, 2025
**Purpose:** Comprehensive system documentation to prevent context loss

---

# STOP. READ THIS FIRST.

## TLDR - The Only Thing You Need to Know

```
Code Analysis → generates Java → Code Refactor → improves it → Java Packaging → ZIP download
```

**That's the flow. Don't overthink it.**

- **Code Analysis generates Java.** (engines/code_analysis/generators/java_generator_clean.py)
- **We fixed it.** 14 fixes. 0 compile errors. BUILD SUCCESS.
- **The Java we fixed IS the Java that gets packaged.**

**If you're confused, re-read this box. The answer is here.**

---

## RULE: ALWAYS FOCUS ON THE FLOW, NOT A TASK

**WRONG:** Fix Code Analysis → declare victory

**RIGHT:** Fix Code Analysis → verify Refactor → verify Packaging → verify DOWNLOAD compiles

**The user downloads from Java Packaging. That's what matters. Test the FULL FLOW.**

---

## CRITICAL: Read This First

**Code Analysis DOES generate Java.** This is step 9 of the 11-step pipeline. The Java then flows to Code Refactor and Java Packaging.

**The flow:**
```
Code Analysis → generates Java → Code Refactor → improves Java → Java Packaging → downloadable ZIP
```

---

## 1. System Overview

ModernizeIT transforms legacy COBOL applications to Java/Spring Boot through a multi-stage pipeline.

```
┌─────────────────────────────────────────────────────────────────┐
│                    MODERNIZEIT PLATFORM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              FRONTEND (modernizeit-ui)                 │    │
│  │              React 19 + Vite + Electron                │    │
│  │                                                        │    │
│  │  • Workflow Designer (drag-drop nodes)                 │    │
│  │  • Code Editor (COBOL read-only, Java read/write)      │    │
│  │  • Phase Views (Analyze, Map, Decompose)               │    │
│  │  • Reports Dashboard                                   │    │
│  └────────────────────────────────────────────────────────┘    │
│                             │                                   │
│                  REST API Calls (Async Job Pattern)             │
│                             ▼                                   │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              BACKEND API (modernizeit-api)             │    │
│  │              FastAPI @ localhost:8000                  │    │
│  │                                                        │    │
│  │  10 Transformation Flows (see Section 3)               │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Directory Structure

### Backend API
```
modernizeit-api/
├── main.py                      # FastAPI entry point
├── CLAUDE.md                    # Development rules
├── api/
│   ├── models/                  # Pydantic request/response models
│   └── routes/                  # FastAPI route handlers
├── engines/                     # Flow execution logic
│   ├── code_analysis/           # THE MAIN ENGINE - generates Java
│   ├── code_refactor/           # Improves generated Java
│   ├── dependency_mapper/       # Builds dependency graphs
│   ├── monolith_identifier/     # Detects microservice boundaries
│   ├── data_analysis/           # ERD and data lineage
│   ├── discovery/               # ROI and business analysis
│   ├── architecture/            # AWS recommendations
│   ├── ingest/                  # File upload handling
│   └── ai/                      # Unified AI integration (BedrockAgent)
├── db/                          # SQLite job tracking
├── docs/                        # Documentation (THIS FILE)
└── modernizeit_output/          # All generated output
```

### Frontend UI
```
modernizeit-ui/
├── src/
│   ├── core/                    # Domain entities and ports
│   ├── adapters/                # Database, storage, API adapters
│   ├── hooks/                   # Business logic hooks
│   ├── components/              # React components
│   ├── services/                # API calls and executors
│   └── data/                    # Node registry, mock data
├── docs/                        # UI documentation
└── data/                        # SQLite database (Electron)
```

---

## 3. The 10 Transformation Flows

### Flow Sequence
```
1. Ingest        → Upload and extract COBOL zip files
2. Code Analysis → Parse COBOL, generate Java (11 steps)
3. Code Refactor → Improve generated Java with Spring Boot patterns
4. Dependency Mapper → Build call graphs and coupling metrics
5. Monolith Identifier → Detect patterns, suggest microservices
6. Data Analysis → ERD, data lineage, schema recommendations
7. Discovery    → ROI calculation, business process extraction
8. Architecture → AWS recommendations, IaC generation
9. Java Packaging → Create downloadable Spring Boot ZIP
10. Test Generation → Generate JUnit tests
```

### API Endpoints

| Flow | Endpoint | Method |
|------|----------|--------|
| Ingest | `/ingest/upload` | POST |
| Code Analysis | `/codeanalysis` | POST |
| Code Refactor | `/coderefactor` | POST |
| Dependency Mapper | `/dependencymapper` | POST |
| Monolith Identifier | `/monolithidentifier` | POST |
| Data Analysis | `/dataanalysis` | POST |
| Discovery | `/discovery/analyze` | POST |
| Architecture | `/architecture/analyze` | POST |
| Java Packaging | `/java-packaging/start` | POST |
| Test Generation | `/test-generation/stubs` | POST |

---

## 4. Code Analysis - The Core Engine

**Location:** `engines/code_analysis/`

**THIS IS THE MOST IMPORTANT ENGINE. It generates Java from COBOL.**

### The 11-Step Pipeline

```
Step 1:  Scan COBOL files
Step 2:  Detect main program
Step 3:  Comprehensive parse (tree-sitter) - ALL programs + copybooks
Step 4:  Tree-sitter line inventory (zero-loss parse tree)
Step 5:  DATA division analysis (working storage, files)
Step 6:  PROCEDURE division parsing (paragraphs, sections)
Step 7:  FILE section parsing (file definitions, records)
Step 8:  Semantic modeling (unified data model)
Step 9:  JAVA GENERATION ← THIS IS WHERE JAVA IS CREATED
Step 10: Dependency graphing (call graphs, PNG)
Step 11: Report generation (JSON artifacts)
```

### Key Files

| File | Purpose |
|------|---------|
| `runner.py` | Orchestrates the 11-step pipeline |
| `parsers/comprehensive_parser.py` | Parses all programs + copybooks |
| `parsers/cobol_procedure_parser.py` | Parses PROCEDURE DIVISION |
| `parsers/cobol_data_parser.py` | Parses DATA DIVISION |
| `generators/java_generator_clean.py` | **GENERATES JAVA CODE** |
| `generators/maven_project_generator.py` | Creates Maven project structure |

### Output Location

```
modernizeit_output/code-transformation-v2/{account}/{app}/
└── code_analysis/
    └── generated/
        └── {program}_cbl/           ← GENERATED JAVA PROJECT
            ├── pom.xml
            ├── README.md
            └── src/main/java/
                └── com/modernizeit/generated/
                    └── {PROGRAM}.java    ← THE JAVA FILE
```

---

## 5. Java Flow: Analysis → Refactor → Packaging

### The Complete Path

```
1. Code Analysis generates Java
   └── modernizeit_output/.../code_analysis/generated/{program}_cbl/

2. Code Refactor (optional) improves it
   └── modernizeit_output/.../code_refactor/{class}/output/transformed/

3. Java Packaging creates downloadable ZIP
   └── Reads from code_analysis/generated/ (or code_refactor if available)
   └── Wraps in Spring Boot structure
   └── Creates ZIP for download
```

### Java Packaging Source Selection (from java_packaging.py)

```python
# From _find_source_java_path():
if source == JavaSource.REFACTOR:
    # Try code_refactor first
    refactor_path = base_path / "code_refactor"
    # ... look for transformed output

# Fall back to code_analysis generated output
analysis_path = base_path / "code_analysis" / "generated"
```

**IMPORTANT:** Java Packaging uses the Java from `code_analysis/generated/` - the same Java we fixed to compile.

---

## 6. What We Fixed (December 2025)

### 14 Fixes to Code Analysis

All fixes were in `engines/code_analysis/`:

| Fix | File | Issue |
|-----|------|-------|
| 1 | cobol_procedure_parser.py | Multi-line statements not collected |
| 2 | java_generator_clean.py | GO TO statements commented out |
| 3 | java_generator_clean.py | Hardcoded paragraph stub list |
| 4 | java_generator_clean.py | Hardcoded CALL stub list |
| 5 | runner.py | Copybook paragraphs not merged |
| 6 | cobol_procedure_parser.py | Paragraph header detection fallback |
| 7 | java_generator_clean.py | STRING quoted string parsing |
| 8 | java_generator_clean.py | MULTIPLY numeric literal handling |
| 9 | java_generator_clean.py | ADD operand separator |
| 10 | cobol_procedure_parser.py | Continuation line extraction |
| 11 | cobol_procedure_parser.py | COBOL literal continuation joining |
| 12 | java_generator_clean.py | MULTIPLY int array elements |
| 13 | java_generator_clean.py | COPYBOOK variable/method stubs |
| 14 | java_generator_clean.py | GO TO unreachable code |

### Result

```
Before: 112 compile errors
After:  0 compile errors (BUILD SUCCESS)
```

### Verification

```bash
cd modernizeit_output/code-transformation-v2/0U812/TestApp02/code_analysis/generated/ifpr321_cbl
mvn compile
# BUILD SUCCESS
```

---

## 7. UI Integration

### How UI Triggers Code Analysis

```
1. User drags "Code Analysis" node onto workflow canvas
2. User clicks "Execute Workflow"
3. WorkflowExecutor calls analysisExecutor.js
4. analysisExecutor calls POST /codeanalysis
5. API runs the 11-step pipeline
6. API returns job_id
7. UI polls for completion
8. UI displays results in AnalyzeView
```

### Key UI Files

| File | Purpose |
|------|---------|
| `services/nodeExecutors/analysisExecutor.js` | Calls /codeanalysis API |
| `components/views/AnalyzeView.jsx` | Displays analysis results |
| `services/codeAnalysisService.js` | API helper functions |

---

## 8. Async Job Pattern

All flows follow this pattern:

```
CLIENT                          API
  │                              │
  ├─ POST /endpoint ────────────>│ Start job
  │                              │
  │<────────── 201 ──────────────┤ { job_id, status: "running" }
  │                              │
  ├─ GET /endpoint/{job_id}/status ──>│ Poll
  │                              │
  │<────────── 200 ──────────────┤ { status: "completed" }
  │                              │
  ├─ GET /endpoint/{job_id}/results ──>│ Get results
  │                              │
  │<────────── 200 ──────────────┤ { artifacts: [...] }
```

---

## 9. Output Directory Structure

```
modernizeit_output/
└── code-transformation-v2/
    └── {account_id}/                    # e.g., 0U812
        └── {application_name}/          # e.g., TestApp02
            │
            ├── shared/
            │   └── uploads/
            │       └── {source_hash}/
            │           └── extracted/   # Original COBOL files
            │
            ├── code_analysis/
            │   └── generated/
            │       └── {program}_cbl/   # Generated Java Maven project
            │
            ├── code_refactor/
            │   └── {class}/
            │       └── output/transformed/
            │
            ├── dependency_mapper/
            │   └── {job_id}/
            │       └── dependency_graph.json
            │
            ├── monolith_identifier/
            │   └── {job_id}/
            │       └── decomposition_strategy.json
            │
            ├── data_analysis/
            │   └── {job_id}/
            │       └── erd.json
            │
            ├── discovery/
            │   └── {job_id}/
            │       └── roi_analysis.json
            │
            ├── architecture/
            │   └── {job_id}/
            │       └── architecture_recommendation.json
            │
            └── java_packaging/
                └── jobs/{job_id}/
                    └── *.zip            # Downloadable package
```

---

## 10. Key Facts to Remember

### Code Analysis

1. **Code Analysis generates Java** - Step 9 of 11 steps
2. **Location:** `engines/code_analysis/generators/java_generator_clean.py`
3. **Output:** `code_analysis/generated/{program}_cbl/`
4. **Result:** Single Java file with all COBOL paragraphs as methods
5. **Status:** Compiles with 0 errors after our fixes

### Java Flow

1. Code Analysis creates initial Java
2. Code Refactor improves it (optional)
3. Java Packaging bundles it for download
4. **Our fixes carry through** to the final package

### The Generated Java

- **419 methods** - one per COBOL paragraph
- **8,296 lines** of translated code
- **Line mapping** - every line has `// L:nnn` comment
- **Compiles** with `mvn compile`

### What Stubs Exist

- **COPYBOOK variables** - external files not fully parsed
- **External CALLs** - programs like PZE1XFK need separate conversion
- **GO TO xxx-EXIT** - emitted as comments to avoid unreachable code

---

## 11. Common Commands

### Start API
```bash
cd modernizeit-api
source .venv/bin/activate
uvicorn main:app --reload
# http://localhost:8000/docs
```

### Start UI
```bash
cd modernizeit-ui
npm run dev
# http://localhost:5173
```

### Verify Java Compiles
```bash
cd modernizeit_output/code-transformation-v2/0U812/TestApp02/code_analysis/generated/ifpr321_cbl
mvn compile
```

### Run Full Workflow
1. Start API and UI
2. Upload COBOL ZIP via Ingest
3. Run Code Analysis
4. Run other flows as needed
5. Download package via Java Packaging

---

## 12. Documentation References

| Document | Location | Purpose |
|----------|----------|---------|
| CLAUDE.md | modernizeit-api/ | Development rules |
| FIXES_20251229_FINAL.md | modernizeit-api/docs/ | All 14 fixes documented |
| 20251230_latest_changes.md | modernizeit-api/docs/ | Today's changes |
| HANDOFF_2025-12-19.md | modernizeit-ui/ | UI architecture |
| 2025-12-19_important_flow.md | modernizeit-ui/docs/ | Pipeline overview |

---

## 13. Summary

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│   COBOL Source                                                 │
│        │                                                       │
│        ▼                                                       │
│   ┌─────────────┐                                              │
│   │   INGEST    │  Upload ZIP                                  │
│   └──────┬──────┘                                              │
│          │                                                     │
│          ▼                                                     │
│   ┌─────────────────────────────────────────┐                  │
│   │         CODE ANALYSIS (11 steps)        │                  │
│   │                                         │                  │
│   │  • Parse COBOL (tree-sitter)            │                  │
│   │  • Extract data structures              │                  │
│   │  • Extract procedure logic              │                  │
│   │  • GENERATE JAVA ← Key step             │                  │
│   │  • Create dependency graphs             │                  │
│   └──────┬──────────────────────────────────┘                  │
│          │                                                     │
│          ▼                                                     │
│   ┌─────────────┐                                              │
│   │CODE REFACTOR│  Improve Java (optional)                     │
│   └──────┬──────┘                                              │
│          │                                                     │
│          ▼                                                     │
│   ┌─────────────┐                                              │
│   │JAVA PACKAGE │  Create downloadable ZIP                     │
│   └──────┬──────┘                                              │
│          │                                                     │
│          ▼                                                     │
│   Spring Boot Application                                      │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**The work we did (14 fixes) ensures the Java generated in Code Analysis compiles. That Java flows through to the final downloadable package.**

---

*Last Updated: December 30, 2025*
