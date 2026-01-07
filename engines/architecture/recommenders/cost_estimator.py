"""
Cost Estimator for Architecture Recommender

Evidence-based cost estimation using:
- Actual code metrics (endpoint count, entity count)
- Discovery transaction volumes
- AWS pricing (us-east-1 as baseline)

All estimates include the evidence they're based on.
"""

from typing import Any, Dict, List, Optional

from api.models.architecture import (
    CostEstimate,
    CostCalculation,
    ComputeRecommendation,
    DatabaseRecommendation,
    APIRecommendation,
    ComputeService,
    DatabaseService,
)
from engines.architecture.analyzers.source_consolidator import ConsolidatedSources


# AWS Pricing (us-east-1, as of 2024)
# These are approximate and should be updated periodically

LAMBDA_PRICING = {
    'request_per_million': 0.20,
    'gb_second': 0.0000166667,
    'free_tier_requests': 1000000,
    'free_tier_gb_seconds': 400000,
}

AURORA_PRICING = {
    'db.t4g.medium': {
        'hourly': 0.073,
        'storage_gb': 0.10,
    },
    'db.r6g.medium': {
        'hourly': 0.145,
        'storage_gb': 0.10,
    },
    'db.r6g.large': {
        'hourly': 0.29,
        'storage_gb': 0.10,
    },
}

API_GATEWAY_PRICING = {
    'rest': {
        'per_million': 3.50,
    },
    'http': {
        'per_million': 1.00,
    },
    'websocket': {
        'per_million': 1.00,
        'per_million_minutes': 0.25,
    },
}

S3_PRICING = {
    'storage_gb': 0.023,
    'put_per_1000': 0.005,
    'get_per_1000': 0.0004,
}

DYNAMODB_PRICING = {
    'read_per_million': 0.25,
    'write_per_million': 1.25,
    'storage_gb': 0.25,
}


class CostEstimator:
    """Estimates AWS costs based on architecture recommendations."""

    def __init__(
        self,
        sources: ConsolidatedSources,
        compute: ComputeRecommendation,
        database: DatabaseRecommendation,
        api: APIRecommendation
    ):
        """
        Initialize estimator.

        Args:
            sources: Consolidated source data
            compute: Compute recommendation
            database: Database recommendation
            api: API recommendation
        """
        self.sources = sources
        self.compute = compute
        self.database = database
        self.api = api
        self.notes: List[str] = []

    def estimate(self) -> CostEstimate:
        """
        Generate cost estimate.

        Returns:
            CostEstimate with breakdown
        """
        # Estimate each component
        compute_cost = self._estimate_compute()
        database_cost = self._estimate_database()
        api_cost = self._estimate_api()
        storage_cost = self._estimate_storage()

        # Calculate totals
        total_monthly = compute_cost.monthly_cost
        if database_cost:
            total_monthly += database_cost.monthly_cost
        if api_cost:
            total_monthly += api_cost.monthly_cost
        if storage_cost:
            total_monthly += storage_cost.monthly_cost

        total_annual = total_monthly * 12

        # Calculate savings vs mainframe (if we have Discovery ROI data)
        savings_percent = None
        discovery = self.sources.discovery
        if discovery.has_data and discovery.roi_analysis:
            infra = discovery.roi_analysis.get('infrastructure_savings_analysis', {})
            legacy_cost = infra.get('annual_legacy_cost', 0)
            if legacy_cost > 0:
                savings_percent = ((legacy_cost - total_annual) / legacy_cost) * 100
                self.notes.append(f"Compared to mainframe cost of ${legacy_cost:,.0f}/year")

        # Determine confidence based on data quality
        confidence = 0.75
        if self.sources.java_analysis and self.sources.java_analysis.files_analyzed > 0:
            confidence += 0.10
        if discovery.has_data:
            confidence += 0.05
        confidence = min(0.95, confidence)

        return CostEstimate(
            compute_cost=compute_cost,
            database_cost=database_cost,
            storage_cost=storage_cost,
            api_cost=api_cost,
            other_costs=[],
            total_monthly=total_monthly,
            total_annual=total_annual,
            vs_mainframe_savings_percent=savings_percent,
            confidence=confidence,
            notes=self.notes
        )

    def _estimate_compute(self) -> CostCalculation:
        """Estimate compute costs."""
        if self.compute.service == ComputeService.LAMBDA:
            return self._estimate_lambda()
        elif self.compute.service == ComputeService.ECS_FARGATE:
            return self._estimate_fargate()
        else:
            return self._estimate_lambda()  # Default

    def _estimate_lambda(self) -> CostCalculation:
        """Estimate Lambda costs."""
        # Get metrics
        java = self.sources.java_analysis
        discovery = self.sources.discovery

        # Estimate invocations
        endpoint_count = 0
        scheduled_count = 0

        if java:
            for entry in java.entry_points:
                if entry.entry_type == "REST":
                    endpoint_count += entry.endpoint_count or 0
                elif entry.entry_type == "SCHEDULED":
                    scheduled_count += 1

        # Base estimate: 100 invocations per endpoint per day
        # This is conservative; real applications vary widely
        invocations_per_month = endpoint_count * 100 * 30

        # Add scheduled invocations
        invocations_per_month += scheduled_count * 30  # Once per day

        # Adjust based on Discovery if available
        if discovery.has_data and discovery.real_time_processes > 0:
            # Scale up for high-value processes
            invocations_per_month *= (1 + discovery.high_value_processes * 0.5)

        # Minimum of 10,000 for any application
        invocations_per_month = max(10000, int(invocations_per_month))

        # Calculate cost
        # Assume average 200ms duration, 1GB memory
        avg_duration_ms = 200
        memory_gb = 1.0

        gb_seconds = (invocations_per_month * avg_duration_ms / 1000) * memory_gb

        # Apply pricing (excluding free tier for simplicity)
        request_cost = invocations_per_month * LAMBDA_PRICING['request_per_million'] / 1000000
        compute_cost = gb_seconds * LAMBDA_PRICING['gb_second']
        monthly_cost = request_cost + compute_cost

        evidence = f"Based on {endpoint_count} REST endpoints + {scheduled_count} scheduled tasks"

        return CostCalculation(
            service="AWS Lambda",
            monthly_cost=round(monthly_cost, 2),
            calculation={
                "functions": len(self.compute.functions),
                "invocations_per_month": invocations_per_month,
                "avg_duration_ms": avg_duration_ms,
                "avg_memory_mb": int(memory_gb * 1024),
            },
            evidence=evidence
        )

    def _estimate_fargate(self) -> CostCalculation:
        """Estimate ECS/Fargate costs."""
        # Estimate based on always-on container
        # 1 vCPU, 2 GB memory
        vcpu_hours = 24 * 30  # Hours per month
        gb_hours = 2 * 24 * 30

        # Fargate pricing
        vcpu_cost = vcpu_hours * 0.04048
        memory_cost = gb_hours * 0.004445

        monthly_cost = vcpu_cost + memory_cost

        return CostCalculation(
            service="Amazon ECS/Fargate",
            monthly_cost=round(monthly_cost, 2),
            calculation={
                "vcpu": 1,
                "memory_gb": 2,
                "hours_per_month": 24 * 30,
            },
            evidence="Based on 1 vCPU, 2 GB container running 24/7"
        )

    def _estimate_database(self) -> Optional[CostCalculation]:
        """Estimate database costs."""
        if self.database.service == DatabaseService.NONE:
            return None

        if self.database.service in [DatabaseService.AURORA_POSTGRESQL, DatabaseService.AURORA_MYSQL]:
            return self._estimate_aurora()
        elif self.database.service == DatabaseService.DYNAMODB:
            return self._estimate_dynamodb()
        else:
            return self._estimate_aurora()

    def _estimate_aurora(self) -> CostCalculation:
        """Estimate Aurora costs."""
        instance_class = self.database.instance_class or "db.t4g.medium"
        storage_gb = self.database.storage_gb or 50

        pricing = AURORA_PRICING.get(instance_class, AURORA_PRICING['db.t4g.medium'])

        instance_cost = pricing['hourly'] * 24 * 30
        storage_cost = storage_gb * pricing['storage_gb']

        # Multi-AZ doubles instance cost
        if self.database.multi_az:
            instance_cost *= 2

        monthly_cost = instance_cost + storage_cost

        # Get entity count for evidence
        entity_count = 0
        java = self.sources.java_analysis
        if java:
            entity_count = java.class_breakdown.entities

        data_analysis = self.sources.data_analysis
        if data_analysis.has_data:
            entity_count = max(entity_count, data_analysis.entity_count)

        return CostCalculation(
            service=self.database.service.value,
            monthly_cost=round(monthly_cost, 2),
            calculation={
                "instance": instance_class,
                "storage_gb": storage_gb,
                "multi_az": self.database.multi_az,
            },
            evidence=f"Based on {entity_count} @Entity classes + ERD entities"
        )

    def _estimate_dynamodb(self) -> CostCalculation:
        """Estimate DynamoDB costs."""
        # On-demand pricing estimate
        # Assume 100K reads and 50K writes per month per table
        java = self.sources.java_analysis
        table_count = 1  # Default

        if java:
            # Use entity count as proxy for tables
            table_count = max(1, java.class_breakdown.entities)

        reads_per_month = 100000 * table_count
        writes_per_month = 50000 * table_count
        storage_gb = 1 * table_count

        read_cost = reads_per_month * DYNAMODB_PRICING['read_per_million'] / 1000000
        write_cost = writes_per_month * DYNAMODB_PRICING['write_per_million'] / 1000000
        storage_cost = storage_gb * DYNAMODB_PRICING['storage_gb']

        monthly_cost = read_cost + write_cost + storage_cost

        return CostCalculation(
            service="DynamoDB",
            monthly_cost=round(monthly_cost, 2),
            calculation={
                "tables": table_count,
                "reads_per_month": reads_per_month,
                "writes_per_month": writes_per_month,
                "storage_gb": storage_gb,
            },
            evidence=f"Based on {table_count} tables with on-demand pricing"
        )

    def _estimate_api(self) -> Optional[CostCalculation]:
        """Estimate API Gateway costs."""
        if not self.api.required:
            return None

        api_type = self.api.api_type or "REST"

        # Estimate requests from compute estimation
        java = self.sources.java_analysis
        endpoint_count = 0
        if java:
            for entry in java.entry_points:
                if entry.entry_type == "REST":
                    endpoint_count += entry.endpoint_count or 0

        requests_per_month = max(10000, endpoint_count * 100 * 30)

        if api_type == "REST":
            pricing = API_GATEWAY_PRICING['rest']
            monthly_cost = requests_per_month * pricing['per_million'] / 1000000
        elif api_type == "HTTP":
            pricing = API_GATEWAY_PRICING['http']
            monthly_cost = requests_per_month * pricing['per_million'] / 1000000
        else:  # WebSocket
            pricing = API_GATEWAY_PRICING['websocket']
            # Assume 1 minute average connection time
            monthly_cost = requests_per_month * pricing['per_million'] / 1000000
            monthly_cost += requests_per_month * pricing['per_million_minutes'] / 1000000

        return CostCalculation(
            service=f"API Gateway ({api_type})",
            monthly_cost=round(monthly_cost, 2),
            calculation={
                "api_type": api_type,
                "requests_per_month": requests_per_month,
            },
            evidence=f"Based on {endpoint_count} endpoints, ~{requests_per_month:,} requests/month"
        )

    def _estimate_storage(self) -> Optional[CostCalculation]:
        """Estimate S3 storage costs."""
        discovery = self.sources.discovery

        # Only if VSAM detected
        if not (discovery.has_data and discovery.has_vsam):
            return None

        # Estimate storage based on code size
        code_analysis = self.sources.code_analysis
        if code_analysis.has_data:
            # Rough estimate: 10 MB per 1000 LOC of data
            storage_gb = max(1, code_analysis.total_loc / 1000 * 10 / 1024)
        else:
            storage_gb = 10  # Default

        storage_cost = storage_gb * S3_PRICING['storage_gb']
        # Estimate 10K puts and 100K gets per month
        request_cost = 10 * S3_PRICING['put_per_1000'] + 100 * S3_PRICING['get_per_1000']

        monthly_cost = storage_cost + request_cost

        return CostCalculation(
            service="Amazon S3",
            monthly_cost=round(monthly_cost, 2),
            calculation={
                "storage_gb": round(storage_gb, 1),
                "puts_per_month": 10000,
                "gets_per_month": 100000,
            },
            evidence="Based on VSAM file migration from Discovery"
        )


def estimate_costs(
    sources: ConsolidatedSources,
    compute: ComputeRecommendation,
    database: DatabaseRecommendation,
    api: APIRecommendation
) -> CostEstimate:
    """
    Convenience function to estimate costs.

    Args:
        sources: Consolidated source data
        compute: Compute recommendation
        database: Database recommendation
        api: API recommendation

    Returns:
        CostEstimate
    """
    estimator = CostEstimator(sources, compute, database, api)
    return estimator.estimate()
