#!/usr/bin/env python3
"""
Code Analysis V2 - Tree-Sitter AST Analyzer
Lambda handler for deep AST-based COBOL analysis
"""

import json
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from analysis.run import analyze_path
import pathlib
import tempfile
import os

s3_client = boto3.client('s3')

# Constants
BUCKET_NAME = 'code-transformation-v2'

def lambda_handler(event, context):
    """
    Tree-Sitter AST analysis for COBOL files
    Reads from shared/uploads/{source_hash}/extracted/
    Writes to code_analysis_v2/jobs/{job_id}/artifacts/ast_analysis.json
    """

    try:
        print(f"Tree-Sitter Analyzer starting: {json.dumps(event)}")

        # Parse input
        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')
        source_hash = event.get('source_hash')

        if not all([job_id, scout_account_id, application_name, source_hash]):
            return error_response(400, 'Missing required fields')

        base_path = f"{scout_account_id}/{application_name}"
        job_path = f"{base_path}/code_analysis_v2/jobs/{job_id}"

        print(f"Analyzing job: {job_id}")

        # Read classified_catalog.json to know which files are COBOL
        classified_catalog_key = f"{base_path}/shared/catalogs/{source_hash}/classified_catalog.json"
        catalog_response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=classified_catalog_key
        )
        classified_catalog = json.loads(catalog_response['Body'].read().decode('utf-8'))

        # Get list of COBOL files to analyze
        cobol_files = classified_catalog.get('classifications', {}).get('cobol', [])
        print(f"Found {len(cobol_files)} COBOL files to analyze")

        if len(cobol_files) == 0:
            return error_response(400, 'No COBOL files found in catalog')

        # Analyze each COBOL file
        file_results = []
        total_symbols = 0
        total_paragraphs = 0

        for file_path in cobol_files:
            file_key = f"{base_path}/shared/uploads/{source_hash}/extracted/{file_path}"

            print(f"Analyzing: {file_path}")

            try:
                # Read COBOL file content from S3
                file_response = s3_client.get_object(
                    Bucket=BUCKET_NAME,
                    Key=file_key
                )
                content = file_response['Body'].read().decode('utf-8', errors='ignore')

                # Write content to temp file (Tree-Sitter needs file path)
                with tempfile.NamedTemporaryFile(mode='w', suffix='.cbl', delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name

                try:
                    # Analyze with Tree-Sitter
                    analysis = analyze_path(pathlib.Path(tmp_path))
                    # Add the original S3 path to the result
                    analysis['path'] = file_path
                    file_results.append(analysis)
                finally:
                    # Clean up temp file
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

                total_symbols += len(analysis.get('symbols', {}).get('data_items', []))
                total_paragraphs += len(analysis.get('structure', {}).get('paragraphs', []))

            except Exception as e:
                print(f"Error analyzing file {file_path}: {str(e)}")
                # Continue with other files
                continue

        # Create summary
        summary = {
            'total_files': len(file_results),
            'total_symbols': total_symbols,
            'total_paragraphs': total_paragraphs,
            'total_programs': len([f for f in file_results if f.get('program_id')])
        }

        # Build final output
        ast_analysis = {
            'analyzer': 'tree-sitter',
            'job_id': job_id,
            'source_hash': source_hash,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': summary,
            'files': file_results
        }

        # Write results to S3
        output_key = f"{job_path}/artifacts/ast_analysis.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(ast_analysis, indent=2),
            ContentType='application/json'
        )

        print(f"AST analysis complete. Analyzed {len(file_results)} files with {total_symbols} symbols found.")
        print(f"Output written to: {output_key}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'status': 'completed',
                'job_id': job_id,
                'files_analyzed': len(file_results),
                'total_symbols': total_symbols,
                'output_path': f"s3://{BUCKET_NAME}/{output_key}"
            })
        }

    except Exception as e:
        print(f"Error in AST analysis: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Analysis failed: {str(e)}")


def analyze_cobol_content(file_path, content):
    """
    Wrapper around the Tree-Sitter analyzer
    Returns AST analysis similar to cobol_ts_analyzer output
    """
    from analysis.run import analyze_path
    import tempfile
    import os

    # Tree-Sitter needs a file path, so write to temp
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cbl', delete=False) as f:
        f.write(content)
        temp_path = f.name

    try:
        # Run Tree-Sitter analysis
        result = analyze_path(temp_path)

        # Add file path from S3
        result['path'] = file_path

        return result
    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def error_response(status_code, message):
    """Return error response"""
    return {
        'statusCode': status_code,
        'body': json.dumps({
            'error': message
        })
    }
