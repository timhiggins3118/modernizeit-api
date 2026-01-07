# V5 Architecture Review - Fresh Start

**Date:** November 6, 2025, 10:45 AM
**Purpose:** Complete analysis of ALL flows to understand what exists, what works, what's broken, and how to improve
**Context:** Starting over after 2 days of failed fixes due to not understanding the architecture
**Approach:** ANALYSIS ONLY - no fixes, no assumptions, just understanding

---

## Mission Statement

Analyze each flow systematically to:
1. **UNDERSTAND** what it does (inputs, outputs, purpose)
2. **DOCUMENT** current state (working, broken, missing features)
3. **IDENTIFY** data dependencies between flows
4. **ASSESS** business logic extraction and Java code generation gaps
5. **PROPOSE** improvements for V5 architecture

**NO CODING. NO DEPLOYING. ONLY ANALYSIS.**

---

## Flows to Analyze

### Production Flows (V2 - Live with 100+ Users)

**Location:** `/Volumes/My_Passport/Source/COBOL/cobalt_etl_studio/aws_arch2/`

1. **Ingestion Flow** (`01_ingesting/`)
   - Status: ?
   - Purpose: ?
   - Bucket: ?
   - API: ?

2. **Code Analysis V2** (`02_code_analysis_v2/`)
   - Status: ?
   - Purpose: ?
   - Outputs: static_analysis.json, ERD.json, etc.
   - Business Logic Extraction: ?

3. **Code Refactor V2** (`code_refactor/`)
   - Status: ?
   - Purpose: ?
   - Inputs: ?
   - Outputs: ?

4. **Dependency Mapper V2** (`dependency_mapper_v2/`)
   - Status: ?
   - Purpose: ?
   - Outputs: ?

5. **Monolith Identifier V2** (`monolith_identifier_v2/`)
   - Status: ?
   - Purpose: ?
   - Outputs: ?

6. **Data Analyzer V2** (`data_analyzer/`)
   - Status: ?
   - Purpose: ?
   - Outputs: ?

7. **Discovery V2** (`step0_discovery/`)
   - Status: ?
   - Purpose: ?
   - Contains: business_logic_analyzer Lambda?

8. **Architecture Recommender V2** (`architecture_recommender_v2/`)
   - Status: FIXED (Nov 6)
   - Purpose: ?
   - Inputs: ?

9. **Java Generation V2** (`java_generation_v2/`)
   - Status: ?
   - Purpose: ?
   - Business Logic: ?

### New Flows (V3 - Development/Testing)

**Location:** `/Volumes/My_Passport/Source/COBOL/cobalt_etl_studio/aws_arch3/`

10. **Code Analysis V3** (`code_analysis_v3/`)
    - Status: DEPLOYED (Nov 5)
    - Purpose: Per-file analysis with BedrockAnalyzerPerFile
    - Outputs: ai_analyses/*.json, structural_context.json, static_analysis.json
    - Business Logic Extraction: ?

11. **Java Generation V3** (`java_generation_v3/`)
    - Status: DEPLOYED (Oct 2025)
    - Purpose: Generate Spring Boot app from V2 artifacts
    - Workflows: 3 (JavaGenerationWorkflowV3, JavaCodeAnalysisWorkflowV3, ?)
    - Business Logic: BROKEN (generates stubs only)

---

## Analysis Framework

For each flow, document:

### 1. Basic Information
- **Flow Name:**
- **Location:**
- **Version:** (V2 or V3)
- **Status:** (Production, Testing, Broken, Unknown)
- **Last Modified:**
- **Documentation:** (MD files to read)

### 2. Purpose & Scope
- **What does it do?**
- **Why does it exist?**
- **Who uses it?** (100+ customers, internal only, etc.)
- **Critical or Optional?**

### 3. Technical Details
- **Lambdas:**
- **Step Functions:**
- **S3 Buckets:**
- **API Endpoints:**
- **Triggers:**

### 4. Data Flow
- **Inputs:** (from which flows/S3 paths)
- **Outputs:** (to which flows/S3 paths)
- **Artifacts Generated:**
- **Schema/Structure:**

### 5. Business Logic Handling
- **Does it extract COBOL business logic?** (Y/N)
- **Does it generate Java code?** (Y/N)
- **Format:** (paragraph_analysis, java_method.code, etc.)
- **Quality:** (working, stubs, missing)

### 6. Current State Assessment
- **Working?** (Y/N)
- **Known Issues:**
- **Missing Features:**
- **Dependencies:**

### 7. Improvement Opportunities
- **What could be better?**
- **What's missing?**
- **What should change in V5?**

---

## Analysis Progress

### ✅ Completed
- [ ] None yet - starting fresh

### 🔄 In Progress
- [ ] Reading architecture documentation
- [ ] Understanding V2 vs V3 differences

### ⏸️ Blocked
- [ ] User demo (in progress)

---

## Key Questions to Answer

1. **Where does business logic extraction happen in V2?**
   - Code Analysis V2 Bedrock Agent?
   - Discovery flow business_logic_analyzer?
   - Somewhere else?

2. **What does static_analysis.json contain in V2 vs V3?**
   - V2: Has paragraph_analysis with java_method.code?
   - V3: Has paragraph_analysis without java_method.code?
   - Structure differences?

3. **How does JavaGen V2 work?**
   - Does it generate real code or stubs?
   - What inputs does it read?
   - Why did it work in October (java_export_final)?

4. **What changed between October working version and November broken version?**
   - Code Analysis V2 → V3 migration?
   - JavaGen V2 → V3 changes?
   - Prompt changes?

5. **What is the correct end-to-end flow for COBOL → Java with business logic?**
   - Ingestion → Analysis → ??? → JavaGen → Working Java
   - Where should business logic be extracted?
   - Who should generate Java code?

6. **What role does each V2 flow play?**
   - Are all 9 V2 flows required for JavaGen?
   - Can some be skipped?
   - What's the minimum viable path?

---

## Documentation to Read

### Priority 1: Architecture Understanding
- [ ] `/aws_arch2/FINAL_AWS_ARCHITECTURE_SUMMARY.md`
- [ ] `/aws_arch2/V2_AWS_ARCHITECTURE_MASTER.md`
- [ ] `/aws_arch2/20251031_CODE_ANALYSIS_V2_ARCHITECTURE.md`
- [ ] `/aws_arch/java_generation_v3/FLOW1_V3_JAVA_GENERATION_HLD.md`
- [ ] `/aws_arch/20251024_analysis_business_logic.md`

### Priority 2: Flow-Specific Docs
- [ ] Code Analysis V2: `/aws_arch2/2025-09-26_analysis_flow.md`
- [ ] Code Refactor V2: `/aws_arch/analysis_workflows/20251002_code_refactor_flow_v2_COMPLETE.md`
- [ ] JavaGen V2: `/aws_arch/java_generation_v2/COMPLETE_20251004.md`
- [ ] JavaGen V3: `/aws_arch/java_generation_v3/V3_STATUS_SUMMARY.md`
- [ ] Discovery: `/aws_arch2/step0_application_discovery.md`

### Priority 3: Working Examples
- [ ] Analyze: `/Users/timhiggins/Desktop/java_export_final/` (October working version)
- [ ] Compare: `/Users/timhiggins/Desktop/s3_files_6nov/` (November broken version)
- [ ] Understand: What changed between these two?

---

## Analysis Methodology

### Phase 1: Document Reading (1-2 hours)
1. Read all Priority 1 architecture docs
2. Create mental map of V2 flows
3. Understand Code Analysis V2 vs V3 differences
4. Document findings below

### Phase 2: Code Inspection (1-2 hours)
1. Read Lambda handler code for each flow
2. Trace data flow through S3 paths
3. Identify where business logic is extracted
4. Document actual vs expected behavior

### Phase 3: Comparison Analysis (1 hour)
1. Compare October working output vs November broken output
2. Identify what changed
3. Pinpoint exact breaking change
4. Document root cause

### Phase 4: Recommendations (1 hour)
1. Propose V5 architecture improvements
2. Identify quick wins vs long-term fixes
3. Create implementation roadmap
4. Get user approval before ANY coding

---

## Notes & Findings

### 2025-11-06 10:45 - Session Start

**Context from previous failures:**
- Spent 2 days trying to fix JavaGen business logic issue
- Didn't read architecture docs first
- Made assumptions about Code Analysis V3
- Deployed "fixes" that didn't fix anything
- User has demo today - can't risk breaking more

**Lesson learned:**
- MUST read docs before acting
- MUST understand full architecture
- MUST trace data flow completely
- MUST analyze before fixing

**Current understanding (to be validated):**
- Code Analysis V2 Bedrock Agent does NOT extract PROCEDURE DIVISION logic
- ServiceGeneratorV3 expects java_method.code field (doesn't exist)
- Business logic extraction is the missing piece
- 10-16 day effort to fix properly

**Questions to answer:**
1. Is this understanding correct?
2. What actually exists in V2?
3. How did October version work?
4. What's the minimal fix for demo?

---

## Next Steps

1. **WAIT for user to finish demo**
2. **READ all Priority 1 docs**
3. **ANALYZE actual code and data**
4. **DOCUMENT findings**
5. **PROPOSE V5 architecture**
6. **GET APPROVAL before any changes**

---

**Status:** Created - Ready to begin analysis after user's demo
**DO NOT proceed with fixes until analysis is complete and approved**
