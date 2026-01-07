# UI Thoughts - Company Portal Analysis

**Date:** December 26, 2025
**Status:** Analysis Complete
**Source:** `/Users/timhiggins/Desktop/pooja_modernizeit/p-docs`

---

## Three Deployment Modes

| Mode | Description | Status |
|------|-------------|--------|
| 1. Thick Client | Desktop app like VS Code | Future |
| 2. Self Portal | Local UI we built (modernizeit-ui) | Working |
| 3. Company Portal | AWS-hosted multi-tenant (Scout-itAI) | Existing - needs API integration |

---

## Company Portal Overview

**Product:** Scout-itAI - Agentic Event Intelligence System
**URL:** `dev.scoutitai.com`
**Powered by:** Amazon Bedrock
**Version:** 2.4.1

### Platform Modules (Top Navigation)

- MonitorIT
- AnalyzeIT
- ManageIT
- **ModernizeIT** ← Our focus
- LearnIT
- AGI
- AdminIT

---

## ModernizeIT Portal Structure

### Application Portfolio (Landing Page)

- **Grid of application cards** (78+ applications in screenshots)
- Each card shows:
  - Application name
  - Internal ID (e.g., `app_sat122_1765626976`)
  - Description
  - Files count
  - Created date
  - Tags: `COBOL → JAVA`
  - Edit/Delete icons
- **Actions:** Search, Add Application, Grid/List toggle
- Click card → Opens Modernization Process

### Portfolio Summary (Dashboard)

Summary tiles:
- Total Applications
- Total Files
- Avg Progress (%)
- Near Completion (75%+ complete)

Table view:
- Application Name, Files, Progress bar, Status, Created, Last Updated, Actions (drill-down arrow)

---

## Modernization Process (4-Step Wizard)

### Step 1: Analysis

**Analysis Queue Panel**
- Lists uploaded files (file name, size, status)
- Status progression: Uploaded → Analyzed
- Actions: Upload Documents, Analyze Application

**Expanded File View (after analysis)**
- File Type (e.g., COBOL_PROGRAM)
- Total Lines
- Paragraphs count
- Confidence (%)

**AI Analysis Overview**
- Complexity: Low/Medium/High
- Analyzer: BedrockAnalyzerPerFile
- Business Purpose: AI-generated description
- Data Flows: AI-generated data flow description

**Flow Report Tabs**
| Tab | Content |
|-----|---------|
| Overview | Executive Summary, Key Metrics (ROI, Payback, 5-Year Savings), Business Processes |
| Code Analysis | Code structure analysis |
| Data Analysis | ERD, data lineage |
| Refactor Analysis | Refactoring opportunities |
| Dependency Analysis | Call graphs, dependencies |
| Monolith Analysis | Anti-patterns, decomposition |

**Run Metadata**
- Triggered At, Completed At, Duration, Total Files, Status (COMPLETED)

### Step 2: O&T (Operations & Transformation)

**Code Generation Panel**
- Application Name
- AI Status: FINALIZED
- Code Quality: View Report link
- Progress bar
- **Download Zip** button

### Step 3: QA

**Files from O&T Panel**
- Application Name
- QA Status: Completed
- Progress bar
- **Re-run QA** button

**QA Analysis Results**
| Column | Example |
|--------|---------|
| Application | ModernizationTesting |
| Round | Round 1 |
| Test Results | Pass Rate: 83.1% |
| Score | 78.1% |
| Recommendation | Blocked |
| Critical Issues | 3 found |
| Actions | View, Export |

### Step 4: Architecture

- Displays architecture recommendations when available
- Shows "No Architecture Data Available" if not run
- **Done** button to exit workflow

---

## Comparison: Company Portal vs Our Local System

| Aspect | Company Portal (Scout-itAI) | Our Local System (modernizeit-ui) |
|--------|----------------------------|-----------------------------------|
| **UI Pattern** | 4-step wizard | Node-based workflow canvas |
| **Hosting** | AWS (S3, EC2, Bedrock) | Local (files + MongoDB) |
| **Users** | Multi-tenant (accounts/users) | Single user |
| **App Management** | Portfolio with 78+ apps | Direct workflow execution |
| **QA Step** | Built-in with pass/fail scores | Test Generation node (new) |
| **Navigation** | Linear stepper | Flexible node connections |
| **State** | Server-side (AWS) | Local files + job tracking |

---

## Flow Mapping: Portal Steps → Our API

| Portal Step | Our API Endpoints |
|-------------|-------------------|
| **1. Analysis** | `/ingest/upload` + `/codeanalysis` + `/dataanalysis` + `/discovery/analyze` |
| **2. O&T** | `/coderefactor` + `/java-packaging/start` |
| **3. QA** | `/test-generation/smart` (NEW) |
| **4. Architecture** | `/architecture/analyze` |

---

## Key Observations

### What the Portal Does Well
1. **Simple 4-step flow** - Easy for non-technical users
2. **Portfolio management** - Track many applications
3. **Progress tracking** - Clear status at every step
4. **AI summaries** - Business Purpose, Data Flows shown inline
5. **QA scoring** - Pass rate, score, recommendation, critical issues
6. **Export capabilities** - Download ZIP, Export reports

### What Our System Adds
1. **Flexible workflows** - Not locked into 4 steps
2. **Node-based composition** - Mix and match flows
3. **Pipeline templates** - Full Pipeline with all stages
4. **Test Generation** - Two modes (Stubs + Smart Tests)
5. **Local execution** - No cloud dependency for dev
6. **MCP integration** - Claude can query artifacts

---

## Integration Considerations

### For Company Portal to Use Our API

1. **Authentication** - Add multi-tenant auth layer
2. **Storage** - Switch from local files to S3
3. **Job Tracking** - Use DynamoDB instead of SQLite
4. **AI Calls** - Already using Bedrock (compatible)
5. **File Upload** - S3 presigned URLs instead of local

### API Endpoints Ready for Portal

| Endpoint | Portal Step | Status |
|----------|-------------|--------|
| POST /ingest/upload | Analysis | Ready |
| POST /codeanalysis | Analysis | Ready |
| POST /dataanalysis | Analysis | Ready |
| POST /discovery/analyze | Analysis | Ready |
| POST /coderefactor | O&T | Ready |
| POST /java-packaging/start | O&T | Ready |
| POST /test-generation/smart | QA | Ready (NEW) |
| POST /architecture/analyze | Architecture | Ready |

---

## Screenshots Reference

| Image | Screen |
|-------|--------|
| 01_application_portfolio.jpeg | Application Portfolio grid |
| 02_portfolio_summary.jpeg | Portfolio Summary dashboard |
| 03_analysis_queue_upload.jpeg | Analysis Queue with files |
| 04_analysis_results_file.jpeg | AI Analysis Overview expanded |
| 05_flow_reports_tabs_overview.jpeg | Flow report tabs (Overview) |
| 06_ot_code_generation.jpeg | O&T Code Generation |
| 07_qa_results.jpeg | QA Results with scores |
| 08_architecture_step.jpeg | Architecture step |

---

## Next Steps (When Ready)

1. [ ] Define API contract for Portal integration
2. [ ] Add S3 storage adapter
3. [ ] Add multi-tenant authentication
4. [ ] Map Portal UI actions to API calls
5. [ ] Deploy to AWS (EC2/ECS)
6. [ ] Connect Portal frontend to API

---

*Document created: December 26, 2025*
*Source docs: /Users/timhiggins/Desktop/pooja_modernizeit/p-docs*
