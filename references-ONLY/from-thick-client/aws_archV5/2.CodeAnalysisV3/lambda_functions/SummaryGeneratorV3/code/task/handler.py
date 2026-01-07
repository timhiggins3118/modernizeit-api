"""
SummaryGeneratorV3 Lambda Handler

Purpose: Create V2-compatible static_analysis.json summary from V3 outputs
         for Architecture Recommender V2 backward compatibility

V3 Design Principles:
- Reads structural_context.json (TreeSitter aggregated stats)
- Reads ai_analyses/*.json files (Bedrock AI complexity)
- Generates lightweight summary (~5KB vs 373KB in V2)
- Architecture Recommender V2 works WITHOUT code changes
"""

import json
import boto3
from datetime import datetime, timezone
from typing import Dict, Any, List

s3_client = boto3.client('s3')

BUCKET_NAME = 'code-transformation-v2'


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Generate V2-compatible summary from V3 outputs

    Input (from Step Functions):
    {
        "job_id": "ca3_job_0U812_TestApp01_1762355296_d4901d79",
        "scout_account_id": "0U812",
        "application_name": "TestApp01",
        "source_hash": "f23f85de..."
    }

    Output:
    {
        "summary_generated": true,
        "summary_file": "s3://bucket/path/static_analysis.json",
        "stats": {...}
    }
    """
    try:
        print("=" * 80)
        print("SUMMARY GENERATOR V3 - Creating V2-compatible summary")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']
        source_hash = event.get('source_hash', 'unknown')

        print(f"Job ID: {job_id}")
        print(f"Account: {scout_account_id}, App: {application_name}")

        base_path = f"{scout_account_id}/{application_name}/code_analysis_v3/jobs/{job_id}"

        # Step 1: Read structural_context.json
        print("\n[1/4] Reading structural_context.json...")
        structural_context_key = f"{base_path}/artifacts/structural_context.json"

        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=structural_context_key)
            structural_context = json.loads(response['Body'].read().decode('utf-8'))
            print(f"✓ Structural context loaded: {len(json.dumps(structural_context))} bytes")
        except s3_client.exceptions.NoSuchKey:
            raise Exception(f"structural_context.json not found at {structural_context_key}")

        # Step 2: List all AI analysis files
        print("\n[2/4] Listing AI analysis files...")
        ai_analyses_prefix = f"{base_path}/ai_analyses/"

        paginator = s3_client.get_paginator('list_objects_v2')
        ai_files = []

        for page in paginator.paginate(Bucket=BUCKET_NAME, Prefix=ai_analyses_prefix):
            if 'Contents' in page:
                ai_files.extend([obj['Key'] for obj in page['Contents'] if obj['Key'].endswith('.json')])

        print(f"✓ Found {len(ai_files)} AI analysis files")

        # Step 3: Calculate aggregate stats
        print("\n[3/4] Calculating aggregate statistics...")
        summary = calculate_summary(structural_context, ai_files)
        print(f"✓ Summary calculated:")
        print(f"   - Total files: {summary['total_files']}")
        print(f"   - Total LOC: {summary['total_loc']}")
        print(f"   - Total programs: {summary['total_programs']}")
        print(f"   - Average complexity: {summary['average_complexity']:.1f}")
        print(f"   - Total paragraphs: {summary['total_paragraphs']}")
        print(f"   - Files with AI analysis: {summary['files_with_ai_analysis']}")

        # Step 4: Build V2-compatible output with files array for JavaGen V3
        print("\n[4/4] Building V2-compatible output...")

        # PHASE 1 FIX 2025-11-06: Build files array from V3 outputs for JavaGen V3
        print("   Building files array from V3 outputs...")
        files_array = build_files_array_from_v3(structural_context, ai_files)
        print(f"   ✓ Built files array with {len(files_array)} COBOL programs")

        static_analysis = {
            "schema_version": "v3.0_summary",
            "job_id": job_id,
            "source_hash": source_hash,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "files": files_array,  # PHASE 1: Populated for JavaGen V3
            "programs": [],  # Empty in V3 summary (Architecture Recommender doesn't use)
            "analyzers_used": ["TreeSitterAnalyzer", "BedrockAnalyzerPerFile"]
        }

        # Write to S3
        output_key = f"{base_path}/artifacts/static_analysis.json"
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=output_key,
            Body=json.dumps(static_analysis, indent=2),
            ContentType='application/json'
        )

        output_size = len(json.dumps(static_analysis))
        print(f"\n✓ Written to S3: s3://{BUCKET_NAME}/{output_key}")
        print(f"✓ File size: {output_size} bytes (~{output_size/1024:.1f} KB)")

        return {
            "summary_generated": True,
            "summary_file": f"s3://{BUCKET_NAME}/{output_key}",
            "summary_size_bytes": output_size,
            "stats": summary
        }

    except Exception as e:
        print(f"\nERROR in SummaryGeneratorV3: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def calculate_summary(structural_context: Dict[str, Any], ai_files: List[str]) -> Dict[str, Any]:
    """
    Calculate aggregate summary statistics from V3 outputs

    Args:
        structural_context: TreeSitter structural_context.json data
        ai_files: List of S3 keys for ai_analyses/*.json files

    Returns:
        Dictionary with V2-compatible summary fields
    """

    statistics = structural_context.get('statistics', {})
    files = structural_context.get('files', [])

    # 1. total_files - from structural_context.statistics
    total_files = statistics.get('total_files', 0)

    # 2. total_loc - sum all file.total_lines
    total_loc = 0
    for file in files:
        total_lines = file.get('total_lines')
        if total_lines and isinstance(total_lines, int):
            total_loc += total_lines

    # 3. total_programs - count COBOL_PROGRAM files
    total_programs = sum(
        1 for file in files
        if file.get('file_type') == 'COBOL_PROGRAM'
    )

    # 4. average_complexity - read AI analyses and map HIGH/MEDIUM/LOW to numbers
    average_complexity = calculate_average_complexity(ai_files)

    # 5. total_paragraphs - from structural_context.statistics
    total_paragraphs = statistics.get('total_paragraphs', 0)

    # 6. files_with_ai_analysis - count of AI analysis files
    files_with_ai_analysis = len(ai_files)

    return {
        "total_files": total_files,
        "total_loc": total_loc,
        "total_programs": total_programs,
        "average_complexity": average_complexity,
        "total_paragraphs": total_paragraphs,
        "files_with_ai_analysis": files_with_ai_analysis
    }


def calculate_average_complexity(ai_files: List[str]) -> float:
    """
    Calculate average complexity from AI analysis files

    Maps complexity strings to numbers:
    - HIGH → 15
    - MEDIUM → 10
    - LOW → 5

    Args:
        ai_files: List of S3 keys for ai_analyses/*.json files

    Returns:
        Average complexity as float
    """

    complexity_map = {
        'HIGH': 15,
        'MEDIUM': 10,
        'LOW': 5
    }

    complexities = []

    for ai_file_key in ai_files:
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=ai_file_key)
            ai_data = json.loads(response['Body'].read().decode('utf-8'))

            # Get complexity from program_level
            complexity_str = ai_data.get('program_level', {}).get('complexity', 'MEDIUM')
            complexity_value = complexity_map.get(complexity_str.upper(), 10)
            complexities.append(complexity_value)

        except Exception as e:
            print(f"Warning: Could not read {ai_file_key}: {str(e)}")
            # Default to MEDIUM if file can't be read
            complexities.append(10)

    # Calculate average
    if complexities:
        return sum(complexities) / len(complexities)
    else:
        return 0.0


def build_files_array_from_v3(structural_context: Dict[str, Any], ai_files: List[str]) -> List[Dict[str, Any]]:
    """
    PHASE 1 FIX 2025-11-06: Build V2-compatible files array from V3 outputs

    Maps V3 structure to V2 format that JavaGen V3 expects:
    - Reads structural_context for file metadata
    - Reads ai_analyses/*.json for paragraph business logic
    - Maps V3 paragraph structure → V2 paragraph_analysis format

    NOTE: Does NOT include java_method.code field (Phase 2)
          ServiceGeneratorV3 will generate TODO stubs

    Args:
        structural_context: TreeSitter structural_context.json data
        ai_files: List of S3 keys for ai_analyses/*.json files

    Returns:
        List of file dictionaries in V2 format
    """

    files_array = []
    files_data = structural_context.get('files', [])

    # Create map of filename → AI analysis key
    ai_files_map = {}
    for ai_key in ai_files:
        # Extract filename from key: "...ai_analyses/CMCMCL00.CBL_ai_analysis.json"
        filename = ai_key.split('/')[-1].replace('_ai_analysis.json', '')
        ai_files_map[filename] = ai_key

    for file_data in files_data:
        file_name = file_data.get('file_name', '')
        file_type = file_data.get('file_type', '')

        # ONLY include COBOL programs (JavaGen doesn't need copybooks, JCL, etc.)
        if file_type != 'COBOL_PROGRAM':
            continue

        # Extract program_id from filename
        program_id = file_name.replace('.CBL', '').replace('.cbl', '').replace('.COBOL', '').replace('.cobol', '')

        # Find corresponding AI analysis
        ai_key = ai_files_map.get(file_name)
        paragraph_analysis = []

        if ai_key:
            try:
                response = s3_client.get_object(Bucket=BUCKET_NAME, Key=ai_key)
                ai_data = json.loads(response['Body'].read().decode('utf-8'))

                # Map V3 paragraphs → V2 paragraph_analysis format
                v3_paragraphs = ai_data.get('paragraphs', [])
                for v3_para in v3_paragraphs:
                    # V2 format expected by JavaGen
                    v2_para = {
                        'name': v3_para.get('name', ''),
                        'business_purpose': v3_para.get('business_logic', ''),
                        'cobol_logic': v3_para.get('data_flow', ''),
                        'dependencies': v3_para.get('dependencies', []),
                        'criticality': v3_para.get('complexity', 'MEDIUM'),
                        # NOTE: NO java_method.code field (Phase 2 needed)
                        # ServiceGeneratorV3 will generate TODO stub
                    }
                    paragraph_analysis.append(v2_para)

                print(f"      {file_name}: Mapped {len(paragraph_analysis)} paragraphs")

            except Exception as e:
                print(f"      Warning: Could not read AI analysis for {file_name}: {str(e)}")

        # Build V2-compatible file entry
        file_entry = {
            'path': file_name,
            'program_id': program_id,
            'size': file_data.get('total_lines', 0),
            'paragraph_analysis': paragraph_analysis,
            'regex_findings': {
                'metrics': {
                    'lines_of_code': file_data.get('total_lines', 0),
                    'paragraph_count': file_data.get('paragraph_count', 0)
                },
                'code_quality': {
                    'cyclomatic_complexity': 0  # Placeholder
                }
            }
        }

        files_array.append(file_entry)

    return files_array
