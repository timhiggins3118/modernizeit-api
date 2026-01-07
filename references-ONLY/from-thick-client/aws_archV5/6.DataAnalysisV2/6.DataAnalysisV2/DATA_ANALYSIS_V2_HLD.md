# Data Analysis V2 - High-Level Design Document

**Flow Name:** Data Analysis V2
**Version:** V2 (Production)
**AWS Account:** 376129851858
**Region:** us-east-1
**Status:** ✅ PRODUCTION (Serving 100+ users)
**Document Created:** November 6, 2025
**Last Updated:** November 6, 2025

---

## Executive Summary

Data Analysis V2 is a **multi-source data intelligence pipeline** that analyzes COBOL data structures using three parallel approaches (Regex, AST, AI) to generate comprehensive Entity-Relationship Diagrams (ERD), data lineage, and database design recommendations. This flow processes COBOL FD (File Definitions), WORKING-STORAGE, and copybook structures to understand legacy data models and prepare them for modernization.

**Key Capabilities:**
- Three-pronged data structure extraction (Regex + AST + AI)
- ERD generation with entities, attributes, and relationships
- Data lineage tracking (source → transformations → destination)
- Copybook analysis and field mapping
- Hierarchical data structure parsing (OCCURS, REDEFINES, levels)
- Business entity identification from COBOL records
- Normalization opportunity detection
- Data quality issue identification

**Processing Speed:** ~2 minutes for 20 COBOL files (4 parallel AI batches)

**Output Artifacts:** 7 comprehensive JSON files (537 KB total)

---

## Architecture Overview

### High-Level Flow

```
API Gateway POST /dataanalysis2
    ↓
StartJob Lambda → Creates job_info.json, starts Step Functions
    ↓
Step Functions: DataAnalysisWorkflowV2
    ↓
┌────────────────────────────────────────────────────────────┐
│  PARALLEL DATA ANALYSIS (3 simultaneous branches)         │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Branch 1: RegexDataExtractor                             │
│    → Pattern-based FD/copybook extraction                 │
│    → Fast, comprehensive structure capture                │
│    → Output: data_structures.json (150 KB)                │
│                                                            │
│  Branch 2: ASTDataAnalyzer                                │
│    → Deep COBOL AST parsing                               │
│    → Hierarchical relationships (OCCURS, REDEFINES)       │
│    → Output: hierarchical_structures.json (126 KB)        │
│                                                            │
│  Branch 3: AI Analysis Pipeline                           │
│    → PrepareDataBatches (creates batches)                 │
│    → BedrockAnalyzerBatch x N (MaxConcurrency: 40)        │
│    → AI entity identification, relationships, lineage     │
│    → MergeDataBatches (combines all AI results)           │
│    → Output: ai_data_analysis.json (52 KB)                │
│                                                            │
└────────────────────────────────────────────────────────────┘
    ↓
ERDGenerator Lambda → Synthesizes all 3 sources
    ↓
Output: erd.json, data_lineage.json, copybook_analysis.json
    ↓
StatusAPI & ResultsAPI → Query job status and results
```

### Component Count
- **Lambda Functions:** 9 (all ZIP-based, Python 3.11)
- **Step Functions:** 1 (DataAnalysisWorkflowV2)
- **Bedrock Agent:** COBOLDataAnalystV2 (TP8XJLYJUM)
- **API Endpoints:** 3 (StartJob, StatusAPI, ResultsAPI)
- **Output Artifacts:** 7 JSON files

---

## Lambda Functions (9 Total)

### 1. DataAnalysisV2StartJob
**Purpose:** API Gateway handler - creates job and triggers Step Functions

**Runtime:** Python 3.11 (ZIP)
**Handler:** `start_data_analysis_v2_handler.lambda_handler`
**Timeout:** 30 seconds
**Memory:** 256 MB

**Input (API Gateway):**
```json
{
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74"
}
```

**Actions:**
1. Generate job ID: `da2_job_{account}_{app}_{timestamp}_{uuid}`
2. Create `job_info.json` in S3
3. Create `status.json` (state: "started")
4. Start Step Functions execution
5. Return job ID to API caller

**Output:**
```json
{
  "job_id": "da2_job_0U812_TestApp01_1762439897_08497588",
  "status": "started"
}
```

**S3 Paths Used:**
- Input: `{base}/shared/uploads/{source_hash}/extracted/` (COBOL files)
- Input: `{base}/shared/catalogs/{source_hash}/classified_catalog.json`
- Output: `{base}/data_analysis_v2/jobs/{job_id}/job_info.json`
- Output: `{base}/data_analysis_v2/jobs/{job_id}/status.json`

**Key Logic:**
- Validates source_hash exists in shared storage
- Creates job metadata with ingest paths
- Initiates asynchronous Step Functions workflow

**Questions/Issues:**
- None identified

---

### 2. DataAnalysisV2PrepareDataBatches
**Purpose:** Split COBOL files into batches for parallel AI analysis

**Runtime:** Python 3.11 (ZIP)
**Handler:** `prepare_data_batches_v2_handler.lambda_handler`
**Timeout:** 60 seconds
**Memory:** 512 MB

**Input (Step Functions):**
```json
{
  "job_id": "da2_job_...",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076..."
}
```

**Actions:**
1. Read `classified_catalog.json` to get COBOL file list
2. Filter to only COBOL files (*.cbl, *.cob, *.CBL, *.COB)
3. Split files into batches (batch size: 5 files)
4. Create batch metadata

**Output:**
```json
{
  "batches": [
    {
      "batch_id": 0,
      "files": ["file1.CBL", "file2.CBL", "file3.CBL", "file4.CBL", "file5.CBL"]
    },
    {
      "batch_id": 1,
      "files": ["file6.CBL", "file7.CBL", ...]
    }
  ],
  "batch_count": 4
}
```

**Batch Strategy:**
- **Batch Size:** 5 files per batch
- **Reason:** Balance between parallelization and Lambda timeout
- **Sample Data:** 20 files → 4 batches

**Key Logic:**
```python
batch_size = 5
batches = []
for i in range(0, len(cobol_files), batch_size):
    batch_files = cobol_files[i:i+batch_size]
    batches.append({
        'batch_id': len(batches),
        'files': batch_files
    })
```

**Questions/Issues:**
- ⚠️ **What if batch_count is 0?** Step Functions has Choice state to skip AI analysis if no batches

---

### 3. DataAnalysisV2RegexDataExtractor
**Purpose:** Fast regex-based extraction of COBOL data structures

**Runtime:** Python 3.11 (ZIP)
**Handler:** `regex_data_extractor_v2_handler.lambda_handler`
**Timeout:** 120 seconds
**Memory:** 1024 MB

**Input:** Same as PrepareDataBatches (job metadata)

**Extraction Patterns:**
1. **FD (File Definitions):** `FD\s+(\w+)` → Identifies file records
2. **Record Structures:** `01\s+(\w+)` → Top-level records
3. **Field Definitions:** Level numbers (02-49) with PIC clauses
4. **Copybooks:** `COPY\s+(\w+)` → Identifies included copybooks
5. **PIC Clauses:** `PIC\s+([X9AVS\(\)\.\,\$\-\+]+)` → Data types

**Output Structure:**
```json
{
  "files": [
    {
      "file_path": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
      "file_definitions": [
        {
          "fd_name": "CMLHCL00-FILE",
          "record_name": "CMFHCL00",
          "fields": [
            {
              "level": "02",
              "name": "CLPREFIX",
              "pic": "X(002)",
              "data_type": "alphanumeric"
            }
          ]
        }
      ],
      "copybooks": ["STATUSCODE", "CMCSCL50L"],
      "working_storage_records": [...]
    }
  ],
  "summary": {
    "total_fds": 150,
    "total_records": 450,
    "total_fields": 2000
  }
}
```

**S3 Output:**
- `{base}/data_analysis_v2/jobs/{job_id}/artifacts/data_structures.json` (150 KB)

**Key Characteristics:**
- **Speed:** Very fast (regex is efficient)
- **Coverage:** Captures all FDs, records, fields
- **Limitations:** No semantic understanding, no relationships
- **Strength:** Comprehensive structural extraction

**Questions/Issues:**
- None identified - regex patterns appear robust

---

### 4. DataAnalysisV2ASTDataAnalyzer
**Purpose:** Deep AST-based COBOL parsing for hierarchical structures

**Runtime:** Python 3.11 (ZIP)
**Handler:** `ast_data_analyzer_v2_handler.lambda_handler`
**Timeout:** 120 seconds
**Memory:** 1024 MB

**Input:** Same as PrepareDataBatches

**AST Parsing:**
1. Parse COBOL source into Abstract Syntax Tree
2. Identify hierarchical relationships (parent-child via level numbers)
3. Detect OCCURS clauses (arrays/repeating groups)
4. Detect REDEFINES clauses (union types/overlapping fields)
5. Build nested structure trees

**Output Structure:**
```json
{
  "files": [
    {
      "file_path": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
      "hierarchical_structures": [
        {
          "parent_record": "CMFHCL00",
          "children": [
            {
              "field": "WK-HW-CLAIM",
              "level": "01",
              "children": [
                {"field": "CLACPRE", "level": "02", "pic": "X(002)"},
                {"field": "CLACSUF", "level": "02", "pic": "X(002)"},
                {"field": "CLACNBR", "level": "02", "pic": "S9(006)"}
              ]
            }
          ]
        }
      ],
      "occurs_clauses": [
        {
          "field": "SOME-ARRAY",
          "occurs_count": 100,
          "parent": "PARENT-RECORD"
        }
      ],
      "redefines_clauses": [
        {
          "field": "FIELD-A",
          "redefines": "FIELD-B",
          "note": "Union type - same memory location"
        }
      ]
    }
  ]
}
```

**S3 Output:**
- `{base}/data_analysis_v2/jobs/{job_id}/artifacts/hierarchical_structures.json` (126 KB)

**Key Characteristics:**
- **Depth:** Deep hierarchical parsing (level 01 → 02 → 03 → ... → 49)
- **Special Handling:** OCCURS (arrays), REDEFINES (unions)
- **Relationship Focus:** Parent-child relationships via level numbers
- **Strength:** Captures nested data structures accurately

**Questions/Issues:**
- ⚠️ **COBOL AST Parser Library:** Which Python library is used? (Check code for imports)

---

### 5. DataAnalysisV2BedrockAnalyzerBatch
**Purpose:** AI-powered data structure analysis per batch using Bedrock Agent

**Runtime:** Python 3.11 (ZIP)
**Handler:** `bedrock_data_analyzer_batch_v2_handler.lambda_handler`
**Timeout:** 300 seconds (5 minutes)
**Memory:** 1024 MB

**Bedrock Configuration:**
- **Agent ID:** TP8XJLYJUM (COBOLDataAnalystV2)
- **Agent Alias:** TSTALIASID
- **Model:** anthropic.claude-3-5-sonnet-20240620-v1:0

**Input (from Map state):**
```json
{
  "job_id": "da2_job_...",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076...",
  "batch": {
    "batch_id": 0,
    "files": ["file1.CBL", "file2.CBL", ...]
  }
}
```

**AI Prompt (per file):**
```
Analyze the data structures in this COBOL file for database design:

FILE: {file_path}

{cobol_content}

Provide:
1. Business Entity Identification
   - Entity name, COBOL record, suggested table name
   - Business purpose and confidence score
   - Key attributes

2. Relationship Discovery
   - Relationships between entities (type, cardinality)
   - Business rules and join fields
   - Confidence scores

3. Data Lineage
   - Source files (READ operations)
   - Transformations (COMPUTE, MOVE, CALL)
   - Destination files (WRITE operations)
   - Business impact

4. Normalization Opportunities
   - Repeated data and redundancy
   - Suggested normalization (1NF, 2NF, 3NF)
   - Benefits of normalization

5. Data Quality Issues
   - Missing constraints (PK, FK, UNIQUE)
   - Data validation rules needed
   - Data type issues or risks
```

**AI Output (per file):**
```json
{
  "file_path": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
  "analysis": {
    "analysis_text": "## Business Entity Identification\n- Entity: Claim (Confidence: 0.95)\n  - COBOL Records: CMFHCL00, CMFDCL50\n  - Suggested Table: claims\n  - Business Purpose: Represents workers' compensation claims\n  - Attributes: clprefix, clsuffix, clnumber (composite PK)\n\n## Relationship Discovery\n- Claim → Risk (Confidence: 0.85)\n  - Type: many-to-one\n  - Business Rule: \"Each claim is associated with one risk (employer)\"\n\n## Data Lineage\n- Flow: Claim Evaluation\n  - Source: CMLHCL00-FILE (Claim Header)\n  - Transformations: Read → Check type → Evaluate risk\n  - Destination: BWC-REP-NEEDED flag\n\n## Normalization Opportunities\n- Claim Identifier Redundancy (clprefix, clsuffix, clnumber)\n  - Suggestion: Create surrogate claim_id\n\n## Data Quality Issues\n- Missing PK constraint on composite key\n- CLTYPE uses positional substrings - normalize to separate fields",
    "model": "anthropic.claude-3-5-sonnet-20240620-v1:0",
    "agent": "COBOLDataAnalystV2"
  }
}
```

**Batch Output:**
```json
{
  "batch_id": 0,
  "files_analyzed": 5,
  "results": [
    { "file_path": "...", "analysis": {...} },
    { "file_path": "...", "analysis": {...} }
  ]
}
```

**S3 Output:**
- `{base}/data_analysis_v2/jobs/{job_id}/artifacts/ai_data_analysis/batch_{batch_id}.json`

**Key Characteristics:**
- **Semantic Understanding:** AI identifies business entities from technical structures
- **Relationship Inference:** Detects implicit relationships from code logic
- **Business Context:** Provides "why" behind data structures
- **Quality Focus:** Identifies normalization and data quality issues
- **Confidence Scores:** AI provides confidence ratings (0.0-1.0)

**Parallel Execution:**
- Map state with **MaxConcurrency: 40**
- 4 batches → 4 concurrent Lambda invocations
- Dramatically reduces total time (5 min → ~1 min with parallelization)

**Questions/Issues:**
- ✅ **Bedrock Agent:** Uses dedicated COBOLDataAnalystV2 agent (not generic analysis agent)
- ⚠️ **Cost:** 40 concurrent Bedrock invocations could be expensive - what's the cost per job?

---

### 6. DataAnalysisV2MergeDataBatches
**Purpose:** Merge all AI batch results into single comprehensive analysis

**Runtime:** Python 3.11 (ZIP)
**Handler:** `merge_data_batches_v2_handler.lambda_handler`
**Timeout:** 60 seconds
**Memory:** 512 MB

**Input (from Map state results):**
```json
{
  "job_id": "da2_job_...",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076...",
  "batch_results": [
    { "batch_id": 0, "files_analyzed": 5, "output_path": "s3://..." },
    { "batch_id": 1, "files_analyzed": 5, "output_path": "s3://..." },
    { "batch_id": 2, "files_analyzed": 5, "output_path": "s3://..." },
    { "batch_id": 3, "files_analyzed": 5, "output_path": "s3://..." }
  ]
}
```

**Actions:**
1. Read all batch files from S3
2. Combine all `results` arrays into single list
3. Calculate summary stats (total files analyzed)
4. Write merged output

**Output:**
```json
{
  "files_analyzed": 20,
  "results": [
    {"file_path": "...", "analysis": {...}},  // Batch 0 results
    {"file_path": "...", "analysis": {...}},  // Batch 1 results
    // ... all batches merged
  ]
}
```

**S3 Output:**
- `{base}/data_analysis_v2/jobs/{job_id}/artifacts/ai_data_analysis.json` (52 KB)

**Key Logic:**
```python
all_results = []
for batch_result in batch_results:
    batch_data = s3_read(batch_result['output_path'])
    all_results.extend(batch_data['results'])

merged = {
    'files_analyzed': len(all_results),
    'results': all_results
}
```

**Questions/Issues:**
- None identified - straightforward merge logic

---

### 7. DataAnalysisV2ERDGenerator
**Purpose:** **THE INTELLIGENCE LAYER** - Synthesizes regex, AST, and AI analysis into unified ERD

**Runtime:** Python 3.11 (ZIP)
**Handler:** `erd_generator_v2_handler.lambda_handler`
**Timeout:** 120 seconds
**Memory:** 1024 MB

**Input:** Same as PrepareDataBatches (job metadata)

**Input Sources (reads 3 artifacts):**
1. `data_structures.json` (150 KB) - Regex extraction
2. `hierarchical_structures.json` (126 KB) - AST parsing
3. `ai_data_analysis.json` (52 KB) - AI analysis

**Synthesis Logic:**

**Step 1: Entity Extraction**
- Read AI analysis for business entity identification
- Read regex data_structures for COBOL record → entity mapping
- Create entity for each FD record and significant WORKING-STORAGE record
- **Source Priority:** AI > Regex (AI provides business context)

**Step 2: Attribute Mapping**
- Read regex data_structures for field lists
- Read hierarchical_structures for parent-child relationships
- Map COBOL fields to entity attributes
- Convert COBOL PIC clauses to SQL data types:
  - `X(n)` → VARCHAR
  - `9(n)` → INTEGER
  - `9(n)V99` or `9(n).99` → DECIMAL
  - `S9(n) COMP` → INTEGER
- Infer business meaning from field names (pattern matching)

**Step 3: Primary Key Inference**
- Look for fields with "ID", "KEY", "NUMBER" in name
- Check AI analysis for explicit PK mentions
- Default: First field or composite key from multiple ID fields

**Step 4: Relationship Detection**
- Read AI analysis for explicit relationship mentions
- Look for foreign key patterns (matching field names across entities)
- Check data lineage for READ/WRITE patterns (source → destination relationships)

**Step 5: Data Lineage Construction**
- Read AI analysis for data flow descriptions
- Parse COBOL READ operations → source files
- Parse COBOL WRITE operations → destination files
- Parse CALL statements → transformation programs
- Build flow: Source → Transform → Destination

**Step 6: Copybook Analysis**
- Read regex data_structures for COPY statements
- Map copybook fields to entities
- Identify shared data structures

**Output Artifacts (7 files):**

**1. erd.json (125 KB)**
```json
{
  "generated_at": "2025-11-06T14:40:30.095305+00:00",
  "summary": {
    "total_entities": 34,
    "total_relationships": 0
  },
  "entities": [
    {
      "id": "entity_001",
      "name": "SpecialWorkFields",
      "source": {
        "cobol_record": "SPECIAL-WORK-FIELDS",
        "files": ["IBMi-Cobol/Cobol/CMCSCL50.CBL"],
        "section": "working_storage"
      },
      "attributes": [
        {
          "name": "wk_hw_claim",
          "cobol_field": "WK-HW-CLAIM",
          "data_type": "VARCHAR",
          "is_primary_key": false,
          "nullable": true,
          "source_pic": "N/A",
          "business_meaning": "Wk Hw Claim field"
        },
        {
          "name": "clacpre",
          "cobol_field": "CLACPRE",
          "data_type": "VARCHAR",
          "is_primary_key": false,
          "nullable": true,
          "source_pic": "X(002)",
          "business_meaning": "Clacpre field"
        }
      ]
    }
  ],
  "relationships": []
}
```

**2. data_lineage.json (13 KB)**
```json
{
  "generated_at": "2025-11-06T14:40:30.096081+00:00",
  "summary": {
    "total_flows": 38
  },
  "flows": [
    {
      "flow_name": "Claim Representative Data Retrieval",
      "source_file": "Unknown (possibly a database or file)",
      "source_type": "unknown",
      "transformations": [
        {
          "operation": "TRANSFORM",
          "program": "IBMi-Cobol/Cobol/CMCSRP00C.CBL",
          "description": "CALL \"CMCSRP00\" USING CMCSRP00-DATA"
        }
      ],
      "destination_file": "CMCSRP00-DATA structure (in-memory)",
      "destination_type": "unknown",
      "business_impact": "Retrieval of claim representative information"
    }
  ]
}
```

**3. copybook_analysis.json (18 KB)**
```json
{
  "generated_at": "2025-11-06T14:40:30.096081+00:00",
  "copybooks": [
    {
      "copybook_name": "STATUSCODE",
      "used_in_files": [
        "IBMi-Cobol/Cobol/CMCSCL50.CBL",
        "IBMi-Cobol/Cobol/ADCPSH21.CBL"
      ],
      "fields": [
        {"name": "STATUS-CODE", "pic": "XX", "usage": "File I/O status"}
      ],
      "entities_mapped": ["StatusCode"]
    }
  ]
}
```

**4-7. (Already documented in previous sections)**
- `data_structures.json` (Regex output)
- `hierarchical_structures.json` (AST output)
- `ai_data_analysis.json` (AI output - merged)
- `ai_data_analysis/batch_*.json` (AI batches - intermediate)

**Key Characteristics:**
- **Multi-Source Synthesis:** Combines strengths of all 3 approaches
- **Business Context:** AI provides "why", Regex provides "what", AST provides "how"
- **Complete Picture:** ERD + Lineage + Copybooks = comprehensive data model
- **SQL-Ready:** Entities/attributes map directly to CREATE TABLE statements

**Type Mapping (COBOL PIC → SQL):**
```python
def map_cobol_pic_to_sql(pic_clause):
    if 'V' in pic or '.' in pic or '$' in pic:
        return 'DECIMAL'
    elif '9' in pic or 'S9' in pic:
        return 'INTEGER'
    elif 'X' in pic or 'A' in pic:
        return 'VARCHAR'
    elif 'COMP' in pic or 'BINARY' in pic:
        return 'INTEGER'
    else:
        return 'VARCHAR'  # Default
```

**Business Meaning Inference:**
```python
patterns = [
    (r'(_id|^id)$', 'Unique identifier'),
    (r'_key$', 'Key field'),
    (r'_number$', 'Number field'),
    (r'_code$', 'Code field'),
    (r'_date$', 'Date field'),
    (r'_amount$', 'Amount field'),
    (r'_name$', 'Name field'),
    (r'_status$', 'Status field'),
    # ... more patterns
]
```

**Questions/Issues:**
- ⚠️ **Why 0 relationships in sample?** ERD shows `"total_relationships": 0` but AI analysis mentions relationships. Is relationship detection not working?
- ⚠️ **Type Mapping Accuracy:** Does type mapping handle all COBOL PIC variations? (COMP-3, PACKED-DECIMAL, etc.)
- ⚠️ **Business Meaning Quality:** Pattern-based meaning is basic ("Clacpre field"). AI analysis has better meanings - why not use those?

---

### 8. DataAnalysisV2StatusAPI
**Purpose:** API Gateway handler - query job status

**Runtime:** Python 3.11 (ZIP)
**Handler:** `data_status_v2_handler.lambda_handler`
**Timeout:** 30 seconds
**Memory:** 256 MB

**Input (API Gateway):**
```
GET /dataanalysis2/status?job_id=da2_job_0U812_TestApp01_1762439897_08497588
```

**Actions:**
1. Read `status.json` from S3
2. Return current job status

**Output:**
```json
{
  "job_id": "da2_job_0U812_TestApp01_1762439897_08497588",
  "state": "completed",
  "phase": "completed",
  "message": "ERD generation completed successfully",
  "outputs": {
    "erd": "s3://code-transformation-v2/0U812/TestApp01/data_analysis_v2/jobs/da2_job_0U812_TestApp01_1762439897_08497588/artifacts/erd.json"
  },
  "started_at": "2025-11-06T14:38:17.999Z",
  "completed_at": "2025-11-06T14:40:30.246Z"
}
```

**Status States:**
- `started` - Job initiated
- `running` - Data analysis in progress
- `erd_generation` - ERD generation phase
- `completed` - All artifacts generated
- `failed` - Error occurred

**Questions/Issues:**
- None identified

---

### 9. DataAnalysisV2ResultsAPI
**Purpose:** API Gateway handler - fetch data analysis results with section filtering

**Runtime:** Python 3.11 (ZIP)
**Handler:** `data_results_v2_handler.lambda_handler`
**Timeout:** 30 seconds
**Memory:** 256 MB

**Input (API Gateway):**
```
GET /dataanalysis2/results?job_id=da2_job_...&section=erd
GET /dataanalysis2/results?job_id=da2_job_...&section=lineage
GET /dataanalysis2/results?job_id=da2_job_...&section=all
```

**Supported Sections:**
- `erd` - Entity-Relationship Diagram (125 KB)
- `lineage` - Data lineage flows (13 KB)
- `copybooks` - Copybook analysis (18 KB)
- `data_structures` - Regex extraction results (150 KB)
- `hierarchical` - AST parsing results (126 KB)
- `ai_analysis` - AI analysis results (52 KB)
- `all` - All artifacts (537 KB total)

**Output Example (section=erd):**
```json
{
  "job_id": "da2_job_...",
  "section": "erd",
  "data": {
    "generated_at": "2025-11-06T14:40:30.095305+00:00",
    "summary": {
      "total_entities": 34,
      "total_relationships": 0
    },
    "entities": [...]
  }
}
```

**Key Logic:**
```python
section_map = {
    'erd': 'artifacts/erd.json',
    'lineage': 'artifacts/data_lineage.json',
    'copybooks': 'artifacts/copybook_analysis.json',
    'data_structures': 'artifacts/data_structures.json',
    'hierarchical': 'artifacts/hierarchical_structures.json',
    'ai_analysis': 'artifacts/ai_data_analysis.json'
}

if section == 'all':
    # Read all artifacts
else:
    # Read specific section
```

**Questions/Issues:**
- None identified - good API design with section filtering

---

## Step Functions Workflow

### DataAnalysisWorkflowV2

**Type:** Standard Workflow
**ARN:** `arn:aws:states:us-east-1:376129851858:stateMachine:DataAnalysisWorkflowV2`

**Input:**
```json
{
  "job_id": "da2_job_0U812_TestApp01_1762439897_08497588",
  "scout_account_id": "0U812",
  "application_name": "TestApp01",
  "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74"
}
```

**Workflow States (14 total):**

```json
{
  "Comment": "Data Analysis V2 Workflow - Multi-source data intelligence",
  "StartAt": "CaptureStartTime",
  "States": {

    "CaptureStartTime": {
      "Type": "Pass",
      "Result": "${CurrentTimestamp}",
      "ResultPath": "$.start_time",
      "Next": "UpdateStatusRunning"
    },

    "UpdateStatusRunning": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:s3:putObject",
      "Parameters": {
        "Bucket": "code-transformation-v2",
        "Key.$": "States.Format('{}/{}/data_analysis_v2/jobs/{}/status.json', $.scout_account_id, $.application_name, $.job_id)",
        "Body": {
          "state": "running",
          "phase": "data_analysis",
          "message": "Performing multi-source data analysis"
        }
      },
      "Next": "ParallelDataAnalysis"
    },

    "ParallelDataAnalysis": {
      "Type": "Parallel",
      "Branches": [
        {
          "StartAt": "RegexDataExtractor",
          "States": {
            "RegexDataExtractor": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:us-east-1:376129851858:function:DataAnalysisV2RegexDataExtractor",
              "End": true
            }
          }
        },
        {
          "StartAt": "ASTDataAnalyzer",
          "States": {
            "ASTDataAnalyzer": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:us-east-1:376129851858:function:DataAnalysisV2ASTDataAnalyzer",
              "End": true
            }
          }
        },
        {
          "StartAt": "PrepareDataBatches",
          "States": {
            "PrepareDataBatches": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:us-east-1:376129851858:function:DataAnalysisV2PrepareDataBatches",
              "ResultPath": "$.batches_data",
              "Next": "CheckBatchCount"
            },

            "CheckBatchCount": {
              "Type": "Choice",
              "Choices": [
                {
                  "Variable": "$.batches_data.batch_count",
                  "NumericEquals": 0,
                  "Next": "SkipAIAnalysis"
                }
              ],
              "Default": "DataAnalyzerMap"
            },

            "SkipAIAnalysis": {
              "Type": "Pass",
              "Result": {
                "message": "No COBOL files to analyze"
              },
              "End": true
            },

            "DataAnalyzerMap": {
              "Type": "Map",
              "ItemsPath": "$.batches_data.batches",
              "MaxConcurrency": 40,
              "Iterator": {
                "StartAt": "BedrockAnalyzerBatch",
                "States": {
                  "BedrockAnalyzerBatch": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:us-east-1:376129851858:function:DataAnalysisV2BedrockAnalyzerBatch",
                    "End": true
                  }
                }
              },
              "ResultPath": "$.batch_results",
              "Next": "MergeDataBatches"
            },

            "MergeDataBatches": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:us-east-1:376129851858:function:DataAnalysisV2MergeDataBatches",
              "End": true
            }
          }
        }
      ],
      "Next": "UpdateStatusERDGeneration"
    },

    "UpdateStatusERDGeneration": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:s3:putObject",
      "Parameters": {
        "Bucket": "code-transformation-v2",
        "Key.$": "States.Format('{}/{}/data_analysis_v2/jobs/{}/status.json', $.scout_account_id, $.application_name, $.job_id)",
        "Body": {
          "state": "running",
          "phase": "erd_generation",
          "message": "Generating ERD and data lineage"
        }
      },
      "Next": "ERDGenerator"
    },

    "ERDGenerator": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:us-east-1:376129851858:function:DataAnalysisV2ERDGenerator",
      "Next": "UpdateStatusCompleted"
    },

    "UpdateStatusCompleted": {
      "Type": "Task",
      "Resource": "arn:aws:states:::aws-sdk:s3:putObject",
      "Parameters": {
        "Bucket": "code-transformation-v2",
        "Key.$": "States.Format('{}/{}/data_analysis_v2/jobs/{}/status.json', $.scout_account_id, $.application_name, $.job_id)",
        "Body": {
          "state": "completed",
          "phase": "completed",
          "message": "ERD generation completed successfully",
          "completed_at.$": "$$.State.EnteredTime"
        }
      },
      "Next": "Success"
    },

    "Success": {
      "Type": "Succeed"
    }
  }
}
```

**Execution Flow:**
1. Capture start time
2. Update status → "running" (data_analysis phase)
3. **PARALLEL EXECUTION (3 branches):**
   - Branch 1: RegexDataExtractor → data_structures.json
   - Branch 2: ASTDataAnalyzer → hierarchical_structures.json
   - Branch 3: PrepareDataBatches → Map (40 concurrent AI analyzers) → MergeDataBatches → ai_data_analysis.json
4. Update status → "running" (erd_generation phase)
5. ERDGenerator → Synthesize all 3 sources → erd.json, data_lineage.json, copybook_analysis.json
6. Update status → "completed"
7. Success

**Parallelization Benefits:**
- **Without Parallel:** 120s (regex) + 120s (AST) + 300s (AI) = 540s (~9 min)
- **With Parallel:** max(120s, 120s, 60s [AI batches]) + 120s (ERD) = ~240s (~4 min)
- **Sample Data:** 2 min 13 sec for 20 files (very fast!)

**Map State Details:**
- **ItemsPath:** `$.batches_data.batches`
- **MaxConcurrency:** 40
- **Iterator:** BedrockAnalyzerBatch Lambda
- **Effect:** Processes up to 40 batches simultaneously

**Choice State Logic:**
```python
if batch_count == 0:
    goto SkipAIAnalysis  # No COBOL files
else:
    goto DataAnalyzerMap  # Process batches
```

**Error Handling:**
- None visible in workflow definition
- **RISK:** If one Lambda fails, entire Parallel state fails
- **Recommendation:** Add Retry and Catch blocks

**Questions/Issues:**
- ⚠️ **No Error Handling:** No Retry or Catch blocks - what happens if Bedrock times out?
- ⚠️ **Parallel State Failure:** If regex fails, does AI analysis still complete? (No - entire Parallel fails)
- ✅ **Choice State:** Good handling of empty batch scenario

---

## Sample Execution Analysis

### Job Details
- **Job ID:** `da2_job_0U812_TestApp01_1762439897_08497588`
- **Account:** 0U812
- **Application:** TestApp01
- **Source Hash:** `9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74`
- **Files Analyzed:** 20 COBOL files
- **Duration:** 2 minutes 13 seconds (133 seconds)

### Timeline
- **Started:** 2025-11-06 14:38:17 UTC
- **Completed:** 2025-11-06 14:40:30 UTC
- **Regex Completion:** ~14:38:20 (3 seconds)
- **AST Completion:** ~14:38:21 (4 seconds)
- **AI Batches:** 14:40:05 - 14:40:28 (23 seconds for 4 batches)
- **ERD Generation:** 14:40:30 (2 seconds)

### Artifacts Generated (7 files, 537 KB)

| Artifact | Size | Records | Purpose |
|----------|------|---------|---------|
| data_structures.json | 150 KB | ~2000 fields | Regex extraction (fast, comprehensive) |
| hierarchical_structures.json | 126 KB | ~450 records | AST parsing (deep relationships) |
| erd.json | 125 KB | 34 entities | ERD (SQL-ready schema) |
| ai_data_analysis.json | 52 KB | 20 files | AI insights (business context) |
| copybook_analysis.json | 18 KB | ~30 copybooks | Copybook field mappings |
| data_lineage.json | 13 KB | 38 flows | Data flow tracking |
| ai_data_analysis/batch_*.json | 53 KB | 4 batches | AI intermediate results |

### Performance Analysis

**Regex Extraction (DataAnalysisV2RegexDataExtractor):**
- **Duration:** ~3 seconds
- **Throughput:** ~6.7 files/second
- **Memory Used:** Unknown (limit: 1024 MB)
- **Result:** 2000+ fields extracted

**AST Parsing (DataAnalysisV2ASTDataAnalyzer):**
- **Duration:** ~4 seconds
- **Throughput:** ~5 files/second
- **Memory Used:** Unknown (limit: 1024 MB)
- **Result:** 450+ hierarchical structures

**AI Analysis (4 batches, 5 files each):**
- **Batch Preparation:** Instant (PrepareDataBatches)
- **Batch Processing:** 23 seconds (parallel execution)
- **Average per Batch:** ~6 seconds
- **Average per File:** ~1.2 seconds
- **Bedrock Model:** Claude 3.5 Sonnet
- **Result:** 20 comprehensive AI analyses

**ERD Generation (DataAnalysisV2ERDGenerator):**
- **Duration:** ~2 seconds
- **Input Size:** 328 KB (3 files)
- **Output Size:** 281 KB (4 files)
- **Entities Generated:** 34

**Overall Performance:**
- **Total Duration:** 133 seconds (2 min 13 sec)
- **Parallelization Speedup:** ~4x faster than sequential
- **Cost Efficiency:** High (batch processing reduces API calls)

### ERD Results

**Entities Identified:** 34
- SpecialWorkFields
- ClaimHeader
- RiskRecord
- ProcessRecord
- StatusCode
- ExtendedStatusCode
- DateConversion
- ClaimRepresentative
- ClientAccount
- ... (25 more entities)

**Relationships Identified:** 0
- **ISSUE:** Sample ERD shows 0 relationships despite AI analysis mentioning multiple relationships
- **Potential Cause:** Relationship detection logic not working? Only implicit relationships in COBOL?

**Sample Entity (SpecialWorkFields):**
```json
{
  "id": "entity_001",
  "name": "SpecialWorkFields",
  "source": {
    "cobol_record": "SPECIAL-WORK-FIELDS",
    "files": ["IBMi-Cobol/Cobol/CMCSCL50.CBL"],
    "section": "working_storage"
  },
  "attributes": [
    {
      "name": "wk_hw_claim",
      "cobol_field": "WK-HW-CLAIM",
      "data_type": "VARCHAR",
      "is_primary_key": false,
      "nullable": true,
      "source_pic": "N/A",
      "business_meaning": "Wk Hw Claim field"
    },
    {
      "name": "clacpre",
      "cobol_field": "CLACPRE",
      "data_type": "VARCHAR",
      "is_primary_key": false,
      "nullable": true,
      "source_pic": "X(002)",
      "business_meaning": "Clacpre field"
    }
  ]
}
```

**Data Lineage Results:**

**Flows Identified:** 38

Sample flows:
- Claim Representative Data Retrieval (CALL "CMCSRP00")
- Date Conversion Processing (CALL "UTCSDC00")
- Address Validation Process
- Upper Case Words Loading (READ UTLMTB00-FILE)
- Claim Header Retrieval (READ CMLHCL00-FILE)

**Sample Flow:**
```json
{
  "flow_name": "Claim Representative Data Retrieval",
  "source_file": "Unknown (possibly a database or file)",
  "source_type": "unknown",
  "transformations": [
    {
      "operation": "TRANSFORM",
      "program": "IBMi-Cobol/Cobol/CMCSRP00C.CBL",
      "description": "CALL \"CMCSRP00\" USING CMCSRP00-DATA"
    }
  ],
  "destination_file": "CMCSRP00-DATA structure (in-memory)",
  "destination_type": "unknown",
  "business_impact": "Retrieval of claim representative information"
}
```

**AI Analysis Sample (Claim Entity):**
```
## Business Entity Identification
- Entity: Claim (Confidence: 0.95)
  - COBOL Records: CMFHCL00, CMFDCL50
  - Suggested Table: claims
  - Business Purpose: Represents workers' compensation claims
  - Attributes: clprefix, clsuffix, clnumber (composite PK)

## Relationship Discovery
- Claim → Risk (Confidence: 0.85)
  - Type: many-to-one
  - Business Rule: "Each claim is associated with one risk (employer)"

## Data Lineage
- Flow: Claim Evaluation
  - Source: CMLHCL00-FILE (Claim Header)
  - Transformations: Read → Check type → Evaluate risk
  - Destination: BWC-REP-NEEDED flag

## Normalization Opportunities
- Claim Identifier Redundancy (clprefix, clsuffix, clnumber)
  - Suggestion: Create surrogate claim_id

## Data Quality Issues
- Missing PK constraint on composite key
- CLTYPE uses positional substrings - normalize to separate fields
```

---

## API Gateway Integration

### Endpoints

**1. POST /dataanalysis2** (StartJob)
- **Lambda:** DataAnalysisV2StartJob
- **Purpose:** Create new data analysis job
- **Request:**
  ```json
  {
    "scout_account_id": "0U812",
    "application_name": "TestApp01",
    "source_hash": "9ec86076ac3255da03e23428fe0a874d4bb75c421feb22eb8ce7821d1392af74"
  }
  ```
- **Response:**
  ```json
  {
    "job_id": "da2_job_0U812_TestApp01_1762439897_08497588",
    "status": "started"
  }
  ```

**2. GET /dataanalysis2/status** (StatusAPI)
- **Lambda:** DataAnalysisV2StatusAPI
- **Purpose:** Query job status
- **Query Params:** `?job_id=da2_job_...`
- **Response:**
  ```json
  {
    "job_id": "da2_job_...",
    "state": "completed",
    "phase": "completed",
    "message": "ERD generation completed successfully",
    "started_at": "2025-11-06T14:38:17.999Z",
    "completed_at": "2025-11-06T14:40:30.246Z"
  }
  ```

**3. GET /dataanalysis2/results** (ResultsAPI)
- **Lambda:** DataAnalysisV2ResultsAPI
- **Purpose:** Fetch analysis results
- **Query Params:** `?job_id=da2_job_...&section=erd`
- **Sections:** erd, lineage, copybooks, data_structures, hierarchical, ai_analysis, all
- **Response:**
  ```json
  {
    "job_id": "da2_job_...",
    "section": "erd",
    "data": { ... erd.json contents ... }
  }
  ```

**API Gateway URL:**
```
https://hzz9izcu47.execute-api.us-east-1.amazonaws.com/prod/dataanalysis2
```

**Authentication:** Unknown (needs investigation)

---

## S3 Storage Architecture

### Bucket Structure

```
code-transformation-v2/
└── {scout_account_id}/
    └── {application_name}/
        ├── shared/
        │   ├── uploads/{source_hash}/
        │   │   └── extracted/          # COBOL source files (INPUT)
        │   │       ├── IBMi-Cobol/Cobol/*.CBL
        │   │       └── ...
        │   │
        │   ├── catalogs/{source_hash}/
        │   │   └── classified_catalog.json  # File classification (INPUT)
        │   │
        │   └── type_mappings/{source_hash}/
        │       └── cobol_to_java.json  # Type mapping rules (OPTIONAL)
        │
        └── data_analysis_v2/
            └── jobs/
                └── {job_id}/
                    ├── job_info.json
                    ├── status.json
                    └── artifacts/
                        ├── data_structures.json        # Regex output (150 KB)
                        ├── hierarchical_structures.json # AST output (126 KB)
                        ├── erd.json                    # ERD output (125 KB)
                        ├── ai_data_analysis.json       # AI merged (52 KB)
                        ├── copybook_analysis.json      # Copybook mapping (18 KB)
                        ├── data_lineage.json           # Data flows (13 KB)
                        └── ai_data_analysis/
                            ├── batch_0.json            # AI batch (14 KB)
                            ├── batch_1.json            # AI batch (13 KB)
                            ├── batch_2.json            # AI batch (13 KB)
                            └── batch_3.json            # AI batch (13 KB)
```

### Job ID Format
```
da2_job_{scout_account_id}_{application_name}_{timestamp}_{uuid}
```

**Example:**
```
da2_job_0U812_TestApp01_1762439897_08497588
```

**Components:**
- `da2_job_` - Prefix (Data Analysis V2)
- `0U812` - Scout account ID
- `TestApp01` - Application name
- `1762439897` - Unix timestamp
- `08497588` - Short UUID (8 characters)

### Storage Optimization

**Content-Addressed Storage:**
- Source files stored once by hash: `shared/uploads/{source_hash}/`
- Multiple jobs can reference same source_hash
- Reduces duplication

**Intermediate Artifacts:**
- AI batch files kept for debugging/audit trail
- Could be deleted after merge to save space (53 KB per job)

---

## Integration with Other Flows

### Upstream Dependencies

**1. Ingest Flow (V2)** - REQUIRED
- **Provides:**
  - `shared/uploads/{source_hash}/extracted/` (COBOL files)
  - `shared/catalogs/{source_hash}/classified_catalog.json` (file list)
- **Data Analysis V2 reads these paths**

**2. Code Analysis V3** - OPTIONAL
- **Provides:**
  - `shared/type_mappings/{source_hash}/cobol_to_java.json`
- **Data Analysis V2 uses for PIC → SQL type mapping**
- **Fallback:** Uses default mapping if not found

### Downstream Consumers

**1. Java Generation V3** - LIKELY
- **Could Use:**
  - `erd.json` - Entity/attribute mappings for JPA entity generation
  - `data_structures.json` - Field mappings for DTO generation
  - `hierarchical_structures.json` - Nested object creation
  - `data_lineage.json` - Service layer logic
- **Not Confirmed:** Need to analyze Java Generation V3 to verify

**2. Monolith Identifier V2** - UNLIKELY
- Monolith flow focuses on program structure, not data structure
- Probably no integration

**3. Dependency Mapper V2** - UNLIKELY
- Dependency flow focuses on call graphs, not data
- Probably no integration

**4. Architecture Recommender V2** - LIKELY
- **Could Use:**
  - `erd.json` - Database schema recommendations
  - `data_lineage.json` - Data flow for microservice boundaries
- **Not Confirmed:** Need to analyze Architecture Recommender V2

---

## Key Algorithms and Logic

### 1. Regex Data Structure Extraction

**Algorithm:** Pattern-based extraction using Python `re` module

**Patterns:**
```python
# FD (File Definition)
fd_pattern = r'FD\s+(\w+)'

# Record definition
record_pattern = r'(\d{2})\s+(\w+)'

# PIC clause
pic_pattern = r'PIC\s+([X9AVS\(\)\.\,\$\-\+]+)'

# COPY statement
copy_pattern = r'COPY\s+(\w+)'
```

**Logic:**
1. Read COBOL file
2. For each line:
   - Check for FD → Create file definition
   - Check for level 01 → Create record
   - Check for level 02-49 → Create field under current record
   - Check for PIC clause → Extract data type
   - Check for COPY → Add to copybook list
3. Build nested structure based on level numbers
4. Output JSON

**Strengths:**
- Very fast (no parsing overhead)
- Comprehensive (catches all FD/records)
- Simple logic (no dependencies)

**Weaknesses:**
- No semantic understanding
- Can't detect implicit relationships
- May miss complex COBOL syntax

---

### 2. AST Hierarchical Structure Parsing

**Algorithm:** Abstract Syntax Tree parsing

**Library:** Unknown (likely `cobol-parser` or similar)

**Logic:**
1. Parse COBOL file into AST
2. Walk AST to find:
   - DATA DIVISION nodes
   - Level-number structures (01-49)
   - OCCURS clauses (arrays)
   - REDEFINES clauses (unions)
3. Build parent-child relationships based on level numbers:
   ```
   01 PARENT
     02 CHILD-1
       03 GRANDCHILD
     02 CHILD-2
   ```
   → PARENT → [CHILD-1 → [GRANDCHILD], CHILD-2]
4. Output JSON tree structure

**Strengths:**
- Deep understanding of structure
- Correct parsing of complex COBOL
- Handles OCCURS/REDEFINES properly

**Weaknesses:**
- Slower than regex (parsing overhead)
- No business context
- Parser library dependency

---

### 3. AI Business Entity Identification

**Algorithm:** Claude 3.5 Sonnet via Bedrock Agent

**Prompt Strategy:**
```
Analyze the data structures in this COBOL file for database design:

FILE: {file_path}
{cobol_content}

Provide:
1. Business Entity Identification
2. Relationship Discovery
3. Data Lineage
4. Normalization Opportunities
5. Data Quality Issues
```

**Claude's Approach:**
1. Identify COBOL records (FD, WORKING-STORAGE 01 levels)
2. Map each record to a business entity
3. Infer business purpose from:
   - Field names (CLAIM, CUSTOMER, ORDER)
   - Record context (file I/O operations)
   - Comments in code
4. Assign confidence score (0.0-1.0)
5. Suggest SQL table names
6. Identify attributes (fields → columns)
7. Detect relationships by:
   - Matching field names across entities (foreign keys)
   - READ/WRITE patterns (data flows)
   - CALL statements (transformations)
8. Provide normalization suggestions (1NF, 2NF, 3NF)
9. Flag data quality issues (missing PKs, validation rules)

**Strengths:**
- Business context ("why" behind structures)
- Relationship inference (implicit patterns)
- Normalization recommendations
- Confidence scores

**Weaknesses:**
- Slow (LLM inference time)
- Expensive (Bedrock API costs)
- Non-deterministic (AI may vary)
- Limited by context window (large files may be truncated)

---

### 4. ERD Synthesis Algorithm

**Algorithm:** Multi-source intelligent merge

**Logic:**
```python
def generate_erd(regex_data, ast_data, ai_data):
    entities = []

    # Step 1: Extract entities from AI analysis (primary source)
    for ai_file in ai_data['results']:
        for entity in ai_file['analysis']['entities']:
            entities.append({
                'name': entity['name'],
                'cobol_record': entity['cobol_record'],
                'business_purpose': entity['business_purpose'],
                'confidence': entity['confidence']
            })

    # Step 2: Enrich with fields from regex data (comprehensive)
    for entity in entities:
        record = find_record(regex_data, entity['cobol_record'])
        entity['attributes'] = []
        for field in record['fields']:
            entity['attributes'].append({
                'name': normalize_name(field['name']),
                'cobol_field': field['name'],
                'data_type': map_pic_to_sql(field['pic']),
                'source_pic': field['pic'],
                'business_meaning': infer_meaning(field['name'])
            })

    # Step 3: Add hierarchy info from AST data
    for entity in entities:
        hierarchy = find_hierarchy(ast_data, entity['cobol_record'])
        entity['nested_structures'] = hierarchy

    # Step 4: Detect relationships from AI analysis
    relationships = []
    for ai_file in ai_data['results']:
        for rel in ai_file['analysis']['relationships']:
            relationships.append({
                'from_entity': rel['from'],
                'to_entity': rel['to'],
                'type': rel['type'],
                'cardinality': rel['cardinality'],
                'confidence': rel['confidence']
            })

    return {
        'entities': entities,
        'relationships': relationships
    }
```

**Source Priority:**
1. **AI Analysis** - Business entities, relationships, purpose (highest value)
2. **Regex Data** - Comprehensive field list, PIC clauses (most complete)
3. **AST Data** - Hierarchical relationships, OCCURS/REDEFINES (structural)

**Synthesis Rules:**
- Entity names from AI (business context)
- Field lists from Regex (completeness)
- Hierarchies from AST (accuracy)
- Relationships from AI (inference)
- Data types from Regex + type mapping (precision)

**Questions/Issues:**
- ⚠️ **Why sample shows 0 relationships?** Algorithm should extract from AI analysis but sample ERD has none
- ⚠️ **Business meaning quality:** Pattern-based inference is basic - why not use AI analysis meanings?

---

### 5. Data Lineage Construction

**Algorithm:** Flow extraction from COBOL operations

**COBOL Patterns Tracked:**
```cobol
READ file-name INTO record
WRITE file-name FROM record
CALL 'program-name' USING data-area
MOVE source TO destination
COMPUTE result = expression
```

**Logic:**
1. Scan COBOL for I/O operations
2. For each READ:
   - Source: File name
   - Destination: Record name
   - Operation: READ
3. For each WRITE:
   - Source: Record name
   - Destination: File name
   - Operation: WRITE
4. For each CALL:
   - Source: Calling program
   - Transformation: Called program
   - Destination: Returned data
   - Operation: TRANSFORM
5. Build flow: Source → Transform → Destination
6. Extract business impact from AI analysis

**Output:**
```json
{
  "flow_name": "Claim Header Retrieval",
  "source_file": "CMLHCL00-FILE",
  "source_type": "indexed_file",
  "transformations": [
    {
      "operation": "READ",
      "program": "IBMi-Cobol/Cobol/CMCSCL50.CBL",
      "paragraph": "20100-GET-CLAIM-HEADER"
    }
  ],
  "destination_file": "CMFHCL00 record (in-memory)",
  "destination_type": "working_storage",
  "business_impact": "Retrieves claim header for processing"
}
```

**Strengths:**
- Traces data movement
- Identifies transformation points
- Documents business impact

**Weaknesses:**
- Many flows show "unknown" source/destination (incomplete parsing)
- Paragraph-level tracking inconsistent
- Difficult to trace complex PERFORM chains

---

### 6. Type Mapping (COBOL PIC → SQL)

**Algorithm:** Pattern matching with fallback

**Mapping Rules:**
```python
def map_cobol_pic_to_sql(pic_clause):
    """
    Map COBOL PIC to SQL data type

    Examples:
    - PIC X(50) → VARCHAR(50)
    - PIC 9(7) → INTEGER
    - PIC 9(7)V99 → DECIMAL(9,2)
    - PIC S9(4) COMP → INTEGER
    - PIC $$,$$$,$$9.99 → DECIMAL(12,2)
    """

    # Normalize
    pic = pic_clause.upper()

    # Check for decimal indicators (V, ., $, Z, ,)
    if any(c in pic for c in ['V', '.', '$', 'Z', ',']):
        return 'DECIMAL'

    # Check for numeric (9 or S9)
    if '9' in pic or 'S9' in pic:
        return 'INTEGER'

    # Check for alphanumeric (X or A)
    if 'X' in pic or 'A' in pic:
        return 'VARCHAR'

    # Check for COMP (binary)
    if 'COMP' in pic or 'BINARY' in pic:
        return 'INTEGER'

    # Default fallback
    return 'VARCHAR'
```

**Type Mapping Table:**

| COBOL PIC | SQL Type | Example |
|-----------|----------|---------|
| PIC X(n) | VARCHAR(n) | X(50) → VARCHAR(50) |
| PIC A(n) | VARCHAR(n) | A(30) → VARCHAR(30) |
| PIC 9(n) | INTEGER | 9(7) → INTEGER |
| PIC S9(n) | INTEGER | S9(4) → INTEGER |
| PIC 9(n)V99 | DECIMAL(n+2,2) | 9(7)V99 → DECIMAL(9,2) |
| PIC 9(n).99 | DECIMAL(n+2,2) | 9(5).99 → DECIMAL(7,2) |
| PIC $$,$$$,$$9.99 | DECIMAL | DECIMAL(12,2) |
| PIC ZZ,ZZZ,ZZ9 | DECIMAL | DECIMAL(10,0) |
| PIC S9(n) COMP | INTEGER | INTEGER |
| PIC S9(n) COMP-3 | DECIMAL | DECIMAL (packed) |
| PIC N/A | VARCHAR | VARCHAR (default) |

**Questions/Issues:**
- ⚠️ **COMP-3 (Packed Decimal):** Not explicitly handled - mapped to INTEGER but should be DECIMAL
- ⚠️ **VARCHAR Length:** Mapping doesn't preserve length - `X(50)` → `VARCHAR` (no length)
- ⚠️ **Precision/Scale:** `9(7)V99` → `DECIMAL` but precision/scale not calculated

---

### 7. Business Meaning Inference

**Algorithm:** Pattern-based field name analysis

**Patterns:**
```python
patterns = [
    # Identifiers
    (r'(_id|^id)$', 'Unique identifier'),
    (r'_key$', 'Key field'),
    (r'_number$', 'Number field'),
    (r'_code$', 'Code field'),

    # Dates
    (r'_date$', 'Date field'),
    (r'_time$', 'Time field'),
    (r'_timestamp$', 'Timestamp field'),

    # Amounts
    (r'_amount$', 'Amount field'),
    (r'_price$', 'Price field'),
    (r'_cost$', 'Cost field'),

    # Names
    (r'_name$', 'Name field'),
    (r'_desc$', 'Description field'),

    # Status
    (r'_status$', 'Status field'),
    (r'_flag$', 'Flag field'),
    (r'_ind$', 'Indicator field'),

    # Address
    (r'_addr$', 'Address field'),
    (r'_city$', 'City field'),
    (r'_state$', 'State field'),
    (r'_zip$', 'ZIP code field')
]

def infer_business_meaning(field_name):
    name_lower = field_name.lower()
    for pattern, meaning in patterns:
        if re.search(pattern, name_lower):
            return meaning

    # Default: Title case the field name
    return ' '.join(word.capitalize() for word in field_name.split('_'))
```

**Examples:**
- `customer_id` → "Unique identifier"
- `order_date` → "Date field"
- `total_amount` → "Amount field"
- `clacpre` → "Clacpre field" (no pattern match, uses title case)

**Strengths:**
- Fast (regex matching)
- Covers common patterns

**Weaknesses:**
- Generic meanings for non-standard names
- Doesn't use AI analysis (which has better meanings)
- COBOL field names often abbreviated - pattern matching fails

---

## ⚠️ Questions and Issues

### Critical Issues

**1. Relationship Detection Not Working**
- **Observation:** Sample ERD shows `"total_relationships": 0` despite AI analysis explicitly mentioning relationships
- **AI Analysis Says:**
  ```
  Claim → Risk (Confidence: 0.85)
  Type: many-to-one
  Business Rule: "Each claim is associated with one risk"
  ```
- **ERD Shows:** 0 relationships
- **Root Cause:** ERD generator not parsing AI relationship section? Or relationship detection algorithm not implemented?
- **Impact:** ERD missing critical foreign key relationships
- **Recommendation:** Fix ERD generator to extract relationships from AI analysis

**2. Business Meaning Quality**
- **Observation:** ERD uses pattern-based inference: `"business_meaning": "Clacpre field"`
- **AI Analysis Has Better:**
  ```
  Attributes: clprefix, clsuffix, clnumber (composite PK)
  Business Purpose: Account prefix for claim identification
  ```
- **Root Cause:** ERD generator uses simple pattern matching instead of AI meanings
- **Impact:** Poor quality business documentation
- **Recommendation:** Extract business meanings from AI analysis instead of pattern inference

**3. Type Mapping Precision**
- **Issue:** COBOL PIC → SQL mapping doesn't preserve length, precision, scale
  - `X(50)` → `VARCHAR` (should be VARCHAR(50))
  - `9(7)V99` → `DECIMAL` (should be DECIMAL(9,2))
  - `S9(4) COMP-3` → `INTEGER` (should be DECIMAL - packed decimal)
- **Impact:** ERD not SQL-ready (missing size constraints)
- **Recommendation:** Calculate precision/scale from PIC clause

**4. No Error Handling in Step Functions**
- **Issue:** No Retry or Catch blocks in workflow
- **Impact:** If any Lambda fails (Bedrock timeout, S3 error), entire job fails
- **Recommendation:** Add retry logic and error handling

---

### Medium Priority Issues

**5. Cost of AI Analysis**
- **Question:** What's the Bedrock cost per job?
- **Calculation Needed:**
  - 20 files × ~1000 lines each = ~20,000 lines
  - Claude 3.5 Sonnet pricing: $3/million input tokens, $15/million output tokens
  - Estimated: ~$0.50 per job?
- **Recommendation:** Monitor costs, consider caching for repeated analyses

**6. Parallel Execution Limits**
- **Question:** MaxConcurrency: 40 - what if job has 100 batches?
- **Answer:** Step Functions queues remaining batches (processes 40 at a time)
- **Impact:** Large jobs (100+ files) may take longer
- **Recommendation:** Document scaling limits

**7. Data Lineage Incomplete**
- **Observation:** Many flows show:
  - `"source_file": "Unknown (possibly a database or file)"`
  - `"source_type": "unknown"`
- **Root Cause:** Lineage extraction can't determine source when:
  - File opened in different paragraph
  - File name in WORKING-STORAGE variable
  - External system (DB2, CICS)
- **Impact:** Incomplete data flow documentation
- **Recommendation:** Enhance lineage extraction to handle complex scenarios

**8. Copybook Analysis Depth**
- **Question:** Does copybook_analysis.json expand nested copybooks?
- **Example:** If COPY A includes COPY B, are B's fields shown?
- **Not Clear:** Need to examine Lambda code
- **Recommendation:** Verify copybook expansion logic

---

### Low Priority Questions

**9. AST Parser Library**
- **Question:** Which Python library is used for COBOL AST parsing?
- **Check:** Look for imports in `ast_data_analyzer_v2_handler.py`
- **Options:** `cobol-parser`, `tree-sitter-cobol`, custom parser?

**10. Type Mapping Overrides**
- **Question:** Can users provide custom type mappings?
- **Answer:** Yes - `shared/type_mappings/{source_hash}/cobol_to_java.json`
- **Default:** Falls back to built-in rules if not found
- **Recommendation:** Document type mapping format for users

**11. Batch Size Tuning**
- **Current:** 5 files per batch
- **Question:** Is this optimal? Should it vary by file size?
- **Consideration:** Large files may timeout in 5-min Lambda
- **Recommendation:** Consider dynamic batch sizing based on total LOC

**12. API Authentication**
- **Question:** What auth mechanism protects API endpoints?
- **Options:** API key, IAM, Cognito, none?
- **Need:** Check API Gateway configuration
- **Recommendation:** Document authentication requirements

---

## V5 Improvement Opportunities

### 1. Fix Relationship Detection
**Priority:** HIGH
```python
# Current: Relationships not extracted from AI analysis
# V5: Parse AI analysis text for relationship mentions

def extract_relationships_from_ai(ai_analysis):
    relationships = []
    for file_analysis in ai_analysis['results']:
        text = file_analysis['analysis']['analysis_text']
        # Parse "Entity A → Entity B" patterns
        # Extract type, cardinality, business rule
        # Build relationship objects
    return relationships
```

### 2. Enhance Business Meanings
**Priority:** HIGH
```python
# Current: Pattern-based inference ("Clacpre field")
# V5: Extract from AI analysis

def extract_attribute_meanings(ai_analysis, entity_name):
    for file_analysis in ai_analysis['results']:
        if entity_name in file_analysis['analysis']['entities']:
            entity = file_analysis['analysis']['entities'][entity_name]
            return entity['attributes']  # Has real business meanings
```

### 3. Improve Type Mapping
**Priority:** HIGH
```python
# Current: PIC 9(7)V99 → DECIMAL (no precision)
# V5: Calculate precision and scale

def map_pic_to_sql_with_precision(pic_clause):
    pic = pic_clause.upper()

    if '9' in pic or 'S9' in pic:
        # Extract digits before and after decimal
        match = re.match(r'S?9\((\d+)\)(?:V(\d+))?', pic)
        if match:
            int_digits = int(match.group(1))
            dec_digits = int(match.group(2)) if match.group(2) else 0
            if dec_digits > 0:
                return f"DECIMAL({int_digits + dec_digits}, {dec_digits})"
            else:
                return f"INTEGER"  # or BIGINT if > 9 digits

    elif 'X' in pic:
        match = re.match(r'X\((\d+)\)', pic)
        if match:
            length = match.group(1)
            return f"VARCHAR({length})"

    return "VARCHAR"  # Default
```

### 4. Add Error Handling
**Priority:** MEDIUM
```json
{
  "BedrockAnalyzerBatch": {
    "Type": "Task",
    "Resource": "arn:aws:lambda:...",
    "Retry": [
      {
        "ErrorEquals": ["States.TaskFailed"],
        "IntervalSeconds": 2,
        "MaxAttempts": 3,
        "BackoffRate": 2.0
      }
    ],
    "Catch": [
      {
        "ErrorEquals": ["States.ALL"],
        "ResultPath": "$.error",
        "Next": "HandleAIFailure"
      }
    ]
  }
}
```

### 5. Enhance Data Lineage
**Priority:** MEDIUM
```python
# Current: Can't detect file names in variables
# V5: Track WORKING-STORAGE file assignments

def extract_file_assignments(cobol_code):
    # Find: 01 FILE-NAME PIC X(20) VALUE "CUSTOMER.DAT"
    # Track: MOVE "ORDER.DAT" TO FILE-NAME
    # Resolve: READ variable-file-name (use tracked value)
    pass
```

### 6. Parallel Analysis of Large Files
**Priority:** MEDIUM
```python
# Current: Entire file sent to AI (may hit context limit)
# V5: Split large files into sections

def prepare_large_file_for_ai(cobol_content, max_lines=500):
    sections = []
    current_section = []

    for line in cobol_content.split('\n'):
        current_section.append(line)
        if len(current_section) >= max_lines:
            sections.append('\n'.join(current_section))
            current_section = []

    if current_section:
        sections.append('\n'.join(current_section))

    return sections  # Analyze each section separately
```

### 7. Copybook Expansion
**Priority:** LOW
```python
# Current: Copybooks listed but not expanded
# V5: Recursively expand nested copybooks

def expand_copybooks(cobol_code, copybook_dir):
    while 'COPY ' in cobol_code:
        match = re.search(r'COPY\s+(\w+)', cobol_code)
        if match:
            copybook_name = match.group(1)
            copybook_content = read_copybook(copybook_dir, copybook_name)
            # Replace COPY statement with actual content
            cobol_code = cobol_code.replace(match.group(0), copybook_content)
    return cobol_code
```

### 8. Dynamic Batch Sizing
**Priority:** LOW
```python
# Current: Fixed 5 files per batch
# V5: Dynamic based on total LOC

def create_dynamic_batches(files, max_loc_per_batch=5000):
    batches = []
    current_batch = []
    current_loc = 0

    for file in files:
        file_loc = count_lines(file)
        if current_loc + file_loc > max_loc_per_batch:
            batches.append(current_batch)
            current_batch = [file]
            current_loc = file_loc
        else:
            current_batch.append(file)
            current_loc += file_loc

    if current_batch:
        batches.append(current_batch)

    return batches
```

### 9. Caching AI Analyses
**Priority:** LOW
```python
# Current: Re-analyze same files in different jobs
# V5: Cache AI analyses by file hash

def get_ai_analysis_cached(file_content, file_hash):
    cache_key = f"ai_cache/{file_hash}.json"

    if s3_exists(cache_key):
        return s3_read(cache_key)

    # Not cached - invoke Bedrock
    analysis = invoke_bedrock_agent(file_content)

    # Cache for future use
    s3_write(cache_key, analysis)

    return analysis
```

### 10. SQL DDL Generation
**Priority:** MEDIUM
```python
# Current: ERD is JSON - user must manually create tables
# V5: Generate CREATE TABLE statements

def generate_sql_ddl(erd):
    ddl = []

    for entity in erd['entities']:
        table_name = entity['name'].lower()
        ddl.append(f"CREATE TABLE {table_name} (")

        columns = []
        for attr in entity['attributes']:
            col_name = attr['name']
            data_type = attr['data_type']
            nullable = "NULL" if attr['nullable'] else "NOT NULL"
            pk = "PRIMARY KEY" if attr['is_primary_key'] else ""

            columns.append(f"  {col_name} {data_type} {nullable} {pk}".strip())

        ddl.append(",\n".join(columns))
        ddl.append(");")
        ddl.append("")

    return "\n".join(ddl)
```

---

## Comparison with Other Flows

### vs. Code Analysis V3
| Aspect | Code Analysis V3 | Data Analysis V2 |
|--------|------------------|------------------|
| **Focus** | Program logic, business rules | Data structures, entities |
| **Output** | Business logic docs, refactor recipes | ERD, data lineage |
| **AI Approach** | Per-file analysis | Batch processing (5 files) |
| **Deployment** | Docker images | ZIP packages |
| **Parallelization** | Map state (40 concurrent) | Map state (40 concurrent) |
| **Performance** | ~5 min for 20 files | ~2 min for 20 files |
| **Cost** | Higher (more AI analysis) | Lower (fewer AI tokens) |
| **Complexity** | High (multi-phase, many Lambdas) | Medium (3-phase parallel) |

**Key Difference:** Code Analysis V3 focuses on "what the code DOES" (business logic), Data Analysis V2 focuses on "what the code STORES" (data model).

**Overlap:** Both use Bedrock AI, both have batch processing, both produce JSON artifacts.

**Integration:** Data Analysis V2 ERD could inform Code Analysis V3 refactoring (data-driven refactor).

---

### vs. Dependency Mapper V2
| Aspect | Dependency Mapper V2 | Data Analysis V2 |
|--------|---------------------|------------------|
| **Focus** | Call graphs, program dependencies | Data structures, entity relationships |
| **Output** | Dependency graph (nodes/edges), service boundaries | ERD (entities/attributes), data lineage |
| **AI Approach** | AI for service recommendations | AI for entity identification |
| **Graph Type** | Program call graph | Entity relationship graph |
| **Service Recommendations** | 20 small services (technical coupling) | N/A (not microservice-focused) |

**Key Difference:** Dependency Mapper V2 analyzes PROGRAM relationships (calls), Data Analysis V2 analyzes DATA relationships (entities).

**Complementary:** Could combine both to recommend microservices that align with both code AND data boundaries.

---

### vs. Monolith Identifier V2
| Aspect | Monolith Identifier V2 | Data Analysis V2 |
|--------|----------------------|------------------|
| **Focus** | God Objects, monolith patterns | Data entities, ERD |
| **Output** | Business capability services, migration strategy | ERD, data lineage, copybooks |
| **Service Recommendations** | 4-5 large services (business capability) | N/A |
| **Business Context** | High (identifies business capabilities) | Medium (entity business purpose) |

**Key Difference:** Monolith Identifier V2 recommends SERVICES, Data Analysis V2 documents DATA MODEL.

**Complementary:** Monolith service boundaries could align with entity boundaries from ERD.

---

## Production Readiness Assessment

### ✅ Strengths
1. **Multi-Source Intelligence:** Combines regex (fast), AST (accurate), AI (contextual)
2. **Parallel Execution:** 3-branch parallel + Map state = very fast (~2 min)
3. **Comprehensive Output:** 7 artifacts covering all data aspects
4. **SQL-Ready ERD:** Entities/attributes map to database schema
5. **Business Context:** AI provides business meanings, relationships, quality issues
6. **Batch Processing:** Efficient use of Bedrock (5 files per batch)
7. **API Integration:** Clean REST API for status/results
8. **Production Proven:** Serving 100+ users

### ⚠️ Weaknesses
1. **Relationship Detection Broken:** ERD shows 0 relationships (critical bug)
2. **Business Meanings Poor:** Pattern-based inference instead of AI meanings
3. **Type Mapping Imprecise:** Missing length/precision/scale
4. **No Error Handling:** Step Functions will fail hard on any error
5. **Data Lineage Incomplete:** Many "unknown" sources/destinations
6. **No SQL DDL Output:** User must manually create tables
7. **Cost Uncertainty:** Bedrock costs not monitored/documented
8. **Large File Handling:** May hit AI context limits (not tested)

### 🔧 Recommendations for V5

**Must Fix (Blocking Issues):**
1. Fix relationship detection in ERD generator
2. Extract business meanings from AI analysis
3. Add precision/scale to type mapping
4. Add error handling to Step Functions

**Should Improve (Quality Issues):**
5. Enhance data lineage extraction (resolve "unknown" sources)
6. Generate SQL DDL from ERD
7. Monitor Bedrock costs per job
8. Test with large files (10,000+ lines)

**Nice to Have (Features):**
9. Cache AI analyses for repeated files
10. Dynamic batch sizing based on LOC
11. Copybook expansion (nested COPY statements)
12. Visual ERD diagram generation (Graphviz, Mermaid)

---

## Summary

Data Analysis V2 is a **production-ready multi-source data intelligence pipeline** that:
- Analyzes COBOL data structures using 3 parallel approaches (Regex + AST + AI)
- Generates comprehensive ERD with 34 entities, data lineage with 38 flows, and copybook mappings
- Processes 20 files in ~2 minutes using batch parallelization (MaxConcurrency: 40)
- Provides REST API for job management and result retrieval
- Serves 100+ users in production

**Key Innovation:** Combines strengths of regex (speed), AST (accuracy), and AI (business context) into unified ERD.

**Critical Bug:** Relationship detection not working (0 relationships in ERD despite AI identifying them).

**V5 Focus:** Fix relationship detection, improve business meanings, add precision to type mapping, enhance error handling.

---

**Document Status:** ✅ COMPLETE
**Next Steps:** Analyze remaining flows (Architecture Recommender V2, Java Generation V2/V3, Discovery V2)
