"""
Java Generation V3 - Project Setup Handler
Lambda: JavaGenV3ProjectSetup

Purpose: Create Maven project structure and configuration files

V3 Design Principles:
- NO HARDCODING
- Template-driven (Jinja2)
- Creates ONE Maven project (Modular Monolith)
- Organized by business domains (not microservices)
"""

import json
import boto3
import os
from datetime import datetime, timezone
from typing import Dict, Any, List
from jinja2 import Template

s3_client = boto3.client('s3')

# Environment variables (NO HARDCODING)
INPUT_BUCKET = os.environ.get('INPUT_BUCKET', 'code-transformation-v2')  # Read V2 artifacts
OUTPUT_BUCKET = os.environ.get('OUTPUT_BUCKET', 'code-transformation-v3')  # Write V3 results


# Jinja2 template for pom.xml (inline for Lambda deployment)
POM_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>{{ spring_boot_version }}</version>
        <relativePath/>
    </parent>

    <groupId>{{ group_id }}</groupId>
    <artifactId>{{ artifact_id }}</artifactId>
    <version>{{ version }}</version>
    <name>{{ project_name }}</name>
    <description>{{ description }}</description>

    <properties>
        <java.version>17</java.version>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
        <aws.sdk.version>2.20.0</aws.sdk.version>
        <lombok.version>1.18.34</lombok.version>
    </properties>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>software.amazon.awssdk</groupId>
                <artifactId>bom</artifactId>
                <version>${aws.sdk.version}</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <!-- AWS SDK Dependencies -->
        <dependency>
            <groupId>software.amazon.awssdk</groupId>
            <artifactId>aws-core</artifactId>
        </dependency>
        <dependency>
            <groupId>software.amazon.awssdk</groupId>
            <artifactId>regions</artifactId>
        </dependency>
        <dependency>
            <groupId>software.amazon.awssdk</groupId>
            <artifactId>dynamodb</artifactId>
        </dependency>
        <dependency>
            <groupId>software.amazon.awssdk</groupId>
            <artifactId>s3</artifactId>
        </dependency>
        <dependency>
            <groupId>software.amazon.awssdk</groupId>
            <artifactId>sqs</artifactId>
        </dependency>
        <dependency>
            <groupId>software.amazon.awssdk</groupId>
            <artifactId>eventbridge</artifactId>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.11.0</version>
                <configuration>
                    <source>17</source>
                    <target>17</target>
                    <annotationProcessorPaths>
                        <path>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                            <version>1.18.34</version>
                        </path>
                    </annotationProcessorPaths>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
"""


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Create Maven project structure

    Input:
    {
        "job_id": "jgv3_job_...",
        "scout_account_id": "5150",
        "application_name": "TestApp01"
    }

    Output:
    {
        "projects_created": [list of project names],
        "structure_ready": true
    }
    """
    try:
        print("=" * 80)
        print("JAVA GENERATION V2 - PROJECT SETUP")
        print("=" * 80)

        job_id = event['job_id']
        scout_account_id = event['scout_account_id']
        application_name = event['application_name']

        print(f"Job ID: {job_id}")

        base_path = f"{scout_account_id}/{application_name}"
        job_base = f"{base_path}/java_generation_v3/jobs/{job_id}"

        # Update status
        update_status(job_base, 'running', 'project_setup', 25, 'Creating Maven project structure...')

        # Read generation plan
        plan_key = f"{job_base}/generation_plan.json"
        generation_plan = read_json(plan_key)

        # V3: Read domains array (not microservices - modular monolith!)
        domains = generation_plan.get('domains', [])

        if not domains or len(domains) == 0:
            # No domains defined, create single default domain
            domains = [{
                'domain_name': 'core',
                'package': 'core',
                'services': [],
                'service_count': 0
            }]

        print(f"Creating ONE Maven project with {len(domains)} business domains")

        # V3: Create ONE Maven project for entire application (Modular Monolith)
        project_name = "ModernizedApplication"
        project_base = f"{job_base}/artifacts/{project_name}"

        print(f"\n=== Creating Modular Monolith: {project_name} ===")

        # Generate pom.xml (ONE for entire application)
        pom_content = generate_pom_xml(project_name, application_name)
        write_file(f"{project_base}/pom.xml", pom_content)

        # Generate application.properties (ONE for entire application)
        app_props = generate_application_properties(application_name)
        write_file(f"{project_base}/src/main/resources/application.properties", app_props)

        # Create base package structure
        base_package = f"com.modernized.{application_name.lower()}"
        package_path = base_package.replace('.', '/')

        # Create common directories (shared across all domains)
        common_directories = [
            f"{project_base}/src/main/java/{package_path}/common",
            f"{project_base}/src/main/java/{package_path}/config",
            f"{project_base}/src/test/java/{package_path}",
            f"{project_base}/src/main/resources"
        ]

        for directory in common_directories:
            write_file(f"{directory}/.gitkeep", "# Directory marker")

        # Create domain-specific directories
        print(f"\nCreating domain-based package structure:")
        domain_info = []

        for domain in domains:
            domain_name = domain['domain_name']
            service_count = domain['service_count']

            print(f"  - {domain_name}: {service_count} services")

            # Each domain gets: entities/, services/, repositories/, controllers/
            domain_directories = [
                f"{project_base}/src/main/java/{package_path}/domains/{domain_name}/entities",
                f"{project_base}/src/main/java/{package_path}/domains/{domain_name}/services",
                f"{project_base}/src/main/java/{package_path}/domains/{domain_name}/repositories",
                f"{project_base}/src/main/java/{package_path}/domains/{domain_name}/controllers"
            ]

            for directory in domain_directories:
                write_file(f"{directory}/.gitkeep", "# Directory marker")

            domain_info.append({
                'domain_name': domain_name,
                'package': f"{base_package}.domains.{domain_name}",
                'service_count': service_count
            })

        # Create Application.java (Spring Boot main class)
        app_class = generate_application_class(base_package, application_name)
        write_file(f"{project_base}/src/main/java/{package_path}/Application.java", app_class)

        # Create README.md
        readme = generate_readme(project_name, application_name, domains)
        write_file(f"{project_base}/README.md", readme)

        print(f"\n✓ Created Modular Monolith project: {project_name}")

        # Write project metadata
        project_metadata = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'project_name': project_name,
            'project_base': project_base,
            'base_package': base_package,
            'domains': domain_info,
            'total_domains': len(domain_info)
        }

        metadata_key = f"{job_base}/project_metadata.json"
        write_json(metadata_key, project_metadata)

        print(f"\n✓ Created Modular Monolith with {len(domain_info)} domains")

        # Update status
        update_status(job_base, 'running', 'project_setup_complete', 30, f'Created Maven project with {len(domain_info)} domains')

        return {
            'statusCode': 200,
            'project_name': project_name,
            'project_base': project_base,
            'base_package': base_package,
            'domains': domain_info,
            'structure_ready': True
        }

    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


def generate_pom_xml(service_name: str, application_name: str) -> str:
    """Generate pom.xml from template"""
    template = Template(POM_TEMPLATE)

    artifact_id = service_name.lower().replace('service', '-service')

    return template.render(
        spring_boot_version='3.2.0',
        group_id='com.modernized',
        artifact_id=artifact_id,
        version='1.0.0-SNAPSHOT',
        project_name=service_name,
        description=f'{service_name} - Modernized from COBOL application {application_name}'
    )


def generate_application_properties(service_name: str) -> str:
    """Generate application.properties"""
    return f"""# {service_name} Configuration

# Server Configuration
server.port=8080

# Application Name
spring.application.name={service_name.lower()}

# JPA Configuration
spring.jpa.hibernate.ddl-auto=update
spring.jpa.show-sql=true
spring.jpa.properties.hibernate.dialect=org.hibernate.dialect.PostgreSQLDialect

# DataSource Configuration (PostgreSQL)
spring.datasource.url=jdbc:postgresql://localhost:5432/{service_name.lower()}
spring.datasource.username=postgres
spring.datasource.password=postgres

# Logging
logging.level.root=INFO
logging.level.com.modernized=DEBUG
"""


def generate_application_class(base_package: str, application_name: str) -> str:
    """Generate Spring Boot Application main class"""
    return f"""package {base_package};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * {application_name} - Modernized Application
 * Generated by Java Generation V3
 *
 * This is a Modular Monolith organized by business domains.
 * Modernized from legacy COBOL application.
 */
@SpringBootApplication
public class Application {{

    public static void main(String[] args) {{
        SpringApplication.run(Application.class, args);
    }}
}}
"""


def generate_readme(project_name: str, application_name: str, domains: List[Dict[str, Any]]) -> str:
    """Generate README.md for Modular Monolith"""
    domain_list = '\n'.join([f"- **{d['domain_name']}**: {d['service_count']} services" for d in domains])

    return f"""# {project_name}

## Overview

This is a Modular Monolith application modernized from the legacy COBOL application **{application_name}**.

The application is organized by business domains:

{domain_list}

## Architecture

This application follows the **Modular Monolith** pattern:
- **ONE deployable artifact** (not microservices)
- **Domain-driven design** with clear boundaries
- **Shared infrastructure** (database, logging, security)
- **Easy to extract microservices later** if needed

## Technology Stack

- **Java 17**
- **Spring Boot 3.2.0**
- **Spring Data JPA**
- **PostgreSQL** (or DynamoDB)
- **Maven**
- **Lombok** (reduce boilerplate)

## Project Structure

```
src/main/java/com/modernized/{application_name.lower()}/
├── common/          # Shared utilities and DTOs
├── config/          # Spring configuration
└── domains/         # Business domains
    ├── billing/     # Billing domain
    ├── accounts/    # Accounts domain
    ├── reports/     # Reports domain
    └── core/        # Core/ungrouped services
```

## Building

```bash
mvn clean install
```

## Running Locally

```bash
mvn spring-boot:run
```

## Testing

```bash
mvn test
```

## API Documentation

The application exposes REST endpoints organized by business domain.

See the `controllers` package within each domain for API details.

## Generated Code

This code was automatically generated from COBOL using **Java Generation V3**:
- **Entities**: Generated from ERD (Data Analyzer V2)
- **Services**: Generated from COBOL logic + Refactor recipes (AI-powered)
- **Repositories**: Spring Data JPA repositories with intelligent PK strategies
- **Controllers**: Generated from API patterns and microservice boundaries

---

**Generated on:** {datetime.now(timezone.utc).isoformat()}
**Generator:** Java Generation V3 (Modular Monolith Architecture)
"""


def write_file(s3_key: str, content: str):
    """Write file to S3"""
    s3_client.put_object(
        Bucket=OUTPUT_BUCKET,  # Write to V3 bucket
        Key=s3_key,
        Body=content,
        ContentType='text/plain'
    )


def write_json(s3_key: str, data: Dict[str, Any]):
    """Write JSON to S3"""
    s3_client.put_object(
        Bucket=OUTPUT_BUCKET,  # Write to V3 bucket
        Key=s3_key,
        Body=json.dumps(data, indent=2),
        ContentType='application/json'
    )


def read_json(s3_key: str) -> Dict[str, Any]:
    """Read JSON from S3"""
    # Determine bucket based on key prefix
    bucket = OUTPUT_BUCKET if 'java_generation_v3' in s3_key else INPUT_BUCKET
    response = s3_client.get_object(Bucket=bucket, Key=s3_key)
    return json.loads(response['Body'].read().decode('utf-8'))


def update_status(job_base: str, state: str, phase: str, progress: int, message: str):
    """Update job status"""
    try:
        status_key = f"{job_base}/status.json"
        status_response = s3_client.get_object(Bucket=OUTPUT_BUCKET, Key=status_key)
        status_data = json.loads(status_response['Body'].read())

        status_data['state'] = state
        status_data['phase'] = phase
        status_data['progress'] = progress
        status_data['message'] = message
        status_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        s3_client.put_object(
            Bucket=OUTPUT_BUCKET,  # Write to V3 bucket
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status: {state} / {phase} ({progress}%) - {message}")
    except Exception as e:
        print(f"ERROR updating status: {str(e)}")
