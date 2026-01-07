"""
Parallel Bedrock Execution Utility

DEPRECATED: Use engines.ai.BedrockAgent directly instead.

This module provides backwards compatibility for code using ParallelBedrockExecutor.
All functionality is now in engines.ai.BedrockAgent.
"""

from typing import Any, Callable, List, Optional, TypeVar

from engines.ai import BedrockAgent, BatchResult

# Re-export BatchResult as BedrockCallResult for backwards compatibility
BedrockCallResult = BatchResult

T = TypeVar('T')


class ParallelBedrockExecutor:
    """
    DEPRECATED: Use engines.ai.BedrockAgent instead.

    This class is kept for backwards compatibility.
    All functionality delegates to BedrockAgent.

    Migration:
        # Old way
        executor = ParallelBedrockExecutor(max_workers=4)
        result = executor.invoke_model(prompt)

        # New way
        from engines.ai import BedrockAgent
        agent = BedrockAgent(max_workers=4)
        result = agent.invoke(prompt)
    """

    DEFAULT_MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    DEFAULT_MAX_TOKENS = 4096

    def __init__(
        self,
        max_workers: int = 4,
        region: str = "us-east-1",
        model_id: Optional[str] = None,
        rate_limit_delay: float = 0.0
    ):
        """Initialize - delegates to BedrockAgent."""
        self.agent = BedrockAgent(
            model=model_id or self.DEFAULT_MODEL_ID,
            region=region,
            max_workers=max_workers
        )
        self.max_workers = max_workers
        self.region = region
        self.model_id = model_id or self.DEFAULT_MODEL_ID
        self.rate_limit_delay = rate_limit_delay

    def get_client(self):
        """Get Bedrock client - delegates to agent."""
        return self.agent._get_client()

    def invoke_model(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2
    ) -> str:
        """Invoke model - delegates to BedrockAgent."""
        return self.agent.invoke(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )

    def execute_batch(
        self,
        items: List[T],
        process_fn: Callable[[T], Any],
        item_id_fn: Callable[[T], str],
        progress_prefix: str = "[Parallel]",
        log_fn: Optional[Callable[[str], None]] = None
    ) -> List[BatchResult]:
        """
        Execute processing function on items in parallel.

        DEPRECATED: Use BedrockAgent.invoke_batch() instead.

        Note: This method takes a process_fn that handles the full processing,
        not just prompt generation. For migration, refactor to use BedrockAgent
        with prompt_fn instead.
        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if log_fn is None:
            log_fn = print

        total = len(items)
        results: List[BatchResult] = []
        completed = 0

        log_fn(f"{progress_prefix} Starting {total} items with {self.max_workers} workers")

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {}
            for i, item in enumerate(items):
                if self.rate_limit_delay > 0 and i > 0:
                    time.sleep(self.rate_limit_delay)

                future = executor.submit(self._process_item, item, process_fn, item_id_fn)
                future_to_item[future] = item

            for future in as_completed(future_to_item):
                result = future.result()
                results.append(result)
                completed += 1

                status = "OK" if result.success else f"FAILED: {result.error}"
                log_fn(f"{progress_prefix} [{completed}/{total}] {result.item_id}: {status} ({result.duration_ms}ms)")

        total_time = int((time.time() - start_time) * 1000)
        success_count = sum(1 for r in results if r.success)
        log_fn(f"{progress_prefix} Complete: {success_count}/{total} succeeded in {total_time}ms")

        return results

    def _process_item(
        self,
        item: T,
        process_fn: Callable[[T], Any],
        item_id_fn: Callable[[T], str]
    ) -> BatchResult:
        """Process a single item with error handling."""
        import time

        item_id = item_id_fn(item)
        start = time.time()

        try:
            result = process_fn(item)
            duration_ms = int((time.time() - start) * 1000)
            return BatchResult(
                item_id=item_id,
                success=True,
                result=result,
                duration_ms=duration_ms
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            return BatchResult(
                item_id=item_id,
                success=False,
                error=str(e),
                duration_ms=duration_ms
            )


def parallel_map(
    items: List[T],
    process_fn: Callable[[T], Any],
    max_workers: int = 4,
    progress_prefix: str = "[Parallel]",
    log_fn: Optional[Callable[[str], None]] = None
) -> List[Any]:
    """
    DEPRECATED: Use BedrockAgent.invoke_batch() instead.

    Simple parallel map with progress logging.
    Returns list of results (None for failures).
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if log_fn is None:
        log_fn = print

    if not items:
        return []

    total = len(items)
    results = [None] * total
    completed = 0

    log_fn(f"{progress_prefix} Processing {total} items with {max_workers} workers")

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(process_fn, item): i
            for i, item in enumerate(items)
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            completed += 1

            try:
                results[index] = future.result()
                log_fn(f"{progress_prefix} [{completed}/{total}] Item {index} completed")
            except Exception as e:
                log_fn(f"{progress_prefix} [{completed}/{total}] Item {index} FAILED: {e}")
                results[index] = None

    total_time = int((time.time() - start_time) * 1000)
    success_count = sum(1 for r in results if r is not None)
    log_fn(f"{progress_prefix} Complete: {success_count}/{total} succeeded in {total_time}ms")

    return results
