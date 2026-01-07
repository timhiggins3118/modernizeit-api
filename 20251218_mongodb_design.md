# MongoDB Integration Design

**Status:** PLANNING (not building yet)
**Last Updated:** 2024-12-18
**Next Step:** Build Phase 1 after morning review

---

## Design Decisions (Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Line inventory chunking | 2000 lines per chunk | Keeps docs under 1MB, better Atlas UI display, query specific ranges |
| Other collections | Single document | Under 5MB, no chunking needed |
| History retention | 90 days default + pinning | TTL index for auto-cleanup, pin important runs |
| API structure | Reports nested under each flow | Not centralized `/reports` router |
| MongoDB driver | `motor` (async) | Native async for FastAPI |
| Dev environment | Docker locally + Atlas for viewing | User needs Atlas UI access |
| Production | Atlas or self-hosted (TBD) | Decision pending |

---

## Overview

Replace flat JSON files with MongoDB for structured storage, querying, and reporting.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Electron App   │     │   Portal (Web)  │     │   FastAPI API   │
│  (Desktop)      │     │                 │     │                 │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │    FastAPI Backend      │
                    │   (modernizeit-api)     │
                    │                         │
                    │  ┌─────────────────┐    │
                    │  │  MongoDB Client │    │
                    │  │   (Motor/Pymongo)│   │
                    │  └────────┬────────┘    │
                    └───────────┼─────────────┘
                                │
                    ┌───────────▼───────────┐
                    │      MongoDB          │
                    │   (Local or Atlas)    │
                    │                       │
                    │  Collections:         │
                    │  - jobs               │
                    │  - code_analysis      │
                    │  - data_models        │
                    │  - procedures         │
                    │  - refactor_recipes   │
                    │  - dependencies       │
                    │  - architecture       │
                    │  - reports            │
                    └───────────────────────┘
```

## Database Schema

### Database: `modernizeit`

### Collection: `jobs`
Master job tracking - replaces current SQLite jobs.db
```json
{
  "_id": "ca_EVH_TestApp01_20251218_abc123",
  "account_id": "EVH",
  "application": "TestApp01",
  "flow_type": "code_analysis",
  "status": "completed",
  "created_at": "2024-12-18T13:31:00Z",
  "updated_at": "2024-12-18T13:31:45Z",
  "duration_ms": 45000,
  "input": {
    "source_path": "/path/to/cobol",
    "main_program": "IFPR321",
    "options": {}
  },
  "output": {
    "artifacts_path": "/path/to/output",
    "artifact_ids": ["artifact_id_1", "artifact_id_2"]
  },
  "metrics": {
    "files_processed": 5,
    "lines_analyzed": 12500,
    "errors": 0
  }
}
```

### Collection: `code_analysis`
Stores comprehensive parse results, line inventories, cross-references
```json
{
  "_id": "ca_EVH_TestApp01_IFPR321_20251218",
  "job_id": "ca_EVH_TestApp01_20251218_abc123",
  "account_id": "EVH",
  "application": "TestApp01",
  "program": "IFPR321",
  "created_at": "2024-12-18T13:31:00Z",

  "summary": {
    "total_lines": 8500,
    "data_lines": 2100,
    "procedure_lines": 5200,
    "comment_lines": 1200,
    "complexity_score": 45
  },

  "divisions": {
    "identification": { "start_line": 1, "end_line": 15 },
    "environment": { "start_line": 16, "end_line": 85 },
    "data": { "start_line": 86, "end_line": 2186 },
    "procedure": { "start_line": 2187, "end_line": 7387 }
  },

  "files_referenced": ["CUSTFILE", "TRANSLOG", "ERRLOG"],
  "copybooks_used": ["CUSTCPY", "DATECPY", "ERRCPY"],
  "programs_called": ["SUBPGM1", "SUBPGM2"]
}
```

### Collection: `data_models`
Data structures, ERD entities, hierarchical structures
```json
{
  "_id": "dm_EVH_TestApp01_IFPR321_20251218",
  "job_id": "ca_EVH_TestApp01_20251218_abc123",
  "account_id": "EVH",
  "application": "TestApp01",
  "program": "IFPR321",
  "type": "data_model",

  "structures": [
    {
      "name": "WS-CUSTOMER-RECORD",
      "level": "01",
      "section": "WORKING-STORAGE",
      "total_bytes": 256,
      "fields": [
        {
          "name": "WS-CUST-ID",
          "level": "05",
          "picture": "9(10)",
          "bytes": 10,
          "offset": 0,
          "usage": "DISPLAY"
        }
      ]
    }
  ],

  "erd_entities": [
    {
      "name": "Customer",
      "source_structure": "WS-CUSTOMER-RECORD",
      "fields": [],
      "relationships": []
    }
  ]
}
```

### Collection: `procedures`
Procedure models - paragraphs, sections, control flow
```json
{
  "_id": "proc_EVH_TestApp01_IFPR321_20251218",
  "job_id": "ca_EVH_TestApp01_20251218_abc123",
  "account_id": "EVH",
  "application": "TestApp01",
  "program": "IFPR321",

  "sections": [
    {
      "name": "MAIN-PROCESSING",
      "start_line": 2200,
      "end_line": 2500,
      "paragraphs": ["INIT-PARA", "PROCESS-PARA", "CLEANUP-PARA"]
    }
  ],

  "paragraphs": [
    {
      "name": "INIT-PARA",
      "section": "MAIN-PROCESSING",
      "start_line": 2210,
      "end_line": 2250,
      "performs": ["OPEN-FILES", "INIT-COUNTERS"],
      "calls": [],
      "complexity": 3
    }
  ],

  "control_flow": {
    "entry_point": "MAIN-PROCESSING",
    "edges": [
      {"from": "MAIN-PROCESSING", "to": "INIT-PARA", "type": "PERFORM"},
      {"from": "INIT-PARA", "to": "OPEN-FILES", "type": "PERFORM"}
    ]
  }
}
```

### Collection: `line_inventory`
Line-by-line analysis (can be large - use sharding/pagination)
```json
{
  "_id": "lines_EVH_TestApp01_IFPR321_chunk_0",
  "job_id": "ca_EVH_TestApp01_20251218_abc123",
  "program": "IFPR321",
  "chunk_index": 0,
  "chunk_size": 1000,
  "total_lines": 8500,

  "lines": [
    {
      "line_num": 1,
      "original": "       IDENTIFICATION DIVISION.",
      "type": "division_header",
      "division": "IDENTIFICATION",
      "semantic_role": "header"
    }
  ]
}
```

### Collection: `refactor_recipes`
Code refactoring patterns and recipes
```json
{
  "_id": "rf_EVH_TestApp01_20251218",
  "job_id": "rf_EVH_TestApp01_20251218_xyz789",
  "account_id": "EVH",
  "application": "TestApp01",

  "summary": {
    "total_patterns": 45,
    "auto_fixable": 30,
    "manual_review": 15,
    "estimated_effort_hours": 24
  },

  "patterns": [
    {
      "id": "pattern_001",
      "type": "goto_elimination",
      "severity": "HIGH",
      "location": {
        "file": "IFPR321.cbl",
        "line": 3456
      },
      "original_code": "GO TO ERROR-PARA",
      "suggested_fix": "PERFORM ERROR-PARA",
      "auto_fixable": true,
      "confidence": 0.95
    }
  ],

  "recipes": [
    {
      "id": "recipe_001",
      "name": "Extract Error Handler",
      "description": "Extract error handling to separate method",
      "patterns_addressed": ["pattern_001", "pattern_002"],
      "estimated_effort_minutes": 30
    }
  ]
}
```

### Collection: `dependencies`
Dependency maps, coupling analysis
```json
{
  "_id": "dep_EVH_TestApp01_20251218",
  "job_id": "dep_EVH_TestApp01_20251218_def456",
  "account_id": "EVH",
  "application": "TestApp01",
  "source_type": "cobol",

  "programs": [
    {
      "name": "IFPR321",
      "type": "batch",
      "calls_out": ["SUBPGM1", "SUBPGM2"],
      "called_by": ["MAINPGM"],
      "files_used": ["CUSTFILE", "TRANSLOG"],
      "copybooks": ["CUSTCPY"]
    }
  ],

  "coupling_matrix": {
    "IFPR321-SUBPGM1": {"strength": 0.8, "type": "call"},
    "IFPR321-CUSTFILE": {"strength": 0.9, "type": "file_io"}
  },

  "clusters": [
    {
      "name": "Customer Processing",
      "programs": ["IFPR321", "SUBPGM1"],
      "cohesion_score": 0.85
    }
  ]
}
```

### Collection: `architecture`
Architecture recommendations, IaC templates
```json
{
  "_id": "arch_EVH_TestApp01_20251218",
  "job_id": "arch_EVH_TestApp01_20251218_ghi789",
  "account_id": "EVH",
  "application": "TestApp01",

  "recommendations": {
    "compute": {
      "service": "AWS Lambda",
      "confidence": 0.85,
      "evidence": ["Low memory footprint", "Event-driven pattern"]
    },
    "database": {
      "service": "Aurora PostgreSQL",
      "confidence": 0.90,
      "evidence": ["Complex relational data", "ACID required"]
    }
  },

  "cost_estimate": {
    "monthly_total": 450.00,
    "breakdown": {
      "compute": 150.00,
      "database": 250.00,
      "storage": 50.00
    }
  },

  "iac_templates": {
    "cdk_stack": "// CDK code here",
    "terraform": "# Terraform code here"
  }
}
```

### Collection: `reports`
Pre-generated reports for dashboards
```json
{
  "_id": "report_EVH_TestApp01_summary_20251218",
  "account_id": "EVH",
  "application": "TestApp01",
  "report_type": "executive_summary",
  "generated_at": "2024-12-18T14:00:00Z",

  "data": {
    "total_programs": 15,
    "total_lines": 125000,
    "complexity_distribution": {
      "low": 5,
      "medium": 7,
      "high": 3
    },
    "migration_readiness": 0.75,
    "estimated_cost_savings": 250000
  },

  "charts": {
    "complexity_pie": { "type": "pie", "data": {} },
    "lines_by_program": { "type": "bar", "data": {} }
  }
}
```

## Indexes

```javascript
// jobs collection
db.jobs.createIndex({ "account_id": 1, "application": 1 })
db.jobs.createIndex({ "flow_type": 1, "status": 1 })
db.jobs.createIndex({ "created_at": -1 })

// code_analysis collection
db.code_analysis.createIndex({ "job_id": 1 })
db.code_analysis.createIndex({ "account_id": 1, "application": 1, "program": 1 })
db.code_analysis.createIndex({ "programs_called": 1 })

// data_models collection
db.data_models.createIndex({ "job_id": 1 })
db.data_models.createIndex({ "structures.name": 1 })

// procedures collection
db.procedures.createIndex({ "job_id": 1 })
db.procedures.createIndex({ "paragraphs.name": 1 })

// line_inventory collection
db.line_inventory.createIndex({ "job_id": 1, "chunk_index": 1 })
db.line_inventory.createIndex({ "program": 1, "lines.line_num": 1 })

// refactor_recipes collection
db.refactor_recipes.createIndex({ "job_id": 1 })
db.refactor_recipes.createIndex({ "patterns.type": 1 })
db.refactor_recipes.createIndex({ "patterns.severity": 1 })

// dependencies collection
db.dependencies.createIndex({ "job_id": 1 })
db.dependencies.createIndex({ "programs.name": 1 })

// architecture collection
db.architecture.createIndex({ "job_id": 1 })

// reports collection
db.reports.createIndex({ "account_id": 1, "application": 1, "report_type": 1 })
db.reports.createIndex({ "generated_at": -1 })
```

## API Endpoints

### Per-Flow Report Endpoints (NOT centralized)

Each flow owns its own report endpoints. No generic `/reports` router.

```
# Code Analysis - reports nested under existing routes
GET  /codeanalysis/{job_id}/results              # existing
GET  /codeanalysis/{job_id}/results/json/{name}  # existing
GET  /codeanalysis/{job_id}/reports/summary      # NEW - dashboard data
GET  /codeanalysis/{job_id}/reports/complexity   # NEW - chart data
GET  /codeanalysis/{job_id}/reports/lines        # NEW - paginated lines
     ?from=1000&to=2000

# Code Refactor
GET  /coderefactor/{job_id}/reports/patterns     # NEW - paginated patterns
     ?severity=HIGH&auto_fixable=true&page=1

# Dependency Mapper
GET  /dependencymapper/{job_id}/reports/graph    # NEW - D3 graph data

# Data Analysis
GET  /dataanalysis/{job_id}/reports/erd          # NEW - ERD visualization data

# Discovery
GET  /discovery/{job_id}/reports/roi             # NEW - ROI chart data

# Architecture
GET  /architecture/{job_id}/reports/cost         # NEW - cost breakdown chart

# Cross-application query (if needed)
GET  /jobs/{account_id}/{application}/history    # Job timeline
     ?days=90&pinned_only=false
```

### Query Examples

```javascript
// Find all high-complexity paragraphs
db.procedures.aggregate([
  { $match: { account_id: "EVH", application: "TestApp01" } },
  { $unwind: "$paragraphs" },
  { $match: { "paragraphs.complexity": { $gt: 10 } } },
  { $project: {
      program: 1,
      paragraph: "$paragraphs.name",
      complexity: "$paragraphs.complexity",
      line: "$paragraphs.start_line"
  }},
  { $sort: { complexity: -1 } }
])

// Get program call graph
db.dependencies.aggregate([
  { $match: { account_id: "EVH", application: "TestApp01" } },
  { $unwind: "$programs" },
  { $project: {
      from: "$programs.name",
      to: "$programs.calls_out"
  }},
  { $unwind: "$to" }
])

// Refactor pattern summary by type
db.refactor_recipes.aggregate([
  { $match: { account_id: "EVH" } },
  { $unwind: "$patterns" },
  { $group: {
      _id: "$patterns.type",
      count: { $sum: 1 },
      auto_fixable: { $sum: { $cond: ["$patterns.auto_fixable", 1, 0] } }
  }},
  { $sort: { count: -1 } }
])
```

## Implementation Plan

### Phase 1: Core Infrastructure
1. Add `motor` (async MongoDB driver) to dependencies
2. Create `db/mongodb.py` - connection management
3. Create `db/models/` - Pydantic models for each collection
4. Create `db/repositories/` - CRUD operations for each collection

### Phase 2: Migration
1. Update engine runners to save to MongoDB instead of JSON files
2. Keep JSON file export as optional backup
3. Migrate existing JSON data to MongoDB (one-time script)

### Phase 3: Query API
1. Add `/reports` router with query endpoints
2. Implement aggregation pipelines for common queries
3. Add pagination support

### Phase 4: Visualization
1. Add chart data endpoints (D3.js compatible)
2. Implement graph endpoints for ERD, dependencies, control flow
3. Add export endpoints (PNG, SVG, PDF)

## File Structure

```
db/
├── __init__.py
├── mongodb.py           # Connection, client management
├── models/
│   ├── __init__.py
│   ├── job.py
│   ├── code_analysis.py
│   ├── data_model.py
│   ├── procedure.py
│   ├── line_inventory.py
│   ├── refactor.py
│   ├── dependency.py
│   ├── architecture.py
│   └── report.py
├── repositories/
│   ├── __init__.py
│   ├── base.py          # BaseRepository with CRUD
│   ├── job_repo.py
│   ├── code_analysis_repo.py
│   ├── data_model_repo.py
│   ├── procedure_repo.py
│   ├── refactor_repo.py
│   ├── dependency_repo.py
│   ├── architecture_repo.py
│   └── report_repo.py
└── migrations/
    ├── __init__.py
    └── json_to_mongo.py  # One-time migration script

api/routes/
├── reports.py            # New report/query endpoints
└── graphs.py             # Graph/visualization endpoints
```

## Configuration

```python
# config/settings.py additions
class Settings:
    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "modernizeit"
    mongodb_max_pool_size: int = 10

    # For production/Atlas
    # mongodb_uri: str = "mongodb+srv://..."
```

## Deployment Options

### Local Development
- MongoDB Community Server (docker or native)
- Connection: `mongodb://localhost:27017`

### Production (Self-Hosted)
- MongoDB Community Server on EC2/VM
- Connection: `mongodb://server:27017`

### Production (Managed)
- MongoDB Atlas (free tier available)
- Connection: `mongodb+srv://cluster.mongodb.net`

## Docker Compose (Local Dev)

```yaml
version: '3.8'
services:
  mongodb:
    image: mongo:7.0
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      MONGO_INITDB_DATABASE: modernizeit

  modernizeit-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      MONGODB_URI: mongodb://mongodb:27017
      MONGODB_DATABASE: modernizeit
    depends_on:
      - mongodb

volumes:
  mongodb_data:
```

## Questions for Discussion

1. **Line Inventory Chunking**: Should we chunk large line inventories (1000 lines per document) or store as single large documents?

2. **Historical Data**: Keep all job runs or just latest per application?

3. **Real-time Updates**: Do we need change streams for live dashboard updates?

4. **Backup Strategy**: MongoDB dumps vs application-level JSON export?

5. **Atlas vs Self-Hosted**: For production deployment, which is preferred?
