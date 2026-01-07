"""
Storage API Routes

Simple endpoints to list and read files from storage.
Used by AI Explain to read Java files from artifacts_path.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.storage import storage_service

router = APIRouter(prefix="/storage", tags=["storage"])


class FileItem(BaseModel):
    name: str
    path: str


class ListFilesResponse(BaseModel):
    files: List[FileItem]
    total: int
    path: str


class ReadFileResponse(BaseModel):
    path: str
    content: str
    size: int


@router.get("/list", response_model=ListFilesResponse)
async def list_files(
    path: str = Query(..., description="Path to list files from"),
    pattern: str = Query("*", description="File pattern to match (e.g., *.java)")
):
    """
    List files and directories at the given path matching the pattern.
    """
    print(f"[storage] list_files: path={path}, pattern={pattern}")

    if not storage_service.directory_exists(path):
        print(f"[storage] Directory does not exist: {path}")
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")

    try:
        files = []

        # First list directories
        dirs = storage_service.list_directories(path)
        print(f"[storage] Found {len(dirs)} directories: {dirs}")
        for d in dirs:
            files.append(FileItem(name=d, path=f"{path}/{d}"))

        # Then list files matching pattern
        raw_files = storage_service.list_files(path, pattern=pattern, recursive=False)
        print(f"[storage] Found {len(raw_files)} files: {raw_files}")
        for f in raw_files:
            name = f.split("/")[-1] if "/" in f else f
            files.append(FileItem(name=name, path=f"{path}/{f}" if not f.startswith(path) else f))

        return ListFilesResponse(files=files, total=len(files), path=path)

    except Exception as e:
        print(f"[storage] Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/read", response_model=ReadFileResponse)
async def read_file(
    path: str = Query(..., description="Path to the file to read")
):
    """
    Read content of a file.
    """
    print(f"[storage] read_file: path={path}")

    if not storage_service.file_exists(path):
        print(f"[storage] File does not exist: {path}")
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    try:
        content = storage_service.read_file(path)
        print(f"[storage] Read {len(content)} bytes from {path}")

        return ReadFileResponse(path=path, content=content, size=len(content))

    except Exception as e:
        print(f"[storage] Error reading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))
