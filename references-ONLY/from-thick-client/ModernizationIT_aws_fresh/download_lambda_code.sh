#!/bin/bash
# Download Lambda function code for all V2/V3 functions
# READ-ONLY operation

set -e

BASE_DIR="/Users/timhiggins/Desktop/ModernizationIT_aws_fresh"

# Function to download code for a Lambda function
download_lambda_code() {
    local func_name=$1
    local flow_dir=$2

    echo "Processing $func_name..."

    func_dir="$BASE_DIR/$flow_dir/lambda_functions/$func_name"

    if [ ! -f "$func_dir/function_full.json" ]; then
        echo "  ⚠️  function_full.json not found, skipping"
        return
    fi

    # Extract code location
    code_url=$(cat "$func_dir/function_full.json" | jq -r '.Code.Location' 2>/dev/null || echo "")

    if [ -z "$code_url" ] || [ "$code_url" == "null" ]; then
        # Check if it's a container image
        pkg_type=$(cat "$func_dir/function_full.json" | jq -r '.Configuration.PackageType' 2>/dev/null || echo "Zip")
        if [ "$pkg_type" == "Image" ]; then
            echo "  📦 Container image detected - will download later"
            echo '{"package_type": "Image"}' > "$func_dir/container_info.json"
        else
            echo "  ✗ No code URL found"
        fi
        return
    fi

    # Download ZIP file
    mkdir -p "$func_dir/code"
    curl -s "$code_url" -o "$func_dir/code.zip"

    if [ $? -eq 0 ] && [ -f "$func_dir/code.zip" ]; then
        # Extract ZIP
        cd "$func_dir"
        unzip -q -o code.zip -d code/
        rm code.zip
        echo "  ✓ Code extracted"
    else
        echo "  ✗ Download failed"
    fi
}

# Download Code Analysis V2
echo "=== CODE ANALYSIS V2 ==="
for func in CodeAnalysisV2BedrockAnalyzer CodeAnalysisV2BedrockAnalyzerBatch CodeAnalysisV2CreateJob \
            CodeAnalysisV2MergeAIBatches CodeAnalysisV2MergeAnalysis CodeAnalysisV2PrepareAIBatches \
            CodeAnalysisV2RegexAnalyzer CodeAnalysisV2ResultsAPI CodeAnalysisV2StaticPython2 \
            CodeAnalysisV2StatusAPI CodeAnalysisV2TreeSitterAnalyzer CodeAnalysisV2TriggerAnalysis; do
    download_lambda_code "$func" "02_code_analysis_v2"
done

echo ""
echo "=== DOWNLOAD COMPLETE ==="
