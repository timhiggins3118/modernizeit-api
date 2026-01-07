"""
AI Module - Unified AI/LLM Interface

This module provides a single, unified interface for all AI interactions.
All analyzers should use BedrockAgent instead of direct boto3 calls.

Usage:
    from engines.ai import BedrockAgent, invoke, invoke_json

    # Full control
    agent = BedrockAgent(temperature=0.3, max_workers=4)
    response = agent.invoke("Your prompt here")

    # JSON responses
    data = agent.invoke_json("Return JSON...")

    # Batch processing
    results = agent.invoke_batch(
        items=files,
        prompt_fn=lambda f: f"Analyze {f}",
        item_id_fn=lambda f: f.name
    )

    # Quick one-off calls
    response = invoke("Quick question")
    data = invoke_json("Return JSON...")

    # AI Logging
    from engines.ai import get_ai_logger
    logger = get_ai_logger()
    stats = logger.get_stats()
    logs = logger.get_logs(limit=100)
"""

from .bedrock_agent import (
    BedrockAgent,
    BatchResult,
    invoke,
    invoke_json,
)

from .ai_logger import (
    AILogger,
    get_logger as get_ai_logger,
    log_request,
)

__all__ = [
    'BedrockAgent',
    'BatchResult',
    'invoke',
    'invoke_json',
    'AILogger',
    'get_ai_logger',
    'log_request',
]
