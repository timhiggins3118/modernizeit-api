"""
Token Estimation Module

Purpose: Estimate token count for COBOL file analysis
Date: November 3, 2025
Version: V3.0
"""

def estimate_tokens(file_analysis):
    """
    Estimate tokens needed to analyze a COBOL file

    Based on empirical testing:
    - COBOL line ~= 50 tokens (code + JSON structure + overhead)
    - Conservative estimate to prevent API errors

    Args:
        file_analysis: File analysis dictionary from TreeSitterAnalyzer

    Returns:
        Estimated token count (int)
    """
    total_lines = file_analysis.get('total_lines', 0)

    # If total_lines not available, estimate from paragraph count
    if total_lines == 0:
        paragraph_count = file_analysis.get('paragraph_count', 0)
        total_lines = paragraph_count * 15  # Average 15 lines per paragraph

    # Conservative estimate: 50 tokens per line
    # Includes COBOL code + JSON structure + prompt overhead
    estimated_tokens = total_lines * 50

    return estimated_tokens


def estimate_batch_tokens(paragraphs, batch_size):
    """
    Estimate tokens for a batch of paragraphs

    Args:
        paragraphs: List of paragraph dictionaries
        batch_size: Number of paragraphs in batch

    Returns:
        Estimated token count for batch
    """
    if not paragraphs or batch_size == 0:
        return 0

    # Calculate average lines per paragraph
    total_lines = sum(p.get('line_count', 15) for p in paragraphs[:batch_size])
    avg_lines = total_lines / min(len(paragraphs), batch_size)

    # Estimate tokens for batch
    batch_lines = avg_lines * batch_size
    estimated_tokens = batch_lines * 50

    return int(estimated_tokens)
