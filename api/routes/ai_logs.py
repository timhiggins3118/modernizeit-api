"""
AI API Routes

Provides endpoints for:
- AI chat/prompts for code analysis
- Monitoring AI/LLM requests and responses
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from engines.ai import BedrockAgent, get_ai_logger


router = APIRouter(prefix="/ai", tags=["ai"])


# ==================== AI Chat Endpoints ====================

class AIChatRequest(BaseModel):
    """Request model for AI chat."""
    prompt: str
    code: str
    context: Optional[Dict[str, Any]] = None
    purpose: str = "general"  # code_explain, generate_java, refactor, custom


class AIChatResponse(BaseModel):
    """Response model for AI chat."""
    response: str
    code: Optional[str] = None
    suggestions: Optional[List[str]] = None
    confidence: Optional[float] = None
    log_id: str
    duration_ms: int


# System prompts for different purposes
SYSTEM_PROMPTS = {
    "code_explain": """You are an expert code analyst. Explain the provided code clearly and concisely.
Focus on:
- What the code does (purpose)
- Key logic and flow
- Important variables and data structures
- Any potential issues or improvements

Format your response with markdown for readability.""",

    "generate_java": """You are an expert COBOL to Java migration specialist. Convert the provided COBOL code to modern, idiomatic Java.

Requirements:
- Use modern Java features (Java 17+)
- Follow Java naming conventions (camelCase for methods/variables, PascalCase for classes)
- Add JavaDoc comments explaining the original COBOL logic
- Include @ai-generated annotation with source reference
- Handle COBOL-specific constructs appropriately (COMP-3, REDEFINES, etc.)
- Return ONLY the Java code, no explanations.

Output format: Return only valid Java code that can be inserted directly into a file.""",

    "refactor": """You are an expert Java code reviewer. Analyze the provided code and suggest refactoring improvements.

Focus on:
- Code quality and maintainability
- Modern Java patterns and idioms
- Performance optimizations
- Security considerations
- SOLID principles

Format your response as a numbered list of specific, actionable suggestions.""",

    "custom": """You are an expert software engineer assistant. Answer the user's question about the provided code.
Be specific, accurate, and helpful. Use markdown formatting for readability."""
}


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(request: AIChatRequest) -> AIChatResponse:
    """
    Send a prompt to AI for code analysis, generation, or custom queries.

    Purposes:
    - code_explain: Explain what the code does
    - generate_java: Convert COBOL to Java
    - refactor: Suggest refactoring improvements
    - custom: Custom user prompt
    """
    start_time = time.time()

    # Get system prompt for purpose
    system_prompt = SYSTEM_PROMPTS.get(request.purpose, SYSTEM_PROMPTS["custom"])

    # Build the full prompt
    context_info = ""
    if request.context:
        if request.context.get("file"):
            context_info += f"\nFile: {request.context['file']}"
        if request.context.get("language"):
            context_info += f"\nLanguage: {request.context['language']}"
        if request.context.get("section"):
            context_info += f"\nSection: {request.context['section']}"

    full_prompt = f"""{request.prompt}
{context_info}

Code:
```
{request.code}
```"""

    try:
        # Create agent with purpose for logging
        agent = BedrockAgent.create(
            purpose=request.purpose,
            max_tokens=8192 if request.purpose == "generate_java" else 4096
        )

        # Invoke with system prompt
        response_text = agent.invoke(
            prompt=full_prompt,
            system=system_prompt,
            purpose=request.purpose
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Parse response based on purpose
        result = AIChatResponse(
            response=response_text,
            log_id="",  # Will be filled from logger
            duration_ms=duration_ms
        )

        # For generate_java, extract clean code (strip markdown blocks)
        if request.purpose == "generate_java":
            clean_code = response_text.strip()
            # Remove markdown code blocks if present
            if clean_code.startswith('```'):
                # Find the end of the first line (e.g., ```java or ```)
                first_newline = clean_code.find('\n')
                if first_newline > 0:
                    clean_code = clean_code[first_newline + 1:]
                # Remove closing ```
                if clean_code.endswith('```'):
                    clean_code = clean_code[:-3].rstrip()
            result.code = clean_code
            result.confidence = 0.85  # Default confidence

        # For refactor, try to extract suggestions
        if request.purpose == "refactor":
            # Parse numbered suggestions from response
            lines = response_text.split('\n')
            suggestions = []
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                    # Clean up the suggestion
                    suggestion = line.lstrip('0123456789.-•) ').strip()
                    if suggestion:
                        suggestions.append(suggestion)
            if suggestions:
                result.suggestions = suggestions[:10]  # Limit to 10

        # Get the log_id from the most recent log
        logger = get_ai_logger()
        logs = logger.get_logs(limit=1)
        if logs:
            result.log_id = logs[0]['id']

        return result

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        raise HTTPException(
            status_code=500,
            detail=f"AI request failed: {str(e)}"
        )


class AILogEntry(BaseModel):
    """Response model for a single AI log entry."""
    id: str
    timestamp: str
    model: str
    purpose: Optional[str]
    prompt_preview: str
    prompt_length: int
    response_preview: Optional[str]
    response_length: int
    duration_ms: int
    success: bool
    error: Optional[str]
    tokens_input: Optional[int]
    tokens_output: Optional[int]
    temperature: Optional[float]
    max_tokens: Optional[int]


class AILogDetail(BaseModel):
    """Response model for detailed AI log entry with full prompt/response."""
    id: str
    timestamp: str
    model: str
    purpose: Optional[str]
    prompt_preview: str
    prompt_length: int
    response_preview: Optional[str]
    response_length: int
    duration_ms: int
    success: bool
    error: Optional[str]
    tokens_input: Optional[int]
    tokens_output: Optional[int]
    temperature: Optional[float]
    max_tokens: Optional[int]
    full_prompt: Optional[str] = None
    full_response: Optional[str] = None


class AILogListResponse(BaseModel):
    """Response model for AI log list."""
    logs: List[AILogEntry]
    total: int


class AIStatsResponse(BaseModel):
    """Response model for AI usage statistics."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    avg_duration_ms: float
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    by_model: List[Dict[str, Any]]
    by_purpose: List[Dict[str, Any]]
    top_errors: List[Dict[str, Any]]


@router.get("/logs", response_model=AILogListResponse)
async def get_ai_logs(
    limit: int = Query(default=100, ge=1, le=500, description="Maximum logs to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    model: Optional[str] = Query(default=None, description="Filter by model"),
    purpose: Optional[str] = Query(default=None, description="Filter by purpose"),
    success_only: Optional[bool] = Query(default=None, description="Filter by success status"),
    hours: Optional[int] = Query(default=None, description="Only logs from last N hours"),
) -> AILogListResponse:
    """
    Get AI request/response logs.

    Returns logs sorted by timestamp (newest first).
    """
    logger = get_ai_logger()

    since = None
    if hours:
        since = datetime.utcnow() - timedelta(hours=hours)

    logs = logger.get_logs(
        limit=limit,
        offset=offset,
        model=model,
        purpose=purpose,
        success_only=success_only,
        since=since,
    )

    entries = [
        AILogEntry(
            id=log['id'],
            timestamp=log['timestamp'],
            model=log['model'],
            purpose=log.get('purpose'),
            prompt_preview=log.get('prompt_preview', ''),
            prompt_length=log.get('prompt_length', 0),
            response_preview=log.get('response_preview'),
            response_length=log.get('response_length', 0),
            duration_ms=log.get('duration_ms', 0),
            success=bool(log.get('success')),
            error=log.get('error'),
            tokens_input=log.get('tokens_input'),
            tokens_output=log.get('tokens_output'),
            temperature=log.get('temperature'),
            max_tokens=log.get('max_tokens'),
        )
        for log in logs
    ]

    return AILogListResponse(logs=entries, total=len(entries))


@router.get("/logs/{log_id}", response_model=AILogDetail)
async def get_ai_log_detail(log_id: str) -> AILogDetail:
    """
    Get detailed AI log entry including full prompt and response.
    """
    logger = get_ai_logger()
    log = logger.get_log_detail(log_id)

    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Log entry {log_id} not found")

    return AILogDetail(
        id=log['id'],
        timestamp=log['timestamp'],
        model=log['model'],
        purpose=log.get('purpose'),
        prompt_preview=log.get('prompt_preview', ''),
        prompt_length=log.get('prompt_length', 0),
        response_preview=log.get('response_preview'),
        response_length=log.get('response_length', 0),
        duration_ms=log.get('duration_ms', 0),
        success=bool(log.get('success')),
        error=log.get('error'),
        tokens_input=log.get('tokens_input'),
        tokens_output=log.get('tokens_output'),
        temperature=log.get('temperature'),
        max_tokens=log.get('max_tokens'),
        full_prompt=log.get('full_prompt'),
        full_response=log.get('full_response'),
    )


@router.get("/stats", response_model=AIStatsResponse)
async def get_ai_stats(
    hours: Optional[int] = Query(default=24, description="Stats from last N hours (default 24)"),
) -> AIStatsResponse:
    """
    Get aggregated AI usage statistics.
    """
    logger = get_ai_logger()

    since = None
    if hours:
        since = datetime.utcnow() - timedelta(hours=hours)

    stats = logger.get_stats(since=since)

    return AIStatsResponse(
        total_requests=stats['total_requests'],
        successful_requests=stats['successful_requests'],
        failed_requests=stats['failed_requests'],
        success_rate=stats['success_rate'],
        avg_duration_ms=stats['avg_duration_ms'],
        total_input_tokens=stats['total_input_tokens'],
        total_output_tokens=stats['total_output_tokens'],
        total_tokens=stats['total_tokens'],
        by_model=stats['by_model'],
        by_purpose=stats['by_purpose'],
        top_errors=stats['top_errors'],
    )


@router.delete("/logs/cleanup")
async def cleanup_ai_logs(
    days: int = Query(default=30, ge=1, le=365, description="Delete logs older than N days"),
) -> Dict[str, Any]:
    """
    Clean up old AI logs.

    Deletes logs older than the specified number of days.
    """
    logger = get_ai_logger()
    deleted = logger.cleanup_old_logs(days=days)

    return {
        "deleted_count": deleted,
        "retention_days": days,
        "message": f"Deleted {deleted} log entries older than {days} days"
    }
