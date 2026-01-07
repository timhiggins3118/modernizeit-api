# Live Portal Analysis - December 30, 2025

## What The Live App Shows

**URL:** `dev.scoutitai.com/home/modernzeit/application-management`

**Scout-itAI Portal** - Application Portfolio page

### Current State
- **78 real applications** being managed
- Each card shows: name, app_id, description, file count, created date
- Tags: `COBOL` → `JAVA` (the transformation)
- Users click a card to enter the 4-step wizard (Analysis → O&T → QA → Architecture)

---

## What The UI Is Calling

### List Applications
```
/uidata/api/applications  →  lists these 78 apps
```

### When User Clicks An App
```
/uidata/api/applications/{id}           →  app details
/uidata/api/applications/files/list     →  COBOL files
/uidata/api/files/{id}/analyze          →  run Code Analysis
/uidata/codetransform/upload            →  run Refactor + Dependency + Monolith
/uidata/app-creator/modernize           →  run Java Packaging
/uidata/qa-agent/process-files          →  run QA/Tests
```

### From cobolModernizationService.ts
```typescript
// All calls go through goInstance which prefixes /uidata/
'/uidata/api/applications'              // List/create apps
'/uidata/api/applications/files/upload' // Upload files
'/uidata/api/files/{id}/analyze'        // Analyze
'/uidata/codetransform/upload'          // Transform
'/uidata/app-creator/modernize'         // Java generation
'/uidata/qa-agent/process-files'        // QA
'/uidata/api/portfolio/summary'         // Portfolio
```

---

## The Deployment Reality

**This IS production.** Real users. Real data. 78 applications.

### Current Architecture
```
Live UI (React) → uidata (Go @ 8080) → AWS Lambdas → S3/DynamoDB
```

### Target Architecture
```
Live UI (React) → Our FastAPI (@ 8000) → Local processing → Local storage
```

---

## What We Need To Do

### 1. Add Application Management Endpoints
- `GET /api/applications` - List all applications
- `POST /api/applications` - Create application
- `GET /api/applications/{id}` - Get app details
- `PUT /api/applications/{id}` - Update app
- `DELETE /api/applications/{id}` - Delete app

### 2. Add File Management Endpoints
- `GET /api/applications/files/list` - List files in app
- `POST /api/applications/files/upload` - Upload file
- `DELETE /api/files/{id}` - Delete file

### 3. Map Existing Flow Endpoints
| UI Calls | Our FastAPI |
|----------|-------------|
| `/uidata/api/files/{id}/analyze` | `/codeanalysis` |
| `/uidata/codetransform/upload` | `/coderefactor` + `/dependencymapper` + `/monolithidentifier` |
| `/uidata/app-creator/modernize` | `/java-packaging/start` |
| `/uidata/qa-agent/process-files` | `/test-generation/stubs` |

### 4. Update UI Configuration
- Change `goInstance` base URL from uidata to our FastAPI
- Or add route aliases to match uidata paths

---

## Our Flows Are Ready

| Flow | Endpoint | Status |
|------|----------|--------|
| Ingest | `/ingest/upload` | ✅ Working |
| Code Analysis | `/codeanalysis` | ✅ Working (BUILD SUCCESS) |
| Code Refactor | `/coderefactor` | ✅ Working |
| Dependency Mapper | `/dependencymapper` | ✅ Working |
| Monolith Identifier | `/monolithidentifier` | ✅ Working |
| Data Analysis | `/dataanalysis` | ✅ Working |
| Discovery | `/discovery/analyze` | ✅ Working |
| Architecture | `/architecture/analyze` | ✅ Working |
| Java Packaging | `/java-packaging/start` | ✅ Working |
| Test Generation | `/test-generation/stubs` | ✅ Working |

**We just need the application/file management layer and endpoint mapping.**

---

*Created: December 30, 2025*
