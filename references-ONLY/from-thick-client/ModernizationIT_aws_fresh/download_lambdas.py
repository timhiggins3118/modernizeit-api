#!/usr/bin/env python3
"""
AWS Lambda Downloader - READ-ONLY
Downloads all V2/V3 Lambda functions with progress tracking
"""

import boto3
import json
import os
import requests
import zipfile
from io import BytesIO

# AWS Configuration
REGION = 'us-east-1'
BASE_DIR = '/Users/timhiggins/Desktop/ModernizationIT_aws_fresh'

# Initialize AWS client
lambda_client = boto3.client('lambda', region_name=REGION)

# Flow definitions
FLOWS = {
    '03_code_refactor_v2': [
        'RefactorV2BedrockAnalyzerBatch', 'Refactor V2CreateJob', 'RefactorV2MergeRefactorBatches',
        'RefactorV2PrepareRefactorBatches', 'RefactorV2RecipeGenerator', 'RefactorV2RegexPatternDetector',
        'RefactorV2ResultsAPI', 'RefactorV2StatusAPI', 'RefactorV2TriggerWorkflow'
    ],
    '04_dependency_mapper_v2': [
        'DependencyMapperV2ASTParser', 'DependencyMapperV2BedrockAnalyzer', 'DependencyMapperV2CouplingAnalyzer',
        'DependencyMapperV2CreateJob', 'DependencyMapperV2GraphBuilder', 'DependencyMapperV2MergeDependency',
        'DependencyMapperV2MergeStatic', 'DependencyMapperV2ResultsAPI', 'DependencyMapperV2StartJob',
        'DependencyMapperV2StaticParser', 'DependencyMapperV2StatusAPI', 'DependencyMapperV2TriggerWorkflow'
    ],
    '05_monolith_identifier_v2': [
        'MonolithIdentifierV2AIAnalyzer', 'MonolithIdentifierV2CreateJob', 'MonolithIdentifierV2DecompositionStrategy',
        'MonolithIdentifierV2MergeAnalysis', 'MonolithIdentifierV2MergeStatic', 'MonolithIdentifierV2PatternDetector',
        'MonolithIdentifierV2ResultsAPI', 'MonolithIdentifierV2StartJob', 'MonolithIdentifierV2StatusAPI',
        'MonolithIdentifierV2TriggerWorkflow'
    ],
    '07_data_analyzer_v2': [
        'DataAnalysisV2ASTDataAnalyzer', 'DataAnalysisV2BedrockAnalyzerBatch', 'DataAnalysisV2CreateJob',
        'DataAnalysisV2ERDGenerator', 'DataAnalysisV2MergeAnalysis', 'DataAnalysisV2PrepareAIBatches',
        'DataAnalysisV2ResultsAPI', 'DataAnalysisV2StartJob', 'DataAnalysisV2StatusAPI',
        'DataAnalysisV2TriggerWorkflow'
    ],
    '08_discovery_v2': [
        'DiscoveryV2APIDetector', 'DiscoveryV2BedrockAnalyzerBatch', 'DiscoveryV2BusinessProcessExtractor',
        'DiscoveryV2CreateJob', 'DiscoveryV2IntegrationDetector', 'DiscoveryV2MergeDiscovery',
        'DiscoveryV2PrepareDiscoveryBatches', 'DiscoveryV2ResultsAPI', 'DiscoveryV2RoadmapGenerator',
        'DiscoveryV2StartJob', 'DiscoveryV2StatusAPI', 'DiscoveryV2TriggerWorkflow'
    ],
    '09_architecture_recommender_v2': [
        'ArchitectureRecommenderV2BedrockAnalyzer', 'ArchitectureRecommenderV2CostEstimator',
        'ArchitectureRecommenderV2IaCGenerator', 'ArchitectureRecommenderV2LoadReports',
        'ArchitectureRecommenderV2ResultsAPI', 'ArchitectureRecommenderV2StartJob',
        'ArchitectureRecommenderV2StatusAPI'
    ],
    '10_application_creator_jgv2': [
        'APIGeneratorV2', 'AWSIntegrationGeneratorV2', 'EntityGeneratorV2', 'JavaGenResultsV2',
        'JavaGenStatusV2', 'PackagerV2', 'PrepareGenerationV2', 'ProjectSetupV2',
        'RepositoryGeneratorV2', 'ServiceGeneratorV2', 'StartJavaGenerationV2',
        'TestGeneratorV2', 'ValidatorV2', 'ValidationEngineV2'
    ],
    '11_application_creator_jgv3': [
        'APIGeneratorV3', 'EntityGeneratorV3', 'JavaCodeAnalyzerV3', 'PackagerV3',
        'PrepareGenerationV3', 'ProjectSetupV3', 'RepositoryGeneratorV3',
        'ServiceGeneratorV3', 'StartCodeAnalysisV3', 'StartFinalizationV3',
        'StartJavaGenerationV3', 'TestGeneratorV3', 'ValidationEngineV3'
    ]
}

def download_lambda(func_name, flow_dir):
    """Download a single Lambda function"""
    print(f"  {func_name}...", end=' ', flush=True)

    func_dir = os.path.join(BASE_DIR, flow_dir, 'lambda_functions', func_name)
    os.makedirs(func_dir, exist_ok=True)

    try:
        # Get function metadata
        response = lambda_client.get_function(FunctionName=func_name)

        # Save full response
        with open(os.path.join(func_dir, 'function_full.json'), 'w') as f:
            json.dump(response, f, indent=2, default=str)

        # Check package type
        pkg_type = response['Configuration'].get('PackageType', 'Zip')

        if pkg_type == 'Image':
            # Container image
            image_uri = response['Code'].get('ImageUri', '')
            with open(os.path.join(func_dir, 'container_info.json'), 'w') as f:
                json.dump({'package_type': 'Image', 'image_uri': image_uri}, f, indent=2)
            print('📦 Container')
            return True

        # Download code ZIP
        code_url = response['Code'].get('Location')
        if not code_url:
            print('⚠️  No code URL')
            return False

        # Download and extract
        r = requests.get(code_url)
        if r.status_code == 200:
            with zipfile.ZipFile(BytesIO(r.content)) as z:
                z.extractall(os.path.join(func_dir, 'code'))
            print('✓ Downloaded')
            return True
        else:
            print(f'✗ HTTP {r.status_code}')
            return False

    except Exception as e:
        print(f'✗ {str(e)[:30]}')
        return False

def main():
    """Main download function"""
    total = 0
    success = 0
    containers = 0

    for flow_dir, functions in FLOWS.items():
        print(f"\n=== {flow_dir.upper()} ===")
        os.makedirs(os.path.join(BASE_DIR, flow_dir, 'lambda_functions'), exist_ok=True)

        for func in functions:
            total += 1
            if download_lambda(func, flow_dir):
                success += 1

    print(f"\n\n=== DOWNLOAD COMPLETE ===")
    print(f"Total: {total} | Success: {success} | Failed: {total - success}")

if __name__ == '__main__':
    main()
