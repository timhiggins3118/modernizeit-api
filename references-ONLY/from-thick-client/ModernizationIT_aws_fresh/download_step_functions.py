#!/usr/bin/env python3
"""
AWS Step Functions Downloader - READ-ONLY
"""

import boto3
import json
import os

REGION = 'us-east-1'
BASE_DIR = '/Users/timhiggins/Desktop/ModernizationIT_aws_fresh'

# Step Functions to Flow mapping
FLOW_MAP = {
    'CodeAnalysisWorkflowV2': '02_code_analysis_v2',
    'CodeRefactorWorkflowV2': '03_code_refactor_v2',
    'DependencyMapperWorkflowV2': '04_dependency_mapper_v2',
    'MonolithIdentifierWorkflowV2': '05_monolith_identifier_v2',
    'DataAnalysisWorkflowV2': '07_data_analyzer_v2',
    'DiscoveryWorkflowV2': '08_discovery_v2',
    'ArchitectureRecommendationWorkflowV2': '09_architecture_recommender_v2',
    'JavaGenerationWorkflowV2': '10_application_creator_jgv2',
    'JavaGenerationWorkflowV3': '11_application_creator_jgv3',
    'JavaCodeAnalysisWorkflowV3': '11_application_creator_jgv3',
    'JavaCodeFinalizationWorkflowV3': '11_application_creator_jgv3',
}

def main():
    client = boto3.client('stepfunctions', region_name=REGION)

    # List all state machines
    response = client.list_state_machines()

    downloaded = 0
    for sm in response['stateMachines']:
        name = sm['name']
        arn = sm['stateMachineArn']

        # Skip non-V2/V3
        if 'V2' not in name and 'V3' not in name:
            continue

        flow_dir = FLOW_MAP.get(name)
        if not flow_dir:
            print(f"⚠️  {name} - no flow mapping")
            continue

        print(f"{name}...", end=' ', flush=True)

        # Create directory
        sf_dir = os.path.join(BASE_DIR, flow_dir, 'step_functions')
        os.makedirs(sf_dir, exist_ok=True)

        # Download full definition
        full_response = client.describe_state_machine(stateMachineArn=arn)

        with open(os.path.join(sf_dir, f'{name}_full.json'), 'w') as f:
            json.dump(full_response, f, indent=2, default=str)

        # Extract ASL definition
        definition = json.loads(full_response['definition'])
        with open(os.path.join(sf_dir, f'{name}_definition.json'), 'w') as f:
            json.dump(definition, f, indent=2)

        print(f'✓ → {flow_dir}')
        downloaded += 1

    print(f"\n=== {downloaded} Step Functions downloaded ===")

if __name__ == '__main__':
    main()
