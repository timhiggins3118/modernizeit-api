# Migration Ideas v1 - Portal Integration Strategy

**Date:** December 26, 2025
**Status:** Initial Ideas - Needs Refinement
**Context:** Integrating ModernizeIT API/UI with Company Portal (Scout-itAI)

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Company Portal Shell                      │
│  (Scout-itAI React - dev.scoutitai.com)                     │
│  ├── MonitorIT                                               │
│  ├── AnalyzeIT                                               │
│  ├── ManageIT                                                │
│  ├── ModernizeIT  ← TARGET FOR REPLACEMENT                  │
│  ├── LearnIT                                                 │
│  ├── AGI                                                     │
│  └── AdminIT                                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Go Backend (uidata:8086)                        │
│  - DynamoDB (scout_applications, scout_files)               │
│  - S3 (scoutitmodernization)                                │
│  - Proxies to AWS Lambda APIs                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              AWS Lambda APIs                                 │
│  - hzz9izcu47 (Analysis flows)                              │
│  - msir2392qb (Java Generation)                             │
└─────────────────────────────────────────────────────────────┘
```

---

## What We Replace vs Keep

| Layer | Current | Our Replacement | Action |
|-------|---------|-----------------|--------|
| Portal Shell | React nav/auth | - | **KEEP** |
| ModernizeIT UI | 4-step wizard | Node canvas | **REPLACE** |
| Backend API | Go (uidata) | Python FastAPI | **REPLACE** |
| Lambda APIs | AWS Lambdas | Our engines | **REPLACE** |
| Storage | DynamoDB + S3 | SQLite + Local | **TBD** |
| Auth | JWT + X-Account-Id | - | **KEEP** |

---

## Integration Options

### Option A: Iframe Embed (Quickest)

```
Portal Shell
├── ModernizeIT (4-step wizard) ← Keep for basic users
└── Advanced Flows (new menu item)
    └── <iframe src="our-ui.com/app?account={id}">
```

| Pros | Cons |
|------|------|
| Zero risk to existing portal | Auth token passing complexity |
| Our app runs independently | iframe security restrictions |
| Fast to implement | Feels "tacked on" |
| Can iterate independently | Duplicate navigation/styling |

---

### Option B: Component Integration (Medium Effort)

```
Portal Shell (React)
├── ModernizeIT
│   ├── Simple Mode (their wizard - preserved)
│   └── Advanced Mode (our canvas - embedded as React component)
```

**Implementation:**
1. Export workflow canvas as npm package
2. Import into their React app
3. Shared state via props/callbacks
4. Match their Ant Design theming

| Pros | Cons |
|------|------|
| Native feel within portal | Dependency coupling |
| Shared auth/session | Must match React 18.3.1 |
| Can share components | Build/deploy coordination |
| Professional integration | Their release cycle affects us |

---

### Option C: Full Takeover (Most Work)

```
Portal Shell (React)
└── ModernizeIT → COMPLETE REPLACEMENT
    ├── Portfolio Dashboard (reimplemented)
    ├── App Detail → Workflow Canvas
    └── All flows via our API
```

| Pros | Cons |
|------|------|
| Clean architecture | Highest risk |
| Single source of truth | Must match ALL contracts |
| Full control over UX | Feature parity required first |
| No duplicate code | Longer timeline |

---

## Recommended: Hybrid Phased Approach

### Phase 1: Parallel Deploy
- Keep their wizard as-is
- Add "Developer View" menu item
- Our app opens in new tab (separate deploy)
- Shared auth via URL params (encrypted token)

### Phase 2: API Compatibility
- Create `/uidata/*` routes in our Python API
- Point their React to our API (feature flag)
- Test side-by-side
- Migrate to their DynamoDB schema

### Phase 3: UI Integration
- Embed our canvas as React component
- Replace wizard internals with our canvas
- Single "ModernizeIT" experience
- Deprecate old Go routes

---

## Data Compatibility

### Their Model (DynamoDB)

```go
// scout_applications table
Application {
    ApplicationID    string    // "app_0U812_1735123456"
    AccountID        string    // "0U812"
    Name             string
    Status           string    // "Ready", "Processing", "Error"
    FileCount        int
    // 20+ job ID fields...
}

// scout_files table
FileRecord {
    FileID           string    // "file_abc123"
    ApplicationID    string
    FileName         string
    FileStatus       string    // "uploaded", "analyzed", "transformed"
    // Status for each pipeline stage...
}
```

### Our Model (SQLite)

```python
# jobs table
Job {
    job_id           string    # "ca3_job_0U812_..."
    scout_account_id string
    application_name string
    status           string
    # Job-centric, not app-centric
}
```

### Gap Analysis
- **Theirs:** Application-centric (app → files → statuses)
- **Ours:** Job-centric (flow → job → results)

### Resolution Options

1. **Adapt to theirs** - Add application_id, use their DynamoDB
2. **Keep both** - Sync layer between SQLite and DynamoDB
3. **Replace theirs** - Migrate to our schema (risky)

---

## API Compatibility Layer

Create routes that match their contracts:

```python
# Match /uidata/api/applications
@router.get("/uidata/api/applications")
async def list_applications(limit: int = 100, account_id: str = Header(...)):
    # Return THEIR format
    return {"items": [...], "count": n}

# Match /uidata/api/applications/files/upload
@router.post("/uidata/api/applications/files/upload")
async def upload_file(file: UploadFile, application_id: str = Form(...)):
    return {"file_id": "...", "status": "uploaded"}

# Match /uidata/codetransform/upload
@router.post("/uidata/codetransform/upload")
async def launch_transform(body: TheirTransformRequest):
    # Call our engine, return THEIR format
    pass
```

---

## Developer View Concept

### Menu Integration
```jsx
<Menu.Item key="modernize">
  <Link to="/modernize">ModernizeIT</Link>
</Menu.Item>
<Menu.Item key="modernize-advanced">
  <Link to="/modernize/advanced">Developer View</Link>
</Menu.Item>
```

### Implementation Options

1. **Same app, different route**
   ```jsx
   <Route path="/modernize" element={<TheirWizard />} />
   <Route path="/modernize/advanced" element={<OurCanvas />} />
   ```

2. **External link with auth**
   ```jsx
   <ExternalRedirect to={`https://modernizeit.com/app?token=${token}`} />
   ```

3. **Iframe with postMessage**
   ```jsx
   <AdvancedViewIframe
     src="https://modernizeit.com/app"
     onAuth={(iframe) => iframe.postMessage({type: 'auth', token})}
   />
   ```

---

## Do Not Break

1. **Existing workflows** - 4-step wizard must keep working
2. **Data integrity** - Don't corrupt DynamoDB
3. **Auth flow** - JWT + X-Account-Id respected
4. **API contracts** - Same response formats
5. **File statuses** - React depends on status strings
6. **Job IDs** - Keep patterns (ca2_job_, etc.)

---

## Open Decisions

| Decision | Options | Leaning |
|----------|---------|---------|
| Integration approach | A/B/C/Hybrid | Hybrid |
| Data storage | DynamoDB / SQLite / Both | TBD |
| Auth passing | URL params / postMessage / shared session | TBD |
| Deploy location | Same domain / Subdomain / Separate | TBD |
| Feature parity | What's MVP? | TBD |

---

## Feature Parity Checklist

| Feature | Their Portal | Our API | Status |
|---------|--------------|---------|--------|
| Application CRUD | Yes | No | Need to add |
| File upload | Yes | Yes | Ready |
| Code Analysis | Yes | Yes | Ready |
| Data Analysis | Yes | Yes | Ready |
| Discovery/ROI | Yes | Yes | Ready |
| Code Transform | Yes | Yes | Ready |
| Java Packaging | Yes | Yes | Ready |
| QA/Smart Tests | Yes | Yes | Ready |
| Portfolio Dashboard | Yes | No | Need to add |
| Batch status check | Yes | No | Need to add |

---

## Next Steps

1. Decide integration approach
2. Decide data strategy
3. Decide auth mechanism
4. Build Application CRUD endpoints
5. Build compatibility layer
6. Prototype Developer View

---

*Document created: December 26, 2025*
*Status: Initial ideas - needs team review and refinement*
