"""
Java Analyzer for Architecture Recommender

Scans generated Java code to extract:
- Dependencies from pom.xml / build.gradle
- Annotations (@RestController, @Entity, @Scheduled, etc.)
- Package structure and class breakdown
- Entry points (REST endpoints, scheduled tasks, listeners)

This provides evidence for architecture recommendations.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from api.models.architecture import (
    JavaAnalysis,
    DependencyInfo,
    AnnotationCount,
    ClassBreakdown,
    EntryPoint,
)


# =============================================================================
# Dependency Patterns - What each dependency implies for AWS
# =============================================================================

DEPENDENCY_PATTERNS = {
    'database': {
        'postgresql': ('Aurora PostgreSQL', 'PostgreSQL driver detected'),
        'mysql': ('Aurora MySQL', 'MySQL driver detected'),
        'oracle': ('RDS Oracle', 'Oracle driver detected'),
        'h2': ('In-memory only', 'H2 is for dev/testing only'),
        'spring-data-jpa': ('JPA detected', 'JPA requires relational database'),
        'spring-data-jdbc': ('JDBC detected', 'JDBC requires relational database'),
        'hibernate': ('Hibernate ORM', 'ORM requires relational database'),
        'mybatis': ('MyBatis', 'SQL mapper requires database'),
        'dynamodb': ('DynamoDB', 'AWS DynamoDB SDK detected'),
    },
    'web': {
        'spring-boot-starter-web': ('REST API', 'Spring Web MVC for REST APIs'),
        'spring-webflux': ('Reactive API', 'Reactive web requires different compute'),
        'spring-boot-starter-webflux': ('Reactive API', 'Reactive web stack'),
        'jersey': ('JAX-RS API', 'JAX-RS REST framework'),
    },
    'messaging': {
        'spring-cloud-aws-sqs': ('SQS', 'SQS integration detected'),
        'spring-cloud-aws-messaging': ('SQS', 'AWS messaging integration'),
        'spring-kafka': ('MSK/Kafka', 'Kafka integration'),
        'spring-jms': ('MQ migration', 'JMS requires MQ replacement'),
        'activemq': ('Amazon MQ', 'ActiveMQ detected'),
        'rabbitmq': ('Amazon MQ', 'RabbitMQ detected'),
    },
    'aws': {
        'aws-sdk': ('AWS SDK', 'General AWS SDK usage'),
        'aws-lambda-java': ('Lambda-ready', 'Lambda handler detected'),
        'aws-java-sdk-s3': ('S3 integration', 'S3 SDK detected'),
        'aws-java-sdk-dynamodb': ('DynamoDB', 'DynamoDB SDK detected'),
        'aws-java-sdk-sqs': ('SQS', 'SQS SDK detected'),
        'aws-java-sdk-sns': ('SNS', 'SNS SDK detected'),
    },
    'batch': {
        'spring-batch': ('AWS Batch', 'Spring Batch for batch processing'),
        'spring-boot-starter-batch': ('AWS Batch', 'Batch processing detected'),
    },
    'security': {
        'spring-security': ('Cognito/IAM', 'Spring Security requires auth'),
        'spring-boot-starter-security': ('Cognito/IAM', 'Security enabled'),
        'oauth2': ('Cognito', 'OAuth2 requires Cognito'),
        'jwt': ('API Gateway', 'JWT auth via API Gateway'),
    },
}


# =============================================================================
# Annotation Patterns - What each annotation implies for AWS
# =============================================================================

ANNOTATION_PATTERNS = {
    '@RestController': ('REST endpoints', 'API Gateway + Lambda/ECS'),
    '@Controller': ('Web MVC', 'ECS/Fargate for web apps'),
    '@Entity': ('JPA entities', 'Database required'),
    '@Table': ('JPA entities', 'Database required'),
    '@Repository': ('Data access', 'Database required'),
    '@Scheduled': ('Scheduled tasks', 'CloudWatch Events + Lambda'),
    '@SqsListener': ('SQS consumer', 'Lambda + SQS trigger'),
    '@KafkaListener': ('Kafka consumer', 'MSK + Lambda'),
    '@JmsListener': ('JMS consumer', 'Amazon MQ + ECS'),
    '@Service': ('Business logic', 'Service layer'),
    '@Component': ('Spring component', 'General component'),
    '@Configuration': ('Config class', 'Configuration'),
    '@EnableScheduling': ('Scheduling enabled', 'CloudWatch Events'),
    '@EnableAsync': ('Async processing', 'SQS + Lambda'),
    '@EnableWebSocket': ('WebSocket', 'API Gateway WebSocket'),
    '@PreAuthorize': ('Auth required', 'Cognito/IAM'),
    '@Secured': ('Auth required', 'Cognito/IAM'),
    '@Transactional': ('Transactions', 'Database transactions'),
    '@Cacheable': ('Caching', 'ElastiCache'),
    '@SpringBootApplication': ('Spring Boot', 'Spring Boot app'),
}


class JavaAnalyzer:
    """Analyzes generated Java code for architecture evidence."""

    def __init__(self, java_source_path: str):
        """
        Initialize analyzer with path to Java source.

        Args:
            java_source_path: Path to generated Java code
                             (typically from Code Analysis output)
        """
        self.java_path = Path(java_source_path)
        self.dependencies: Dict[str, List[DependencyInfo]] = defaultdict(list)
        self.annotations: Dict[str, int] = defaultdict(int)
        self.class_breakdown = ClassBreakdown()
        self.entry_points: List[EntryPoint] = []
        self.build_tool: str = "unknown"
        self.framework: Optional[str] = None
        self.java_version: Optional[str] = None
        self.files_analyzed: int = 0
        self.packages_analyzed: int = 0

    def analyze(self) -> JavaAnalysis:
        """
        Run complete Java analysis.

        Returns:
            JavaAnalysis with all findings
        """
        if not self.java_path.exists():
            return self._empty_analysis()

        # Analyze build files
        self._analyze_pom_xml()
        self._analyze_gradle()

        # Analyze Java source files
        self._analyze_java_files()

        # Build result
        return JavaAnalysis(
            build_tool=self.build_tool,
            framework=self.framework,
            java_version=self.java_version,
            dependencies=dict(self.dependencies),
            annotations_found=self._build_annotation_counts(),
            class_breakdown=self.class_breakdown,
            entry_points=self.entry_points,
            packages_analyzed=self.packages_analyzed,
            files_analyzed=self.files_analyzed,
        )

    def _empty_analysis(self) -> JavaAnalysis:
        """Return empty analysis when no Java source found."""
        return JavaAnalysis(
            build_tool="unknown",
            framework=None,
            java_version=None,
            dependencies={},
            annotations_found=[],
            class_breakdown=ClassBreakdown(),
            entry_points=[],
            packages_analyzed=0,
            files_analyzed=0,
        )

    def _analyze_pom_xml(self) -> None:
        """Analyze Maven pom.xml for dependencies."""
        pom_files = list(self.java_path.glob("**/pom.xml"))

        for pom_file in pom_files:
            self.build_tool = "maven"
            try:
                tree = ET.parse(pom_file)
                root = tree.getroot()

                # Handle namespace
                ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
                ns_prefix = '{http://maven.apache.org/POM/4.0.0}'

                # Check if namespace is used
                if root.tag.startswith(ns_prefix):
                    deps = root.findall('.//m:dependency', ns)
                    java_version = root.find('.//m:maven.compiler.target', ns)
                    if java_version is None:
                        java_version = root.find('.//m:java.version', ns)
                else:
                    deps = root.findall('.//dependency')
                    java_version = root.find('.//maven.compiler.target')
                    if java_version is None:
                        java_version = root.find('.//java.version')

                if java_version is not None and java_version.text:
                    self.java_version = java_version.text

                for dep in deps:
                    if root.tag.startswith(ns_prefix):
                        group_id = dep.find('m:groupId', ns)
                        artifact_id = dep.find('m:artifactId', ns)
                        version = dep.find('m:version', ns)
                    else:
                        group_id = dep.find('groupId')
                        artifact_id = dep.find('artifactId')
                        version = dep.find('version')

                    if group_id is not None and artifact_id is not None:
                        self._categorize_dependency(
                            group_id.text or '',
                            artifact_id.text or '',
                            version.text if version is not None else None
                        )

                # Detect Spring Boot
                parent = root.find('.//m:parent/m:artifactId', ns) if root.tag.startswith(ns_prefix) else root.find('.//parent/artifactId')
                if parent is not None and 'spring-boot' in (parent.text or ''):
                    parent_version = root.find('.//m:parent/m:version', ns) if root.tag.startswith(ns_prefix) else root.find('.//parent/version')
                    self.framework = f"spring-boot-{parent_version.text}" if parent_version is not None else "spring-boot"

            except ET.ParseError:
                continue

    def _analyze_gradle(self) -> None:
        """Analyze Gradle build files for dependencies."""
        gradle_files = list(self.java_path.glob("**/build.gradle"))
        gradle_files.extend(self.java_path.glob("**/build.gradle.kts"))

        for gradle_file in gradle_files:
            if self.build_tool == "unknown":
                self.build_tool = "gradle"

            try:
                content = gradle_file.read_text()

                # Extract dependencies
                dep_pattern = r"(implementation|api|compile|runtimeOnly)\s*['\"]([^'\"]+)['\"]"
                for match in re.finditer(dep_pattern, content):
                    dep_string = match.group(2)
                    parts = dep_string.split(':')
                    if len(parts) >= 2:
                        group_id = parts[0]
                        artifact_id = parts[1]
                        version = parts[2] if len(parts) > 2 else None
                        self._categorize_dependency(group_id, artifact_id, version)

                # Detect Java version
                java_version_match = re.search(r"sourceCompatibility\s*=\s*['\"]?(\d+)['\"]?", content)
                if java_version_match:
                    self.java_version = java_version_match.group(1)

                # Detect Spring Boot
                if 'spring-boot' in content or 'org.springframework.boot' in content:
                    version_match = re.search(r"springBootVersion\s*=\s*['\"]([^'\"]+)['\"]", content)
                    if version_match:
                        self.framework = f"spring-boot-{version_match.group(1)}"
                    else:
                        self.framework = "spring-boot"

            except Exception:
                continue

    def _categorize_dependency(
        self,
        group_id: str,
        artifact_id: str,
        version: Optional[str]
    ) -> None:
        """Categorize a dependency and add to appropriate category."""
        full_name = f"{group_id}:{artifact_id}"

        for category, patterns in DEPENDENCY_PATTERNS.items():
            for pattern, (aws_service, implication) in patterns.items():
                if pattern in artifact_id.lower() or pattern in group_id.lower():
                    dep_info = DependencyInfo(
                        group_id=group_id,
                        artifact_id=artifact_id,
                        version=version,
                        category=category,
                        aws_implication=f"{aws_service} - {implication}"
                    )
                    # Avoid duplicates
                    existing = [d for d in self.dependencies[category]
                               if d.artifact_id == artifact_id]
                    if not existing:
                        self.dependencies[category].append(dep_info)
                    return

    def _analyze_java_files(self) -> None:
        """Analyze Java source files for annotations and patterns."""
        java_files = list(self.java_path.glob("**/*.java"))
        packages_seen = set()

        for java_file in java_files:
            self.files_analyzed += 1

            try:
                content = java_file.read_text()
                filename = java_file.name

                # Track packages
                package_match = re.search(r'package\s+([\w.]+);', content)
                if package_match:
                    packages_seen.add(package_match.group(1))

                # Count annotations
                for annotation in ANNOTATION_PATTERNS:
                    # Match annotation with optional parameters
                    pattern = rf'{re.escape(annotation)}(?:\s*\([^)]*\))?'
                    count = len(re.findall(pattern, content))
                    if count > 0:
                        self.annotations[annotation] += count

                # Classify by file name pattern
                self._classify_class(filename, content)

                # Extract entry points
                self._extract_entry_points(filename, content)

            except Exception:
                continue

        self.packages_analyzed = len(packages_seen)

    def _classify_class(self, filename: str, content: str) -> None:
        """Classify Java class by type."""
        self.class_breakdown.total += 1

        if filename.endswith('Controller.java') or '@RestController' in content or '@Controller' in content:
            self.class_breakdown.controllers += 1
        elif filename.endswith('Service.java') or filename.endswith('ServiceImpl.java'):
            self.class_breakdown.services += 1
        elif filename.endswith('Repository.java') or '@Repository' in content:
            self.class_breakdown.repositories += 1
        elif '@Entity' in content or '@Table' in content:
            self.class_breakdown.entities += 1
        elif 'Batch' in filename or 'Job' in filename or '@Scheduled' in content:
            self.class_breakdown.batch_jobs += 1
        elif '@Configuration' in content:
            self.class_breakdown.configurations += 1
        elif '@Component' in content:
            self.class_breakdown.components += 1

    def _extract_entry_points(self, filename: str, content: str) -> None:
        """Extract entry points from Java class."""
        class_match = re.search(r'class\s+(\w+)', content)
        if not class_match:
            return

        class_name = class_match.group(1)

        # REST Controllers
        if '@RestController' in content or '@Controller' in content:
            # Count endpoints
            endpoint_patterns = [
                r'@GetMapping',
                r'@PostMapping',
                r'@PutMapping',
                r'@DeleteMapping',
                r'@PatchMapping',
                r'@RequestMapping\s*\(\s*[^)]*method\s*=',
            ]
            endpoint_count = sum(
                len(re.findall(pattern, content))
                for pattern in endpoint_patterns
            )

            if endpoint_count > 0:
                self.entry_points.append(EntryPoint(
                    class_name=class_name,
                    entry_type="REST",
                    endpoint_count=endpoint_count,
                    trigger="API Gateway"
                ))

        # Scheduled tasks
        scheduled_matches = re.findall(
            r'@Scheduled\s*\(\s*cron\s*=\s*["\']([^"\']+)["\']',
            content
        )
        if scheduled_matches:
            for cron in scheduled_matches:
                self.entry_points.append(EntryPoint(
                    class_name=class_name,
                    entry_type="SCHEDULED",
                    cron_expression=cron,
                    trigger="CloudWatch Events"
                ))
        elif '@Scheduled' in content:
            self.entry_points.append(EntryPoint(
                class_name=class_name,
                entry_type="SCHEDULED",
                trigger="CloudWatch Events"
            ))

        # SQS Listeners
        if '@SqsListener' in content:
            self.entry_points.append(EntryPoint(
                class_name=class_name,
                entry_type="SQS_LISTENER",
                trigger="SQS"
            ))

        # Kafka Listeners
        if '@KafkaListener' in content:
            self.entry_points.append(EntryPoint(
                class_name=class_name,
                entry_type="KAFKA_LISTENER",
                trigger="MSK"
            ))

    def _build_annotation_counts(self) -> List[AnnotationCount]:
        """Build list of annotation counts."""
        counts = []
        for annotation, count in sorted(
            self.annotations.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if annotation in ANNOTATION_PATTERNS:
                _, implication = ANNOTATION_PATTERNS[annotation]
                counts.append(AnnotationCount(
                    annotation=annotation,
                    count=count,
                    aws_implication=implication
                ))
        return counts


def analyze_java_code(java_source_path: str) -> JavaAnalysis:
    """
    Convenience function to analyze Java code.

    Args:
        java_source_path: Path to generated Java source

    Returns:
        JavaAnalysis with all findings
    """
    analyzer = JavaAnalyzer(java_source_path)
    return analyzer.analyze()
