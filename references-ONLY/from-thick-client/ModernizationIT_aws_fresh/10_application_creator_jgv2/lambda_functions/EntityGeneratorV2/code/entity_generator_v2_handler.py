"""
Java Generation V2 - Entity Generator Handler
Lambda: JavaGenV2EntityGenerator

Purpose: Generate JPA Entity classes from ERD

V2 Design Principles:
- NO HARDCODING
- Template-driven (Jinja2)
- Generates from ERD (Data Analyzer V2 output)
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
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v2')

# Type mapping loaded from S3 (global variable)
TYPE_MAPPING = None


def load_type_mappings() -> Dict[str, str]:
    """
    Load type mappings from S3 shared location

    Returns:
        Dictionary of COBOL/SQL type to Java type mappings
    """
    global TYPE_MAPPING

    if TYPE_MAPPING is not None:
        return TYPE_MAPPING

    try:
        print("Loading type mappings from S3: shared/mappings/type_mappings.json")
        response = s3_client.get_object(
            Bucket=BUCKET_NAME,
            Key='shared/mappings/type_mappings.json'
        )
        mapping_data = json.loads(response['Body'].read().decode('utf-8'))
        TYPE_MAPPING = mapping_data.get('mappings', {})
        print(f"✓ Loaded {len(TYPE_MAPPING)} type mappings")
        return TYPE_MAPPING
    except Exception as e:
        print(f"ERROR loading type mappings from S3: {str(e)}")
        print("Using fallback default mappings")
        # Fallback to basic mappings if S3 read fails
        TYPE_MAPPING = {
            'VARCHAR': 'String',
            'INTEGER': 'Integer',
            'BIGINT': 'Long',
            'DECIMAL': 'BigDecimal',
            'BOOLEAN': 'Boolean',
            'DATE': 'LocalDate',
            'TIMESTAMP': 'LocalDateTime'
        }
        return TYPE_MAPPING


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate JPA Entity classes from ERD

    Input:
    {
        "job_id": "jgv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "entities_generated": 56,
        "files_created": [list of entity class files]
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V2 - ENTITY GENERATOR")
        print("=" * 80)

        # Load type mappings from S3
        load_type_mappings()

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v2/jobs/{job_id}"

        # Update status
        update_status(job_base, 'running', 'generating_entities', 35, 'Generating JPA entity classes...')

        # Read generation plan
        plan_key = f"{job_base}/generation_plan.json"
        generation_plan = read_json(plan_key)

        # Read project metadata
        project_metadata = read_json(f"{job_base}/project_metadata.json")
        projects = project_metadata.get('projects', [])

        # Get entities from plan
        entities = generation_plan.get('entities', [])

        print(f"Generating {len(entities)} entity classes")

        # Initialize code validator for self-validation
        validator = JavaCodeValidator(generation_plan)
        print(f"✓ Code validator initialized")

        files_created = []
        validation_results = []

        # Generate entity for each project (or just one project if monolith)
        for project in projects:
            service_name = project['service_name']
            base_package = project['base_package']
            project_base = project['base_path']

            print(f"\n=== Generating entities for {service_name} ===")

            for entity_data in entities:
                entity_name = entity_data.get('entity_name', entity_data.get('name', 'UnknownEntity'))

                # IMPORTANT: entity_name is already normalized by PrepareJavaGenV2
                # DO NOT call clean_class_name() - it breaks multi-word names!
                # Example: "FinancialReports".capitalize() = "Financialreports" (WRONG!)

                print(f"Generating: {entity_name}")

                # Map COBOL fields to Java fields
                java_fields = map_fields_to_java(entity_data.get('fields', []))

                # Map relationships
                java_relationships = map_relationships_to_java(entity_data.get('relationships', []))

                # Generate entity class from template (in-memory, don't write yet)
                entity_code = generate_entity_class(
                    package_name=base_package,
                    entity_name=entity_name,
                    table_name=entity_data.get('table_name', entity_name.upper()),
                    fields=java_fields,
                    relationships=java_relationships
                )

                # SELF-VALIDATE: Check generated code BEFORE writing to S3
                filename = f"{entity_name}.java"
                validation_result = validator.validate_entity(
                    entity_code,
                    entity_name,
                    filename
                )

                # Log validation results
                if not validation_result['valid']:
                    print(f"  ❌ VALIDATION FAILED: {entity_name}")
                    for error in validation_result['errors']:
                        print(f"     ERROR: {error}")
                    # Skip writing invalid file
                    validation_results.append({
                        'entity': entity_name,
                        'status': 'failed',
                        'errors': validation_result['errors'],
                        'warnings': validation_result['warnings']
                    })
                    continue  # Skip this entity

                # Show warnings but allow
                if validation_result['warnings']:
                    print(f"  ⚠️  WARNINGS for {entity_name}:")
                    for warning in validation_result['warnings']:
                        print(f"     {warning}")

                # Validation passed - safe to write
                print(f"  ✅ VALIDATED: {entity_name}")
                entity_file_path = f"{project_base}/src/main/java/{base_package.replace('.', '/')}/entities/{entity_name}.java"
                write_file(entity_file_path, entity_code)

                files_created.append(entity_file_path)
                validation_results.append({
                    'entity': entity_name,
                    'status': 'passed',
                    'errors': [],
                    'warnings': validation_result['warnings']
                })

            print(f"✓ Generated {len(entities)} entities for {service_name}")

        print(f"\n✓ Total entities generated: {len(files_created)}")

        # Report validation summary
        failed_count = len([r for r in validation_results if r['status'] == 'failed'])
        if failed_count > 0:
            print(f"⚠️  {failed_count} entities failed validation and were skipped")

        # Update status
        update_status(job_base, 'running', 'entities_complete', 40, f'Generated {len(files_created)} entity classes (validated)')

        return {
            'statusCode': 200,
            'entities_generated': len(files_created),
            'entities_validated': len(validation_results),
            'entities_failed_validation': failed_count,
            'files_created': files_created,
            'validation_results': validation_results
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def map_fields_to_java(cobol_fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map COBOL fields to Java fields with types"""
    java_fields = []

    for idx, field in enumerate(cobol_fields):
        field_name = field.get('field_name', field.get('name', f'field{idx}'))
        cobol_type = field.get('type', field.get('cobol_type', 'PIC X'))

        # Map COBOL type to Java type
        java_type = map_cobol_type_to_java(cobol_type)

        # Read primary key and ID generation strategy from PrepareJavaGenV2
        # (PrepareJavaGenV2 determines these intelligently)
        is_primary_key = field.get('is_primary_key', False)
        id_generation_strategy = field.get('id_generation_strategy', None)

        java_fields.append({
            'field_name': camel_case(field_name),
            'column_name': field.get('column_name', field_name.upper().replace('-', '_')),
            'java_type': java_type,
            'nullable': field.get('nullable', True),
            'is_primary_key': is_primary_key,
            'id_generation_strategy': id_generation_strategy,  # Pass through from PrepareJavaGenV2
            'length': field.get('length', None)
        })

    return java_fields


def map_cobol_type_to_java(cobol_type: str) -> str:
    """Map COBOL data type to Java type"""
    # Normalize type
    cobol_type_upper = cobol_type.upper().strip()

    # Direct mapping
    if cobol_type_upper in TYPE_MAPPING:
        return TYPE_MAPPING[cobol_type_upper]

    # Pattern matching
    if 'COMP-3' in cobol_type_upper or 'V99' in cobol_type_upper:
        return 'BigDecimal'
    elif 'PIC 9' in cobol_type_upper and 'COMP' in cobol_type_upper:
        return 'Long'
    elif 'PIC 9' in cobol_type_upper:
        # Check length
        if '(9)' in cobol_type_upper or '(8)' in cobol_type_upper:
            return 'Long'
        else:
            return 'Integer'
    elif 'PIC X' in cobol_type_upper or 'PIC A' in cobol_type_upper:
        return 'String'
    elif 'DATE' in cobol_type_upper:
        return 'LocalDate'
    elif 'TIME' in cobol_type_upper:
        return 'LocalDateTime'
    else:
        # Default to String for unknown types
        return 'String'


def map_relationships_to_java(relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map ERD relationships to JPA relationships"""
    java_relationships = []

    for rel in relationships:
        rel_type = rel.get('type', rel.get('relationship_type', 'OneToMany'))
        target = rel.get('target', rel.get('target_entity', 'UnknownEntity'))

        java_relationships.append({
            'type': rel_type,
            'target_entity': clean_class_name(target),
            'field_name': camel_case(target) + 's' if 'Many' in rel_type else camel_case(target),
            'mapped_by': rel.get('mapped_by', camel_case(target)),
            'join_column': rel.get('join_column', target.lower() + '_id')
        })

    return java_relationships


def generate_entity_class(package_name: str, entity_name: str, table_name: str,
                           fields: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> str:
    """Generate JPA entity class from template"""
    template_str = """package {{ package_name }}.entities;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * {{ entity_name }} Entity
 * Generated from COBOL data structure via ERD
 * Table: {{ table_name }}
 */
@Entity
@Table(name = "{{ table_name }}")
@Data
@NoArgsConstructor
@AllArgsConstructor
public class {{ entity_name }} {

    {% for field in fields %}
    {% if field.is_primary_key %}
    @Id
    {% if field.id_generation_strategy == 'IDENTITY' %}
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    {% endif %}
    {% endif %}
    {% if not field.nullable %}
    @Column(name = "{{ field.column_name }}", nullable = false{% if field.length %}, length = {{ field.length }}{% endif %})
    {% else %}
    @Column(name = "{{ field.column_name }}"{% if field.length %}, length = {{ field.length }}{% endif %})
    {% endif %}
    private {{ field.java_type }} {{ field.field_name }};
    {% if not loop.last %}

    {% endif %}
    {% endfor %}

    {% for relationship in relationships %}
    {% if relationship.type == 'OneToMany' %}
    @OneToMany(mappedBy = "{{ relationship.mapped_by }}", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private List<{{ relationship.target_entity }}> {{ relationship.field_name }};
    {% elif relationship.type == 'ManyToOne' %}
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "{{ relationship.join_column }}")
    private {{ relationship.target_entity }} {{ relationship.field_name }};
    {% endif %}
    {% if not loop.last %}

    {% endif %}
    {% endfor %}
}
"""

    template = Template(template_str)
    return template.render(
        package_name=package_name,
        entity_name=entity_name,
        table_name=table_name,
        fields=fields,
        relationships=relationships
    )


def clean_class_name(name: str) -> str:
    """Clean class name (remove special chars, capitalize)"""
    # Remove file extension
    name = name.replace('.cbl', '').replace('.cobol', '').replace('.CBL', '')

    # Remove special characters
    name = name.replace('-', '_').replace(' ', '_')

    # Convert to PascalCase
    parts = name.split('_')
    return ''.join([p.capitalize() for p in parts if p])


def camel_case(name: str) -> str:
    """Convert to camelCase"""
    # Remove special characters
    name = name.replace('-', '_').replace(' ', '_')

    parts = name.split('_')
    if len(parts) == 0:
        return name

    # First part lowercase, rest capitalized
    return parts[0].lower() + ''.join([p.capitalize() for p in parts[1:] if p])


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
