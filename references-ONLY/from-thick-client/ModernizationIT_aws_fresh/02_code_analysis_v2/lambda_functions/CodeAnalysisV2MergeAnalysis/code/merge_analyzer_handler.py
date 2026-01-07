#!/usr/bin/env python3
"""
Code Analysis V2 - Merge Analysis Results - ENHANCED
Combines regex, AST, and AI analysis (WITH STRUCTURED PARAGRAPH DATA)
"""

import json
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

# Constants
BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    Merge regex, AST, and AI analysis results
    Reads: regex_analysis.json, ast_analysis.json, ai_analysis.json
    Writes: static_analysis.json WITH STRUCTURED PARAGRAPH DATA
    """

    try:
        print(f"Merge Analyzer starting: {json.dumps(event)}")

        # Parse input
        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')
        source_hash = event.get('source_hash')

        # Check which analyzers completed
        regex_status = event.get('regex_status', 'completed')
        ast_status = event.get('ast_status', 'completed')
        ai_status = event.get('ai_status', 'completed')

        if not all([job_id, scout_account_id, application_name, source_hash]):
            return error_response(400, 'Missing required fields')

        base_path = f"{scout_account_id}/{application_name}"
        job_path = f"{base_path}/code_analysis_v2/jobs/{job_id}"

        print(f"Merging analysis for job: {job_id}")
        print(f"Regex status: {regex_status}, AST status: {ast_status}, AI status: {ai_status}")

        # Read regex_analysis.json
        regex_analysis = None
        if regex_status == 'completed':
            try:
                regex_key = f"{job_path}/artifacts/regex_analysis.json"
                regex_response = s3_client.get_object(
                    Bucket=BUCKET_NAME,
                    Key=regex_key
                )
                regex_analysis = json.loads(regex_response['Body'].read().decode('utf-8'))
                print(f"Loaded regex analysis: {len(regex_analysis.get('files', []))} files")
            except ClientError as e:
                print(f"Error loading regex analysis: {str(e)}")
                regex_status = 'failed'

        # Read ast_analysis.json
        ast_analysis = None
        if ast_status == 'completed':
            try:
                ast_key = f"{job_path}/artifacts/ast_analysis.json"
                ast_response = s3_client.get_object(
                    Bucket=BUCKET_NAME,
                    Key=ast_key
                )
                ast_analysis = json.loads(ast_response['Body'].read().decode('utf-8'))
                print(f"Loaded AST analysis: {len(ast_analysis.get('files', []))} files")
            except ClientError as e:
                print(f"Error loading AST analysis: {str(e)}")
                ast_status = 'skipped'

        # Read ai_analysis.json
        ai_analysis = None
        if ai_status == 'completed':
            try:
                ai_key = f"{job_path}/artifacts/ai_analysis.json"
                ai_response = s3_client.get_object(
                    Bucket=BUCKET_NAME,
                    Key=ai_key
                )
                ai_analysis = json.loads(ai_response['Body'].read().decode('utf-8'))
                print(f"Loaded AI analysis: {len(ai_analysis.get('files', []))} files")
            except ClientError as e:
                print(f"Error loading AI analysis: {str(e)}")
                ai_status = 'skipped'

        # Verify we have at least one analysis
        if not regex_analysis and not ast_analysis and not ai_analysis:
            return error_response(500, 'No analysis results available to merge')

        # Merge the results
        merged = merge_analysis_results(
            regex_analysis,
            ast_analysis,
            ai_analysis,
            job_id,
            source_hash
        )

        # Add analyzer status
        merged['analyzers_used'] = []
        if regex_status == 'completed':
            merged['analyzers_used'].append('regex')
        if ast_status == 'completed':
            merged['analyzers_used'].append('tree-sitter')
        if ai_status == 'completed':
            merged['analyzers_used'].append('ai-bedrock')

        # Write merged results to S3
        output_key = f"{job_path}/artifacts/static_analysis.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(merged, indent=2),
            ContentType='application/json'
        )

        print(f"Merge complete. Output written to: {output_key}")
        print(f"Total paragraphs extracted: {merged['summary'].get('total_paragraphs_with_business_logic', 0)}")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'job_id': job_id,
                'analyzers_used': merged['analyzers_used'],
                'files_analyzed': merged['summary']['total_files'],
                'paragraphs_extracted': merged['summary'].get('total_paragraphs_with_business_logic', 0),
                'output_path': f"s3://{BUCKET_NAME}/{output_key}"
            }
        }

    except Exception as e:
        print(f"Error in merge analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Merge failed: {str(e)}")


def merge_analysis_results(regex_analysis, ast_analysis, ai_analysis, job_id, source_hash):
    """
    Merge regex, AST, and AI analysis into unified structure
    ENHANCED: Now includes structured paragraph-level business logic
    """

    merged = {
        'job_id': job_id,
        'source_hash': source_hash,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'summary': {},
        'files': []
    }

    # Use regex summary as base
    if regex_analysis:
        merged['summary'] = regex_analysis.get('summary', {})

    # Enhance with AST data if available
    if ast_analysis:
        ast_summary = ast_analysis.get('summary', {})
        merged['summary']['total_symbols'] = ast_summary.get('total_symbols', 0)
        merged['summary']['total_paragraphs'] = ast_summary.get('total_paragraphs', 0)

    # Add AI summary if available
    if ai_analysis:
        merged['summary']['files_with_ai_analysis'] = ai_analysis.get('files_analyzed', 0)

    # Merge file-level data
    # Create a map of files by path
    files_map = {}

    # Add regex data
    if regex_analysis:
        for file in regex_analysis.get('files', []):
            path = file.get('path')
            files_map[path] = {
                'path': path,
                'program_id': file.get('program_id'),
                'size': file.get('size'),
                'regex_findings': {
                    'metrics': file.get('metrics'),
                    'code_quality': file.get('code_quality'),
                    'code_smells': file.get('code_smells'),
                    'quality_metrics': file.get('quality_metrics'),
                    'dependencies': file.get('dependencies')
                }
            }

    # Add AST data
    if ast_analysis:
        for file in ast_analysis.get('files', []):
            path = file.get('path')
            if path in files_map:
                # Add AST data to existing file
                files_map[path]['ast_findings'] = {
                    'structure': file.get('structure'),
                    'symbols': file.get('symbols'),
                    'graphs': file.get('graphs'),
                    'data_flow': file.get('data_flow'),
                    'metrics': file.get('metrics')
                }
            else:
                # AST only (shouldn't happen, but handle it)
                files_map[path] = {
                    'path': path,
                    'program_id': file.get('program_id'),
                    'ast_findings': {
                        'structure': file.get('structure'),
                        'symbols': file.get('symbols'),
                        'graphs': file.get('graphs'),
                        'data_flow': file.get('data_flow'),
                        'metrics': file.get('metrics')
                    }
                }

    # Add AI data WITH STRUCTURED PARAGRAPH ANALYSIS
    total_paragraphs_with_logic = 0
    files_with_ai_analysis = 0
    files_skipped_ai = 0

    if ai_analysis:
        for file in ai_analysis.get('files', []):
            path = file.get('path')
            analysis_data = file.get('analysis') or {}  # Handle None gracefully

            # Skip files where AI analysis failed
            if not analysis_data:
                print(f"Skipping AI data for {path}: analysis is None (file processing failed)")
                files_skipped_ai += 1
                continue

            if path in files_map:
                # ENHANCED: Add both original AI analysis AND structured paragraph data
                files_map[path]['ai_analysis'] = {
                    'analysis_text': analysis_data.get('analysis_text'),  # Original text
                    'model': analysis_data.get('model'),
                    'agent': analysis_data.get('agent'),
                    'timestamp': analysis_data.get('timestamp'),
                    'encoding_used': analysis_data.get('encoding_used')  # Track encoding
                }

                # ADD STRUCTURED PROGRAM-LEVEL ANALYSIS
                program_level = analysis_data.get('program_level_analysis') or {}
                if program_level:
                    files_map[path]['program_level_analysis'] = program_level

                # ADD STRUCTURED PARAGRAPH-LEVEL ANALYSIS
                paragraph_analysis = analysis_data.get('paragraph_analysis') or []
                if paragraph_analysis:
                    files_map[path]['paragraph_analysis'] = paragraph_analysis
                    total_paragraphs_with_logic += len(paragraph_analysis)

                    print(f"File {path}: Found {len(paragraph_analysis)} paragraphs with business logic")

                files_with_ai_analysis += 1

            else:
                # AI only (create entry if file not already in map)
                files_map[path] = {
                    'path': path,
                    'ai_analysis': {
                        'analysis_text': analysis_data.get('analysis_text'),
                        'model': analysis_data.get('model'),
                        'agent': analysis_data.get('agent'),
                        'timestamp': analysis_data.get('timestamp'),
                        'encoding_used': analysis_data.get('encoding_used')
                    }
                }

                # Add structured data
                program_level = analysis_data.get('program_level_analysis') or {}
                if program_level:
                    files_map[path]['program_level_analysis'] = program_level

                paragraph_analysis = analysis_data.get('paragraph_analysis') or []
                if paragraph_analysis:
                    files_map[path]['paragraph_analysis'] = paragraph_analysis
                    total_paragraphs_with_logic += len(paragraph_analysis)

                files_with_ai_analysis += 1

    # Convert map to list
    merged['files'] = list(files_map.values())

    # Add paragraph statistics to summary
    merged['summary']['total_paragraphs_with_business_logic'] = total_paragraphs_with_logic
    merged['summary']['files_with_ai_analysis'] = files_with_ai_analysis
    merged['summary']['files_skipped_ai'] = files_skipped_ai

    # Calculate quality score (if we have regex data)
    if regex_analysis:
        total_maintainability = sum([
            f.get('regex_findings', {}).get('code_quality', {}).get('maintainability_index', 0)
            for f in merged['files']
        ])
        file_count = len([f for f in merged['files'] if f.get('regex_findings')])
        if file_count > 0:
            merged['summary']['quality_score'] = round(total_maintainability / file_count, 2)

    return merged


def error_response(status_code, message):
    """Return error response"""
    return {
        'statusCode': status_code,
        'body': {
            'error': message
        }
    }
