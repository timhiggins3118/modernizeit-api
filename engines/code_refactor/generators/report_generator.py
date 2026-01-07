"""
Report Generator

Generates JSON and Markdown reports from refactor analysis results.
"""

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from engines.code_refactor.analyzers.rule_analyzer import RuleAnalysisResult, PatternMatch
from engines.code_refactor.analyzers.ai_analyzer import AIAnalysisResult, AIRecommendation


class ReportGenerator:
    """
    Generates refactoring reports in JSON and Markdown formats.

    Reports include:
    - Executive summary
    - Rule-based pattern findings
    - AI recommendations
    - Metrics and statistics
    - Actionable next steps
    """

    def __init__(self, output_dir: str):
        """
        Initialize report generator.

        Args:
            output_dir: Directory to write reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_full_report(
        self,
        rule_results: RuleAnalysisResult,
        ai_results: AIAnalysisResult,
        job_id: str,
    ) -> Dict[str, str]:
        """
        Generate complete refactoring report.

        Args:
            rule_results: Results from rule-based analysis
            ai_results: Results from AI analysis
            job_id: Job identifier

        Returns:
            Dict with paths to generated report files
        """
        timestamp = datetime.utcnow().isoformat()

        # Build combined report data
        report_data = {
            "job_id": job_id,
            "generated_at": timestamp,
            "java_file": rule_results.java_file,
            "class_name": rule_results.class_name,
            "summary": self._build_combined_summary(rule_results, ai_results),
            "metrics": rule_results.metrics,
            "rule_patterns": [self._pattern_to_dict(p) for p in rule_results.patterns],
            "ai_recommendations": [self._recommendation_to_dict(r) for r in ai_results.recommendations],
            "action_items": self._generate_action_items(rule_results, ai_results),
        }

        # Write JSON report
        json_path = self.output_dir / "refactor_report.json"
        with open(json_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        # Write Markdown report
        md_path = self.output_dir / "refactor_report.md"
        md_content = self._generate_markdown_report(report_data)
        with open(md_path, 'w') as f:
            f.write(md_content)

        # Write rule patterns separately (for detailed analysis)
        patterns_path = self.output_dir / "rule_patterns.json"
        with open(patterns_path, 'w') as f:
            json.dump({
                "job_id": job_id,
                "generated_at": timestamp,
                "patterns": [self._pattern_to_dict(p) for p in rule_results.patterns],
                "summary": rule_results.summary,
            }, f, indent=2)

        # Write AI analysis separately
        ai_path = self.output_dir / "ai_analysis.json"
        with open(ai_path, 'w') as f:
            json.dump({
                "job_id": job_id,
                "generated_at": timestamp,
                "recommendations": [self._recommendation_to_dict(r) for r in ai_results.recommendations],
                "summary": ai_results.summary,
                "raw_analysis": ai_results.raw_analysis,
            }, f, indent=2)

        return {
            "report_json": str(json_path),
            "report_md": str(md_path),
            "rule_patterns": str(patterns_path),
            "ai_analysis": str(ai_path),
        }

    def _pattern_to_dict(self, pattern: PatternMatch) -> Dict[str, Any]:
        """Convert PatternMatch to dictionary."""
        return {
            "pattern_type": pattern.pattern_type,
            "severity": pattern.severity,
            "confidence": pattern.confidence,
            "location": pattern.location,
            "details": pattern.details,
            "suggested_recipe": pattern.suggested_recipe,
            "evidence": pattern.evidence,
        }

    def _recommendation_to_dict(self, rec: AIRecommendation) -> Dict[str, Any]:
        """Convert AIRecommendation to dictionary."""
        return {
            "id": rec.recommendation_id,
            "category": rec.category,
            "title": rec.title,
            "description": rec.description,
            "priority": rec.priority,
            "confidence": rec.confidence,
            "affected_elements": rec.affected_elements,
            "proposed_changes": rec.proposed_changes,
            "rationale": rec.rationale,
            "risks": rec.risks,
            "prerequisites": rec.prerequisites,
        }

    def _build_combined_summary(
        self,
        rule_results: RuleAnalysisResult,
        ai_results: AIAnalysisResult
    ) -> Dict[str, Any]:
        """Build combined summary from both analyses."""
        # Determine overall recommendation
        high_severity_patterns = len([p for p in rule_results.patterns if p.severity == "high"])
        high_priority_recs = len([r for r in ai_results.recommendations if r.priority == "high"])

        if high_severity_patterns > 0 or high_priority_recs > 0:
            overall_recommendation = "REFACTORING_RECOMMENDED"
            urgency = "high"
        elif len(rule_results.patterns) > 5 or len(ai_results.recommendations) > 3:
            overall_recommendation = "REFACTORING_SUGGESTED"
            urgency = "medium"
        else:
            overall_recommendation = "MINOR_IMPROVEMENTS"
            urgency = "low"

        return {
            "overall_recommendation": overall_recommendation,
            "urgency": urgency,
            "total_patterns_detected": len(rule_results.patterns),
            "total_recommendations": len(ai_results.recommendations),
            "high_severity_issues": high_severity_patterns,
            "high_priority_recommendations": high_priority_recs,
            "metrics": {
                "total_lines": rule_results.metrics.get("total_lines", 0),
                "field_count": rule_results.metrics.get("field_count", 0),
                "method_count": rule_results.metrics.get("method_count", 0),
                "total_complexity": rule_results.metrics.get("total_complexity", 0),
            },
            "primary_issues": rule_results.summary.get("primary_issues", []),
            "top_recommendations": ai_results.summary.get("top_recommendations", []),
        }

    def _generate_action_items(
        self,
        rule_results: RuleAnalysisResult,
        ai_results: AIAnalysisResult
    ) -> List[Dict[str, Any]]:
        """Generate prioritized action items."""
        action_items = []

        # Add high-priority AI recommendations as action items
        for rec in ai_results.recommendations:
            if rec.priority == "high":
                action_items.append({
                    "priority": 1,
                    "action": rec.title,
                    "description": rec.description,
                    "type": "ai_recommendation",
                    "source_id": rec.recommendation_id,
                })

        # Add high-severity patterns as action items
        for pattern in rule_results.patterns:
            if pattern.severity == "high" and pattern.pattern_type not in [a.get("type") for a in action_items]:
                action_items.append({
                    "priority": 2,
                    "action": f"Address {pattern.pattern_type}",
                    "description": pattern.details,
                    "type": "rule_pattern",
                    "recipe": pattern.suggested_recipe,
                })

        # Add medium-priority items
        for rec in ai_results.recommendations:
            if rec.priority == "medium":
                action_items.append({
                    "priority": 3,
                    "action": rec.title,
                    "description": rec.description,
                    "type": "ai_recommendation",
                    "source_id": rec.recommendation_id,
                })

        # Sort by priority
        action_items.sort(key=lambda x: x["priority"])

        return action_items[:15]  # Top 15 action items

    def _generate_markdown_report(self, report_data: Dict[str, Any]) -> str:
        """Generate human-readable Markdown report."""
        lines = []

        # Header
        lines.append(f"# Code Refactor Report")
        lines.append(f"\n**Job ID:** {report_data['job_id']}")
        lines.append(f"\n**Generated:** {report_data['generated_at']}")
        lines.append(f"\n**File:** {report_data['java_file']}")
        lines.append(f"\n**Class:** {report_data['class_name']}")

        # Executive Summary
        summary = report_data['summary']
        lines.append(f"\n---\n\n## Executive Summary")
        lines.append(f"\n**Overall Recommendation:** {summary['overall_recommendation']}")
        lines.append(f"\n**Urgency:** {summary['urgency'].upper()}")

        lines.append(f"\n\n### Key Metrics")
        lines.append(f"\n| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total Lines | {summary['metrics']['total_lines']:,} |")
        lines.append(f"| Fields | {summary['metrics']['field_count']} |")
        lines.append(f"| Methods | {summary['metrics']['method_count']} |")
        lines.append(f"| Total Complexity | {summary['metrics']['total_complexity']} |")
        lines.append(f"| Patterns Detected | {summary['total_patterns_detected']} |")
        lines.append(f"| AI Recommendations | {summary['total_recommendations']} |")

        # High Priority Issues
        if summary['high_severity_issues'] > 0 or summary['high_priority_recommendations'] > 0:
            lines.append(f"\n\n### Critical Issues")
            lines.append(f"\n- **{summary['high_severity_issues']}** high-severity patterns detected")
            lines.append(f"- **{summary['high_priority_recommendations']}** high-priority recommendations")

        # Action Items
        lines.append(f"\n---\n\n## Recommended Actions")
        for i, action in enumerate(report_data['action_items'][:10], 1):
            priority_emoji = "🔴" if action['priority'] == 1 else "🟡" if action['priority'] <= 2 else "🟢"
            lines.append(f"\n### {i}. {action['action']} {priority_emoji}")
            lines.append(f"\n{action['description']}")
            if action.get('recipe'):
                lines.append(f"\n**Recipe:** `{action['recipe']}`")

        # Rule-Based Patterns
        lines.append(f"\n---\n\n## Detected Patterns")
        lines.append(f"\n| Pattern | Severity | Confidence | Details |")
        lines.append(f"|---------|----------|------------|---------|")
        for pattern in report_data['rule_patterns'][:15]:
            sev_emoji = "🔴" if pattern['severity'] == 'high' else "🟡" if pattern['severity'] == 'medium' else "🟢"
            lines.append(f"| {pattern['pattern_type']} | {sev_emoji} {pattern['severity']} | {pattern['confidence']:.0%} | {pattern['details'][:50]}... |")

        # AI Recommendations
        lines.append(f"\n---\n\n## AI Recommendations")
        for rec in report_data['ai_recommendations'][:10]:
            priority_emoji = "🔴" if rec['priority'] == 'high' else "🟡" if rec['priority'] == 'medium' else "🟢"
            lines.append(f"\n### {rec['title']} {priority_emoji}")
            lines.append(f"\n**Category:** {rec['category']} | **Confidence:** {rec['confidence']:.0%}")
            lines.append(f"\n{rec['description']}")
            if rec['rationale']:
                lines.append(f"\n**Rationale:** {rec['rationale']}")
            if rec['affected_elements']:
                lines.append(f"\n**Affected Elements:** {', '.join(rec['affected_elements'][:5])}")
            if rec['risks']:
                lines.append(f"\n**Risks:** {', '.join(rec['risks'])}")

        # Footer
        lines.append(f"\n---\n\n*Report generated by ModernizeIT Code Refactor Engine*")

        return '\n'.join(lines)

    def generate_recipe_file(
        self,
        rule_results: RuleAnalysisResult,
        ai_results: AIAnalysisResult,
        job_id: str,
    ) -> str:
        """
        Generate a structured recipe file similar to old refactor_recipes.json.

        This can be used as input for the transform phase.
        """
        recipes = []
        recipe_id = 1

        # Convert AI recommendations to recipes
        for rec in ai_results.recommendations:
            recipe = {
                "id": f"recipe_{recipe_id:03d}",
                "type": self._map_category_to_recipe_type(rec.category),
                "target": {
                    "file": rule_results.java_file,
                    "class": rule_results.class_name,
                    "elements": rec.affected_elements,
                },
                "sources": {
                    "ai": {
                        "confidence": rec.confidence,
                        "details": rec.description,
                    }
                },
                "proposed_change": {
                    "title": rec.title,
                    "changes": rec.proposed_changes,
                },
                "confidence": rec.confidence,
                "risk_level": self._map_priority_to_risk(rec.priority),
                "rationale": rec.rationale,
                "risks": rec.risks,
                "prerequisites": rec.prerequisites,
            }

            # Add rule source if there's a matching pattern
            matching_patterns = [
                p for p in rule_results.patterns
                if any(elem in p.details for elem in rec.affected_elements[:3])
            ]
            if matching_patterns:
                recipe["sources"]["rules"] = {
                    "confidence": matching_patterns[0].confidence,
                    "pattern_type": matching_patterns[0].pattern_type,
                }
                # Boost confidence if both agree
                recipe["confidence"] = min(0.98, recipe["confidence"] * 1.1)

            recipes.append(recipe)
            recipe_id += 1

        # Add rule patterns without AI recommendations
        covered_patterns = set()
        for rec in ai_results.recommendations:
            for elem in rec.affected_elements:
                covered_patterns.add(elem)

        for pattern in rule_results.patterns:
            pattern_elements = pattern.evidence.get('field_names', []) + pattern.evidence.get('method_names', [])
            if not any(elem in covered_patterns for elem in pattern_elements):
                recipe = {
                    "id": f"recipe_{recipe_id:03d}",
                    "type": pattern.suggested_recipe,
                    "target": {
                        "file": rule_results.java_file,
                        "class": rule_results.class_name,
                        "elements": pattern_elements[:10],
                    },
                    "sources": {
                        "rules": {
                            "confidence": pattern.confidence,
                            "pattern_type": pattern.pattern_type,
                        }
                    },
                    "proposed_change": {
                        "title": f"Apply {pattern.suggested_recipe}",
                        "details": pattern.details,
                    },
                    "confidence": pattern.confidence,
                    "risk_level": pattern.severity,
                    "rationale": pattern.details,
                }
                recipes.append(recipe)
                recipe_id += 1

        # Build summary
        high_confidence = len([r for r in recipes if r['confidence'] >= 0.90])
        medium_confidence = len([r for r in recipes if 0.75 <= r['confidence'] < 0.90])
        low_confidence = len([r for r in recipes if r['confidence'] < 0.75])

        recipe_types: Dict[str, int] = {}
        for r in recipes:
            t = r['type']
            recipe_types[t] = recipe_types.get(t, 0) + 1

        output = {
            "job_id": job_id,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_recipes": len(recipes),
                "high_confidence": high_confidence,
                "medium_confidence": medium_confidence,
                "low_confidence": low_confidence,
                "recipe_type_breakdown": recipe_types,
            },
            "recipes": recipes,
        }

        # Write to file
        recipes_path = self.output_dir / "refactor_recipes.json"
        with open(recipes_path, 'w') as f:
            json.dump(output, f, indent=2)

        return str(recipes_path)

    def _map_category_to_recipe_type(self, category: str) -> str:
        """Map AI category to recipe type."""
        mapping = {
            "class_structure": "extract_class",
            "naming": "rename_elements",
            "types": "optimize_types",
            "control_flow": "implement_control_flow",
            "patterns": "apply_pattern",
            "general": "modernize",
        }
        return mapping.get(category, "modernize")

    def _map_priority_to_risk(self, priority: str) -> str:
        """Map priority to risk level (inverse relationship)."""
        mapping = {
            "high": "low",  # High priority = low risk (well understood)
            "medium": "medium",
            "low": "high",  # Low priority often means higher risk/less certain
        }
        return mapping.get(priority, "medium")
