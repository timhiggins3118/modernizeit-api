"""
Entity Generator V3 - Using JavaPoet for Type-Safe Generation
Lambda: EntityGeneratorV3

Purpose: Generate JPA entities using JavaPoet (ZERO syntax errors guaranteed)

V3 Innovation:
- Uses Square's JavaPoet library for type-safe code generation
- Cannot produce invalid Java (compile-time safety)
- Perfect JPA annotations every time
- No string concatenation, no templates
"""

import json
import boto3
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

s3_client = boto3.client('s3')

# Environment variables
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v3')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate JPA entities using JavaPoet

    Input:
    {
        "job_id": "jgv3_job_5150_TestApp01_1760617960_abc123",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Reads:
    - s3://{bucket}/{account}/{app}/java_generation_v3/jobs/{job_id}/generation_plan.json

    Writes:
    - s3://{bucket}/{account}/{app}/java_generation_v3/jobs/{job_id}/entities/*.java
    """
    try:
        print("=" * 80)
        print("ENTITY GENERATOR V3 - JavaPoet Generation")
        print("=" * 80)

        # Parse input
        job_id = event.get('job_id')
        scout_account_id = event.get('scout_account_id')
        application_name = event.get('application_name')

        if not all([job_id, scout_account_id, application_name]):
            raise ValueError("Missing required fields: job_id, scout_account_id, application_name")

        print(f"Job ID: {job_id}")
        print(f"Account: {scout_account_id}")
        print(f"Application: {application_name}")

        # Update status
        update_status(scout_account_id, application_name, job_id, "in_progress", "Generating entities with JavaPoet")

        # Step 1: Download generation_plan.json from S3
        base_path = f"{scout_account_id}/{application_name}/java_generation_v3/jobs/{job_id}"
        generation_plan_key = f"{base_path}/generation_plan.json"

        print(f"Downloading: s3://{BUCKET_NAME}/{generation_plan_key}")

        generation_plan_response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key=generation_plan_key
        )
        generation_plan = json.loads(generation_plan_response['Body'].read().decode('utf-8'))

        print(f"Generation plan loaded: {len(generation_plan.get('entities', []))} entities")

        # Step 1.5: Read project_metadata.json to get correct project_base
        # This is needed because entities must go into the Maven project structure
        # at: {project_base}/src/main/java/{package}/entities/
        # NOT at: {base_path}/entities/
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

            # Write generation plan to temp file
            with open(input_json_path, 'w') as f:
                json.dump(generation_plan, f, indent=2)

            print(f"Temp input: {input_json_path}")
            print(f"Output dir: {output_dir}")

            # Step 3: Call Java EntityGenerator
            java_home = os.environ.get('JAVA_HOME', '/usr/lib/jvm/java-17-amazon-corretto')
            java_cmd = f"{java_home}/bin/java"

            classpath = "/var/task/lib/javapoet-1.13.0.jar:/var/task/lib/json-20240303.jar:/var/task/java_src"

            cmd = [
                java_cmd,
                "-cp", classpath,
                "EntityGenerator",
                str(input_json_path),
                str(output_dir)
            ]

            print(f"Executing: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes max
            )

            print("=== Java Output ===")
            print(result.stdout)

            if result.returncode != 0:
                print("=== Java Errors ===")
                print(result.stderr)
                raise RuntimeError(f"EntityGenerator failed with exit code {result.returncode}")

            # Step 4: Upload generated entities to S3
            entity_count = 0
            package_name = generation_plan.get('package_name', 'com.modernized.modernizedapplication')
            package_path = package_name.replace('.', '/') + '/entities'

            # Find all generated .java files
            entities_dir = output_dir / package_path

            if not entities_dir.exists():
                raise RuntimeError(f"Expected entities directory not found: {entities_dir}")

            for java_file in entities_dir.glob('*.java'):
                # Upload to Maven structure: {project_base}/src/main/java/{package}/entities/
                # Example: 0U812/TestApp01/.../artifacts/ModernizedApplication/src/main/java/com/modernized/testapp01/entities/FooEntity.java
                s3_key = f"{project_base}/src/main/java/{package_name.replace('.', '/')}/entities/{java_file.name}"

                with open(java_file, 'r') as f:
                    content = f.read()

                s3_client.put_object(
                    Bucket=BUCKET_NAME,
                    Key=s3_key,
                    Body=content,
                    ContentType='text/x-java-source'
                )

                print(f"  ✓ Uploaded: {java_file.name} to s3://{BUCKET_NAME}/{s3_key}")
                entity_count += 1

            print(f"\n✓ Generated {entity_count} entities successfully")

            # Step 5: Create generation metadata
            metadata = {
                'generator': 'EntityGeneratorV3',
                'library': 'JavaPoet 1.13.0',
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'entity_count': entity_count,
                'package_name': package_name,
                'guarantee': 'Zero syntax errors (JavaPoet type-safe generation)'
            }

            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=f"{base_path}/entity_generation_metadata.json",  # Keep metadata at job level, not in entities/
                Body=json.dumps(metadata, indent=2),
                ContentType='application/json'
            )

            # Update status
            update_status(scout_account_id, application_name, job_id, "entity_generation_complete",
                         f"Generated {entity_count} entities with JavaPoet")

            return {
                'statusCode': 200,
                'entity_count': entity_count,
                'generator': 'JavaPoet',
                'message': f'Generated {entity_count} JPA entities successfully'
            }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        # Update status to failed
        if 'job_id' in locals() and 'scout_account_id' in locals() and 'application_name' in locals():
            update_status(scout_account_id, application_name, job_id, "failed",
                         f"Entity generation failed: {str(e)}")

        raise


def update_status(account_id: str, app_name: str, job_id: str, status: str, message: str):
    """Update job status in S3"""
    try:
        status_key = f"{account_id}/{app_name}/java_generation_v3/jobs/{job_id}/status.json"

        # Read current status
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
            status_data = json.loads(response['Body'].read().decode('utf-8'))
        except:
            status_data = {}

        # Update status
        status_data['status'] = status
        status_data['message'] = message
        status_data['updated_at'] = datetime.now(timezone.utc).isoformat()
        status_data['phase'] = 'entity_generation'

        if status == "failed":
            status_data['state'] = 'failed'
        elif status == "entity_generation_complete":
            status_data['progress'] = 20  # Entities = 20% of total workflow

        # Write back
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status updated: {status} - {message}")

    except Exception as e:
        print(f"WARNING: Could not update status: {str(e)}")
