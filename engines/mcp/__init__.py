"""
MCP Module - MCP server generation and client communication.

The MCP (Model Context Protocol) server provides tools for AI to access user's project data:
- Source files (COBOL, Java, copybooks, etc.)
- Analysis artifacts (JSON outputs from all engines)
- Project metadata

Architecture:
    1. MCPBuilder generates the MCP server (server.py) for a project
    2. MCPClient communicates with the MCP server via JSON-RPC/stdio
    3. Our API uses MCPClient to call MCP tools
    4. Claude Desktop can also use the same MCP server

Usage (Generate MCP Server):
    from engines.mcp import MCPBuilder, generate_mcp_for_project

    builder = MCPBuilder("EVH", "TestApp01")
    result = builder.generate()
    config = builder.get_claude_config()

Usage (Call MCP Tools from API):
    from engines.mcp import MCPClient

    async with MCPClient("0U812", "TestApp02") as client:
        tools = await client.list_tools()
        result = await client.call_tool("list_source_files", {"pattern": "*.cbl"})
"""

from .mcp_builder import (
    MCPBuilder,
    generate_mcp_for_project,
    get_mcp_status,
    get_claude_config,
)

from .mcp_client import (
    MCPClient,
    MCPClientError,
    get_mcp_tools,
    call_mcp_tool,
)

__all__ = [
    # Builder (generates MCP server)
    "MCPBuilder",
    "generate_mcp_for_project",
    "get_mcp_status",
    "get_claude_config",
    # Client (communicates with MCP server)
    "MCPClient",
    "MCPClientError",
    "get_mcp_tools",
    "call_mcp_tool",
]
