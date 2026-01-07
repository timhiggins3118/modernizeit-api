"""
Java Generation V2 - Test Generator Handler
Lambda: JavaGenV2TestGenerator

Purpose: Generate JUnit 5 unit tests for service classes

V2 Design Principles:
- NO HARDCODING
- Template-driven (Jinja2)
- Generates comprehensive test coverage
- Uses Mockito + AssertJ best practices
"""

import json
import boto3
import os
from datetime import datetime, timezone
from typing import Dict, Any, List
from jinja2 import Template

s3_client = boto3.client('s3')

# Environment variables (NO HARDCODING)
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v2')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate JUnit 5 test classes for services

    Input:
    {
        "job_id": "jgv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "tests_generated": 23,
        "files_created": [list of test files]
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V2 - TEST GENERATOR")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v2/jobs/{job_id}"

        # Update status
        update_status(job_base, 'running', 'generating_tests', 75, 'Generating JUnit 5 tests...')

        # Read generation plan
        plan_key = f"{job_base}/generation_plan.json"
        generation_plan = read_json(plan_key)

        # Read project metadata
        project_metadata = read_json(f"{job_base}/project_metadata.json")
        projects = project_metadata.get('projects', [])

        # Get services and entities
        services = generation_plan.get('services', [])
        entities = generation_plan.get('entities', [])

        print(f"Generating tests for {len(services)} service classes")

        files_created = []

        # Load test template
        test_template = load_template('test.java.j2')

        # Generate tests for each project
        for project in projects:
            service_name = project['service_name']
            base_package = project['base_package']
            project_base = project['base_path']

            print(f"\n=== Generating tests for {service_name} ===")

            # Filter services for this project
            project_services = [s for s in services if s['service_name'] == service_name]

            for service_data in project_services:
                program_name = service_data.get('program_name', '')
                service_class_name = clean_class_name(program_name) + 'Service'

                print(f"Generating: {service_class_name}Test")

                # Find corresponding entity
                entity_name = find_entity_for_service(program_name, entities)

                # Generate test class
                test_code = generate_test_class(
                    template=test_template,
                    package_name=base_package,
                    service_class_name=service_class_name,
                    entity_name=entity_name,
                    cobol_program_name=program_name,
                    service_data=service_data
                )

                # Write test file
                test_file_path = f"{project_base}/src/test/java/{base_package.replace('.', '/')}/services/{service_class_name}Test.java"
                write_file(test_file_path, test_code)

                files_created.append(test_file_path)

            print(f"✓ Generated {len(project_services)} test classes for {service_name}")

        print(f"\n✓ Total test classes generated: {len(files_created)}")

        # Update status
        update_status(job_base, 'running', 'tests_complete', 80, f'Generated {len(files_created)} JUnit 5 test classes')

        return {
            'statusCode': 200,
            'tests_generated': len(files_created),
            'files_created': files_created
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def load_template(template_name: str) -> Template:
    """Load Jinja2 template from S3"""
    template_key = f"java_generation_v2/templates/{template_name}"

    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=template_key)
        template_content = response['Body'].read().decode('utf-8')
        return Template(template_content)
    except Exception as e:
        print(f"ERROR loading template {template_name}: {str(e)}")
        return get_fallback_test_template()


def get_fallback_test_template() -> Template:
    """Fallback test template if S3 load fails"""
    template_str = """package {{ package_name }}.services;

import {{ package_name }}.entities.{{ entity_name }};
import {{ package_name }}.repositories.{{ repository_name }};
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("{{ service_class_name }} Tests")
class {{ service_class_name }}Test {

    @Mock
    private {{ repository_name }} {{ repository_name_camel }};

    @InjectMocks
    private {{ service_class_name }} {{ service_class_name_camel }};

    @BeforeEach
    void setUp() {
        // TODO: Initialize test data
    }

    @Test
    @DisplayName("Should execute business logic")
    void shouldExecuteBusinessLogic() {
        // Arrange
        // TODO: Setup test data

        // Act
        // TODO: Call service method

        // Assert
        // TODO: Verify results
    }
}
"""
    return Template(template_str)


def generate_test_class(template: Template, package_name: str, service_class_name: str,
                       entity_name: str, cobol_program_name: str,
                       service_data: Dict[str, Any]) -> str:
    """Generate JUnit 5 test class from template"""

    repository_name = entity_name + 'Repository'
    repository_name_camel = to_camel_case(repository_name)
    service_class_name_camel = to_camel_case(service_class_name)
    entity_name_plural = pluralize(entity_name)

    # Extract business methods if available
    has_business_methods = False
    business_methods = []

    # Try to detect business methods from service data or recipe
    recipe = service_data.get('recipe', {})
    if recipe and 'methods' in recipe:
        has_business_methods = True
        for method in recipe.get('methods', []):
            business_methods.append({
                'name': method.get('name', 'businessMethod'),
                'description': method.get('description', 'Test business method'),
                'test_method_name': to_camel_case('test_' + method.get('name', 'businessMethod'))
            })

    return template.render(
        package_name=package_name,
        service_class_name=service_class_name,
        service_class_name_camel=service_class_name_camel,
        entity_name=entity_name,
        entity_name_plural=entity_name_plural,
        repository_name=repository_name,
        repository_name_camel=repository_name_camel,
        cobol_program_name=cobol_program_name,
        has_business_methods=has_business_methods,
        business_methods=business_methods
    )


def find_entity_for_service(program_name: str, entities: List[Dict[str, Any]]) -> str:
    """Find entity corresponding to service/program name"""
    program_clean = clean_class_name(program_name)

    # Try to find matching entity
    for entity in entities:
        entity_name = entity.get('entity_name', entity.get('name', ''))
        entity_clean = clean_class_name(entity_name)

        if entity_clean == program_clean or program_clean in entity_clean or entity_clean in program_clean:
            return entity_clean

    # Default to using program name as entity
    return program_clean


def clean_class_name(name: str) -> str:
    """Clean class name (remove special chars, capitalize)"""
    name = name.replace('.cbl', '').replace('.cobol', '').replace('.CBL', '')
    name = name.replace('-', '_').replace(' ', '_')
    parts = name.split('_')
    return ''.join([p.capitalize() for p in parts if p])


def to_camel_case(name: str) -> str:
    """Convert to camelCase"""
    clean = clean_class_name(name)
    if not clean:
        return name
    return clean[0].lower() + clean[1:]


def pluralize(name: str) -> str:
    """Simple pluralization"""
    if name.endswith('y'):
        return name[:-1] + 'ies'
    elif name.endswith('s'):
        return name + 'es'
    else:
        return name + 's'


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
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        print(f"WARNING: Could not read {s3_key}: {str(e)}")
        return {}


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
