"""
Files API Routes

Provides file access for the Code Editor:
- COBOL source files (read-only)
- Java workspace files (read/write)
- Section mapping from procedure model
- Workspace management (reset from generated)

All paths are relative to: {account}/{app}/
"""

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.storage import storage_service

router = APIRouter(prefix="/files", tags=["files"])


# ============================================================================
# Request/Response Models
# ============================================================================

class FileInfo(BaseModel):
    """File information."""
    name: str
    path: str
    size: Optional[int] = None
    type: str  # "file" or "directory"


class FileListResponse(BaseModel):
    """Response for file listing."""
    files: List[FileInfo]
    total: int


class FileContentResponse(BaseModel):
    """Response for file content."""
    path: str
    content: str
    size: int


class SaveFileRequest(BaseModel):
    """Request to save file content."""
    content: str


class WorkspaceResetResponse(BaseModel):
    """Response for workspace reset."""
    success: bool
    message: str
    files_copied: int


class SectionMapping(BaseModel):
    """COBOL section to Java method mapping."""
    cobol_name: str
    cobol_start_line: int
    cobol_end_line: int
    java_method: Optional[str] = None
    java_class: Optional[str] = None
    status: str = "pending"  # pending, converted, modified


class SectionsResponse(BaseModel):
    """Response for section mappings."""
    sections: List[SectionMapping]
    total: int


# ============================================================================
# Helper Functions
# ============================================================================

def _find_source_hash(account: str, app: str) -> Optional[str]:
    """
    Find the source_hash for an application.

    Looks for latest.json in the uploads folder.
    """
    latest_path = f"{account}/{app}/shared/uploads/latest.json"
    try:
        content = storage_service.read_file(latest_path)
        data = json.loads(content)
        return data.get("source_hash")
    except FileNotFoundError:
        # Try to find any upload folder
        uploads_path = f"{account}/{app}/shared/uploads"
        if storage_service.directory_exists(uploads_path):
            files = storage_service.list_files(uploads_path, recursive=False)
            # Find directories (hash folders)
            for f in files:
                if len(f) == 64:  # SHA256 hash length
                    return f
        return None
    except Exception as e:
        print(f"[files] Error finding source_hash: {e}")
        return None


def _find_java_project_name(account: str, app: str) -> Optional[str]:
    """
    Find the Java project folder name (e.g., 'ifpr321_cbl').

    Checks for directories containing Java files under code_analysis/generated/
    """
    generated_path = f"{account}/{app}/code_analysis/generated"
    print(f"[files] Looking for Java project in: {generated_path}")

    if not storage_service.directory_exists(generated_path):
        print(f"[files] Generated path does not exist: {generated_path}")
        return None

    dirs = storage_service.list_directories(generated_path)
    print(f"[files] Found directories: {dirs}")

    # First try: directories with _cbl in the name (COBOL projects)
    for d in dirs:
        if "_cbl" in d.lower():
            print(f"[files] Found COBOL project: {d}")
            return d

    # Second try: any directory containing .java files
    for d in dirs:
        dir_path = f"{generated_path}/{d}"
        java_files = storage_service.list_files(dir_path, pattern="*.java", recursive=True)
        if java_files:
            print(f"[files] Found project with Java files: {d} ({len(java_files)} files)")
            return d

    # Third try: just return the first directory if any exist
    if dirs:
        print(f"[files] No Java files found, returning first directory: {dirs[0]}")
        return dirs[0]

    print("[files] No project directories found")
    return None


def _ensure_workspace(account: str, app: str) -> bool:
    """
    Ensure workspace exists. If not, copy from generated.

    Returns True if workspace exists (or was created).
    """
    project_name = _find_java_project_name(account, app)
    print(f"[files] _ensure_workspace: project_name={project_name}")
    if not project_name:
        print("[files] _ensure_workspace: No project name found")
        return False

    workspace_path = f"{account}/{app}/workspace/java/{project_name}"
    generated_path = f"{account}/{app}/code_analysis/generated/{project_name}"

    print(f"[files] _ensure_workspace: workspace_path={workspace_path}")
    print(f"[files] _ensure_workspace: generated_path={generated_path}")

    if storage_service.directory_exists(workspace_path):
        print("[files] _ensure_workspace: Workspace already exists")
        return True

    if storage_service.directory_exists(generated_path):
        print("[files] _ensure_workspace: Copying from generated to workspace")
        try:
            storage_service.copy_directory(generated_path, workspace_path)
            print("[files] _ensure_workspace: Copy successful")
            return True
        except Exception as e:
            print(f"[files] Error creating workspace: {e}")
            return False

    print(f"[files] _ensure_workspace: Generated path does not exist: {generated_path}")
    return False


def _find_refactored_java_path(account: str, app: str) -> Optional[str]:
    """
    Find the path to refactored Java files from code_refactor output.

    Looks in: code_refactor/{class_name}/output/transformed/

    Returns the path if found, None otherwise.
    """
    refactor_base = f"{account}/{app}/code_refactor"
    if not storage_service.directory_exists(refactor_base):
        return None

    # Find class folders (e.g., IFPR321)
    class_dirs = storage_service.list_directories(refactor_base)
    for class_dir in class_dirs:
        transformed_path = f"{refactor_base}/{class_dir}/output/transformed"
        if storage_service.directory_exists(transformed_path):
            return transformed_path

    return None


def _find_refactor_class_name(account: str, app: str) -> Optional[str]:
    """
    Find the refactor class folder name (e.g., 'IFPR321').
    """
    refactor_base = f"{account}/{app}/code_refactor"
    if not storage_service.directory_exists(refactor_base):
        return None

    class_dirs = storage_service.list_directories(refactor_base)
    for class_dir in class_dirs:
        transformed_path = f"{refactor_base}/{class_dir}/output/transformed"
        if storage_service.directory_exists(transformed_path):
            return class_dir

    return None


def _ensure_refactor_workspace(account: str, app: str) -> bool:
    """
    Ensure refactor workspace exists. If not, copy from transformed output.

    Returns True if workspace exists (or was created).
    """
    class_name = _find_refactor_class_name(account, app)
    if not class_name:
        return False

    workspace_path = f"{account}/{app}/workspace/refactor/{class_name}"
    transformed_path = f"{account}/{app}/code_refactor/{class_name}/output/transformed"

    if storage_service.directory_exists(workspace_path):
        return True

    if storage_service.directory_exists(transformed_path):
        try:
            storage_service.copy_directory(transformed_path, workspace_path)
            return True
        except Exception as e:
            print(f"[files] Error creating refactor workspace: {e}")
            return False

    return False


# ============================================================================
# COBOL Endpoints (Read-Only)
# ============================================================================

@router.get(
    "/{account}/{app}/cobol",
    response_model=FileListResponse,
    summary="List COBOL source files"
)
async def list_cobol_files(account: str, app: str):
    """
    List all COBOL source files for an application.

    Returns files from: shared/uploads/{hash}/extracted/COBOLSource/
    """
    source_hash = _find_source_hash(account, app)
    if not source_hash:
        raise HTTPException(
            status_code=404,
            detail="No source files found. Run ingest first."
        )

    base_path = f"{account}/{app}/shared/uploads/{source_hash}/extracted/COBOLSource"

    files = []

    # Main COBOL files
    cobol_path = f"{base_path}/Cobol"
    if storage_service.directory_exists(cobol_path):
        for f in storage_service.list_files(cobol_path, pattern="*.CBL"):
            files.append(FileInfo(
                name=f.split("/")[-1],
                path=f"cobol/{f}",
                type="file"
            ))
        for f in storage_service.list_files(cobol_path, pattern="*.cbl"):
            files.append(FileInfo(
                name=f.split("/")[-1],
                path=f"cobol/{f}",
                type="file"
            ))

    # Copybooks (check both spellings)
    for copybook_folder in ["Copybooks", "Copyboioks"]:
        copybook_path = f"{base_path}/{copybook_folder}"
        if storage_service.directory_exists(copybook_path):
            for f in storage_service.list_files(copybook_path, pattern="*.CBL"):
                files.append(FileInfo(
                    name=f.split("/")[-1],
                    path=f"copybooks/{f}",
                    type="file"
                ))
            for f in storage_service.list_files(copybook_path, pattern="*.cpy"):
                files.append(FileInfo(
                    name=f.split("/")[-1],
                    path=f"copybooks/{f}",
                    type="file"
                ))

    return FileListResponse(files=files, total=len(files))


@router.get(
    "/{account}/{app}/cobol/{file_path:path}",
    response_model=FileContentResponse,
    summary="Read COBOL file content"
)
async def read_cobol_file(account: str, app: str, file_path: str):
    """
    Read content of a COBOL source file (read-only).

    file_path can be:
    - cobol/IFPR321.CBL (main program)
    - copybooks/PAYCNLP1FD.CBL (copybook)
    """
    source_hash = _find_source_hash(account, app)
    if not source_hash:
        raise HTTPException(status_code=404, detail="Source not found")

    base_path = f"{account}/{app}/shared/uploads/{source_hash}/extracted/COBOLSource"

    # Map virtual path to actual path
    if file_path.startswith("cobol/"):
        actual_path = f"{base_path}/Cobol/{file_path[6:]}"
    elif file_path.startswith("copybooks/"):
        # Try both spellings
        filename = file_path[10:]
        actual_path = f"{base_path}/Copybooks/{filename}"
        if not storage_service.file_exists(actual_path):
            actual_path = f"{base_path}/Copyboioks/{filename}"
    else:
        actual_path = f"{base_path}/{file_path}"

    try:
        content = storage_service.read_file(actual_path)
        return FileContentResponse(
            path=file_path,
            content=content,
            size=len(content)
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")


# ============================================================================
# Java Endpoints (Read/Write from Workspace)
# ============================================================================

@router.get(
    "/{account}/{app}/java",
    response_model=FileListResponse,
    summary="List Java workspace files"
)
async def list_java_files(account: str, app: str, source: Optional[str] = None):
    """
    List all Java files.

    Query params:
    - source: "refactor" to list refactored files from code_refactor output
              (default: list from code_analysis workspace)
    """
    print(f"[files] list_java_files called: account={account}, app={app}, source={source}")

    # Handle refactored source - uses workspace (editable copy)
    if source == "refactor":
        # Ensure workspace exists (copies from transformed if needed)
        if not _ensure_refactor_workspace(account, app):
            raise HTTPException(
                status_code=404,
                detail="No refactored files found. Run code refactor with transformations first."
            )

        class_name = _find_refactor_class_name(account, app)
        workspace_path = f"{account}/{app}/workspace/refactor/{class_name}"

        files = []
        for f in storage_service.list_files(workspace_path, pattern="*.java"):
            files.append(FileInfo(
                name=f.split("/")[-1],
                path=f,
                type="file"
            ))
        return FileListResponse(files=files, total=len(files))

    # Default: workspace from code_analysis
    if not _ensure_workspace(account, app):
        raise HTTPException(
            status_code=404,
            detail="No Java files found. Run code analysis first."
        )

    project_name = _find_java_project_name(account, app)
    workspace_path = f"{account}/{app}/workspace/java/{project_name}"
    print(f"[files] list_java_files: workspace_path={workspace_path}")

    files = []
    raw_files = storage_service.list_files(workspace_path, pattern="*.java")
    print(f"[files] list_java_files: raw files found: {raw_files}")
    for f in raw_files:
        files.append(FileInfo(
            name=f.split("/")[-1],
            path=f,
            type="file"
        ))

    print(f"[files] list_java_files: returning {len(files)} files")
    return FileListResponse(files=files, total=len(files))


@router.get(
    "/{account}/{app}/java/{file_path:path}",
    response_model=FileContentResponse,
    summary="Read Java file content"
)
async def read_java_file(account: str, app: str, file_path: str, source: Optional[str] = None):
    """
    Read content of a Java file.

    Query params:
    - source: "refactor" to read from code_refactor output
              (default: read from code_analysis workspace)
    """
    # Handle refactored source - uses workspace (editable copy)
    if source == "refactor":
        if not _ensure_refactor_workspace(account, app):
            raise HTTPException(status_code=404, detail="No refactored files found")

        class_name = _find_refactor_class_name(account, app)
        actual_path = f"{account}/{app}/workspace/refactor/{class_name}/{file_path}"

        try:
            content = storage_service.read_file(actual_path)
            return FileContentResponse(
                path=file_path,
                content=content,
                size=len(content)
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    # Default: workspace from code_analysis
    if not _ensure_workspace(account, app):
        raise HTTPException(status_code=404, detail="Java workspace not found")

    project_name = _find_java_project_name(account, app)
    actual_path = f"{account}/{app}/workspace/java/{project_name}/{file_path}"

    try:
        content = storage_service.read_file(actual_path)
        return FileContentResponse(
            path=file_path,
            content=content,
            size=len(content)
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")


@router.post(
    "/{account}/{app}/java/{file_path:path}",
    response_model=FileContentResponse,
    summary="Save Java file content"
)
async def save_java_file(
    account: str,
    app: str,
    file_path: str,
    request: SaveFileRequest,
    source: Optional[str] = None
):
    """
    Save Java file content to workspace.

    Query params:
    - source: "refactor" to save to refactor workspace
              (default: save to code_analysis workspace)
    """
    # Handle refactored source
    if source == "refactor":
        if not _ensure_refactor_workspace(account, app):
            raise HTTPException(status_code=404, detail="Refactor workspace not found")

        class_name = _find_refactor_class_name(account, app)
        actual_path = f"{account}/{app}/workspace/refactor/{class_name}/{file_path}"

        try:
            storage_service.write_file(actual_path, request.content)
            return FileContentResponse(
                path=file_path,
                content=request.content,
                size=len(request.content)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error saving file: {e}")

    # Default: code_analysis workspace
    if not _ensure_workspace(account, app):
        raise HTTPException(status_code=404, detail="Java workspace not found")

    project_name = _find_java_project_name(account, app)
    actual_path = f"{account}/{app}/workspace/java/{project_name}/{file_path}"

    try:
        storage_service.write_file(actual_path, request.content)
        return FileContentResponse(
            path=file_path,
            content=request.content,
            size=len(request.content)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {e}")


# ============================================================================
# Workspace Management
# ============================================================================

@router.post(
    "/{account}/{app}/workspace/reset",
    response_model=WorkspaceResetResponse,
    summary="Reset workspace from generated"
)
async def reset_workspace(account: str, app: str):
    """
    Reset workspace by copying from generated/ folder.

    This overwrites any user edits with the original generated code.
    Use with caution - user changes will be lost!
    """
    project_name = _find_java_project_name(account, app)
    if not project_name:
        raise HTTPException(
            status_code=404,
            detail="No generated Java project found. Run code analysis first."
        )

    workspace_path = f"{account}/{app}/workspace/java/{project_name}"
    generated_path = f"{account}/{app}/code_analysis/generated/{project_name}"

    if not storage_service.directory_exists(generated_path):
        raise HTTPException(status_code=404, detail="Generated folder not found")

    try:
        # Delete existing workspace
        if storage_service.directory_exists(workspace_path):
            storage_service.delete_directory(workspace_path)

        # Copy from generated
        storage_service.copy_directory(generated_path, workspace_path)

        # Count files copied
        files = storage_service.list_files(workspace_path, pattern="*.java")

        return WorkspaceResetResponse(
            success=True,
            message="Workspace reset to original generated code",
            files_copied=len(files)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting workspace: {e}")


@router.post(
    "/{account}/{app}/workspace/refactor/reset",
    response_model=WorkspaceResetResponse,
    summary="Reset refactor workspace from transformed"
)
async def reset_refactor_workspace(account: str, app: str):
    """
    Reset refactor workspace by copying from transformed/ folder.

    This overwrites any user edits with the original refactored code.
    Use with caution - user changes will be lost!
    """
    class_name = _find_refactor_class_name(account, app)
    if not class_name:
        raise HTTPException(
            status_code=404,
            detail="No refactored Java files found. Run code refactor first."
        )

    workspace_path = f"{account}/{app}/workspace/refactor/{class_name}"
    transformed_path = f"{account}/{app}/code_refactor/{class_name}/output/transformed"

    if not storage_service.directory_exists(transformed_path):
        raise HTTPException(status_code=404, detail="Transformed folder not found")

    try:
        # Delete existing workspace
        if storage_service.directory_exists(workspace_path):
            storage_service.delete_directory(workspace_path)

        # Copy from transformed
        storage_service.copy_directory(transformed_path, workspace_path)

        # Count files copied
        files = storage_service.list_files(workspace_path, pattern="*.java")

        return WorkspaceResetResponse(
            success=True,
            message="Refactor workspace reset to original refactored code",
            files_copied=len(files)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting refactor workspace: {e}")


@router.get(
    "/{account}/{app}/workspace/status",
    summary="Get workspace status"
)
async def get_workspace_status(account: str, app: str):
    """
    Get workspace status - whether it exists and any modifications.
    """
    project_name = _find_java_project_name(account, app)

    result = {
        "has_generated": False,
        "has_workspace": False,
        "project_name": project_name,
        "java_files": 0,
    }

    if project_name:
        generated_path = f"{account}/{app}/code_analysis/generated/{project_name}"
        workspace_path = f"{account}/{app}/workspace/java/{project_name}"

        result["has_generated"] = storage_service.directory_exists(generated_path)
        result["has_workspace"] = storage_service.directory_exists(workspace_path)

        if result["has_workspace"]:
            files = storage_service.list_files(workspace_path, pattern="*.java")
            result["java_files"] = len(files)

    return result


# ============================================================================
# Section Mapping (for Code Editor navigation)
# ============================================================================

@router.get(
    "/{account}/{app}/sections",
    response_model=SectionsResponse,
    summary="Get section mappings"
)
async def get_sections(account: str, app: str):
    """
    Get COBOL section to Java method mappings.

    Uses procedure_model.json from code analysis reports.
    """
    # Find procedure model
    reports_path = f"{account}/{app}/code_analysis/reports"

    # Try to find procedure model file
    procedure_model = None
    if storage_service.directory_exists(reports_path):
        files = storage_service.list_files(reports_path, pattern="*_procedure_model.json", recursive=False)
        if files:
            try:
                content = storage_service.read_file(f"{reports_path}/{files[0]}")
                procedure_model = json.loads(content)
            except Exception as e:
                print(f"[files] Error loading procedure model: {e}")

    if not procedure_model:
        return SectionsResponse(sections=[], total=0)

    # Extract section mappings
    sections = []

    # Paragraphs
    for para in procedure_model.get("paragraphs", []):
        sections.append(SectionMapping(
            cobol_name=para.get("name", "UNKNOWN"),
            cobol_start_line=para.get("start_line", 0),
            cobol_end_line=para.get("end_line", 0),
            java_method=para.get("java_method"),
            java_class=para.get("java_class"),
            status="converted" if para.get("java_method") else "pending"
        ))

    # Sections (COBOL sections containing paragraphs)
    for section in procedure_model.get("sections", []):
        sections.append(SectionMapping(
            cobol_name=section.get("name", "UNKNOWN"),
            cobol_start_line=section.get("start_line", 0),
            cobol_end_line=section.get("end_line", 0),
            java_method=None,
            java_class=section.get("java_class"),
            status="converted" if section.get("java_class") else "pending"
        ))

    # Sort by start line
    sections.sort(key=lambda s: s.cobol_start_line)

    return SectionsResponse(sections=sections, total=len(sections))
