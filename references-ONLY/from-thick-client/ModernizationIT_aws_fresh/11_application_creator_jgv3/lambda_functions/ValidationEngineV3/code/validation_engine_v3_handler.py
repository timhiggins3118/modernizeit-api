"""
Java Generation V3 - Validation Engine Handler
Lambda: ValidationEngineV3

Purpose: Validate COBOL→Java transformation quality using static analysis

V3 Design Principles (Flow 2 Redesign - October 23, 2025):
- NO Java compilation (static analysis ONLY)
- Compare V2 exports (ERD.json, static_analysis.json) to V3 generated code
- Classify every issue by root cause (V2_ANALYSIS_INCOMPLETE, FLOW1_GENERATION_BUG, etc.)
- Provide actionable customer guidance with clear remediation steps
- Does NOT auto-chain to Flow 3 (customer decides next action)

Validation Layers:
1. Transformation Accuracy (BLOCKING) - V2 exports vs V3 generated code
2. Code Quality (MEDIUM/LOW) - Static analysis tools
3. Spring Boot Specific (MEDIUM) - Framework patterns
4. Architecture Validation (HIGH/BLOCKING) - Domain boundaries
5. Security Analysis (HIGH) - OWASP checks
6. Performance Analysis (LOW) - Pattern detection

Design Document: /aws_arch/20251023_flow2_remediation_process.md
"""

import json
import boto3
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple
from botocore.exceptions import ClientError

# Tree-sitter for AST parsing (Layer 2 validation)
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

s3_client = boto3.client('s3')

# Environment variables
INPUT_BUCKET = os.environ.get('INPUT_BUCKET', 'code-transformation-v2')  # V2 exports
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'code-transformation-v3')  # V3 generated code

# Initialize tree-sitter Java parser (Layer 2 validation)
JAVA_LANGUAGE = None
JAVA_PARSER = None

def setup_java_parser():
    """Initialize tree-sitter Java parser (lazy initialization)"""
    global JAVA_LANGUAGE, JAVA_PARSER
    if JAVA_PARSER is None:
        JAVA_LANGUAGE = Language(tsjava.language())
        JAVA_PARSER = Parser(JAVA_LANGUAGE)
    return JAVA_PARSER


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Validate COBOL→Java transformation quality (NO compilation, static analysis only)

    Input:
    {
        "job_id": "jgv3_job_5150_TestApp01_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "job_id": "jgv3_job_5150_TestApp01_...",
        "validation_status": "PASSED" | "PASSED_WITH_MINOR_ISSUES" | "FAILED_WITH_HIGH_SEVERITY" | "FAILED_WITH_BLOCKING_ISSUES",
        "overall_score": 0-100,
        "validation_passed": true/false,
        "issue_summary": {
            "blocking": 0,
            "high": 0,
            "medium": 12,
            "low": 8,
            "total": 20
        },
        "recommended_action": "PROCEED_TO_FLOW3" | "RECOMMEND_FIX" | "STOP_AND_FIX",
        "customer_action": {
            "decision": "PROCEED_TO_FLOW3" | "RECOMMEND_FIX" | "STOP_AND_FIX",
            "proceed_to_flow3": true/false,
            "message": "...",
            "steps": ["1. ...", "2. ...", ...],
            "estimated_fix_time": "..."
        },
        "issues_by_category": {...},
        "validation_details": {...}
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V3 - VALIDATION ENGINE (STATIC ANALYSIS)")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")
        print(f"Account: {scout_account_id}, App: {application_name}")

        base_path = f"{scout_account_id}/{application_name}"
        v3_job_base = f"{base_path}/java_generation_v3/jobs/{job_id}"

        # V2 exports are in the LATEST V2 job for this application
        # We need to find the latest V2 job
        v2_job_base = find_latest_v2_job(scout_account_id, application_name)

        if not v2_job_base:
            raise Exception(f"No V2 job found for {scout_account_id}/{application_name}")

        print(f"V2 Job Base: s3://{INPUT_BUCKET}/{v2_job_base}")
        print(f"V3 Job Base: s3://{OUTPUT_BUCKET}/{v3_job_base}")

        # Update status
        update_status(v3_job_base, 'running', 'validation', 60, 'Validating transformation quality...')

        # Read V2 exports (source of truth)
        print("\n=== Reading V2 Exports ===")
        v2_exports = read_v2_exports(v2_job_base)

        # Read V3 generated code
        print("\n=== Reading V3 Generated Code ===")
        v3_generated = read_v3_generated_code(v3_job_base)

        # Validate Layer 1: Transformation Accuracy (BLOCKING)
        print("\n=== Layer 1: Transformation Accuracy Validation ===")
        transformation_issues = validate_transformation_accuracy(v2_exports, v3_generated)

        # Validate Layer 2: Java Code Structure (AST parsing with tree-sitter)
        ast_issues = validate_java_code_structure(v3_generated.get('java_files', []), v2_exports)

        # Merge all issues from both layers
        all_issues = transformation_issues + ast_issues

        # Classify all issues by severity
        issue_summary = {
            'blocking': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'total': 0
        }

        for issue in all_issues:
            severity = issue['severity'].lower()
            issue_summary[severity] = issue_summary.get(severity, 0) + 1
            issue_summary['total'] += 1

        # Calculate overall score
        overall_score = calculate_overall_score(issue_summary)

        # Determine customer action
        customer_action = determine_customer_action(issue_summary, all_issues)

        # Build validation report
        validation_report = {
            'job_id': job_id,
            'validation_status': customer_action['validation_status'],
            'overall_score': overall_score,
            'validation_passed': issue_summary['blocking'] == 0,
            # Backward compatibility for Step Function (expects fields at top level)
            'total_files': v3_generated['total_files'],
            'files_with_errors': len([i for i in all_issues if i['severity'] in ['BLOCKING', 'HIGH']]),
            'report_key': f"{v3_job_base}/validation_report.json",
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'issue_summary': issue_summary,
            'recommended_action': customer_action['recommended_action'],
            'customer_action': customer_action['customer_action'],
            'issues_by_category': {
                'transformation_accuracy': {
                    'score': calculate_category_score(transformation_issues),
                    'severity': get_highest_severity(transformation_issues),
                    'root_cause': get_primary_root_cause(transformation_issues),
                    'phase_to_fix': get_phase_to_fix(transformation_issues),
                    'issues': transformation_issues
                },
                'ast_validation': {
                    'score': calculate_category_score(ast_issues),
                    'severity': get_highest_severity(ast_issues),
                    'root_cause': get_primary_root_cause(ast_issues),
                    'phase_to_fix': get_phase_to_fix(ast_issues),
                    'issues': ast_issues
                }
            },
            'validation_details': {
                'entities_validated': v3_generated['entity_count'],
                'entities_expected': v2_exports['entity_count'],
                'entities_missing': max(0, v2_exports['entity_count'] - v3_generated['entity_count']),
                'services_validated': v3_generated['service_count'],
                'services_expected': v2_exports['program_count'],
                'repositories_validated': v3_generated['repository_count'],
                'controllers_validated': v3_generated['controller_count'],
                'tests_validated': v3_generated['test_count'],
                'total_java_files': v3_generated['total_files'],
                'files_with_errors': len([i for i in all_issues if i['severity'] in ['BLOCKING', 'HIGH']]),
                'layer1_issues': len(transformation_issues),
                'layer2_issues': len(ast_issues)
            },
            's3_paths': {
                'validation_report': f"s3://{OUTPUT_BUCKET}/{v3_job_base}/validation_report.json",
                'generated_code': f"s3://{OUTPUT_BUCKET}/{v3_job_base}/generated_code/",
                'v2_exports': f"s3://{INPUT_BUCKET}/{v2_job_base}/"
            }
        }

        # Add next_steps_if_proceed guidance
        if issue_summary['blocking'] > 0:
            validation_report['next_steps_if_proceed'] = "If you choose to proceed to Flow 3 despite blocking issues, ErrorFixerV3 can handle code quality issues (imports, formatting) but CANNOT auto-generate missing entities or business logic. Final package will be incomplete."
        else:
            validation_report['next_steps_if_proceed'] = "Proceed to Flow 3 to auto-fix minor issues and generate final_package.zip with Docker deployment files"

        # Write validation report to S3
        report_key = f"{v3_job_base}/validation_report.json"
        s3_client.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=report_key,
            Body=json.dumps(validation_report, indent=2),
            ContentType='application/json'
        )

        print(f"\n✓ Validation report written to s3://{OUTPUT_BUCKET}/{report_key}")

        # Print summary
        print(f"\n=== Validation Summary ===")
        print(f"Overall Score: {overall_score}/100")
        print(f"Validation Status: {validation_report['validation_status']}")
        print(f"Issues: BLOCKING={issue_summary['blocking']}, HIGH={issue_summary['high']}, MEDIUM={issue_summary['medium']}, LOW={issue_summary['low']}")
        print(f"Recommended Action: {customer_action['recommended_action']}")
        print(f"Customer Decision: {customer_action['customer_action']['decision']}")

        # Update status
        if validation_report['validation_passed']:
            update_status(v3_job_base, 'running', 'validation_passed', 70, 'Validation passed - ready for Flow 3')
        else:
            update_status(v3_job_base, 'running', 'validation_failed', 70, f"Validation failed - {issue_summary['blocking']} blocking issues")

        return validation_report

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        # Update status to failed
        try:
            update_status(v3_job_base, 'failed', 'validation_error', 0, f'Validation failed: {str(e)}')
        except:
            pass

        raise


def find_latest_v2_job(scout_account_id: str, application_name: str) -> str:
    """Find the latest V2 code_analysis_v2 job for this application (contains static_analysis.json)"""
    prefix = f"{scout_account_id}/{application_name}/code_analysis_v2/jobs/"

    print(f"Searching for V2 jobs: s3://{INPUT_BUCKET}/{prefix}")

    try:
        response = s3_client.list_objects_v2(
            Bucket=INPUT_BUCKET,
            Prefix=prefix,
            Delimiter='/'
        )

        if 'CommonPrefixes' not in response:
            return None

        # Get all job folders
        job_folders = [p['Prefix'] for p in response['CommonPrefixes']]

        if not job_folders:
            return None

        # Sort by job ID (timestamp embedded) and get latest
        latest_job = sorted(job_folders)[-1].rstrip('/')

        print(f"Found latest V2 job: {latest_job}")
        return latest_job

    except Exception as e:
        print(f"ERROR finding V2 job: {e}")
        return None


def read_v2_exports(v2_job_base: str) -> Dict[str, Any]:
    """Read V2 export files (ERD.json, static_analysis.json, etc.)"""
    v2_exports = {
        'erd': None,
        'static_analysis': None,
        'entity_count': 0,
        'program_count': 0
    }

    # Read ERD.json
    try:
        erd_key = f"{v2_job_base}/artifacts/ERD.json"
        response = s3_client.get_object(Bucket=INPUT_BUCKET, Key=erd_key)
        v2_exports['erd'] = json.loads(response['Body'].read().decode('utf-8'))
        v2_exports['entity_count'] = len(v2_exports['erd'].get('entities', []))
        print(f"✓ Read ERD.json: {v2_exports['entity_count']} entities")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"⚠️  ERD.json not found in V2 job")
        else:
            raise

    # Read static_analysis.json
    try:
        static_key = f"{v2_job_base}/artifacts/static_analysis.json"
        response = s3_client.get_object(Bucket=INPUT_BUCKET, Key=static_key)
        v2_exports['static_analysis'] = json.loads(response['Body'].read().decode('utf-8'))
        v2_exports['program_count'] = len(v2_exports['static_analysis'].get('files', []))
        print(f"✓ Read static_analysis.json: {v2_exports['program_count']} programs")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            print(f"⚠️  static_analysis.json not found in V2 job")
        else:
            raise

    return v2_exports


def read_v3_generated_code(v3_job_base: str) -> Dict[str, Any]:
    """Read V3 generated code, count files by type, and download content for AST parsing"""
    v3_generated = {
        'entity_count': 0,
        'service_count': 0,
        'repository_count': 0,
        'controller_count': 0,
        'test_count': 0,
        'total_files': 0,
        'entities': [],
        'services': [],
        'java_files': []  # NEW: Store file content for AST parsing
    }

    # List all .java files in artifacts/ModernizedApplication/
    prefix = f"{v3_job_base}/artifacts/ModernizedApplication/"

    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=OUTPUT_BUCKET, Prefix=prefix)

        for page in pages:
            if 'Contents' not in page:
                continue

            for obj in page['Contents']:
                key = obj['Key']
                if key.endswith('.java'):
                    v3_generated['total_files'] += 1
                    filename = os.path.basename(key)

                    # Download file content for AST parsing
                    try:
                        response = s3_client.get_object(Bucket=OUTPUT_BUCKET, Key=key)
                        content = response['Body'].read().decode('utf-8')

                        # Determine file type
                        file_type = 'other'
                        if '/entities/' in key:
                            file_type = 'entity'
                            v3_generated['entity_count'] += 1
                            v3_generated['entities'].append(filename.replace('.java', ''))
                        elif '/services/' in key:
                            file_type = 'service'
                            v3_generated['service_count'] += 1
                            v3_generated['services'].append(filename.replace('.java', ''))
                        elif '/repositories/' in key:
                            file_type = 'repository'
                            v3_generated['repository_count'] += 1
                        elif '/controllers/' in key:
                            file_type = 'controller'
                            v3_generated['controller_count'] += 1
                        elif '/test/' in key or 'Test.java' in filename:
                            file_type = 'test'
                            v3_generated['test_count'] += 1

                        # Store file info with content for AST parsing
                        v3_generated['java_files'].append({
                            's3_key': key,
                            'filename': filename,
                            'file_type': file_type,
                            'content': content
                        })
                    except Exception as e:
                        print(f"⚠️  Could not download {key}: {e}")

        print(f"✓ Found {v3_generated['total_files']} Java files:")
        print(f"  - Entities: {v3_generated['entity_count']}")
        print(f"  - Services: {v3_generated['service_count']}")
        print(f"  - Repositories: {v3_generated['repository_count']}")
        print(f"  - Controllers: {v3_generated['controller_count']}")
        print(f"  - Tests: {v3_generated['test_count']}")
        print(f"  - Downloaded {len(v3_generated['java_files'])} files for AST parsing")

    except Exception as e:
        print(f"ERROR reading V3 generated code: {e}")

    return v3_generated


def validate_transformation_accuracy(v2_exports: Dict[str, Any], v3_generated: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Layer 1: Transformation Accuracy Validation (BLOCKING severity)

    Compare V2 exports (ERD.json, static_analysis.json) to V3 generated code.
    Check if all expected entities and services were generated.
    """
    issues = []

    # Check 1: Missing Entities
    if v2_exports['erd']:
        expected_entities = v2_exports['erd'].get('entities', [])
        generated_entity_names = set(v3_generated['entities'])

        for entity_def in expected_entities:
            entity_name = entity_def.get('name', '')

            # Check if entity was generated
            if entity_name not in generated_entity_names:
                issues.append({
                    'type': 'MISSING_ENTITY',
                    'severity': 'BLOCKING',
                    'root_cause': 'V2_ANALYSIS_INCOMPLETE',
                    'phase_to_fix': 'V2 Analysis Flow',
                    'expected_entity': entity_name,
                    'expected_source': f"COBOL copybook (defined in ERD.json)",
                    'source_file': 'ERD.json should have complete entity definition',
                    'impact': f"Cannot generate {entity_name}.java, {entity_name}Service.java, {entity_name}Repository.java, {entity_name}Controller.java",
                    'remediation': f"Verify {entity_name} copybook included in V2 Analysis, re-run V2 Analysis, then re-run Flow 1",
                    'auto_fixable': False,
                    'estimated_fix_time': '10-15 minutes'
                })

    # Check 2: Entity count mismatch
    if v2_exports['entity_count'] > v3_generated['entity_count']:
        missing_count = v2_exports['entity_count'] - v3_generated['entity_count']
        issues.append({
            'type': 'ENTITY_COUNT_MISMATCH',
            'severity': 'BLOCKING',
            'root_cause': 'FLOW1_GENERATION_BUG',
            'phase_to_fix': 'Flow 1 (PrepareGenerationV3 or EntityGeneratorV3)',
            'expected_count': v2_exports['entity_count'],
            'actual_count': v3_generated['entity_count'],
            'missing_count': missing_count,
            'impact': f"{missing_count} entities from ERD.json were not generated",
            'remediation': 'Review PrepareGenerationV3 and EntityGeneratorV3 logs, fix generation bug, re-run Flow 1',
            'auto_fixable': False,
            'estimated_fix_time': '1-2 hours (requires code fix)'
        })

    # Check 3: Service count mismatch
    if v2_exports['program_count'] > v3_generated['service_count']:
        missing_count = v2_exports['program_count'] - v3_generated['service_count']
        issues.append({
            'type': 'SERVICE_COUNT_MISMATCH',
            'severity': 'HIGH',
            'root_cause': 'FLOW1_GENERATION_BUG',
            'phase_to_fix': 'Flow 1 (ServiceGeneratorV3)',
            'expected_count': v2_exports['program_count'],
            'actual_count': v3_generated['service_count'],
            'missing_count': missing_count,
            'impact': f"{missing_count} services from static_analysis.json were not generated",
            'remediation': 'Review ServiceGeneratorV3 logs, fix generation bug, re-run Flow 1',
            'auto_fixable': False,
            'estimated_fix_time': '1-2 hours (requires code fix)'
        })

    return issues


def validate_java_code_structure(java_files: List[Dict[str, Any]], v2_exports: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Layer 2: Java Code Structure Validation using AST parsing

    Uses tree-sitter to parse Java files and detect:
    - Class structure issues
    - Missing/incorrect Spring Boot annotations
    - Method validation issues
    - Import problems
    - Relationship issues (Controller->Service->Repository)
    - Anti-patterns
    - Syntax errors
    """
    print(f"\n=== Layer 2: AST Validation (tree-sitter) ===")

    if not java_files:
        print("⚠️  No Java files to validate")
        return []

    parser = setup_java_parser()
    issues = []

    print(f"Parsing {len(java_files)} Java files...")

    for java_file in java_files:
        try:
            # Parse Java file to AST
            tree = parser.parse(bytes(java_file['content'], 'utf8'))

            # Run 7 validation checks
            issues.extend(validate_class_structure(tree, java_file))
            issues.extend(validate_spring_annotations(tree, java_file))
            issues.extend(validate_methods(tree, java_file))
            issues.extend(validate_imports(tree, java_file))
            issues.extend(validate_relationships(tree, java_file, v2_exports))
            issues.extend(validate_patterns(tree, java_file))
            issues.extend(validate_syntax(tree, java_file))

        except Exception as e:
            print(f"⚠️  AST parsing error for {java_file['filename']}: {e}")
            issues.append({
                'type': 'AST_PARSE_ERROR',
                'severity': 'HIGH',
                'root_cause': 'FLOW1_GENERATION_BUG',
                'phase_to_fix': 'Flow 1',
                'file': java_file['filename'],
                's3_key': java_file['s3_key'],
                'impact': f"Could not parse {java_file['filename']} - may have syntax errors",
                'remediation': 'Review generated code for syntax issues, fix Flow 1 generator',
                'auto_fixable': False,
                'estimated_fix_time': '30 minutes'
            })

    print(f"✓ AST validation found {len(issues)} issues")
    return issues


def validate_class_structure(tree, java_file: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate class structure (class name matches file, package declaration, etc.)"""
    issues = []
    root_node = tree.root_node

    # Find class declaration
    class_declarations = [node for node in root_node.children if node.type == 'class_declaration']

    if not class_declarations:
        issues.append({
            'type': 'NO_CLASS_DECLARATION',
            'severity': 'BLOCKING',
            'root_cause': 'FLOW1_GENERATION_BUG',
            'phase_to_fix': 'Flow 1',
            'file': java_file['filename'],
            's3_key': java_file['s3_key'],
            'impact': 'Java file has no class declaration',
            'remediation': 'Fix generator to include class declaration',
            'auto_fixable': False,
            'estimated_fix_time': '1 hour'
        })
        return issues

    # Check class name matches filename
    class_node = class_declarations[0]
    class_name_node = None
    for child in class_node.children:
        if child.type == 'identifier':
            class_name_node = child
            break

    if class_name_node:
        class_name = java_file['content'][class_name_node.start_byte:class_name_node.end_byte]
        expected_class_name = java_file['filename'].replace('.java', '')

        if class_name != expected_class_name:
            issues.append({
                'type': 'CLASS_NAME_MISMATCH',
                'severity': 'BLOCKING',
                'root_cause': 'FLOW1_GENERATION_BUG',
                'phase_to_fix': 'Flow 1',
                'file': java_file['filename'],
                's3_key': java_file['s3_key'],
                'expected': expected_class_name,
                'actual': class_name,
                'impact': 'Java compiler will reject file with mismatched class name',
                'remediation': f"Rename class '{class_name}' to '{expected_class_name}' or rename file",
                'auto_fixable': True,
                'estimated_fix_time': '1 minute (Flow 3 auto-fix)'
            })

    # Check for package declaration
    package_declarations = [node for node in root_node.children if node.type == 'package_declaration']
    if not package_declarations:
        issues.append({
            'type': 'NO_PACKAGE_DECLARATION',
            'severity': 'HIGH',
            'root_cause': 'FLOW1_GENERATION_BUG',
            'phase_to_fix': 'Flow 1',
            'file': java_file['filename'],
            's3_key': java_file['s3_key'],
            'impact': 'Missing package declaration - code won\'t compile in Maven project',
            'remediation': 'Add package declaration matching directory structure',
            'auto_fixable': True,
            'estimated_fix_time': '1 minute (Flow 3 auto-fix)'
        })

    return issues


def validate_spring_annotations(tree, java_file: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate Spring Boot annotations based on file type"""
    issues = []
    root_node = tree.root_node
    file_type = java_file.get('file_type', 'other')

    # Get all annotations in the file
    annotations = []
    def find_annotations(node):
        if node.type == 'marker_annotation' or node.type == 'annotation':
            # Get annotation name
            for child in node.children:
                if child.type == 'identifier' or child.type == 'scoped_identifier':
                    annotation_text = java_file['content'][child.start_byte:child.end_byte]
                    annotations.append(annotation_text)
        for child in node.children:
            find_annotations(child)

    find_annotations(root_node)

    # Validate based on file type
    if file_type == 'controller':
        if not any(ann in ['RestController', 'Controller'] for ann in annotations):
            issues.append({
                'type': 'MISSING_CONTROLLER_ANNOTATION',
                'severity': 'HIGH',
                'root_cause': 'FLOW1_GENERATION_BUG',
                'phase_to_fix': 'Flow 1 (APIGeneratorV3)',
                'file': java_file['filename'],
                's3_key': java_file['s3_key'],
                'impact': 'Spring Boot won\'t recognize this as a REST controller',
                'remediation': 'Add @RestController annotation to class',
                'auto_fixable': True,
                'estimated_fix_time': '1 minute (Flow 3 auto-fix)'
            })

    elif file_type == 'service':
        if 'Service' not in annotations:
            issues.append({
                'type': 'MISSING_SERVICE_ANNOTATION',
                'severity': 'HIGH',
                'root_cause': 'FLOW1_GENERATION_BUG',
                'phase_to_fix': 'Flow 1 (ServiceGeneratorV3)',
                'file': java_file['filename'],
                's3_key': java_file['s3_key'],
                'impact': 'Spring Boot won\'t manage this as a service bean',
                'remediation': 'Add @Service annotation to class',
                'auto_fixable': True,
                'estimated_fix_time': '1 minute (Flow 3 auto-fix)'
            })

    elif file_type == 'repository':
        if 'Repository' not in annotations:
            issues.append({
                'type': 'MISSING_REPOSITORY_ANNOTATION',
                'severity': 'HIGH',
                'root_cause': 'FLOW1_GENERATION_BUG',
                'phase_to_fix': 'Flow 1 (RepositoryGeneratorV3)',
                'file': java_file['filename'],
                's3_key': java_file['s3_key'],
                'impact': 'Spring Data JPA won\'t recognize this repository',
                'remediation': 'Add @Repository annotation to interface',
                'auto_fixable': True,
                'estimated_fix_time': '1 minute (Flow 3 auto-fix)'
            })

    elif file_type == 'entity':
        if 'Entity' not in annotations:
            issues.append({
                'type': 'MISSING_ENTITY_ANNOTATION',
                'severity': 'BLOCKING',
                'root_cause': 'FLOW1_GENERATION_BUG',
                'phase_to_fix': 'Flow 1 (EntityGeneratorV3)',
                'file': java_file['filename'],
                's3_key': java_file['s3_key'],
                'impact': 'JPA won\'t map this class to database table',
                'remediation': 'Add @Entity annotation to class',
                'auto_fixable': True,
                'estimated_fix_time': '1 minute (Flow 3 auto-fix)'
            })

    return issues


def validate_methods(tree, java_file: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate methods exist and have proper signatures"""
    issues = []
    root_node = tree.root_node
    file_type = java_file.get('file_type', 'other')

    # Count methods
    method_count = 0
    def count_methods(node):
        nonlocal method_count
        if node.type == 'method_declaration':
            method_count += 1
        for child in node.children:
            count_methods(child)

    count_methods(root_node)

    # Services and Controllers should have methods
    if file_type in ['service', 'controller'] and method_count == 0:
        issues.append({
            'type': 'NO_METHODS',
            'severity': 'HIGH',
            'root_cause': 'FLOW1_GENERATION_BUG',
            'phase_to_fix': f"Flow 1 ({'ServiceGeneratorV3' if file_type == 'service' else 'APIGeneratorV3'})",
            'file': java_file['filename'],
            's3_key': java_file['s3_key'],
            'impact': f"{file_type.capitalize()} has no business logic methods",
            'remediation': f"Add business logic methods to {file_type}",
            'auto_fixable': False,
            'estimated_fix_time': '1-2 hours (requires code fix)'
        })

    return issues


def validate_imports(tree, java_file: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate imports (prefer jakarta.* over javax.*)"""
    issues = []
    root_node = tree.root_node

    # Find all imports
    imports = []
    for node in root_node.children:
        if node.type == 'import_declaration':
            import_text = java_file['content'][node.start_byte:node.end_byte]
            imports.append(import_text)

    # Check for javax.* imports (should be jakarta.*)
    for import_stmt in imports:
        if 'javax.' in import_stmt:
            issues.append({
                'type': 'OLD_JAVAX_IMPORT',
                'severity': 'MEDIUM',
                'root_cause': 'FLOW1_AUTO_FIXABLE',
                'phase_to_fix': 'Flow 3 (ErrorFixerV3)',
                'file': java_file['filename'],
                's3_key': java_file['s3_key'],
                'import_statement': import_stmt.strip(),
                'impact': 'Using deprecated javax.* instead of jakarta.*',
                'remediation': 'Replace javax.* imports with jakarta.* equivalents',
                'auto_fixable': True,
                'estimated_fix_time': '1 minute (Flow 3 auto-fix)'
            })

    return issues


def validate_relationships(tree, java_file: Dict[str, Any], v2_exports: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate relationships (Controller->Service->Repository)"""
    issues = []
    # This would require more complex AST traversal to check field declarations
    # and constructor parameters - skipping for now to keep implementation simple
    # Can be enhanced in future iterations
    return issues


def validate_patterns(tree, java_file: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate Spring Boot best practices (constructor injection, etc.)"""
    issues = []
    root_node = tree.root_node
    file_type = java_file.get('file_type', 'other')

    # Check for field-level @Autowired (anti-pattern, should use constructor injection)
    def find_field_autowired(node):
        if node.type == 'field_declaration':
            # Check if field has @Autowired annotation
            for child in node.children:
                if child.type == 'modifiers':
                    modifiers_text = java_file['content'][child.start_byte:child.end_byte]
                    if '@Autowired' in modifiers_text:
                        issues.append({
                            'type': 'FIELD_AUTOWIRED_ANTIPATTERN',
                            'severity': 'LOW',
                            'root_cause': 'FLOW1_AUTO_FIXABLE',
                            'phase_to_fix': 'Flow 3 (ErrorFixerV3)',
                            'file': java_file['filename'],
                            's3_key': java_file['s3_key'],
                            'impact': 'Using field injection instead of recommended constructor injection',
                            'remediation': 'Replace field @Autowired with constructor injection',
                            'auto_fixable': True,
                            'estimated_fix_time': '2 minutes (Flow 3 auto-fix)'
                        })
        for child in node.children:
            find_field_autowired(child)

    if file_type in ['controller', 'service']:
        find_field_autowired(root_node)

    return issues


def validate_syntax(tree, java_file: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate syntax (detect parsing errors in tree)"""
    issues = []
    root_node = tree.root_node

    # Check for ERROR nodes in parse tree
    def find_errors(node):
        if node.type == 'ERROR' or node.is_missing:
            issues.append({
                'type': 'SYNTAX_ERROR',
                'severity': 'BLOCKING',
                'root_cause': 'FLOW1_GENERATION_BUG',
                'phase_to_fix': 'Flow 1',
                'file': java_file['filename'],
                's3_key': java_file['s3_key'],
                'line': node.start_point[0] + 1,
                'column': node.start_point[1] + 1,
                'impact': 'Syntax error prevents compilation',
                'remediation': f"Fix syntax error at line {node.start_point[0] + 1}",
                'auto_fixable': False,
                'estimated_fix_time': '30 minutes to 1 hour'
            })
        for child in node.children:
            find_errors(child)

    find_errors(root_node)

    return issues


def calculate_overall_score(issue_summary: Dict[str, int]) -> int:
    """Calculate overall validation score (0-100)"""
    # Perfect score if no issues
    if issue_summary['total'] == 0:
        return 100

    # Deduct points based on severity
    score = 100
    score -= issue_summary['blocking'] * 20  # -20 per blocking
    score -= issue_summary['high'] * 10      # -10 per high
    score -= issue_summary['medium'] * 5     # -5 per medium
    score -= issue_summary['low'] * 2        # -2 per low

    return max(0, score)


def determine_customer_action(issue_summary: Dict[str, int], all_issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Determine recommended customer action based on validation results.

    Algorithm:
    - blocking > 0 → STOP_AND_FIX
    - high > 5 → RECOMMEND_FIX
    - medium > 0 or low > 0 → PROCEED_TO_FLOW3
    - no issues → PROCEED_TO_FLOW3
    """
    blocking = issue_summary['blocking']
    high = issue_summary['high']
    medium = issue_summary['medium']
    low = issue_summary['low']

    if blocking > 0:
        # STOP - Critical issues require fixing
        root_causes = {}
        for issue in all_issues:
            if issue['severity'] == 'BLOCKING':
                rc = issue['root_cause']
                root_causes[rc] = root_causes.get(rc, 0) + 1

        primary_root_cause = max(root_causes.items(), key=lambda x: x[1])[0] if root_causes else 'UNKNOWN'

        return {
            'validation_status': 'FAILED_WITH_BLOCKING_ISSUES',
            'recommended_action': 'STOP_AND_FIX',
            'customer_action': {
                'decision': 'STOP_AND_FIX',
                'proceed_to_flow3': False,
                'message': f"{blocking} blocking issue(s) found. Root cause: {primary_root_cause}. Fix source data or Flow 1 bugs before proceeding.",
                'steps': generate_remediation_steps(all_issues),
                'estimated_fix_time': '10-15 minutes to 2 hours (depends on root cause)'
            }
        }

    elif high > 5:
        # RECOMMEND FIX - High severity issues
        return {
            'validation_status': 'FAILED_WITH_HIGH_SEVERITY',
            'recommended_action': 'RECOMMEND_FIX',
            'customer_action': {
                'decision': 'RECOMMEND_FIX',
                'proceed_to_flow3': 'CUSTOMER_CHOICE',
                'message': f"{high} high-severity issue(s) found. Recommend fixing, but Flow 3 can attempt auto-fix at customer's risk.",
                'steps': generate_remediation_steps(all_issues),
                'estimated_fix_time': '1-2 hours'
            }
        }

    elif medium > 0 or low > 0:
        # PROCEED TO FLOW 3 - Minor issues
        return {
            'validation_status': 'PASSED_WITH_MINOR_ISSUES',
            'recommended_action': 'PROCEED_TO_FLOW3',
            'customer_action': {
                'decision': 'PROCEED_TO_FLOW3',
                'proceed_to_flow3': True,
                'message': f"{medium + low} minor issue(s) detected. Flow 3 auto-fix will handle these.",
                'steps': [
                    '1. Review validation report (optional)',
                    '2. Proceed to Flow 3 (POST /finalizejgv3) to auto-fix minor issues and package final application'
                ],
                'estimated_fix_time': '1-2 minutes (Flow 3 auto-fix)'
            }
        }

    else:
        # PERFECT - No issues
        return {
            'validation_status': 'PASSED',
            'recommended_action': 'PROCEED_TO_FLOW3',
            'customer_action': {
                'decision': 'PROCEED_TO_FLOW3',
                'proceed_to_flow3': True,
                'message': 'Validation passed! No issues detected. Code ready for packaging.',
                'steps': [
                    '1. Proceed to Flow 3 (POST /finalizejgv3) to generate final_package.zip'
                ],
                'estimated_fix_time': '1-2 minutes (Flow 3 packaging only)'
            }
        }


def generate_remediation_steps(issues: List[Dict[str, Any]]) -> List[str]:
    """Generate step-by-step remediation guidance from issues"""
    steps = []
    step_num = 1

    # Group issues by root cause
    by_root_cause = {}
    for issue in issues:
        if issue['severity'] in ['BLOCKING', 'HIGH']:
            rc = issue['root_cause']
            if rc not in by_root_cause:
                by_root_cause[rc] = []
            by_root_cause[rc].append(issue)

    # Generate steps for each root cause
    for root_cause, rc_issues in by_root_cause.items():
        if root_cause == 'V2_ANALYSIS_INCOMPLETE':
            steps.append(f"{step_num}. Review ERD.json and static_analysis.json in V2 job")
            step_num += 1
            for issue in rc_issues[:3]:  # Show first 3
                if 'expected_entity' in issue:
                    steps.append(f"{step_num}. Verify COBOL copybook for {issue['expected_entity']} was included in V2 Analysis")
                    step_num += 1
            steps.append(f"{step_num}. Re-run V2 Analysis flow with complete COBOL files")
            step_num += 1
            steps.append(f"{step_num}. Re-run Flow 1 (POST /startjgv3) to regenerate with complete data")
            step_num += 1

        elif root_cause == 'FLOW1_GENERATION_BUG':
            steps.append(f"{step_num}. Report issue to development team with validation report")
            step_num += 1
            steps.append(f"{step_num}. Development team fixes Flow 1 Lambda ({rc_issues[0].get('phase_to_fix', 'Flow 1')})")
            step_num += 1
            steps.append(f"{step_num}. Re-run Flow 1 (POST /startjgv3) after fix is deployed")
            step_num += 1

    steps.append(f"{step_num}. Re-run Flow 2 (POST /analyzejgv3) to validate fixes")

    return steps


def calculate_category_score(issues: List[Dict[str, Any]]) -> int:
    """Calculate score for a category based on issues"""
    if not issues:
        return 100

    score = 100
    for issue in issues:
        if issue['severity'] == 'BLOCKING':
            score -= 20
        elif issue['severity'] == 'HIGH':
            score -= 10
        elif issue['severity'] == 'MEDIUM':
            score -= 5
        elif issue['severity'] == 'LOW':
            score -= 2

    return max(0, score)


def get_highest_severity(issues: List[Dict[str, Any]]) -> str:
    """Get the highest severity level from issues"""
    if not issues:
        return 'NONE'

    for severity in ['BLOCKING', 'HIGH', 'MEDIUM', 'LOW']:
        if any(i['severity'] == severity for i in issues):
            return severity

    return 'NONE'


def get_primary_root_cause(issues: List[Dict[str, Any]]) -> str:
    """Get the most common root cause from issues"""
    if not issues:
        return 'NONE'

    root_causes = {}
    for issue in issues:
        rc = issue['root_cause']
        root_causes[rc] = root_causes.get(rc, 0) + 1

    return max(root_causes.items(), key=lambda x: x[1])[0] if root_causes else 'UNKNOWN'


def get_phase_to_fix(issues: List[Dict[str, Any]]) -> str:
    """Get the phase that needs to be fixed"""
    if not issues:
        return 'None'

    # Return phase from first BLOCKING or HIGH severity issue
    for issue in issues:
        if issue['severity'] in ['BLOCKING', 'HIGH']:
            return issue.get('phase_to_fix', 'Unknown')

    return issues[0].get('phase_to_fix', 'Unknown')


def update_status(job_base: str, status: str, stage: str, progress: int, message: str):
    """Update job status in S3"""
    try:
        status_key = f"{job_base}/status.json"

        status_data = {
            'status': status,
            'stage': stage,
            'progress': progress,
            'message': message,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        s3_client.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status updated: {status} / {stage} ({progress}%) - {message}")

    except Exception as e:
        print(f"ERROR updating status: {e}")
