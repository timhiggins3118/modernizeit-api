"""
Compute Recommender for Architecture Recommender

Recommends AWS compute service based on evidence:
- AWS Lambda: Serverless, event-driven, REST APIs
- Amazon ECS/Fargate: Containers, long-running, complex apps
- AWS Batch: Batch processing, long-running jobs
- Step Functions: Orchestration, workflows

Decision based on:
- Java annotations (@RestController, @Scheduled, etc.)
- Entry points detected
- Discovery patterns (real-time vs batch)
- Code complexity
"""

from typing import Any, Dict, List, Optional

from api.models.architecture import (
    ComputeRecommendation,
    ComputeService,
    LambdaFunction,
    AlternativeRecommendation,
    TradeOffs,
    Evidence,
)
from engines.architecture.analyzers.source_consolidator import ConsolidatedSources


class ComputeRecommender:
    """Recommends AWS compute service based on evidence."""

    def __init__(self, sources: ConsolidatedSources):
        """
        Initialize recommender.

        Args:
            sources: Consolidated source data
        """
        self.sources = sources
        self.evidence: List[Evidence] = []

    def recommend(self) -> ComputeRecommendation:
        """
        Generate compute recommendation.

        Returns:
            ComputeRecommendation with evidence and alternative
        """
        # Analyze Java code
        java = self.sources.java_analysis
        has_rest = False
        rest_endpoint_count = 0
        has_scheduled = False
        scheduled_count = 0
        has_listeners = False

        if java:
            for entry in java.entry_points:
                if entry.entry_type == "REST":
                    has_rest = True
                    rest_endpoint_count += entry.endpoint_count or 0
                elif entry.entry_type == "SCHEDULED":
                    has_scheduled = True
                    scheduled_count += 1
                elif entry.entry_type in ["SQS_LISTENER", "KAFKA_LISTENER"]:
                    has_listeners = True

            if has_rest:
                self.evidence.append(Evidence(
                    source="java",
                    finding=f"{java.class_breakdown.controllers} @RestController classes with {rest_endpoint_count} endpoints"
                ))
            if has_scheduled:
                self.evidence.append(Evidence(
                    source="java",
                    finding=f"{scheduled_count} @Scheduled methods for batch processing"
                ))
            if has_listeners:
                self.evidence.append(Evidence(
                    source="java",
                    finding="Message listeners detected (SQS/Kafka)"
                ))

        # Analyze Discovery patterns
        discovery = self.sources.discovery
        if discovery.has_data:
            pattern = discovery.primary_pattern
            if pattern and pattern != "unknown":
                self.evidence.append(Evidence(
                    source="discovery",
                    finding=f"Primary pattern: {pattern}"
                ))
            if discovery.batch_processes > 0 and discovery.real_time_processes > 0:
                self.evidence.append(Evidence(
                    source="discovery",
                    finding="Mixed real-time and batch workload"
                ))

        # Decision tree
        return self._decide_compute(
            has_rest=has_rest,
            rest_endpoint_count=rest_endpoint_count,
            has_scheduled=has_scheduled,
            scheduled_count=scheduled_count,
            has_listeners=has_listeners
        )

    def _decide_compute(
        self,
        has_rest: bool,
        rest_endpoint_count: int,
        has_scheduled: bool,
        scheduled_count: int,
        has_listeners: bool
    ) -> ComputeRecommendation:
        """
        Apply decision tree for compute selection.

        Decision tree:
        1. Has @RestController?
           - >20 endpoints: ECS/Fargate (microservice)
           - >5 endpoints: Lambda (consider ECS)
           - <=5 endpoints: Lambda
        2. Has @Scheduled?
           - Duration >15 min: Step Functions + AWS Batch
           - Duration <=15 min: Lambda + CloudWatch Events
        3. Has listeners?
           - Lambda + SQS/MSK trigger
        4. Plain batch:
           - Step Functions + Lambda
        """
        functions = self._build_lambda_functions()

        # Large API = ECS/Fargate
        if has_rest and rest_endpoint_count > 20:
            self.evidence.append(Evidence(
                source="decision",
                finding=f"Large API ({rest_endpoint_count} endpoints) favors container deployment"
            ))
            return ComputeRecommendation(
                service=ComputeService.ECS_FARGATE,
                runtime="java17",
                functions=[],  # Not Lambda functions
                confidence=0.85,
                evidence=self.evidence,
                alternative=AlternativeRecommendation(
                    service="AWS Lambda",
                    reason="Consider if: low traffic, cost optimization, or prefer serverless",
                    trade_offs=TradeOffs(
                        pros=["Lower cost at low volume", "No server management", "Auto-scaling"],
                        cons=["Cold starts", "15-min timeout", "Split into multiple functions"]
                    )
                )
            )

        # Medium API or any REST = Lambda
        if has_rest:
            self.evidence.append(Evidence(
                source="decision",
                finding="REST API detected - API Gateway + Lambda recommended"
            ))

            # Check if also has scheduled tasks
            if has_scheduled:
                self.evidence.append(Evidence(
                    source="decision",
                    finding="Hybrid workload: REST API + scheduled tasks"
                ))

            return ComputeRecommendation(
                service=ComputeService.LAMBDA,
                runtime="java17",
                functions=functions,
                confidence=0.92,
                evidence=self.evidence,
                alternative=AlternativeRecommendation(
                    service="Amazon ECS/Fargate",
                    reason="Consider if: high sustained traffic, need WebSocket, or prefer container-based deployment",
                    trade_offs=TradeOffs(
                        pros=["No cold starts", "WebSocket support", "Easier local dev"],
                        cons=["Higher base cost", "More operational overhead"]
                    )
                )
            )

        # Only scheduled tasks
        if has_scheduled:
            self.evidence.append(Evidence(
                source="decision",
                finding="Batch-only workload - Lambda + CloudWatch Events"
            ))
            return ComputeRecommendation(
                service=ComputeService.LAMBDA,
                runtime="java17",
                functions=functions,
                confidence=0.88,
                evidence=self.evidence,
                alternative=AlternativeRecommendation(
                    service="AWS Batch",
                    reason="Consider if: jobs run >15 minutes or need more compute resources",
                    trade_offs=TradeOffs(
                        pros=["No timeout limit", "More memory/CPU options", "Spot instances"],
                        cons=["Slower startup", "More complex setup"]
                    )
                )
            )

        # Message listeners
        if has_listeners:
            self.evidence.append(Evidence(
                source="decision",
                finding="Event-driven workload - Lambda with message triggers"
            ))
            return ComputeRecommendation(
                service=ComputeService.LAMBDA,
                runtime="java17",
                functions=functions,
                confidence=0.90,
                evidence=self.evidence,
                alternative=AlternativeRecommendation(
                    service="Amazon ECS/Fargate",
                    reason="Consider if: high message volume or complex processing logic",
                    trade_offs=TradeOffs(
                        pros=["Persistent connections", "No cold starts", "Complex state"],
                        cons=["Higher cost", "Manual scaling"]
                    )
                )
            )

        # Default: Step Functions + Lambda for orchestration
        self.evidence.append(Evidence(
            source="decision",
            finding="No specific pattern detected - Step Functions for orchestration"
        ))
        return ComputeRecommendation(
            service=ComputeService.LAMBDA,
            runtime="java17",
            functions=functions,
            confidence=0.75,
            evidence=self.evidence,
            alternative=AlternativeRecommendation(
                service="Amazon ECS/Fargate",
                reason="Consider if: application requires long-running processes or complex state",
                trade_offs=TradeOffs(
                    pros=["Simpler deployment model", "Full control"],
                    cons=["Higher cost", "More operational work"]
                )
            )
        )

    def _build_lambda_functions(self) -> List[LambdaFunction]:
        """Build list of Lambda functions from entry points."""
        functions = []
        java = self.sources.java_analysis

        if not java:
            return functions

        for entry in java.entry_points:
            if entry.entry_type == "REST":
                functions.append(LambdaFunction(
                    name=self._to_function_name(entry.class_name),
                    source_class=entry.class_name,
                    memory_mb=1024,
                    timeout_seconds=30,
                    trigger="API Gateway"
                ))
            elif entry.entry_type == "SCHEDULED":
                # Scheduled tasks might need more time
                cron = entry.cron_expression or "rate(1 day)"
                functions.append(LambdaFunction(
                    name=self._to_function_name(entry.class_name),
                    source_class=entry.class_name,
                    memory_mb=2048,
                    timeout_seconds=900,  # 15 min max
                    trigger=f"CloudWatch Events ({cron})"
                ))
            elif entry.entry_type == "SQS_LISTENER":
                functions.append(LambdaFunction(
                    name=self._to_function_name(entry.class_name),
                    source_class=entry.class_name,
                    memory_mb=1024,
                    timeout_seconds=300,
                    trigger="SQS"
                ))
            elif entry.entry_type == "KAFKA_LISTENER":
                functions.append(LambdaFunction(
                    name=self._to_function_name(entry.class_name),
                    source_class=entry.class_name,
                    memory_mb=1024,
                    timeout_seconds=300,
                    trigger="MSK"
                ))

        return functions

    def _to_function_name(self, class_name: str) -> str:
        """Convert Java class name to Lambda function name."""
        # CustomerController -> customer-service
        # BatchProcessor -> batch-processor
        import re

        # Remove common suffixes
        name = class_name
        for suffix in ['Controller', 'Service', 'Handler', 'Processor']:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break

        # CamelCase to kebab-case
        name = re.sub(r'(?<!^)(?=[A-Z])', '-', name).lower()

        # Add suffix
        if 'controller' in class_name.lower():
            name = f"{name}-service"
        elif 'batch' in class_name.lower() or 'job' in class_name.lower():
            name = f"{name}-processor"
        else:
            name = f"{name}-function"

        return name


def recommend_compute(sources: ConsolidatedSources) -> ComputeRecommendation:
    """
    Convenience function to get compute recommendation.

    Args:
        sources: Consolidated source data

    Returns:
        ComputeRecommendation
    """
    recommender = ComputeRecommender(sources)
    return recommender.recommend()
