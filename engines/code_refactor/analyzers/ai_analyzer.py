"""
AI-Based Analyzer for Code Refactoring

Uses the unified BedrockAgent to interpret rule-based findings and provide
semantic understanding for refactoring recommendations.

This is the second layer of the hybrid approach - intelligent interpretation.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from engines.ai import BedrockAgent
from engines.code_refactor.analyzers.rule_analyzer import PatternMatch, RuleAnalysisResult


@dataclass
class AIRecommendation:
    """An AI-generated refactoring recommendation."""
    recommendation_id: str
    category: str  # "class_structure", "naming", "types", "control_flow", "patterns"
    title: str
    description: str
    priority: str  # "high", "medium", "low"
    confidence: float
    affected_elements: List[str]
    proposed_changes: List[Dict[str, Any]]
    rationale: str
    risks: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)


@dataclass
class AIAnalysisResult:
    """Results from AI analysis."""
    java_file: str
    class_name: str
    recommendations: List[AIRecommendation]
    summary: Dict[str, Any]
    raw_analysis: Optional[str] = None


class AIAnalyzer:
    """
    AI-powered analyzer using BedrockAgent.

    Takes rule-based findings and uses AI to:
    1. Interpret field groupings semantically (what business concept?)
    2. Suggest meaningful names for methods/classes
    3. Propose class splitting strategies
    4. Identify business logic boundaries
    5. Recommend modern Java patterns
    """

    def __init__(
        self,
        region: str = "us-east-1",
        log_fn: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize AI analyzer.

        Args:
            region: AWS region for Bedrock
            log_fn: Optional logging function
        """
        self.region = region
        self.log_fn = log_fn or print
        self.agent = BedrockAgent.create(
            purpose="refactor",
            log_fn=log_fn
        )

    def analyze(
        self,
        rule_results: RuleAnalysisResult,
        java_content: Optional[str] = None,
        semantic_context: Optional[Dict[str, Any]] = None,
    ) -> AIAnalysisResult:
        """
        Analyze Java code using AI, informed by rule-based findings.

        Args:
            rule_results: Results from RuleAnalyzer
            java_content: Optional Java source code (first N lines for context)
            semantic_context: Optional COBOL semantic models for context

        Returns:
            AIAnalysisResult with recommendations
        """
        prompt = self._build_analysis_prompt(rule_results, java_content, semantic_context)

        try:
            response = self.agent.invoke(prompt)
            raw_analysis = response

            # Parse AI response into recommendations
            recommendations = self._parse_response(response, rule_results)

            # Build summary
            summary = self._build_summary(recommendations)

            return AIAnalysisResult(
                java_file=rule_results.java_file,
                class_name=rule_results.class_name,
                recommendations=recommendations,
                summary=summary,
                raw_analysis=raw_analysis,
            )

        except Exception as e:
            self.log_fn(f"[AI Refactor] Analysis failed: {e}")
            return AIAnalysisResult(
                java_file=rule_results.java_file,
                class_name=rule_results.class_name,
                recommendations=[],
                summary={
                    "error": str(e),
                    "total_recommendations": 0,
                },
                raw_analysis=None,
            )

    def _build_analysis_prompt(
        self,
        rule_results: RuleAnalysisResult,
        java_content: Optional[str],
        semantic_context: Optional[Dict[str, Any]],
    ) -> str:
        """Build the prompt for AI analysis."""
        prompt_parts = []

        prompt_parts.append("""You are a senior Java architect analyzing generated COBOL-to-Java code for modernization.

The code was automatically converted from COBOL and needs refactoring to be idiomatic, maintainable Java.

Your task is to analyze the rule-based findings and provide specific, actionable refactoring recommendations.

For each recommendation, provide:
1. A clear title and description
2. Priority (high/medium/low)
3. Specific elements affected
4. Proposed changes with rationale
5. Any risks or prerequisites

Focus on:
- Semantic grouping (what business concepts do field/method groups represent?)
- Modern Java patterns (services, DTOs, enums, streams)
- Meaningful naming (translate COBOL conventions to Java conventions)
- Class splitting strategy (which classes to extract, what to name them)
- Type modernization (BigDecimal to int where appropriate, arrays to Lists)
""")

        # Add rule-based findings
        prompt_parts.append("\n## Rule-Based Findings\n")
        prompt_parts.append(f"Class: {rule_results.class_name}")
        prompt_parts.append(f"File: {rule_results.java_file}")
        prompt_parts.append(f"\nMetrics:")
        for key, value in rule_results.metrics.items():
            prompt_parts.append(f"  - {key}: {value}")

        prompt_parts.append(f"\n\nDetected Patterns ({len(rule_results.patterns)} total):\n")
        for i, pattern in enumerate(rule_results.patterns, 1):
            prompt_parts.append(f"\n### Pattern {i}: {pattern.pattern_type}")
            prompt_parts.append(f"- Severity: {pattern.severity}")
            prompt_parts.append(f"- Confidence: {pattern.confidence:.2f}")
            prompt_parts.append(f"- Details: {pattern.details}")
            prompt_parts.append(f"- Suggested Recipe: {pattern.suggested_recipe}")
            if pattern.evidence:
                prompt_parts.append(f"- Evidence: {json.dumps(pattern.evidence, indent=2)}")

        # Add Java content snippet if provided
        if java_content:
            lines = java_content.split('\n')[:200]  # First 200 lines
            prompt_parts.append("\n\n## Java Code Sample (first 200 lines):\n```java")
            prompt_parts.append('\n'.join(lines))
            prompt_parts.append("```")

        # Add semantic context if provided
        if semantic_context:
            prompt_parts.append("\n\n## COBOL Semantic Context:")
            if 'data_model' in semantic_context:
                dm = semantic_context['data_model']
                prompt_parts.append(f"\nData Model: {dm.get('summary', {})}")
            if 'procedure_model' in semantic_context:
                pm = semantic_context['procedure_model']
                prompt_parts.append(f"\nProcedure Model: {pm.get('summary', {})}")

        prompt_parts.append("""

## Response Format

Provide your analysis as a JSON array of recommendations:

```json
[
  {
    "category": "class_structure",
    "title": "Extract Tax Calculation Service",
    "description": "47 tax-related fields and 12 methods should be extracted to TaxCalculationService",
    "priority": "high",
    "confidence": 0.90,
    "affected_elements": ["taxCppFedSum", "taxCppSttSum", "calculateTax_300_400()"],
    "proposed_changes": [
      {
        "type": "extract_class",
        "new_class": "TaxCalculationService",
        "fields_to_move": ["taxCppFedSum", "taxCppSttSum"],
        "methods_to_move": ["calculateTax_300_400()"]
      }
    ],
    "rationale": "Tax calculations form a cohesive business domain that should be encapsulated",
    "risks": ["May require updating method references in main class"],
    "prerequisites": ["Ensure no circular dependencies"]
  }
]
```

Provide 3-10 specific, actionable recommendations.
""")

        return '\n'.join(prompt_parts)

    def _parse_response(
        self,
        response: str,
        rule_results: RuleAnalysisResult
    ) -> List[AIRecommendation]:
        """Parse AI response into structured recommendations."""
        recommendations = []

        # Try to extract JSON from response
        try:
            # Find JSON array in response
            json_start = response.find('[')
            json_end = response.rfind(']') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                parsed = json.loads(json_str)

                for i, rec in enumerate(parsed):
                    recommendations.append(AIRecommendation(
                        recommendation_id=f"ai_rec_{i+1:03d}",
                        category=rec.get('category', 'general'),
                        title=rec.get('title', 'Untitled'),
                        description=rec.get('description', ''),
                        priority=rec.get('priority', 'medium'),
                        confidence=rec.get('confidence', 0.75),
                        affected_elements=rec.get('affected_elements', []),
                        proposed_changes=rec.get('proposed_changes', []),
                        rationale=rec.get('rationale', ''),
                        risks=rec.get('risks', []),
                        prerequisites=rec.get('prerequisites', []),
                    ))
        except json.JSONDecodeError:
            # If JSON parsing fails, create basic recommendations from rule results
            for i, pattern in enumerate(rule_results.patterns[:5]):
                recommendations.append(AIRecommendation(
                    recommendation_id=f"fallback_rec_{i+1:03d}",
                    category="general",
                    title=f"Address {pattern.pattern_type}",
                    description=pattern.details,
                    priority=pattern.severity,
                    confidence=pattern.confidence,
                    affected_elements=list(pattern.location.values())[:5],
                    proposed_changes=[{"type": pattern.suggested_recipe}],
                    rationale=f"Detected by rule analyzer with {pattern.confidence:.0%} confidence",
                    risks=[],
                    prerequisites=[],
                ))

        return recommendations

    def _build_summary(self, recommendations: List[AIRecommendation]) -> Dict[str, Any]:
        """Build summary of AI analysis."""
        high_priority = [r for r in recommendations if r.priority == "high"]
        medium_priority = [r for r in recommendations if r.priority == "medium"]
        low_priority = [r for r in recommendations if r.priority == "low"]

        category_counts: Dict[str, int] = {}
        for r in recommendations:
            category_counts[r.category] = category_counts.get(r.category, 0) + 1

        return {
            "total_recommendations": len(recommendations),
            "high_priority": len(high_priority),
            "medium_priority": len(medium_priority),
            "low_priority": len(low_priority),
            "category_breakdown": category_counts,
            "avg_confidence": sum(r.confidence for r in recommendations) / max(1, len(recommendations)),
            "top_recommendations": [r.title for r in high_priority[:3]],
        }

    def analyze_without_bedrock(
        self,
        rule_results: RuleAnalysisResult
    ) -> AIAnalysisResult:
        """
        Generate recommendations without calling Bedrock.

        Useful for testing or when Bedrock is unavailable.
        Creates recommendations directly from rule patterns.
        """
        recommendations = []

        for i, pattern in enumerate(rule_results.patterns):
            rec = self._pattern_to_recommendation(pattern, i + 1)
            if rec:
                recommendations.append(rec)

        summary = self._build_summary(recommendations)

        return AIAnalysisResult(
            java_file=rule_results.java_file,
            class_name=rule_results.class_name,
            recommendations=recommendations,
            summary=summary,
            raw_analysis=None,
        )

    def _pattern_to_recommendation(
        self,
        pattern: PatternMatch,
        index: int
    ) -> Optional[AIRecommendation]:
        """Convert a rule pattern to an AI recommendation."""
        pattern_map = {
            "class_too_large": {
                "category": "class_structure",
                "title": "Split Large Class",
                "description": "Class exceeds size threshold and should be split into smaller, focused classes",
            },
            "too_many_fields": {
                "category": "class_structure",
                "title": "Extract Field Groups to Classes",
                "description": "Too many fields suggest multiple responsibilities - extract to separate classes",
            },
            "field_grouping": {
                "category": "class_structure",
                "title": f"Extract Class for '{pattern.evidence.get('prefix', 'grouped')}' Fields",
                "description": f"Fields with common prefix suggest a cohesive class: {pattern.evidence.get('field_names', [])[:5]}",
            },
            "method_grouping": {
                "category": "class_structure",
                "title": f"Extract Service for '{pattern.evidence.get('prefix', '')}' Methods",
                "description": f"Methods with COBOL prefix form a functional unit",
            },
            "goto_usage": {
                "category": "control_flow",
                "title": "Implement Proper Control Flow",
                "description": "GO TO comments indicate unhandled control flow that needs implementation",
            },
            "bigdecimal_overuse": {
                "category": "types",
                "title": "Optimize Numeric Types",
                "description": "Some BigDecimal fields appear to be simple counters and could use int",
            },
            "parallel_arrays": {
                "category": "types",
                "title": "Convert Parallel Arrays to Object List",
                "description": f"Arrays of size {pattern.evidence.get('array_size')} should be List<T>",
            },
            "cobol_method_naming": {
                "category": "naming",
                "title": "Modernize Method Names",
                "description": "Methods have COBOL paragraph naming that should be converted to Java conventions",
            },
            "cobol_field_naming": {
                "category": "naming",
                "title": "Modernize Field Names",
                "description": "Fields have COBOL-style naming that should be converted to camelCase",
            },
            "inner_class_extraction": {
                "category": "class_structure",
                "title": "Extract Inner Classes to Separate Files",
                "description": "Inner data classes could be standalone DTOs/POJOs",
            },
            "high_complexity_method": {
                "category": "patterns",
                "title": f"Simplify Complex Method: {pattern.location.get('method', 'unknown')}",
                "description": f"Method complexity ({pattern.evidence.get('complexity')}) exceeds threshold",
            },
        }

        mapping = pattern_map.get(pattern.pattern_type)
        if not mapping:
            return None

        return AIRecommendation(
            recommendation_id=f"rec_{index:03d}",
            category=mapping["category"],
            title=mapping["title"],
            description=mapping["description"],
            priority=pattern.severity,
            confidence=pattern.confidence,
            affected_elements=self._extract_affected_elements(pattern),
            proposed_changes=[{
                "type": pattern.suggested_recipe,
                "details": pattern.evidence,
            }],
            rationale=pattern.details,
            risks=[],
            prerequisites=[],
        )

    def _extract_affected_elements(self, pattern: PatternMatch) -> List[str]:
        """Extract affected element names from pattern evidence."""
        elements = []

        evidence = pattern.evidence
        if 'field_names' in evidence:
            elements.extend(evidence['field_names'][:10])
        if 'method_names' in evidence:
            elements.extend(evidence['method_names'][:10])
        if 'class_names' in evidence:
            elements.extend(evidence['class_names'][:10])

        return elements
