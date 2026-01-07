"""
AI-Based Data Analyzer for Data Analysis

Uses the unified BedrockAgent for AI-powered data structure analysis.

Features:
- Business entity identification
- Relationship discovery
- Data lineage tracing
- Business meaning inference
- Parallel processing for performance
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from engines.ai import BedrockAgent


@dataclass
class AIEntityAnalysis:
    """AI-identified business entity."""
    entity_name: str
    cobol_record: str
    business_purpose: str
    suggested_table_name: str
    confidence: float
    key_fields: List[str] = field(default_factory=list)
    attributes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AIRelationship:
    """AI-identified relationship between entities."""
    from_entity: str
    to_entity: str
    relationship_type: str
    cardinality: str
    business_rule: str
    confidence: float
    join_fields: List[str] = field(default_factory=list)


@dataclass
class AIDataFlow:
    """AI-identified data flow."""
    flow_name: str
    source: str
    destination: str
    transformations: List[str]
    business_purpose: str


class AIDataAnalyzer:
    """
    AI-powered data analyzer using BedrockAgent.

    Analyzes COBOL data structures to identify:
    1. Business entities (what real-world things the data represents)
    2. Relationships between entities
    3. Data lineage (how data flows through the program)
    4. Business meanings for fields
    """

    def __init__(
        self,
        region: str = "us-east-1",
        max_workers: int = 4,
        log_fn: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize AI analyzer.

        Args:
            region: AWS region for Bedrock
            max_workers: Maximum concurrent Bedrock calls (default 4)
            log_fn: Optional logging function (default: print)
        """
        self.region = region
        self.max_workers = max_workers
        self.log_fn = log_fn or print
        self.agent = BedrockAgent.create(
            purpose="code_analysis",
            max_workers=max_workers,
            log_fn=log_fn
        )

    def analyze_directory(
        self,
        source_path: str,
        regex_results: Optional[Dict[str, Any]] = None,
        ast_results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze all COBOL files in directory using AI.

        Args:
            source_path: Path to COBOL source files
            regex_results: Optional results from regex extractor
            ast_results: Optional results from AST analyzer

        Returns:
            Combined AI analysis results
        """
        source_dir = Path(source_path)
        start_time = time.time()

        # Find all COBOL files
        cobol_patterns = ['*.cbl', '*.CBL', '*.cob', '*.COB']
        cobol_files = []

        for pattern in cobol_patterns:
            cobol_files.extend(source_dir.rglob(pattern))

        # Filter out junk files
        cobol_files = [
            f for f in cobol_files
            if '__MACOSX' not in str(f) and not f.name.startswith('.')
        ]

        total_files = len(cobol_files)
        self.log_fn(f"[AI Analysis] Found {total_files} COBOL files to analyze")

        # Prepare file data for parallel processing
        file_data_list = []
        for file_path in cobol_files:
            try:
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                relative_path = str(file_path.relative_to(source_dir))

                # Get pre-analysis context if available
                file_context = None
                if regex_results:
                    for f in regex_results.get('files', []):
                        if f.get('file_path') == relative_path:
                            file_context = f.get('data_structures')
                            break

                file_data_list.append({
                    'content': content,
                    'relative_path': relative_path,
                    'file_context': file_context,
                    'file_path': file_path
                })
            except Exception as e:
                self.log_fn(f"[AI Analysis] Error reading {file_path}: {e}")

        # Process files in parallel using BedrockAgent
        results = self.agent.invoke_batch(
            items=file_data_list,
            prompt_fn=lambda fd: self._build_analysis_prompt(
                fd['content'],
                fd['relative_path'],
                fd['file_context']
            ),
            item_id_fn=lambda fd: fd['relative_path'],
            parse_json=True,
            progress_prefix="[AI Analysis]"
        )

        # Collect results
        file_analyses: List[Dict] = []
        all_entities = []
        all_relationships = []
        all_data_flows = []
        all_business_meanings = {}

        for result in results:
            if result.success and result.result:
                analysis = result.result
                analysis['file_path'] = result.item_id
                file_analyses.append(analysis)

                all_entities.extend(analysis.get('entities', []))
                all_relationships.extend(analysis.get('relationships', []))
                all_data_flows.extend(analysis.get('data_flows', []))
                all_business_meanings.update(analysis.get('business_meanings', {}))

        duration_ms = int((time.time() - start_time) * 1000)
        success_count = sum(1 for r in results if r.success)

        self.log_fn(f"[AI Analysis] Complete: {success_count}/{total_files} files in {duration_ms}ms")

        return {
            'summary': {
                'total_files_analyzed': len(file_analyses),
                'total_entities': len(all_entities),
                'total_relationships': len(all_relationships),
                'total_data_flows': len(all_data_flows),
                'success_count': success_count,
                'total_files': total_files,
                'duration_ms': duration_ms
            },
            'file_analyses': file_analyses,
            'entities': all_entities,
            'relationships': all_relationships,
            'data_flows': all_data_flows,
            'business_meanings': all_business_meanings
        }

    def analyze_file(
        self,
        content: str,
        file_path: str,
        pre_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a single COBOL file using AI.

        Args:
            content: COBOL source code
            file_path: Relative file path
            pre_analysis: Optional pre-analysis from regex/AST

        Returns:
            Analysis results for the file
        """
        prompt = self._build_analysis_prompt(content, file_path, pre_analysis)

        try:
            result = self.agent.invoke_json(prompt)
            if result:
                result['file_path'] = file_path
                return result
            else:
                return self._empty_result(file_path, "Failed to parse response")
        except Exception as e:
            self.log_fn(f"AI analysis failed for {file_path}: {e}")
            return self._empty_result(file_path, str(e))

    def _build_analysis_prompt(
        self,
        content: str,
        file_path: str,
        pre_analysis: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build the analysis prompt for Claude."""
        # Truncate content if too long
        max_content_length = 12000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n... [truncated]"

        pre_analysis_text = ""
        if pre_analysis:
            ws_count = len(pre_analysis.get('working_storage', []))
            fs_count = len(pre_analysis.get('file_section', []))
            ls_count = len(pre_analysis.get('linkage_section', []))
            cb_count = len(pre_analysis.get('copybooks', []))
            pre_analysis_text = f"""
Pre-Analysis Summary:
- Working Storage Records: {ws_count}
- File Section Entries: {fs_count}
- Linkage Section Records: {ls_count}
- Copybooks: {cb_count}
"""

        return f"""Analyze this COBOL file for database design and data modeling.

File: {file_path}
{pre_analysis_text}

COBOL Code:
{content}

Provide your analysis as JSON with this exact structure:
{{
    "entities": [
        {{
            "entity_name": "PascalCaseName",
            "cobol_record": "ORIGINAL-COBOL-NAME",
            "business_purpose": "What this entity represents in business terms",
            "suggested_table_name": "lowercase_table_name",
            "confidence": 0.0-1.0,
            "key_fields": ["field1", "field2"],
            "attributes": [
                {{
                    "name": "attribute_name",
                    "cobol_field": "COBOL-FIELD-NAME",
                    "business_meaning": "What this field means",
                    "is_key": true/false
                }}
            ]
        }}
    ],
    "relationships": [
        {{
            "from_entity": "EntityA",
            "to_entity": "EntityB",
            "relationship_type": "one-to-many|many-to-one|one-to-one|many-to-many",
            "cardinality": "1:N|N:1|1:1|M:N",
            "business_rule": "Describe the business rule",
            "confidence": 0.0-1.0,
            "join_fields": ["field_name"]
        }}
    ],
    "data_flows": [
        {{
            "flow_name": "Descriptive name",
            "source": "Source file/record",
            "destination": "Destination file/record",
            "transformations": ["transformation1", "transformation2"],
            "business_purpose": "What this flow accomplishes"
        }}
    ],
    "business_meanings": {{
        "COBOL-FIELD-NAME": "Human readable business meaning"
    }}
}}

Focus on:
1. Identifying real business entities from data structures
2. Finding relationships between entities based on common fields
3. Tracing data flow through READ/WRITE/MOVE operations
4. Providing meaningful business context for field names

Return ONLY valid JSON, no markdown formatting."""

    def _empty_result(self, file_path: str, error: str) -> Dict[str, Any]:
        """Return empty result structure with error."""
        return {
            'file_path': file_path,
            'entities': [],
            'relationships': [],
            'data_flows': [],
            'business_meanings': {},
            'error': error
        }
