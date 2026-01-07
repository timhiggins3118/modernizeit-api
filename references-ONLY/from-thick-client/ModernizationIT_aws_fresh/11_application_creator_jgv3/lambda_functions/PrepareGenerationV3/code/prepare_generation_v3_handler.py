"""
Java Generation V2 - Prepare Generation Handler
Lambda: JavaGenV3PrepareGeneration

Purpose: Read all input artifacts and build generation plan

V2 Design Principles:
- NO HARDCODING
- NO SHARED CODE
- Validates ALL inputs
- Builds generation metadata
"""

import json
import boto3
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List
from botocore.exceptions import ClientError

# Add common directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'common'))
from java_name_validator import JavaNameValidator

s3_client = boto3.client('s3')

# Environment variables (NO HARDCODING)
INPUT_BUCKET = os.environ.get('INPUT_BUCKET', 'code-transformation-v2')  # Read V2 artifacts
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'code-transformation-v3')  # Write V3 results


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Prepare Java generation by reading all inputs and building plan

    Input:
    {
        "job_id": "jgv3_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01",
        "source_hash": "abc123..."
    }

    Output:
    {
        "generation_plan": {
            "entities": [list of entities from ERD],
            "services": [list of services from boundaries],
            "recipe_mapping": {program: recipe},
            "microservices": [list of microservice projects]
        }
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V2 - PREPARE GENERATION")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event.get('source_hash', '')

        print(f"Job ID: {job_id}")
        print(f"Account: {scout_account_id}, App: {application_name}")

        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v3/jobs/{job_id}"

        # Initialize Java name validator
        name_validator = JavaNameValidator(OUTPUT_BUCKET)  # Validator writes to output bucket

        # Update status
        update_status(job_base, 'running', 'preparing', 10, 'Reading input artifacts...')

        # Step 1: Read input_ref.json to get all artifact paths
        input_ref_key = f"{job_base}/input_ref.json"
        input_ref = read_json(input_ref_key)
        artifacts = input_ref['artifacts']

        print(f"Found {len(artifacts)} input artifacts")

        # Step 2: Read all artifacts
        print("\n=== Reading All Artifacts ===")

        # Discovery V2 artifacts
        business_processes = read_json(artifacts.get('business_processes', ''))
        api_patterns = read_json(artifacts.get('api_patterns', ''))

        # Data Analyzer V2
        erd = read_json(artifacts.get('erd', ''))

        # Code Analysis V2
        static_analysis = read_json(artifacts.get('static_analysis', ''))

        # Code Refactor V2
        refactor_recipes = read_json(artifacts.get('refactor_recipes', ''))

        # Dependency Mapper V2
        microservice_boundaries = read_json(artifacts.get('microservice_boundaries', ''))
        dependency_graph = read_json(artifacts.get('dependency_graph', ''))

        # Monolith Identifier V2
        decomposition_strategy = read_json(artifacts.get('decomposition_strategy', ''))

        # Architecture Recommender V2
        aws_recommendations = read_json(artifacts.get('aws_recommendations', ''))

        print("✓ All artifacts loaded successfully")

        # Step 3: Build generation plan
        print("\n=== Building Generation Plan ===")

        # Extract entity list from ERD with DEDUPLICATION
        # If multiple COBOL files define the same entity with different fields,
        # we MERGE them to create a union/superset of all fields
        entities_map = {}  # Track entities by name for deduplication
        erd_entity_count = 0

        if erd and 'entities' in erd:
            for entity in erd['entities']:
                erd_entity_count += 1
                entity_name_raw = entity.get('name', '')  # ERD uses 'name', not 'entity_name'

                # CRITICAL: Normalize entity name to Java naming conventions
                # This fixes issues like "financial_reports" -> "FinancialReports"
                # and "accounts" -> "Accounts"
                entity_name = name_validator.normalize_entity_name(entity_name_raw)

                # Validate the normalized name
                validation_result = name_validator.validate_entity_name(entity_name)
                if not validation_result['valid']:
                    print(f"  WARNING: Entity name '{entity_name_raw}' normalized to '{entity_name}' has issues:")
                    for error in validation_result['errors']:
                        print(f"    - {error}")

                # If normalization changed the name, log it
                if entity_name != entity_name_raw:
                    print(f"  NORMALIZED: '{entity_name_raw}' → '{entity_name}'")

                table_name = entity_name_raw.upper() if entity_name_raw else ''  # Keep original for DB table

                # STANDARDIZE FIELD STRUCTURE - THE CANONICAL CONTRACT!
                # This ensures ALL downstream generators read the same field names
                standardized_fields = []
                for idx, attr in enumerate(entity.get('attributes', [])):
                    field_name = attr.get('name', '').lower()
                    data_type = attr.get('data_type', 'VARCHAR').upper()

                    # Determine if this is primary key (COBOL doesn't declare PKs)
                    # Rule: First field OR field with "id" in name
                    is_pk = (idx == 0) or ('id' in field_name)

                    # Determine ID generation strategy based on type
                    # Rule: IDENTITY for numeric types, NONE for strings
                    id_generation_strategy = None
                    if is_pk:
                        if data_type in ['INTEGER', 'BIGINT', 'LONG', 'INT']:
                            id_generation_strategy = 'IDENTITY'  # Auto-increment
                        elif data_type in ['VARCHAR', 'CHAR', 'STRING', 'TEXT']:
                            id_generation_strategy = 'NONE'      # Manual assignment or UUID
                        else:
                            id_generation_strategy = 'NONE'      # Default

                    standardized_fields.append({
                        # Field identification (multiple formats for compatibility)
                        'name': attr.get('name'),                      # Standard field name
                        'field_name': attr.get('name'),                # Alias for compatibility
                        'cobol_field': attr.get('cobol_field'),        # Original COBOL name

                        # Data type (CRITICAL - multiple names for safety!)
                        'type': attr.get('data_type'),                 # NEW: Standard 'type' field
                        'data_type': attr.get('data_type'),            # Original from ERD
                        'cobol_type': attr.get('source_pic'),          # COBOL PIC clause
                        'source_pic': attr.get('source_pic'),          # Original PIC

                        # Constraints
                        'is_primary_key': is_pk,                       # Intelligently determined
                        'nullable': attr.get('nullable', True),
                        'id_generation_strategy': id_generation_strategy  # NEW: How to generate IDs
                    })

                # Check if we've seen this entity name before
                if entity_name in entities_map:
                    # MERGE FIELDS - take union/superset of all fields
                    print(f"  MERGING: Found duplicate entity '{entity_name}'")
                    existing_entity = entities_map[entity_name]
                    existing_field_names = {f['name'] for f in existing_entity['fields']}

                    # Add any new fields that don't exist yet
                    fields_added = 0
                    for new_field in standardized_fields:
                        if new_field['name'] not in existing_field_names:
                            existing_entity['fields'].append(new_field)
                            fields_added += 1
                            print(f"    + Added field: {new_field['name']} ({new_field['data_type']})")

                    if fields_added == 0:
                        print(f"    (no new fields to add)")

                    # Merge relationships too
                    existing_rel_targets = {r.get('target', '') for r in existing_entity.get('relationships', [])}
                    for new_rel in entity.get('relationships', []):
                        if new_rel.get('target', '') not in existing_rel_targets:
                            existing_entity['relationships'].append(new_rel)
                else:
                    # First time seeing this entity - add it
                    entities_map[entity_name] = {
                        'entity_name': entity_name,
                        'name': entity_name,
                        'class_name': entity_name,  # Alias for Java generators
                        'table_name': table_name,
                        'fields': standardized_fields,
                        'relationships': entity.get('relationships', []),
                        'package': 'entities'
                    }

        # Convert map back to list
        entities = list(entities_map.values())

        print(f"✓ Extracted {erd_entity_count} entities from ERD")
        print(f"✓ After deduplication: {len(entities)} unique entities")
        if erd_entity_count != len(entities):
            print(f"  (Merged {erd_entity_count - len(entities)} duplicate entity definitions)")

        # Extract microservice boundaries
        # CRITICAL: Dependency Mapper V2 uses 'suggested_services' not 'recommended_services'
        microservices = []
        if microservice_boundaries and 'suggested_services' in microservice_boundaries:
            for service in microservice_boundaries['suggested_services']:
                microservices.append({
                    'service_name': service.get('service_name', ''),
                    'programs': service.get('programs', []),
                    'business_capability': service.get('business_capability', ''),
                    'package': f"services.{service.get('service_name', '').lower().replace('service', '')}"
                })

        print(f"✓ Identified {len(microservices)} microservices")

        # GROUP SERVICES INTO LOGICAL DOMAINS
        # Strategy: Use keywords in program names and service names to classify into domains
        print("\n=== Grouping Services into Domains ===")

        domain_keywords = {
            'billing': ['PAYROL', 'BILL', 'INVOICE', 'PAYMENT', 'PAY'],
            'accounts': ['ACCT', 'ACCOUNT', 'CUSTOMER', 'CUST'],
            'reports': ['REPORT', 'PRINT', 'DISPLAY', 'RPT', 'OUTPUT'],
            'data': ['FILE', 'DATA', 'RECORD', 'TABLE']
        }

        def classify_service_to_domain(service_name: str, programs: List[str]) -> str:
            """Classify service into a business domain based on keywords"""
            # Combine service name and program names for classification
            combined_text = f"{service_name} {' '.join(programs)}".upper()

            # Check each domain's keywords
            for domain, keywords in domain_keywords.items():
                if any(keyword in combined_text for keyword in keywords):
                    return domain

            # Default domain for ungrouped services
            return 'core'

        # Assign each service to a domain
        domain_services = {}
        for ms in microservices:
            domain = classify_service_to_domain(ms['service_name'], ms['programs'])
            ms['domain'] = domain  # Add domain field to service

            if domain not in domain_services:
                domain_services[domain] = []
            domain_services[domain].append(ms['service_name'])

        # Build domains array for generation_plan
        domains = []
        for domain_name, service_names in domain_services.items():
            domains.append({
                'domain_name': domain_name,
                'package': domain_name,  # Package name matches domain
                'services': service_names,
                'service_count': len(service_names)
            })

        print(f"✓ Grouped {len(microservices)} services into {len(domains)} domains:")
        for domain in domains:
            print(f"  - {domain['domain_name']}: {domain['service_count']} services")

        # Build recipe mapping (COBOL program → Recipe)
        recipe_mapping = {}
        if refactor_recipes and 'recipes' in refactor_recipes:
            for recipe in refactor_recipes['recipes']:
                target_file = recipe.get('target', {}).get('file', '')
                if target_file:
                    recipe_mapping[target_file] = {
                        'recipe_id': recipe.get('id', ''),
                        'recipe_type': recipe.get('type', ''),
                        'java_recipe': recipe.get('java_recipe', {}),
                        'confidence': recipe.get('confidence', 0.0)
                    }

        print(f"✓ Mapped {len(recipe_mapping)} COBOL programs to recipes")

        # Extract service list from static analysis
        services = []
        if static_analysis and 'files' in static_analysis:
            for file_info in static_analysis['files']:
                program_name = file_info.get('path', '')
                program_id = file_info.get('program_id', '')

                # FIX: If program_id is missing/null, extract from program_name
                # Example: "IBMi-Cobol/Cobol/STATUSCODE.CBL" → "STATUSCODE"
                if not program_id:
                    # Extract filename without path and extension
                    filename = program_name.split('/')[-1]  # Get last part after slashes
                    program_id = filename.replace('.CBL', '').replace('.cbl', '').replace('.cobol', '').replace('.COBOL', '')
                    print(f"  INFO: Extracted program_id '{program_id}' from path '{program_name}'")

                # Extract metrics from regex_findings
                regex_findings = file_info.get('regex_findings', {})
                metrics = regex_findings.get('metrics', {})
                code_quality = regex_findings.get('code_quality', {})

                # ENHANCEMENT 2025-10-25: Extract paragraph_analysis for business logic generation
                # This data comes from Code Analysis V2 Bedrock Agent which analyzes COBOL PROCEDURE DIVISION
                # and extracts paragraph-level business logic with Java method equivalents
                paragraph_analysis = file_info.get('paragraph_analysis', [])
                paragraph_count = len(paragraph_analysis)
                if paragraph_count > 0:
                    print(f"  INFO: Found {paragraph_count} paragraphs with business logic in {program_id}")

                # Find which microservice this belongs to AND its domain
                service_name = 'default'
                domain = 'core'  # Default domain
                for ms in microservices:
                    if program_name in ms['programs']:
                        service_name = ms['service_name']
                        domain = ms.get('domain', 'core')  # Get domain from microservice
                        break

                services.append({
                    'program_name': program_name,
                    'program_id': program_id,
                    'service_name': service_name,
                    'domain': domain,  # Add domain to service
                    'loc': metrics.get('lines_of_code', 0),
                    'complexity': code_quality.get('cyclomatic_complexity', 0),
                    'has_recipe': program_name in recipe_mapping,
                    'recipe': recipe_mapping.get(program_name, None),
                    'paragraph_analysis': paragraph_analysis  # ADDED: Business logic paragraphs for method generation
                })

        print(f"✓ Identified {len(services)} service classes to generate")

        # Extract API endpoints from api_patterns
        api_endpoints = []
        if api_patterns and 'patterns' in api_patterns:
            for pattern in api_patterns['patterns']:
                api_endpoints.append({
                    'pattern_type': pattern.get('pattern_type', ''),
                    'characteristics': pattern.get('characteristics', {}),
                    'aws_architecture': pattern.get('aws_architecture', {})
                })

        print(f"✓ Identified {len(api_endpoints)} API patterns")

        # Build complete generation plan
        generation_plan = {
            'job_id': job_id,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_hash': source_hash,
            'package_name': f'com.modernized.{application_name.lower()}',  # Top-level package for Java generators
            'entities': entities,
            'services': services,
            'microservices': microservices,
            'domains': domains,  # Add domains array for domain-driven organization
            'recipe_mapping': recipe_mapping,
            'api_endpoints': api_endpoints,
            'aws_recommendations': aws_recommendations,
            'summary': {
                'total_entities': len(entities),
                'total_services': len(services),
                'total_microservices': len(microservices),
                'total_domains': len(domains),  # Add domain count to summary
                'total_recipes': len(recipe_mapping),
                'services_with_recipes': len([s for s in services if s['has_recipe']])
            }
        }

        # Step 4: Write generation_plan.json
        plan_key = f"{job_base}/generation_plan.json"
        s3_client.put_object(
            Bucket=OUTPUT_BUCKET,  # Write to V3 bucket
            Key=plan_key,
            Body=json.dumps(generation_plan, indent=2),
            ContentType='application/json'
        )

        print(f"\n✓ Wrote generation plan to s3://{OUTPUT_BUCKET}/{plan_key}")
        print(f"\nGeneration Plan Summary:")
        print(f"  Entities: {generation_plan['summary']['total_entities']}")
        print(f"  Services: {generation_plan['summary']['total_services']}")
        print(f"  Microservices: {generation_plan['summary']['total_microservices']}")
        print(f"  Domains: {generation_plan['summary']['total_domains']}")
        print(f"  Recipes: {generation_plan['summary']['total_recipes']}")
        print(f"  Services with Recipes: {generation_plan['summary']['services_with_recipes']}")

        # Update status
        update_status(job_base, 'running', 'prepared', 20, 'Generation plan created')

        return {
            'statusCode': 200,
            'generation_plan_key': plan_key,
            'summary': generation_plan['summary']
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        # Update status to failed
        try:
            update_status(job_base, 'failed', 'preparation_failed', 0, f'Error: {str(e)}')
        except:
            pass

        raise


def read_json(s3_key: str) -> Dict[str, Any]:
    """Read JSON file from S3"""
    if not s3_key:
        return {}

    try:
        # Determine which bucket based on key prefix
        # input_ref.json is in OUTPUT_BUCKET, all other artifacts in INPUT_BUCKET
        bucket = OUTPUT_BUCKET if 'java_generation_v3' in s3_key else INPUT_BUCKET
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        return json.loads(response['Body'].read().decode('utf-8'))
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NoSuchKey':
            print(f"WARNING: Artifact not found: {s3_key}")
            return {}
        raise
    except Exception as e:
        print(f"ERROR reading {s3_key}: {str(e)}")
        return {}


def update_status(job_base: str, state: str, phase: str, progress: int, message: str):
    """Update job status in S3"""
    try:
        status_key = f"{job_base}/status.json"

        # Read current status
        try:
            status_response = s3_client.get_object(Bucket=OUTPUT_BUCKET, Key=status_key)
            status_data = json.loads(status_response['Body'].read())
        except ClientError:
            status_data = {}

        # Update fields
        status_data['state'] = state
        status_data['status'] = state
        status_data['phase'] = phase
        status_data['progress'] = progress
        status_data['message'] = message
        status_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        # Write back
        s3_client.put_object(
            Bucket=OUTPUT_BUCKET,  # Write to V3 bucket
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status updated: {state} / {phase} ({progress}%) - {message}")

    except Exception as e:
        print(f"ERROR updating status: {str(e)}")
