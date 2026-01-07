# Data Analysis Flow - Implementation Documentation

**Date:** 2025-12-18
**Status:** Complete
**Flow:** Data Analysis

---

## 1. Overview

Data Analysis is a multi-source data intelligence pipeline that analyzes COBOL data structures to generate:
- Entity-Relationship Diagrams (ERD)
- Data Lineage graphs
- Copybook dependencies
- Type mappings for database design

---

## 2. Architecture

### 2.1 Three-Branch Pipeline

```
┌──────────────────────────────────────────────────────────┐
│                    COBOL Source Files                     │
└──────────────────────────┬───────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   Branch 1      │ │   Branch 2      │ │   Branch 3      │
│  REGEX          │ │   AST           │ │   AI            │
│  EXTRACTOR      │ │   ANALYZER      │ │   ANALYZER      │
├─────────────────┤ ├─────────────────┤ ├─────────────────┤
│ • PIC clauses   │ │ • Hierarchical  │ │ • Business      │
│ • FD entries    │ │   structure     │ │   entities      │
│ • COPY stmts    │ │ • Entity detect │ │ • Relationships │
│ • OCCURS        │ │ • Key fields    │ │ • Data lineage  │
│ • REDEFINES     │ │ • Copybook deps │ │ • Business      │
│ • Type mapping  │ │                 │ │   meanings      │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                  ┌─────────────────────┐
                  │    ERD GENERATOR    │
                  │    (Merge Point)    │
                  ├─────────────────────┤
                  │ • Combine entities  │
                  │ • Enrich types      │
                  │ • Add business ctx  │
                  │ • Build relations   │
                  └──────────┬──────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│    erd.json     │ │ data_lineage    │ │   copybook_     │
│                 │ │    .json        │ │ analysis.json   │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 2.2 Component Summary

| Component | Purpose | Input | Output |
|-----------|---------|-------|--------|
| RegexDataExtractor | Fast pattern extraction | COBOL files | data_structures.json |
| ASTDataAnalyzer | Hierarchical structure | COBOL files | hierarchical_structures.json |
| AIDataAnalyzer | Business context (Claude) | COBOL files | ai_data_analysis.json |
| ERDGenerator | Combine all sources | All 3 outputs | erd.json, data_lineage.json, copybook_analysis.json |

---

## 3. API Endpoints

### 3.1 POST /dataanalysis

Start data analysis on COBOL source code.

**Request:**
```json
{
    "scout_account_id": "EVH",
    "application_name": "TestApp01"
}
```

**Response (201):**
```json
{
    "success": true,
    "job_id": "da_EVH_TestApp01_1734567890",
    "status": "completed",
    "source_path": "/path/to/cobol",
    "artifacts_path": "/path/to/artifacts",
    "duration_ms": 15230,
    "summary": {
        "regex": { "total_files": 20, "total_data_items": 614 },
        "ast": { "total_entities": 34, "total_relationships": 120 },
        "ai": { "total_entities": 30, "total_relationships": 25 },
        "erd": { "total_entities": 34, "total_relationships": 25 }
    },
    "artifacts": {
        "data_structures": "/path/to/data_structures.json",
        "hierarchical_structures": "/path/to/hierarchical_structures.json",
        "erd": "/path/to/erd.json",
        "data_lineage": "/path/to/data_lineage.json",
        "copybook_analysis": "/path/to/copybook_analysis.json"
    }
}
```

### 3.2 GET /dataanalysis/{job_id}/status

Get job status.

**Response:**
```json
{
    "job_id": "da_EVH_TestApp01_1734567890",
    "flow_type": "dataanalysis",
    "status": "completed",
    "artifacts_path": "/path/to/artifacts",
    "created_at": "2025-12-18T10:00:00Z",
    "updated_at": "2025-12-18T10:00:15Z"
}
```

### 3.3 GET /dataanalysis/{job_id}/results

Get results overview.

**Response:**
```json
{
    "job_id": "da_EVH_TestApp01_1734567890",
    "status": "completed",
    "artifacts_path": "/path/to/artifacts",
    "json_artifacts": [
        "ai_data_analysis.json",
        "copybook_analysis.json",
        "data_lineage.json",
        "data_structures.json",
        "erd.json",
        "hierarchical_structures.json"
    ],
    "summary": {
        "erd": { "total_entities": 34, "total_relationships": 25 },
        "data_lineage": { "total_flows": 38 },
        "copybooks": { "total_copybooks": 125 }
    }
}
```

### 3.4 Convenience Endpoints

- `GET /dataanalysis/{job_id}/results/erd` - Get ERD directly
- `GET /dataanalysis/{job_id}/results/lineage` - Get data lineage
- `GET /dataanalysis/{job_id}/results/copybooks` - Get copybook analysis
- `GET /dataanalysis/{job_id}/results/json/{filename}` - Get any artifact

---

## 4. Output Artifacts

### 4.1 data_structures.json (Regex Output)

Fast extraction of data structures.

```json
{
    "generated_at": "2025-12-18T10:00:05Z",
    "summary": {
        "total_files": 20,
        "total_data_items": 614,
        "total_01_levels": 95,
        "total_copybooks": 167
    },
    "files": [{
        "file_path": "CMCSCL50.CBL",
        "data_structures": {
            "working_storage": [{
                "level": "01",
                "name": "SPECIAL-WORK-FIELDS",
                "fields": [{
                    "level": "05",
                    "name": "WK-HW-CLAIM",
                    "pic": "X(010)",
                    "data_type": "VARCHAR(10)",
                    "java_type": "String",
                    "length": 10
                }]
            }],
            "file_section": [...],
            "linkage_section": [...],
            "copybooks": [...]
        }
    }]
}
```

### 4.2 hierarchical_structures.json (AST Output)

Structural analysis with entity/relationship detection.

```json
{
    "generated_at": "2025-12-18T10:00:08Z",
    "summary": {
        "total_entities": 34,
        "total_relationships": 120,
        "copybook_files": 125
    },
    "entities": [{
        "name": "SpecialWorkFields",
        "source_file": "CMCSCL50.CBL",
        "record_name": "SPECIAL-WORK-FIELDS",
        "section": "working_storage",
        "attributes": [{
            "name": "wk_hw_claim",
            "cobol_name": "WK-HW-CLAIM",
            "level": "05",
            "pic": "X(010)",
            "data_type": "VARCHAR(10)",
            "is_potential_key": false
        }]
    }],
    "relationships": [{
        "from_entity": "Entity1",
        "to_entity": "Entity2",
        "relationship_type": "potential_foreign_key",
        "join_field": "claim_id",
        "confidence": 0.7
    }]
}
```

### 4.3 ai_data_analysis.json (AI Output)

Business context from Claude.

```json
{
    "generated_at": "2025-12-18T10:00:12Z",
    "summary": {
        "total_files_analyzed": 20,
        "total_entities": 30,
        "total_relationships": 25
    },
    "entities": [{
        "entity_name": "Claim",
        "cobol_record": "CMFHCL00",
        "business_purpose": "Workers compensation claim record",
        "suggested_table_name": "claims",
        "confidence": 0.95,
        "key_fields": ["clprefix", "clsuffix", "clnumber"]
    }],
    "relationships": [{
        "from_entity": "Claim",
        "to_entity": "Risk",
        "relationship_type": "many-to-one",
        "cardinality": "N:1",
        "business_rule": "Each claim is associated with one risk",
        "confidence": 0.85
    }],
    "business_meanings": {
        "WK-HW-CLAIM": "Claim identifier for hardware claims",
        "CLPREFIX": "Claim prefix code identifying claim type"
    }
}
```

### 4.4 erd.json (Combined ERD)

Final merged ERD with all context.

```json
{
    "generated_at": "2025-12-18T10:00:15Z",
    "job_id": "da_EVH_TestApp01_1734567890",
    "summary": {
        "total_entities": 34,
        "total_relationships": 25,
        "total_attributes": 450,
        "entities_by_section": {
            "working_storage": 28,
            "file_section": 4,
            "linkage_section": 2
        }
    },
    "entities": [{
        "id": "entity_abc12345",
        "name": "SpecialWorkFields",
        "source": {
            "cobol_record": "SPECIAL-WORK-FIELDS",
            "files": ["CMCSCL50.CBL"],
            "section": "working_storage"
        },
        "business_purpose": "Work fields for claim processing",
        "attributes": [{
            "name": "wk_hw_claim",
            "cobol_field": "WK-HW-CLAIM",
            "data_type": "VARCHAR(10)",
            "sql_type": "VARCHAR(10)",
            "length": 10,
            "is_primary_key": false,
            "is_foreign_key": false,
            "nullable": true,
            "source_pic": "X(010)",
            "business_meaning": "Claim identifier for hardware claims"
        }],
        "confidence": 0.85
    }],
    "relationships": [{
        "id": "rel_def67890",
        "from_entity": "Claim",
        "to_entity": "Risk",
        "relationship_type": "foreign_key",
        "cardinality": "N:1",
        "business_rule": "Each claim is associated with one risk",
        "join_field": "risk_id",
        "confidence": 0.85,
        "sources": ["ast_analysis", "ai_analysis"]
    }]
}
```

### 4.5 data_lineage.json

Data flow tracking.

```json
{
    "generated_at": "2025-12-18T10:00:15Z",
    "summary": {
        "total_flows": 38
    },
    "flows": [{
        "flow_name": "Claim Evaluation",
        "source_file": "CMLHCL00-FILE",
        "source_type": "file",
        "transformations": [{
            "operation": "READ",
            "program": "CMCSCL50.CBL",
            "description": "Read claim header"
        }],
        "destination_file": "BWC-REP-NEEDED",
        "destination_type": "flag",
        "business_impact": "Determines if BWC rep notification needed"
    }]
}
```

### 4.6 copybook_analysis.json

Copybook dependencies.

```json
{
    "generated_at": "2025-12-18T10:00:15Z",
    "summary": {
        "total_copybooks": 125
    },
    "copybooks": [{
        "name": "STDPROCESS",
        "used_by": [
            "DICPCC00.CBL",
            "CMCSCL50.CBL",
            "ADCPSH21.CBL"
        ],
        "data_structures": [],
        "total_fields": 0
    }]
}
```

---

## 5. Implementation Files

```
engines/data_analysis/
├── __init__.py
├── runner.py                      # Main orchestrator
├── analyzers/
│   ├── __init__.py
│   ├── regex_extractor.py         # Branch 1: Fast pattern extraction
│   ├── ast_analyzer.py            # Branch 2: Hierarchical analysis
│   └── ai_analyzer.py             # Branch 3: AI business context
├── generators/
│   ├── __init__.py
│   └── erd_generator.py           # Merge point
└── utils/
    ├── __init__.py
    └── type_mapper.py             # COBOL PIC → SQL type mapping

api/
├── models/
│   └── data_analysis.py           # Pydantic models
└── routes/
    └── data_analysis.py           # API endpoints
```

---

## 6. Key Improvements Over Reference

| Issue in Reference | Our Fix |
|--------------------|---------|
| Relationship detection broken (0 relationships) | Properly merge AST + AI relationships |
| Business meanings pattern-based only | Use AI-generated meanings, fallback to patterns |
| Type mapping lacks precision | Full precision: VARCHAR(50), DECIMAL(9,2) |
| Copybook data_structures empty | Auto-detect section context for copybooks without headers |
| Fragile regex parsing of AI output | Structured JSON prompts |
| Junk files in output (__MACOSX, .DS_Store) | Filtered at ingest AND in analyzers |

### 6.1 Junk File Filtering

Junk files (Mac OS artifacts, hidden files) are filtered at two levels:

1. **Ingest (primary)** - `engines/ingest/ingest_upload_handler.py`
   - Filters during ZIP extraction before files are stored
   - Prevents junk from ever entering the system

2. **Data Analysis (safety net)** - `engines/data_analysis/analyzers/`
   - Filters when processing COBOL files
   - Handles legacy data that was ingested before filtering was added

Filtered patterns:
- `__MACOSX/*` - Mac OS resource forks
- `.*` - Hidden files (including `.DS_Store`)
- `Thumbs.db` - Windows thumbnail cache

### 6.2 Copybook Parsing

Copybooks often lack section headers (WORKING-STORAGE SECTION, FILE SECTION) since they're meant to be COPY'd into programs. Our analyzers auto-detect context:

- FD entry at start → assume `file_section`
- 01-level at start → assume `working_storage`

This increased field extraction by **136%** (564 → 1,332 fields) on test data.

---

## 7. Usage Example

```bash
# Start data analysis
curl -X POST http://localhost:8000/dataanalysis \
  -H "Content-Type: application/json" \
  -d '{"scout_account_id": "EVH", "application_name": "TestApp01"}'

# Check status
curl http://localhost:8000/dataanalysis/da_EVH_TestApp01_1734567890/status

# Get ERD
curl http://localhost:8000/dataanalysis/da_EVH_TestApp01_1734567890/results/erd

# Get data lineage
curl http://localhost:8000/dataanalysis/da_EVH_TestApp01_1734567890/results/lineage
```

---

## 8. Dependencies

- boto3 (Bedrock for AI analysis)
- pydantic (API models)
- fastapi (API routes)

---

## 9. Next Steps

After Data Analysis, the remaining flows are:
- Discovery
- Final Optimization
