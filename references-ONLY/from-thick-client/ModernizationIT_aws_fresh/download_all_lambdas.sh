#!/bin/bash
# Master Lambda Download Script - ALL V2/V3 Flows
# READ-ONLY operation

set -e

BASE_DIR="/Users/timhiggins/Desktop/ModernizationIT_aws_fresh"
REGION="us-east-1"

# Function to download Lambda metadata and code
download_lambda() {
    local func_name=$1
    local flow_dir=$2

    echo "  $func_name..."

    func_dir="$BASE_DIR/$flow_dir/lambda_functions/$func_name"
    mkdir -p "$func_dir"

    # Download function metadata
    aws lambda get-function --function-name "$func_name" --region $REGION > "$func_dir/function_full.json" 2>&1

    if [ $? -ne 0 ]; then
        echo "    ✗ Failed to get function metadata"
        return
    fi

    # Extract code location
    code_url=$(cat "$func_dir/function_full.json" | jq -r '.Code.Location' 2>/dev/null || echo "")

    if [ -z "$code_url" ] || [ "$code_url" == "null" ]; then
        # Check if it's a container image
        pkg_type=$(cat "$func_dir/function_full.json" | jq -r '.Configuration.PackageType' 2>/dev/null || echo "Zip")
        if [ "$pkg_type" == "Image" ]; then
            echo "    📦 Container"
            image_uri=$(cat "$func_dir/function_full.json" | jq -r '.Code.ImageUri' 2>/dev/null)
            echo "{\"package_type\": \"Image\", \"image_uri\": \"$image_uri\"}" > "$func_dir/container_info.json"
        else
            echo "    ⚠️  No code URL"
        fi
        return
    fi

    # Download and extract ZIP
    mkdir -p "$func_dir/code"
    curl -s "$code_url" -o "$func_dir/code.zip"

    if [ $? -eq 0 ] && [ -f "$func_dir/code.zip" ]; then
        cd "$func_dir"
        unzip -q -o code.zip -d code/ 2>/dev/null
        rm code.zip
        echo "    ✓ Downloaded"
    else
        echo "    ✗ Download failed"
    fi
}

# Code Refactor V2
echo "=== CODE REFACTOR V2 ==="
mkdir -p "$BASE_DIR/03_code_refactor_v2/lambda_functions"
for func in RefactorV2BedrockAnalyzerBatch RefactorV2CreateJob RefactorV2MergeRefactorBatches \
            RefactorV2PrepareRefactorBatches RefactorV2RecipeGenerator RefactorV2RegexPatternDetector \
            RefactorV2ResultsAPI RefactorV2StatusAPI RefactorV2TriggerWorkflow; do
    download_lambda "$func" "03_code_refactor_v2"
done

# Dependency Mapper V2
echo ""
echo "=== DEPENDENCY MAPPER V2 ==="
mkdir -p "$BASE_DIR/04_dependency_mapper_v2/lambda_functions"
for func in DependencyMapperV2ASTParser DependencyMapperV2BedrockAnalyzer DependencyMapperV2CouplingAnalyzer \
            DependencyMapperV2CreateJob DependencyMapperV2GraphBuilder DependencyMapperV2MergeDependency \
            DependencyMapperV2MergeStatic DependencyMapperV2ResultsAPI DependencyMapperV2StartJob \
            DependencyMapperV2StaticParser DependencyMapperV2StatusAPI DependencyMapperV2TriggerWorkflow; do
    download_lambda "$func" "04_dependency_mapper_v2"
done

# Monolith Identifier V2
echo ""
echo "=== MONOLITH IDENTIFIER V2 ==="
mkdir -p "$BASE_DIR/05_monolith_identifier_v2/lambda_functions"
for func in MonolithIdentifierV2AIAnalyzer MonolithIdentifierV2CreateJob MonolithIdentifierV2DecompositionStrategy \
            MonolithIdentifierV2MergeAnalysis MonolithIdentifierV2MergeStatic MonolithIdentifierV2PatternDetector \
            MonolithIdentifierV2ResultsAPI MonolithIdentifierV2StartJob MonolithIdentifierV2StatusAPI \
            MonolithIdentifierV2TriggerWorkflow; do
    download_lambda "$func" "05_monolith_identifier_v2"
done

# Data Analyzer V2
echo ""
echo "=== DATA ANALYZER V2 ==="
mkdir -p "$BASE_DIR/07_data_analyzer_v2/lambda_functions"
for func in DataAnalysisV2ASTDataAnalyzer DataAnalysisV2BedrockAnalyzerBatch DataAnalysisV2CreateJob \
            DataAnalysisV2ERDGenerator DataAnalysisV2MergeAnalysis DataAnalysisV2PrepareAIBatches \
            DataAnalysisV2ResultsAPI DataAnalysisV2StartJob DataAnalysisV2StatusAPI \
            DataAnalysisV2TriggerWorkflow; do
    download_lambda "$func" "07_data_analyzer_v2"
done

# Discovery V2
echo ""
echo "=== DISCOVERY V2 ==="
mkdir -p "$BASE_DIR/08_discovery_v2/lambda_functions"
for func in DiscoveryV2APIDetector DiscoveryV2BedrockAnalyzerBatch DiscoveryV2BusinessProcessExtractor \
            DiscoveryV2CreateJob DiscoveryV2IntegrationDetector DiscoveryV2MergeDiscovery \
            DiscoveryV2PrepareDiscoveryBatches DiscoveryV2ResultsAPI DiscoveryV2RoadmapGenerator \
            DiscoveryV2StartJob DiscoveryV2StatusAPI DiscoveryV2TriggerWorkflow; do
    download_lambda "$func" "08_discovery_v2"
done

# Architecture Recommender V2
echo ""
echo "=== ARCHITECTURE RECOMMENDER V2 ==="
mkdir -p "$BASE_DIR/09_architecture_recommender_v2/lambda_functions"
for func in ArchitectureRecommenderV2BedrockAnalyzer ArchitectureRecommenderV2CostEstimator \
            ArchitectureRecommenderV2IaCGenerator ArchitectureRecommenderV2LoadReports \
            ArchitectureRecommenderV2ResultsAPI ArchitectureRecommenderV2StartJob \
            ArchitectureRecommenderV2StatusAPI; do
    download_lambda "$func" "09_architecture_recommender_v2"
done

# Java Gen V2
echo ""
echo "=== JAVA GENERATION V2 ==="
mkdir -p "$BASE_DIR/10_application_creator_jgv2/lambda_functions"
for func in APIGeneratorV2 AWSIntegrationGeneratorV2 EntityGeneratorV2 JavaGenResultsV2 \
            JavaGenStatusV2 PackagerV2 PrepareGenerationV2 ProjectSetupV2 \
            RepositoryGeneratorV2 ServiceGeneratorV2 StartJavaGenerationV2 \
            TestGeneratorV2 ValidatorV2 ValidationEngineV2; do
    download_lambda "$func" "10_application_creator_jgv2"
done

# Java Gen V3
echo ""
echo "=== JAVA GENERATION V3 ==="
mkdir -p "$BASE_DIR/11_application_creator_jgv3/lambda_functions"
for func in APIGeneratorV3 EntityGeneratorV3 JavaCodeAnalyzerV3 PackagerV3 \
            PrepareGenerationV3 ProjectSetupV3 RepositoryGeneratorV3 \
            ServiceGeneratorV3 StartCodeAnalysisV3 StartFinalizationV3 \
            StartJavaGenerationV3 TestGeneratorV3 ValidationEngineV3; do
    download_lambda "$func" "11_application_creator_jgv3"
done

# Ingesting (if exists)
echo ""
echo "=== INGESTING ==="
mkdir -p "$BASE_DIR/01_ingesting/lambda_functions"
for func in IngestUpload IngestHandler IngestProcessor; do
    download_lambda "$func" "01_ingesting" 2>/dev/null || echo "  ⚠️  $func not found (may not exist)"
done

echo ""
echo "================================================================"
echo "=== LAMBDA DOWNLOAD COMPLETE ==="
echo "================================================================"
