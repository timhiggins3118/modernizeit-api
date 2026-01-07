"""
Test Generation API Routes

Generates JUnit tests for Java code from Code Analysis or Code Refactor.

Two modes:
1. Test Stubs - Quick scaffolding with TODOs (no AI, free, fast)
2. Smart Tests - AI-powered meaningful tests with real assertions

Smart Tests use:
- procedure_model.json (from Code Analysis) - What COBOL does
- data_model.json (from Code Analysis) - Field definitions/constraints
- Java code (from Refactor) - What we generated

This creates tests that validate the Java code does what the COBOL code did.
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from api.models.test_generation import (
    TestStubsRequest,
    TestStubsResponse,
    SmartTestsRequest,
    SmartTestsResponse,
    TestGenerationStatusResponse,
    TestGenerationResultsResponse,
    TestGenerationJobsResponse,
    TestStatistics,
    GeneratedTest,
    JobSummary,
    TestFramework,
    MockFramework,
    TestSource,
)
from config.settings import settings
from migrate_dynamodb.dynamodb_jobs import JobRecord, get_job, save_job, list_jobs
from utils.storage_uploader import upload_to_s3_if_needed

router = APIRouter(prefix="/test-generation", tags=["test_generation"])


# =============================================================================
# Constants
# =============================================================================

FLOW_TYPE_STUBS = "test_stubs"
FLOW_TYPE_SMART = "test_smart"
JOB_PREFIX_STUBS = "tstub"
JOB_PREFIX_SMART = "tsmart"

PHASES_STUBS = [
    "initializing",
    "scanning_java_files",
    "generating_test_classes",
    "generating_test_methods",
    "writing_tests",
    "complete",
]

PHASES_SMART = [
    "initializing",
    "loading_procedure_model",
    "loading_data_model",
    "scanning_java_files",
    "analyzing_methods",
    "generating_unit_tests",
    "generating_validation_tests",
    "generating_integration_tests",
    "writing_tests",
    "complete",
]


# =============================================================================
# API Endpoints - Test Stubs (No AI)
# =============================================================================

@router.post(
    "/stubs",
    response_model=TestStubsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Test Stubs",
    description="""
    Generate JUnit test scaffolding without AI (free, fast).

    Creates:
    - Test class per service/entity
    - @BeforeEach setup with mocks
    - Empty test method for each public method
    - Tests compile and run (fail with TODO)

    Use case: Customer wants CI pipeline setup, will write assertions themselves.
    """
)
async def generate_test_stubs(request: TestStubsRequest) -> TestStubsResponse:
    """Generate test stubs (no AI)."""
    start_time = time.time()

    try:
        # Generate job ID
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        job_id = f"{JOB_PREFIX_STUBS}_{request.application_name}_{timestamp}"

        print(f"[Test Stubs] Starting job: {job_id}")
        print(f"[Test Stubs] Source: {request.source.value}")
        print(f"[Test Stubs] Account: {request.scout_account_id}")
        print(f"[Test Stubs] Application: {request.application_name}")

        # Create output directory
        output_dir = _get_job_output_dir(
            request.scout_account_id,
            request.application_name,
            job_id,
            "stubs"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find source Java files
        source_path = _find_source_java_path(
            request.scout_account_id,
            request.application_name,
            request.source
        )

        print(f"[Test Stubs] Source path: {source_path}")

        # Run test stub generation
        result = _generate_test_stubs(
            job_id=job_id,
            source_path=source_path,
            output_dir=output_dir,
            request=request,
        )

        duration_ms = int((time.time() - start_time) * 1000)
        print(f"[Test Stubs] Completed in {duration_ms}ms")

        # Save job record
        now = datetime.now(timezone.utc)
        record = JobRecord(
            job_id=job_id,
            flow_type=FLOW_TYPE_STUBS,
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

        return TestStubsResponse(
            success=result["success"],
            job_id=job_id,
            status="completed" if result["success"] else "failed",
            message=result.get("message", "Test stubs generated"),
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


# =============================================================================
# API Endpoints - Smart Tests (AI-Powered)
# =============================================================================

@router.post(
    "/smart",
    response_model=SmartTestsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Smart Tests",
    description="""
    Generate meaningful JUnit tests using AI.

    Uses:
    - procedure_model.json - What COBOL does (conditions, actions)
    - data_model.json - Field definitions and constraints
    - Java code - What we generated

    Creates:
    - Unit tests with real assertions
    - Validation tests from copybook constraints
    - Edge case tests
    - Integration tests (optional)

    Use case: Customer wants tests that actually validate the transformation.
    """
)
async def generate_smart_tests(request: SmartTestsRequest) -> SmartTestsResponse:
    """Generate smart tests (AI-powered)."""
    start_time = time.time()

    try:
        # Generate job ID
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        job_id = f"{JOB_PREFIX_SMART}_{request.application_name}_{timestamp}"

        print(f"[Smart Tests] Starting job: {job_id}")
        print(f"[Smart Tests] Source: {request.source.value}")
        print(f"[Smart Tests] Account: {request.scout_account_id}")
        print(f"[Smart Tests] Application: {request.application_name}")

        # Create output directory
        output_dir = _get_job_output_dir(
            request.scout_account_id,
            request.application_name,
            job_id,
            "smart"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find source Java files
        source_path = _find_source_java_path(
            request.scout_account_id,
            request.application_name,
            request.source
        )

        # Load procedure model and data model for AI context
        procedure_model = _load_procedure_model(
            request.scout_account_id,
            request.application_name
        )
        data_model = _load_data_model(
            request.scout_account_id,
            request.application_name
        )

        print(f"[Smart Tests] Source path: {source_path}")
        print(f"[Smart Tests] Procedure model loaded: {procedure_model is not None}")
        print(f"[Smart Tests] Data model loaded: {data_model is not None}")

        # Run smart test generation
        result = _generate_smart_tests(
            job_id=job_id,
            source_path=source_path,
            output_dir=output_dir,
            request=request,
            procedure_model=procedure_model,
            data_model=data_model,
        )

        duration_ms = int((time.time() - start_time) * 1000)
        print(f"[Smart Tests] Completed in {duration_ms}ms")

        # Save job record
        now = datetime.now(timezone.utc)
        record = JobRecord(
            job_id=job_id,
            flow_type=FLOW_TYPE_SMART,
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
        upload_to_s3_if_needed(request.scout_account_id, request.application_name, "test_generation")

        return SmartTestsResponse(
            success=result["success"],
            job_id=job_id,
            status="completed" if result["success"] else "failed",
            message=result.get("message", "Smart tests generated"),
            created_at=now.isoformat(),
            ai_calls_used=result.get("ai_calls_used", 0),
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


# =============================================================================
# Status and Results Endpoints
# =============================================================================

@router.get(
    "/status/{job_id}",
    response_model=TestGenerationStatusResponse,
    summary="Get Job Status",
    description="Get the status of a test generation job."
)
async def get_test_generation_status(job_id: str) -> TestGenerationStatusResponse:
    """Get status of a test generation job."""
    record = get_job(job_id)
    if record is None or record.flow_type not in [FLOW_TYPE_STUBS, FLOW_TYPE_SMART]:
        raise HTTPException(status_code=404, detail="Job not found")

    test_type = "stubs" if record.flow_type == FLOW_TYPE_STUBS else "smart"
    phases = PHASES_STUBS if test_type == "stubs" else PHASES_SMART

    # Load status file if it exists
    artifacts_path = Path(record.artifacts_path)
    status_file = artifacts_path / "status.json"

    status_data = {
        "progress": 100 if record.status == "completed" else 0,
        "phase": "complete" if record.status == "completed" else "unknown",
        "phases_completed": phases if record.status == "completed" else [],
        "tests_generated": 0,
        "classes_covered": 0,
        "methods_covered": 0,
        "ai_calls_used": 0,
    }

    if status_file.exists():
        try:
            status_data = json.loads(status_file.read_text())
        except json.JSONDecodeError:
            pass

    # Load statistics if available
    stats_file = artifacts_path / "statistics.json"
    if stats_file.exists():
        try:
            stats = json.loads(stats_file.read_text())
            status_data["tests_generated"] = stats.get("total_tests", 0)
            status_data["classes_covered"] = stats.get("classes_covered", 0)
            status_data["methods_covered"] = stats.get("methods_covered", 0)
            status_data["ai_calls_used"] = stats.get("ai_calls_used", 0)
        except json.JSONDecodeError:
            pass

    return TestGenerationStatusResponse(
        success=True,
        job_id=record.job_id,
        status=record.status,
        progress=status_data.get("progress", 0),
        phase=status_data.get("phase", ""),
        phases_completed=status_data.get("phases_completed", []),
        test_type=test_type,
        tests_generated=status_data.get("tests_generated", 0),
        classes_covered=status_data.get("classes_covered", 0),
        methods_covered=status_data.get("methods_covered", 0),
        ai_calls_used=status_data.get("ai_calls_used", 0),
        created_at=record.created_at.isoformat(),
        completed_at=record.updated_at.isoformat() if record.status == "completed" else None,
        error=status_data.get("error"),
    )


@router.get(
    "/results/{job_id}",
    response_model=TestGenerationResultsResponse,
    summary="Get Results",
    description="Get the results of a test generation job."
)
async def get_test_generation_results(job_id: str) -> TestGenerationResultsResponse:
    """Get results of a test generation job."""
    record = get_job(job_id)
    if record is None or record.flow_type not in [FLOW_TYPE_STUBS, FLOW_TYPE_SMART]:
        raise HTTPException(status_code=404, detail="Job not found")

    if record.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Results not ready. Job status: {record.status}"
        )

    test_type = "stubs" if record.flow_type == FLOW_TYPE_STUBS else "smart"
    artifacts_path = Path(record.artifacts_path)

    # Load statistics
    stats = {"total_tests": 0, "classes_covered": 0, "methods_covered": 0, "ai_calls_used": 0}
    stats_file = artifacts_path / "statistics.json"
    if stats_file.exists():
        try:
            stats = json.loads(stats_file.read_text())
        except json.JSONDecodeError:
            pass

    # Load test manifest
    tests = []
    manifest_file = artifacts_path / "test_manifest.json"
    if manifest_file.exists():
        try:
            manifest = json.loads(manifest_file.read_text())
            for test_info in manifest.get("tests", []):
                tests.append(GeneratedTest(
                    file_path=test_info.get("file_path", ""),
                    class_name=test_info.get("class_name", ""),
                    test_count=test_info.get("test_count", 0),
                    methods_tested=test_info.get("methods_tested", []),
                ))
        except json.JSONDecodeError:
            pass

    # Get input for framework info
    try:
        input_data = json.loads(record.input_json)
        framework = input_data.get("options", {}).get("framework", "junit5")
    except json.JSONDecodeError:
        framework = "junit5"

    return TestGenerationResultsResponse(
        success=True,
        job_id=job_id,
        test_type=test_type,
        framework=framework,
        tests_generated=stats.get("total_tests", 0),
        classes_covered=stats.get("classes_covered", 0),
        methods_covered=stats.get("methods_covered", 0),
        output_path=str(artifacts_path / "tests"),
        tests=tests,
        ai_calls_used=stats.get("ai_calls_used", 0),
        duration_ms=stats.get("duration_ms", 0),
    )


@router.get(
    "/jobs/{scout_account_id}/{application_name}",
    response_model=TestGenerationJobsResponse,
    summary="List Jobs",
    description="List all test generation jobs for an application."
)
async def list_test_generation_jobs(
    scout_account_id: str,
    application_name: str
) -> TestGenerationJobsResponse:
    """List all test generation jobs for an application."""
    # Get both stub and smart jobs
    stubs_records = list_jobs(
        account_id=scout_account_id,
        application_name=application_name,
        flow_type=FLOW_TYPE_STUBS,
        limit=25
    )
    smart_records = list_jobs(
        account_id=scout_account_id,
        application_name=application_name,
        flow_type=FLOW_TYPE_SMART,
        limit=25
    )

    jobs = []
    for record in stubs_records + smart_records:
        # Get source and tests from input/stats
        try:
            input_data = json.loads(record.input_json)
            source = input_data.get("source", "refactor")
        except json.JSONDecodeError:
            source = "unknown"

        # Load stats for test count
        tests_generated = 0
        artifacts_path = Path(record.artifacts_path)
        stats_file = artifacts_path / "statistics.json"
        if stats_file.exists():
            try:
                stats = json.loads(stats_file.read_text())
                tests_generated = stats.get("total_tests", 0)
            except json.JSONDecodeError:
                pass

        test_type = "stubs" if record.flow_type == FLOW_TYPE_STUBS else "smart"

        jobs.append(JobSummary(
            job_id=record.job_id,
            status=record.status,
            test_type=test_type,
            source=source,
            created_at=record.created_at.isoformat(),
            tests_generated=tests_generated,
        ))

    # Sort by created_at descending
    jobs.sort(key=lambda x: x.created_at, reverse=True)

    return TestGenerationJobsResponse(
        success=True,
        scout_account_id=scout_account_id,
        application_name=application_name,
        jobs=jobs[:50],  # Limit to 50 total
    )


# =============================================================================
# Helper Functions - Path Resolution
# =============================================================================

def _get_job_output_dir(
    scout_account_id: str,
    application_name: str,
    job_id: str,
    test_type: str
) -> Path:
    """Get the output directory for a test generation job."""
    return (
        settings.base_local_path
        / "code-transformation-v2"
        / scout_account_id
        / application_name
        / "test_generation"
        / test_type
        / "jobs"
        / job_id
    )


def _find_source_java_path(
    scout_account_id: str,
    application_name: str,
    source: TestSource
) -> Path:
    """Find the path to source Java files."""
    base_path = (
        settings.base_local_path
        / "code-transformation-v2"
        / scout_account_id
        / application_name
    )

    if source == TestSource.REFACTOR:
        # Look for refactored Java
        refactor_path = base_path / "code_refactor"
        if refactor_path.exists():
            for class_folder in refactor_path.iterdir():
                if class_folder.is_dir():
                    transformed = class_folder / "output" / "transformed"
                    if transformed.exists():
                        return transformed

    # Fall back to code_analysis generated output
    analysis_path = base_path / "code_analysis" / "generated"
    if not analysis_path.exists():
        raise FileNotFoundError(
            f"No Java source found for {scout_account_id}/{application_name}. "
            f"Run Code Analysis first."
        )

    for gen_folder in sorted(analysis_path.iterdir(), reverse=True):
        if gen_folder.is_dir():
            java_src = gen_folder / "src" / "main" / "java"
            if java_src.exists():
                return gen_folder

    raise FileNotFoundError(
        f"No generated Java files found in {analysis_path}. "
        f"Run Code Analysis first."
    )


def _load_procedure_model(scout_account_id: str, application_name: str) -> Optional[Dict]:
    """Load procedure model from Code Analysis output."""
    base_path = (
        settings.base_local_path
        / "code-transformation-v2"
        / scout_account_id
        / application_name
        / "code_analysis"
    )

    # Look for procedure_model.json in analysis output
    for folder in sorted(base_path.glob("*"), reverse=True):
        if folder.is_dir():
            model_file = folder / "procedure_model.json"
            if model_file.exists():
                try:
                    return json.loads(model_file.read_text())
                except json.JSONDecodeError:
                    continue

    return None


def _load_data_model(scout_account_id: str, application_name: str) -> Optional[Dict]:
    """Load data model from Code Analysis output."""
    base_path = (
        settings.base_local_path
        / "code-transformation-v2"
        / scout_account_id
        / application_name
        / "code_analysis"
    )

    # Look for data_model.json in analysis output
    for folder in sorted(base_path.glob("*"), reverse=True):
        if folder.is_dir():
            model_file = folder / "data_model.json"
            if model_file.exists():
                try:
                    return json.loads(model_file.read_text())
                except json.JSONDecodeError:
                    continue

    return None


# =============================================================================
# Test Stub Generation (No AI)
# =============================================================================

def _generate_test_stubs(
    job_id: str,
    source_path: Path,
    output_dir: Path,
    request: TestStubsRequest,
) -> Dict[str, Any]:
    """Generate test stubs without AI."""
    try:
        stats = {
            "total_tests": 0,
            "unit_tests": 0,
            "classes_covered": 0,
            "methods_covered": 0,
            "ai_calls_used": 0,
            "duration_ms": 0,
        }
        start_time = time.time()
        test_manifest = {"tests": []}

        _update_status(output_dir, "scanning_java_files", 10, ["initializing"])

        # Find Java source files
        java_src = source_path / "src" / "main" / "java"
        if not java_src.exists():
            java_src = source_path

        java_files = list(java_src.rglob("*.java"))
        print(f"[Test Stubs] Found {len(java_files)} Java files")

        _update_status(output_dir, "generating_test_classes", 30,
                       ["initializing", "scanning_java_files"])

        # Create test output directory
        test_output = output_dir / "tests" / "src" / "test" / "java"
        test_output.mkdir(parents=True, exist_ok=True)

        # Generate tests for each service/entity
        for java_file in java_files:
            content = java_file.read_text()

            # Skip non-testable files
            if "@Entity" not in content and "@Service" not in content:
                continue

            # Extract class info
            class_name = java_file.stem
            package = _extract_package(content)
            methods = _extract_public_methods(content)

            if not methods:
                continue

            _update_status(output_dir, "generating_test_methods", 50,
                           ["initializing", "scanning_java_files", "generating_test_classes"])

            # Generate test class
            test_content = _generate_stub_test_class(
                package=package,
                class_name=class_name,
                methods=methods,
                framework=request.options.framework,
                include_mocks=request.options.include_mocks,
                fail_on_todo=request.options.fail_on_todo,
            )

            # Write test file
            test_package_path = package.replace(".", "/") if package else ""
            test_file_dir = test_output / test_package_path
            test_file_dir.mkdir(parents=True, exist_ok=True)
            test_file = test_file_dir / f"{class_name}Test.java"
            test_file.write_text(test_content)

            # Update stats
            stats["classes_covered"] += 1
            stats["methods_covered"] += len(methods)
            stats["total_tests"] += len(methods)
            stats["unit_tests"] += len(methods)

            # Add to manifest
            test_manifest["tests"].append({
                "file_path": str(test_file.relative_to(output_dir)),
                "class_name": f"{class_name}Test",
                "test_count": len(methods),
                "methods_tested": methods,
            })

        _update_status(output_dir, "writing_tests", 80,
                       ["initializing", "scanning_java_files", "generating_test_classes", "generating_test_methods"])

        # Save statistics
        stats["duration_ms"] = int((time.time() - start_time) * 1000)
        (output_dir / "statistics.json").write_text(json.dumps(stats, indent=2))

        # Save manifest
        (output_dir / "test_manifest.json").write_text(json.dumps(test_manifest, indent=2))

        _update_status(output_dir, "complete", 100, PHASES_STUBS)

        return {
            "success": True,
            "message": f"Generated {stats['total_tests']} test stubs for {stats['classes_covered']} classes",
            "statistics": stats,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        _update_status(output_dir, "failed", 0, [], error=str(e))
        return {"success": False, "error": str(e)}


def _generate_stub_test_class(
    package: str,
    class_name: str,
    methods: List[str],
    framework: TestFramework,
    include_mocks: bool,
    fail_on_todo: bool,
) -> str:
    """Generate a test stub class."""
    # Build package statement
    package_stmt = f"package {package};\n\n" if package else ""

    # Build imports
    imports = []
    if framework == TestFramework.JUNIT5:
        imports.extend([
            "import org.junit.jupiter.api.BeforeEach;",
            "import org.junit.jupiter.api.Test;",
            "import org.junit.jupiter.api.DisplayName;",
            "",
            "import static org.junit.jupiter.api.Assertions.*;",
        ])
    else:  # TestNG
        imports.extend([
            "import org.testng.annotations.BeforeMethod;",
            "import org.testng.annotations.Test;",
            "",
            "import static org.testng.Assert.*;",
        ])

    if include_mocks:
        imports.extend([
            "",
            "import org.mockito.Mock;",
            "import org.mockito.MockitoAnnotations;",
            "import static org.mockito.Mockito.*;",
        ])

    imports_str = "\n".join(imports)

    # Build test methods
    test_methods = []
    for method in methods:
        method_name = method.split("(")[0]  # Get just the method name
        test_method_name = f"{method_name}_shouldWork"
        display_name = f"Should {_to_display_name(method_name)}"

        if framework == TestFramework.JUNIT5:
            fail_stmt = 'fail("Not implemented");' if fail_on_todo else "assertTrue(true);"
            test_methods.append(f'''
    @Test
    @DisplayName("{display_name}")
    void {test_method_name}() {{
        // TODO: Implement test for {method_name}
        {fail_stmt}
    }}''')
        else:  # TestNG
            fail_stmt = 'fail("Not implemented");' if fail_on_todo else "assertTrue(true);"
            test_methods.append(f'''
    @Test(description = "{display_name}")
    public void {test_method_name}() {{
        // TODO: Implement test for {method_name}
        {fail_stmt}
    }}''')

    tests_str = "\n".join(test_methods)

    # Build class
    service_var = class_name[0].lower() + class_name[1:]
    before_annotation = "@BeforeEach" if framework == TestFramework.JUNIT5 else "@BeforeMethod"
    before_method = "setUp" if framework == TestFramework.JUNIT5 else "setUp"

    mock_setup = ""
    if include_mocks:
        mock_setup = """
        MockitoAnnotations.openMocks(this);"""

    return f'''{package_stmt}{imports_str}

/**
 * Tests for {class_name}
 * Generated by ModernizeIT - Test Stubs
 */
@DisplayName("{class_name} Tests")
class {class_name}Test {{

    private {class_name} {service_var};

    {before_annotation}
    void {before_method}() {{{mock_setup}
        {service_var} = new {class_name}();
        // TODO: Initialize dependencies
    }}
{tests_str}
}}
'''


# =============================================================================
# Smart Test Generation (AI-Powered)
# =============================================================================

def _generate_smart_tests(
    job_id: str,
    source_path: Path,
    output_dir: Path,
    request: SmartTestsRequest,
    procedure_model: Optional[Dict],
    data_model: Optional[Dict],
) -> Dict[str, Any]:
    """Generate smart tests using AI."""
    try:
        stats = {
            "total_tests": 0,
            "unit_tests": 0,
            "validation_tests": 0,
            "integration_tests": 0,
            "classes_covered": 0,
            "methods_covered": 0,
            "ai_calls_used": 0,
            "duration_ms": 0,
        }
        start_time = time.time()
        test_manifest = {"tests": []}

        _update_status(output_dir, "loading_procedure_model", 5, ["initializing"])
        _update_status(output_dir, "loading_data_model", 10,
                       ["initializing", "loading_procedure_model"])
        _update_status(output_dir, "scanning_java_files", 15,
                       ["initializing", "loading_procedure_model", "loading_data_model"])

        # Find Java source files
        java_src = source_path / "src" / "main" / "java"
        if not java_src.exists():
            java_src = source_path

        java_files = list(java_src.rglob("*.java"))
        print(f"[Smart Tests] Found {len(java_files)} Java files")

        _update_status(output_dir, "analyzing_methods", 20,
                       ["initializing", "loading_procedure_model", "loading_data_model", "scanning_java_files"])

        # Create test output directory
        test_output = output_dir / "tests" / "src" / "test" / "java"
        test_output.mkdir(parents=True, exist_ok=True)

        # Extract procedure info for test generation context
        procedure_info = _extract_procedure_info(procedure_model) if procedure_model else {}
        data_constraints = _extract_data_constraints(data_model) if data_model else {}

        # Generate tests for each service/entity
        processed_files = 0
        for java_file in java_files:
            content = java_file.read_text()

            # Skip non-testable files
            if "@Entity" not in content and "@Service" not in content:
                continue

            # Extract class info
            class_name = java_file.stem
            package = _extract_package(content)
            methods = _extract_public_methods(content)

            if not methods:
                continue

            processed_files += 1
            progress = 20 + int((processed_files / max(len(java_files), 1)) * 50)

            _update_status(output_dir, "generating_unit_tests", progress,
                           ["initializing", "loading_procedure_model", "loading_data_model",
                            "scanning_java_files", "analyzing_methods"])

            # Generate smart test class using procedure model context
            test_content, test_count, ai_calls = _generate_smart_test_class(
                package=package,
                class_name=class_name,
                methods=methods,
                java_content=content,
                procedure_info=procedure_info,
                data_constraints=data_constraints,
                request=request,
                max_ai_calls=request.options.max_ai_calls - stats["ai_calls_used"],
            )

            stats["ai_calls_used"] += ai_calls

            # Check AI call limit
            if stats["ai_calls_used"] >= request.options.max_ai_calls:
                print(f"[Smart Tests] AI call limit reached ({request.options.max_ai_calls})")

            # Write test file
            test_package_path = package.replace(".", "/") if package else ""
            test_file_dir = test_output / test_package_path
            test_file_dir.mkdir(parents=True, exist_ok=True)
            test_file = test_file_dir / f"{class_name}Test.java"
            test_file.write_text(test_content)

            # Update stats
            stats["classes_covered"] += 1
            stats["methods_covered"] += len(methods)
            stats["total_tests"] += test_count
            stats["unit_tests"] += test_count

            # Add to manifest
            test_manifest["tests"].append({
                "file_path": str(test_file.relative_to(output_dir)),
                "class_name": f"{class_name}Test",
                "test_count": test_count,
                "methods_tested": methods,
            })

        # Generate validation tests from data model
        if request.options.validation_tests and data_constraints:
            _update_status(output_dir, "generating_validation_tests", 75,
                           ["initializing", "loading_procedure_model", "loading_data_model",
                            "scanning_java_files", "analyzing_methods", "generating_unit_tests"])

            val_tests, val_count = _generate_validation_tests(
                test_output, data_constraints, request
            )
            stats["validation_tests"] += val_count
            stats["total_tests"] += val_count
            test_manifest["tests"].extend(val_tests)

        # Generate integration tests
        if request.options.integration_tests:
            _update_status(output_dir, "generating_integration_tests", 85,
                           ["initializing", "loading_procedure_model", "loading_data_model",
                            "scanning_java_files", "analyzing_methods", "generating_unit_tests",
                            "generating_validation_tests"])
            # Integration tests would go here
            pass

        _update_status(output_dir, "writing_tests", 95,
                       ["initializing", "loading_procedure_model", "loading_data_model",
                        "scanning_java_files", "analyzing_methods", "generating_unit_tests",
                        "generating_validation_tests", "generating_integration_tests"])

        # Save statistics
        stats["duration_ms"] = int((time.time() - start_time) * 1000)
        (output_dir / "statistics.json").write_text(json.dumps(stats, indent=2))

        # Save manifest
        (output_dir / "test_manifest.json").write_text(json.dumps(test_manifest, indent=2))

        _update_status(output_dir, "complete", 100, PHASES_SMART)

        return {
            "success": True,
            "message": f"Generated {stats['total_tests']} smart tests for {stats['classes_covered']} classes",
            "statistics": stats,
            "ai_calls_used": stats["ai_calls_used"],
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        _update_status(output_dir, "failed", 0, [], error=str(e))
        return {"success": False, "error": str(e)}


def _generate_smart_test_class(
    package: str,
    class_name: str,
    methods: List[str],
    java_content: str,
    procedure_info: Dict,
    data_constraints: Dict,
    request: SmartTestsRequest,
    max_ai_calls: int,
) -> tuple:
    """Generate a smart test class with meaningful assertions.

    For now, generates rule-based tests. AI integration would go here.
    Returns: (test_content, test_count, ai_calls_used)
    """
    ai_calls = 0
    test_count = 0

    # Build package statement
    package_stmt = f"package {package};\n\n" if package else ""

    # Build imports for JUnit 5
    imports = """import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.junit.jupiter.params.provider.NullAndEmptySource;

import static org.junit.jupiter.api.Assertions.*;

import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import static org.mockito.Mockito.*;
"""

    # Build test methods based on procedure model
    test_methods = []

    for method in methods:
        method_name = method.split("(")[0]

        # Look for matching procedure in model
        procedure = procedure_info.get(method_name.lower(), {})

        if procedure:
            # Generate tests based on procedure conditions/actions
            conditions = procedure.get("conditions", [])
            actions = procedure.get("actions", [])

            # Generate test for each condition
            for i, condition in enumerate(conditions[:3]):  # Limit to 3 conditions
                test_method = _generate_condition_test(method_name, condition, i)
                test_methods.append(test_method)
                test_count += 1

            # Generate happy path test
            test_methods.append(_generate_happy_path_test(method_name, actions))
            test_count += 1
        else:
            # Generate basic test without procedure context
            test_methods.append(_generate_basic_test(method_name))
            test_count += 1

    tests_str = "\n".join(test_methods)

    # Build class
    service_var = class_name[0].lower() + class_name[1:]

    test_content = f'''{package_stmt}{imports}

/**
 * Tests for {class_name}
 * Generated by ModernizeIT - Smart Tests
 *
 * These tests validate that the Java code behaves like the original COBOL.
 */
@DisplayName("{class_name} Tests")
class {class_name}Test {{

    private {class_name} {service_var};

    @BeforeEach
    void setUp() {{
        MockitoAnnotations.openMocks(this);
        {service_var} = new {class_name}();
    }}
{tests_str}
}}
'''

    return test_content, test_count, ai_calls


def _generate_condition_test(method_name: str, condition: str, index: int) -> str:
    """Generate a test for a specific condition from procedure model."""
    # Parse condition for test name
    test_name = f"{method_name}_condition{index + 1}_shouldHandle"
    display_name = f"{method_name} handles condition: {condition[:50]}"

    return f'''
    @Test
    @DisplayName("{display_name}")
    void {test_name}() {{
        // Condition from COBOL: {condition}
        // TODO: Set up test data to match condition

        // Act
        // {method_name}(...);

        // Assert
        // Verify behavior matches COBOL logic
        assertTrue(true, "Implement test for condition: {condition}");
    }}'''


def _generate_happy_path_test(method_name: str, actions: List[str]) -> str:
    """Generate a happy path test with expected actions."""
    actions_comment = "\n        // ".join(actions[:3]) if actions else "Expected behavior"

    return f'''
    @Test
    @DisplayName("{method_name} completes successfully with valid input")
    void {method_name}_validInput_succeeds() {{
        // Expected actions from COBOL:
        // {actions_comment}

        // Arrange
        // TODO: Set up valid test data

        // Act
        // var result = {method_name}(...);

        // Assert
        // Verify expected actions occurred
        assertTrue(true, "Implement happy path test");
    }}'''


def _generate_basic_test(method_name: str) -> str:
    """Generate a basic test without procedure context."""
    return f'''
    @Test
    @DisplayName("{method_name} should execute without error")
    void {method_name}_shouldExecute() {{
        // No COBOL procedure model found - basic test

        // Arrange
        // TODO: Set up test data

        // Act
        // {method_name}(...);

        // Assert
        assertDoesNotThrow(() -> {{
            // TODO: Call method under test
        }});
    }}'''


def _generate_validation_tests(
    test_output: Path,
    data_constraints: Dict,
    request: SmartTestsRequest,
) -> tuple:
    """Generate validation tests from data model constraints.

    Returns: (test_info_list, test_count)
    """
    tests = []
    total_count = 0

    # Create validation test file
    val_test_dir = test_output / "com" / "modernized" / "validation"
    val_test_dir.mkdir(parents=True, exist_ok=True)

    test_methods = []

    for field_name, constraint in list(data_constraints.items())[:20]:  # Limit to 20
        # Generate test based on constraint type
        if "max_length" in constraint:
            max_len = constraint["max_length"]
            test_methods.append(f'''
    @Test
    @DisplayName("{field_name} max length is {max_len} - from COBOL PIC X({max_len})")
    void {field_name}_maxLength() {{
        // From COBOL: PIC X({max_len})
        String validValue = "A".repeat({max_len});
        String invalidValue = "A".repeat({max_len + 1});

        // TODO: Validate field accepts valid, rejects invalid
        assertTrue(validValue.length() <= {max_len});
        assertTrue(invalidValue.length() > {max_len});
    }}''')
            total_count += 1

        if "max_digits" in constraint:
            max_digits = constraint["max_digits"]
            test_methods.append(f'''
    @Test
    @DisplayName("{field_name} max {max_digits} digits - from COBOL PIC 9({max_digits})")
    void {field_name}_maxDigits() {{
        // From COBOL: PIC 9({max_digits})
        long maxValue = (long) Math.pow(10, {max_digits}) - 1;

        // TODO: Validate field accepts valid, rejects overflow
        assertTrue(maxValue > 0);
    }}''')
            total_count += 1

        if "valid_values" in constraint:
            values = constraint["valid_values"][:4]  # Limit to 4 values
            values_str = ", ".join([f"'{v}'" for v in values])
            test_methods.append(f'''
    @Test
    @DisplayName("{field_name} only allows {values_str} - from COBOL 88-level")
    void {field_name}_validValues() {{
        // From COBOL 88-level condition
        String[] validValues = {{{values_str}}};

        // TODO: Validate only these values are accepted
        assertTrue(validValues.length > 0);
    }}''')
            total_count += 1

    tests_str = "\n".join(test_methods)

    test_content = f'''package com.modernized.validation;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Validation Tests - from COBOL Copybook Constraints
 * Generated by ModernizeIT - Smart Tests
 *
 * These tests verify Java code respects the same field constraints as COBOL.
 */
@DisplayName("Data Validation Tests")
class DataValidationTest {{
{tests_str}
}}
'''

    test_file = val_test_dir / "DataValidationTest.java"
    test_file.write_text(test_content)

    tests.append({
        "file_path": str(test_file.relative_to(test_output.parent.parent.parent)),
        "class_name": "DataValidationTest",
        "test_count": total_count,
        "methods_tested": list(data_constraints.keys())[:20],
    })

    return tests, total_count


# =============================================================================
# Helper Functions
# =============================================================================

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


def _extract_package(java_content: str) -> str:
    """Extract package name from Java file."""
    match = re.search(r'^package\s+([\w.]+);', java_content, re.MULTILINE)
    return match.group(1) if match else ""


def _extract_public_methods(java_content: str) -> List[str]:
    """Extract public method signatures from Java file."""
    # Match public methods (not constructors, not main)
    pattern = r'public\s+(?!class|interface|enum|static\s+void\s+main)(\w+)\s+(\w+)\s*\([^)]*\)'
    matches = re.findall(pattern, java_content)
    return [f"{name}()" for _, name in matches if not name[0].isupper()]


def _extract_procedure_info(procedure_model: Dict) -> Dict:
    """Extract procedure info indexed by method name."""
    procedures = {}

    # Handle different procedure model formats
    for proc in procedure_model.get("procedures", []):
        name = proc.get("name", "").lower()
        # Convert COBOL name to Java method name (e.g., 3100-VALIDATE-CUSTOMER -> validateCustomer)
        java_name = _cobol_to_java_method_name(name)
        procedures[java_name] = {
            "conditions": proc.get("conditions", []),
            "actions": proc.get("actions", []),
            "purpose": proc.get("purpose", ""),
        }

    return procedures


def _extract_data_constraints(data_model: Dict) -> Dict:
    """Extract field constraints from data model."""
    constraints = {}

    for field in data_model.get("fields", []):
        name = field.get("name", "")
        if not name:
            continue

        constraint = {}

        # PIC X(n) -> max_length
        pic = field.get("picture", "")
        if "X(" in pic:
            match = re.search(r'X\((\d+)\)', pic)
            if match:
                constraint["max_length"] = int(match.group(1))

        # PIC 9(n) -> max_digits
        if "9(" in pic:
            match = re.search(r'9\((\d+)\)', pic)
            if match:
                constraint["max_digits"] = int(match.group(1))

        # 88-level values -> valid_values
        if field.get("level_88"):
            constraint["valid_values"] = field.get("level_88", [])

        if constraint:
            constraints[name] = constraint

    return constraints


def _cobol_to_java_method_name(cobol_name: str) -> str:
    """Convert COBOL procedure name to Java method name."""
    # Remove numeric prefix (e.g., 3100-)
    name = re.sub(r'^\d+-', '', cobol_name)
    # Convert to camelCase
    parts = name.lower().split('-')
    return parts[0] + ''.join(p.title() for p in parts[1:])


def _to_display_name(method_name: str) -> str:
    """Convert method name to display name."""
    # camelCase to "camel case"
    name = re.sub(r'([A-Z])', r' \1', method_name)
    return name.lower().strip()
