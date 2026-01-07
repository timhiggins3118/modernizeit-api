"""
Fargate Entrypoint for BedrockAnalyzerPerFile

This wrapper allows the Lambda handler to run in ECS Fargate.
Reads environment variables and calls the Lambda handler function.

Date: November 5, 2025
Version: V3.0
"""

import os
import sys
import json
from handler import lambda_handler

def main():
    """
    Main entry point for Fargate task.
    Reads environment variables and invokes Lambda handler.
    """
    try:
        # Read required environment variables
        job_id = os.environ['JOB_ID']
        file_name = os.environ['FILE_NAME']
        scout_account_id = os.environ['SCOUT_ACCOUNT_ID']
        application_name = os.environ['APPLICATION_NAME']
        source_hash = os.environ.get('SOURCE_HASH', '')
        file_analysis_s3_key = os.environ['FILE_ANALYSIS_S3_KEY']

        print(f"=== Fargate Task Starting ===")
        print(f"File: {file_name}")
        print(f"Job ID: {job_id}")
        print(f"Account: {scout_account_id}/{application_name}")
        print(f"Source Hash: {source_hash}")
        print(f"File Analysis Key: {file_analysis_s3_key}")
        print(f"===========================")

        # Build Lambda-style event
        event = {
            'job_id': job_id,
            'file_name': file_name,
            'scout_account_id': scout_account_id,
            'application_name': application_name,
            'source_hash': source_hash,
            'file_analysis_s3_key': file_analysis_s3_key
        }

        # Call the SAME Lambda handler
        print(f"\n🎸 Invoking Lambda handler for {file_name}...")
        result = lambda_handler(event, None)

        # Parse result
        status_code = result.get('statusCode')
        body = json.loads(result.get('body', '{}'))

        print(f"\n=== Handler Result ===")
        print(f"Status Code: {status_code}")
        print(f"Status: {body.get('status', 'unknown')}")

        if status_code == 200:
            print(f"Paragraphs Analyzed: {body.get('paragraphs_analyzed', 0)}")
            print(f"Batches Used: {body.get('batches_used', 0)}")
            print(f"Estimated Tokens: {body.get('estimated_tokens', 0)}")
            print(f"✅ SUCCESS: AI analysis completed for {file_name}")
            print(f"======================")
            sys.exit(0)
        else:
            error = body.get('error', 'Unknown error')
            error_type = body.get('error_type', 'UNKNOWN')
            print(f"❌ ERROR ({error_type}): {error}")
            print(f"======================")
            sys.exit(1)

    except KeyError as e:
        print(f"❌ ERROR: Missing required environment variable: {e}")
        print(f"Required variables:")
        print(f"  - JOB_ID")
        print(f"  - FILE_NAME")
        print(f"  - SCOUT_ACCOUNT_ID")
        print(f"  - APPLICATION_NAME")
        print(f"  - FILE_ANALYSIS_S3_KEY")
        print(f"Optional variables:")
        print(f"  - SOURCE_HASH")
        sys.exit(1)

    except Exception as e:
        print(f"❌ ERROR: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
