# Run Generated Java - Quick Runbook

## User Flow

Users download the packaged Java from **Java Packaging**, not from internal folders.

```
Code Analysis → Code Refactor → Java Packaging → Download ZIP
```

## Download Location

Portal: Click "Download" on Java Packaging results

API: `GET /java-packaging/download/{job_id}`

## Run Downloaded Package

1. Unzip the downloaded file
2. Open folder in IntelliJ (or terminal)

### Using Docker (Recommended)
```bash
docker-compose up --build
# App at http://localhost:8080
```

### Using Maven
```bash
mvn clean package
java -jar target/*.jar
```

## Notes

- Package includes: pom.xml, Dockerfile, docker-compose.yml, README
- Requires PostgreSQL (docker-compose handles this)
- File I/O and external CALLs are stubbed until fully implemented
