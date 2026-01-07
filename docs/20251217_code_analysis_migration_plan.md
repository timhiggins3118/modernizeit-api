# Code Analysis Migration Plan - CLI to API

## Overview

Migrate the working POC/CLI code analysis pipeline to the API app.

**Source:** `/modernizeit-cli/` (11-step pipeline, tested, produces JSON + Java + Graphs)
**Target:** `/modernizeit-api/engines/code_analysis/` (new engine)

---

## What Exists Today

### CLI App (Working)
11-step pipeline producing:
- 9 JSON artifact files
- 3 dependency graphs (PNG)
- Complete Maven project with generated Java
- Zero-loss line inventory (10,646 lines → 10,646 entries)

### API App (Stub)
- Old AWS Lambda-style runner (4 lambdas)
- Basic routes for `/codeanalysis3`
- Not connected to the CLI's robust parsing/generation

---

## Files to Migrate from CLI

| # | File | Purpose | Size |
|---|------|---------|------|
| 1 | `cobol_parser_adapter.py` | Tree-sitter wrapper, loads COBOL grammar | Core |
| 2 | `cobol_parse_export.py` | Line-by-line inventory (zero-loss) | Core |
| 3 | `comprehensive_parser.py` | Full codebase analysis (programs + copybooks) | Core |
| 4 | `cobol_data_parser.py` | DATA DIVISION parsing, PIC clause parser | Core |
| 5 | `cobol_data_extractor.py` | Complete data model (IBM ODM 9.5.0) | Core |
| 6 | `cobol_procedure_parser.py` | PROCEDURE DIVISION parsing | Core |
| 7 | `cobol_file_parser.py` | FILE SECTION parsing | Core |
| 8 | `java_generator_clean.py` | Primary Java generator | 155KB |
| 9 | `project_template_generator.py` | Maven/IntelliJ project generation | Templates |
| 10 | `graph_generator.py` | Dependency visualization (Graphviz) | Graphs |
| 11 | `file_analyzer.py` | ZIP extraction utilities | Utility |

### Also Required
- Tree-sitter COBOL grammar: `cobol.so` (pre-built binary)
- Jinja2 for templates

---

## JSON Artifacts Produced

| File | Description |
|------|-------------|
| `comprehensive_parse_results.json` | All programs + copybooks analysis |
| `unified_data_model.json` | All data items from entire codebase |
| `cross_reference.json` | Copybook usage, file access patterns |
| `{program}_line_inventory.json` | Zero-loss line-by-line catalog |
| `{program}_data_model.json` | DATA DIVISION semantic model |
| `{program}_complete_data_model.json` | IBM ODM 9.5.0 mapping (717 items) |
| `{program}_procedure_model.json` | PROCEDURE DIVISION (284 paragraphs) |
| `{program}_file_model.json` | FILE SECTION definitions |

---

## Graphs Produced

| Graph | Description |
|-------|-------------|
| `{program}_high_level.png` | Program → Copybooks → Files |
| `{program}_summary.png` | Top-level call graph |
| `{program}_detailed.png` | Full paragraph call graph |

---

## Generated Output

```
generated/{program}/
├── pom.xml                 # Maven build
├── {program}.iml           # IntelliJ module
├── .idea/                  # IDE config
├── README.md               # Project docs
└── src/main/java/com/modernizeit/generated/
    └── {Program}.java      # Generated Java (8,000+ lines)
```

---

## Migration Plan

### Phase 1: Copy Core Modules
Create new engine directory and copy files:

```
engines/
└── code_analysis/          # NEW (not code_analysis_v3)
    ├── __init__.py
    ├── runner.py           # Main orchestrator
    ├── parsers/
    │   ├── __init__.py
    │   ├── cobol_parser_adapter.py
    │   ├── cobol_parse_export.py
    │   ├── comprehensive_parser.py
    │   ├── cobol_data_parser.py
    │   ├── cobol_data_extractor.py
    │   ├── cobol_procedure_parser.py
    │   └── cobol_file_parser.py
    ├── generators/
    │   ├── __init__.py
    │   ├── java_generator_clean.py
    │   ├── project_template_generator.py
    │   └── graph_generator.py
    └── utils/
        ├── __init__.py
        └── file_analyzer.py
```

### Phase 2: Copy Grammar File
```
engines/code_analysis/
└── grammar/
    └── cobol.so            # Tree-sitter COBOL grammar
```

### Phase 3: Create Runner
New `runner.py` that:
1. Takes ingest artifacts path as input
2. Runs the 11-step pipeline
3. Saves all JSON to `reports/` folder
4. Generates graphs to `reports/graphs/`
5. Generates Maven project to `generated/`
6. Returns job metadata

### Phase 4: Update API Routes
Update or create routes:

```python
POST /codeanalysis         # Run full analysis
GET  /codeanalysis/{job_id}/status
GET  /codeanalysis/{job_id}/results
GET  /codeanalysis/{job_id}/results/json/{filename}
GET  /codeanalysis/{job_id}/results/graphs/{filename}
GET  /codeanalysis/{job_id}/results/java
```

### Phase 5: Wire to Ingest
- Code analysis reads from ingest output path
- Uses `source_hash` to locate extracted COBOL files
- Path: `{base_path}/{account}/{app}/shared/uploads/{source_hash}/extracted/`

---

## API Contract (Proposed)

### POST /codeanalysis

**Request:**
```json
{
  "scout_account_id": "string",
  "application_name": "string",
  "source_hash": "string (optional, uses latest if omitted)",
  "main_program": "string (optional, auto-detect if omitted)",
  "generate_java": true,
  "generate_graphs": true
}
```

**Response:**
```json
{
  "job_id": "ca_job_...",
  "status": "completed",
  "artifacts_path": "/path/to/output",
  "summary": {
    "source_lines": 10646,
    "data_items": 717,
    "paragraphs": 284,
    "files_analyzed": 41,
    "java_lines": 8013
  },
  "artifacts": {
    "json": ["comprehensive_parse_results.json", ...],
    "graphs": ["high_level.png", "summary.png", "detailed.png"],
    "java_project": "generated/ifpr321_cbl/"
  }
}
```

---

## Dependencies to Add

```toml
# pyproject.toml
[project.dependencies]
tree-sitter = "^0.20.0"
jinja2 = "^3.1.0"
```

**External:**
- `graphviz` (system install: `brew install graphviz`)

---

## Testing Checklist

- [ ] Tree-sitter loads COBOL grammar
- [ ] Line inventory produces zero-loss output
- [ ] All 9 JSON files generated
- [ ] All 3 graphs render to PNG
- [ ] Java compiles with `mvn compile`
- [ ] API routes return correct data
- [ ] Job records saved to database

---

## Order of Operations

1. **Copy files** - Get all modules into API structure
2. **Fix imports** - Update relative imports for new structure
3. **Test parsing** - Verify tree-sitter works
4. **Test generation** - Verify Java output
5. **Wire API** - Connect routes to runner
6. **Test end-to-end** - Postman/curl full flow

---

## Notes

- Keep old `engines/code_analysis_v3/` for reference (don't delete yet)
- The CLI's `main.py` has the orchestration logic to reference
- Grammar file is at: `/Users/timhiggins/Desktop/desktop/Source/TransformationCode/code-transformation-modernizeit/build/cobol.so`
