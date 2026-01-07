#!/usr/bin/env python3
"""
Code Refactor V2 - Regex Pattern Detector V2
Detects refactorable patterns in COBOL using regex analysis
FOCUS: Transformation opportunities, NOT metrics

Uses shared job context helpers for consistent path handling.
"""

import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

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
    Detect patterns for refactoring recipes using regex analysis
    """

    try:
        print(f"Regex Pattern Detector V2 starting: {json.dumps(event)}")

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

        print(f"Analyzing {len(cobol_files)} files for refactor patterns")

        # Analyze each file for patterns
        all_patterns = []
        total_patterns = 0

        for file_path in cobol_files:
            file_key = job_ctx.get_file_key(file_path)

            try:
                file_response = s3_client.get_object(Bucket=bucket, Key=file_key)
                cobol_content = file_response['Body'].read().decode('utf-8', errors='ignore')

                # Detect patterns
                patterns = detect_refactor_patterns(cobol_content, file_path)

                if patterns:
                    all_patterns.append({
                        'path': file_path,
                        'patterns': patterns,
                        'pattern_count': len(patterns)
                    })
                    total_patterns += len(patterns)

            except Exception as e:
                print(f"Error analyzing {file_path}: {str(e)}")
                continue

        # Calculate summary
        summary = calculate_pattern_summary(all_patterns)

        # Build output
        output = {
            'job_id': job_ctx.job_id,
            'source_hash': job_ctx.source_hash,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'summary': {
                'total_files': len(cobol_files),
                'files_with_patterns': len(all_patterns),
                'total_patterns': total_patterns,
                **summary
            },
            'files': all_patterns
        }

        # Write to S3 using job context helper
        output_key = job_ctx.get_artifact_key('regex_patterns.json')
        s3_client.put_object(
            Bucket=bucket,
            Key=output_key,
            Body=json.dumps(output, indent=2),
            ContentType='application/json'
        )

        print(f"Regex pattern detection complete: {total_patterns} patterns found")

        return {
            'statusCode': 200,
            'body': {
                'status': 'completed',
                'patterns_found': total_patterns,
                'files_analyzed': len(cobol_files),
                'output_path': f"s3://{bucket}/{output_key}"
            }
        }

    except ValueError as e:
        # Missing required fields
        print(f"Validation error: {str(e)}")
        return error_response(400, str(e))

    except Exception as e:
        print(f"Error in regex pattern detection: {str(e)}")
        import traceback
        traceback.print_exc()
        return error_response(500, f"Pattern detection failed: {str(e)}")


def detect_refactor_patterns(cobol_content, file_path):
    """
    Detect refactorable patterns in COBOL code
    FOCUS: What can be transformed, not what exists
    """
    patterns = []
    lines = cobol_content.split('\n')

    # Pattern 1: Deeply Nested Conditionals (5+ levels)
    nested_if_patterns = detect_nested_conditionals(cobol_content, lines)
    patterns.extend(nested_if_patterns)

    # Pattern 2: GO TO Usage
    goto_patterns = detect_goto_usage(cobol_content, lines)
    patterns.extend(goto_patterns)

    # Pattern 3: Repeated Code Blocks
    duplicate_patterns = detect_duplicated_code(lines)
    patterns.extend(duplicate_patterns)

    # Pattern 4: Sequential File I/O
    file_io_patterns = detect_sequential_io(cobol_content, lines)
    patterns.extend(file_io_patterns)

    # Pattern 5: Level-88 Conditions (Enum candidates)
    level88_patterns = detect_level88_conditions(cobol_content, lines)
    patterns.extend(level88_patterns)

    # Pattern 6: Magic Numbers
    magic_number_patterns = detect_magic_numbers(cobol_content, lines)
    patterns.extend(magic_number_patterns)

    return patterns


def detect_nested_conditionals(content, lines):
    """Detect deeply nested IF statements (5+ levels) - Strategy Pattern candidates"""
    patterns = []

    # Track nesting depth
    current_depth = 0
    max_depth = 0
    start_line = 0
    in_if_block = False

    for i, line in enumerate(lines):
        line_upper = line.strip().upper()

        if re.match(r'^\s*IF\s+', line_upper):
            if current_depth == 0:
                start_line = i + 1
                in_if_block = True
            current_depth += 1
            max_depth = max(max_depth, current_depth)

        elif 'END-IF' in line_upper:
            current_depth = max(0, current_depth - 1)
            if current_depth == 0 and in_if_block and max_depth >= 5:
                patterns.append({
                    'type': 'deeply_nested_conditionals',
                    'location': f'Lines {start_line}-{i+1}',
                    'depth': max_depth,
                    'lines': [start_line, i+1],
                    'recipe_type': 'strategy_pattern',
                    'confidence': min(0.95, 0.70 + (max_depth - 5) * 0.05),
                    'rationale': f'{max_depth}-level nesting creates maintenance burden and testing complexity'
                })
                in_if_block = False
                max_depth = 0

    return patterns


def detect_goto_usage(content, lines):
    """Detect GO TO statements - State Machine candidates"""
    goto_locations = []

    for i, line in enumerate(lines):
        if re.search(r'\bGO\s+TO\b', line, re.IGNORECASE):
            # Extract target paragraph if possible
            match = re.search(r'GO\s+TO\s+([\w-]+)', line, re.IGNORECASE)
            target = match.group(1) if match else 'unknown'
            goto_locations.append({
                'line': i + 1,
                'target': target
            })

    if goto_locations:
        return [{
            'type': 'goto_usage',
            'count': len(goto_locations),
            'locations': goto_locations[:10],  # Limit to first 10
            'recipe_type': 'state_machine',
            'confidence': min(0.90, 0.75 + len(goto_locations) * 0.03),
            'rationale': f'{len(goto_locations)} GO TO statements create spaghetti code. State machine pattern enables testing and clarity.'
        }]

    return []


def detect_duplicated_code(lines):
    """Detect repeated code blocks - Extract Method candidates"""
    # Simple heuristic: find code blocks that appear multiple times
    code_blocks = {}

    # Create 5-line sliding window
    for i in range(len(lines) - 4):
        block = '\n'.join([l.strip() for l in lines[i:i+5] if l.strip()])
        if len(block) > 50:  # Only consider substantial blocks
            if block in code_blocks:
                code_blocks[block].append(i + 1)
            else:
                code_blocks[block] = [i + 1]

    patterns = []
    for block, occurrences in code_blocks.items():
        if len(occurrences) >= 3:  # Appears 3+ times
            patterns.append({
                'type': 'duplicated_code',
                'occurrences': len(occurrences),
                'locations': occurrences[:5],  # First 5 occurrences
                'recipe_type': 'extract_common_method',
                'confidence': min(0.95, 0.70 + len(occurrences) * 0.05),
                'rationale': f'Code block repeated {len(occurrences)} times. Extract to reusable method for DRY principle.'
            })

    return patterns


def detect_sequential_io(content, lines):
    """Detect sequential file I/O patterns - Stream API candidates"""
    patterns = []

    # Look for READ loops
    for i, line in enumerate(lines):
        if re.search(r'\bREAD\s+\w+', line, re.IGNORECASE):
            # Check if it's in a loop structure
            context = '\n'.join(lines[max(0, i-5):min(len(lines), i+10)])
            if re.search(r'\b(PERFORM|GO\s+TO)', context, re.IGNORECASE):
                patterns.append({
                    'type': 'sequential_file_io',
                    'location': f'Line {i+1}',
                    'lines': [i+1],
                    'recipe_type': 'stream_api',
                    'confidence': 0.85,
                    'rationale': 'Sequential file processing can use Java Stream API for cleaner, more functional code'
                })
                break  # One pattern per file for now

    return patterns


def detect_level88_conditions(content, lines):
    """Detect Level-88 conditions - Enum candidates"""
    level88_groups = []
    current_group = []
    parent_field = None

    for i, line in enumerate(lines):
        # Detect Level-88
        match = re.match(r'\s*88\s+([\w-]+)\s+VALUE', line, re.IGNORECASE)
        if match:
            current_group.append({
                'name': match.group(1),
                'line': i + 1
            })
        # Detect parent field (05 level)
        elif re.match(r'\s*05\s+([\w-]+)', line, re.IGNORECASE) and current_group:
            # End current group
            if len(current_group) >= 2:
                level88_groups.append({
                    'parent': parent_field,
                    'conditions': current_group,
                    'count': len(current_group)
                })
            current_group = []
            parent_field = re.match(r'\s*05\s+([\w-]+)', line, re.IGNORECASE).group(1)

    patterns = []
    for group in level88_groups:
        if group['count'] >= 2:
            patterns.append({
                'type': 'level88_conditions',
                'parent_field': group['parent'],
                'condition_count': group['count'],
                'conditions': [c['name'] for c in group['conditions']],
                'recipe_type': 'enum_pattern',
                'confidence': 0.97,
                'rationale': f"{group['count']} Level-88 conditions can be modernized to Java Enum for type safety"
            })

    return patterns


def detect_magic_numbers(content, lines):
    """Detect magic numbers - Constants candidates"""
    magic_numbers = []

    for i, line in enumerate(lines):
        # Find numeric literals (excluding common values like 0, 1)
        numbers = re.findall(r'\b(\d{2,})\b', line)
        for num in numbers:
            if int(num) > 1:  # Skip 0 and 1
                magic_numbers.append({
                    'value': num,
                    'line': i + 1
                })

    if len(magic_numbers) > 20:  # Threshold for meaningful pattern
        return [{
            'type': 'magic_numbers',
            'count': len(magic_numbers),
            'sample_values': list(set([m['value'] for m in magic_numbers[:10]])),
            'recipe_type': 'extract_constants',
            'confidence': 0.80,
            'rationale': f'{len(magic_numbers)} magic numbers found. Extract to named constants for clarity.'
        }]

    return []


def calculate_pattern_summary(all_patterns):
    """Calculate summary statistics across all detected patterns"""
    pattern_types = Counter()
    recipe_types = Counter()
    total_confidence = 0
    count = 0

    for file_data in all_patterns:
        for pattern in file_data['patterns']:
            pattern_types[pattern['type']] += 1
            recipe_types[pattern['recipe_type']] += 1
            total_confidence += pattern['confidence']
            count += 1

    return {
        'pattern_type_breakdown': dict(pattern_types),
        'recipe_type_breakdown': dict(recipe_types),
        'average_confidence': round(total_confidence / count, 2) if count > 0 else 0
    }
