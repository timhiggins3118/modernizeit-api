"""
Java Generation V2 - Project Setup Handler
Lambda: JavaGenV2ProjectSetup

Purpose: Create Maven project structure and configuration files

V2 Design Principles:
- NO HARDCODING
- Template-driven (Jinja2)
- Creates Maven skeleton for each microservice
"""

import json
import boto3
import os
from datetime import datetime, timezone
from typing import Dict, Any, List
from jinja2 import Template

s3_client = boto3.client('s3')

# Environment variables (NO HARDCODING)
BUCKET_NAME = os.environ.get('BUCKET_NAME', 'code-transformation-v2')


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
        "job_id": "jgv2_job_...",
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
        job_base = f"{base_path}/java_generation_v2/jobs/{job_id}"

        # Update status
        update_status(job_base, 'running', 'project_setup', 25, 'Creating Maven project structure...')

        # Read generation plan
        plan_key = f"{job_base}/generation_plan.json"
        generation_plan = read_json(plan_key)

        microservices = generation_plan.get('microservices', [])

        if not microservices or len(microservices) == 0:
            # No microservices defined, create single default project
            microservices = [{
                'service_name': 'ModernizedApplication',
                'business_capability': 'Main Application',
                'package': 'services.main'
            }]

        print(f"Creating {len(microservices)} Maven projects")

        projects_created = []

        for service in microservices:
            service_name = service['service_name']
            print(f"\n=== Creating project: {service_name} ===")

            # Create project structure
            project_base = f"{job_base}/artifacts/{service_name}"

            # Generate pom.xml
            pom_content = generate_pom_xml(service_name, application_name)
            write_file(f"{project_base}/pom.xml", pom_content)

            # Generate application.properties
            app_props = generate_application_properties(service_name)
            write_file(f"{project_base}/src/main/resources/application.properties", app_props)

            # Create package structure
            base_package = f"com.modernized.{service_name.lower().replace('service', '')}"
            package_path = base_package.replace('.', '/')

            # Create directories (S3 doesn't need explicit directory creation, but we'll add markers)
            directories = [
                f"{project_base}/src/main/java/{package_path}/entities",
                f"{project_base}/src/main/java/{package_path}/repositories",
                f"{project_base}/src/main/java/{package_path}/services",
                f"{project_base}/src/main/java/{package_path}/controllers",
                f"{project_base}/src/main/java/{package_path}/aws",
                f"{project_base}/src/test/java/{package_path}",
                f"{project_base}/src/main/resources"
            ]

            for directory in directories:
                write_file(f"{directory}/.gitkeep", "# Directory marker")

            # Create Application.java (Spring Boot main class)
            app_class = generate_application_class(base_package, service_name)
            write_file(f"{project_base}/src/main/java/{package_path}/Application.java", app_class)

            # Create README.md
            readme = generate_readme(service_name, service.get('business_capability', ''))
            write_file(f"{project_base}/README.md", readme)

            projects_created.append({
                'service_name': service_name,
                'base_path': project_base,
                'base_package': base_package
            })

            print(f"✓ Created project structure for {service_name}")

        # Write project metadata
        project_metadata = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'projects': projects_created,
            'total_projects': len(projects_created)
        }

        metadata_key = f"{job_base}/project_metadata.json"
        write_json(metadata_key, project_metadata)

        print(f"\n✓ Created {len(projects_created)} Maven projects")

        # Update status
        update_status(job_base, 'running', 'project_setup_complete', 30, f'Created {len(projects_created)} Maven projects')

        return {
            'statusCode': 200,
            'projects_created': projects_created,
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


def generate_application_class(base_package: str, service_name: str) -> str:
    """Generate Spring Boot Application main class"""
    return f"""package {base_package};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * {service_name} - Main Application
 * Generated by Java Generation V2
 * Modernized from legacy COBOL application
 */
@SpringBootApplication
public class Application {{

    public static void main(String[] args) {{
        SpringApplication.run(Application.class, args);
    }}
}}
"""


def generate_readme(service_name: str, business_capability: str) -> str:
    """Generate README.md"""
    return f"""# {service_name}

## Overview

{service_name} provides {business_capability} functionality.

This microservice was automatically generated from a legacy COBOL application using Java Generation V2.

## Technology Stack

- **Java 17**
- **Spring Boot 3.2.0**
- **Spring Data JPA**
- **PostgreSQL** (or DynamoDB)
- **Maven**

## Building

```bash
mvn clean install
```

## Running

```bash
mvn spring-boot:run
```

## Testing

```bash
mvn test
```

## API Documentation

The application exposes REST endpoints for {business_capability.lower()}.

See controllers package for API details.

## Generated Code

This code was automatically generated using:
- **Entities**: From ERD (Data Analyzer V2)
- **Services**: From COBOL logic + Refactor recipes (AI-powered)
- **Controllers**: From API patterns and microservice boundaries

---

**Generated on:** {datetime.now(timezone.utc).isoformat()}
**Generator:** Java Generation V2
"""


def write_file(s3_key: str, content: str):
    """Write file to S3"""
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=content,
        ContentType='text/plain'
    )


def write_json(s3_key: str, data: Dict[str, Any]):
    """Write JSON to S3"""
    s3_client.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=json.dumps(data, indent=2),
        ContentType='application/json'
    )


def read_json(s3_key: str) -> Dict[str, Any]:
    """Read JSON from S3"""
    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
    return json.loads(response['Body'].read().decode('utf-8'))


def update_status(job_base: str, state: str, phase: str, progress: int, message: str):
    """Update job status"""
    try:
        status_key = f"{job_base}/status.json"
        status_response = s3_client.get_object(Bucket=BUCKET_NAME, Key=status_key)
        status_data = json.loads(status_response['Body'].read())

        status_data['state'] = state
        status_data['phase'] = phase
        status_data['progress'] = progress
        status_data['message'] = message
        status_data['last_updated'] = datetime.now(timezone.utc).isoformat()

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=status_key,
            Body=json.dumps(status_data, indent=2),
            ContentType='application/json'
        )

        print(f"Status: {state} / {phase} ({progress}%) - {message}")
    except Exception as e:
        print(f"ERROR updating status: {str(e)}")
