# DynamoDB Schema - January 1, 2026

Documented from live exploration of AWS DynamoDB.

---

## Tables for ModernizeIT

| Table | Purpose |
|-------|---------|
| `{account}_applications` | Application/project metadata |
| `{account}_files` | File records per application |
| `{account}_application_analysis_history` | Historical analysis runs |
| `{account}_file_analysis_history` | Per-file analysis history |
| `{account}_modernize` | Modernization state (unclear) |

**Account 341 stats:** 78 applications, 548 files

---

## Application Schema

**Table:** `{account}_applications`
**Primary Key:** `application_id`

```json
{
  "application_id": "app_AppointmentBooking_1761645037",
  "application_name": "AppointmentBooking",
  "account_id": "341",
  "status": "active",
  "file_count": "16",
  "created_at": "2025-10-28T09:50:37Z",
  "updated_at": "2025-11-04T06:43:31Z",
  "metadata": {
    "project_type": "COBOL_MODERNIZATION",
    "source_language": "COBOL",
    "target_language": "JAVA"
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `application_id` | String | Primary key, format: `app_{name}_{timestamp}` |
| `application_name` | String | Display name |
| `account_id` | String | Customer account ID |
| `status` | String | `active`, `archived`, etc. |
| `file_count` | String | Number of files (stored as string!) |
| `created_at` | String | ISO 8601 timestamp |
| `updated_at` | String | ISO 8601 timestamp |
| `metadata` | Object | Nested config object |

### Metadata Object

| Field | Type | Description |
|-------|------|-------------|
| `project_type` | String | `COBOL_MODERNIZATION` |
| `source_language` | String | `COBOL` |
| `target_language` | String | `JAVA` |

---

## File Schema

**Table:** `{account}_files`
**Primary Key:** `file_id`

```json
{
  "file_id": "file_app_SanityOnModernization_1764156984_1764157005349650425",
  "application_id": "app_SanityOnModernization_1764156984",
  "account_id": "341",
  "file_name": "01_CustomerMgmt.cob",
  "file_type": "cobol",
  "file_size": "580",
  "status": "analyzed",
  "analysis_status": "analyzed",
  "s3_path": "s3://scoutitmodernization/341/SanityOnModernization/20251126_113645_01_CustomerMgmt.cob",
  "uploaded_at": "2025-11-26T11:36:45Z",
  "updated_at": "2025-11-27T06:21:42Z",
  "version": "1",

  "cobol_job_id": "",
  "refactor_job_id": "",
  "dependency_job_id": "",
  "monolith_job_id": "",
  "data_job_id": "",
  "discovery_job_id": "",
  "architecture_job_id": "",
  "jgv3_generation_job_id": "",
  "jgv3_status": "",
  "jgv3_flow_status": "",
  "jgv3_workflow_status": ""
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `file_id` | String | Primary key, format: `file_{app_id}_{timestamp}` |
| `application_id` | String | Foreign key to applications |
| `account_id` | String | Customer account ID |
| `file_name` | String | Original filename |
| `file_type` | String | `cobol`, `copybook`, `jcl` |
| `file_size` | String | Size in bytes (stored as string!) |
| `status` | String | `uploaded`, `analyzing`, `analyzed`, `failed` |
| `analysis_status` | String | Duplicate of status? |
| `s3_path` | String | Full S3 URI to actual file |
| `uploaded_at` | String | ISO 8601 timestamp |
| `updated_at` | String | ISO 8601 timestamp |
| `version` | String | Version number |

### Job Tracking Fields

Each workflow step has a job ID field:

| Field | Workflow Step |
|-------|---------------|
| `cobol_job_id` | Code Analysis |
| `refactor_job_id` | Code Refactor |
| `dependency_job_id` | Dependency Mapper |
| `monolith_job_id` | Monolith Identifier |
| `data_job_id` | Data Analysis |
| `discovery_job_id` | Discovery |
| `architecture_job_id` | Architecture |
| `jgv3_generation_job_id` | Java Generation V3 |

### Java Generation Status Fields

| Field | Description |
|-------|-------------|
| `jgv3_status` | Overall JG status |
| `jgv3_flow_status` | Flow execution status |
| `jgv3_workflow_status` | Workflow state |

---

## S3 Path Pattern

Files are stored in S3 with this pattern:

```
s3://scoutitmodernization/{account_id}/{app_name}/{timestamp}_{filename}
```

Example:
```
s3://scoutitmodernization/341/SanityOnModernization/20251126_113645_01_CustomerMgmt.cob
```

---

## ID Generation Patterns

**Application ID:**
```
app_{application_name}_{unix_timestamp}
```
Example: `app_AppointmentBooking_1761645037`

**File ID:**
```
file_{application_id}_{unix_timestamp_with_nanos}
```
Example: `file_app_SanityOnModernization_1764156984_1764157005349650425`

---

## Notes

1. **Numbers stored as strings** - `file_count`, `file_size` are strings, not integers
2. **Timestamps are ISO 8601** - All dates in `YYYY-MM-DDTHH:MM:SSZ` format
3. **Empty strings for null** - Job IDs are `""` not `null` when empty
4. **S3 integration** - Actual file content in S3, DynamoDB just stores metadata

---

## For Local Provider

The local SQLite provider must:
1. Store same fields with same names
2. Handle string numbers (or convert consistently)
3. Generate IDs in same format
4. Support same query patterns (by app_id, by account_id)

---

*Documented: January 1, 2026*
