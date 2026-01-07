# Scout-itAI React Codebase Analysis

**Date:** December 26, 2025
**Status:** Analysis Complete
**Source:** `/Users/timhiggins/Desktop/pooja_modernizeit/scoutitai-react/`

---

## Overview

This is the **Company Portal UI** - a React/TypeScript application that powers the Scout-itAI platform at `dev.scoutitai.com`. It's a multi-module enterprise platform with ModernizeIT being one of several modules.

---

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.3.1 | UI framework |
| TypeScript | 5.6.2 | Type safety |
| Vite | 6.0.5 | Build tool |
| Ant Design | 5.24.0 | Primary UI components |
| Material-UI | 6.3.1 | Secondary UI components |
| Redux Toolkit | 2.5.0 | State management |
| Redux Saga | 1.3.0 | Async operations |
| React Query | 5.62.16 | Data fetching/caching |
| Axios | 1.7.9 | HTTP client |
| React Router | 7.1.2 | Navigation |
| Chart.js | 4.4.7 | Charts |
| Recharts | 2.15.0 | Charts |
| ApexCharts | 4.5.0 | Charts |
| Formik + Yup | 2.4.6 / 1.6.1 | Forms & validation |
| Styled Components | 6.1.15 | CSS-in-JS |

---

## Project Structure

```
scoutitai-react/
├── src/
│   ├── components/
│   │   ├── modernizeIT/              ← COBOL modernization module
│   │   │   ├── ModernizeITDashboard.tsx
│   │   │   └── applicationManagement/
│   │   │       ├── ApplicationPortfolioManagement.tsx
│   │   │       ├── ApplicationPortfolioConfiguration.tsx
│   │   │       ├── ApplicationPortfolioBuilder.tsx
│   │   │       ├── ApplicationPortfolioEditor.tsx
│   │   │       ├── PortfolioSummary.tsx
│   │   │       └── steps/
│   │   │           ├── AnalysisStep.tsx
│   │   │           ├── OrchestrationStep.tsx
│   │   │           ├── QAStep.tsx
│   │   │           ├── CodeAnalysisReport.tsx
│   │   │           ├── TransformResultsReport.tsx
│   │   │           ├── QAReportView.tsx
│   │   │           └── CostAnalysisReport.tsx
│   │   ├── agi/                      ← AI Agents module
│   │   │   ├── agentics/
│   │   │   ├── AI-dashboard/
│   │   │   ├── knowledge-bases/
│   │   │   ├── model-configuration/
│   │   │   └── AgentAlerts/
│   │   ├── adminIT/                  ← Admin module
│   │   ├── manageIT/                 ← Management module
│   │   ├── monitorIT/                ← Monitoring module
│   │   ├── settings/                 ← User settings
│   │   ├── customer-success/
│   │   ├── dashboard/
│   │   └── universal/
│   ├── services/
│   │   └── cobolModernizationService.ts  ← ModernizeIT API service
│   ├── utils/
│   │   ├── goServerHelper.ts         ← Axios instance with interceptors
│   │   ├── theme.ts                  ← Theme configuration
│   │   └── helper.ts
│   ├── constants/
│   │   ├── RestConstant.ts           ← API base URLs
│   │   └── config.ts
│   ├── hooks/
│   │   └── useGoHttp.ts              ← Custom HTTP hook
│   ├── common-components/            ← Shared components
│   ├── mocks/                        ← MSW mock handlers
│   └── test/
├── public/
├── docs/
├── getting-started/
├── code-reviews/
└── package.json
```

---

## ModernizeIT Module Architecture

### Component Hierarchy

```
ModernizeITDashboard
└── ApplicationPortfolioManagement
    ├── PortfolioSummary (dashboard view)
    └── ApplicationPortfolioConfiguration (4-step wizard)
        ├── Step 1: AnalysisStep
        │   └── CodeAnalysisReport (expandable)
        ├── Step 2: OrchestrationStep (O&T)
        │   └── TransformResultsReport (drawer)
        ├── Step 3: QAStep
        │   └── QAReportView (drawer)
        └── Step 4: Architecture (placeholder)
```

### Data Flow

```
User uploads file
    ↓
AnalysisStep.tsx
    → POST /uidata/api/applications/files/upload
    → POST /uidata/api/files/{id}/analyze
    → Poll: POST /uidata/api/analysis/status
    ↓
OrchestrationStep.tsx
    → POST /uidata/codetransform/upload
    → Poll: GET /uidata/codetransform/status/{id}
    → GET /uidata/codetransform/results/{id}
    → POST /uidata/app-creator/modernize (code gen)
    ↓
QAStep.tsx
    → POST /uidata/qa-agent/process-files
    → GET /uidata/api/applications/{id}/qa/history
```

---

## API Service: cobolModernizationService.ts

### Application Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `listApplications` | GET `/uidata/api/applications?limit=100` | List all apps |
| `createApplication` | POST `/uidata/api/applications` | Create app |
| `getApplicationDetails` | GET `/uidata/api/applications/{id}` | Get app details |
| `updateApplication` | PUT `/uidata/api/applications/{id}` | Update app |
| `deleteApplication` | DELETE `/uidata/api/applications/{id}` | Delete app |

### File Management

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `listApplicationFiles` | GET `/uidata/api/applications/files/list?application_id={id}` | List files |
| `uploadFileToApplication` | POST `/uidata/api/applications/files/upload` | Upload file |
| `deleteCOBOLFile` | DELETE `/uidata/api/applications/{appId}/files/{fileId}` | Delete file |

### Analysis

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `analyzeFile` | POST `/uidata/api/files/{id}/analyze?analysis_type=both` | Run analysis |
| `getAnalysisStatus` | POST `/uidata/api/analysis/status` | Check status (batch) |
| `getFileAnalysisResults` | GET `/uidata/api/files/{id}/analysis?section=analysis_text` | Get results |

### Code Transformation

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `launchCodeTransform` | POST `/uidata/codetransform/upload` | Start transform |
| `getCodeTransformStatus` | GET `/uidata/codetransform/status/{id}` | Check status |
| `getCodeTransformResults` | GET `/uidata/codetransform/results/{id}` | Get results |

### Code Generation (App Creator)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `launchModernization` | POST `/uidata/app-creator/modernize` | Generate code |
| `getModernizationStatus` | GET `/uidata/app-creator/status/{id}` | Check status |
| `getModernizationResults` | GET `/uidata/app-creator/results/{id}` | Get results |

### QA Processing

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `launchQAProcessing` | POST `/uidata/qa-agent/process-files` | Run QA |
| `getApplicationQAHistory` | GET `/uidata/api/applications/{id}/qa/history` | QA history |
| `getFileQAHistory` | GET `/uidata/api/files/{id}/qa/history` | File QA history |

### Other

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `getPortfolioSummary` | GET `/uidata/api/portfolio/summary` | Dashboard stats |
| `getCostBenefitAnalysis` | GET `/uidata/api/cost-benefit/{discoveryJobId}` | ROI analysis |

---

## Key Implementation Patterns

### 1. Account ID Header

All API calls include `X-Account-Id` header, added automatically by the Axios interceptor in `goServerHelper.ts`. The account ID comes from the Redux store.

```typescript
// goServerHelper.ts interceptor adds:
headers: {
  'X-Account-Id': accountId  // from Redux store
}
```

### 2. Polling Pattern

Async jobs use polling with 20-second intervals:

```typescript
const pollIntervalMs = 20000;  // 20 seconds
const maxPolls = 30;           // ~10 minutes max

const pollInterval = setInterval(async () => {
  const statusResponse = await cobolModernizationService.getAnalysisStatus(jobIds);
  if (statusResponse.data?.overall_status !== 'processing') {
    clearInterval(pollInterval);
    // Handle completion
  }
}, pollIntervalMs);
```

### 3. File Status Flow

```
uploaded → analyzing/processing → analyzed → transformed → qa_complete
```

### 4. Application Type

```typescript
type Application = {
  application_id: string;
  application_name: string;
  account_id?: string;
  description?: string;
  status: 'active' | 'inactive' | 'processing' | 'error' | 'Ready' | 'Processing' | 'Error';
  created_at: string;
  updated_at: string;
  file_count?: number;
  tags?: string[];
  metadata?: {
    project_type?: string;
    source_language?: string;
    target_language?: string;
    ai_enabled?: boolean;
    enterprise?: boolean;
  };
};
```

### 5. QA Report Type

```typescript
interface QAReport {
  id: string;
  fileId: string;
  applicationName: string;
  testingRound: number;
  completedDate: Date;
  testResults: string;        // "83.1%"
  overallScore: number;       // 78.1
  recommendation: 'Deploy' | 'Retest' | 'Block';
  criticalIssues: string;
  nextSteps: string[];
  detailedReport: string;
  testSummary?: {
    test_case: string;
    breakdown: {
      Functional_test: string;
      Integration_test: string;
      Performance_test: string;
      Security_test: string;
    };
  };
}
```

---

## Gap Analysis: Their Backend vs Our API

### What They Have (Go Backend at `/uidata/*`)

| Their Endpoint | Description |
|----------------|-------------|
| `/uidata/api/applications` | Application CRUD |
| `/uidata/api/applications/files/list` | List files in app |
| `/uidata/api/applications/files/upload` | Upload to app |
| `/uidata/api/files/{id}/analyze` | Analyze single file |
| `/uidata/api/analysis/status` | Batch status check |
| `/uidata/codetransform/upload` | Launch transformation |
| `/uidata/codetransform/status/{id}` | Transform status |
| `/uidata/codetransform/results/{id}` | Transform results |
| `/uidata/qa-agent/process-files` | Run QA agent |
| `/uidata/app-creator/modernize` | Generate code package |
| `/uidata/api/portfolio/summary` | Dashboard metrics |

### What We Have (Python FastAPI)

| Our Endpoint | Maps To |
|--------------|---------|
| `POST /ingest/upload` | `/uidata/api/applications/files/upload` |
| `POST /codeanalysis` | `/uidata/api/files/{id}/analyze` |
| `GET /codeanalysis/status/{id}` | `/uidata/api/analysis/status` |
| `POST /coderefactor` | `/uidata/codetransform/upload` |
| `POST /test-generation/smart` | `/uidata/qa-agent/process-files` |
| `POST /java-packaging/start` | `/uidata/app-creator/modernize` |

### What We Need to Add

| Endpoint | Purpose | Priority |
|----------|---------|----------|
| `GET/POST /applications` | Application CRUD | High |
| `GET /applications/{id}/files` | List files in app | High |
| `GET /portfolio/summary` | Dashboard metrics | Medium |
| `POST /analysis/status` | Batch status check | Medium |

---

## UI Component Details

### AnalysisStep.tsx

- File upload with drag-drop
- Table with columns: Checkbox, File Name, Size, Status, Progress, Complexity, Actions
- Expandable rows show `CodeAnalysisReport`
- Select files → "Analyze Application" button
- Status icons: Uploaded (clock), Analyzing (spin), Analyzed (check), Failed (x)

### OrchestrationStep.tsx (O&T)

- Shows analyzed files only
- Table with columns: Select, File Name, AI Status, Code Quality, Progress, Actions
- Actions: View Results, Generate Code
- Drawer shows `TransformResultsReport`
- Status: ready → transforming → completed

### QAStep.tsx

- Two sections:
  1. "Files from O&T" - files with `codezip` ready for QA
  2. "QA Analysis Results" - completed QA reports
- QA Results columns: Application, Round, Test Results, Score, Recommendation, Critical Issues, Actions
- Recommendations with colors: Deploy (green), Retest (yellow), Block (red)
- Export reports as JSON

---

## Development Commands

```bash
npm run dev          # Start dev server
npm run build        # Build for production
npm run lint         # Run ESLint
npm run lint:fix     # Fix lint errors
npm run format       # Prettier format
npm run test         # Run tests
npm run test:ui      # Test UI
npm run preview      # Preview build
```

---

## Integration Path

To connect our API to this portal:

1. **Option A: Adapter Layer**
   - Create `/uidata/*` routes in our FastAPI that match their expected endpoints
   - Translate requests/responses to our internal format

2. **Option B: Update Portal**
   - Modify `cobolModernizationService.ts` to point to our endpoints
   - Update `RestConstant.ts` with our base URL

3. **Required Changes Either Way:**
   - Add `X-Account-Id` header support
   - Add Application CRUD endpoints
   - Match their response formats
   - Support batch status checks

---

## Files Reference

| File | Purpose |
|------|---------|
| `package.json` | Dependencies and scripts |
| `CLAUDE.md` | AI coding guidelines |
| `src/services/cobolModernizationService.ts` | All API calls |
| `src/utils/goServerHelper.ts` | Axios instance |
| `src/components/modernizeIT/applicationManagement/` | Main UI components |
| `src/constants/RestConstant.ts` | API URLs |

---

*Document created: December 26, 2025*
*Source: /Users/timhiggins/Desktop/pooja_modernizeit/scoutitai-react/*
