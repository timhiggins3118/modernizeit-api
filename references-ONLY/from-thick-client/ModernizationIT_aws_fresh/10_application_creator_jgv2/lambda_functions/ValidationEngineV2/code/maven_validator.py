"""
Maven Compilation Validator
Phase 4 validation: Full compilation check using Maven
"""

from typing import List, Dict
import subprocess
import tempfile
import shutil
import boto3
import os
import re


class MavenValidator:
    """Validates Java code through Maven compilation"""

    def __init__(self):
        """Initialize Maven validator"""
        self.s3_client = boto3.client('s3')
        self.bucket_name = os.environ.get('BUCKET_NAME', 'code-transformation-v2')
        print("Maven validator initialized")

    def validate(self, project_base_s3_path: str, job_id: str) -> List[Dict]:
        """
        Validate by compiling the project with Maven

        Args:
            project_base_s3_path: S3 path to project root
            job_id: Job ID for logging

        Returns:
            List of compilation error dictionaries
        """
        errors = []
        temp_dir = None

        try:
            print(f"  Downloading project from S3: {project_base_s3_path}")

            # Create temporary directory
            temp_dir = tempfile.mkdtemp()

            # Download entire project from S3
            self._download_project(project_base_s3_path, temp_dir)

            print(f"  Running Maven compilation...")

            # Run Maven compile
            result = subprocess.run(
                ['mvn', 'clean', 'compile', '-B', '-q'],
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5-minute timeout
            )

            if result.returncode != 0:
                # Parse compilation errors
                errors = self._parse_maven_errors(result.stdout + result.stderr)
                print(f"  Maven compilation failed with {len(errors)} errors")
            else:
                print(f"  Maven compilation succeeded")

        except subprocess.TimeoutExpired:
            print(f"  ERROR: Maven compilation timeout (5 minutes)")
            errors.append({
                'file': 'pom.xml',
                'line': 0,
                'column': 0,
                'message': 'Maven compilation timeout after 5 minutes',
                'type': 'compilation_timeout',
                'severity': 'error'
            })
        except Exception as e:
            print(f"  ERROR: Maven validation failed: {str(e)}")
            errors.append({
                'file': 'unknown',
                'line': 0,
                'column': 0,
                'message': f'Maven validation error: {str(e)}',
                'type': 'maven_error',
                'severity': 'error'
            })
        finally:
            # Cleanup temp directory
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

        return errors

    def _download_project(self, s3_prefix: str, local_dir: str):
        """Download entire project from S3 to local directory"""
        paginator = self.s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=self.bucket_name, Prefix=s3_prefix)

        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    s3_key = obj['Key']

                    # Skip directories
                    if s3_key.endswith('/'):
                        continue

                    # Calculate local path
                    relative_path = s3_key[len(s3_prefix):].lstrip('/')
                    local_path = os.path.join(local_dir, relative_path)

                    # Create parent directories
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)

                    # Download file
                    self.s3_client.download_file(self.bucket_name, s3_key, local_path)

    def _parse_maven_errors(self, maven_output: str) -> List[Dict]:
        """
        Parse Maven compilation errors into structured format

        Example Maven error:
        [ERROR] /path/to/Foo.java:[123,45] error: cannot find symbol

        Returns:
            List of error dictionaries
        """
        errors = []
        lines = maven_output.split('\n')

        for line in lines:
            if '[ERROR]' in line and '.java:[' in line:
                try:
                    # Extract file path
                    file_match = re.search(r'/([^/]+\.java):\[', line)
                    if not file_match:
                        continue
                    file_name = file_match.group(1)

                    # Extract line and column
                    location_match = re.search(r'\[(\d+),(\d+)\]', line)
                    if not location_match:
                        continue
                    line_num = int(location_match.group(1))
                    column_num = int(location_match.group(2))

                    # Extract error message
                    message_match = re.search(r'\] (.+)$', line)
                    error_message = message_match.group(1) if message_match else 'Unknown compilation error'

                    # Classify error type
                    error_type = self._classify_error(error_message)

                    errors.append({
                        'file': file_name,
                        'line': line_num,
                        'column': column_num,
                        'message': error_message.strip(),
                        'type': error_type,
                        'severity': 'error'
                    })

                except Exception as e:
                    print(f"  WARNING: Could not parse Maven error line: {line}")
                    continue

        return errors

    def _classify_error(self, error_message: str) -> str:
        """Classify Maven error into categories for targeted fixing"""
        error_lower = error_message.lower()

        if 'cannot find symbol' in error_lower:
            return 'missing_symbol'
        elif 'incompatible types' in error_lower:
            return 'type_mismatch'
        elif 'cannot assign' in error_lower and 'final' in error_lower:
            return 'immutability_violation'
        elif 'cannot be applied' in error_lower:
            return 'method_signature'
        elif 'package does not exist' in error_lower:
            return 'missing_import'
        else:
            return 'compilation_error'
