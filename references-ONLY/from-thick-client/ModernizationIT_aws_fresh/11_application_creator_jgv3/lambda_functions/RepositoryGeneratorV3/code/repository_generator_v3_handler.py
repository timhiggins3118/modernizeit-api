"""
Java Generation V2 - Repository Generator Handler
Lambda: JavaGenV3RepositoryGenerator

Purpose: Generate Spring Data JPA repository interfaces from ERD

V2 Design Principles:
- NO HARDCODING
- NO EXTERNAL DEPENDENCIES (uses f-strings, not Jinja2)
- Generates from ERD (Data Analyzer V2 output)
- Detects ID types from entity fields
"""

import json
import boto3
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

# Import JavaCodeValidator for self-validation
sys.path.append(os.path.join(os.path.dirname(__file__), 'common'))
from java_code_validator import JavaCodeValidator

s3_client = boto3.client('s3')

# Environment variables (NO HARDCODING)
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v3')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate Spring Data JPA repository interfaces

    Input:
    {
        "job_id": "jgv3_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "repositories_generated": 56,
        "files_created": [list of repository files]
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V2 - REPOSITORY GENERATOR")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v3/jobs/{job_id}"

        # Update status
        update_status(job_base, 'running', 'generating_repositories', 50, 'Generating Spring Data repositories...')

        # Read generation plan
        plan_key = f"{job_base}/generation_plan.json"
        generation_plan = read_json(plan_key)

        # Read project metadata
        project_metadata = read_json(f"{job_base}/project_metadata.json")
        projects = project_metadata.get('projects', [])

        # Get entities from plan
        entities = generation_plan.get('entities', [])

        print(f"Generating {len(entities)} repository interfaces")

        # Initialize code validator for self-validation
        validator = JavaCodeValidator(generation_plan)
        print(f"✓ Code validator initialized")

        files_created = []
        validation_results = []

        # Generate repository for each project
        for project in projects:
            service_name = project['service_name']
            base_package = project['base_package']
            project_base = project['base_path']

            print(f"\n=== Generating repositories for {service_name} ===")

            for entity_data in entities:
                entity_name = entity_data.get('entity_name', entity_data.get('name', 'UnknownEntity'))

                # IMPORTANT: entity_name is already normalized by PrepareJavaGenV3
                # DO NOT call clean_class_name() - it breaks multi-word names!

                print(f"Generating: {entity_name}Repository")

                # Generate repository interface (in-memory, don't write yet)
                repository_code = generate_repository_interface(
                    package_name=base_package,
                    entity_name=entity_name,
                    entity_data=entity_data
                )

                # SELF-VALIDATE: Check generated code BEFORE writing to S3
                repository_name = f"{entity_name}Repository"
                filename = f"{repository_name}.java"
                validation_result = validator.validate_repository(
                    repository_code,
                    repository_name,
                    filename
                )

                # Log validation results
                if not validation_result['valid']:
                    print(f"  ❌ VALIDATION FAILED: {repository_name}")
                    for error in validation_result['errors']:
                        print(f"     ERROR: {error}")
                    # Skip writing invalid file
                    validation_results.append({
                        'repository': repository_name,
                        'status': 'failed',
                        'errors': validation_result['errors'],
                        'warnings': validation_result['warnings']
                    })
                    continue  # Skip this repository

                # Show warnings but allow
                if validation_result['warnings']:
                    print(f"  ⚠️  WARNINGS for {repository_name}:")
                    for warning in validation_result['warnings']:
                        print(f"     {warning}")

                # Validation passed - safe to write
                print(f"  ✅ VALIDATED: {repository_name}")
                repo_file_path = f"{project_base}/src/main/java/{base_package.replace('.', '/')}/repositories/{entity_name}Repository.java"
                write_file(repo_file_path, repository_code)

                files_created.append(repo_file_path)
                validation_results.append({
                    'repository': repository_name,
                    'status': 'passed',
                    'errors': [],
                    'warnings': validation_result['warnings']
                })

            print(f"✓ Generated {len(entities)} repositories for {service_name}")

        print(f"\n✓ Total repositories generated: {len(files_created)}")

        # Report validation summary
        failed_count = len([r for r in validation_results if r['status'] == 'failed'])
        if failed_count > 0:
            print(f"⚠️  {failed_count} repositories failed validation and were skipped")

        # Update status
        update_status(job_base, 'running', 'repositories_complete', 55, f'Generated {len(files_created)} repository interfaces (validated)')

        return {
            'statusCode': 200,
            'repositories_generated': len(files_created),
            'repositories_validated': len(validation_results),
            'repositories_failed_validation': failed_count,
            'files_created': files_created,
            'validation_results': validation_results
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def detect_id_type(entity_data: Dict[str, Any]) -> str:
    """
    Detect the ID field type from entity data
    Looks for the first field (typically the @Id field) and returns its Java type
    """
    fields = entity_data.get('fields', [])

    if not fields or len(fields) == 0:
        print("  WARNING: No fields found in entity, defaulting to Long ID")
        return "Long"

    # First field is typically the ID field in COBOL copybooks
    id_field = fields[0]
    sql_type = id_field.get('type', id_field.get('data_type', 'VARCHAR'))

    # Map SQL type to Java type
    java_type = map_sql_type_to_java(sql_type)

    print(f"  Detected ID type: {java_type} (from SQL type: {sql_type})")
    return java_type


def map_sql_type_to_java(sql_type: str) -> str:
    """
    Map SQL data type to Java type
    Same mapping as Entity Generator and Service Generator
    """
    if not sql_type:
        return "String"

    sql_type_upper = sql_type.upper()

    # Map SQL types to Java types
    if sql_type_upper == 'DECIMAL' or sql_type_upper == 'NUMERIC':
        return 'BigDecimal'
    elif sql_type_upper == 'INTEGER' or sql_type_upper == 'INT':
        return 'Integer'
    elif sql_type_upper == 'BIGINT' or sql_type_upper == 'LONG':
        return 'Long'
    elif sql_type_upper == 'VARCHAR' or sql_type_upper == 'CHAR' or sql_type_upper == 'TEXT':
        return 'String'
    elif sql_type_upper == 'DATE':
        return 'LocalDate'
    elif sql_type_upper == 'TIMESTAMP' or sql_type_upper == 'DATETIME':
        return 'LocalDateTime'
    elif sql_type_upper == 'BOOLEAN' or sql_type_upper == 'BIT':
        return 'Boolean'
    else:
        # Default fallback
        return 'String'


def generate_repository_interface(package_name: str, entity_name: str, entity_data: Dict[str, Any]) -> str:
    """Generate Spring Data JPA repository interface with correct ID type"""

    # Detect ID type from entity fields
    id_type = detect_id_type(entity_data)

    # Use f-string instead of Jinja2 - no external dependencies!
    repository_code = f"""package {package_name}.repositories;

import {package_name}.entities.{entity_name};
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * {entity_name} Repository
 * Spring Data JPA repository for {entity_name} entity
 * Generated from ERD
 */
@Repository
public interface {entity_name}Repository extends JpaRepository<{entity_name}, {id_type}> {{

    // Spring Data JPA will automatically implement basic CRUD operations:
    // - save(entity)
    // - findById(id)
    // - findAll()
    // - delete(entity)
    // - count()

    // Add custom query methods as needed
    // Spring Data JPA will auto-implement based on method naming conventions

    // Example custom queries:
    // List<{entity_name}> findByStatus(String status);
    // Optional<{entity_name}> findByCode(String code);
    // List<{entity_name}> findByNameContaining(String name);
}}
"""

    return repository_code


def clean_class_name(name: str) -> str:
    """Clean class name (remove special chars, capitalize)"""
    name = name.replace('.cbl', '').replace('.cobol', '').replace('.CBL', '')
    name = name.replace('-', '_').replace(' ', '_')
    parts = name.split('_')
    return ''.join([p.capitalize() for p in parts if p])


def write_file(s3_key: str, content: str):
    """Write file to S3"""
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=content,
        ContentType='text/plain'
    )


def read_json(s3_key: str) -> Dict[str, Any]:
    """Read JSON from S3"""
    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
    return json.loads(response['Body'].read().decode('utf-8'))


def update_status(job_base: str, state: str, phase: str, progress: int, message: str):
    """Update job status"""
    try:
        status_key = f"{job_base}/status.json"
        status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
        status_data = json.loads(status_response['Body'].read())

        status_data['state'] = state
        status_data['phase'] = phase
        status_data['progress'] = progress
        status_data['message'] = message
        status_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status: {state} / {phase} ({progress}%) - {message}")
    except Exception as e:
        print(f"ERROR updating status: {str(e)}")
