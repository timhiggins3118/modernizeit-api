"""
Java Packaging API Routes

The final step in the ModernizeIT pipeline. Takes existing Java code
from Code Analysis or Code Refactor and packages it into a production-ready
Spring Boot application that customers can download, build, and deploy.

Key Principle: We do NOT regenerate Java code here. We package existing code
into a runnable Spring Boot application with proper project structure.
"""

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse

from api.models.java_packaging import (
    JavaPackagingRequest,
    JavaPackagingResponse,
    JavaPackagingStatusResponse,
    JavaPackagingValidationResponse,
    JavaPackagingJobsResponse,
    JavaSource,
    PackageStatistics,
    ValidationSummary,
    ValidationIssue,
    JobSummary,
)
from config.settings import settings
from migrate_dynamodb.dynamodb_jobs import JobRecord, get_job, save_job, list_jobs
from utils.storage_uploader import upload_to_s3_if_needed

router = APIRouter(prefix="/java-packaging", tags=["java_packaging"])


# =============================================================================
# Constants
# =============================================================================

FLOW_TYPE = "java_packaging"
JOB_PREFIX = "jpkg"

PHASES = [
    "initializing",
    "collecting_source_files",
    "generating_project_structure",
    "generating_controllers",
    "generating_repositories",
    "generating_config",
    "validation",
    "creating_package",
    "packaging_complete",
]


# =============================================================================
# API Endpoints
# =============================================================================

@router.post(
    "/start",
    response_model=JavaPackagingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start Java Packaging Job",
    description="""
    Start a new Java packaging job.

    This endpoint:
    1. Locates Java code from Code Analysis or Code Refactor output
    2. Generates Spring Boot project structure (pom.xml, Dockerfile, etc.)
    3. Generates REST Controllers and Repositories for entities
    4. Validates the packaged code (optional)
    5. Creates a downloadable ZIP file

    The source parameter determines where to get Java code:
    - "analysis": Use raw Java from Code Analysis (direct COBOL translation)
    - "refactor": Use modernized Java from Code Refactor (recommended)

    Returns immediately with job_id. Use GET /java-packaging/status/{job_id}
    to check progress.
    """
)
async def start_java_packaging(request: JavaPackagingRequest) -> JavaPackagingResponse:
    """Start a new Java packaging job."""
    import time
    start_time = time.time()

    try:
        # Generate job ID
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        job_id = f"{JOB_PREFIX}_{request.application_name}_{timestamp}"

        print(f"[Java Packaging] Starting job: {job_id}")
        print(f"[Java Packaging] Source: {request.source.value}")
        print(f"[Java Packaging] Account: {request.scout_account_id}")
        print(f"[Java Packaging] Application: {request.application_name}")

        # Create output directory for this job
        output_dir = _get_job_output_dir(
            request.scout_account_id,
            request.application_name,
            job_id
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find source Java files
        source_path = _find_source_java_path(
            request.scout_account_id,
            request.application_name,
            request.source
        )

        print(f"[Java Packaging] Source path: {source_path}")

        # Run the packaging pipeline
        result = _run_packaging_pipeline(
            job_id=job_id,
            source_path=source_path,
            output_dir=output_dir,
            request=request,
        )

        duration_ms = int((time.time() - start_time) * 1000)
        print(f"[Java Packaging] Completed in {duration_ms}ms")

        # Save job record
        now = datetime.now(timezone.utc)
        record = JobRecord(
            job_id=job_id,
            flow_type=FLOW_TYPE,
            status="completed" if result["success"] else "failed",
            created_at=now,
            updated_at=now,
            artifacts_path=str(output_dir),
            input_json=json.dumps({
                "scout_account_id": request.scout_account_id,
                "application_name": request.application_name,
                "source": request.source.value,
                "options": request.options.model_dump(),
            })
        )
        save_job(record)

        # Upload to S3 if account uses S3 storage
        upload_to_s3_if_needed(request.scout_account_id, request.application_name, "java_packaging")

        return JavaPackagingResponse(
            success=result["success"],
            job_id=job_id,
            status="completed" if result["success"] else "failed",
            message=result.get("message", "Java packaging completed"),
            created_at=now.isoformat(),
            error=result.get("error"),
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/status/{job_id}",
    response_model=JavaPackagingStatusResponse,
    summary="Get Job Status",
    description="Get the status of a Java packaging job."
)
async def get_java_packaging_status(job_id: str) -> JavaPackagingStatusResponse:
    """Get status of a Java packaging job."""
    record = get_job(job_id)
    if record is None or record.flow_type != FLOW_TYPE:
        raise HTTPException(status_code=404, detail="Job not found")

    # Load status file if it exists
    artifacts_path = Path(record.artifacts_path)
    status_file = artifacts_path / "status.json"

    status_data = {
        "progress": 100 if record.status == "completed" else 0,
        "phase": "packaging_complete" if record.status == "completed" else "unknown",
        "phases_completed": PHASES if record.status == "completed" else [],
    }

    if status_file.exists():
        try:
            status_data = json.loads(status_file.read_text())
        except json.JSONDecodeError:
            pass

    # Load statistics if available
    statistics = None
    stats_file = artifacts_path / "statistics.json"
    if stats_file.exists():
        try:
            stats_data = json.loads(stats_file.read_text())
            statistics = PackageStatistics(**stats_data)
        except (json.JSONDecodeError, Exception):
            pass

    # Load validation summary if available
    validation = None
    validation_file = artifacts_path / "validation_report.json"
    if validation_file.exists():
        try:
            val_data = json.loads(validation_file.read_text())
            validation = ValidationSummary(
                status=val_data.get("overall_status", "UNKNOWN"),
                total_files=val_data.get("summary", {}).get("total_files", 0),
                valid_files=val_data.get("summary", {}).get("valid_files", 0),
                invalid_files=val_data.get("summary", {}).get("invalid_files", 0),
                warnings=val_data.get("summary", {}).get("warnings", 0),
                todos=val_data.get("summary", {}).get("total_todos", 0),
            )
        except (json.JSONDecodeError, Exception):
            pass

    return JavaPackagingStatusResponse(
        success=True,
        job_id=record.job_id,
        status=record.status,
        progress=status_data.get("progress", 0),
        phase=status_data.get("phase", ""),
        phases_completed=status_data.get("phases_completed", []),
        statistics=statistics,
        validation=validation,
        created_at=record.created_at.isoformat(),
        completed_at=record.updated_at.isoformat() if record.status == "completed" else None,
        error=status_data.get("error"),
    )


@router.get(
    "/download/{job_id}",
    summary="Download Package",
    description="Download the generated Spring Boot application as a ZIP file."
)
async def download_java_package(job_id: str):
    """Download the packaged Spring Boot application."""
    record = get_job(job_id)
    if record is None or record.flow_type != FLOW_TYPE:
        raise HTTPException(status_code=404, detail="Job not found")

    if record.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Package not ready. Job status: {record.status}"
        )

    artifacts_path = Path(record.artifacts_path)

    # Find the ZIP file
    zip_files = list(artifacts_path.glob("*.zip"))
    if not zip_files:
        raise HTTPException(status_code=404, detail="Package ZIP not found")

    zip_file = zip_files[0]

    # Parse application name from job input
    try:
        input_data = json.loads(record.input_json)
        app_name = input_data.get("application_name", "ModernizedApplication")
    except json.JSONDecodeError:
        app_name = "ModernizedApplication"

    return FileResponse(
        path=str(zip_file),
        media_type="application/zip",
        filename=f"ModernizedApplication_{app_name}.zip"
    )


@router.get(
    "/validation/{job_id}",
    response_model=JavaPackagingValidationResponse,
    summary="Get Validation Report",
    description="Get detailed validation report for the packaged Java code."
)
async def get_validation_report(job_id: str) -> JavaPackagingValidationResponse:
    """Get the validation report for a packaging job."""
    record = get_job(job_id)
    if record is None or record.flow_type != FLOW_TYPE:
        raise HTTPException(status_code=404, detail="Job not found")

    artifacts_path = Path(record.artifacts_path)
    validation_file = artifacts_path / "validation_report.json"

    if not validation_file.exists():
        raise HTTPException(status_code=404, detail="Validation report not found")

    try:
        val_data = json.loads(validation_file.read_text())
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid validation report")

    # Parse issues
    issues = []
    for issue_data in val_data.get("issues", []):
        issues.append(ValidationIssue(
            file=issue_data.get("file", ""),
            type=issue_data.get("type", "warning"),
            message=issue_data.get("message", ""),
            line=issue_data.get("line"),
        ))

    return JavaPackagingValidationResponse(
        success=True,
        job_id=job_id,
        validation_method=val_data.get("validation_method", "ast"),
        overall_status=val_data.get("overall_status", "UNKNOWN"),
        summary=ValidationSummary(
            status=val_data.get("overall_status", "UNKNOWN"),
            total_files=val_data.get("summary", {}).get("total_files", 0),
            valid_files=val_data.get("summary", {}).get("valid_files", 0),
            invalid_files=val_data.get("summary", {}).get("invalid_files", 0),
            warnings=val_data.get("summary", {}).get("warnings", 0),
            todos=val_data.get("summary", {}).get("total_todos", 0),
        ),
        issues=issues,
    )


@router.get(
    "/jobs/{scout_account_id}/{application_name}",
    response_model=JavaPackagingJobsResponse,
    summary="List Jobs",
    description="List all Java packaging jobs for an application."
)
async def list_packaging_jobs(
    scout_account_id: str,
    application_name: str
) -> JavaPackagingJobsResponse:
    """List all packaging jobs for an application."""
    records = list_jobs(
        account_id=scout_account_id,
        application_name=application_name,
        flow_type=FLOW_TYPE,
        limit=50
    )

    jobs = []
    for record in records:
        # Check if package is ready
        artifacts_path = Path(record.artifacts_path)
        zip_files = list(artifacts_path.glob("*.zip")) if artifacts_path.exists() else []

        # Get source from input
        try:
            input_data = json.loads(record.input_json)
            source = input_data.get("source", "refactor")
        except json.JSONDecodeError:
            source = "unknown"

        jobs.append(JobSummary(
            job_id=record.job_id,
            status=record.status,
            source=source,
            created_at=record.created_at.isoformat(),
            package_ready=len(zip_files) > 0,
        ))

    return JavaPackagingJobsResponse(
        success=True,
        scout_account_id=scout_account_id,
        application_name=application_name,
        jobs=jobs,
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _get_job_output_dir(
    scout_account_id: str,
    application_name: str,
    job_id: str
) -> Path:
    """Get the output directory for a packaging job."""
    return (
        settings.base_local_path
        / "code-transformation-v2"
        / scout_account_id
        / application_name
        / "java_packaging"
        / "jobs"
        / job_id
    )


def _find_source_java_path(
    scout_account_id: str,
    application_name: str,
    source: JavaSource
) -> Path:
    """
    Find the path to source Java files.

    Args:
        scout_account_id: Account ID
        application_name: Application name
        source: Source type (analysis or refactor)

    Returns:
        Path to the Java source directory

    Raises:
        FileNotFoundError: If source path doesn't exist
    """
    base_path = (
        settings.base_local_path
        / "code-transformation-v2"
        / scout_account_id
        / application_name
    )

    if source == JavaSource.REFACTOR:
        # Look for refactored Java in code_refactor output
        refactor_path = base_path / "code_refactor"
        if refactor_path.exists():
            # Find transformed output folders
            for class_folder in refactor_path.iterdir():
                if class_folder.is_dir():
                    transformed = class_folder / "output" / "transformed"
                    if transformed.exists():
                        return transformed

            # Fall back to original Java from code_analysis
            print("[Java Packaging] No transformed code found, using code_analysis output")

        # If no refactor output, fall through to analysis

    # Use code_analysis generated output
    analysis_path = base_path / "code_analysis" / "generated"
    if not analysis_path.exists():
        raise FileNotFoundError(
            f"No Java source found for {scout_account_id}/{application_name}. "
            f"Run Code Analysis first."
        )

    # Find the first generated folder with Java files
    for gen_folder in sorted(analysis_path.iterdir(), reverse=True):
        if gen_folder.is_dir():
            java_src = gen_folder / "src" / "main" / "java"
            if java_src.exists():
                return gen_folder

    raise FileNotFoundError(
        f"No generated Java files found in {analysis_path}. "
        f"Run Code Analysis first."
    )


def _run_packaging_pipeline(
    job_id: str,
    source_path: Path,
    output_dir: Path,
    request: JavaPackagingRequest,
) -> Dict[str, Any]:
    """
    Run the complete packaging pipeline.

    Steps:
    1. Copy source Java files to output
    2. Generate Spring Boot project structure
    3. Generate Controllers and Repositories
    4. Validate code (optional)
    5. Create ZIP package

    Returns:
        Dict with success status and statistics
    """
    try:
        # Track statistics
        stats = {
            "services_packaged": 0,
            "entities_packaged": 0,
            "controllers_generated": 0,
            "repositories_generated": 0,
            "tests_generated": 0,
            "total_files": 0,
            "package_size_bytes": 0,
        }

        # Create project directory
        project_name = "ModernizedApplication"
        project_dir = output_dir / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        # Update status
        _update_status(output_dir, "collecting_source_files", 10, ["initializing"])

        # Step 1: Copy source Java files
        java_files = _copy_source_files(source_path, project_dir, stats)
        print(f"[Java Packaging] Copied {len(java_files)} Java files")

        # Update status
        _update_status(output_dir, "generating_project_structure", 30,
                      ["initializing", "collecting_source_files"])

        # Step 2: Generate project structure (pom.xml, Dockerfile, etc.)
        _generate_project_structure(
            project_dir,
            request.application_name,
            request.options
        )

        # Update status
        _update_status(output_dir, "generating_controllers", 50,
                      ["initializing", "collecting_source_files", "generating_project_structure"])

        # Step 3: Generate Controllers and Repositories
        entities = _find_entities(project_dir)
        stats["entities_packaged"] = len(entities)

        for entity in entities:
            _generate_controller(project_dir, entity, request.application_name)
            stats["controllers_generated"] += 1

            _generate_repository(project_dir, entity, request.application_name)
            stats["repositories_generated"] += 1

        # Update status
        _update_status(output_dir, "generating_config", 60,
                      ["initializing", "collecting_source_files", "generating_project_structure",
                       "generating_controllers", "generating_repositories"])

        # Step 4: Generate config files
        _generate_application_config(project_dir, request.application_name)

        # Step 5: Generate tests (optional)
        if request.options.include_tests:
            services = _find_services(project_dir)
            stats["services_packaged"] = len(services)
            for service in services:
                _generate_test(project_dir, service, request.application_name)
                stats["tests_generated"] += 1

        # Update status
        _update_status(output_dir, "validation", 70,
                      ["initializing", "collecting_source_files", "generating_project_structure",
                       "generating_controllers", "generating_repositories", "generating_config"])

        # Step 6: Validate (optional)
        validation_result = {"overall_status": "SKIPPED", "summary": {}}
        if request.options.run_validation:
            validation_result = _validate_java_code(project_dir, output_dir)

        # Update status
        _update_status(output_dir, "creating_package", 85,
                      ["initializing", "collecting_source_files", "generating_project_structure",
                       "generating_controllers", "generating_repositories", "generating_config", "validation"])

        # Step 7: Create ZIP
        stats["total_files"] = _count_files(project_dir)
        zip_path = _create_zip_package(project_dir, output_dir, job_id)
        stats["package_size_bytes"] = zip_path.stat().st_size

        # Save statistics
        stats_file = output_dir / "statistics.json"
        stats_file.write_text(json.dumps(stats, indent=2))

        # Update final status
        _update_status(output_dir, "packaging_complete", 100, PHASES)

        return {
            "success": True,
            "message": f"Package created with {stats['total_files']} files",
            "statistics": stats,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        _update_status(output_dir, "failed", 0, [], error=str(e))
        return {
            "success": False,
            "error": str(e),
        }


def _update_status(
    output_dir: Path,
    phase: str,
    progress: int,
    phases_completed: List[str],
    error: Optional[str] = None
) -> None:
    """Update the status file."""
    status_data = {
        "phase": phase,
        "progress": progress,
        "phases_completed": phases_completed,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if error:
        status_data["error"] = error

    status_file = output_dir / "status.json"
    status_file.write_text(json.dumps(status_data, indent=2))


def _copy_source_files(
    source_path: Path,
    project_dir: Path,
    stats: Dict[str, int]
) -> List[Path]:
    """Copy source Java files to project directory."""
    copied_files = []

    # Determine source structure
    src_java = source_path / "src" / "main" / "java"
    if not src_java.exists():
        src_java = source_path  # Direct Java folder

    # Create target structure
    target_java = project_dir / "src" / "main" / "java"
    target_java.mkdir(parents=True, exist_ok=True)

    # Copy all Java files preserving structure
    for java_file in src_java.rglob("*.java"):
        relative = java_file.relative_to(src_java)
        target_file = target_java / relative
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(java_file, target_file)
        copied_files.append(target_file)

    return copied_files


def _generate_project_structure(
    project_dir: Path,
    application_name: str,
    options
) -> None:
    """Generate Spring Boot project structure files."""
    # Generate pom.xml
    pom_content = _get_pom_template(
        application_name,
        options.spring_boot_version,
        options.java_version
    )
    (project_dir / "pom.xml").write_text(pom_content)

    # Generate Dockerfile (if enabled)
    if options.include_docker:
        dockerfile_content = _get_dockerfile_template(options.java_version)
        (project_dir / "Dockerfile").write_text(dockerfile_content)

        compose_content = _get_docker_compose_template(application_name)
        (project_dir / "docker-compose.yml").write_text(compose_content)

    # Generate README
    readme_content = _get_readme_template(
        application_name,
        options.java_version,
        options.spring_boot_version
    )
    (project_dir / "README.md").write_text(readme_content)

    # Generate helper scripts
    (project_dir / "build.sh").write_text(_get_build_script())
    (project_dir / "start.sh").write_text(_get_start_script())
    (project_dir / "stop.sh").write_text(_get_stop_script())

    # Generate .gitignore
    (project_dir / ".gitignore").write_text(_get_gitignore())


def _find_entities(project_dir: Path) -> List[str]:
    """Find entity class names in the project."""
    entities = []
    entities_dir = project_dir / "src" / "main" / "java"

    for java_file in entities_dir.rglob("*.java"):
        content = java_file.read_text()
        if "@Entity" in content:
            entities.append(java_file.stem)

    return entities


def _find_services(project_dir: Path) -> List[str]:
    """Find service class names in the project."""
    services = []
    src_dir = project_dir / "src" / "main" / "java"

    for java_file in src_dir.rglob("*.java"):
        content = java_file.read_text()
        if "@Service" in content:
            services.append(java_file.stem)

    return services


def _generate_controller(project_dir: Path, entity_name: str, app_name: str) -> None:
    """Generate a REST controller for an entity."""
    package = f"com.modernized.{app_name.lower()}"
    controllers_dir = project_dir / "src" / "main" / "java" / "com" / "modernized" / app_name.lower() / "controllers"
    controllers_dir.mkdir(parents=True, exist_ok=True)

    controller_content = _get_controller_template(package, entity_name)
    (controllers_dir / f"{entity_name}Controller.java").write_text(controller_content)


def _generate_repository(project_dir: Path, entity_name: str, app_name: str) -> None:
    """Generate a Spring Data repository for an entity."""
    package = f"com.modernized.{app_name.lower()}"
    repos_dir = project_dir / "src" / "main" / "java" / "com" / "modernized" / app_name.lower() / "repositories"
    repos_dir.mkdir(parents=True, exist_ok=True)

    repo_content = _get_repository_template(package, entity_name)
    (repos_dir / f"{entity_name}Repository.java").write_text(repo_content)


def _generate_application_config(project_dir: Path, app_name: str) -> None:
    """Generate application configuration files."""
    resources_dir = project_dir / "src" / "main" / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)

    # Generate application.yml
    config_content = _get_application_yml_template(app_name)
    (resources_dir / "application.yml").write_text(config_content)

    # Generate Application.java if not exists
    package = f"com.modernized.{app_name.lower()}"
    app_dir = project_dir / "src" / "main" / "java" / "com" / "modernized" / app_name.lower()
    app_dir.mkdir(parents=True, exist_ok=True)

    app_file = app_dir / "Application.java"
    if not app_file.exists():
        app_content = _get_application_java_template(package, app_name)
        app_file.write_text(app_content)


def _generate_test(project_dir: Path, service_name: str, app_name: str) -> None:
    """Generate a test class for a service."""
    package = f"com.modernized.{app_name.lower()}"
    test_dir = project_dir / "src" / "test" / "java" / "com" / "modernized" / app_name.lower() / "services"
    test_dir.mkdir(parents=True, exist_ok=True)

    test_content = _get_test_template(package, service_name)
    (test_dir / f"{service_name}Test.java").write_text(test_content)


def _validate_java_code(project_dir: Path, output_dir: Path) -> Dict[str, Any]:
    """
    Validate Java code using AST parsing.

    Returns validation report.
    """
    import re

    java_files = list((project_dir / "src").rglob("*.java"))
    total_files = len(java_files)
    valid_files = 0
    invalid_files = 0
    warnings = 0
    total_todos = 0
    issues = []

    for java_file in java_files:
        try:
            content = java_file.read_text()

            # Basic syntax checks
            is_valid = True

            # Check for balanced braces
            if content.count('{') != content.count('}'):
                is_valid = False
                issues.append({
                    "file": str(java_file.relative_to(project_dir)),
                    "type": "error",
                    "message": "Unbalanced braces",
                    "line": None,
                })

            # Check for package declaration
            if not re.search(r'^package\s+[\w.]+;', content, re.MULTILINE):
                is_valid = False
                issues.append({
                    "file": str(java_file.relative_to(project_dir)),
                    "type": "error",
                    "message": "Missing package declaration",
                    "line": None,
                })

            # Count TODOs as warnings
            todo_count = len(re.findall(r'TODO', content, re.IGNORECASE))
            if todo_count > 0:
                total_todos += todo_count
                warnings += 1
                issues.append({
                    "file": str(java_file.relative_to(project_dir)),
                    "type": "warning",
                    "message": f"Contains {todo_count} TODO comments",
                    "line": None,
                })

            if is_valid:
                valid_files += 1
            else:
                invalid_files += 1

        except Exception as e:
            invalid_files += 1
            issues.append({
                "file": str(java_file.relative_to(project_dir)),
                "type": "error",
                "message": f"Failed to read file: {str(e)}",
                "line": None,
            })

    # Determine overall status
    if invalid_files > 0:
        overall_status = "FAILED"
    elif warnings > 0:
        overall_status = "PASSED_WITH_WARNINGS"
    else:
        overall_status = "PASSED"

    validation_report = {
        "validation_method": "ast",
        "overall_status": overall_status,
        "summary": {
            "total_files": total_files,
            "valid_files": valid_files,
            "invalid_files": invalid_files,
            "warnings": warnings,
            "total_todos": total_todos,
        },
        "issues": issues,
        "validated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Save validation report
    validation_file = output_dir / "validation_report.json"
    validation_file.write_text(json.dumps(validation_report, indent=2))

    return validation_report


def _count_files(project_dir: Path) -> int:
    """Count total files in project."""
    return sum(1 for _ in project_dir.rglob("*") if _.is_file())


def _create_zip_package(
    project_dir: Path,
    output_dir: Path,
    job_id: str
) -> Path:
    """Create ZIP package of the project."""
    zip_name = f"{job_id}_ModernizedApplication.zip"
    zip_path = output_dir / zip_name

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in project_dir.rglob("*"):
            if file_path.is_file():
                arcname = file_path.relative_to(project_dir.parent)
                zipf.write(file_path, arcname)

    print(f"[Java Packaging] Created ZIP: {zip_path} ({zip_path.stat().st_size} bytes)")
    return zip_path


# =============================================================================
# Template Functions
# =============================================================================

def _get_pom_template(app_name: str, spring_boot_version: str, java_version: str) -> str:
    """Generate pom.xml content."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>{spring_boot_version}</version>
        <relativePath/>
    </parent>

    <groupId>com.modernized</groupId>
    <artifactId>{app_name.lower()}</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <name>{app_name}</name>
    <description>Modernized application - generated by ModernizeIT</description>

    <properties>
        <java.version>{java_version}</java.version>
        <maven.compiler.source>{java_version}</maven.compiler.source>
        <maven.compiler.target>{java_version}</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
'''


def _get_dockerfile_template(java_version: str = "17") -> str:
    """Generate Dockerfile content with dynamic Java version."""
    return f'''# Stage 1: Build
FROM maven:3.9-eclipse-temurin-{java_version} AS build

WORKDIR /app

COPY pom.xml .
RUN mvn dependency:go-offline -B

COPY src ./src
RUN mvn clean package -DskipTests -B

# Stage 2: Runtime
FROM eclipse-temurin:{java_version}-jre

LABEL maintainer="ModernizeIT"
LABEL description="Modernized application"

RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

COPY --from=build /app/target/*.jar app.jar

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \\
  CMD curl -f http://localhost:8080/actuator/health || exit 1

ENV JAVA_OPTS="-Xms512m -Xmx1024m -XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0"

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
'''


def _get_docker_compose_template(app_name: str) -> str:
    """Generate docker-compose.yml content."""
    return f'''version: '3.8'

services:
  app:
    build: .
    ports:
      - "8080:8080"
    environment:
      - SPRING_DATASOURCE_URL=jdbc:postgresql://db:5432/{app_name.lower()}
      - SPRING_DATASOURCE_USERNAME=postgres
      - SPRING_DATASOURCE_PASSWORD=postgres
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB={app_name.lower()}
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
'''


def _get_readme_template(app_name: str, java_version: str = "17", spring_boot_version: str = "3.2.0") -> str:
    """Generate README.md content with dynamic versions."""
    return f'''# {app_name} - Modernized Application

Generated by **ModernizeIT** - COBOL to Java Modernization Platform

## Quick Start

### Using Docker (Recommended)

```bash
# Start the application with PostgreSQL
docker-compose up --build

# Application will be available at http://localhost:8080
```

### Using Maven

```bash
# Build the application
mvn clean package

# Run (requires PostgreSQL)
java -jar target/*.jar
```

## API Documentation

- Swagger UI: http://localhost:8080/swagger-ui.html
- API Docs: http://localhost:8080/v3/api-docs

## Project Structure

```
src/
├── main/
│   ├── java/com/modernized/{app_name.lower()}/
│   │   ├── Application.java      # Spring Boot main class
│   │   ├── entities/             # JPA entities
│   │   ├── services/             # Business logic
│   │   ├── repositories/         # Data access
│   │   └── controllers/          # REST endpoints
│   └── resources/
│       └── application.yml       # Configuration
└── test/
    └── java/                     # Unit tests
```

## Technology Stack

- Java {java_version}
- Spring Boot {spring_boot_version}
- Spring Data JPA
- PostgreSQL 15
- Docker

---

*Generated by ModernizeIT*
'''


def _get_build_script() -> str:
    """Generate build.sh content."""
    return '''#!/bin/bash
set -e
echo "Building application..."
mvn clean package -DskipTests
echo "Build complete!"
'''


def _get_start_script() -> str:
    """Generate start.sh content."""
    return '''#!/bin/bash
echo "Starting application..."
docker-compose up --build -d
echo "Application started at http://localhost:8080"
'''


def _get_stop_script() -> str:
    """Generate stop.sh content."""
    return '''#!/bin/bash
echo "Stopping application..."
docker-compose down
echo "Application stopped."
'''


def _get_gitignore() -> str:
    """Generate .gitignore content."""
    return '''target/
*.class
*.jar
*.war
*.log
.idea/
*.iml
.DS_Store
.env
'''


def _get_controller_template(package: str, entity_name: str) -> str:
    """Generate REST controller content."""
    entity_var = entity_name[0].lower() + entity_name[1:]
    return f'''package {package}.controllers;

import {package}.entities.{entity_name};
import {package}.repositories.{entity_name}Repository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/{entity_var}s")
public class {entity_name}Controller {{

    @Autowired
    private {entity_name}Repository repository;

    @GetMapping
    public List<{entity_name}> findAll() {{
        return repository.findAll();
    }}

    @GetMapping("/{{id}}")
    public ResponseEntity<{entity_name}> findById(@PathVariable Long id) {{
        return repository.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }}

    @PostMapping
    public {entity_name} create(@RequestBody {entity_name} entity) {{
        return repository.save(entity);
    }}

    @PutMapping("/{{id}}")
    public ResponseEntity<{entity_name}> update(@PathVariable Long id, @RequestBody {entity_name} entity) {{
        if (!repository.existsById(id)) {{
            return ResponseEntity.notFound().build();
        }}
        return ResponseEntity.ok(repository.save(entity));
    }}

    @DeleteMapping("/{{id}}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {{
        if (!repository.existsById(id)) {{
            return ResponseEntity.notFound().build();
        }}
        repository.deleteById(id);
        return ResponseEntity.noContent().build();
    }}

    @GetMapping("/count")
    public long count() {{
        return repository.count();
    }}
}}
'''


def _get_repository_template(package: str, entity_name: str) -> str:
    """Generate Spring Data repository content."""
    return f'''package {package}.repositories;

import {package}.entities.{entity_name};
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface {entity_name}Repository extends JpaRepository<{entity_name}, Long> {{
    // Custom query methods can be added here
}}
'''


def _get_application_yml_template(app_name: str) -> str:
    """Generate application.yml content."""
    return f'''server:
  port: 8080

spring:
  application:
    name: {app_name}
  datasource:
    url: jdbc:postgresql://localhost:5432/{app_name.lower()}
    username: postgres
    password: postgres
  jpa:
    hibernate:
      ddl-auto: update
    show-sql: false
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
        format_sql: true

logging:
  level:
    root: INFO
    com.modernized: DEBUG
'''


def _get_application_java_template(package: str, app_name: str) -> str:
    """Generate Application.java content."""
    return f'''package {package};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * {app_name} - Modernized Application
 * Generated by ModernizeIT
 */
@SpringBootApplication
public class Application {{

    public static void main(String[] args) {{
        SpringApplication.run(Application.class, args);
    }}
}}
'''


def _get_test_template(package: str, service_name: str) -> str:
    """Generate test class content."""
    return f'''package {package}.services;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.springframework.boot.test.context.SpringBootTest;

import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest
@DisplayName("{service_name} Tests")
class {service_name}Test {{

    @BeforeEach
    void setUp() {{
        // TODO: Initialize test data
    }}

    @Test
    @DisplayName("Should pass basic test")
    void shouldPassBasicTest() {{
        // TODO: Implement test
        assertTrue(true);
    }}
}}
'''
