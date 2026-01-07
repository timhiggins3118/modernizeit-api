"""
Batch Strategy Module

Purpose: Determine optimal batching strategy for Bedrock AI analysis
Date: November 3, 2025
Version: V3.0
"""

from token_estimator import estimate_tokens


def determine_batch_strategy(file_analysis):
    """
    Determine batching strategy based on estimated token count

    Strategy:
    - Small files (<150K tokens): Single call (best quality, lowest cost)
    - Large files (>150K tokens): Batched calls (safe, scalable)

    Args:
        file_analysis: File analysis dictionary from TreeSitterAnalyzer

    Returns:
        Dictionary with batching strategy:
        {
            'strategy': 'single_call' | 'batched',
            'num_batches': int,
            'batch_size': int,
            'estimated_tokens': int
        }
    """
    estimated_tokens = estimate_tokens(file_analysis)
    paragraph_count = file_analysis.get('paragraph_count', 0)

    # Claude 3.5 Sonnet: 200K input limit
    # Reserve 20K for prompt, 30K for response
    SAFE_TOKEN_LIMIT = 150000

    if estimated_tokens < SAFE_TOKEN_LIMIT:
        # ONE call - full file analysis (best quality)
        return {
            'strategy': 'single_call',
            'num_batches': 1,
            'batch_size': paragraph_count,
            'estimated_tokens': estimated_tokens
        }

    # BATCHED approach
    # Target: ~75K tokens per batch (safe margin)
    # Estimate: 100 paragraphs = ~75K tokens

    if paragraph_count < 300:
        batch_size = 100  # Larger batches for medium files
    else:
        batch_size = 50   # Smaller batches for giant files

    num_batches = (paragraph_count + batch_size - 1) // batch_size

    return {
        'strategy': 'batched',
        'num_batches': num_batches,
        'batch_size': batch_size,
        'estimated_tokens': estimated_tokens
    }


def create_paragraph_batches(paragraphs, batch_size):
    """
    Split paragraphs into batches

    Args:
        paragraphs: List of paragraph dictionaries
        batch_size: Number of paragraphs per batch

    Returns:
        List of batches (each batch is a list of paragraphs)
    """
    batches = []

    for i in range(0, len(paragraphs), batch_size):
        batch = paragraphs[i:i + batch_size]
        batches.append(batch)

    return batches
