"""
MCP Chat API

Provides AI chat that uses MCP server tools.
Users can ask questions about their COBOL files, Java files, reports, etc.
AI uses the MCP server's tools to access the user's project data.
"""

import json
import time
from typing import List, Optional

import boto3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.settings import settings
from engines.mcp.mcp_client import MCPClient, MCPClientError
from engines.ai.ai_logger import log_request

# Import server management for auto-starting (Docker-based)
from api.routes.mcp_config import (
    _get_container_name,
    _is_container_running,
    _get_port_for_server,
    start_mcp_server,
    StartServerRequest,
)

router = APIRouter(prefix="/ai", tags=["ai", "mcp"])


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


class MCPChatRequest(BaseModel):
    """Request for MCP chat."""
    message: str
    scout_account_id: str
    application_name: str
    history: Optional[List[ChatMessage]] = None


class MCPChatResponse(BaseModel):
    """Response from MCP chat."""
    response: str
    tools_used: List[str] = []
    duration_ms: int = 0


# Bedrock model for chat
CHAT_MODEL = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 10  # Prevent infinite loops


def get_bedrock_client():
    """Get Bedrock runtime client."""
    region = getattr(settings, 'bedrock_region', 'us-east-1')
    return boto3.client('bedrock-runtime', region_name=region)


def build_system_prompt(account_id: str, app_name: str) -> str:
    """Build the system prompt for MCP chat."""
    return f"""You are an AI assistant helping users understand their legacy code transformation project.

Project: {account_id} / {app_name}

You have access to tools that let you:
- List and read source files (COBOL, Java, copybooks, etc.)
- Search through source code
- Read analysis artifacts (dependency graphs, metrics, etc.)
- Get project summaries

When answering questions:
1. Use the tools to find relevant information in the user's project
2. Be specific - cite file names, line numbers, and actual code when relevant
3. If you can't find something, say so rather than guessing
4. Focus on the user's actual code and data, not general knowledge

The user can only see their own project data. All file paths are relative to their project."""


async def _ensure_server_running(account_id: str, app_name: str) -> str:
    """
    Ensure the MCP server Docker container is running and return its URL.

    Auto-starts the container if not running.
    """
    container_name = _get_container_name(account_id, app_name)
    port = _get_port_for_server(account_id, app_name)

    # Check if already running
    if _is_container_running(container_name):
        return f"http://localhost:{port}"

    # Start the Docker container
    result = await start_mcp_server(StartServerRequest(
        scout_account_id=account_id,
        application_name=app_name
    ))

    return result.get("url", f"http://localhost:{port}")


@router.post("/mcp-chat", response_model=MCPChatResponse)
async def mcp_chat(request: MCPChatRequest):
    """
    Chat with AI about project data.

    AI uses the MCP server's tools to answer questions about the user's project.
    Auto-starts the MCP server if not running (local development).
    """
    start_time = time.time()

    # Check for mock mode
    if getattr(settings, 'bedrock_mode', 'real') == 'mock':
        return MCPChatResponse(
            response=f"[MOCK MODE] I would answer your question about {request.application_name} here.",
            tools_used=[],
            duration_ms=100
        )

    try:
        # Create client to check if server files exist
        mcp_client = MCPClient(request.scout_account_id, request.application_name)

        if not mcp_client.server_exists():
            raise HTTPException(
                status_code=400,
                detail="MCP server not found. Please generate the MCP server first."
            )

        # Ensure server is running and get URL
        server_url = await _ensure_server_running(
            request.scout_account_id,
            request.application_name
        )

        # Create client with the running server's URL
        mcp_client = MCPClient(
            request.scout_account_id,
            request.application_name,
            base_url=server_url
        )

        async with mcp_client:
            # Get tools from MCP server
            mcp_tools = await mcp_client.list_tools()
            tool_definitions = mcp_client.get_tool_definitions_for_bedrock(mcp_tools)

            # Build conversation messages
            messages = []

            # Add history if provided
            if request.history:
                for msg in request.history:
                    messages.append({
                        "role": msg.role,
                        "content": [{"text": msg.content}]
                    })

            # Add current message
            messages.append({
                "role": "user",
                "content": [{"text": request.message}]
            })

            # Get Bedrock client
            client = get_bedrock_client()

            # System prompt
            system_prompt = build_system_prompt(request.scout_account_id, request.application_name)

            # Tool use loop
            tools_used = []
            iterations = 0

            while iterations < MAX_TOOL_ITERATIONS:
                iterations += 1

                # Call Bedrock converse API
                response = client.converse(
                    modelId=CHAT_MODEL,
                    messages=messages,
                    system=[{"text": system_prompt}],
                    toolConfig={"tools": tool_definitions},
                    inferenceConfig={
                        "maxTokens": MAX_TOKENS,
                        "temperature": 0.3
                    }
                )

                # Check stop reason
                stop_reason = response.get("stopReason", "")

                # Extract response content
                output_message = response.get("output", {}).get("message", {})
                content_blocks = output_message.get("content", [])

                # Check if we need to handle tool use
                if stop_reason == "tool_use":
                    # Add assistant message to conversation
                    messages.append(output_message)

                    # Process tool uses
                    tool_results = []
                    for block in content_blocks:
                        if "toolUse" in block:
                            tool_use = block["toolUse"]
                            tool_name = tool_use["name"]
                            tool_input = tool_use.get("input", {})
                            tool_use_id = tool_use["toolUseId"]

                            # Execute the tool via MCP server
                            result = await mcp_client.call_tool(tool_name, tool_input)
                            tools_used.append(tool_name)

                            # Add to tool results
                            tool_results.append({
                                "toolUseId": tool_use_id,
                                "content": [{"json": result}]
                            })

                    # Add tool results to conversation
                    messages.append({
                        "role": "user",
                        "content": [{"toolResult": tr} for tr in tool_results]
                    })

                else:
                    # No more tool use - extract final response
                    final_response = ""
                    for block in content_blocks:
                        if "text" in block:
                            final_response += block["text"]

                    duration_ms = int((time.time() - start_time) * 1000)

                    # Log the request
                    try:
                        log_request(
                            model=CHAT_MODEL,
                            prompt=request.message,
                            response=final_response,
                            duration_ms=duration_ms,
                            success=True,
                            purpose="mcp_chat",
                            metadata={
                                "account_id": request.scout_account_id,
                                "app_name": request.application_name,
                                "tools_used": tools_used,
                                "iterations": iterations
                            }
                        )
                    except Exception:
                        pass

                    return MCPChatResponse(
                        response=final_response,
                        tools_used=tools_used,
                        duration_ms=duration_ms
                    )

            # Max iterations reached
            raise HTTPException(
                status_code=500,
                detail="Max tool iterations reached"
            )

    except MCPClientError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)

        # Log the error
        try:
            log_request(
                model=CHAT_MODEL,
                prompt=request.message,
                response=None,
                duration_ms=duration_ms,
                success=False,
                error=str(e),
                purpose="mcp_chat",
                metadata={
                    "account_id": request.scout_account_id,
                    "app_name": request.application_name
                }
            )
        except Exception:
            pass

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mcp-tools/{scout_account_id}/{application_name}")
async def get_mcp_tools(scout_account_id: str, application_name: str):
    """
    Get available MCP tools for a project.

    Returns tool definitions from the MCP server.
    Auto-starts the MCP server if not running (local development).
    """
    try:
        # Check if server files exist
        mcp_client = MCPClient(scout_account_id, application_name)

        if not mcp_client.server_exists():
            raise HTTPException(
                status_code=400,
                detail="MCP server not found. Please generate the MCP server first."
            )

        # Ensure server is running and get URL
        server_url = await _ensure_server_running(scout_account_id, application_name)

        # Create client with the running server's URL
        mcp_client = MCPClient(scout_account_id, application_name, base_url=server_url)

        async with mcp_client:
            tools = await mcp_client.list_tools()

            return {
                "account_id": scout_account_id,
                "application_name": application_name,
                "tools": [
                    {
                        "name": t.get("name", ""),
                        "description": t.get("description", "")
                    }
                    for t in tools
                ]
            }

    except MCPClientError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
