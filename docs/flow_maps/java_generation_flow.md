# Java Generation V4 Flow Map

## Overview

The Java Generation flow transforms COBOL code analysis outputs into a complete Spring Boot application. It runs 10 sequential Lambdas locally, each generating a portion of the final application.

## Execution Path

```
UI (workflow_panel.py)
    ↓
JavaGenerationWorkflowExecutor (workflow_executor.py)
    ↓
10 Sequential Lambdas:
    1. PrepareGenerationV3      → Read 7 flow outputs, create plan
    1.5 SurfacePlannerV3        → Classify programs by complexity
    2. ProjectSetupV3           → Create Maven structure
    3. EntityGeneratorV3        → Generate JPA entities
    4. ServiceGeneratorV3       → Generate Spring services
    5. RepositoryGeneratorV3    → Generate Spring Data repos
    6. APIGeneratorV3           → Generate REST controllers
    7. TestGeneratorV3          → Generate JUnit tests
    8. ValidateGeneratedCodeV3  → Validate with tree-sitter
    9. PackageResultsV3         → Create ZIP package
    10. GenerateFinalReportV3   → Generate final report
    ↓
Generated Spring Boot Application + Reports
```

## Key Files

### UI Entry Point
| File | Purpose |
|------|---------|
| `src/workflow/workflow_panel.py` | Main UI, triggers `_run_java_generation_v4_real()` |

### Workflow Orchestrator
| File | Purpose |
|------|---------|
| `src/workflow/java_generation_v4/workflow_executor.py` | `JavaGenerationWorkflowExecutor` - chains all Lambdas |

### Lambda Handlers (10 Steps)
| # | File | Purpose |
|---|------|---------|
| 1 | `lambdas/prepare_generation_v3.py` | Read upstream flows, create generation_plan.json |
| 1.5 | `lambdas/surface_planner_v3.py` | Classify programs (simple/complex) |
| 2 | `lambdas/project_setup_v3.py` | Create Maven project (pom.xml, Dockerfile) |
| 3 | `lambdas/entity_generator_v3.py` | Generate JPA entity classes |
| 4 | `lambdas/service_generator_v3.py` | Generate Spring service classes |
| 5 | `lambdas/repository_generator_v3.py` | Generate Spring Data repositories |
| 6 | `lambdas/api_generator_v3.py` | Generate REST controllers |
| 7 | `lambdas/test_generator_v3.py` | Generate JUnit 5 tests |
| 8 | `lambdas/validate_generated_code_v3.py` | Validate syntax (NO compilation) |
| 9 | `lambdas/package_results_v3.py` | Create downloadable ZIP |
| 10 | `lambdas/generate_final_report_v3.py` | Generate final report (JSON + MD) |

### Utility Modules
| File | Purpose |
|------|---------|
| `lambdas/java_naming_utils.py` | COBOL → Java naming conversion |
| `lambdas/cobol_entity_extractor.py` | Extract entities from copybooks |
| `lambdas/business_rules_processor.py` | Process business rules |
| `lambdas/control_flow_analyzer.py` | Analyze COBOL control flow |

### Jinja2 Templates
| File | Purpose |
|------|---------|
| `templates/entity_template.java.j2` | JPA entity template |
| `templates/service_simple_template.java.j2` | Simple service template |
| `templates/service_complex_template.java.j2` | Complex service with business logic |
| `templates/repository_template.java.j2` | Repository interface template |
| `templates/controller_template.java.j2` | REST controller template |
| `templates/service_test_template.java.j2` | JUnit test template |
| `templates/final_report_template.md.j2` | Report markdown template |

### Validation
| File | Purpose |
|------|---------|
| `validation/java_validator.py` | Tree-sitter based Java validation |

## Input Dependencies (7 Upstream Flows)

Lambda 1 (PrepareGenerationV3) reads outputs from:

1. **Discovery V2** → `business_processes.json`, `api_patterns.json`
2. **Data Analysis V2** → `erd.json` (Entity-Relationship Diagram)
3. **Code Analysis V3** → `static_analysis.json`
4. **Code Refactor V2** → `refactor_recipes.json`
5. **Dependency Mapper V2** → `microservice_boundaries.json`, `dependency_graph.json`
6. **Monolith Identifier V2** → `decomposition_strategy.json`
7. **Architecture Recommender V2** → `architecture_recommendations.json`

## Output Structure

```
{working_folder}/code-transformation-v2/{account}/{app}/java_generation_v4/jobs/{job_id}/
├── artifacts/
│   ├── ModernizedApplication/
│   │   ├── src/main/java/com/modernized/{app}/
│   │   │   ├── entities/           # JPA entities
│   │   │   ├── services/           # Spring services
│   │   │   ├── repositories/       # Spring Data repos
│   │   │   ├── controllers/        # REST controllers
│   │   │   ├── config/
│   │   │   └── Application.java
│   │   ├── src/main/resources/
│   │   │   └── application.yml
│   │   ├── src/test/java/
│   │   ├── pom.xml
│   │   ├── Dockerfile
│   │   ├── docker-compose.yml
│   │   └── README.md
│   └── {job_id}_ModernizedApplication.zip
├── reports/
│   ├── preparation_report.json
│   ├── project_setup_report.json
│   ├── entity_generation_report.json
│   ├── service_generation_report.json
│   ├── repository_generation_report.json
│   ├── api_generation_report.json
│   ├── test_generation_report.json
│   ├── validation_report.json
│   ├── package_report.json
│   ├── final_report.json
│   └── final_report.md
└── generation_plan.json
```

## Job ID Pattern
`jgv3_job_{account}_{app}_{timestamp}`

## Key Differences from Ingest Flow

| Aspect | Ingest | Java Generation |
|--------|--------|-----------------|
| Lambdas | 1 | 10 (sequential) |
| Input | ZIP file | 7 upstream flow outputs |
| Output | Catalogs, type mappings | Full Spring Boot app |
| AI Usage | None | Used in PrepareGeneration |
| Complexity | Simple extraction | Complex code generation |

## AWS Reference
- Step Functions: `references/aws_archV5/9.JavaGenerationV3/step_functions/JavaGenerationWorkflowV3.json`
- Lambda code: `references/aws_archV5/9.JavaGenerationV3/lambda_functions/*/code/`

## Notes for API Implementation

1. **No LocalLambdaExecutor needed** - The workflow_executor.py already handles local execution by importing modules directly
2. **Jinja2 templates** - Must be copied or referenced correctly
3. **Tree-sitter validation** - No Java compilation, just syntax checking
4. **Large flow** - Consider progress callbacks for UI updates
5. **Dependencies** - Requires upstream flow outputs to exist first
