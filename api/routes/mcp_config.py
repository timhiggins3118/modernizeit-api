"""
MCP Configuration Route

Manages project-specific MCP servers:
- Generate MCP servers for account/application
- Get Claude Desktop configuration
- List available tools
- Get MCP status

MCP servers are generated at: {base_path}/mcp_servers/{account}_{app}/
"""

import subprocess
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from config.settings import settings
from engines.mcp import MCPBuilder, generate_mcp_for_project, get_mcp_status, get_claude_config

router = APIRouter(prefix="/mcp", tags=["mcp"])


class MCPServerConfig(BaseModel):
    """MCP server configuration for client connections."""
    name: str
    command: str
    args: list[str]
    cwd: str
    env: dict[str, str]


class MCPConfigResponse(BaseModel):
    """Response containing MCP configuration."""
    servers: dict[str, MCPServerConfig]


@router.get("/config", response_model=MCPConfigResponse)
async def get_mcp_config():
    """
    Get MCP server configuration for Claude Desktop or other MCP clients.

    Returns the configuration needed to connect to the modernizeit-artifacts MCP.
    The UI can use this to dynamically configure MCP connections.
    """
    # MCP server location (relative to modernizeit-api)
    mcp_path = str(settings.base_local_path.parent / "modernizeit-mcp")

    return MCPConfigResponse(
        servers={
            "modernizeit-artifacts": MCPServerConfig(
                name="modernizeit-artifacts",
                command="uv",
                args=["run", "--with", "mcp", "mcp", "run", "server.py"],
                cwd=mcp_path,
                env={
                    "MODERNIZEIT_BASE_LOCAL_PATH": str(settings.base_local_path),
                    "MONGODB_URI": settings.mongodb_uri,
                    "MONGODB_DATABASE": settings.mongodb_database
                }
            )
        }
    )


@router.get("/tools")
async def list_mcp_tools():
    """
    List available MCP tools and their descriptions.

    This helps the UI understand what capabilities the MCP provides.
    """
    return {
        "tools": [
            {
                "name": "list_accounts",
                "description": "List all available scout accounts and their applications",
                "parameters": []
            },
            {
                "name": "list_artifacts",
                "description": "List all JSON artifact files for an account/application",
                "parameters": ["scout_account_id", "application_name", "flow (optional)", "pattern (optional)"]
            },
            {
                "name": "read_artifact",
                "description": "Read the contents of a specific JSON artifact file",
                "parameters": ["scout_account_id", "application_name", "filename"]
            },
            {
                "name": "search_artifacts",
                "description": "Search across all JSON files for content matching a query",
                "parameters": ["scout_account_id", "application_name", "query", "flow (optional)", "max_results (optional)"]
            },
            {
                "name": "summarize_artifacts",
                "description": "Get a high-level summary of all artifacts for an account/application",
                "parameters": ["scout_account_id", "application_name"]
            },
            {
                "name": "query_mongodb",
                "description": "Query MongoDB for artifacts by account/application",
                "parameters": ["scout_account_id", "application_name", "collection", "artifact_type (optional)", "program (optional)", "limit (optional)"]
            },
            {
                "name": "list_mongodb_collections",
                "description": "List all MongoDB collections with document counts",
                "parameters": []
            },
            {
                "name": "list_mongodb_artifact_types",
                "description": "List artifact types available for an account/application in a collection",
                "parameters": ["scout_account_id", "application_name", "collection"]
            }
        ]
    }


# =============================================================================
# Project-Specific MCP Endpoints
# =============================================================================

class GenerateMCPRequest(BaseModel):
    """Request to generate MCP server for a project."""
    scout_account_id: str
    application_name: str
    custom_tools: Optional[list] = None


class GenerateMCPResponse(BaseModel):
    """Response from MCP generation."""
    success: bool
    mcp_dir: str
    server_path: str
    dockerfile_path: str
    account_id: str
    app_name: str
    generated_at: str
    files: list[str]
    # Docker container info (auto-started)
    container_running: bool = False
    container_name: Optional[str] = None
    container_port: Optional[int] = None
    container_url: Optional[str] = None
    docker_error: Optional[str] = None


class MCPStatusResponse(BaseModel):
    """MCP status for a project."""
    account_id: str
    app_name: str
    mcp_dir: str
    server_exists: bool
    dockerfile_exists: bool
    source_path: str
    source_exists: bool
    artifacts_path: str
    artifacts_exist: bool


@router.post("/generate", response_model=GenerateMCPResponse)
async def generate_mcp(request: GenerateMCPRequest):
    """
    Generate an MCP server for a specific project.

    Creates:
    - server.py - FastMCP server with project-specific tools
    - requirements.txt - Python dependencies
    - pyproject.toml - For uv package manager
    - claude_desktop_config.json - Configuration snippet for Claude Desktop
    - README.md - Documentation
    - Dockerfile - For running in Docker container

    Output location: {base_path}/mcp_servers/{account}_{app}/

    After generation, automatically builds and starts the Docker container.
    """
    try:
        # Generate the MCP server files
        result = generate_mcp_for_project(
            scout_account_id=request.scout_account_id,
            application_name=request.application_name,
            custom_tools=request.custom_tools
        )

        # Auto-start Docker container
        container_name = _get_container_name(request.scout_account_id, request.application_name)
        image_name = _get_image_name(request.scout_account_id, request.application_name)
        port = _get_port_for_server(request.scout_account_id, request.application_name)
        builder = MCPBuilder(request.scout_account_id, request.application_name)

        container_running = False
        container_url = None
        docker_error = None

        try:
            # Stop any existing container first
            if _container_exists(container_name):
                subprocess.run(
                    ["docker", "rm", "-f", container_name],
                    capture_output=True,
                    timeout=30
                )

            # Build Docker image (always rebuild after regeneration)
            print(f"[MCP] Building Docker image: {image_name}")
            build_result = subprocess.run(
                ["docker", "build", "-t", image_name, "."],
                cwd=str(builder.mcp_dir),
                capture_output=True,
                text=True,
                timeout=120
            )

            if build_result.returncode != 0:
                docker_error = f"Docker build failed: {build_result.stderr}"
                print(f"[MCP] {docker_error}")
            else:
                print(f"[MCP] Docker image built successfully")
                # Run the container
                print(f"[MCP] Starting container: {container_name} on port {port}")
                run_result = subprocess.run(
                    [
                        "docker", "run", "-d",
                        "--name", container_name,
                        "-p", f"{port}:8080",
                        "-e", "STORAGE_MODE=local",
                        "-e", f"LOCAL_SOURCE_PATH=/data/source",
                        "-e", f"LOCAL_ARTIFACTS_PATH=/data/artifacts",
                        "-e", f"ACCOUNT_ID={request.scout_account_id}",
                        "-e", f"APP_NAME={request.application_name}",
                        "-v", f"{builder.source_path}:/data/source:ro",
                        "-v", f"{builder.artifacts_path}:/data/artifacts:ro",
                        image_name
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                if run_result.returncode != 0:
                    docker_error = f"Docker run failed: {run_result.stderr}"
                    print(f"[MCP] {docker_error}")
                else:
                    # Wait for container to start
                    await asyncio.sleep(2)
                    container_running = _is_container_running(container_name)
                    if container_running:
                        container_url = f"http://localhost:{port}"
                        print(f"[MCP] Container running at {container_url}")
                    else:
                        # Get logs to see why it failed
                        logs_result = subprocess.run(
                            ["docker", "logs", container_name],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        docker_error = f"Container started but stopped: {logs_result.stdout or logs_result.stderr}"
                        print(f"[MCP] {docker_error}")

        except subprocess.TimeoutExpired as e:
            docker_error = f"Docker operation timed out: {str(e)}"
            print(f"[MCP] {docker_error}")
        except Exception as e:
            docker_error = f"Docker error: {str(e)}"
            print(f"[MCP] {docker_error}")

        return GenerateMCPResponse(
            **result,
            container_running=container_running,
            container_name=container_name,
            container_port=port,
            container_url=container_url,
            docker_error=docker_error
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{scout_account_id}/{application_name}", response_model=MCPStatusResponse)
async def get_status(scout_account_id: str, application_name: str):
    """
    Get the MCP status for a project.

    Returns whether the MCP server has been generated and paths to project data.
    """
    try:
        status = get_mcp_status(scout_account_id, application_name)
        return MCPStatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/claude-config/{scout_account_id}/{application_name}")
async def get_project_claude_config(scout_account_id: str, application_name: str):
    """
    Get the claude_desktop_config.json configuration for a project's MCP server.

    Returns the JSON configuration that can be added to Claude Desktop.
    """
    try:
        config = get_claude_config(scout_account_id, application_name)
        return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download-config/{scout_account_id}/{application_name}")
async def download_claude_config(scout_account_id: str, application_name: str):
    """
    Download the claude_desktop_config.json file for a project.

    Returns the file for download if it exists, or generates it first.
    """
    try:
        builder = MCPBuilder(scout_account_id, application_name)
        config_path = builder.mcp_dir / "claude_desktop_config.json"

        # Generate if doesn't exist
        if not config_path.exists():
            builder.generate()

        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Config file not found")

        return FileResponse(
            path=str(config_path),
            filename=f"claude_desktop_config_{scout_account_id}_{application_name}.json",
            media_type="application/json"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/inspector-url")
async def get_inspector_url():
    """
    Get the MCP Inspector URL for testing MCP servers.

    Returns the URL for the MCP Inspector tool.
    """
    return {
        "url": "http://localhost:6274",
        "instructions": "Run: npx @anthropic-ai/mcp-inspector uv run server.py"
    }


@router.delete("/delete/{scout_account_id}/{application_name}")
async def delete_mcp(scout_account_id: str, application_name: str):
    """
    Delete the MCP server for a project.

    Removes all generated files (server.py, config, etc.)
    """
    import shutil

    try:
        builder = MCPBuilder(scout_account_id, application_name)

        if not builder.mcp_dir.exists():
            return {"success": True, "message": "MCP server does not exist"}

        shutil.rmtree(builder.mcp_dir)

        return {
            "success": True,
            "message": f"Deleted MCP server at {builder.mcp_dir}",
            "account_id": scout_account_id,
            "app_name": application_name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/project-tools/{scout_account_id}/{application_name}")
async def get_project_tools(scout_account_id: str, application_name: str):
    """
    List tools available in a project's MCP server.

    Returns the tools that are generated for this specific project.
    """
    return {
        "account_id": scout_account_id,
        "application_name": application_name,
        "tools": [
            {
                "name": "list_source_files",
                "description": "List source files in the project",
                "parameters": ["pattern"]
            },
            {
                "name": "read_source_file",
                "description": "Read a source file's contents with line numbers",
                "parameters": ["file_path"]
            },
            {
                "name": "search_source_code",
                "description": "Search for text in source files",
                "parameters": ["query", "file_pattern"]
            },
            {
                "name": "list_artifacts",
                "description": "List analysis artifact files",
                "parameters": ["flow"]
            },
            {
                "name": "read_artifact",
                "description": "Read an artifact JSON file",
                "parameters": ["artifact_path"]
            },
            {
                "name": "search_artifacts",
                "description": "Search across all artifact JSON files",
                "parameters": ["query"]
            },
            {
                "name": "get_project_info",
                "description": "Get information about this project",
                "parameters": []
            },
            {
                "name": "get_analysis_summary",
                "description": "Get a summary of all analysis results",
                "parameters": []
            }
        ]
    }


# =============================================================================
# MCP Server Docker Management
# =============================================================================


def _get_container_name(account_id: str, app_name: str) -> str:
    """Get Docker container name for a project."""
    return f"mcp-{account_id}-{app_name}".lower().replace("_", "-")


def _get_image_name(account_id: str, app_name: str) -> str:
    """Get Docker image name for a project."""
    return f"mcp-{account_id}-{app_name}".lower().replace("_", "-")


def _get_port_for_server(account_id: str, app_name: str) -> int:
    """Get a port number for a server based on account/app hash."""
    import hashlib
    key = f"{account_id}_{app_name}"
    # Use MD5 for consistent hash across sessions (Python's hash() is randomized)
    hash_bytes = hashlib.md5(key.encode()).digest()
    hash_int = int.from_bytes(hash_bytes[:4], 'big')
    return 8100 + (hash_int % 900)


def _is_container_running(container_name: str) -> bool:
    """Check if a Docker container is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", f"name=^{container_name}$"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def _container_exists(container_name: str) -> bool:
    """Check if a Docker container exists (running or stopped)."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-aq", "-f", f"name=^{container_name}$"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def _image_exists(image_name: str) -> bool:
    """Check if a Docker image exists."""
    try:
        result = subprocess.run(
            ["docker", "images", "-q", image_name],
            capture_output=True,
            text=True,
            timeout=10
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


class StartServerRequest(BaseModel):
    """Request to start MCP server."""
    scout_account_id: str
    application_name: str
    port: Optional[int] = None
    rebuild: Optional[bool] = False


class ServerStatusResponse(BaseModel):
    """Response with server status."""
    account_id: str
    app_name: str
    running: bool
    port: Optional[int] = None
    url: Optional[str] = None
    container_name: Optional[str] = None


@router.post("/start")
async def start_mcp_server(request: StartServerRequest):
    """
    Start an MCP server in a Docker container.

    Builds the image if needed, then runs the container.
    """
    container_name = _get_container_name(request.scout_account_id, request.application_name)
    image_name = _get_image_name(request.scout_account_id, request.application_name)
    port = request.port or _get_port_for_server(request.scout_account_id, request.application_name)

    # Check if already running
    if _is_container_running(container_name):
        return {
            "success": True,
            "message": "Container already running",
            "account_id": request.scout_account_id,
            "app_name": request.application_name,
            "port": port,
            "url": f"http://localhost:{port}",
            "container_name": container_name
        }

    # Get server directory
    builder = MCPBuilder(request.scout_account_id, request.application_name)
    dockerfile_path = builder.mcp_dir / "Dockerfile"

    if not dockerfile_path.exists():
        raise HTTPException(
            status_code=400,
            detail="MCP server not found. Please generate it first."
        )

    try:
        # Build image if needed or rebuild requested
        if request.rebuild or not _image_exists(image_name):
            build_result = subprocess.run(
                ["docker", "build", "-t", image_name, "."],
                cwd=str(builder.mcp_dir),
                capture_output=True,
                text=True,
                timeout=120
            )
            if build_result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"Docker build failed: {build_result.stderr}"
                )

        # Remove existing stopped container if exists
        if _container_exists(container_name):
            subprocess.run(
                ["docker", "rm", "-f", container_name],
                capture_output=True,
                timeout=30
            )

        # Run the container
        run_result = subprocess.run(
            [
                "docker", "run", "-d",
                "--name", container_name,
                "-p", f"{port}:8080",
                "-e", "STORAGE_MODE=local",
                "-e", f"LOCAL_SOURCE_PATH=/data/source",
                "-e", f"LOCAL_ARTIFACTS_PATH=/data/artifacts",
                "-e", f"ACCOUNT_ID={request.scout_account_id}",
                "-e", f"APP_NAME={request.application_name}",
                "-v", f"{builder.source_path}:/data/source:ro",
                "-v", f"{builder.artifacts_path}:/data/artifacts:ro",
                image_name
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if run_result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Docker run failed: {run_result.stderr}"
            )

        # Wait a moment for container to start
        await asyncio.sleep(2)

        # Verify it's running
        if not _is_container_running(container_name):
            # Get container logs to see what went wrong
            logs_result = subprocess.run(
                ["docker", "logs", container_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            raise HTTPException(
                status_code=500,
                detail=f"Container failed to start: {logs_result.stderr or logs_result.stdout}"
            )

        return {
            "success": True,
            "message": "MCP server started in Docker",
            "account_id": request.scout_account_id,
            "app_name": request.application_name,
            "port": port,
            "url": f"http://localhost:{port}",
            "container_name": container_name
        }

    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Docker operation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop/{scout_account_id}/{application_name}")
async def stop_mcp_server(scout_account_id: str, application_name: str):
    """
    Stop an MCP server Docker container.
    """
    container_name = _get_container_name(scout_account_id, application_name)

    if not _container_exists(container_name):
        return {
            "success": True,
            "message": "Container not found",
            "account_id": scout_account_id,
            "app_name": application_name,
        }

    try:
        # Stop and remove the container
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            capture_output=True,
            timeout=30
        )

        return {
            "success": True,
            "message": "MCP server stopped",
            "account_id": scout_account_id,
            "app_name": application_name,
            "container_name": container_name
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Docker stop timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/running/{scout_account_id}/{application_name}", response_model=ServerStatusResponse)
async def get_server_status(scout_account_id: str, application_name: str):
    """
    Check if an MCP server Docker container is running.
    """
    container_name = _get_container_name(scout_account_id, application_name)
    port = _get_port_for_server(scout_account_id, application_name)

    running = _is_container_running(container_name)

    return ServerStatusResponse(
        account_id=scout_account_id,
        app_name=application_name,
        running=running,
        port=port if running else None,
        url=f"http://localhost:{port}" if running else None,
        container_name=container_name if running else None
    )


@router.get("/logs/{scout_account_id}/{application_name}")
async def get_server_logs(scout_account_id: str, application_name: str, tail: int = 100):
    """
    Get logs from an MCP server Docker container.
    """
    container_name = _get_container_name(scout_account_id, application_name)

    if not _container_exists(container_name):
        raise HTTPException(status_code=404, detail="Container not found")

    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(tail), container_name],
            capture_output=True,
            text=True,
            timeout=10
        )

        return {
            "account_id": scout_account_id,
            "app_name": application_name,
            "container_name": container_name,
            "logs": result.stdout + result.stderr
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Docker logs timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
