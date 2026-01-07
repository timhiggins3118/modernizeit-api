"""
API Recommender for Architecture Recommender

Recommends API Gateway configuration based on evidence:
- REST API: Standard @RestController endpoints
- HTTP API: Simpler, lower cost for basic REST
- WebSocket: Real-time bidirectional communication
- None: Batch-only applications

Decision based on:
- Java annotations (@RestController, @EnableWebSocket)
- Security annotations (@PreAuthorize, @Secured)
- Entry points and endpoint count
- Discovery patterns
"""

from typing import Any, Dict, List, Optional

from api.models.architecture import (
    APIRecommendation,
    AlternativeRecommendation,
    TradeOffs,
    Evidence,
)
from engines.architecture.analyzers.source_consolidator import ConsolidatedSources


class APIRecommender:
    """Recommends API Gateway configuration based on evidence."""

    def __init__(self, sources: ConsolidatedSources):
        """
        Initialize recommender.

        Args:
            sources: Consolidated source data
        """
        self.sources = sources
        self.evidence: List[Evidence] = []

    def recommend(self) -> APIRecommendation:
        """
        Generate API recommendation.

        Returns:
            APIRecommendation with evidence
        """
        java = self.sources.java_analysis

        # Analyze Java for API patterns
        has_rest = False
        has_websocket = False
        has_auth = False
        endpoint_count = 0
        endpoints = []

        if java:
            # Check entry points
            for entry in java.entry_points:
                if entry.entry_type == "REST":
                    has_rest = True
                    endpoint_count += entry.endpoint_count or 0
                    endpoints.append({
                        "controller": entry.class_name,
                        "endpoints": entry.endpoint_count or 0
                    })

            if has_rest:
                self.evidence.append(Evidence(
                    source="java",
                    finding=f"{java.class_breakdown.controllers} REST controllers with {endpoint_count} endpoints"
                ))

            # Check for WebSocket
            for ann in java.annotations_found:
                if 'WebSocket' in ann.annotation:
                    has_websocket = True
                    self.evidence.append(Evidence(
                        source="java",
                        finding="WebSocket support enabled"
                    ))
                if ann.annotation in ['@PreAuthorize', '@Secured']:
                    has_auth = True
                    self.evidence.append(Evidence(
                        source="java",
                        finding=f"Security annotation {ann.annotation} detected"
                    ))

            # Check security dependencies
            security_deps = java.dependencies.get('security', [])
            if security_deps:
                has_auth = True
                self.evidence.append(Evidence(
                    source="java",
                    finding="Spring Security dependencies detected"
                ))

        # Check Discovery for patterns
        discovery = self.sources.discovery
        if discovery.has_data:
            pattern = discovery.primary_pattern.lower()
            if 'real' in pattern or 'online' in pattern or 'transaction' in pattern:
                self.evidence.append(Evidence(
                    source="discovery",
                    finding=f"Real-time pattern detected: {discovery.primary_pattern}"
                ))
            if discovery.has_cics:
                self.evidence.append(Evidence(
                    source="discovery",
                    finding="CICS transaction manager detected"
                ))

        # Decision
        return self._decide_api(
            has_rest=has_rest,
            has_websocket=has_websocket,
            has_auth=has_auth,
            endpoint_count=endpoint_count,
            endpoints=endpoints
        )

    def _decide_api(
        self,
        has_rest: bool,
        has_websocket: bool,
        has_auth: bool,
        endpoint_count: int,
        endpoints: List[Dict[str, Any]]
    ) -> APIRecommendation:
        """
        Apply decision tree for API selection.

        Decision tree:
        1. No @RestController? -> No API needed
        2. Has WebSocket? -> API Gateway WebSocket
        3. Has Auth? -> REST API with Cognito/IAM
        4. Simple API (< 5 endpoints)? -> HTTP API (lower cost)
        5. Otherwise -> REST API
        """
        # No REST controllers
        if not has_rest:
            self.evidence.append(Evidence(
                source="decision",
                finding="No REST controllers detected - API Gateway not required"
            ))
            return APIRecommendation(
                required=False,
                api_type=None,
                auth_type=None,
                endpoints=[],
                confidence=0.88,
                evidence=self.evidence,
                alternative=None
            )

        # WebSocket needed
        if has_websocket:
            self.evidence.append(Evidence(
                source="decision",
                finding="WebSocket detected - API Gateway WebSocket API recommended"
            ))
            return APIRecommendation(
                required=True,
                api_type="WebSocket",
                auth_type="COGNITO" if has_auth else "NONE",
                endpoints=endpoints,
                confidence=0.90,
                evidence=self.evidence,
                alternative=AlternativeRecommendation(
                    service="Application Load Balancer",
                    reason="Consider if: need sticky sessions or complex routing",
                    trade_offs=TradeOffs(
                        pros=["Sticky sessions", "Complex routing rules"],
                        cons=["Higher cost", "More configuration"]
                    )
                )
            )

        # Auth required - use REST API (more features)
        if has_auth:
            self.evidence.append(Evidence(
                source="decision",
                finding="Authentication required - REST API with Cognito/IAM"
            ))
            return APIRecommendation(
                required=True,
                api_type="REST",
                auth_type="COGNITO",
                endpoints=endpoints,
                confidence=0.92,
                evidence=self.evidence,
                alternative=AlternativeRecommendation(
                    service="HTTP API + Lambda Authorizer",
                    reason="Consider if: lower cost needed, custom auth logic",
                    trade_offs=TradeOffs(
                        pros=["Lower cost", "Custom auth logic"],
                        cons=["More code to write", "Less built-in features"]
                    )
                )
            )

        # Simple API - use HTTP API for cost savings
        if endpoint_count <= 5:
            self.evidence.append(Evidence(
                source="decision",
                finding=f"Simple API ({endpoint_count} endpoints) - HTTP API recommended for cost"
            ))
            return APIRecommendation(
                required=True,
                api_type="HTTP",
                auth_type="API_KEY",
                endpoints=endpoints,
                confidence=0.88,
                evidence=self.evidence,
                alternative=AlternativeRecommendation(
                    service="REST API",
                    reason="Consider if: need API keys, usage plans, or request validation",
                    trade_offs=TradeOffs(
                        pros=["Usage plans", "API keys", "Request validation"],
                        cons=["Higher cost (~70% more)"]
                    )
                )
            )

        # Standard REST API
        self.evidence.append(Evidence(
            source="decision",
            finding=f"Standard REST API ({endpoint_count} endpoints)"
        ))
        return APIRecommendation(
            required=True,
            api_type="REST",
            auth_type="API_KEY",
            endpoints=endpoints,
            confidence=0.90,
            evidence=self.evidence,
            alternative=AlternativeRecommendation(
                service="HTTP API",
                reason="Consider if: cost optimization is priority and features not needed",
                trade_offs=TradeOffs(
                    pros=["~70% lower cost", "Faster"],
                    cons=["No usage plans", "No request validation", "No API keys"]
                )
            )
        )


def recommend_api(sources: ConsolidatedSources) -> APIRecommendation:
    """
    Convenience function to get API recommendation.

    Args:
        sources: Consolidated source data

    Returns:
        APIRecommendation
    """
    recommender = APIRecommender(sources)
    return recommender.recommend()
