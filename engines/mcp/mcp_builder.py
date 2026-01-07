"""
MCP Builder - Generate real MCP servers that run in Docker.

Creates project-specific MCP servers that:
- Use HTTP/SSE transport (not stdio) for API integration
- Can run in Docker containers
- Read from S3 or local filesystem (configurable)
- Are isolated per project (multi-tenant safe)

Usage:
    from engines.mcp import MCPBuilder

    builder = MCPBuilder("EVH", "TestApp01")
    result = builder.generate()

    # Result contains paths to:
    # - server.py (FastMCP server)
    # - Dockerfile
    # - requirements.txt
    # - storage.py (S3/local abstraction)
"""

import json
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from config.settings import settings


class MCPBuilder:
    """
    Builds project-specific MCP servers for Docker deployment.

    Output location: {base_local_path}/mcp_servers/{account}_{app}/
    """

    def __init__(
        self,
        scout_account_id: str,
        application_name: str,
        base_path: Optional[Path] = None,
    ):
        self.account_id = scout_account_id
        self.app_name = application_name
        self.base_path = base_path or settings.base_local_path

        # MCP server output directory
        self.mcp_dir = self.base_path / "mcp_servers" / f"{scout_account_id}_{application_name}"

        # User's data paths (for local mode)
        self.project_path = self.base_path / "code-transformation-v2" / scout_account_id / application_name
        self.artifacts_path = self.project_path
        self.source_path = self._resolve_source_path()

    def _resolve_source_path(self) -> Path:
        """Resolve the actual source files path."""
        uploads_path = self.project_path / "shared" / "uploads"
        latest_json = uploads_path / "latest.json"

        if latest_json.exists():
            try:
                with open(latest_json) as f:
                    data = json.load(f)
                source_hash = data.get("source_hash")
                if source_hash:
                    extracted_path = uploads_path / source_hash / "extracted"
                    if extracted_path.exists():
                        return extracted_path
            except Exception:
                pass

        if uploads_path.exists():
            for item in uploads_path.iterdir():
                if item.is_dir() and (item / "extracted").exists():
                    return item / "extracted"

        return uploads_path / "latest" / "extracted"

    def generate(self, custom_tools: Optional[list] = None) -> dict:
        """
        Generate the MCP server for this project.

        Creates:
        - server.py (FastMCP with HTTP transport)
        - storage.py (S3/local abstraction)
        - Dockerfile
        - requirements.txt
        - docker-compose.yml (for local testing)

        Returns:
            dict with generation results including paths
        """
        self.mcp_dir.mkdir(parents=True, exist_ok=True)

        # Generate all files
        files = {
            "server.py": self._generate_server_code(custom_tools),
            "storage.py": self._generate_storage_code(),
            "Dockerfile": self._generate_dockerfile(),
            "requirements.txt": self._generate_requirements(),
            "docker-compose.yml": self._generate_docker_compose(),
            ".env.example": self._generate_env_example(),
        }

        for filename, content in files.items():
            (self.mcp_dir / filename).write_text(content)

        return {
            "success": True,
            "mcp_dir": str(self.mcp_dir),
            "server_path": str(self.mcp_dir / "server.py"),
            "dockerfile_path": str(self.mcp_dir / "Dockerfile"),
            "account_id": self.account_id,
            "app_name": self.app_name,
            "generated_at": datetime.now().isoformat(),
            "files": list(files.keys()),
        }

    def get_status(self) -> dict:
        """Get the current status of this project's MCP server."""
        server_exists = (self.mcp_dir / "server.py").exists()
        dockerfile_exists = (self.mcp_dir / "Dockerfile").exists()

        return {
            "account_id": self.account_id,
            "app_name": self.app_name,
            "mcp_dir": str(self.mcp_dir),
            "server_exists": server_exists,
            "dockerfile_exists": dockerfile_exists,
            "source_path": str(self.source_path),
            "source_exists": self.source_path.exists(),
            "artifacts_path": str(self.artifacts_path),
            "artifacts_exist": self.artifacts_path.exists(),
        }

    def get_claude_config(self) -> dict:
        """Get claude_desktop_config.json for this MCP server (bonus feature)."""
        server_name = f"modernizeit-{self.account_id}-{self.app_name}"

        return {
            "mcpServers": {
                server_name: {
                    "command": "python",
                    "args": ["server.py", "--transport", "stdio"],
                    "cwd": str(self.mcp_dir),
                    "env": {
                        "STORAGE_MODE": "local",
                        "LOCAL_SOURCE_PATH": str(self.source_path),
                        "LOCAL_ARTIFACTS_PATH": str(self.artifacts_path),
                        "ACCOUNT_ID": self.account_id,
                        "APP_NAME": self.app_name,
                    }
                }
            }
        }

    def _generate_custom_tools_code(self, custom_tools: list) -> str:
        """Generate code for custom API and Database tools."""
        if not custom_tools:
            return ""

        code_parts = []
        code_parts.append('''
# =============================================================================
# Custom Tools
# =============================================================================
''')

        for tool in custom_tools:
            tool_type = tool.get('type', 'api')
            name = tool.get('name', 'custom_tool').replace(' ', '_').lower()
            description = tool.get('description', f'Custom {tool_type} tool')

            if tool_type == 'url':
                # Simple URL fetch - for documentation/reference pages
                url = tool.get('url', '')
                code_parts.append(f'''
@mcp.tool()
async def {name}() -> str:
    """
    {description}

    Fetches and returns the content from: {url}
    """
    import httpx
    from html.parser import HTMLParser

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text = []
            self.skip = False
        def handle_starttag(self, tag, attrs):
            if tag in ('script', 'style', 'nav', 'header', 'footer'):
                self.skip = True
        def handle_endtag(self, tag):
            if tag in ('script', 'style', 'nav', 'header', 'footer'):
                self.skip = False
        def handle_data(self, data):
            if not self.skip:
                text = data.strip()
                if text:
                    self.text.append(text)

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get("{url}", headers={{"User-Agent": "Mozilla/5.0"}})
            response.raise_for_status()
            html = response.text

            # Extract text from HTML
            parser = TextExtractor()
            parser.feed(html)
            content = "\\n".join(parser.text)

            # Truncate if too long
            if len(content) > 50000:
                content = content[:50000] + "\\n... [truncated]"

            return json.dumps({{
                "url": "{url}",
                "content": content
            }}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})
''')

            elif tool_type == 'api':
                url = tool.get('url', '')
                method = tool.get('method', 'GET')
                body = tool.get('body', '')

                if method == 'POST' and body:
                    code_parts.append(f'''
@mcp.tool()
async def {name}(query: str = "") -> str:
    """
    {description}

    Args:
        query: Search query or parameters
    """
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            url = "{url}"
            body_template = """{body}"""
            # Replace ${{query}} placeholder with actual query
            body_str = body_template.replace("${{query}}", query)
            body_data = json.loads(body_str) if body_str else {{}}
            response = await client.post(url, json=body_data)
            response.raise_for_status()
            return json.dumps({{"url": url, "data": response.json()}}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})
''')
                else:
                    code_parts.append(f'''
@mcp.tool()
async def {name}(query: str = "") -> str:
    """
    {description}

    Args:
        query: Search query or parameters
    """
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            url = "{url}"
            if query:
                url = f"{{url}}?q={{query}}" if "?" not in url else f"{{url}}&q={{query}}"
            response = await client.get(url)
            response.raise_for_status()
            return json.dumps({{"url": url, "data": response.json()}}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})
''')

            elif tool_type == 'database':
                db_type = tool.get('dbType', 'sqlite')
                connection = tool.get('connectionString', '')
                query_template = tool.get('query', 'SELECT * FROM ?')

                if db_type == 'sqlite':
                    code_parts.append(f'''
@mcp.tool()
async def {name}(search_term: str = "") -> str:
    """
    {description}

    Args:
        search_term: Value to search for in the query
    """
    import sqlite3
    try:
        conn = sqlite3.connect("{connection}")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = """{query_template}"""
        if "?" in query and search_term:
            cursor.execute(query, (f"%{{search_term}}%",))
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        results = [dict(row) for row in rows[:100]]
        return json.dumps({{"count": len(results), "results": results}}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})
''')
                elif db_type == 'postgresql':
                    code_parts.append(f'''
@mcp.tool()
async def {name}(search_term: str = "") -> str:
    """
    {description}

    Args:
        search_term: Value to search for in the query
    """
    import psycopg2
    import psycopg2.extras
    try:
        conn = psycopg2.connect("{connection}")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query = """{query_template}"""
        if "%s" in query and search_term:
            cursor.execute(query, (f"%{{search_term}}%",))
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        results = [dict(row) for row in rows[:100]]
        return json.dumps({{"count": len(results), "results": results}}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})
''')
                elif db_type == 'mysql':
                    code_parts.append(f'''
@mcp.tool()
async def {name}(search_term: str = "") -> str:
    """
    {description}

    Args:
        search_term: Value to search for in the query
    """
    import pymysql
    try:
        conn = pymysql.connect(
            host="{connection.split('@')[1].split('/')[0] if '@' in connection else 'localhost'}",
            database="{connection.split('/')[-1] if '/' in connection else connection}",
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        query = """{query_template}"""
        if "%s" in query and search_term:
            cursor.execute(query, (f"%{{search_term}}%",))
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        results = list(rows[:100])
        return json.dumps({{"count": len(results), "results": results}}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})
''')

        return ''.join(code_parts)

    def _generate_server_code(self, custom_tools: Optional[list] = None) -> str:
        """Generate the FastMCP server.py code."""
        custom_tools_code = self._generate_custom_tools_code(custom_tools or [])

        return f'''#!/usr/bin/env python3
"""
MCP Server for {self.account_id}/{self.app_name}

A real MCP server that runs in Docker with HTTP/SSE transport.
Can read from S3 (production) or local filesystem (development).

Run modes:
  HTTP (for API): python server.py --transport http --port 8080
  SSE (for API):  python server.py --transport sse --port 8080
  STDIO (Claude): python server.py --transport stdio

Environment variables:
  STORAGE_MODE: "local" or "s3"
  S3_BUCKET: S3 bucket name (when STORAGE_MODE=s3)
  S3_PREFIX: S3 prefix for this project
  LOCAL_SOURCE_PATH: Local path to source files
  LOCAL_ARTIFACTS_PATH: Local path to artifacts
"""

import argparse
import json
import os
from mcp.server.fastmcp import FastMCP
from storage import get_storage

# Configuration from environment
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "{self.account_id}")
APP_NAME = os.getenv("APP_NAME", "{self.app_name}")

# Initialize FastMCP server
mcp = FastMCP(f"ModernizeIT - {{ACCOUNT_ID}}/{{APP_NAME}}")

# Initialize storage (S3 or local based on STORAGE_MODE env var)
storage = get_storage()


# =============================================================================
# Source Code Tools
# =============================================================================

@mcp.tool()
async def list_source_files(pattern: str = "*") -> str:
    """
    List source files in the project.

    Args:
        pattern: Glob pattern to filter files (e.g., "*.cbl", "*.java")

    Returns:
        JSON list of matching files with paths and sizes
    """
    try:
        files = storage.list_files("source", pattern)
        return json.dumps({{
            "pattern": pattern,
            "count": len(files),
            "files": files[:100]
        }}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})


@mcp.tool()
async def read_source_file(file_path: str) -> str:
    """
    Read a source file's contents.

    Args:
        file_path: Path relative to source directory (e.g., "MAIN.cbl")

    Returns:
        File contents with line numbers
    """
    try:
        content = storage.read_file("source", file_path)
        lines = content.splitlines()
        numbered = [f"{{i+1:6d}} | {{line}}" for i, line in enumerate(lines)]
        return json.dumps({{
            "file": file_path,
            "lines": len(lines),
            "content": "\\n".join(numbered)
        }}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})


@mcp.tool()
async def search_source_code(query: str, file_pattern: str = "*") -> str:
    """
    Search for text in source files.

    Args:
        query: Text to search for (case-insensitive)
        file_pattern: Glob pattern to filter files (e.g., "*.cbl")

    Returns:
        Matching lines with file paths and line numbers
    """
    try:
        results = storage.search_files("source", query, file_pattern, max_results=50)
        return json.dumps({{
            "query": query,
            "pattern": file_pattern,
            "count": len(results),
            "matches": results
        }}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})


# =============================================================================
# Artifact Tools
# =============================================================================

@mcp.tool()
async def list_artifacts(flow: str = "") -> str:
    """
    List analysis artifact files.

    Args:
        flow: Filter by analysis flow (e.g., "code_analysis", "dependency_mapper")

    Returns:
        List of JSON artifact files
    """
    try:
        prefix = f"artifacts/{{flow}}" if flow else "artifacts"
        files = storage.list_files(prefix, "*.json")
        return json.dumps({{
            "flow_filter": flow or "all",
            "count": len(files),
            "artifacts": files[:100]
        }}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})


@mcp.tool()
async def read_artifact(artifact_path: str) -> str:
    """
    Read an artifact JSON file.

    Args:
        artifact_path: Path relative to artifacts directory

    Returns:
        JSON contents of the artifact
    """
    try:
        content = storage.read_file("artifacts", artifact_path)
        data = json.loads(content)

        # Truncate if too large
        content_str = json.dumps(data, indent=2)
        if len(content_str) > 50000:
            return json.dumps({{
                "artifact": artifact_path,
                "truncated": True,
                "message": "Artifact too large, showing keys only",
                "keys": list(data.keys()) if isinstance(data, dict) else f"Array with {{len(data)}} items"
            }}, indent=2)

        return json.dumps({{
            "artifact": artifact_path,
            "data": data
        }}, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({{"error": f"Invalid JSON: {{e}}"}})
    except Exception as e:
        return json.dumps({{"error": str(e)}})


@mcp.tool()
async def search_artifacts(query: str) -> str:
    """
    Search across all artifact JSON files.

    Args:
        query: Text to search for in artifact contents

    Returns:
        Artifacts containing the query text
    """
    try:
        results = storage.search_files("artifacts", query, "*.json", max_results=20)
        return json.dumps({{
            "query": query,
            "count": len(results),
            "matching_artifacts": results
        }}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})


# =============================================================================
# Project Info Tools
# =============================================================================

@mcp.tool()
async def get_project_info() -> str:
    """
    Get information about this project.

    Returns:
        Project metadata including account, app name, and file counts
    """
    try:
        source_files = storage.list_files("source", "*")
        artifact_files = storage.list_files("artifacts", "*.json")

        return json.dumps({{
            "account_id": ACCOUNT_ID,
            "application_name": APP_NAME,
            "storage_mode": os.getenv("STORAGE_MODE", "local"),
            "source_file_count": len(source_files),
            "artifact_file_count": len(artifact_files)
        }}, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})


@mcp.tool()
async def get_analysis_summary() -> str:
    """
    Get a summary of all analysis results for this project.

    Returns:
        Summary of available artifacts by analysis type
    """
    try:
        summary = {{
            "account_id": ACCOUNT_ID,
            "application_name": APP_NAME,
            "analyses": {{}}
        }}

        analysis_types = [
            "code_analysis",
            "dependency_mapper",
            "monolith_identifier",
            "data_analysis",
            "discovery",
            "architecture"
        ]

        for analysis in analysis_types:
            try:
                files = storage.list_files(f"artifacts/{{analysis}}", "*.json")
                if files:
                    summary["analyses"][analysis] = {{
                        "artifact_count": len(files),
                        "artifacts": [f["path"] for f in files[:10]]
                    }}
            except Exception:
                pass

        return json.dumps(summary, indent=2)
    except Exception as e:
        return json.dumps({{"error": str(e)}})

{custom_tools_code}
# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="MCP Server for {self.account_id}/{self.app_name}")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="sse",
                        help="Transport mode (default: sse)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind (default: 8080)")

    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run()
    else:
        # Run SSE server using uvicorn
        app = mcp.sse_app()
        uvicorn.run(app, host=args.host, port=args.port)
'''

    def _generate_storage_code(self) -> str:
        """Generate the storage abstraction layer."""
        return '''"""
Storage abstraction for MCP server.

Supports:
- Local filesystem (development)
- S3 (production)

Configure via environment variables:
  STORAGE_MODE: "local" or "s3"

For local:
  LOCAL_SOURCE_PATH: Path to source files
  LOCAL_ARTIFACTS_PATH: Path to artifacts

For S3:
  S3_BUCKET: Bucket name
  S3_PREFIX: Prefix for this project (e.g., "code-transformation-v2/ACME/App1")
  AWS_REGION: AWS region (default: us-east-1)
"""

import os
import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    def list_files(self, prefix: str, pattern: str = "*") -> List[Dict[str, Any]]:
        """List files matching pattern under prefix."""
        pass

    @abstractmethod
    def read_file(self, prefix: str, file_path: str) -> str:
        """Read file contents."""
        pass

    @abstractmethod
    def search_files(self, prefix: str, query: str, pattern: str = "*", max_results: int = 50) -> List[Dict[str, Any]]:
        """Search for text in files."""
        pass


class LocalStorage(StorageProvider):
    """Local filesystem storage provider."""

    def __init__(self):
        self.source_path = Path(os.getenv("LOCAL_SOURCE_PATH", "/data/source"))
        self.artifacts_path = Path(os.getenv("LOCAL_ARTIFACTS_PATH", "/data/artifacts"))

    def _get_base_path(self, prefix: str) -> Path:
        if prefix.startswith("source"):
            return self.source_path / prefix.replace("source", "", 1).lstrip("/")
        elif prefix.startswith("artifacts"):
            return self.artifacts_path / prefix.replace("artifacts", "", 1).lstrip("/")
        return self.source_path / prefix

    def list_files(self, prefix: str, pattern: str = "*") -> List[Dict[str, Any]]:
        base_path = self._get_base_path(prefix)
        if not base_path.exists():
            return []

        files = []
        for f in base_path.rglob(pattern):
            if f.is_file():
                files.append({
                    "path": str(f.relative_to(base_path)),
                    "size": f.stat().st_size,
                    "extension": f.suffix.lower()
                })
        return files

    def read_file(self, prefix: str, file_path: str) -> str:
        base_path = self._get_base_path(prefix)
        full_path = base_path / file_path

        # Security: prevent path traversal
        if not str(full_path.resolve()).startswith(str(base_path.resolve())):
            raise ValueError("Access denied: path outside allowed directory")

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        return full_path.read_text(encoding="utf-8", errors="replace")

    def search_files(self, prefix: str, query: str, pattern: str = "*", max_results: int = 50) -> List[Dict[str, Any]]:
        base_path = self._get_base_path(prefix)
        if not base_path.exists():
            return []

        results = []
        query_lower = query.lower()

        for f in base_path.rglob(pattern):
            if not f.is_file():
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines()):
                    if query_lower in line.lower():
                        results.append({
                            "file": str(f.relative_to(base_path)),
                            "line": i + 1,
                            "content": line.strip()[:200]
                        })
                        if len(results) >= max_results:
                            return results
            except Exception:
                continue

        return results


class S3Storage(StorageProvider):
    """S3 storage provider."""

    def __init__(self):
        import boto3

        self.bucket = os.getenv("S3_BUCKET")
        self.prefix = os.getenv("S3_PREFIX", "").rstrip("/")
        region = os.getenv("AWS_REGION", "us-east-1")

        if not self.bucket:
            raise ValueError("S3_BUCKET environment variable is required")

        self.s3 = boto3.client("s3", region_name=region)

    def _get_s3_prefix(self, prefix: str) -> str:
        if self.prefix:
            return f"{self.prefix}/{prefix}"
        return prefix

    def list_files(self, prefix: str, pattern: str = "*") -> List[Dict[str, Any]]:
        s3_prefix = self._get_s3_prefix(prefix)

        files = []
        paginator = self.s3.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self.bucket, Prefix=s3_prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                relative_path = key[len(s3_prefix):].lstrip("/")

                # Apply pattern filter
                if fnmatch.fnmatch(relative_path, pattern) or fnmatch.fnmatch(Path(relative_path).name, pattern):
                    files.append({
                        "path": relative_path,
                        "size": obj["Size"],
                        "extension": Path(relative_path).suffix.lower()
                    })

        return files

    def read_file(self, prefix: str, file_path: str) -> str:
        s3_prefix = self._get_s3_prefix(prefix)
        key = f"{s3_prefix}/{file_path}".replace("//", "/")

        response = self.s3.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read().decode("utf-8", errors="replace")

    def search_files(self, prefix: str, query: str, pattern: str = "*", max_results: int = 50) -> List[Dict[str, Any]]:
        # List all matching files first
        files = self.list_files(prefix, pattern)

        results = []
        query_lower = query.lower()

        for file_info in files:
            if len(results) >= max_results:
                break

            try:
                content = self.read_file(prefix, file_info["path"])
                for i, line in enumerate(content.splitlines()):
                    if query_lower in line.lower():
                        results.append({
                            "file": file_info["path"],
                            "line": i + 1,
                            "content": line.strip()[:200]
                        })
                        if len(results) >= max_results:
                            break
            except Exception:
                continue

        return results


def get_storage() -> StorageProvider:
    """Get the appropriate storage provider based on configuration."""
    mode = os.getenv("STORAGE_MODE", "local").lower()

    if mode == "s3":
        return S3Storage()
    else:
        return LocalStorage()
'''

    def _generate_dockerfile(self) -> str:
        """Generate Dockerfile for the MCP server."""
        return f'''FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py storage.py ./

# Environment variables (override at runtime)
ENV STORAGE_MODE=local
ENV LOCAL_SOURCE_PATH=/data/source
ENV LOCAL_ARTIFACTS_PATH=/data/artifacts
ENV ACCOUNT_ID={self.account_id}
ENV APP_NAME={self.app_name}

# Expose SSE port
EXPOSE 8080

# Health check using Python (curl not in slim image)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/sse')" || exit 1

# Run MCP server with SSE transport
CMD ["python", "server.py", "--transport", "sse", "--port", "8080"]
'''

    def _generate_requirements(self) -> str:
        """Generate requirements.txt for the MCP server."""
        return '''mcp>=1.0.0
httpx>=0.25.0
boto3>=1.28.0
uvicorn>=0.24.0
# Database drivers
psycopg2-binary>=2.9.0
pymysql>=1.1.0
'''

    def _generate_docker_compose(self) -> str:
        """Generate docker-compose.yml for local testing."""
        return f'''version: '3.8'

services:
  mcp-server:
    build: .
    ports:
      - "8080:8080"
    environment:
      - STORAGE_MODE=local
      - LOCAL_SOURCE_PATH=/data/source
      - LOCAL_ARTIFACTS_PATH=/data/artifacts
      - ACCOUNT_ID={self.account_id}
      - APP_NAME={self.app_name}
    volumes:
      # Mount local data directories for testing
      - {self.source_path}:/data/source:ro
      - {self.artifacts_path}:/data/artifacts:ro
'''

    def _generate_env_example(self) -> str:
        """Generate .env.example file."""
        return f'''# MCP Server Configuration

# Storage mode: "local" or "s3"
STORAGE_MODE=local

# Local storage paths (when STORAGE_MODE=local)
LOCAL_SOURCE_PATH={self.source_path}
LOCAL_ARTIFACTS_PATH={self.artifacts_path}

# S3 storage config (when STORAGE_MODE=s3)
S3_BUCKET=your-bucket-name
S3_PREFIX=code-transformation-v2/{self.account_id}/{self.app_name}
AWS_REGION=us-east-1

# Project info
ACCOUNT_ID={self.account_id}
APP_NAME={self.app_name}
'''


# =============================================================================
# Convenience Functions
# =============================================================================

def generate_mcp_for_project(
    scout_account_id: str,
    application_name: str,
    custom_tools: Optional[list] = None
) -> dict:
    """Generate MCP server for a project."""
    builder = MCPBuilder(scout_account_id, application_name)
    return builder.generate(custom_tools)


def get_mcp_status(scout_account_id: str, application_name: str) -> dict:
    """Get MCP status for a project."""
    builder = MCPBuilder(scout_account_id, application_name)
    return builder.get_status()


def get_claude_config(scout_account_id: str, application_name: str) -> dict:
    """Get claude_desktop_config.json for a project."""
    builder = MCPBuilder(scout_account_id, application_name)
    return builder.get_claude_config()
