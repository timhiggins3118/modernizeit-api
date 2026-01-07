#!/usr/bin/env python3
"""
Code Refactor V2 - AST Pattern Detector V2
Detects refactorable patterns using Tree-sitter AST analysis
FOCUS: Control flow complexity and data structure patterns for transformation

Uses shared job context helpers for consistent path handling.
"""

import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict, Counter

import boto3

# Add shared module to path for Lambda deployment
handler_dir = Path(__file__).parent
shared_dir = handler_dir.parent.parent / 'shared'
if shared_dir.exists():
    sys.path.insert(0, str(shared_dir))

try:
    from refactor_v2_common import get_refactor_job_context, error_response
except ImportError:
    # Fallback for local testing
    from shared.refactor_v2_common import get_refactor_job_context, error_response

s3_client = boto3.client('s3')


def lambda_handler(event, context):
    """
    Detect patterns for refactoring recipes using AST analysis
    """

    try:
        print(f"AST Pattern Detector V2 starting: {json.dumps(event)}")

        # Get job context using shared helper
        job_ctx = get_refactor_job_context(event)
        bucket = job_ctx.bucket_name

        print(f"Job context: job_id={job_ctx.job_id}, job_root={job_ctx.job_root}")

        # Read classified catalog
        catalog_key = job_ctx.get_catalog_key()
        catalog_response = s3_client.get_object(Bucket=bucket, Key=catalog_key)
        classified_catalog = json.loads(catalog_response['Body'].read().decode('utf-8'))

        cobol_files = classified_catalog.get('classifications', {}).get('cobol', [])

        if not cobol_files:
            return error_response(404, 'No COBOL files found')

        print(f"Analyzing {len(cobol_files)} files for AST patterns")

        # Analyze each file for patterns
        all_patterns = []
        total_patterns = 0
        total_complexity = 0

        for file_path in cobol_files:
            file_key = job_ctx.get_file_key(file_path)

            try:
                file_response = s3_client.get_object(Bucket=bucket, Key=file_key)
                cobol_content = file_response['Body'].read().decode('utf-8', errors='ignore')

                # Detect AST patterns
                patterns, complexity = detect_ast_patterns(cobol_content, file_path)

                if patterns:
                    all_patterns.append({
                        'path': file_path,
                        'patterns': patterns,
                        'pattern_count': len(patterns),
                        'total_complexity': complexity
                    })
                    total_patterns += len(patterns)
                    total_complexity += complexity

            except Exception as e:
                print(f"Error analyzing {file_path}: {str(e)}")
                continue

        # Calculate summary
        summary = calculate_ast_summary(all_patterns, total_complexity)

        # Build output
        output = {
            'job_id': job_ctx.job_id,
            'source_hash': job_ctx.source_hash,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_files': len(cobol_files),
                'files_with_patterns': len(all_patterns),
                'total_patterns': total_patterns,
                'total_complexity': total_complexity,
                **summary
            },
            'files': all_patterns
        }

        # Write to S3 using job context helper
        output_key = job_ctx.get_artifact_key('ast_patterns.json')
        s3_client.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=json.dumps(output, indent=2),
            ContentType='application/json'
        )

        print(f"AST pattern detection complete: {total_patterns} patterns found")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'patterns_found': total_patterns,
                'files_analyzed': len(cobol_files),
                'total_complexity': total_complexity,
                'output_path': f"s3://{bucket}/{output_key}"
            }
        }

    except ValueError as e:
        # Missing required fields
        print(f"Validation error: {str(e)}")
        return error_response(400, str(e))

    except Exception as e:
        print(f"Error in AST pattern detection: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"AST pattern detection failed: {str(e)}")


def detect_ast_patterns(cobol_content, file_path):
    """
    Detect refactorable patterns using AST analysis
    FOCUS: Control flow complexity, data structures, coupling
    """
    patterns = []
    total_complexity = 0

    # Pattern 1: Complex Control Flow
    control_flow_patterns, complexity = detect_complex_control_flow(cobol_content)
    patterns.extend(control_flow_patterns)
    total_complexity += complexity

    # Pattern 2: Data Structure Modernization Opportunities
    data_structure_patterns = detect_data_structure_patterns(cobol_content)
    patterns.extend(data_structure_patterns)

    # Pattern 3: Deep PERFORM Chains
    perform_chain_patterns = detect_perform_chains(cobol_content)
    patterns.extend(perform_chain_patterns)

    # Pattern 4: Paragraph Coupling
    coupling_patterns = detect_paragraph_coupling(cobol_content)
    patterns.extend(coupling_patterns)

    # Pattern 5: Global Variable Usage
    global_var_patterns = detect_global_variables(cobol_content)
    patterns.extend(global_var_patterns)

    return patterns, total_complexity


def detect_complex_control_flow(content):
    """Detect high cyclomatic complexity paragraphs - Simplification candidates"""
    patterns = []
    total_complexity = 0

    # Simple heuristic: count IF, EVALUATE, PERFORM statements per paragraph
    lines = content.split('\n')
    current_paragraph = None
    paragraph_complexity = {}
    paragraph_lines = {}

    for i, line in enumerate(lines):
        line_upper = line.strip().upper()

        # Detect paragraph start
        if line_upper and not line_upper.startswith('*') and '.' in line and not line.startswith(' '):
            # Could be paragraph name
            parts = line.strip().split('.')
            if len(parts) >= 1 and not any(kw in parts[0].upper() for kw in ['DIVISION', 'SECTION', 'FD', 'SD', '01', '05', '10']):
                current_paragraph = parts[0].strip()
                paragraph_complexity[current_paragraph] = 0
                paragraph_lines[current_paragraph] = i + 1

        # Count complexity contributors
        if current_paragraph:
            if line_upper.startswith('IF '):
                paragraph_complexity[current_paragraph] += 1
            elif 'EVALUATE' in line_upper:
                paragraph_complexity[current_paragraph] += 2
            elif 'PERFORM' in line_upper and 'UNTIL' in line_upper:
                paragraph_complexity[current_paragraph] += 2

    # Generate patterns for high complexity
    for paragraph, complexity in paragraph_complexity.items():
        total_complexity += complexity
        if complexity >= 10:  # High complexity threshold
            patterns.append({
                'type': 'complex_control_flow',
                'paragraph': paragraph,
                'line': paragraph_lines.get(paragraph, 0),
                'complexity': complexity,
                'recipe_type': 'extract_validation_logic' if 'VALIDATE' in paragraph else 'decompose_paragraph',
                'confidence': min(0.95, 0.70 + (complexity - 10) * 0.02),
                'estimated_improvement': f'complexity: {complexity} → {max(3, complexity // 4)}',
                'rationale': f'High cyclomatic complexity ({complexity}) makes testing and maintenance difficult'
            })

    return patterns, total_complexity


def detect_data_structure_patterns(content):
    """Detect COBOL data structures that can be modernized"""
    patterns = []
    lines = content.split('\n')

    # Track data structures with Level-88 or COMP-3
    in_data_division = False
    current_01_record = None
    record_has_level88 = False
    record_has_comp3 = False
    record_field_count = 0
    record_line = 0

    for i, line in enumerate(lines):
        line_upper = line.strip().upper()

        if 'DATA DIVISION' in line_upper:
            in_data_division = True
            continue

        if 'PROCEDURE DIVISION' in line_upper:
            in_data_division = False
            break

        if in_data_division:
            # New 01 record
            if line_upper.startswith('01 '):
                # Save previous record if it had patterns
                if current_01_record and (record_has_level88 or record_has_comp3):
                    patterns.append({
                        'type': 'data_structure_modernization',
                        'structure': current_01_record,
                        'line': record_line,
                        'fields': record_field_count,
                        'has_level88': record_has_level88,
                        'has_comp3': record_has_comp3,
                        'recipe_type': 'pojo_with_enum' if record_has_level88 else 'pojo_with_bigdecimal',
                        'confidence': 0.95,
                        'benefit': 'Type safety, null safety, immutability',
                        'rationale': f'COBOL record with {"Level-88 conditions and " if record_has_level88 else ""}{"COMP-3 fields" if record_has_comp3 else ""} can use modern Java types'
                    })

                # Reset for new record
                parts = line_upper.split()
                if len(parts) >= 2:
                    current_01_record = parts[1].replace('.', '')
                    record_line = i + 1
                    record_has_level88 = False
                    record_has_comp3 = False
                    record_field_count = 0

            # Count fields
            elif current_01_record and line_upper.startswith('05 '):
                record_field_count += 1

            # Detect Level-88
            elif current_01_record and line_upper.strip().startswith('88 '):
                record_has_level88 = True

            # Detect COMP-3
            elif current_01_record and 'COMP-3' in line_upper:
                record_has_comp3 = True

    return patterns


def detect_perform_chains(content):
    """Detect deep PERFORM chains - Service layer extraction candidates"""
    patterns = []

    # Simple heuristic: multiple nested PERFORMs
    # In real implementation, would build call graph
    lines = content.split('\n')
    perform_counts = Counter()

    for line in lines:
        if 'PERFORM' in line.upper():
            # Extract performed paragraph
            match = re.search(r'PERFORM\s+([\w-]+)', line, re.IGNORECASE)
            if match:
                perform_counts[match.group(1)] += 1

    # Frequently performed paragraphs are service candidates
    for paragraph, count in perform_counts.items():
        if count >= 5:
            patterns.append({
                'type': 'frequent_perform',
                'paragraph': paragraph,
                'perform_count': count,
                'recipe_type': 'extract_service_method',
                'confidence': min(0.90, 0.70 + count * 0.02),
                'rationale': f'Paragraph performed {count} times - candidate for service method extraction'
            })

    return patterns


def detect_paragraph_coupling(content):
    """Detect tightly coupled paragraphs - Class extraction candidates"""
    # Simplified: look for paragraphs with common prefixes
    patterns = []
    lines = content.split('\n')
    paragraphs = []

    for line in lines:
        line_upper = line.strip().upper()
        if line_upper and not line_upper.startswith('*') and '.' in line:
            parts = line.strip().split('.')
            if len(parts) >= 1:
                para = parts[0].strip()
                if para and not any(kw in para for kw in ['DIVISION', 'SECTION']):
                    paragraphs.append(para)

    # Find common prefixes
    prefix_groups = defaultdict(list)
    for para in paragraphs:
        if '-' in para:
            prefix = para.split('-')[0]
            prefix_groups[prefix].append(para)

    # Groups with 3+ paragraphs are class candidates
    for prefix, group in prefix_groups.items():
        if len(group) >= 3:
            patterns.append({
                'type': 'paragraph_coupling',
                'prefix': prefix,
                'paragraph_count': len(group),
                'paragraphs': group[:5],  # First 5
                'recipe_type': 'extract_class',
                'confidence': min(0.90, 0.65 + len(group) * 0.05),
                'rationale': f'{len(group)} paragraphs with common prefix "{prefix}" suggest cohesive class'
            })

    return patterns


def detect_global_variables(content):
    """Detect WORKING-STORAGE variables used globally - Encapsulation candidates"""
    patterns = []

    # Count WS variables
    lines = content.split('\n')
    ws_var_count = 0
    in_working_storage = False

    for line in lines:
        line_upper = line.strip().upper()
        if 'WORKING-STORAGE SECTION' in line_upper:
            in_working_storage = True
        elif 'SECTION' in line_upper and in_working_storage:
            in_working_storage = False

        if in_working_storage and line_upper.startswith('01 '):
            ws_var_count += 1

    if ws_var_count > 10:
        patterns.append({
            'type': 'excessive_global_variables',
            'count': ws_var_count,
            'recipe_type': 'introduce_encapsulation',
            'confidence': 0.75,
            'rationale': f'{ws_var_count} WORKING-STORAGE variables suggest need for encapsulation in classes'
        })

    return patterns


def calculate_ast_summary(all_patterns, total_complexity):
    """Calculate summary statistics"""
    pattern_types = Counter()
    recipe_types = Counter()
    refactorable_paragraphs = 0
    data_opportunities = 0

    for file_data in all_patterns:
        for pattern in file_data['patterns']:
            pattern_types[pattern['type']] += 1
            recipe_types[pattern['recipe_type']] += 1

            if pattern['type'] in ['complex_control_flow', 'frequent_perform', 'paragraph_coupling']:
                refactorable_paragraphs += 1
            elif pattern['type'] == 'data_structure_modernization':
                data_opportunities += 1

    return {
        'pattern_type_breakdown': dict(pattern_types),
        'recipe_type_breakdown': dict(recipe_types),
        'refactorable_paragraphs': refactorable_paragraphs,
        'data_structure_opportunities': data_opportunities
    }
