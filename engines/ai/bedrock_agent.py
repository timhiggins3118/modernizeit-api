"""
Unified Bedrock Agent Class

Single location for ALL AI/LLM interactions in the codebase.
All analyzers should use this class instead of direct boto3 calls.

Features:
- Single and batch/parallel execution
- Consistent error handling with retries
- JSON response parsing (handles markdown wrapping)
- Mock mode for testing
- Configurable model, temperature, max_tokens
- Progress logging

Usage:
    # Single call
    agent = BedrockAgent()
    response = agent.invoke("Analyze this code...")

    # With JSON parsing
    data = agent.invoke_json("Return JSON: {...}")

    # Batch/parallel processing
    results = agent.invoke_batch(
        items=files,
        prompt_fn=lambda f: f"Analyze {f.name}...",
        item_id_fn=lambda f: f.name
    )
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar

import boto3
from botocore.exceptions import ClientError

from config.settings import settings
from engines.ai.ai_logger import get_logger, log_request


T = TypeVar('T')


@dataclass
class BatchResult:
    """Result of a single item in batch processing."""
    item_id: str
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: int = 0


class BedrockAgent:
    """
    Unified Bedrock/Claude agent for all AI interactions.

    This is the ONLY class that should make Bedrock API calls.
    All analyzers (discovery, data_analysis, code_refactor, etc.)
    should use this class.
    """

    # Default model - Claude 3.5 Sonnet (latest)
    DEFAULT_MODEL = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_TEMPERATURE = 0.2
    DEFAULT_REGION = "us-east-1"

    def __init__(
        self,
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        region: Optional[str] = None,
        max_workers: int = 4,
        mock_mode: Optional[bool] = None,
        log_fn: Optional[Callable[[str], None]] = None,
        purpose: Optional[str] = None,
        enable_logging: bool = True
    ):
        """
        Initialize Bedrock agent.

        Args:
            model: Bedrock model ID (default: Claude 3.5 Sonnet)
            max_tokens: Maximum response tokens (default: 4096)
            temperature: Sampling temperature 0-1 (default: 0.2 for consistency)
            region: AWS region (default: us-east-1)
            max_workers: Max concurrent calls for batch processing (default: 4)
            mock_mode: If True, return mock responses (for testing)
            log_fn: Logging function (default: print)
            purpose: Purpose/category for logging (e.g., "discovery", "refactor")
            enable_logging: If True, log requests to AILogger (default: True)
        """
        self.model = model or self.DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.region = region or getattr(settings, 'bedrock_region', self.DEFAULT_REGION)
        self.max_workers = max_workers
        self.log_fn = log_fn or print
        self.purpose = purpose
        self.enable_logging = enable_logging

        # Mock mode from settings or parameter
        if mock_mode is not None:
            self.mock_mode = mock_mode
        else:
            self.mock_mode = getattr(settings, 'bedrock_mode', 'real') == 'mock'

        self._client = None

    # ==================== Core Methods ====================

    def invoke(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system: Optional[str] = None,
        purpose: Optional[str] = None
    ) -> str:
        """
        Invoke Bedrock model with a prompt.

        Args:
            prompt: The user prompt
            max_tokens: Override default max tokens
            temperature: Override default temperature
            system: Optional system prompt
            purpose: Override default purpose for this call

        Returns:
            Response text from model
        """
        start_time = time.time()
        actual_max_tokens = max_tokens or self.max_tokens
        actual_temperature = temperature if temperature is not None else self.temperature
        request_purpose = purpose or self.purpose

        response_text = None
        error_msg = None
        success = False
        tokens_input = None
        tokens_output = None

        try:
            if self.mock_mode:
                response_text = self._mock_response(prompt)
                success = True
                return response_text

            client = self._get_client()

            messages = [{"role": "user", "content": prompt}]

            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": actual_max_tokens,
                "temperature": actual_temperature,
                "messages": messages
            }

            if system:
                body["system"] = system

            response = client.invoke_model(
                modelId=self.model,
                body=json.dumps(body),
                contentType='application/json',
                accept='application/json'
            )

            response_body = json.loads(response['body'].read())
            response_text = response_body['content'][0]['text']

            # Extract token usage if available
            usage = response_body.get('usage', {})
            tokens_input = usage.get('input_tokens')
            tokens_output = usage.get('output_tokens')

            success = True
            return response_text

        except Exception as e:
            error_msg = str(e)
            raise

        finally:
            # Log the request/response
            if self.enable_logging:
                duration_ms = int((time.time() - start_time) * 1000)
                try:
                    log_request(
                        model=self.model,
                        prompt=prompt,
                        response=response_text,
                        duration_ms=duration_ms,
                        success=success,
                        error=error_msg,
                        purpose=request_purpose,
                        temperature=actual_temperature,
                        max_tokens=actual_max_tokens,
                        tokens_input=tokens_input,
                        tokens_output=tokens_output,
                        metadata={"mock_mode": self.mock_mode}
                    )
                except Exception as log_error:
                    self.log_fn(f"[BedrockAgent] Logging failed: {log_error}")

    def invoke_json(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        fallback: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Invoke model and parse JSON response.

        Handles common issues like markdown code blocks.

        Args:
            prompt: The user prompt (should request JSON response)
            max_tokens: Override default max tokens
            temperature: Override default temperature (lower is better for JSON)
            fallback: Return this if parsing fails (default: None)

        Returns:
            Parsed JSON dict, or fallback if parsing fails
        """
        try:
            response = self.invoke(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature or 0.1  # Lower temp for JSON
            )
            return self._parse_json(response)
        except Exception as e:
            self.log_fn(f"[BedrockAgent] invoke_json failed: {e}")
            return fallback

    def invoke_with_retry(
        self,
        prompt: str,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        **kwargs
    ) -> str:
        """
        Invoke with automatic retry on throttling/transient errors.

        Args:
            prompt: The user prompt
            max_retries: Maximum retry attempts (default: 3)
            retry_delay: Initial delay between retries in seconds (doubles each retry)
            **kwargs: Additional args passed to invoke()

        Returns:
            Response text from model
        """
        last_error = None
        delay = retry_delay

        for attempt in range(max_retries + 1):
            try:
                return self.invoke(prompt, **kwargs)
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code in ('ThrottlingException', 'ServiceUnavailableException'):
                    last_error = e
                    if attempt < max_retries:
                        self.log_fn(f"[BedrockAgent] Retry {attempt + 1}/{max_retries} after {delay}s: {error_code}")
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                        continue
                raise
            except Exception as e:
                raise

        raise last_error

    # ==================== Batch Processing ====================

    def invoke_batch(
        self,
        items: List[T],
        prompt_fn: Callable[[T], str],
        item_id_fn: Callable[[T], str],
        parse_json: bool = False,
        progress_prefix: str = "[AI]",
        max_workers: Optional[int] = None
    ) -> List[BatchResult]:
        """
        Process multiple items in parallel.

        Args:
            items: List of items to process
            prompt_fn: Function that takes item and returns prompt string
            item_id_fn: Function that takes item and returns ID for logging
            parse_json: If True, parse responses as JSON
            progress_prefix: Prefix for progress log messages
            max_workers: Override default max workers

        Returns:
            List of BatchResult for each item
        """
        total = len(items)
        if total == 0:
            return []

        workers = max_workers or self.max_workers
        results: List[BatchResult] = []
        completed = 0

        self.log_fn(f"{progress_prefix} Processing {total} items with {workers} workers")
        start_time = time.time()

        def process_item(item: T) -> BatchResult:
            item_id = item_id_fn(item)
            item_start = time.time()

            try:
                prompt = prompt_fn(item)

                if parse_json:
                    result = self.invoke_json(prompt)
                else:
                    result = self.invoke(prompt)

                duration_ms = int((time.time() - item_start) * 1000)
                return BatchResult(
                    item_id=item_id,
                    success=True,
                    result=result,
                    duration_ms=duration_ms
                )
            except Exception as e:
                duration_ms = int((time.time() - item_start) * 1000)
                return BatchResult(
                    item_id=item_id,
                    success=False,
                    error=str(e),
                    duration_ms=duration_ms
                )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_item = {
                executor.submit(process_item, item): item
                for item in items
            }

            for future in as_completed(future_to_item):
                result = future.result()
                results.append(result)
                completed += 1

                status = "OK" if result.success else f"FAILED: {result.error}"
                self.log_fn(f"{progress_prefix} [{completed}/{total}] {result.item_id}: {status} ({result.duration_ms}ms)")

        total_time = int((time.time() - start_time) * 1000)
        success_count = sum(1 for r in results if r.success)
        self.log_fn(f"{progress_prefix} Complete: {success_count}/{total} succeeded in {total_time}ms")

        return results

    # ==================== Helper Methods ====================

    def _get_client(self):
        """Lazy initialization of Bedrock client."""
        if self._client is None:
            self._client = boto3.client(
                'bedrock-runtime',
                region_name=self.region
            )
        return self._client

    def _parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parse JSON from AI response, handling common issues.

        Handles:
        - Direct JSON
        - Markdown code blocks (```json ... ```)
        - JSON embedded in text
        """
        text = text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if '```' in text:
            # Find ```json or ``` block
            if '```json' in text:
                start = text.find('```json') + 7
            else:
                start = text.find('```') + 3

            end = text.find('```', start)
            if end > start:
                try:
                    return json.loads(text[start:end].strip())
                except json.JSONDecodeError:
                    pass

        # Try to find JSON object in text
        if '{' in text:
            start = text.find('{')
            depth = 0
            for i, char in enumerate(text[start:], start):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i+1])
                        except json.JSONDecodeError:
                            break

        self.log_fn(f"[BedrockAgent] Could not parse JSON from response")
        return None

    def _mock_response(self, prompt: str) -> str:
        """Generate mock response for testing."""
        # Return a simple mock based on what seems to be requested
        if 'json' in prompt.lower():
            return json.dumps({
                "mock": True,
                "message": "This is a mock response",
                "prompt_length": len(prompt)
            })
        return f"[MOCK RESPONSE] Received prompt of {len(prompt)} characters"

    # ==================== Class Methods ====================

    @classmethod
    def create(
        cls,
        purpose: str = "general",
        **kwargs
    ) -> "BedrockAgent":
        """
        Factory method to create agent with sensible defaults for purpose.

        Args:
            purpose: One of "general", "code_analysis", "discovery", "refactor"
            **kwargs: Override any default settings

        Returns:
            Configured BedrockAgent instance
        """
        defaults = {
            "general": {
                "temperature": 0.3,
                "max_tokens": 4096
            },
            "code_analysis": {
                "temperature": 0.2,
                "max_tokens": 4096
            },
            "discovery": {
                "temperature": 0.2,
                "max_tokens": 2000
            },
            "refactor": {
                "temperature": 0.3,
                "max_tokens": 8192
            },
            "json": {
                "temperature": 0.1,
                "max_tokens": 4096
            }
        }

        config = defaults.get(purpose, defaults["general"])
        config["purpose"] = purpose  # Set purpose for logging
        config.update(kwargs)

        return cls(**config)


# Convenience functions for simple usage

def invoke(prompt: str, **kwargs) -> str:
    """Simple invoke - creates agent and calls it."""
    return BedrockAgent(**kwargs).invoke(prompt)


def invoke_json(prompt: str, **kwargs) -> Optional[Dict[str, Any]]:
    """Simple invoke with JSON parsing."""
    return BedrockAgent(**kwargs).invoke_json(prompt)
