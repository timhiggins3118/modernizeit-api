"""
ModernizeIT API

FastAPI application for local code transformation operations.
Mimics AWS API Gateway contract for compatibility.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure local AWS credentials are set up before any boto3 usage
from config.settings import settings  # noqa: F401 - triggers AWS creds setup

from api.routes.ingest import router as ingest_router
from api.routes.code_analysis import router as code_analysis_router
from api.routes.code_refactor import router as code_refactor_router
from api.routes.dependency_mapper import router as dependency_mapper_router
from api.routes.monolith_identifier import router as monolith_identifier_router
from api.routes.data_analysis import router as data_analysis_router
from api.routes.discovery import router as discovery_router
from api.routes.architecture import router as architecture_router
from api.routes.credentials import router as credentials_router
from api.routes.accounts import router as accounts_router
from api.routes.mongodb_admin import router as mongodb_admin_router
from api.routes.mcp_config import router as mcp_config_router
from api.routes.files import router as files_router
from api.routes.jobs import router as jobs_router
from api.routes.flows import router as flows_router
from api.routes.ai_logs import router as ai_logs_router
from api.routes.mcp_chat import router as mcp_chat_router
from api.routes.ai_flow import router as ai_flow_router
from api.routes.storage import router as storage_router
from api.routes.ai_assistant import router as ai_assistant_router
from api.routes.java_packaging import router as java_packaging_router
from api.routes.test_generation import router as test_generation_router
from api.routes.s3 import router as s3_router
from api.routes.artifacts import router as artifacts_router
from db import init_db, close_mongodb


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup: Initialize SQLite database
    init_db()
    yield
    # Shutdown: Close MongoDB connection
    await close_mongodb()

# Create FastAPI app
app = FastAPI(
    lifespan=lifespan,
    title="ModernizeIT API",
    description="""
    Local API for code transformation operations.

    This API provides endpoints that mirror the AWS API Gateway contract,
    allowing local execution of transformation flows without AWS infrastructure.

    ## Flows

    ### Ingest
    Upload and catalog source files for transformation.
    - `POST /ingest/upload` - Upload and process source files
    - `GET /ingest/jobs/{job_id}/status` - Check job status
    - `GET /ingest/results/{job_id}` - Get job results

    ### Code Analysis
    Full COBOL analysis with JSON artifacts, graphs, and Java generation.
    - `POST /codeanalysis` - Run full analysis pipeline
    - `GET /codeanalysis/{job_id}/status` - Check job status
    - `GET /codeanalysis/{job_id}/results` - Get results overview
    - `GET /codeanalysis/{job_id}/results/json/{filename}` - Get JSON artifact
    - `GET /codeanalysis/{job_id}/results/graphs/{filename}` - Get graph PNG

    ### Code Refactor
    Analyze generated Java for modernization opportunities.
    - `POST /coderefactor` - Run refactor analysis (hybrid rules + AI)
    - `POST /coderefactor/transform` - Apply refactoring recipes
    - `GET /coderefactor/{job_id}/status` - Check job status
    - `GET /coderefactor/{job_id}/results` - Get results overview
    - `GET /coderefactor/{job_id}/results/json/{filename}` - Get JSON artifact
    - `GET /coderefactor/{job_id}/results/recipes` - Get refactor recipes
    - `GET /coderefactor/{job_id}/results/report` - Get Markdown report

    ### Dependency Mapper
    Analyze dependencies in COBOL or Java source code.
    - `POST /dependencymapper` - Run dependency analysis (source_type: cobol or java)
    - `POST /dependencymapper/compare` - Compare COBOL vs Java analysis
    - `GET /dependencymapper/{job_id}/status` - Check job status
    - `GET /dependencymapper/{job_id}/results` - Get results overview
    - `GET /dependencymapper/{job_id}/results/json/{filename}` - Get JSON artifact

    ### Monolith Identifier
    Detect monolithic anti-patterns and generate decomposition strategy.
    - `POST /monolithidentifier` - Run monolith analysis (source_type: cobol or java)
    - `POST /monolithidentifier/compare` - Compare COBOL vs Java analysis
    - `GET /monolithidentifier/{job_id}/status` - Check job status
    - `GET /monolithidentifier/{job_id}/results` - Get results overview
    - `GET /monolithidentifier/{job_id}/results/json/{filename}` - Get JSON artifact

    ### Data Analysis
    Analyze COBOL data structures for ERD and database design.
    - `POST /dataanalysis` - Run data analysis on COBOL source
    - `GET /dataanalysis/{job_id}/status` - Check job status
    - `GET /dataanalysis/{job_id}/results` - Get results overview
    - `GET /dataanalysis/{job_id}/results/json/{filename}` - Get JSON artifact
    - `GET /dataanalysis/{job_id}/results/erd` - Get ERD directly
    - `GET /dataanalysis/{job_id}/results/lineage` - Get data lineage
    - `GET /dataanalysis/{job_id}/results/copybooks` - Get copybook analysis

    ### Discovery
    Executive-level analysis with ROI and migration roadmap.
    - `POST /discovery/analyze` - Run full discovery analysis
    - `POST /discovery/roi/calculate` - Calculate ROI with custom parameters
    - `GET /discovery/results/{job_id}` - Get discovery results
    - `GET /discovery/assumptions` - Get ROI assumptions and benchmarks

    ### Architecture Recommender
    Evidence-based AWS architecture recommendations.
    - `POST /architecture/analyze` - Run architecture analysis
    - `GET /architecture/{job_id}/status` - Check job status
    - `GET /architecture/{job_id}/results` - Get results overview
    - `GET /architecture/{job_id}/results/json/{filename}` - Get JSON artifact
    - `GET /architecture/{job_id}/results/iac` - Get IaC templates
    - `GET /architecture/{job_id}/results/iac/{filename}` - Get specific IaC file

    ### Files (Code Editor)
    File access for the Code Editor with COBOL (read-only) and Java (read/write).
    - `GET /files/{account}/{app}/cobol` - List COBOL source files
    - `GET /files/{account}/{app}/cobol/{path}` - Read COBOL file (read-only)
    - `GET /files/{account}/{app}/java` - List Java workspace files
    - `GET /files/{account}/{app}/java/{path}` - Read Java file
    - `POST /files/{account}/{app}/java/{path}` - Save Java file
    - `POST /files/{account}/{app}/workspace/reset` - Reset workspace from generated
    - `GET /files/{account}/{app}/workspace/status` - Get workspace status
    - `GET /files/{account}/{app}/sections` - Get COBOL-to-Java section mappings

    ### Java Packaging (Final Step)
    Package Java code into a production-ready Spring Boot application.
    - `POST /java-packaging/start` - Start packaging job
    - `GET /java-packaging/status/{job_id}` - Check job status
    - `GET /java-packaging/download/{job_id}` - Download ZIP package
    - `GET /java-packaging/validation/{job_id}` - Get validation report
    - `GET /java-packaging/jobs/{account}/{app}` - List jobs for an application

    ### Test Generation
    Generate JUnit tests for Java code.
    - `POST /test-generation/stubs` - Generate test stubs (no AI, fast)
    - `POST /test-generation/smart` - Generate smart tests (AI-powered)
    - `GET /test-generation/status/{job_id}` - Check job status
    - `GET /test-generation/results/{job_id}` - Get test results
    - `GET /test-generation/jobs/{account}/{app}` - List jobs for an application
    """,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ingest_router)
app.include_router(code_analysis_router)
app.include_router(code_refactor_router)
app.include_router(dependency_mapper_router)
app.include_router(monolith_identifier_router)
app.include_router(data_analysis_router)
app.include_router(discovery_router)
app.include_router(architecture_router)
app.include_router(credentials_router)
app.include_router(accounts_router)
app.include_router(mongodb_admin_router)
app.include_router(mcp_config_router)
app.include_router(files_router)
app.include_router(jobs_router)
app.include_router(flows_router)
app.include_router(ai_logs_router)
app.include_router(mcp_chat_router)
app.include_router(ai_flow_router)
app.include_router(storage_router)
app.include_router(ai_assistant_router)
app.include_router(java_packaging_router)
app.include_router(test_generation_router)
app.include_router(s3_router)
app.include_router(artifacts_router)


@app.get("/", tags=["health"])
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "modernizeit-api",
        "version": "0.1.0"
    }


@app.get("/health", tags=["health"])
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "service": "modernizeit-api",
        "version": "0.1.0",
        "flows": {
            "ingest": "available",
            "code_analysis": "available",
            "code_refactor": "available",
            "dependency_mapper": "available",
            "monolith_identifier": "available",
            "data_analysis": "available",
            "discovery": "available",
            "architecture": "available",
            "java_packaging": "available",
            "test_generation": "available"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
