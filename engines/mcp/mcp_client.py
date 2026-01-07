"""
MCP Client - Communicate with MCP servers via SSE transport.

Uses the official MCP Python SDK's SSE client for proper protocol handling.

Usage:
    client = MCPClient(account_id, app_name, base_url="http://localhost:8080")

    tools = await client.list_tools()
    result = await client.call_tool("list_source_files", {"pattern": "*.cbl"})
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp import ClientSession
from mcp.client.sse import sse_client

from config.settings import settings


class MCPClientError(Exception):
    """Error communicating with MCP server."""
    pass


class MCPClient:
    """
    Client for communicating with MCP servers via SSE transport.

    Uses the official MCP SDK's SSE client.
    """

    def __init__(
        self,
        scout_account_id: str,
        application_name: str,
        base_url: Optional[str] = None,
    ):
        self.account_id = scout_account_id
        self.app_name = application_name

        # MCP server files location
        base_path = getattr(settings, 'base_local_path', Path('/tmp/modernizeit_output'))
        self.mcp_dir = Path(base_path) / "mcp_servers" / f"{scout_account_id}_{application_name}"

        # Default to local MCP server URL pattern
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            self.base_url = self._get_default_url()

        self._session: Optional[ClientSession] = None
        self._streams = None

    def server_exists(self) -> bool:
        """Check if the MCP server files have been generated."""
        server_file = self.mcp_dir / "server.py"
        return server_file.exists()

    def _get_default_url(self) -> str:
        """Get the default MCP server URL for this project."""
        mcp_base = getattr(settings, 'mcp_server_base_url', 'http://localhost:8080')
        return mcp_base

    async def __aenter__(self):
        """Start the MCP session."""
        try:
            sse_url = f"{self.base_url}/sse"

            # Use MCP SDK's SSE client
            self._streams = sse_client(sse_url)
            read_stream, write_stream = await self._streams.__aenter__()

            # Create and initialize session
            self._session = ClientSession(read_stream, write_stream)
            await self._session.__aenter__()

            # Initialize the MCP protocol
            await self._session.initialize()

            return self

        except Exception as e:
            raise MCPClientError(f"Failed to initialize MCP connection: {e}")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the MCP session."""
        if self._session:
            try:
                await self._session.__aexit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass
            self._session = None

        if self._streams:
            try:
                await self._streams.__aexit__(exc_type, exc_val, exc_tb)
            except Exception:
                pass
            self._streams = None

    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools from the MCP server."""
        if not self._session:
            raise MCPClientError("MCP client not initialized")

        result = await self._session.list_tools()

        # Convert to dict format
        tools = []
        for tool in result.tools:
            tools.append({
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema if hasattr(tool, 'inputSchema') else {"type": "object", "properties": {}}
            })
        return tools

    async def call_tool(self, name: str, arguments: Dict[str, Any] = None) -> Any:
        """
        Call a tool on the MCP server.

        Args:
            name: Tool name (e.g., "list_source_files")
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if not self._session:
            raise MCPClientError("MCP client not initialized")

        result = await self._session.call_tool(name, arguments or {})

        # Extract content from response
        if result.content and len(result.content) > 0:
            first_block = result.content[0]
            if hasattr(first_block, 'text'):
                try:
                    return json.loads(first_block.text)
                except json.JSONDecodeError:
                    return {"text": first_block.text}

        return {"content": str(result.content)}

    def get_tool_definitions_for_bedrock(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert MCP tool definitions to Bedrock format.

        Args:
            tools: List of MCP tool definitions

        Returns:
            List of tool definitions in Bedrock format
        """
        bedrock_tools = []

        for tool in tools:
            bedrock_tool = {
                "toolSpec": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "inputSchema": {
                        "json": tool.get("inputSchema", {"type": "object", "properties": {}})
                    }
                }
            }
            bedrock_tools.append(bedrock_tool)

        return bedrock_tools


# =============================================================================
# Convenience Functions
# =============================================================================

async def get_mcp_tools(
    scout_account_id: str,
    application_name: str,
    base_url: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get available tools from an MCP server."""
    async with MCPClient(scout_account_id, application_name, base_url) as client:
        return await client.list_tools()


async def call_mcp_tool(
    scout_account_id: str,
    application_name: str,
    tool_name: str,
    arguments: Dict[str, Any] = None,
    base_url: Optional[str] = None
) -> Any:
    """Call a tool on an MCP server."""
    async with MCPClient(scout_account_id, application_name, base_url) as client:
        return await client.call_tool(tool_name, arguments)
