"""
Cross Validator for Architecture Recommender

Validates consistency between sources:
- Agreement = High confidence
- Conflict = Warning (NOT blocker)

Cross-validation increases confidence when sources agree,
and generates warnings when they conflict.
"""

from typing import Any, Dict, List, Tuple
from dataclasses import dataclass, field

from api.models.architecture import (
    ValidationWarning,
    ValidationCheck,
    ValidationReport,
    Severity,
)
from engines.architecture.analyzers.source_consolidator import ConsolidatedSources


@dataclass
class ValidationResult:
    """Result of a single validation check."""
    check_name: str
    passed: bool
    warning: ValidationWarning | None = None
    confidence_boost: float = 0.0


class CrossValidator:
    """Validates consistency between sources."""

    def __init__(self, sources: ConsolidatedSources):
        """
        Initialize validator.

        Args:
            sources: Consolidated source data
        """
        self.sources = sources
        self.warnings: List[ValidationWarning] = []
        self.checks: List[ValidationCheck] = []
        self.confidence_adjustments: Dict[str, float] = {
            'compute': 0.0,
            'database': 0.0,
            'api': 0.0,
            'storage': 0.0,
        }

    def validate(self) -> ValidationReport:
        """
        Run all validation checks.

        Returns:
            ValidationReport with results
        """
        # Run all validation rules
        self._validate_database_consistency()
        self._validate_api_consistency()
        self._validate_messaging_consistency()
        self._validate_batch_consistency()
        self._validate_file_storage_consistency()

        # Calculate overall confidence
        base_confidence = 0.70  # Start with 70%
        total_boost = sum(self.confidence_adjustments.values())
        overall_confidence = min(0.99, base_confidence + total_boost)

        # Build confidence breakdown
        confidence_breakdown = {
            'compute': min(0.99, 0.70 + self.confidence_adjustments.get('compute', 0)),
            'database': min(0.99, 0.70 + self.confidence_adjustments.get('database', 0)),
            'api': min(0.99, 0.70 + self.confidence_adjustments.get('api', 0)),
            'storage': min(0.99, 0.70 + self.confidence_adjustments.get('storage', 0)),
            'overall': overall_confidence,
        }

        # Determine status
        passed_count = len([c for c in self.checks if c.passed])
        warning_count = len(self.warnings)
        failed_count = len([c for c in self.checks if not c.passed and
                           not any(w.warning_type == "SOURCE_CONFLICT" for w in self.warnings
                                  if w.description and c.check_name in w.description)])

        if failed_count > 0:
            status = "FAILED"
        elif warning_count > 0:
            status = "PASSED_WITH_WARNINGS"
        else:
            status = "PASSED"

        return ValidationReport(
            status=status,
            checks_passed=passed_count,
            checks_warned=warning_count,
            checks_failed=failed_count,
            checks=self.checks,
            warnings=self.warnings,
            confidence_breakdown=confidence_breakdown,
        )

    def _validate_database_consistency(self) -> None:
        """Check if database usage is consistent across sources."""
        check_name = "database_consistency"

        # Evidence from Java
        java = self.sources.java_analysis
        java_has_db = False
        java_db_type = None

        if java:
            db_deps = java.dependencies.get('database', [])
            if db_deps:
                java_has_db = True
                # Determine type
                for dep in db_deps:
                    if 'postgresql' in dep.artifact_id.lower():
                        java_db_type = 'postgresql'
                        break
                    elif 'mysql' in dep.artifact_id.lower():
                        java_db_type = 'mysql'
                        break

            # Also check for JPA entities
            if java.class_breakdown.entities > 0 or java.class_breakdown.repositories > 0:
                java_has_db = True

        # Evidence from Discovery
        discovery = self.sources.discovery
        discovery_has_db = discovery.has_db2 if discovery.has_data else False

        # Evidence from Data Analysis
        data_analysis = self.sources.data_analysis
        da_has_entities = data_analysis.entity_count > 0 if data_analysis.has_data else False

        # Cross-validate
        all_agree = (java_has_db == discovery_has_db == da_has_entities) or \
                   (not discovery.has_data and not data_analysis.has_data)

        if java_has_db and da_has_entities:
            # Strong agreement - boost confidence
            self.confidence_adjustments['database'] += 0.15
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="Database dependencies in Java match entities in Data Analysis"
            ))

        elif java_has_db and discovery_has_db:
            # Agreement between Java and Discovery
            self.confidence_adjustments['database'] += 0.10
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="Database dependencies in Java match DB2 detection in Discovery"
            ))

        elif not java_has_db and not discovery_has_db and not da_has_entities:
            # No database anywhere - this is fine
            self.confidence_adjustments['database'] += 0.10
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="No database usage detected across all sources"
            ))

        elif discovery_has_db and not java_has_db:
            # Conflict: COBOL has DB2 but Java doesn't have DB
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,  # Warning, not failure
                message="DB2 detected in COBOL but no database dependencies in Java"
            ))
            self.warnings.append(ValidationWarning(
                warning_type="SOURCE_CONFLICT",
                severity=Severity.MEDIUM,
                description="Database mismatch: DB2 in COBOL, no database in Java",
                sources={
                    "discovery": "DB2 integration detected in COBOL",
                    "java": "No JDBC/JPA dependencies found"
                },
                possible_causes=[
                    "Java generation did not include database layer",
                    "Database access planned for later phase",
                    "Data migrated to file-based storage (S3)"
                ],
                recommendation="Review Java generation or confirm file-based approach"
            ))

        elif da_has_entities and not java_has_db:
            # Conflict: Data Analysis has entities but Java doesn't have DB
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="ERD entities exist but no database dependencies in Java"
            ))
            self.warnings.append(ValidationWarning(
                warning_type="SOURCE_CONFLICT",
                severity=Severity.MEDIUM,
                description="Entity mismatch: ERD shows entities, no database in Java",
                sources={
                    "data_analysis": f"{data_analysis.entity_count} entities in ERD",
                    "java": "No JDBC/JPA dependencies found"
                },
                possible_causes=[
                    "Java generation used different data access pattern",
                    "Entities stored in-memory or via files",
                    "Database layer to be added later"
                ],
                recommendation="Verify data persistence strategy"
            ))

        else:
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="Database configuration needs review"
            ))

    def _validate_api_consistency(self) -> None:
        """Check if API patterns are consistent."""
        check_name = "api_consistency"

        # Evidence from Java
        java = self.sources.java_analysis
        java_has_api = False
        java_endpoint_count = 0

        if java:
            for entry in java.entry_points:
                if entry.entry_type == "REST":
                    java_has_api = True
                    java_endpoint_count += entry.endpoint_count or 0

            # Also check annotations
            for ann in java.annotations_found:
                if ann.annotation == "@RestController":
                    java_has_api = True

        # Evidence from Discovery
        discovery = self.sources.discovery
        discovery_says_realtime = False
        if discovery.has_data:
            pattern = discovery.primary_pattern.lower()
            discovery_says_realtime = 'real' in pattern or 'online' in pattern or 'transaction' in pattern
            if discovery.real_time_processes > 0:
                discovery_says_realtime = True

        # Cross-validate
        if java_has_api and discovery_says_realtime:
            # Strong agreement
            self.confidence_adjustments['api'] += 0.15
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message=f"REST API ({java_endpoint_count} endpoints) matches real-time pattern from Discovery"
            ))

        elif java_has_api and not discovery_says_realtime and discovery.has_data:
            # Java has API but Discovery says batch
            self.confidence_adjustments['api'] += 0.05
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="REST API in Java, batch pattern in Discovery (hybrid?)"
            ))
            self.warnings.append(ValidationWarning(
                warning_type="SOURCE_CONFLICT",
                severity=Severity.LOW,
                description="API pattern mismatch: Java has REST, Discovery indicates batch",
                sources={
                    "java": f"{java_endpoint_count} REST endpoints detected",
                    "discovery": f"Primary pattern: {discovery.primary_pattern}"
                },
                possible_causes=[
                    "Application is hybrid (both API and batch)",
                    "API added during modernization",
                    "Discovery analysis focused on batch components"
                ],
                recommendation="Consider hybrid architecture (API Gateway + scheduled tasks)"
            ))

        elif not java_has_api and discovery_says_realtime:
            # Discovery says real-time but no API in Java
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="Discovery indicates real-time but no REST controllers in Java"
            ))
            self.warnings.append(ValidationWarning(
                warning_type="SOURCE_CONFLICT",
                severity=Severity.MEDIUM,
                description="API mismatch: Discovery expects real-time, no REST in Java",
                sources={
                    "discovery": "Real-time/online pattern detected",
                    "java": "No @RestController annotations found"
                },
                possible_causes=[
                    "API layer not yet generated",
                    "CICS transactions not converted to REST",
                    "Different API pattern used (gRPC, GraphQL)"
                ],
                recommendation="Review CICS conversion strategy"
            ))

        else:
            # No API expected or detected
            self.confidence_adjustments['api'] += 0.05
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="No API required (batch-only application)"
            ))

    def _validate_messaging_consistency(self) -> None:
        """Check if messaging patterns are consistent."""
        check_name = "messaging_consistency"

        # Evidence from Java
        java = self.sources.java_analysis
        java_has_messaging = False

        if java:
            msg_deps = java.dependencies.get('messaging', [])
            if msg_deps:
                java_has_messaging = True

            for ann in java.annotations_found:
                if 'Listener' in ann.annotation:
                    java_has_messaging = True

        # Evidence from Discovery
        discovery = self.sources.discovery
        discovery_has_mq = discovery.has_mq if discovery.has_data else False

        # Cross-validate
        if java_has_messaging and discovery_has_mq:
            # Agreement
            self.confidence_adjustments['compute'] += 0.10
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="Messaging in Java matches MQ detection in Discovery"
            ))

        elif not java_has_messaging and not discovery_has_mq:
            # No messaging - fine
            self.confidence_adjustments['compute'] += 0.05
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="No messaging patterns detected"
            ))

        elif discovery_has_mq and not java_has_messaging:
            # MQ in COBOL but not in Java
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="MQ detected in COBOL but no messaging in Java"
            ))
            self.warnings.append(ValidationWarning(
                warning_type="SOURCE_CONFLICT",
                severity=Severity.MEDIUM,
                description="Messaging mismatch: MQ in COBOL, no messaging in Java",
                sources={
                    "discovery": "IBM MQ integration detected",
                    "java": "No messaging dependencies (SQS, Kafka, JMS)"
                },
                possible_causes=[
                    "MQ integration planned for later phase",
                    "Synchronous approach chosen instead",
                    "Different integration pattern (HTTP/REST)"
                ],
                recommendation="Consider adding SQS integration for async processing"
            ))

        else:
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="Messaging configuration needs review"
            ))

    def _validate_batch_consistency(self) -> None:
        """Check if batch processing patterns are consistent."""
        check_name = "batch_consistency"

        # Evidence from Java
        java = self.sources.java_analysis
        java_has_batch = False
        java_scheduled_count = 0

        if java:
            if java.class_breakdown.batch_jobs > 0:
                java_has_batch = True

            for entry in java.entry_points:
                if entry.entry_type == "SCHEDULED":
                    java_has_batch = True
                    java_scheduled_count += 1

            for ann in java.annotations_found:
                if ann.annotation == "@Scheduled":
                    java_has_batch = True

        # Evidence from Discovery
        discovery = self.sources.discovery
        discovery_has_batch = False
        if discovery.has_data:
            if discovery.batch_processes > 0:
                discovery_has_batch = True
            pattern = discovery.primary_pattern.lower()
            if 'batch' in pattern:
                discovery_has_batch = True

        # Cross-validate
        if java_has_batch and discovery_has_batch:
            self.confidence_adjustments['compute'] += 0.10
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message=f"Batch processing ({java_scheduled_count} scheduled) matches Discovery"
            ))

        elif not java_has_batch and not discovery_has_batch:
            self.confidence_adjustments['compute'] += 0.05
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="No batch processing detected"
            ))

        elif discovery_has_batch and not java_has_batch:
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="Batch in Discovery but no @Scheduled in Java"
            ))
            self.warnings.append(ValidationWarning(
                warning_type="SOURCE_CONFLICT",
                severity=Severity.LOW,
                description="Batch mismatch: Discovery shows batch, no scheduling in Java",
                sources={
                    "discovery": f"{discovery.batch_processes} batch processes",
                    "java": "No @Scheduled annotations or batch jobs"
                },
                possible_causes=[
                    "Batch scheduling added externally (CloudWatch Events)",
                    "Batch converted to on-demand processing",
                    "Step Functions orchestration instead"
                ],
                recommendation="Consider Step Functions for batch orchestration"
            ))

        else:
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="Batch configuration reviewed"
            ))

    def _validate_file_storage_consistency(self) -> None:
        """Check if file storage patterns are consistent."""
        check_name = "storage_consistency"

        # Evidence from Discovery
        discovery = self.sources.discovery
        discovery_has_vsam = discovery.has_vsam if discovery.has_data else False

        # Evidence from Java
        java = self.sources.java_analysis
        java_has_s3 = False

        if java:
            aws_deps = java.dependencies.get('aws', [])
            for dep in aws_deps:
                if 's3' in dep.artifact_id.lower():
                    java_has_s3 = True

        # Cross-validate
        if discovery_has_vsam and java_has_s3:
            self.confidence_adjustments['storage'] += 0.10
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="VSAM in COBOL migrated to S3 in Java"
            ))

        elif discovery_has_vsam and not java_has_s3:
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="VSAM detected but no S3 SDK in Java"
            ))
            self.warnings.append(ValidationWarning(
                warning_type="MISSING_DATA",
                severity=Severity.LOW,
                description="VSAM detected but no S3 integration in Java",
                sources={
                    "discovery": "VSAM file processing detected",
                    "java": "No AWS S3 SDK dependency"
                },
                possible_causes=[
                    "S3 integration planned for later",
                    "Local file system used temporarily",
                    "Different storage strategy chosen"
                ],
                recommendation="Add AWS S3 SDK for file storage"
            ))

        else:
            self.confidence_adjustments['storage'] += 0.05
            self.checks.append(ValidationCheck(
                check_name=check_name,
                passed=True,
                message="Storage patterns validated"
            ))


def validate_sources(sources: ConsolidatedSources) -> ValidationReport:
    """
    Convenience function to validate sources.

    Args:
        sources: Consolidated source data

    Returns:
        ValidationReport
    """
    validator = CrossValidator(sources)
    return validator.validate()
