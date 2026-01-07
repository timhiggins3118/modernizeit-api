"""
Bedrock Client Module

Purpose: AWS Bedrock API integration with mock mode for local testing
Date: November 3, 2025
Version: V3.0
"""

import json
import logging
import time

logger = logging.getLogger(__name__)

# Mock mode flag (set to True for local testing)
# Can be overridden with environment variable: BEDROCK_MOCK_MODE=false
import os
MOCK_MODE = os.environ.get('BEDROCK_MOCK_MODE', 'true').lower() == 'true'

try:
    import boto3
    bedrock_runtime = boto3.client('bedrock-runtime', region_name='us-east-1')
    if not MOCK_MODE:
        logger.info("Bedrock client initialized - using REAL API")
    else:
        logger.info("Bedrock client available but MOCK_MODE enabled")
except Exception as e:
    logger.warning(f"boto3 not available or AWS credentials not configured: {e}")
    logger.warning("Running in MOCK MODE")
    MOCK_MODE = True


def invoke_bedrock(prompt, max_retries=3):
    """
    Invoke AWS Bedrock with Claude model

    Args:
        prompt: Prompt string
        max_retries: Number of retry attempts

    Returns:
        Response text from Claude
    """
    if MOCK_MODE:
        return invoke_bedrock_mock(prompt)

    # Real Bedrock API call
    for attempt in range(max_retries):
        try:
            response = bedrock_runtime.invoke_model(
                modelId="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 8192,
                    "temperature": 0.3,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )

            result = json.loads(response['body'].read())
            return result['content'][0]['text']

        except Exception as e:
            if 'ThrottlingException' in str(e):
                # Rate limit hit - exponential backoff
                wait_time = 2 ** attempt
                logger.warning(f"Throttled, retrying in {wait_time}s...")
                time.sleep(wait_time)
            elif 'ModelTimeoutException' in str(e):
                # Model timeout - retry
                logger.warning(f"Model timeout on attempt {attempt + 1}")
                if attempt == max_retries - 1:
                    raise
            else:
                logger.error(f"Bedrock error: {str(e)}")
                raise

    raise Exception("Max retries exceeded")


def invoke_bedrock_mock(prompt):
    """
    Mock Bedrock response for local testing

    Returns realistic JSON responses based on prompt type
    """
    logger.info("MOCK MODE: Generating mock Bedrock response")

    # Detect prompt type
    if "HIGH LEVEL" in prompt:
        # Program-level mock response
        return json.dumps({
            "business_purpose": "This COBOL program processes customer transactions and updates account balances. It reads transaction records, validates them against business rules, and writes updated records to the master file.",
            "data_flows": "Reads TRANSACTION-FILE (sequential), reads/updates CUSTOMER-MASTER (indexed), writes AUDIT-LOG (sequential). Main data structures: TRANSACTION-RECORD (50 bytes), CUSTOMER-RECORD (200 bytes).",
            "business_rules": [
                "Transaction amount must be > 0",
                "Customer account must exist before processing",
                "Daily transaction limit: $10,000 per customer",
                "Negative balance requires manager approval"
            ],
            "dependencies": [
                "TRANSACTION-FILE (input)",
                "CUSTOMER-MASTER (I/O)",
                "AUDIT-LOG (output)",
                "DB2-CUSTOMER-TABLE (external database)"
            ],
            "complexity": "MEDIUM",
            "complexity_reasoning": "Program has moderate complexity. Uses indexed file access, multiple validation rules, and database integration. However, logic is well-structured with clear paragraph separation. Estimated 3-4 weeks for Java conversion.",
            "recommendations": "Convert to Spring Boot microservice. Use JPA for database access. Implement transaction validation as separate service. Consider event-driven architecture for audit logging."
        })

    else:
        # Paragraph-level mock response
        # Extract paragraph names from prompt
        paragraphs_in_prompt = []
        if '"name":' in prompt:
            # Parse paragraph names from JSON in prompt
            import re
            names = re.findall(r'"name":\s*"([^"]+)"', prompt)
            paragraphs_in_prompt = names[:5]  # Mock first 5

        if not paragraphs_in_prompt:
            paragraphs_in_prompt = ["00000-MAIN-CONTROL", "10000-INITIALIZE"]

        mock_paragraphs = []
        for para_name in paragraphs_in_prompt:
            mock_paragraphs.append({
                "name": para_name,
                "business_logic": f"This paragraph implements the {para_name.lower().replace('-', ' ')} functionality. It coordinates the execution of subordinate paragraphs and manages data flow between program sections.",
                "data_flow": f"Reads working storage variables, processes data according to business rules, updates output records. Main data items: WS-COUNTER, INPUT-RECORD, OUTPUT-RECORD.",
                "dependencies": ["NEXT-PARAGRAPH-1", "NEXT-PARAGRAPH-2"],
                "java_recommendations": f"Convert {para_name} to a Java method in the main service class. Use dependency injection for data access. Consider extracting business logic to separate validator classes."
            })

        return json.dumps({"paragraphs": mock_paragraphs})


def parse_bedrock_response(response_text):
    """
    Parse JSON response from Bedrock

    Args:
        response_text: Response text from Bedrock

    Returns:
        Parsed JSON dictionary

    Raises:
        ValueError: If response is not valid JSON
    """
    try:
        # Try to parse as JSON
        return json.loads(response_text)
    except json.JSONDecodeError as e:
        # Try to extract JSON from markdown code blocks
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
            return json.loads(json_str)
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
            return json.loads(json_str)
        else:
            raise ValueError(f"Could not parse JSON from response: {str(e)}")
