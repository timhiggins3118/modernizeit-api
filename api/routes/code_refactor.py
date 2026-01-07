"""
Code Refactor API Routes

Phase 1 (Analyze): Rule-based detection + AI interpretation -> Reports
Phase 2 (Transform): Apply approved changes -> New Java files (stubbed)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse, FileResponse

from api.models.code_refactor import (
    CodeRefactorRequest,
    CodeRefactorResponse,
    CodeRefactorStatusResponse,
    CodeRefactorResultsResponse,
    CodeTransformRequest,
    CodeTransformResponse,
)
from config.settings import settings
from migrate_dynamodb.dynamodb_jobs import JobRecord, get_job, save_job
from engines.code_refactor.runner import run_code_refactor, get_refactor_status

router = APIRouter(prefix="/coderefactor", tags=["code_refactor"])


@router.post(
    "",
    response_model=CodeRefactorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Code Refactor Analysis",
    description="""
    Run code refactoring analysis on generated Java code.

    This endpoint:
    1. Loads the generated Java file
    2. Runs rule-based pattern detection (BigDecimal overuse, parallel arrays, etc.)
    3. Runs AI analysis for semantic interpretation (optional, requires Bedrock)
    4. Generates reports (JSON and Markdown)
    5. Creates refactor_recipes.json
    6. **AUTO-TRANSFORM** (default): Automatically applies recipes to extract services

    Parameters:
    - auto_transform (default: true): Automatically apply transformations after analyze
      Set to false if you want to review recipes before applying

    The flow runs synchronously - returns when complete.
    Output includes extracted service classes (e.g., TaxCalculationService.java)
    """
)
async def start_code_refactor(request: CodeRefactorRequest) -> CodeRefactorResponse:
    """
    Run Code Refactor on generated Java files.

    By default, analyzes ALL generated Java files.
    If class_name is specified, analyzes only that class.
    """
    try:
        import time
        start_time = time.time()

        # Find semantic models from code_analysis output
        semantic_models_path = _find_semantic_models(
            request.scout_account_id,
            request.application_name
        )

        # Output directory for refactor artifacts
        output_dir = (
            settings.base_local_path
            / "code-transformation-v2"
            / request.scout_account_id
            / request.application_name
            / "code_refactor"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # Determine which Java files to analyze
        if request.class_name:
            # Specific class requested
            java_files = [_find_java_file(
                request.scout_account_id,
                request.application_name,
                request.class_name
            )]
        else:
            # Analyze ALL Java files (default)
            java_files = _find_all_java_files(
                request.scout_account_id,
                request.application_name
            )

        print(f"[Code Refactor] Analyzing {len(java_files)} Java file(s)")

        # Run refactor analysis on each file
        all_results = []
        all_patterns = 0
        all_recommendations = 0
        all_high_severity = 0
        job_id = f"rf_job_{int(time.time())}"

        for java_file in java_files:
            print(f"[Code Refactor] Processing: {java_file.stem}")

            # Create per-class output directory
            class_output_dir = output_dir / java_file.stem
            class_output_dir.mkdir(parents=True, exist_ok=True)

            result = run_code_refactor(
                java_file=str(java_file),
                output_dir=str(class_output_dir),
                semantic_models_path=semantic_models_path,
                mode=request.mode,
                use_ai=request.use_ai,
                recipes_to_apply=request.recipes_to_apply,
                account_id=request.scout_account_id,
                application=request.application_name,
                save_to_mongodb=True,
            )

            all_results.append({
                "class_name": java_file.stem,
                "success": result.success,
                "patterns_detected": result.summary.get("patterns_detected", 0),
                "recommendations": result.summary.get("recommendations", 0),
                "high_severity": result.summary.get("high_severity", 0),
            })

            all_patterns += result.summary.get("patterns_detected", 0)
            all_recommendations += result.summary.get("recommendations", 0)
            all_high_severity += result.summary.get("high_severity", 0)

        # Save job record
        _save_job_record(
            job_id=job_id,
            request=request,
            artifacts_path=str(output_dir),
            status="completed"
        )

        # Build aggregated summary
        aggregated_summary = {
            "total_classes_analyzed": len(java_files),
            "total_patterns_detected": all_patterns,
            "total_recommendations": all_recommendations,
            "total_high_severity": all_high_severity,
            "class_results": all_results,
        }

        # Auto-transform: Apply recipes after analyze
        transform_results = None
        if request.auto_transform and request.mode == "analyze":
            print(f"[Code Refactor] Auto-transform enabled, applying recipes...")
            try:
                from engines.code_refactor.transformers.transform_engine import TransformEngine

                for java_file in java_files:
                    class_folder = output_dir / java_file.stem
                    recipes_file = class_folder / "artifacts" / "refactor_recipes.json"

                    if recipes_file.exists():
                        # Load recipes
                        recipes_data = json.loads(recipes_file.read_text())
                        recipes_to_apply = recipes_data.get("recipes", [])

                        if recipes_to_apply:
                            # Create output directory for transformed code
                            transform_output = class_folder / "output" / "transformed"
                            transform_output.mkdir(parents=True, exist_ok=True)

                            # Run transformation
                            engine = TransformEngine(str(transform_output))
                            transform_result = engine.apply_recipes(
                                java_file=str(java_file),
                                recipes=recipes_to_apply
                            )

                            print(f"[Code Refactor] Transform {java_file.stem}: {len(transform_result.changes)} changes, {len(transform_result.files_created)} files")

                            transform_results = {
                                "success": transform_result.success,
                                "changes_made": len(transform_result.changes),
                                "files_created": transform_result.files_created,
                                "output_path": str(transform_output),
                            }

                            aggregated_summary["transform_results"] = transform_results

            except Exception as e:
                print(f"[Code Refactor] Auto-transform failed: {e}")
                aggregated_summary["transform_error"] = str(e)

        # Calculate total duration (including transform)
        total_duration_ms = int((time.time() - start_time) * 1000)

        return CodeRefactorResponse(
            success=True,
            job_id=job_id,
            phase="analyze+transform" if transform_results else request.mode,
            status="completed",
            java_file=str(java_files[0]) if len(java_files) == 1 else f"{len(java_files)} files",
            class_name=java_files[0].stem if len(java_files) == 1 else f"{len(java_files)} classes",
            artifacts_path=str(output_dir),
            error=None,
            duration_ms=total_duration_ms,
            summary=aggregated_summary,
            artifacts=result.artifacts,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/transform",
    response_model=CodeTransformResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply Code Transformations (Phase 2)",
    description="""
    Apply refactoring transformations to generated Java code.

    This endpoint:
    1. Reads recipes from previous analyze phase
    2. Applies selected transformations (or all)
    3. Generates new modernized Java files
    4. Preserves original files (writes to new folder)

    Requires: Run /coderefactor (analyze) first to generate recipes.
    """
)
async def transform_code(request: CodeTransformRequest) -> CodeTransformResponse:
    """
    Apply refactoring transformations.
    """
    import time
    start_time = time.time()

    try:
        # Find the recipes from analyze phase
        # Analyze saves to: code_refactor/{class_name}/artifacts/
        refactor_path = (
            settings.base_local_path
            / "code-transformation-v2"
            / request.scout_account_id
            / request.application_name
            / "code_refactor"
        )

        # Find class folders (analyze creates one folder per class)
        class_folders = [d for d in refactor_path.iterdir() if d.is_dir() and (d / "artifacts").exists()]
        if not class_folders:
            raise FileNotFoundError(
                f"No refactor analysis found for {request.scout_account_id}/{request.application_name}. "
                "Run POST /coderefactor first."
            )

        # Use the first class folder (or could aggregate all)
        # TODO: Support multi-class transform with class_name parameter
        class_folder = class_folders[0]
        recipes_file = class_folder / "artifacts" / "refactor_recipes.json"
        if not recipes_file.exists():
            raise FileNotFoundError(
                f"No recipes found in {class_folder.name}. Run POST /coderefactor first."
            )

        # Load recipes
        recipes_data = json.loads(recipes_file.read_text())
        all_recipes = recipes_data.get("recipes", [])

        # Determine which recipes to apply
        if request.recipes_to_apply == "all":
            recipes_to_apply = all_recipes
        else:
            recipe_ids = request.recipes_to_apply if isinstance(request.recipes_to_apply, list) else []
            recipes_to_apply = [r for r in all_recipes if r.get("id") in recipe_ids]

        if not recipes_to_apply:
            raise ValueError("No valid recipes to apply")

        # Find original Java file (use class name from folder)
        java_file = _find_java_file(
            request.scout_account_id,
            request.application_name,
            class_folder.name  # e.g., "IFPR321"
        )

        # Create output directory for transformed code (inside class folder)
        output_path = class_folder / "output" / "transformed"
        output_path.mkdir(parents=True, exist_ok=True)

        # Run transformation
        from engines.code_refactor.transformers.transform_engine import TransformEngine

        engine = TransformEngine(str(output_path))
        result = engine.apply_recipes(
            java_file=str(java_file),
            recipes=recipes_to_apply
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Generate job ID
        job_id = f"rf_transform_{int(time.time())}"

        return CodeTransformResponse(
            success=result.success,
            job_id=job_id,
            status="completed" if result.success else "failed",
            original_file=str(java_file),
            output_path=str(output_path),
            recipes_applied=len(recipes_to_apply),
            changes_made=result.changes,
            error=result.error,
            duration_ms=duration_ms,
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
    "/{job_id}/status",
    response_model=CodeRefactorStatusResponse,
    summary="Get Code Refactor job status"
)
async def get_code_refactor_status(job_id: str) -> CodeRefactorStatusResponse:
    """Get status of a Code Refactor job."""
    record = get_job(job_id)
    if record is None or record.flow_type != "coderefactor":
        raise HTTPException(status_code=404, detail="Job not found")

    return CodeRefactorStatusResponse(
        job_id=record.job_id,
        flow_type=record.flow_type,
        status=record.status,
        artifacts_path=record.artifacts_path,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


@router.get(
    "/{job_id}/results",
    response_model=CodeRefactorResultsResponse,
    summary="Get Code Refactor results overview"
)
async def get_code_refactor_results(job_id: str) -> CodeRefactorResultsResponse:
    """
    Get overview of Code Refactor results.

    Returns available artifacts and summary stats.
    """
    record = get_job(job_id)
    if record is None or record.flow_type != "coderefactor":
        raise HTTPException(status_code=404, detail="Job not found")

    artifacts_path = Path(record.artifacts_path)
    artifacts_dir = artifacts_path / "artifacts"

    result = CodeRefactorResultsResponse(
        job_id=record.job_id,
        status=record.status,
        artifacts_path=str(artifacts_path),
        json_artifacts=[],
        summary={},
    )

    # Try direct path first (single class analysis)
    if artifacts_dir.exists():
        result.json_artifacts = sorted([f.name for f in artifacts_dir.glob("*.json")])
        result.json_artifacts += sorted([f.name for f in artifacts_dir.glob("*.md")])

        # Load summary from main report if available
        report_path = artifacts_dir / "refactor_report.json"
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text())
                result.summary = report.get("summary", {})
            except json.JSONDecodeError:
                pass

    # Check for multi-class folder structure
    if not result.json_artifacts:
        all_artifacts = set()
        total_patterns = 0
        total_action_items = 0
        class_count = 0

        for class_folder in artifacts_path.iterdir():
            if class_folder.is_dir() and class_folder.name != "artifacts":
                class_artifacts_dir = class_folder / "artifacts"
                if class_artifacts_dir.exists():
                    class_count += 1
                    for f in class_artifacts_dir.glob("*.json"):
                        all_artifacts.add(f.name)
                    for f in class_artifacts_dir.glob("*.md"):
                        all_artifacts.add(f.name)

                    # Load summary from class report
                    report_path = class_artifacts_dir / "refactor_report.json"
                    if report_path.exists():
                        try:
                            report = json.loads(report_path.read_text())
                            summary = report.get("summary", {})
                            total_patterns += summary.get("patterns_detected", 0)
                            total_action_items += len(report.get("action_items", []))
                        except json.JSONDecodeError:
                            pass

        result.json_artifacts = sorted(list(all_artifacts))
        if class_count > 0:
            result.summary = {
                "total_classes": class_count,
                "total_patterns": total_patterns,
                "total_action_items": total_action_items,
            }

    return result


@router.get(
    "/{job_id}/results/json/{filename}",
    summary="Get specific JSON artifact"
)
async def get_json_artifact(job_id: str, filename: str):
    """Get a specific JSON artifact by filename."""
    record = get_job(job_id)
    if record is None or record.flow_type != "coderefactor":
        raise HTTPException(status_code=404, detail="Job not found")

    artifacts_path = Path(record.artifacts_path)

    # Try direct path first (single class analysis)
    file_path = artifacts_path / "artifacts" / filename
    if file_path.exists():
        try:
            content = json.loads(file_path.read_text())
            return JSONResponse(content=content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Invalid JSON in artifact")

    # Try class subfolders (multi-class analysis)
    # Look for the first class folder that has this artifact
    for class_folder in artifacts_path.iterdir():
        if class_folder.is_dir() and class_folder.name != "artifacts":
            class_file = class_folder / "artifacts" / filename
            if class_file.exists():
                try:
                    content = json.loads(class_file.read_text())
                    return JSONResponse(content=content)
                except json.JSONDecodeError:
                    raise HTTPException(status_code=500, detail="Invalid JSON in artifact")

    # If still not found, try to aggregate from all class folders (for reports)
    if filename == "refactor_report.json":
        aggregated = _aggregate_reports(artifacts_path)
        if aggregated:
            return JSONResponse(content=aggregated)

    raise HTTPException(status_code=404, detail=f"Artifact not found: {filename}")


@router.get(
    "/{job_id}/results/report",
    summary="Get Markdown report"
)
async def get_markdown_report(job_id: str):
    """Get the human-readable Markdown report."""
    record = get_job(job_id)
    if record is None or record.flow_type != "coderefactor":
        raise HTTPException(status_code=404, detail="Job not found")

    file_path = Path(record.artifacts_path) / "artifacts" / "refactor_report.md"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(file_path, media_type="text/markdown")


@router.get(
    "/{job_id}/results/recipes",
    summary="Get refactor recipes"
)
async def get_refactor_recipes(job_id: str):
    """
    Get the refactor recipes file.

    This file contains structured recommendations that can be:
    1. Reviewed by humans for approval
    2. Used as input for Phase 2 (Transform) automation
    """
    record = get_job(job_id)
    if record is None or record.flow_type != "coderefactor":
        raise HTTPException(status_code=404, detail="Job not found")

    artifacts_path = Path(record.artifacts_path)

    # Try direct path first (single class analysis)
    file_path = artifacts_path / "artifacts" / "refactor_recipes.json"
    if file_path.exists():
        try:
            content = json.loads(file_path.read_text())
            return JSONResponse(content=content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Invalid JSON in recipes")

    # Try class subfolders (multi-class analysis)
    # Aggregate recipes from all class folders
    aggregated_recipes = _aggregate_recipes(artifacts_path)
    if aggregated_recipes:
        return JSONResponse(content=aggregated_recipes)

    raise HTTPException(status_code=404, detail="Recipes not found")


@router.get(
    "/artifacts",
    summary="Read artifact file directly by path"
)
async def read_artifact_file(path: str):
    """
    Read an artifact JSON file directly by path.

    This is a fallback endpoint when job tracking isn't available.
    Only allows reading JSON files within the modernizeit_output directory.
    """
    file_path = Path(path)

    # Security: Only allow reading from modernizeit_output
    if not str(file_path).startswith(str(settings.base_local_path)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    if not file_path.suffix == '.json':
        raise HTTPException(status_code=400, detail="Only JSON files can be read")

    try:
        content = json.loads(file_path.read_text())
        return JSONResponse(content=content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON in file")


def _find_all_java_files(
    scout_account_id: str,
    application_name: str,
) -> List[Path]:
    """
    Find ALL Java files from code_analysis generated output.

    Args:
        scout_account_id: Account ID
        application_name: Application name

    Returns:
        List of paths to all Java files
    """
    base_path = (
        settings.base_local_path
        / "code-transformation-v2"
        / scout_account_id
        / application_name
        / "code_analysis"
        / "generated"
    )

    if not base_path.exists():
        raise FileNotFoundError(
            f"No code_analysis output found for {scout_account_id}/{application_name}. "
            "Run code_analysis first."
        )

    # Find all Java files in generated output
    java_files = []
    for gen_folder in base_path.iterdir():
        if gen_folder.is_dir():
            java_src = gen_folder / "src" / "main" / "java" / "com" / "modernizeit" / "generated"
            if java_src.exists():
                java_files.extend(java_src.glob("*.java"))

    if not java_files:
        raise FileNotFoundError(
            f"No generated Java files found in {base_path}. "
            "Run code_analysis first."
        )

    return sorted(java_files, key=lambda f: f.stem)


def _find_java_file(
    scout_account_id: str,
    application_name: str,
    class_name: str
) -> Path:
    """
    Find a specific Java file from code_analysis generated output.

    Args:
        scout_account_id: Account ID
        application_name: Application name
        class_name: Specific class name to find

    Returns:
        Path to Java file
    """
    java_files = _find_all_java_files(scout_account_id, application_name)

    for jf in java_files:
        if jf.stem == class_name or jf.name == class_name:
            return jf

    raise FileNotFoundError(
        f"Class '{class_name}' not found. "
        f"Available: {[f.stem for f in java_files]}"
    )


def _find_semantic_models(
    scout_account_id: str,
    application_name: str
) -> Optional[str]:
    """
    Find semantic models from code_analysis output.

    Returns path to reports directory if found, None otherwise.
    """
    reports_path = (
        settings.base_local_path
        / "code-transformation-v2"
        / scout_account_id
        / application_name
        / "code_analysis"
        / "reports"
    )

    if reports_path.exists():
        # Check for required model files
        data_models = list(reports_path.glob("*_data_model.json"))
        if data_models:
            return str(reports_path)

    return None


def _save_job_record(
    job_id: str,
    request: CodeRefactorRequest,
    artifacts_path: str,
    status: str
) -> None:
    """Save job record to database."""
    now = datetime.utcnow()
    record = JobRecord(
        job_id=job_id,
        flow_type="coderefactor",
        status=status,
        created_at=now,
        updated_at=now,
        artifacts_path=artifacts_path,
        input_json=json.dumps({
            "scout_account_id": request.scout_account_id,
            "application_name": request.application_name,
            "class_name": request.class_name,
            "mode": request.mode,
            "use_ai": request.use_ai,
            "recipes_to_apply": request.recipes_to_apply,
        })
    )
    save_job(record)


def _aggregate_reports(artifacts_path: Path) -> Optional[Dict[str, Any]]:
    """
    Aggregate refactor reports from all class folders.

    When analyzing multiple classes, each class has its own folder with artifacts.
    This function combines them into a single aggregated report.
    """
    all_patterns = []
    all_action_items = []
    class_summaries = []

    for class_folder in sorted(artifacts_path.iterdir()):
        if not class_folder.is_dir() or class_folder.name == "artifacts":
            continue

        report_file = class_folder / "artifacts" / "refactor_report.json"
        if report_file.exists():
            try:
                report = json.loads(report_file.read_text())

                # Collect rule patterns
                if "rule_patterns" in report:
                    for pattern in report["rule_patterns"]:
                        pattern["class_name"] = class_folder.name
                        all_patterns.append(pattern)

                # Collect action items
                if "action_items" in report:
                    for item in report["action_items"]:
                        item["class_name"] = class_folder.name
                        all_action_items.append(item)

                # Collect class summary
                if "summary" in report:
                    class_summaries.append({
                        "class_name": class_folder.name,
                        **report["summary"]
                    })

            except json.JSONDecodeError:
                continue

    if not all_patterns and not all_action_items:
        return None

    # Build aggregated report
    return {
        "aggregated": True,
        "class_count": len(class_summaries),
        "rule_patterns": all_patterns,
        "action_items": all_action_items,
        "class_summaries": class_summaries,
        "summary": {
            "total_patterns": len(all_patterns),
            "total_action_items": len(all_action_items),
            "total_classes": len(class_summaries),
        }
    }


def _aggregate_recipes(artifacts_path: Path) -> Optional[Dict[str, Any]]:
    """
    Aggregate refactor recipes from all class folders.

    When analyzing multiple classes, each class has its own folder with recipes.
    This function combines them into a single aggregated recipes file.
    """
    all_recipes = []
    recipe_type_counts = {}

    for class_folder in sorted(artifacts_path.iterdir()):
        if not class_folder.is_dir() or class_folder.name == "artifacts":
            continue

        recipes_file = class_folder / "artifacts" / "refactor_recipes.json"
        if recipes_file.exists():
            try:
                data = json.loads(recipes_file.read_text())
                recipes = data.get("recipes", [])

                for recipe in recipes:
                    # Add class name to recipe for context
                    recipe["class_name"] = class_folder.name
                    all_recipes.append(recipe)

                    # Count by type
                    recipe_type = recipe.get("type", "unknown")
                    recipe_type_counts[recipe_type] = recipe_type_counts.get(recipe_type, 0) + 1

            except json.JSONDecodeError:
                continue

    if not all_recipes:
        return None

    # Build aggregated recipes
    return {
        "aggregated": True,
        "recipes": all_recipes,
        "summary": {
            "total_recipes": len(all_recipes),
            "recipe_type_breakdown": recipe_type_counts,
        }
    }
