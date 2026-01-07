"""
Java Generation V2 - API Generator Handler
Lambda: JavaGenV3APIGenerator

Purpose: Generate REST controller classes from API patterns and microservice boundaries

V2 Design Principles:
- NO HARDCODING
- Template-driven (Jinja2)
- Generates from Discovery V2 API patterns
- Maps to microservice boundaries
"""

import json
import boto3
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List
from jinja2 import Template

# Import JavaCodeValidator for self-validation
sys.path.append(os.path.join(os.path.dirname(__file__), 'common'))
from java_code_validator import JavaCodeValidator

s3_client = boto3.client('s3')

# Environment variables (NO HARDCODING)
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v3')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate REST controller classes from API patterns

    Input:
    {
        "job_id": "jgv3_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "controllers_generated": 12,
        "files_created": [list of controller files]
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V2 - API GENERATOR")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v3/jobs/{job_id}"

        # Update status
        update_status(job_base, 'running', 'generating_apis', 65, 'Generating REST API controllers...')

        # Read generation plan
        plan_key = f"{job_base}/generation_plan.json"
        generation_plan = read_json(plan_key)

        # Read project metadata
        project_metadata = read_json(f"{job_base}/project_metadata.json")

        # V3 uses Modular Monolith with domains, not separate projects
        base_package = project_metadata.get('base_package', 'com.modernized.application')
        project_base = project_metadata.get('project_base', job_base)
        project_name = project_metadata.get('project_name', 'ModernizedApplication')

        # Read input artifacts
        input_ref = read_json(f"{job_base}/input_ref.json")

        # Read API patterns from Discovery V2
        api_patterns_key = input_ref['artifacts'].get('api_patterns', '')
        api_patterns = read_json(api_patterns_key)

        # Read microservice boundaries from Dependency Mapper V2
        microservice_boundaries_key = input_ref['artifacts'].get('microservice_boundaries', '')
        microservice_boundaries = read_json(microservice_boundaries_key)

        # Read business processes for business capability mapping
        business_processes_key = input_ref['artifacts'].get('business_processes', '')
        business_processes = read_json(business_processes_key)

        # Get entities from generation plan
        entities = generation_plan.get('entities', [])

        print(f"Project: {project_name}")
        print(f"Base package: {base_package}")
        print(f"API Patterns found: {len(api_patterns.get('api_patterns', []))}")
        print(f"Entities available: {len(entities)}")

        # Initialize code validator for self-validation
        validator = JavaCodeValidator(generation_plan)
        print(f"✓ Code validator initialized")

        files_created = []
        validation_results = []

        # Load controller template
        controller_template = load_template('controller.java.j2')

        print(f"\n=== Generating API controllers ===")

        # Filter API patterns (for monolith, we use all patterns)
        service_api_patterns = api_patterns.get('api_patterns', [])

        # Generate controllers based on entities and API patterns
        for entity_data in entities:
            entity_name = entity_data.get('entity_name', entity_data.get('name', 'UnknownEntity'))

            # IMPORTANT: entity_name is already normalized by PrepareJavaGenV3
            # DO NOT call clean_class_name() - it breaks multi-word names!

            # Check if this entity has API patterns
            entity_api = find_entity_api_pattern(service_api_patterns, entity_name)

            if entity_api or len(service_api_patterns) == 0:
                # Generate controller for this entity
                print(f"Generating: {entity_name}Controller")

                # Determine resource path
                resource_path = entity_api.get('resource_path', '') if entity_api else to_kebab_case(entity_name) + 's'

                # Get business capability
                business_capability = get_business_capability(business_processes, entity_name)

                # Generate controller code (in-memory, don't write yet)
                controller_code = generate_controller(
                    template=controller_template,
                    package_name=base_package,
                    entity_name=entity_name,
                    service_name=entity_name + 'Service',
                    resource_path=resource_path,
                    business_capability=business_capability,
                    api_pattern=entity_api
                )

                # SELF-VALIDATE: Check generated code BEFORE writing to S3
                controller_name = f"{entity_name}Controller"
                filename = f"{controller_name}.java"
                validation_result = validator.validate_controller(
                    controller_code,
                    controller_name,
                    filename
                )

                # Log validation results
                if not validation_result['valid']:
                    print(f"  ❌ VALIDATION FAILED: {controller_name}")
                    for error in validation_result['errors']:
                        print(f"     ERROR: {error}")
                    # Skip writing invalid file
                    validation_results.append({
                        'controller': controller_name,
                        'status': 'failed',
                        'errors': validation_result['errors'],
                        'warnings': validation_result['warnings']
                    })
                    continue  # Skip this controller

                # Show warnings but allow
                if validation_result['warnings']:
                    print(f"  ⚠️  WARNINGS for {controller_name}:")
                    for warning in validation_result['warnings']:
                        print(f"     {warning}")

                # Validation passed - safe to write
                print(f"  ✅ VALIDATED: {controller_name}")
                controller_file_path = f"{project_base}/src/main/java/{base_package.replace('.', '/')}/controllers/{entity_name}Controller.java"
                write_file(controller_file_path, controller_code)

                files_created.append(controller_file_path)
                validation_results.append({
                    'controller': controller_name,
                    'status': 'passed',
                    'errors': [],
                    'warnings': validation_result['warnings']
                })

        print(f"\n✓ Total API controllers generated: {len(files_created)}")

        # Report validation summary
        failed_count = len([r for r in validation_results if r['status'] == 'failed'])
        if failed_count > 0:
            print(f"⚠️  {failed_count} controllers failed validation and were skipped")

        # Update status
        update_status(job_base, 'running', 'apis_complete', 70, f'Generated {len(files_created)} REST controllers (validated)')

        return {
            'statusCode': 200,
            'controllers_generated': len(files_created),
            'controllers_validated': len(validation_results),
            'controllers_failed_validation': failed_count,
            'files_created': files_created,
            'validation_results': validation_results
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def load_template(template_name: str) -> Template:
    """Load Jinja2 template from S3"""
    template_key = f"java_generation_v3/templates/{template_name}"

    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=template_key)
        template_content = response['Body'].read().decode('utf-8')
        return Template(template_content)
    except Exception as e:
        print(f"ERROR loading template {template_name}: {str(e)}")
        # Return inline template as fallback
        return get_fallback_controller_template()


def get_fallback_controller_template() -> Template:
    """Fallback controller template if S3 load fails"""
    template_str = """package {{ package_name }}.controllers;

import {{ package_name }}.entities.{{ entity_name }};
import {{ package_name }}.services.{{ service_name }};
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import jakarta.validation.Valid;
import java.util.List;
import java.util.Optional;

/**
 * {{ entity_name }} REST Controller
 * Provides REST API endpoints for {{ business_capability }}
 */
@RestController
@RequestMapping("/api/v1/{{ resource_path }}")
@RequiredArgsConstructor
@Slf4j
@CrossOrigin(origins = "*")
public class {{ entity_name }}Controller {

    private final {{ service_name }} {{ service_name_camel }};

    @GetMapping
    public ResponseEntity<List<{{ entity_name }}>> getAll() {
        log.info("GET /api/v1/{{ resource_path }} - Get all {{ entity_name_plural }}");
        List<{{ entity_name }}> results = {{ service_name_camel }}.findAll();
        return ResponseEntity.ok(results);
    }

    @GetMapping("/{id}")
    public ResponseEntity<{{ entity_name }}> getById(@PathVariable Long id) {
        log.info("GET /api/v1/{{ resource_path }}/{} - Get {{ entity_name }} by ID", id);
        return {{ service_name_camel }}.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    public ResponseEntity<{{ entity_name }}> create(@Valid @RequestBody {{ entity_name }} {{ entity_name_camel }}) {
        log.info("POST /api/v1/{{ resource_path }} - Create {{ entity_name }}");
        {{ entity_name }} saved = {{ service_name_camel }}.save({{ entity_name_camel }});
        return ResponseEntity.status(HttpStatus.CREATED).body(saved);
    }

    @PutMapping("/{id}")
    public ResponseEntity<{{ entity_name }}> update(
            @PathVariable Long id,
            @Valid @RequestBody {{ entity_name }} {{ entity_name_camel }}) {
        log.info("PUT /api/v1/{{ resource_path }}/{} - Update {{ entity_name }}", id);
        if (!{{ service_name_camel }}.findById(id).isPresent()) {
            return ResponseEntity.notFound().build();
        }
        {{ entity_name }} updated = {{ service_name_camel }}.save({{ entity_name_camel }});
        return ResponseEntity.ok(updated);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        log.info("DELETE /api/v1/{{ resource_path }}/{} - Delete {{ entity_name }}", id);
        if (!{{ service_name_camel }}.findById(id).isPresent()) {
            return ResponseEntity.notFound().build();
        }
        {{ service_name_camel }}.deleteById(id);
        return ResponseEntity.noContent().build();
    }
}
"""
    return Template(template_str)


def generate_controller(template: Template, package_name: str, entity_name: str,
                       service_name: str, resource_path: str, business_capability: str,
                       api_pattern: Dict[str, Any] = None) -> str:
    """Generate REST controller code from template"""

    entity_name_plural = pluralize(entity_name)
    service_name_camel = to_camel_case(service_name)
    entity_name_camel = to_camel_case(entity_name)

    return template.render(
        package_name=package_name,
        entity_name=entity_name,
        service_name=service_name,
        resource_path=resource_path,
        entity_name_plural=entity_name_plural,
        service_name_camel=service_name_camel,
        entity_name_camel=entity_name_camel,
        business_capability=business_capability
    )


def get_service_api_patterns(api_patterns: Dict[str, Any],
                            microservice_boundaries: Dict[str, Any],
                            service_name: str) -> List[Dict[str, Any]]:
    """Get API patterns for a specific microservice"""
    patterns = api_patterns.get('api_patterns', [])

    # Find service boundary
    boundaries = microservice_boundaries.get('boundaries', [])
    service_boundary = None

    for boundary in boundaries:
        if boundary.get('service_name', '') == service_name:
            service_boundary = boundary
            break

    if not service_boundary:
        return []

    # Filter patterns by business capability
    service_capabilities = service_boundary.get('business_capabilities', [])
    service_patterns = []

    for pattern in patterns:
        pattern_capability = pattern.get('business_capability', '')
        if pattern_capability in service_capabilities:
            service_patterns.append(pattern)

    return service_patterns


def find_entity_api_pattern(api_patterns: List[Dict[str, Any]], entity_name: str) -> Dict[str, Any]:
    """Find API pattern matching entity name"""
    entity_lower = entity_name.lower()

    for pattern in api_patterns:
        resource = pattern.get('resource', '').lower()
        endpoint = pattern.get('endpoint', '').lower()

        if entity_lower in resource or entity_lower in endpoint:
            return pattern

    return None


def get_business_capability(business_processes: Dict[str, Any], entity_name: str) -> str:
    """Get business capability description for entity"""
    if not business_processes or 'processes' not in business_processes:
        return f"{entity_name} management"

    entity_lower = entity_name.lower()

    for process in business_processes.get('processes', []):
        process_name = process.get('name', '').lower()
        if entity_lower in process_name:
            return process.get('description', f"{entity_name} management")

    return f"{entity_name} management"


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


def to_kebab_case(name: str) -> str:
    """Convert to kebab-case"""
    import re
    # Insert hyphens before uppercase letters
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()


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
