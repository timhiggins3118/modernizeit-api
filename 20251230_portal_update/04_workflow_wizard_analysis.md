# Workflow Wizard - Step 1: Analysis - December 30, 2025

## The 4-Step Modernization Wizard

**URL Pattern:** `dev.scoutitai.com/home/modernzeit/application-management/config/app_{AppName}_{AppID}`

**Example:** `app_ModernizationTesting_1764156410`

When user clicks an application from the Portfolio, they enter this 4-step wizard.

---

## Sidebar Navigation

| Step | Name | Description |
|------|------|-------------|
| 1 | **Analysis** | Upload files, run Code Analysis |
| 2 | **O&T** | Optimization & Transformation (Refactor) |
| 3 | **QA** | Quality Assurance, Test Generation |
| 4 | **Architecture** | AWS recommendations, deployment |

Each step = ~20-25% progress on the Portfolio Summary.

---

## Step 1: Analysis View

### Header
- Title: "Modernization Process | {ApplicationName}"
- Subtitle: "Track your application through the 4-step modernization workflow"
- Buttons: Previous (disabled), Next

### Analysis Queue Section

**Action Buttons:**
- "Upload Documents" - upload COBOL files
- "Analyze Application" - run Code Analysis

**File Table Columns:**
| Column | Description |
|--------|-------------|
| File Name | COBOL source file name |
| Size | File size (e.g., 1.19 KB) |
| Status | uploaded, analyzing, Analyzed |
| Actions | Delete button |

### Expanded File Details

When a file row is expanded, shows:

| Field | Example Value |
|-------|---------------|
| File Name | Customer_Billing_System.cob |
| File Type | COBOL_PROGRAM |
| Total Lines | 39 |
| Paragraphs | 2 |
| Confidence | 100% |

### AI Analysis Overview

| Field | Example Value |
|-------|---------------|
| Complexity | MEDIUM (badge) |
| Analyzer | BedrockAnalyzerPerFile |

### Business Purpose (AI-Generated)
```
"This appears to be a customer billing system that calculates charges
based on customer usage. The program processes customer records with
usage data to generate billing amounts, likely for a utility or
service company."
```

### Data Flows (AI-Generated)
```
"The program processes customer records containing CUST-ID, CUST-NAME,
and USAGE data. It transforms this data using WS-RATE to calculate
BILL-AMOUNT. The EOF-FLAG suggests sequential file processing. Data
appears to flow from input customer records through calculation logic
to produce billing outputs."
```

---

## API Endpoints for Step 1

### Upload Files
```
POST /uidata/api/applications/files/upload
Body: multipart/form-data with file
```

### Run Analysis
```
POST /uidata/api/files/{file_id}/analyze
```

### Get Analysis Results
```
GET /uidata/api/files/{file_id}/analysis
```

---

## Expected Analysis Response Schema

```json
{
  "file_id": "file_xxx",
  "file_name": "Customer_Billing_System.cob",
  "file_type": "COBOL_PROGRAM",
  "total_lines": 39,
  "paragraphs": 2,
  "confidence": 100,
  "status": "Analyzed",

  "ai_analysis": {
    "complexity": "MEDIUM",
    "analyzer": "BedrockAnalyzerPerFile",
    "business_purpose": "This appears to be a customer billing system...",
    "data_flows": "The program processes customer records containing..."
  }
}
```

---

## What Our Code Analysis Must Produce

Our `/codeanalysis` endpoint output needs to include:

| Field | Source |
|-------|--------|
| file_type | Parser detection |
| total_lines | Line count |
| paragraphs | Procedure parser |
| confidence | Parse success rate |
| complexity | AI analysis or heuristic |
| business_purpose | **AI-generated** (Bedrock) |
| data_flows | **AI-generated** (Bedrock) |

### Current vs Required

| Feature | Our Engine | Required |
|---------|-----------|----------|
| Parse COBOL | ✅ Yes | ✅ |
| Count lines | ✅ Yes | ✅ |
| Count paragraphs | ✅ Yes | ✅ |
| Generate Java | ✅ Yes | ✅ |
| Complexity rating | ❓ Check | ✅ |
| Business Purpose | ❓ Check | ✅ |
| Data Flows | ❓ Check | ✅ |

**Need to verify:** Does our Code Analysis generate the AI summaries (Business Purpose, Data Flows)?

---

## Tricky Parts

1. **Per-file analysis** - UI shows results per file, expandable
2. **AI summaries** - Need Bedrock integration for business descriptions
3. **Status tracking** - Must update file status (uploaded → analyzing → Analyzed)
4. **Response format** - Must match what UI expects exactly

---

*Created: December 30, 2025*
