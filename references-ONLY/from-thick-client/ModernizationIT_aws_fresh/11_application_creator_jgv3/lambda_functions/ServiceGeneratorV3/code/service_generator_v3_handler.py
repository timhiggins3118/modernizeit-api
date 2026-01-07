"""
Service Generator V3 - Using Roaster for Validation
Lambda: ServiceGeneratorV3

Purpose: Generate Spring @Service classes with Roaster validation

V3 Innovation:
- Uses JBoss Roaster for generation AND validation
- Can parse AI-generated code and validate structure
- Catches semantic errors (records with setters, etc.)
- Type-safe code generation
"""

import json
import boto3
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

s3_client = boto3.client('s3')

# Environment variables
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v3')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate Spring @Service classes using Roaster

    Input:
    {
        "job_id": "jgv3_job_5150_TestApp01_1760617960_abc123",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }
    """
    try:
        print("=" * 80)
        print("SERVICE GENERATOR V3 - Roaster Generation")
        print("=" * 80)

        # Parse input
        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')

        if not all([job_id, scout_account_id, application_name]):
            raise ValueError("Missing required fields")

        print(f"Job ID: {job_id}")

        # Update status
        update_status(scout_account_id, application_name, job_id, "in_progress", "Generating services with Roaster")

        # Step 1: Download generation_plan.json from S3
        base_path = f"{scout_account_id}/{application_name}/java_generation_v3/jobs/{job_id}"
        generation_plan_key = f"{base_path}/generation_plan.json"

        print(f"Downloading: s3://{BUCKET_NAME}/{generation_plan_key}")

        generation_plan_response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=generation_plan_key
        )
        generation_plan = json.loads(generation_plan_response['Body'].read().decode('utf-8'))

        print(f"Generation plan loaded: {len(generation_plan.get('services', []))} services")

        # Step 1.5: Read project_metadata.json to get correct project_base
        # This is needed because services must go into the Maven project structure
        # at: {project_base}/src/main/java/{package}/services/
        # NOT at: {base_path}/services/
        project_metadata_key = f"{base_path}/project_metadata.json"
        print(f"Downloading: s3://{BUCKET_NAME}/{project_metadata_key}")

        project_metadata_response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=project_metadata_key
        )
        project_metadata = json.loads(project_metadata_response['Body'].read().decode('utf-8'))
        project_base = project_metadata.get('project_base')

        print(f"Project base: {project_base}")

        # Step 2: Create temp directories
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_json_path = temp_path / "generation_plan.json"
            output_dir = temp_path / "generated"
            output_dir.mkdir()

            # Write generation plan
            with open(input_json_path, 'w') as f:
                json.dump(generation_plan, f, indent=2)

            # Step 3: Call Java ServiceGenerator
            java_home = os.environ.get('JAVA_HOME', '/usr/lib/jvm/java-17-amazon-corretto')
            java_cmd = f"{java_home}/bin/java"

            classpath = "/var/task/lib/roaster-api-2.29.0.Final.jar:/var/task/lib/roaster-jdt-2.29.0.Final.jar:/var/task/lib/json-20240303.jar:/var/task/java_src"

            cmd = [
                java_cmd,
                "-cp", classpath,
                "ServiceGenerator",
                str(input_json_path),
                str(output_dir)
            ]

            print(f"Executing: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            print("=== Java Output ===")
            print(result.stdout)

            if result.returncode != 0:
                print("=== Java Errors ===")
                print(result.stderr)
                raise RuntimeError(f"ServiceGenerator failed with exit code {result.returncode}")

            # Step 4: Upload generated services to S3
            service_count = 0
            package_name = generation_plan.get('package_name', 'com.modernized.modernizedapplication')
            package_path = package_name.replace('.', '/') + '/services'

            services_dir = output_dir / package_path

            if not services_dir.exists():
                raise RuntimeError(f"Expected services directory not found: {services_dir}")

            for java_file in services_dir.glob('*.java'):
                # Upload to Maven structure: {project_base}/src/main/java/{package}/services/
                # Example: 0U812/TestApp01/.../artifacts/ModernizedApplication/src/main/java/com/modernized/testapp01/services/FooService.java
                s3_key = f"{project_base}/src/main/java/{package_name.replace('.', '/')}/services/{java_file.name}"

                with open(java_file, 'r') as f:
                    content = f.read()

                s3_client.put_object(
                    Bucket=BUCKET_NAME,
                    Key=s3_key,
                    Body=content,
                    ContentType='text/x-java-source'
                )

                print(f"  ✓ Uploaded: {java_file.name} to s3://{BUCKET_NAME}/{s3_key}")
                service_count += 1

            print(f"\n✓ Generated {service_count} services successfully")

            # Step 5: Create metadata
            metadata = {
                'generator': 'ServiceGeneratorV3',
                'library': 'Roaster 2.29.0.Final',
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'service_count': service_count,
                'package_name': package_name,
                'validation': 'Roaster syntax + semantic validation'
            }

            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=f"{base_path}/generation_metadata.json",  # Keep metadata at job level, not in services/
                Body=json.dumps(metadata, indent=2),
                ContentType='application/json'
            )

            # Update status
            update_status(scout_account_id, application_name, job_id, "service_generation_complete",
                         f"Generated {service_count} services with Roaster")

            return {
                'statusCode': 200,
                'service_count': service_count,
                'generator': 'Roaster',
                'message': f'Generated {service_count} services successfully'
            }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        if 'job_id' in locals():
            update_status(scout_account_id, application_name, job_id, "failed",
                         f"Service generation failed: {str(e)}")

        raise


def update_status(account_id: str, app_name: str, job_id: str, status: str, message: str):
    """Update job status in S3"""
    try:
        status_key = f"{account_id}/{app_name}/java_generation_v3/jobs/{job_id}/status.json"

        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(response['Body'].read().decode('utf-8'))
        except:
            status_data = {}

        status_data['status'] = status
        status_data['message'] = message
        status_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        status_data['phase'] = 'service_generation'

        if status == "failed":
            status_data['state'] = 'failed'
        elif status == "service_generation_complete":
            status_data['progress'] = 40  # Services = 40% of total

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status updated: {status}")

    except Exception as e:
        print(f"WARNING: Could not update status: {str(e)}")
