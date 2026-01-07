"""
Java Generation V2 - Service Generator Handler
Lambda: JavaGenV2ServiceGenerator

Purpose: Generate Java service classes from COBOL using AI and Refactor Recipes

V2 Design Principles:
- NO HARDCODING
- AI-POWERED (Bedrock Claude 3.5 Sonnet)
- Recipe-driven transformation
- THIS IS THE CROWN JEWEL OF JAVA GENERATION V2
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
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

# Environment variables (NO HARDCODING)
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v2')
BEDROCK_MODEL_ID = 'anthropic.claude-3-5-sonnet-20240620-v1:0'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate Java service classes using AI + Refactor Recipes

    Input:
    {
        "job_id": "jgv2_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "services_generated": 23,
        "ai_powered": 18,
        "template_fallback": 5
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V2 - SERVICE GENERATOR (AI-POWERED)")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v2/jobs/{job_id}"

        # Update status
        update_status(job_base, 'running', 'generating_services', 45, 'Generating service classes with AI...')

        # Read generation plan
        plan_key = f"{job_base}/generation_plan.json"
        generation_plan = read_json(plan_key)

        # Read project metadata
        project_metadata = read_json(f"{job_base}/project_metadata.json")
        projects = project_metadata.get('projects', [])

        # Get services to generate
        services = generation_plan.get('services', [])
        recipe_mapping = generation_plan.get('recipe_mapping', {})
        entities = generation_plan.get('entities', [])  # Get entity list for AI prompt

        # Read COBOL source files and static analysis
        input_ref = read_json(f"{job_base}/input_ref.json")
        source_hash = input_ref.get('source_hash', '')

        static_analysis_key = input_ref['artifacts'].get('static_analysis', '')
        static_analysis = read_json(static_analysis_key)

        # Read business processes for context
        business_processes_key = input_ref['artifacts'].get('business_processes', '')
        business_processes = read_json(business_processes_key)

        print(f"Generating {len(services)} service classes")

        # Initialize code validator for self-validation
        validator = JavaCodeValidator(generation_plan)
        print(f"✓ Code validator initialized")

        ai_powered_count = 0
        template_fallback_count = 0
        files_created = []
        validation_results = []

        # Generate services for each project
        for project in projects:
            service_name = project['service_name']
            base_package = project['base_package']
            project_base = project['base_path']

            print(f"\n=== Generating services for {service_name} ===")

            # Filter services for this project
            # If services have 'default' service_name, assign them to first/only project
            project_services = [
                s for s in services
                if s['service_name'] == service_name or s['service_name'] == 'default'
            ]

            for service_data in project_services:
                program_name = service_data.get('program_name', '')
                has_recipe = service_data.get('has_recipe', False)
                recipe = service_data.get('recipe', None)

                print(f"\nGenerating service for: {program_name}")

                # Get COBOL source
                cobol_source = get_cobol_source(scout_account_id, application_name, source_hash, program_name)

                # Get business context
                business_context = get_business_context(business_processes, program_name)

                # Get program analysis
                program_analysis = get_program_analysis(static_analysis, program_name)

                # Generate service class
                if has_recipe and recipe and cobol_source:
                    # AI-POWERED GENERATION
                    print(f"  Using AI with recipe: {recipe.get('recipe_type', 'unknown')}")

                    service_code = generate_service_with_ai(
                        program_name=program_name,
                        cobol_source=cobol_source,
                        recipe=recipe,
                        business_context=business_context,
                        program_analysis=program_analysis,
                        base_package=base_package,
                        entities=entities
                    )

                    ai_powered_count += 1
                else:
                    # TEMPLATE FALLBACK
                    print(f"  Using template fallback (no recipe or source)")

                    service_code = generate_service_from_template(
                        program_name=program_name,
                        program_analysis=program_analysis,
                        base_package=base_package
                    )

                    template_fallback_count += 1

                # SELF-VALIDATE: Check generated code BEFORE writing to S3
                service_class_name = clean_class_name(program_name) + 'Service'
                filename = f"{service_class_name}.java"
                validation_result = validator.validate_service(
                    service_code,
                    service_class_name,
                    filename
                )

                # Log validation results
                if not validation_result['valid']:
                    print(f"  ❌ VALIDATION FAILED: {service_class_name}")
                    for error in validation_result['errors']:
                        print(f"     ERROR: {error}")
                    # Skip writing invalid file
                    validation_results.append({
                        'service': service_class_name,
                        'status': 'failed',
                        'errors': validation_result['errors'],
                        'warnings': validation_result['warnings']
                    })
                    continue  # Skip this service

                # Show warnings but allow
                if validation_result['warnings']:
                    print(f"  ⚠️  WARNINGS for {service_class_name}:")
                    for warning in validation_result['warnings']:
                        print(f"     {warning}")

                # Validation passed - safe to write
                print(f"  ✅ VALIDATED: {service_class_name}")
                service_file_path = f"{project_base}/src/main/java/{base_package.replace('.', '/')}/services/{service_class_name}.java"

                write_file(service_file_path, service_code)
                files_created.append(service_file_path)
                validation_results.append({
                    'service': service_class_name,
                    'status': 'passed',
                    'errors': [],
                    'warnings': validation_result['warnings']
                })

                print(f"  Generated: {service_class_name}")

            # ALSO GENERATE ENTITY-BASED CRUD SERVICES
            # These are needed by the REST controllers
            print(f"\n=== Generating entity-based CRUD services for {service_name} ===")

            for entity_data in entities:
                entity_name = entity_data.get('entity_name', entity_data.get('name', 'UnknownEntity'))

                # IMPORTANT: entity_name is already normalized by PrepareJavaGenV2
                # DO NOT call clean_class_name() - it breaks multi-word names!

                print(f"\nGenerating entity service for: {entity_name}")

                # Generate entity-based CRUD service (in-memory, don't write yet)
                entity_service_code = generate_entity_service(
                    entity_class_name=entity_name,
                    entity_data=entity_data,
                    base_package=base_package
                )

                # SELF-VALIDATE: Check generated code BEFORE writing to S3
                entity_service_class_name = entity_name + 'Service'
                filename = f"{entity_service_class_name}.java"
                validation_result = validator.validate_service(
                    entity_service_code,
                    entity_service_class_name,
                    filename
                )

                # Log validation results
                if not validation_result['valid']:
                    print(f"  ❌ VALIDATION FAILED: {entity_service_class_name}")
                    for error in validation_result['errors']:
                        print(f"     ERROR: {error}")
                    # Skip writing invalid file
                    validation_results.append({
                        'service': entity_service_class_name,
                        'status': 'failed',
                        'errors': validation_result['errors'],
                        'warnings': validation_result['warnings']
                    })
                    continue  # Skip this service

                # Show warnings but allow
                if validation_result['warnings']:
                    print(f"  ⚠️  WARNINGS for {entity_service_class_name}:")
                    for warning in validation_result['warnings']:
                        print(f"     {warning}")

                # Validation passed - safe to write
                print(f"  ✅ VALIDATED: {entity_service_class_name}")
                entity_service_file_path = f"{project_base}/src/main/java/{base_package.replace('.', '/')}/services/{entity_service_class_name}.java"

                write_file(entity_service_file_path, entity_service_code)
                files_created.append(entity_service_file_path)
                validation_results.append({
                    'service': entity_service_class_name,
                    'status': 'passed',
                    'errors': [],
                    'warnings': validation_result['warnings']
                })

        print(f"\n✓ Total services generated: {len(files_created)}")
        print(f"  AI-powered: {ai_powered_count}")
        print(f"  Template fallback: {template_fallback_count}")

        # Report validation summary
        failed_count = len([r for r in validation_results if r['status'] == 'failed'])
        if failed_count > 0:
            print(f"⚠️  {failed_count} services failed validation and were skipped")

        # Update status
        update_status(job_base, 'running', 'services_complete', 60, f'Generated {len(files_created)} service classes (validated, {ai_powered_count} AI-powered)')

        return {
            'statusCode': 200,
            'services_generated': len(files_created),
            'services_validated': len(validation_results),
            'services_failed_validation': failed_count,
            'ai_powered': ai_powered_count,
            'template_fallback': template_fallback_count,
            'files_created': files_created,
            'validation_results': validation_results
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def generate_service_with_ai(program_name: str, cobol_source: str, recipe: Dict[str, Any],
                              business_context: str, program_analysis: Dict[str, Any],
                              base_package: str, entities: List[Dict[str, Any]]) -> str:
    """
    Generate Java service class using Bedrock AI + Recipe

    THIS IS THE MAGIC - AI transforms COBOL to modern Java using recipes
    """
    print(f"    Calling Bedrock AI for {program_name}...")

    # Build comprehensive prompt
    prompt = build_ai_service_prompt(
        program_name=program_name,
        cobol_source=cobol_source,
        recipe=recipe,
        business_context=business_context,
        program_analysis=program_analysis,
        base_package=base_package,
        entities=entities
    )

    # Call Bedrock
    service_code = call_bedrock(prompt)

    # Validate generated code
    if not service_code or len(service_code) < 100:
        print(f"    WARNING: AI generated code too short, using fallback")
        return generate_service_from_template(program_name, program_analysis, base_package)

    return service_code


def format_entity_fields_with_types(entity: Dict[str, Any]) -> str:
    """Format entity fields with their types for AI prompt - SHOW ALL FIELDS"""
    fields = entity.get('fields', [])  # NO LIMIT - show all fields!
    field_strings = []
    for f in fields:
        field_name = camel_case(f.get('name', f.get('field_name', 'unknown')))
        field_type = map_sql_type_to_java(f.get('type', f.get('data_type', 'String')))
        field_strings.append(f"{field_name}:{field_type}")
    return ', '.join(field_strings)


def build_ai_service_prompt(program_name: str, cobol_source: str, recipe: Dict[str, Any],
                             business_context: str, program_analysis: Dict[str, Any],
                             base_package: str, entities: List[Dict[str, Any]]) -> str:
    """Build comprehensive AI prompt for service generation"""

    recipe_type = recipe.get('recipe_type', 'standard_transformation')
    java_recipe = recipe.get('java_recipe', {})
    confidence = recipe.get('confidence', 0.0)

    # Build entity list with types (separate from f-string to avoid nesting issues)
    entity_list_lines = []
    for e in entities:
        if e.get('entity_name') or e.get('name'):
            # IMPORTANT: entity_name is already normalized by PrepareJavaGenV2
            # DO NOT call clean_class_name() - it breaks multi-word names!
            entity_name = e.get('entity_name', e.get('name', 'Unknown'))
            table_name = e.get('table_name', 'UNKNOWN')
            fields_with_types = format_entity_fields_with_types(e)
            entity_list_lines.append(f"- {entity_name} (table: {table_name})")
            entity_list_lines.append(f"  Fields: {fields_with_types}")

    entity_list = '\n'.join(entity_list_lines)

    prompt = f"""You are a COBOL-to-Java transformation expert specializing in modern design patterns.

**COBOL PROGRAM:** {program_name}

**BUSINESS CONTEXT:**
{business_context}

**PROGRAM ANALYSIS:**
- Lines of Code: {program_analysis.get('loc', 0)}
- Cyclomatic Complexity: {program_analysis.get('complexity', 0)}
- Data Flow: {json.dumps(program_analysis.get('data_flow', {}), indent=2)}

**TRANSFORMATION RECIPE:**
- Type: {recipe_type}
- Confidence: {confidence}
- Recommended Pattern: {java_recipe.get('action', 'Standard transformation')}
- Implementation: {java_recipe.get('implementation', 'Standard service class')}

**COBOL SOURCE CODE:**
```cobol
{cobol_source[:3000]}
```

**AVAILABLE ENTITY CLASSES (VALIDATED):**
The following entity classes are VALIDATED and available in the {base_package}.entities package.
These are the ONLY classes you may use. Entity names are EXACT and case-sensitive.

{entity_list}

**CRITICAL LOMBOK RULES - ENTITIES USE @Data AND @AllArgsConstructor:**
All entities use Lombok @Data, @NoArgsConstructor, @AllArgsConstructor which generates:
- Getters: getFieldName() - ALWAYS use this format
- Setters: setFieldName(value) - ALWAYS use this format
- NEVER call fieldName() directly - this method does NOT exist
- Example for field "acctNo": use entity.getAcctNo() NOT entity.acctNo()
- Example for field "acctLimit": use entity.getAcctLimit() NOT entity.acctLimit()
- Example for field "tableMax": use flags.getTableMax() NOT flags.tableMax()

**CRITICAL ENTITY CONSTRUCTOR RULES:**
Entities have @AllArgsConstructor which generates a constructor with ALL fields in order:
- new EntityName(field1, field2, field3, ...) - ALL fields must be provided in EXACT order shown in Fields list
- Example: Flags entity has fields (lastrec:String, tableVar:Integer, tableMax:Integer)
  - CORRECT: new Flags("Y", 5, 45)
  - WRONG: new Flags("Y", "Y", 5, 45) ❌ - too many parameters
- If you need to create an entity, list ONLY the fields from the Fields list in EXACT order
- Entities do NOT have an "id" constructor parameter unless "id" is shown in Fields list

**CRITICAL RULES YOU MUST FOLLOW:**
1. ONLY use entity class names from the VALIDATED list above - NEVER invent entity names
   - ✅ Use: Accounts, Flags, FinancialReports (if in list)
   - ❌ NEVER invent: TlimitTbalance, AccountRecord, CustomerData (if NOT in list)

2. Entity names are EXACT and case-sensitive (e.g., ClientsPerState NOT Clientsperstate)

3. ALL entity field access MUST use Lombok getters/setters:
   - Reading: entity.getFieldName() - NEVER entity.fieldName()
   - Writing: entity.setFieldName(value) - NEVER entity.fieldName(value)
   - Example: account.getAcctNo() ✅ NOT account.acctNo() ❌
   - Example: flags.getTableMax() ✅ NOT flags.tableMax() ❌

4. Field names must EXACTLY match the Fields list - do NOT add suffixes or modify names:
   - If Fields list shows "acctLimit:BigDecimal", use entity.getAcctLimit() ✅
   - NEVER invent: entity.getAcctLimitO() ❌ (unless "acctLimitO" is in Fields list)
   - If entity FinancialReports has "acctLimitO" in its Fields, then use getAcctLimitO()
   - Always check the Fields list for the SPECIFIC entity you're working with

5. If you don't see a field in the Fields list above, that getter/setter does NOT exist
   - Do NOT assume fields exist - check the list first
   - Do NOT create setters for fields that don't exist in the entity

6. Entity constructors must match the Fields list EXACTLY:
   - Count the fields, use ALL of them in order
   - Do NOT add extra parameters like "id" unless "id" is explicitly in Fields list
   - Example: If Flags has 3 fields (lastrec, tableVar, tableMax), use new Flags(str, int, int)

**CRITICAL JAVA TIME/DATE RULES:**
- LocalDate: has getYear(), getMonthValue(), getDayOfMonth() ✅
  - LocalDate does NOT have getHour(), getMinute(), getSecond() ❌
- LocalDateTime: has getYear(), getMonthValue(), getDayOfMonth(), getHour(), getMinute(), getSecond() ✅
- For current date AND time: use LocalDateTime.now() NOT LocalDate.now()
- For date formatting with time: use LocalDateTime.format(DateTimeFormatter.ofPattern("HHmmss"))
- Example correct usage:
  ```java
  LocalDateTime now = LocalDateTime.now();
  int hour = now.getHour();
  int minute = now.getMinute();
  int second = now.getSecond();
  ```

**CRITICAL JAVA/JPA REQUIREMENTS:**
- Use jakarta.persistence imports (NOT javax.persistence - this is Spring Boot 3+)
- Use exact entity class names in PascalCase from the VALIDATED list above
- Use exact field names AND types shown above (e.g., acctLimit:BigDecimal means use BigDecimal, not String or Integer)
- When calling setters, ensure the value type matches the field type (e.g., BigDecimal for DECIMAL fields)
- Import: import jakarta.persistence.EntityManager; import jakarta.persistence.PersistenceContext;
- For numeric conversions: new BigDecimal("value") for BigDecimal fields, Integer.parseInt() for Integer fields

**CRITICAL ERROR PREVENTION CHECKLIST:**
Before generating code, verify:
1. ✓ All entity names are from the VALIDATED list (no invented entities)
2. ✓ All field accesses use getFieldName() format (NEVER fieldName())
3. ✓ All field names match Fields list EXACTLY (no suffixes like "O" unless in list)
4. ✓ Entity constructors have correct number of parameters matching Fields list
5. ✓ LocalDateTime used for time operations (NOT LocalDate.getHour())
6. ✓ No getId() calls unless entity has "id" field in Fields list

**TASK:**
Generate a complete Spring Boot @Service class that:
1. Implements the COBOL business logic using the recommended pattern: {recipe_type}
2. Uses JPA entities for data access (from the list above - use exact names)
3. Applies the transformation recipe: {java_recipe.get('action', 'standard')}
4. Includes proper error handling and validation
5. Is unit testable (dependency injection)
6. Uses Java 17+ features (records, switch expressions, etc. where appropriate)
7. Includes comprehensive JavaDoc comments

**IMPORTANT TRANSFORMATIONS:**
{java_recipe.get('implementation', 'Standard COBOL to Java transformation')}

**OUTPUT REQUIREMENTS:**
- Package: {base_package}.services
- Class name: {clean_class_name(program_name)}Service
- @Service annotation
- Constructor injection for dependencies
- Business methods from COBOL PROCEDURE DIVISION
- NO System.out.println (use logging)
- Professional, production-ready code

Generate ONLY the complete Java service class code. No explanations.
"""

    return prompt


def call_bedrock(prompt: str) -> str:
    """Call AWS Bedrock Claude 3.5 Sonnet"""
    try:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4000,
            "temperature": 0.0,  # Deterministic for code generation
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())
        generated_code = response_body['content'][0]['text']

        # Extract code if wrapped in markdown
        if '```java' in generated_code:
            parts = generated_code.split('```java')
            if len(parts) > 1:
                code_part = parts[1].split('```')[0]
                return code_part.strip()

        return generated_code

    except Exception as e:
        print(f"    ERROR calling Bedrock: {str(e)}")
        return ""


def generate_service_from_template(program_name: str, program_analysis: Dict[str, Any],
                                   base_package: str) -> str:
    """Generate basic service class from template (fallback)"""
    class_name = clean_class_name(program_name) + 'Service'

    return f"""package {base_package}.services;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

/**
 * {class_name}
 * Generated from COBOL program: {program_name}
 * Template-based generation (fallback)
 */
@Service
@Transactional
@RequiredArgsConstructor
@Slf4j
public class {class_name} {{

    // TODO: Add repository dependencies via constructor injection

    /**
     * Main business logic method
     * Implement business logic from COBOL PROCEDURE DIVISION
     */
    public void processBusinessLogic() {{
        log.info("Processing business logic for {program_name}");

        // TODO: Implement COBOL business logic here
        // This is a template fallback - manual implementation required

        log.info("Processing complete");
    }}
}}
"""


def detect_id_type(entity_data: Dict[str, Any]) -> str:
    """
    Detect the ID field type from entity data
    Looks for the first field (typically the @Id field) and returns its Java type
    Same logic as Repository Generator
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


def generate_entity_service(entity_class_name: str, entity_data: Dict[str, Any],
                            base_package: str) -> str:
    """Generate entity-based CRUD service (for REST controllers)"""
    repository_class_name = entity_class_name + 'Repository'
    repository_var_name = entity_class_name[0].lower() + entity_class_name[1:] + 'Repository'
    entity_var_name = entity_class_name[0].lower() + entity_class_name[1:]

    # Detect ID type from entity fields (same as Repository Generator does)
    id_type = detect_id_type(entity_data)

    return f"""package {base_package}.services;

import {base_package}.entities.{entity_class_name};
import {base_package}.repositories.{repository_class_name};
import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import java.util.List;
import java.util.Optional;

/**
 * {entity_class_name} Service
 * Handles business logic for {entity_class_name} entity
 * Generated for REST API support
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class {entity_class_name}Service {{

    private final {repository_class_name} {repository_var_name};

    public List<{entity_class_name}> findAll() {{
        log.debug("Finding all {entity_class_name}");
        return {repository_var_name}.findAll();
    }}

    public Optional<{entity_class_name}> findById({id_type} id) {{
        log.debug("Finding {entity_class_name} by id: {{}}", id);
        return {repository_var_name}.findById(id);
    }}

    public {entity_class_name} save({entity_class_name} {entity_var_name}) {{
        log.debug("Saving {entity_class_name}: {{}}", {entity_var_name});
        return {repository_var_name}.save({entity_var_name});
    }}

    public void deleteById({id_type} id) {{
        log.debug("Deleting {entity_class_name} by id: {{}}", id);
        {repository_var_name}.deleteById(id);
    }}
}}
"""


def get_cobol_source(scout_account_id: str, application_name: str, source_hash: str, program_name: str) -> str:
    """Read COBOL source file from S3"""
    try:
        source_key = f"{scout_account_id}/{application_name}/shared/uploads/{source_hash}/extracted/{program_name}"

        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=source_key)
        return response['Body'].read().decode('utf-8')
    except Exception as e:
        print(f"    WARNING: Could not read COBOL source for {program_name}: {str(e)}")
        return ""


def get_business_context(business_processes: Dict[str, Any], program_name: str) -> str:
    """Get business context for program"""
    if not business_processes or 'processes' not in business_processes:
        return "No business context available"

    for process in business_processes.get('processes', []):
        if program_name in process.get('programs', []):
            return f"{process.get('name', 'Unknown')}: {process.get('description', '')}"

    return "No specific business context found"


def get_program_analysis(static_analysis: Dict[str, Any], program_name: str) -> Dict[str, Any]:
    """Get static analysis for program"""
    if not static_analysis or 'files' not in static_analysis:
        return {}

    for file_info in static_analysis.get('files', []):
        if file_info.get('path', '') == program_name:
            # Return combined data
            return {
                'path': file_info.get('path', ''),
                'program_id': file_info.get('program_id', ''),
                'loc': file_info.get('regex_findings', {}).get('metrics', {}).get('lines_of_code', 0),
                'complexity': file_info.get('regex_findings', {}).get('code_quality', {}).get('cyclomatic_complexity', 0),
                'data_flow': file_info.get('ast_findings', {}).get('symbols', {})
            }

    return {}


def clean_class_name(name: str) -> str:
    """Clean class name (remove special chars, capitalize)"""
    # Extract just the filename from path (remove directories)
    name = name.split('/')[-1]  # Get last part after slashes

    # Remove file extensions
    name = name.replace('.cbl', '').replace('.cobol', '').replace('.CBL', '')
    name = name.replace('-', '_').replace(' ', '_')
    parts = name.split('_')
    return ''.join([p.capitalize() for p in parts if p])


def camel_case(name: str) -> str:
    """Convert to camelCase (same as EntityGenerator uses)"""
    # Remove special characters
    name = name.replace('-', '_').replace(' ', '_')

    parts = name.split('_')
    if len(parts) == 0:
        return name

    # First part lowercase, rest capitalized
    return parts[0].lower() + ''.join([p.capitalize() for p in parts[1:] if p])


def map_sql_type_to_java(sql_type: str) -> str:
    """
    Map SQL data type to Java type
    Used to tell AI what types entity fields have

    Args:
        sql_type: SQL type from ERD (e.g., "DECIMAL", "INTEGER", "VARCHAR")

    Returns:
        Java type (e.g., "BigDecimal", "Integer", "String")
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
        print(f"ERROR reading {s3_key}: {str(e)}")
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
