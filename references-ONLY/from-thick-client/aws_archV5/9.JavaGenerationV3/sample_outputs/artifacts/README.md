# ModernizedApplication

## Overview

This is a Modular Monolith application modernized from the legacy COBOL application **TestApp01**.

The application is organized by business domains:

- **core**: 35 services

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
src/main/java/com/modernized/testapp01/
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

**Generated on:** 2025-11-06T14:52:08.006478+00:00
**Generator:** Java Generation V3 (Modular Monolith Architecture)
