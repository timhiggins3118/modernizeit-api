"""
AI Flow Endpoint - Handle AI requests from workflow nodes.

Supports multiple context sources:
- flow_input: Use code/data passed from upstream nodes
- specific_files: Load files matching a glob pattern
- project_files: Load all project source files and artifacts
- mcp_tools: Use MCP server tools for rich context (requires MCP running)

Each AI node type (transform, explain, review) has specialized prompts and output formats.
"""

import glob
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.settings import settings
from engines.ai import BedrockAgent

router = APIRouter(prefix="/ai", tags=["ai", "flow"])


# =============================================================================
# Request/Response Models
# =============================================================================

class AIFlowRequest(BaseModel):
    """Request for AI flow node execution."""
    # Required
    scout_account_id: str
    application_name: str
    node_type: str  # ai-transform, ai-explain, ai-review

    # Context source
    context_source: str = "flow_input"  # flow_input, specific_files, project_files, mcp_tools
    file_pattern: Optional[str] = None  # For specific_files

    # Flow input (from upstream nodes)
    code: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    # AI settings
    provider: str = "bedrock"
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.2
    max_tokens: int = 4096

    # Node-specific settings
    config: Optional[Dict[str, Any]] = None


class AIFlowResponse(BaseModel):
    """Response from AI flow node execution."""
    success: bool
    node_type: str
    output: Any  # Type depends on node_type
    files_analyzed: List[str] = []
    duration_ms: int
    context_source: str
    error: Optional[str] = None


# =============================================================================
# System Prompts for Each Node Type
# =============================================================================

SYSTEM_PROMPTS = {
    "ai-transform": """You are an expert code transformation assistant. Your task is to transform code to a target language or style while preserving functionality.

Guidelines:
- Maintain the exact same behavior and logic
- Use idiomatic patterns for the target language
- Add appropriate comments explaining complex transformations
- Handle edge cases properly
- Output ONLY the transformed code, no explanations""",

    "ai-explain": """You are an expert code documentation specialist. Your task is to explain code clearly and thoroughly.

Guidelines:
- Explain the purpose and functionality
- Document inputs, outputs, and side effects
- Describe the algorithm or approach used
- Note any dependencies or requirements
- Highlight potential issues or areas of concern
- Tailor explanations to the target audience""",

    "ai-review": """You are an expert code reviewer. Your task is to analyze code and provide actionable feedback.

Return your review as a JSON object with this structure:
{
  "summary": "Brief overall assessment",
  "findings": [
    {
      "severity": "error|warning|info",
      "category": "security|performance|maintainability|bugs|style",
      "location": "file:line or description",
      "issue": "Description of the issue",
      "suggestion": "How to fix it",
      "rationale": "Why this matters"
    }
  ],
  "metrics": {
    "overall_quality": 1-10,
    "security_score": 1-10,
    "maintainability_score": 1-10
  }
}"""
}


# =============================================================================
# Context Loading Functions
# =============================================================================

def load_project_files(account_id: str, app_name: str, pattern: Optional[str] = None) -> Dict[str, str]:
    """
    Load source files from a project.

    Args:
        account_id: Scout account ID
        app_name: Application name
        pattern: Optional glob pattern to filter files

    Returns:
        Dict mapping file paths to contents
    """
    source_path = Path(settings.base_local_path) / account_id / app_name / "source"
    files = {}

    if not source_path.exists():
        return files

    # Determine which files to load
    if pattern:
        patterns = [p.strip() for p in pattern.split(",")]
        for p in patterns:
            for file_path in source_path.glob(f"**/{p}"):
                if file_path.is_file():
                    try:
                        files[str(file_path.relative_to(source_path))] = file_path.read_text()
                    except Exception:
                        pass
    else:
        # Load common source file types
        extensions = [".cbl", ".cpy", ".java", ".py", ".ts", ".js", ".pli", ".rpg"]
        for ext in extensions:
            for file_path in source_path.glob(f"**/*{ext}"):
                if file_path.is_file():
                    try:
                        files[str(file_path.relative_to(source_path))] = file_path.read_text()
                    except Exception:
                        pass

    return files


def load_project_artifacts(account_id: str, app_name: str) -> Dict[str, Any]:
    """
    Load analysis artifacts from a project.

    Returns:
        Dict with artifact summaries
    """
    artifacts_path = Path(settings.base_local_path) / account_id / app_name / "artifacts"
    artifacts = {}

    if not artifacts_path.exists():
        return artifacts

    # Load JSON artifacts
    for json_file in artifacts_path.glob("**/*.json"):
        try:
            relative_path = str(json_file.relative_to(artifacts_path))
            data = json.loads(json_file.read_text())
            # Store summary info, not full content
            if isinstance(data, dict):
                artifacts[relative_path] = {
                    "keys": list(data.keys())[:10],
                    "type": data.get("type", "unknown")
                }
            elif isinstance(data, list):
                artifacts[relative_path] = {
                    "count": len(data),
                    "type": "list"
                }
        except Exception:
            pass

    return artifacts


def build_context_prompt(
    context_source: str,
    code: Optional[str],
    context: Optional[Dict],
    files: Dict[str, str],
    artifacts: Dict[str, Any]
) -> str:
    """Build the context section of the prompt based on context source."""

    parts = []

    if context_source == "flow_input" and code:
        parts.append(f"## Code to Analyze\n```\n{code}\n```")
        if context:
            parts.append(f"\n## Additional Context\n{json.dumps(context, indent=2)}")

    elif context_source in ["specific_files", "project_files"]:
        if files:
            parts.append("## Source Files")
            for path, content in list(files.items())[:20]:  # Limit to 20 files
                # Truncate large files
                if len(content) > 10000:
                    content = content[:10000] + "\n... (truncated)"
                parts.append(f"\n### {path}\n```\n{content}\n```")

        if artifacts:
            parts.append("\n## Available Artifacts")
            for path, info in list(artifacts.items())[:10]:
                parts.append(f"- {path}: {info}")

    return "\n".join(parts)


# =============================================================================
# AI Execution Functions
# =============================================================================

def execute_transform(prompt: str, config: Dict[str, Any], agent: BedrockAgent) -> Dict[str, Any]:
    """Execute AI Transform node."""
    target_lang = config.get("targetLanguage", "java")
    user_prompt = config.get("prompt", "Transform this code to modern, idiomatic style.")

    full_prompt = f"""{user_prompt}

Target Language: {target_lang}

{prompt}

Output ONLY the transformed code, no explanations or markdown."""

    response = agent.invoke(
        prompt=full_prompt,
        system=SYSTEM_PROMPTS["ai-transform"],
        purpose="ai-transform"
    )

    return {
        "transformed_code": response,
        "target_language": target_lang
    }


def execute_explain(prompt: str, config: Dict[str, Any], agent: BedrockAgent) -> Dict[str, Any]:
    """Execute AI Explain node."""
    output_format = config.get("outputFormat", "markdown")
    detail_level = config.get("detailLevel", "standard")
    audience = config.get("audienceLevel", "developer")
    include_examples = config.get("includeExamples", True)

    full_prompt = f"""Analyze and explain the following code.

Output Format: {output_format}
Detail Level: {detail_level}
Target Audience: {audience}
Include Examples: {include_examples}

{prompt}"""

    response = agent.invoke(
        prompt=full_prompt,
        system=SYSTEM_PROMPTS["ai-explain"],
        purpose="ai-explain"
    )

    return {
        "documentation": response,
        "format": output_format,
        "detail_level": detail_level
    }


def execute_review(prompt: str, config: Dict[str, Any], agent: BedrockAgent) -> Dict[str, Any]:
    """Execute AI Review node."""
    review_focus = config.get("reviewFocus", "all")
    min_severity = config.get("severity", "info")
    suggest_fixes = config.get("suggestFixes", True)
    include_rationale = config.get("includeRationale", True)

    full_prompt = f"""Review the following code.

Focus: {review_focus}
Minimum Severity: {min_severity}
Suggest Fixes: {suggest_fixes}
Include Rationale: {include_rationale}

{prompt}

Return your review as a valid JSON object."""

    response = agent.invoke(
        prompt=full_prompt,
        system=SYSTEM_PROMPTS["ai-review"],
        purpose="ai-review"
    )

    # Try to parse JSON response
    try:
        # Handle markdown code blocks
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0]
        elif "```" in response:
            response = response.split("```")[1].split("```")[0]

        review_data = json.loads(response.strip())
    except json.JSONDecodeError:
        review_data = {
            "summary": "Review completed",
            "raw_response": response
        }

    return {
        "review": review_data,
        "focus": review_focus
    }


# =============================================================================
# Main Endpoint
# =============================================================================

@router.post("/flow", response_model=AIFlowResponse)
async def execute_ai_flow_node(request: AIFlowRequest) -> AIFlowResponse:
    """
    Execute an AI flow node.

    Handles ai-transform, ai-explain, and ai-review nodes with various context sources.
    """
    start_time = time.time()
    files_analyzed = []

    try:
        # Load context based on source
        files = {}
        artifacts = {}

        if request.context_source == "specific_files":
            files = load_project_files(
                request.scout_account_id,
                request.application_name,
                request.file_pattern
            )
            files_analyzed = list(files.keys())

        elif request.context_source == "project_files":
            files = load_project_files(
                request.scout_account_id,
                request.application_name
            )
            artifacts = load_project_artifacts(
                request.scout_account_id,
                request.application_name
            )
            files_analyzed = list(files.keys())

        elif request.context_source == "mcp_tools":
            # For MCP tools, we'll include a note about available tools
            # The actual MCP execution happens through /ai/mcp-chat
            raise HTTPException(
                status_code=400,
                detail="MCP Tools context requires using the /ai/mcp-chat endpoint. Use ai-chat node for MCP integration."
            )

        # Build context prompt
        context_prompt = build_context_prompt(
            request.context_source,
            request.code,
            request.context,
            files,
            artifacts
        )

        if not context_prompt.strip():
            raise HTTPException(
                status_code=400,
                detail="No code or files provided. Connect an upstream node or change context source."
            )

        # Create AI agent
        agent = BedrockAgent.create(
            purpose=request.node_type,
            model_id=request.model if request.model else None,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        # Execute based on node type
        config = request.config or {}

        if request.node_type == "ai-transform":
            output = execute_transform(context_prompt, config, agent)
        elif request.node_type == "ai-explain":
            output = execute_explain(context_prompt, config, agent)
        elif request.node_type == "ai-review":
            output = execute_review(context_prompt, config, agent)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown node type: {request.node_type}"
            )

        duration_ms = int((time.time() - start_time) * 1000)

        return AIFlowResponse(
            success=True,
            node_type=request.node_type,
            output=output,
            files_analyzed=files_analyzed,
            duration_ms=duration_ms,
            context_source=request.context_source
        )

    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return AIFlowResponse(
            success=False,
            node_type=request.node_type,
            output=None,
            files_analyzed=files_analyzed,
            duration_ms=duration_ms,
            context_source=request.context_source,
            error=str(e)
        )


@router.get("/flow/context-check/{scout_account_id}/{application_name}")
async def check_context_availability(scout_account_id: str, application_name: str):
    """
    Check what context sources are available for a project.

    Returns availability of:
    - source files
    - artifacts
    - MCP server status
    """
    from api.routes.mcp_config import _is_container_running, _get_container_name

    source_path = Path(settings.base_local_path) / scout_account_id / application_name / "source"
    artifacts_path = Path(settings.base_local_path) / scout_account_id / application_name / "artifacts"

    # Count files
    source_files = list(source_path.glob("**/*")) if source_path.exists() else []
    source_count = len([f for f in source_files if f.is_file()])

    artifact_files = list(artifacts_path.glob("**/*.json")) if artifacts_path.exists() else []
    artifact_count = len(artifact_files)

    # Check MCP
    container_name = _get_container_name(scout_account_id, application_name)
    mcp_running = _is_container_running(container_name)

    return {
        "account_id": scout_account_id,
        "app_name": application_name,
        "context_sources": {
            "flow_input": {
                "available": True,
                "description": "Always available - uses data from upstream nodes"
            },
            "specific_files": {
                "available": source_count > 0,
                "file_count": source_count,
                "description": "Load specific files by pattern"
            },
            "project_files": {
                "available": source_count > 0,
                "file_count": source_count,
                "artifact_count": artifact_count,
                "description": "Load all project files and artifacts"
            },
            "mcp_tools": {
                "available": mcp_running,
                "container_running": mcp_running,
                "description": "Use MCP tools for rich exploration (requires MCP server)"
            }
        }
    }
