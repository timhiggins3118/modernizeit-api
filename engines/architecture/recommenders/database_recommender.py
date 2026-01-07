"""
Database Recommender for Architecture Recommender

Recommends AWS database service based on evidence:
- Aurora PostgreSQL: JPA/Hibernate, complex queries, transactions
- Aurora MySQL: MySQL driver, existing MySQL expertise
- DynamoDB: Simple key-value, high scale, no relationships
- None: No database dependencies detected

CRITICAL: Only recommends database if evidence exists in Java code.
This prevents recommending unused infrastructure.

Decision based on:
- Java dependencies (postgresql, mysql, dynamodb)
- JPA/Hibernate annotations (@Entity, @Repository)
- Entity count from Data Analysis
- COBOL DB2 patterns from Discovery
"""

from typing import Any, Dict, List, Optional

from api.models.architecture import (
    DatabaseRecommendation,
    DatabaseService,
    AlternativeRecommendation,
    TradeOffs,
    Evidence,
    S3Bucket,
)
from engines.architecture.analyzers.source_consolidator import ConsolidatedSources


class DatabaseRecommender:
    """Recommends AWS database service based on evidence."""

    def __init__(self, sources: ConsolidatedSources):
        """
        Initialize recommender.

        Args:
            sources: Consolidated source data
        """
        self.sources = sources
        self.evidence: List[Evidence] = []

    def recommend(self) -> DatabaseRecommendation:
        """
        Generate database recommendation.

        Returns:
            DatabaseRecommendation with evidence (or None if no DB needed)
        """
        # Check Java dependencies
        java = self.sources.java_analysis
        has_postgresql = False
        has_mysql = False
        has_dynamodb = False
        has_jpa = False
        entity_count = 0
        repository_count = 0

        if java:
            db_deps = java.dependencies.get('database', [])
            for dep in db_deps:
                artifact = dep.artifact_id.lower()
                if 'postgresql' in artifact:
                    has_postgresql = True
                    self.evidence.append(Evidence(
                        source="java",
                        finding=f"PostgreSQL driver: {dep.artifact_id}:{dep.version or 'latest'}"
                    ))
                elif 'mysql' in artifact:
                    has_mysql = True
                    self.evidence.append(Evidence(
                        source="java",
                        finding=f"MySQL driver: {dep.artifact_id}:{dep.version or 'latest'}"
                    ))
                elif 'dynamodb' in artifact:
                    has_dynamodb = True
                    self.evidence.append(Evidence(
                        source="java",
                        finding=f"DynamoDB SDK: {dep.artifact_id}"
                    ))
                elif 'jpa' in artifact or 'hibernate' in artifact:
                    has_jpa = True
                    self.evidence.append(Evidence(
                        source="java",
                        finding=f"JPA/Hibernate: {dep.artifact_id}"
                    ))

            # Count entities and repositories
            entity_count = java.class_breakdown.entities
            repository_count = java.class_breakdown.repositories

            if entity_count > 0:
                self.evidence.append(Evidence(
                    source="java",
                    finding=f"{entity_count} @Entity classes detected"
                ))
            if repository_count > 0:
                self.evidence.append(Evidence(
                    source="java",
                    finding=f"{repository_count} @Repository interfaces"
                ))

        # Check Data Analysis for entity count
        data_analysis = self.sources.data_analysis
        if data_analysis.has_data and data_analysis.entity_count > 0:
            self.evidence.append(Evidence(
                source="data_analysis",
                finding=f"{data_analysis.entity_count} entities with {data_analysis.relationship_count} relationships in ERD"
            ))

        # Check Discovery for DB2
        discovery = self.sources.discovery
        if discovery.has_data and discovery.has_db2:
            self.evidence.append(Evidence(
                source="discovery",
                finding="DB2 integration detected in COBOL source"
            ))

        # Decision logic
        return self._decide_database(
            has_postgresql=has_postgresql,
            has_mysql=has_mysql,
            has_dynamodb=has_dynamodb,
            has_jpa=has_jpa,
            entity_count=entity_count,
            repository_count=repository_count,
            erd_entity_count=data_analysis.entity_count if data_analysis.has_data else 0,
            has_db2=discovery.has_db2 if discovery.has_data else False,
            has_vsam=discovery.has_vsam if discovery.has_data else False
        )

    def _decide_database(
        self,
        has_postgresql: bool,
        has_mysql: bool,
        has_dynamodb: bool,
        has_jpa: bool,
        entity_count: int,
        repository_count: int,
        erd_entity_count: int,
        has_db2: bool,
        has_vsam: bool
    ) -> DatabaseRecommendation:
        """
        Apply decision tree for database selection.

        Decision tree:
        1. Has PostgreSQL driver? -> Aurora PostgreSQL
        2. Has MySQL driver? -> Aurora MySQL
        3. Has DynamoDB SDK? -> DynamoDB
        4. Has JPA but no driver?
           - Entity count > 20: Aurora PostgreSQL (scalability)
           - Entity count > 5: Aurora or RDS
           - Entity count <= 5: RDS PostgreSQL (cost)
        5. No database dependencies?
           - Data Analysis has entities? -> Warning
           - COBOL has VSAM? -> Recommend S3
           - COBOL has DB2? -> Warning
           - Otherwise: No database needed
        """
        # PostgreSQL detected
        if has_postgresql:
            return self._recommend_aurora_postgresql(entity_count, erd_entity_count)

        # MySQL detected
        if has_mysql:
            return self._recommend_aurora_mysql(entity_count, erd_entity_count)

        # DynamoDB detected
        if has_dynamodb:
            return self._recommend_dynamodb()

        # JPA without specific driver - default to PostgreSQL
        if has_jpa or entity_count > 0 or repository_count > 0:
            self.evidence.append(Evidence(
                source="decision",
                finding="JPA detected without specific driver - defaulting to PostgreSQL"
            ))
            return self._recommend_aurora_postgresql(entity_count, erd_entity_count)

        # No database dependencies in Java
        return self._recommend_no_database(has_vsam)

    def _recommend_aurora_postgresql(
        self,
        entity_count: int,
        erd_entity_count: int
    ) -> DatabaseRecommendation:
        """Recommend Aurora PostgreSQL."""
        total_entities = max(entity_count, erd_entity_count)

        # Size the instance
        if total_entities > 50:
            instance_class = "db.r6g.large"
            storage_gb = 200
        elif total_entities > 20:
            instance_class = "db.r6g.medium"
            storage_gb = 100
        else:
            instance_class = "db.t4g.medium"
            storage_gb = 50

        self.evidence.append(Evidence(
            source="decision",
            finding=f"Aurora PostgreSQL selected based on {total_entities} entities"
        ))

        return DatabaseRecommendation(
            service=DatabaseService.AURORA_POSTGRESQL,
            instance_class=instance_class,
            storage_gb=storage_gb,
            multi_az=True,
            confidence=0.92,
            evidence=self.evidence,
            alternative=AlternativeRecommendation(
                service="RDS PostgreSQL",
                reason="Consider if: simpler setup preferred, lower cost priority, small workload",
                trade_offs=TradeOffs(
                    pros=["Simpler setup", "Lower cost for small workloads"],
                    cons=["Manual scaling", "Less performant at scale", "No serverless option"]
                )
            )
        )

    def _recommend_aurora_mysql(
        self,
        entity_count: int,
        erd_entity_count: int
    ) -> DatabaseRecommendation:
        """Recommend Aurora MySQL."""
        total_entities = max(entity_count, erd_entity_count)

        if total_entities > 50:
            instance_class = "db.r6g.large"
            storage_gb = 200
        elif total_entities > 20:
            instance_class = "db.r6g.medium"
            storage_gb = 100
        else:
            instance_class = "db.t4g.medium"
            storage_gb = 50

        self.evidence.append(Evidence(
            source="decision",
            finding=f"Aurora MySQL selected based on {total_entities} entities"
        ))

        return DatabaseRecommendation(
            service=DatabaseService.AURORA_MYSQL,
            instance_class=instance_class,
            storage_gb=storage_gb,
            multi_az=True,
            confidence=0.90,
            evidence=self.evidence,
            alternative=AlternativeRecommendation(
                service="RDS MySQL",
                reason="Consider if: simpler setup preferred, lower cost priority",
                trade_offs=TradeOffs(
                    pros=["Simpler", "Lower cost for small workloads"],
                    cons=["Manual scaling", "Less performant at scale"]
                )
            )
        )

    def _recommend_dynamodb(self) -> DatabaseRecommendation:
        """Recommend DynamoDB."""
        self.evidence.append(Evidence(
            source="decision",
            finding="DynamoDB SDK detected - NoSQL database selected"
        ))

        return DatabaseRecommendation(
            service=DatabaseService.DYNAMODB,
            instance_class=None,
            storage_gb=None,
            multi_az=True,  # DynamoDB is always multi-AZ
            confidence=0.95,
            evidence=self.evidence,
            alternative=AlternativeRecommendation(
                service="Aurora PostgreSQL",
                reason="Consider if: complex queries needed, relationships required, ACID transactions",
                trade_offs=TradeOffs(
                    pros=["Complex queries", "Joins", "ACID transactions"],
                    cons=["Higher cost at scale", "Less flexible schema"]
                )
            )
        )

    def _recommend_no_database(self, has_vsam: bool) -> DatabaseRecommendation:
        """Recommend no database when no dependencies found."""
        self.evidence.append(Evidence(
            source="java",
            finding="No JDBC/JPA dependencies in pom.xml"
        ))
        self.evidence.append(Evidence(
            source="java",
            finding="No @Entity or @Repository annotations"
        ))

        # If VSAM detected, suggest S3
        if has_vsam:
            self.evidence.append(Evidence(
                source="discovery",
                finding="VSAM file-based processing detected"
            ))
            return DatabaseRecommendation(
                service=DatabaseService.NONE,
                instance_class=None,
                storage_gb=None,
                multi_az=False,
                confidence=0.88,
                evidence=self.evidence,
                alternative=None,
                alternative_storage={
                    "service": "Amazon S3",
                    "reason": "VSAM files migrate naturally to S3 objects",
                    "buckets": [
                        {"name": "input-data", "purpose": "Input files"},
                        {"name": "output-data", "purpose": "Processed output"},
                        {"name": "archive", "storage_class": "S3 Glacier"}
                    ]
                }
            )

        return DatabaseRecommendation(
            service=DatabaseService.NONE,
            instance_class=None,
            storage_gb=None,
            multi_az=False,
            confidence=0.85,
            evidence=self.evidence,
            alternative=AlternativeRecommendation(
                service="DynamoDB",
                reason="Consider if: need to add simple key-value storage later",
                trade_offs=TradeOffs(
                    pros=["Serverless", "Pay per request", "No management"],
                    cons=["Requires code changes to add"]
                )
            )
        )


def recommend_database(sources: ConsolidatedSources) -> DatabaseRecommendation:
    """
    Convenience function to get database recommendation.

    Args:
        sources: Consolidated source data

    Returns:
        DatabaseRecommendation
    """
    recommender = DatabaseRecommender(sources)
    return recommender.recommend()
