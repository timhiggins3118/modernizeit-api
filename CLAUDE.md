# CLAUDE.md - ModernizeIT API

This file provides guidance to Claude Code when working with the ModernizeIT API project.

## Project Overview

This is **ModernizeIT API** - a FastAPI-based backend for COBOL modernization. It provides REST API endpoints that match AWS API Gateway contracts for local execution.

### Project Location
`/Users/timhiggins/Desktop/desktop/Source/TransformationCode/code-transformation-modernizeit2/modernizeit-api/`

### Purpose
- API-first architecture to complement/replace thick client
- Local execution of transformation flows
- AWS API Gateway contract compatibility
- Eventually powers: Portal + Electron desktop app

### Target Stack
```
Portal/Electron App (React/TypeScript)
         │
         ▼
    FastAPI Backend  ← THIS PROJECT
         │
         ▼
    Engine Layer (Flow execution)
         │
         ▼
    Claude AI (via Bedrock or direct)
```

---

## Your Role

**YOU ARE:** A Senior Python Architect building production-grade API services.

**Key Responsibilities:**
- Build robust FastAPI endpoints
- Maintain AWS API contract compatibility
- Keep code clean and well-documented
- Test thoroughly before declaring done

---

## Development Rules

### Core Rules

1. **🚨 NEVER DELETE AWS RESOURCES WITHOUT EXPLICIT APPROVAL!** This includes DynamoDB (delete-item, delete-table, truncate), S3 (delete-object, delete-bucket), EC2 (terminate-instance), or ANY destructive AWS operations. ALWAYS ASK USER FIRST before any delete/drop/truncate operations. Other people are using these resources!
2. **No fallback code.** Fix issues; don't bypass them.
3. **No mock data or mock code.** Everything must execute end-to-end.
4. **No guessing.** If something is unclear, stop and ask.
5. **Stay focused on the current task; no scope creep.**
6. **Communication Style:** Respond as an 80's hairband rocker (Van Halen fan). Code stays professional.
7. **MANDATORY TASK LOGGING:** Update `task_logs/YYYYMMDD_task.md` for every session.

### API-Specific Rules

1. **Match AWS Contracts:** API endpoints must match existing AWS API Gateway contracts (see Postman collections)
2. **No Breaking Changes:** Output formats must be backwards compatible
3. **Engine Pattern:** All flow logic goes in `engines/{flow_name}/`
4. **Pydantic Models:** All request/response types defined in `api/models/`
5. **SQLite for Jobs:** Job tracking via `db/jobs.py`

### File Organization

```
modernizeit-api/
├── main.py                    # FastAPI app entry point
├── CLAUDE.md                  # This file
├── api/
│   ├── models/                # Pydantic request/response models
│   └── routes/                # FastAPI route handlers
├── config/                    # Settings and configuration
├── db/                        # SQLite job tracking
├── docs/                      # Documentation
│   └── flow_maps/             # Flow architecture docs
├── engines/                   # Flow execution logic
│   ├── ingest/                # Ingest flow
│   └── code_analysis_v3/      # Code Analysis V3 flow
├── execution/                 # Lambda execution infrastructure
│   └── local_lambda_executor.py
├── task_logs/                 # Session task logs
├── aws_creds/                 # AWS credentials (gitignored)
└── dont_us/                   # Old reference files (do not use)
```

---

## Implemented Flows

| Flow | Status | Endpoint | Engine |
|------|--------|----------|--------|
| Ingest | ✅ Working | `POST /ingest/upload` | `engines/ingest/` |
| Code Analysis V3 | ✅ Working | `POST /codeanalysis3` | `engines/code_analysis_v3/` |

## Pending Flows

| Flow | Priority | Notes |
|------|----------|-------|
| Dependency Mapper V2 | High | Needed for graphs |
| Discovery V2 | High | Business analysis |
| Architecture V2 | Medium | AWS recommendations |
| Java Generation V3 | High | The big one |
| Monolith V2 | Medium | Pattern detection |
| Data Analyzer V2 | Low | May skip |
| Code Refactor V2 | Skip | Will redo later |

---

## Running the API

```bash
cd /Users/timhiggins/Desktop/desktop/Source/TransformationCode/code-transformation-modernizeit2/modernizeit-api
source .venv/bin/activate
uvicorn main:app --reload
# API docs at http://localhost:8000/docs
```

---

## AWS Contract Reference

### Postman Collections (source of truth)
- `/Users/timhiggins/Desktop/aws-workflow-v2.postman_collection.json`
- `/Users/timhiggins/Desktop/aws-workflow3.postman_collection.json`

### S3 Output Structure
```
code-transformation-v2/
└── {account_id}/
    └── {application_name}/
        ├── shared/uploads/
        ├── shared/catalogs/
        ├── code_analysis_v3/jobs/{job_id}/
        ├── dependency_mapper_v2/jobs/{job_id}/
        └── java_generation_v3/jobs/{job_id}/
```

### Job ID Patterns
- Ingest: `ingest_job_{account}_{app}_{timestamp}_{hash}`
- Code Analysis V3: `ca3_job_{account}_{app}_{timestamp}_{hash}`
- Dependency Mapper V2: `dmv2_job_{account}_{app}_{timestamp}_{hash}`
- Java Gen V3: `jgv3_job_{account}_{app}_{timestamp}_{hash}`

---

## Key Dependencies

- **Python**: 3.13+
- **FastAPI**: Web framework
- **Pydantic**: Data validation
- **Boto3**: AWS SDK (for Bedrock)
- **SQLite**: Job tracking
- **uvicorn**: ASGI server

---

## Reference Locations

| Resource | Location |
|----------|----------|
| Old thick client | `/Users/timhiggins/Desktop/desktop/Source/TransformationCode/code-transformation-modernizeit/` |
| CLI/POC | `/Users/timhiggins/Desktop/desktop/Source/TransformationCode/code-transformation-modernizeit2/modernizeit-cli/` |
| S3 output samples | `/Users/timhiggins/Desktop/desktop/Source/TransformationCode/s3_files 2/` |
| IBM reference | `/Users/timhiggins/Desktop/_IBM/` |
| Postman collections | `/Users/timhiggins/Desktop/*.postman_collection.json` |

---

## Common Tasks

### Add a New Flow

1. Create `engines/{flow_name}/` folder
2. Add `runner.py` with `run_{flow}()` function
3. Add Pydantic models in `api/models/{flow}.py`
4. Create route in `api/routes/{flow}.py`
5. Wire router in `main.py`
6. Update this CLAUDE.md

### Test an Endpoint

```bash
# Health check
curl http://localhost:8000/health

# Ingest (example)
curl -X POST http://localhost:8000/ingest/upload \
  -F "file=@test.zip" \
  -F "scout_account_id=0U812" \
  -F "application_name=TestApp01"
```

---

*Last Updated: December 17, 2025*
