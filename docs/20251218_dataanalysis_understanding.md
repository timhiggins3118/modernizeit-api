# Data Analysis V2 - Understanding Document

**Date:** 2025-12-18
**Status:** Analysis Complete
**Purpose:** Understand Data Analysis V2 reference implementation before building our version

---

## 1. Executive Summary

Data Analysis V2 is a multi-source data intelligence pipeline that analyzes COBOL data structures to generate:
- Entity-Relationship Diagrams (ERD)
- Data Lineage graphs
- Copybook dependencies
- Type mappings for database design

**Key Architecture:** Three parallel analysis branches (Regex + AST + AI) that converge into ERD generation.

**Processing Time:** ~2 minutes for 20 COBOL files

---

## 2. Reference Implementation Location

```
/references/aws_archV5/6.DataAnalysisV2/
├── DATA_ANALYSIS_V2_HLD.md           # High-Level Design (2199 lines)
├── lambda_functions/
│   ├── DataAnalysisV2StartJob/       # POST /dataanalysis2
│   ├── DataAnalysisV2PrepareDataBatches/
│   ├── DataAnalysisV2RegexDataExtractor/  # Branch 1: Regex
│   ├── DataAnalysisV2ASTDataAnalyzer/     # Branch 2: AST
│   ├── DataAnalysisV2BedrockAnalyzerBatch/ # Branch 3: AI
│   ├── DataAnalysisV2MergeDataBatches/
│   ├── DataAnalysisV2ERDGenerator/        # Merge point
│   ├── DataAnalysisV2StatusAPI/      # GET /statusda2/{job_id}
│   └── DataAnalysisV2ResultsAPI/     # GET /resultsda2/{job_id}
└── sample_outputs/
    └── artifacts/
        ├── data_structures.json      # 150KB - Regex output
        ├── hierarchical_structures.json  # 126KB - AST output
        ├── ai_data_analysis.json     # 52KB - AI output
        ├── erd.json                  # 125KB - Combined ERD
        ├── data_lineage.json         # 13KB - Data flows
        └── copybook_analysis.json    # 18KB - Copybook deps
```

---

## 3. Architecture Overview

### 3.1 Step Functions Workflow

```
┌─────────────────┐
│   StartJob      │
│ (create job_id) │
└───────┬─────────┘
        │
        ▼
┌─────────────────┐
│ PrepareDataBatches │
│ (split files)      │
└───────┬─────────┘
        │
        ▼
┌───────────────────────────────────────────────────┐
│                PARALLEL EXECUTION                  │
├─────────────┬─────────────────┬───────────────────┤
│   Branch 1  │    Branch 2     │     Branch 3      │
│   REGEX     │      AST        │       AI          │
│             │                 │   (Map: 40 batch) │
├─────────────┼─────────────────┼───────────────────┤
│ PIC clauses │ Hierarchical    │ Business entities │
│ FD entries  │ structure       │ Relationships     │
│ COPY stmts  │ Key detection   │ Data lineage      │
│ OCCURS/     │ Record grouping │ Normalization     │
│ REDEFINES   │                 │ Quality issues    │
└─────────────┴─────────────────┴───────────────────┘
        │               │               │
        └───────────────┼───────────────┘
                        ▼
              ┌─────────────────┐
              │ MergeDataBatches │
              │ (combine AI)     │
              └───────┬─────────┘
                      │
                      ▼
              ┌─────────────────┐
              │  ERDGenerator    │
              │ (combine all 3)  │
              └───────┬─────────┘
                      │
                      ▼
              ┌─────────────────┐
              │    OUTPUTS       │
              │ erd.json         │
              │ data_lineage.json│
              │ copybook_analysis│
              └─────────────────┘
```

### 3.2 Lambda Functions

| Lambda | Purpose | Input | Output |
|--------|---------|-------|--------|
| StartJob | Create job, trigger workflow | scout_account_id, application_name | job_id, status |
| PrepareDataBatches | Split files into batches | job_id, source_hash | batches (5 files each) |
| RegexDataExtractor | Fast pattern matching | COBOL files | data_structures.json |
| ASTDataAnalyzer | Hierarchical parsing | COBOL files | hierarchical_structures.json |
| BedrockAnalyzerBatch | AI analysis (parallel) | batch of files | ai_data_analysis/batch_N.json |
| MergeDataBatches | Combine AI batches | batch results | ai_data_analysis.json |
| ERDGenerator | Combine all sources | all 3 outputs | erd.json, data_lineage.json, copybook_analysis.json |
| StatusAPI | Job status | job_id | state, progress, counts |
| ResultsAPI | Get results | job_id, section? | ERD, lineage, copybooks |

---

## 4. API Contracts

### 4.1 POST /dataanalysis2 (Start Job)

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
  "job_id": "da2_job_EVH_TestApp01_1734567890_abc12345",
  "source_hash": "abc123def456",
  "status": "pending",
  "workflow_execution_arn": "arn:aws:states:...",
  "paths": {
    "job_root": "s3://code-transformation-v2/.../",
    "artifacts": "s3://.../{job_id}/artifacts/"
  },
  "next_steps": [
    "Check status: GET /statusda2/{job_id}",
    "Get results: GET /resultsda2/{job_id}"
  ]
}
```

### 4.2 GET /statusda2/{job_id}

**Response (200):**
```json
{
  "job_id": "da2_job_...",
  "status": "completed",
  "progress": 100,
  "phase": "completed",
  "started_at": "2025-12-18T10:00:00Z",
  "completed_at": "2025-12-18T10:02:15Z",
  "has_results": true,
  "results_url": "/resultsda2/{job_id}",
  "entities_discovered": 34,
  "relationships_discovered": 0
}
```

**Progress Map:**
- pending: 0%
- data_analysis: 40%
- erd_generation: 80%
- completed: 100%
- failed: -1

### 4.3 GET /resultsda2/{job_id}?section=

**Section Options:**
- `erd` - Entity-Relationship Diagram
- `data_lineage` - Data flow tracking
- `copybooks` - Copybook dependencies
- `summary` - High-level counts
- `analysis_text` - Markdown report

**Full Response (200):**
```json
{
  "job_id": "da2_job_...",
  "analysis_completed_at": "2025-12-18T10:02:15Z",
  "report_data": {
    "erd": { ... },
    "data_lineage": { ... },
    "copybook_analysis": { ... }
  },
  "available_sections": ["erd", "data_lineage", "copybooks", "summary"]
}
```

---

## 5. Output Artifacts

### 5.1 data_structures.json (Regex Output)

```json
{
  "job_id": "da2_job_...",
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
          "data_type": "alphanumeric",
          "length": 10
        }]
      }],
      "file_section": [{
        "fd_name": "INPUT-FILE",
        "statement": "FD INPUT-FILE..."
      }],
      "linkage_section": [...],
      "copybooks": [{
        "copybook_name": "STDPROCESS",
        "statement": "COPY STDPROCESS."
      }]
    }
  }]
}
```

### 5.2 hierarchical_structures.json (AST Output)

```json
{
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
      "data_type": "VARCHAR",
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

### 5.3 ai_data_analysis.json (AI Output)

```json
{
  "summary": {
    "total_batches": 4,
    "total_files_analyzed": 20
  },
  "file_analyses": [{
    "file_path": "CMCSCL50.CBL",
    "analysis": {
      "analysis_text": "## Business Entity Identification\n- Entity: Claim (Confidence: 0.95)\n  - COBOL Record: CMFHCL00\n  - Suggested Table: claims\n  - Business Purpose: Represents workers' compensation claims\n  - Attributes: clprefix, clsuffix, clnumber (composite PK)\n\n## Relationship Discovery\n- Claim → Risk (Confidence: 0.85)\n  - Type: many-to-one\n  - Business Rule: Each claim is associated with one risk\n\n## Data Lineage\n- Flow: Claim Evaluation\n  - Source: CMLHCL00-FILE\n  - Transformations: READ → CHECK-CLAIM-TYPE → EVALUATE\n  - Destination: BWC-REP-NEEDED flag\n\n## Normalization Opportunities\n...\n\n## Data Quality Issues\n...",
      "model": "anthropic.claude-3-5-sonnet-20240620-v1:0",
      "agent": "COBOLDataAnalystV2"
    }
  }]
}
```

### 5.4 erd.json (Combined ERD)

```json
{
  "generated_at": "2025-12-18T10:02:15Z",
  "summary": {
    "total_entities": 34,
    "total_relationships": 0
  },
  "entities": [{
    "id": "entity_001",
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
      "data_type": "VARCHAR",
      "is_primary_key": false,
      "nullable": true,
      "source_pic": "X(010)",
      "business_meaning": "Claim identifier field"
    }],
    "confidence": 0.85
  }],
  "relationships": []
}
```

### 5.5 data_lineage.json

```json
{
  "summary": {
    "total_flows": 38
  },
  "flows": [{
    "flow_name": "Claim Evaluation",
    "source_file": "CMLHCL00-FILE",
    "source_type": "indexed_file",
    "transformations": [{
      "operation": "READ",
      "program": "CMCSCL50.CBL",
      "paragraph": "20100-GET-CLAIM-HEADER"
    }],
    "destination_file": "BWC-REP-NEEDED",
    "destination_type": "flag",
    "business_impact": "Determines if BWC rep notification needed"
  }]
}
```

### 5.6 copybook_analysis.json

```json
{
  "summary": {
    "total_copybooks": 125
  },
  "copybooks": [{
    "name": "STDPROCESS",
    "used_by": [
      "DICPCC00.CBL",
      "CMCSCL50.CBL",
      "ADCPSH21.CBL",
      "CMCMCL00.CBL"
    ],
    "data_structures": []
  }]
}
```

---

## 6. Known Issues in Reference Implementation

### 6.1 CRITICAL: Relationship Detection Broken

**Problem:** ERD shows 0 relationships despite AI finding many.

**Root Cause:** `parse_ai_relationships()` in `erd_generator_v2_handler.py` uses fragile regex:
```python
rel_pattern = r'- ([^\n]+) → ([^\n]+) \(Confidence: ([\d.]+)\)\s+- Type: ([^\n]+)...'
```

AI doesn't always output in this exact format. The regex fails silently.

**Evidence:** Sample output shows `"total_relationships": 0` but AI text contains relationship info.

### 6.2 Business Meanings Are Pattern-Based

**Problem:** Business meanings are generic ("Clacpre field" instead of "Claim prefix code").

**Root Cause:** `infer_business_meaning()` uses simple regex patterns instead of AI analysis:
```python
patterns = [
    (r'(_id|^id)$', 'Unique identifier'),
    (r'_key$', 'Key field'),
    ...
]
```

**Better Approach:** Parse business meanings from AI analysis which already has context.

### 6.3 Type Mapping Lacks Precision

**Problem:** `X(50)` maps to `VARCHAR` without length. `9(7)V99` maps to `DECIMAL` without precision/scale.

**Root Cause:** `map_cobol_pic_to_sql()` returns type name only:
```python
if 'X' in pic_upper:
    return 'VARCHAR'  # Should be VARCHAR(50)
```

**Better Approach:** Parse PIC clause fully: `X(50)` → `VARCHAR(50)`, `9(7)V99` → `DECIMAL(9,2)`

### 6.4 AST Isn't Real AST

**Problem:** Called "AST" but it's just line-by-line regex parsing.

**Root Cause:** `ast_data_analyzer_v2_handler.py` does:
```python
if code_line.strip().startswith('01 '):
    # Found 01-level
```

**Impact:** Misses complex structures, nested levels, continuation lines.

### 6.5 Data Lineage Incomplete

**Problem:** Many flows show "Unknown" for source.

**Root Cause:** `parse_ai_data_lineage()` uses fragile regex to parse AI output.

### 6.6 Copybook data_structures Always Empty

**Problem:** `copybook_analysis.json` shows `"data_structures": []` for every copybook.

**Root Cause:** Copybook contents aren't analyzed - only usage is tracked.

---

## 7. What Our Implementation Should Fix

### 7.1 Structured AI Output

Instead of parsing markdown text with regex, use structured prompts:
```python
# Ask AI to return JSON directly
prompt = """
Return your analysis as JSON:
{
  "entities": [...],
  "relationships": [...],
  "data_lineage": [...]
}
"""
```

### 7.2 Proper Type Mapping with Precision

```python
def map_pic_to_sql(pic: str) -> dict:
    """
    X(50) → {"sql_type": "VARCHAR", "length": 50}
    9(7)V99 → {"sql_type": "DECIMAL", "precision": 9, "scale": 2}
    """
```

### 7.3 Use Tree-Sitter for Real AST

We already have tree-sitter in Code Analysis - use it here too.

### 7.4 Preserve AI Business Meanings

Store AI-generated business meanings instead of re-inferring with regex.

### 7.5 Analyze Copybook Contents

Actually parse copybook files, not just track which programs use them.

---

## 8. Proposed Local Implementation

### 8.1 Engine Structure

```
engines/data_analysis/
├── __init__.py
├── runner.py                    # Main orchestrator
├── analyzers/
│   ├── regex_extractor.py       # Branch 1: Regex
│   ├── ast_analyzer.py          # Branch 2: Tree-sitter
│   └── ai_analyzer.py           # Branch 3: Bedrock/local
├── generators/
│   ├── erd_generator.py         # Combine sources
│   ├── lineage_generator.py     # Data flow
│   └── copybook_analyzer.py     # Copybook analysis
└── utils/
    └── type_mapper.py           # PIC → SQL with precision
```

### 8.2 API Routes

```python
# api/routes/data_analysis.py

@router.post("")  # POST /dataanalysis
async def run_data_analysis(request: DataAnalysisRequest):
    """Run data analysis on ingested COBOL files."""

@router.get("/{job_id}/status")
async def get_status(job_id: str):
    """Get job status."""

@router.get("/{job_id}/results")
async def get_results(job_id: str, section: str = None):
    """Get analysis results."""

@router.get("/{job_id}/results/json/{filename}")
async def get_json_artifact(job_id: str, filename: str):
    """Get specific JSON artifact."""
```

### 8.3 Key Improvements

1. **Structured AI Output:** JSON schema instead of markdown parsing
2. **Full Type Mapping:** VARCHAR(50), DECIMAL(9,2), INTEGER
3. **Real AST:** Tree-sitter for accurate structure parsing
4. **Relationship Detection:** Cross-reference entities by field names
5. **Copybook Content:** Parse and include copybook data structures

---

## 9. Next Steps

1. **Design API models** (Pydantic)
2. **Build regex extractor** (port from reference)
3. **Build AST analyzer** (use tree-sitter)
4. **Build AI analyzer** (structured JSON output)
5. **Build ERD generator** (fix relationship detection)
6. **Build API routes**
7. **Test with sample COBOL files**

---

## 10. References

- Reference HLD: `/references/aws_archV5/6.DataAnalysisV2/DATA_ANALYSIS_V2_HLD.md`
- Sample Outputs: `/references/aws_archV5/6.DataAnalysisV2/sample_outputs/artifacts/`
- Lambda Code: `/references/aws_archV5/6.DataAnalysisV2/lambda_functions/`
