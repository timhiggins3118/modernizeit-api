"""
Java Generation V3 - Package Results Handler
Lambda: PackageResultsV3

Purpose:
1. Generate Docker files from templates
2. Zip all generated Java files into final_package.zip for download

V3 Design Principles:
- NO HARDCODING
- NO SHARED CODE
- Creates final downloadable ZIP with Docker support
"""

import json
import boto3
import os
import zipfile
import tempfile
from typing import Dict, Any, List
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')

# Environment variables
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'code-transformation-v3')

# Docker template files
DOCKER_TEMPLATES = [
    'Dockerfile.template',
    'docker-compose.yml.template',
    'init-db.sql.template',
    'start.sh.template',
    'stop.sh.template',
    'start.bat.template',
    'stop.bat.template'
]


def generate_docker_files(job_base: str, application_name: str, project_base: str) -> List[str]:
    """
    Generate Docker files from templates

    Returns: List of S3 keys for generated files
    """
    print("=== Generating Docker files ===")

    generated_files = []

    for template_name in DOCKER_TEMPLATES:
        try:
            # Read template from S3
            template_key = f"java_generation_v3/templates/docker/{template_name}"
            response = s3_client.get_object(Bucket=OUTPUT_BUCKET, Key=template_key)
            template_content = response['Body'].read().decode('utf-8')

            # Replace variables
            output_content = template_content.replace('{{APPLICATION_NAME}}', application_name)

            # Determine output filename (remove .template)
            output_filename = template_name.replace('.template', '')

            # Write to S3 in project root
            output_key = f"{project_base}/{output_filename}"
            s3_client.put_object(
                Bucket=OUTPUT_BUCKET,
                Key=output_key,
                Body=output_content,
                ContentType='text/plain'
            )

            generated_files.append(output_key)
            print(f"  ✓ Generated: {output_filename}")

        except Exception as e:
            print(f"  ⚠️  Could not generate {template_name}: {str(e)}")

    print(f"✓ Generated {len(generated_files)} Docker files")
    return generated_files


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Package all generated files into final ZIP

    Input:
    {
        "job_id": "jgv3_job_5150_TestApp01_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "statusCode": 200,
        "zip_key": "5150/TestApp01/java_generation_v3/jobs/{job_id}/final_package.zip",
        "files_packaged": 30,
        "zip_size_bytes": 123456
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V3 - PACKAGE RESULTS")
        print("=" * 80)

        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')

        if not all([job_id, scout_account_id, application_name]):
            raise ValueError("Missing required fields: job_id, scout_account_id, application_name")

        print(f"Job ID: {job_id}")
        print(f"Account: {scout_account_id}, App: {application_name}")

        # Build S3 paths
        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v3/jobs/{job_id}"

        # Read project metadata
        project_metadata = read_json(f"{job_base}/project_metadata.json")
        project_name = project_metadata.get('project_name', 'ModernizedApplication')
        project_base = project_metadata.get('project_base', f"{job_base}/artifacts/ModernizedApplication")

        print(f"Project: {project_name}")
        print(f"Project base: {project_base}")

        # Generate Docker files from templates
        docker_files = generate_docker_files(job_base, application_name, project_base)
        print(f"Generated {len(docker_files)} Docker files")

        # Create temp directory for packaging
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, 'final_package.zip')

            print(f"Creating ZIP at: {zip_path}")

            # List all files in artifacts folder (V2 approach - NO extension filtering)
            # This ensures we copy EVERYTHING that Flow 1 generated
            artifacts_prefix = f"{job_base}/artifacts/"
            print(f"\nListing files in: s3://{OUTPUT_BUCKET}/{artifacts_prefix}")

            paginator = s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=OUTPUT_BUCKET, Prefix=artifacts_prefix)

            files_to_package = []
            for page in pages:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        # Skip directories (like V2 does)
                        if not key.endswith('/'):
                            files_to_package.append(key)
                            print(f"  - {key}")

            print(f"\nFound {len(files_to_package)} files to package")

            if len(files_to_package) == 0:
                raise ValueError("No files found to package")

            # Create ZIP file
            files_packaged = 0
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for s3_key in files_to_package:
                    try:
                        # Download file from S3
                        response = s3_client.get_object(Bucket=OUTPUT_BUCKET, Key=s3_key)
                        file_content = response['Body'].read()

                        # Determine path in ZIP (remove job_base prefix AND artifacts/)
                        # Use V2's proven approach: split on '/artifacts/' to get relative path
                        # This ensures ZIP has ModernizedApplication/ at root, not artifacts/ModernizedApplication/
                        relative_path = s3_key.split('/artifacts/')[-1] if '/artifacts/' in s3_key else s3_key.replace(f"{job_base}/", "")

                        # Add to ZIP
                        zipf.writestr(relative_path, file_content)
                        files_packaged += 1

                        if files_packaged % 10 == 0:
                            print(f"  Packaged {files_packaged}/{len(files_to_package)} files...")

                    except Exception as e:
                        print(f"WARNING: Could not package {s3_key}: {str(e)}")

            print(f"✓ Packaged {files_packaged} files")

            # Get ZIP size
            zip_size = os.path.getsize(zip_path)
            print(f"ZIP size: {zip_size:,} bytes ({zip_size / 1024 / 1024:.2f} MB)")

            # Upload ZIP to S3
            zip_key = f"{job_base}/final_package.zip"
            print(f"Uploading to: s3://{OUTPUT_BUCKET}/{zip_key}")

            with open(zip_path, 'rb') as f:
                s3_client.put_object(
                    Bucket=OUTPUT_BUCKET,
                    Key=zip_key,
                    Body=f,
                    ContentType='application/zip'
                )

            print("✓ ZIP uploaded successfully")

            return {
                'statusCode': 200,
                'zip_key': zip_key,
                'files_packaged': files_packaged,
                'zip_size_bytes': zip_size
            }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'error': str(e)
        }


def read_json(s3_key: str) -> Dict[str, Any]:
    """Read JSON from S3"""
    try:
        response = s3_client.get_object(Bucket=OUTPUT_BUCKET, Key=s3_key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        print(f"WARNING: Could not read {s3_key}: {str(e)}")
        return {}
