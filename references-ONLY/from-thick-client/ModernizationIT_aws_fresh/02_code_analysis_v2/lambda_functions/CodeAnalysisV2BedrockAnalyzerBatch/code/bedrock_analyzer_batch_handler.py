#!/usr/bin/env python3
"""
Code Analysis V2 - Bedrock AI Analyzer (Batch Mode) - ENHANCED
Analyzes a batch of COBOL files using COBOLAnalystV2 Bedrock Agent
NOW WITH STRUCTURED PARAGRAPH-LEVEL ANALYSIS PARSING
"""

import json
import boto3
import time
import re
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

BUCKET_NAME = 'code-transformation-v2'
BEDROCK_AGENT_ID = 'LGXEUDJILW'  # COBOLAnalystV2
BEDROCK_AGENT_ALIAS_ID = 'TSTALIASID'  # Default test alias

def decode_with_fallback(file_bytes, file_path):
    """
    Try multiple encodings to decode COBOL file content
    Returns: (decoded_content, encoding_used)

    Encoding priority:
    1. UTF-8 (most modern files)
    2. ISO-8859-1 (IBM i / AS/400 legacy systems)
    3. CP1252 (Windows Latin-1)
    """
    encodings = ['utf-8', 'iso-8859-1', 'cp1252']

    for encoding in encodings:
        try:
            content = file_bytes.decode(encoding)
            print(f"Successfully decoded {file_path} using {encoding}")
            return content, encoding
        except UnicodeDecodeError:
            continue

    # If all encodings fail, raise the error
    raise UnicodeDecodeError(
        'multi-encoding',
        file_bytes,
        0,
        len(file_bytes),
        f"Could not decode {file_path} with any supported encoding: {encodings}"
    )


def lambda_handler(event, context):
    """
    Analyze a batch of COBOL files using Bedrock Agent
    Processes up to 5 files and writes results to S3
    NOW WITH MULTI-ENCODING SUPPORT for IBM i / legacy COBOL files
    """

    try:
        print(f"Bedrock Analyzer Batch starting: {json.dumps(event)}")

        # Parse input - now includes batch info
        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')
        source_hash = event.get('source_hash')

        # Batch-specific parameters
        batch = event.get('batch', {})
        batch_id = batch.get('batch_id', 0)
        files_to_process = batch.get('files', [])

        if not all([job_id, scout_account_id, application_name, source_hash]):
            return error_response(400, 'Missing required fields')

        if not files_to_process:
            return error_response(400, 'No files in batch')

        base_path = f"{scout_account_id}/{application_name}"
        job_path = f"{base_path}/code_analysis_v2/jobs/{job_id}"

        print(f"Processing batch {batch_id} with {len(files_to_process)} files")

        # Analyze each COBOL file in the batch
        batch_results = []
        files_processed = 0
        files_failed = 0

        for file_path in files_to_process:
            print(f"Analyzing file {files_processed + 1}/{len(files_to_process)}: {file_path}")

            try:
                # Read COBOL file content with multi-encoding support
                file_key = f"{base_path}/shared/uploads/{source_hash}/extracted/{file_path}"
                file_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
                file_bytes = file_response['Body'].read()
                cobol_content, encoding_used = decode_with_fallback(file_bytes, file_path)

                # Invoke Bedrock Agent and parse response
                ai_analysis = invoke_bedrock_agent(cobol_content, file_path)

                # Add encoding metadata to results
                ai_analysis['encoding_used'] = encoding_used

                batch_results.append({
                    'path': file_path,
                    'analysis': ai_analysis,
                    'analyzed_at': datetime.now(timezone.utc).isoformat()
                })
                files_processed += 1

            except Exception as file_error:
                print(f"Error analyzing {file_path}: {str(file_error)}")
                batch_results.append({
                    'path': file_path,
                    'error': str(file_error),
                    'analysis': None
                })
                files_failed += 1

        # Write batch results to S3
        batch_output_key = f"{job_path}/artifacts/ai_analysis/batch_{batch_id}.json"

        batch_data = {
            'batch_id': batch_id,
            'job_id': job_id,
            'source_hash': source_hash,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'files_processed': files_processed,
            'files_failed': files_failed,
            'files': batch_results
        }

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=batch_output_key,
            Body=json.dumps(batch_data, indent=2),
            ContentType='application/json'
        )

        print(f"Batch {batch_id} complete. Processed: {files_processed}, Failed: {files_failed}")
        print(f"Output written to: {batch_output_key}")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'batch_id': batch_id,
                'files_processed': files_processed,
                'files_failed': files_failed,
                'output_path': f"s3://{BUCKET_NAME}/{batch_output_key}"
            }
        }

    except Exception as e:
        print(f"Error in batch analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Batch analysis failed: {str(e)}")


def invoke_bedrock_agent(cobol_content, file_path):
    """
    Invoke Bedrock Agent to analyze COBOL code
    Returns structured analysis with program-level AND paragraph-level data
    """

    try:
        # Prepare the prompt for the agent
        user_prompt = f"""Analyze the following COBOL program from file: {file_path}

```cobol
{cobol_content}
```

Provide a detailed analysis following the structure outlined in your instructions."""

        print(f"Invoking Bedrock Agent for {file_path} (content length: {len(cobol_content)} bytes)")

        # Invoke the agent
        response = bedrock_agent_runtime.invoke_agent(
            agentId=BEDROCK_AGENT_ID,
            agentAliasId=BEDROCK_AGENT_ALIAS_ID,
            sessionId=f"session-batch-{int(time.time())}",
            inputText=user_prompt
        )

        # Process the streaming response
        event_stream = response['completion']
        full_response = ""

        for event in event_stream:
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    full_response += chunk['bytes'].decode('utf-8')

        print(f"Received AI analysis ({len(full_response)} chars)")

        # Parse the response into structured data
        parsed_analysis = parse_ai_response(full_response)

        return {
            'analysis_text': full_response,  # Keep original for reference
            'program_level_analysis': parsed_analysis['program_level'],
            'paragraph_analysis': parsed_analysis['paragraphs'],
            'model': 'anthropic.claude-3-5-sonnet-20240620-v1:0',
            'agent': 'COBOLAnalystV2',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'parsing_stats': {
                'paragraphs_found': len(parsed_analysis['paragraphs']),
                'parsing_errors': parsed_analysis.get('errors', [])
            }
        }

    except Exception as e:
        print(f"Error invoking Bedrock Agent: {str(e)}")
        raise


def parse_ai_response(response_text):
    """
    Parse AI response into structured program-level and paragraph-level data

    Expected format:
    PROGRAM-LEVEL ANALYSIS:
    - Business Purpose: ...
    ...

    PARAGRAPH-LEVEL ANALYSIS:

    PARAGRAPH: NAME
    - BUSINESS PURPOSE: ...
    - COBOL LOGIC: ...
    - JAVA METHOD:
    ```java
    ...
    ```
    - DEPENDENCIES: ...
    - CRITICALITY: ...
    """

    parsed = {
        'program_level': {},
        'paragraphs': [],
        'errors': []
    }

    try:
        # Split into program-level and paragraph-level sections
        sections = response_text.split('PARAGRAPH-LEVEL ANALYSIS:', 1)

        if len(sections) > 0:
            program_section = sections[0].replace('PROGRAM-LEVEL ANALYSIS:', '').strip()
            parsed['program_level'] = {
                'raw_text': program_section,
                'business_purpose': extract_section(program_section, 'Business Purpose'),
                'risks': extract_section(program_section, 'Hidden Risks'),
                'data_flow': extract_section(program_section, 'Data Flow'),
                'modernization': extract_section(program_section, 'Modernization'),
                'performance': extract_section(program_section, 'Performance')
            }

        if len(sections) > 1:
            paragraph_section = sections[1].strip()
            parsed['paragraphs'] = parse_paragraphs(paragraph_section)

    except Exception as e:
        print(f"Error parsing AI response: {str(e)}")
        parsed['errors'].append(f"Parsing error: {str(e)}")
        # Return raw text if parsing fails
        parsed['program_level'] = {'raw_text': response_text}

    return parsed


def extract_section(text, section_name):
    """Extract a specific section from program-level analysis"""
    # Look for patterns like "1. **Business Purpose**" or "- Business Purpose:"
    patterns = [
        rf'\*\*{section_name}\*\*[:\s]+(.*?)(?=\n\d+\.|$)',
        rf'{section_name}[:\s]+(.*?)(?=\n\n|$)'
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return ""


def paragraph_name_to_method_name(para_name):
    """
    Convert COBOL paragraph name to Java method name

    Examples:
    - "10000-INITIALIZE-PROGRAM" → "initializeProgram"
    - "20000-PROCESS-RECORDS" → "processRecords"
    - "20700-CHECK-SI-RISK" → "checkSiRisk"
    """
    # Remove leading digits and hyphens (e.g., "10000-")
    cleaned = re.sub(r'^\d+-', '', para_name)

    # Split by hyphens
    words = cleaned.split('-')

    # Convert to camelCase
    if not words:
        return "unknown"

    # First word lowercase, rest capitalized
    method_name = words[0].lower()
    for word in words[1:]:
        method_name += word.capitalize()

    return method_name


def parse_paragraphs(paragraph_text):
    """
    Parse individual paragraphs from the AI response

    Returns list of paragraph dictionaries
    """
    paragraphs = []

    # Split by "PARAGRAPH:" markers
    paragraph_blocks = re.split(r'\nPARAGRAPH:\s+', paragraph_text)

    for block in paragraph_blocks[1:]:  # Skip first empty split
        try:
            lines = block.strip().split('\n')
            if not lines:
                continue

            # First line is the paragraph name
            para_name = lines[0].strip()

            # Convert paragraph name to Java method name
            method_name = paragraph_name_to_method_name(para_name)

            # Extract fields
            para_data = {
                'name': para_name,
                'business_purpose': extract_field(block, 'BUSINESS PURPOSE'),
                'cobol_logic': extract_field(block, 'COBOL LOGIC'),
                'java_method': extract_java_method(block, method_name),
                'dependencies': extract_dependencies(block),
                'criticality': extract_field(block, 'CRITICALITY')
            }

            paragraphs.append(para_data)

        except Exception as e:
            print(f"Error parsing paragraph block: {str(e)}")
            continue

    return paragraphs


def extract_field(text, field_name):
    """Extract a field value from paragraph text"""
    pattern = rf'-\s*{field_name}:\s*(.+?)(?=\n-|\n\n|$)'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def extract_java_method(text, method_name):
    """
    Extract Java method code from paragraph text
    Uses provided method_name derived from paragraph name

    Looks for ```java code blocks
    """
    # Look for ```java ... ``` code blocks
    pattern = r'```java\s+(.*?)\s+```'
    match = re.search(pattern, text, re.DOTALL)

    if match:
        java_code = match.group(1).strip()

        return {
            'code': java_code,
            'return_type': 'void',
            'method_name': method_name
        }

    return {
        'code': '',
        'return_type': 'void',
        'method_name': method_name
    }


def extract_dependencies(text):
    """Extract paragraph dependencies (which paragraphs it calls)"""
    pattern = r'-\s*DEPENDENCIES:\s*(.+?)(?=\n-|\n\n|$)'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

    if match:
        deps_text = match.group(1).strip()
        # Split by comma and clean up
        if deps_text.lower() == 'none':
            return []
        return [d.strip() for d in deps_text.split(',')]

    return []


def error_response(status_code, message):
    return {
        'statusCode': status_code,
        'body': {
            'error': message
        }
    }
