# Portfolio Summary Dashboard - December 30, 2025

## What This Page Shows

**URL:** `dev.scoutitai.com/home/modernzeit/application-management/portfolio-summary`

This is an **aggregation dashboard** that shows overall modernization progress across all applications.

---

## Summary Cards

| Metric | Value | Description |
|--------|-------|-------------|
| Total Applications | 78 | Across all stages |
| Total Files | 546 | Ready for modernization |
| Avg Progress | 36% | Across all applications |
| Near Completion | 2 | 75%+ complete |

---

## Applications Table

Columns displayed:
- **Application Name** - with optional description
- **Files** - count of COBOL files
- **Progress** - percentage bar (0-100%)
- **Status** - Starting, In Progress, Complete
- **Created** - creation date
- **Last Updated** - last activity date
- **Actions** - navigate arrow

### Sample Data
| Application | Files | Progress | Status |
|-------------|-------|----------|--------|
| AppointmentBooking | 16 | 0% | Starting |
| poojatesting3Nov | 2 | 40% | In Progress |
| SimpleArithmetic | 2 | 40% | In Progress |
| Fresh17Two | 2 | 20% | Starting |
| TestAgainT | 1 | 40% | In Progress |
| TestwithTim34 | 1 | 0% | Starting |
| AppScore | 6 | 48% | In Progress |
| AnalyzeApplication27 | 1 | 40% | In Progress |
| ZipExtractTest | 6 | 0% | Starting |

---

## API Endpoint Required

The UI calls:
```
GET /uidata/api/portfolio/summary
```

### Expected Response (inferred)
```json
{
  "total_applications": 78,
  "total_files": 546,
  "avg_progress": 36,
  "near_completion": 2,
  "applications": [
    {
      "application_id": "app_xxx",
      "application_name": "AppointmentBooking",
      "description": "",
      "file_count": 16,
      "progress": 0,
      "status": "Starting",
      "created_at": "2025-10-28",
      "updated_at": "2025-11-04"
    }
  ]
}
```

---

## Progress Calculation

Progress appears to be based on workflow step completion:

| Step | Weight |
|------|--------|
| Analysis | 20% |
| O&T (Refactor) | 20% |
| QA | 20% |
| Architecture | 20% |
| Complete | 20% |

- **0%** = Starting (no steps complete)
- **20%** = Analysis done
- **40%** = Analysis + O&T done
- **etc.**

---

## What We Need To Build

### New Endpoint
```python
# api/routes/portfolio.py
@router.get("/api/portfolio/summary")
async def get_portfolio_summary(account_id: str):
    """
    Aggregate stats across all applications for the dashboard.
    """
    # Query all applications for account
    # Calculate totals and averages
    # Return summary + application list
```

### Data Requirements
- Count applications per account
- Sum file counts across applications
- Calculate average progress
- Count applications >= 75% complete
- Return sorted application list

---

## Updated Endpoint List

| Endpoint | Purpose | Priority |
|----------|---------|----------|
| `GET /api/applications` | List applications | High |
| `POST /api/applications` | Create application | High |
| `GET /api/applications/{id}` | Get app details | High |
| `PUT /api/applications/{id}` | Update app | High |
| `DELETE /api/applications/{id}` | Delete app | Medium |
| `GET /api/portfolio/summary` | **Dashboard aggregation** | High |
| `GET /api/applications/files/list` | List files | High |
| `POST /api/applications/files/upload` | Upload file | High |

---

*Created: December 30, 2025*
