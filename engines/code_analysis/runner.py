"""
Code Analysis Runner

Orchestrates the 11-step COBOL analysis pipeline.
Migrated from CLI main.py to work with API.

UPDATED: Added better logging and parallel graph generation.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config.settings import settings
from db.repositories.code_analysis_repo import save_artifact_sync


@dataclass
class CodeAnalysisResult:
    """Result of code analysis run."""
    success: bool
    job_id: str
    status: str
    artifacts_path: str
    main_program: Optional[str] = None
    base_name: Optional[str] = None
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


def run_code_analysis(
    source_path: str,
    output_dir: str,
    main_program: Optional[str] = None,
    generate_java: bool = True,
    generate_graphs: bool = True,
    account_id: Optional[str] = None,
    application: Optional[str] = None,
    save_to_mongodb: bool = True,
) -> CodeAnalysisResult:
    """
    Run the full COBOL analysis pipeline.

    Args:
        source_path: Path to extracted COBOL files (from ingest)
        output_dir: Where to write outputs (reports/, generated/)
        main_program: Optional main program name (auto-detect if not provided)
        generate_java: Whether to generate Java project
        generate_graphs: Whether to generate dependency graphs
        account_id: Customer account ID for MongoDB storage
        application: Application name for MongoDB storage
        save_to_mongodb: Whether to save artifacts to MongoDB (default: True)

    Returns:
        CodeAnalysisResult with job details and artifact paths
    """
    start_time = time.time()
    logs: List[str] = []

    def log(msg: str):
        logs.append(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}")
        print(msg)

    def save_to_mongo(program: str, artifact_type: str, data: dict, job_id: str):
        """Save artifact to MongoDB if enabled."""
        if not save_to_mongodb or not account_id or not application:
            return
        try:
            save_artifact_sync(
                account_id=account_id,
                application=application,
                program=program,
                artifact_type=artifact_type,
                job_id=job_id,
                data=data
            )
            log(f"  [MongoDB] Saved {program}/{artifact_type}")
        except Exception as e:
            log(f"  [MongoDB] WARNING: Failed to save {artifact_type}: {e}")

    # Generate job ID
    timestamp = int(time.time())
    job_id = f"ca_job_{timestamp}"

    try:
        source_dir = Path(source_path)
        output_path = Path(output_dir)

        if not source_dir.exists():
            raise ValueError(f"Source path not found: {source_path}")

        # Create output directories
        reports_dir = output_path / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        generated_dir = output_path / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)

        log(f"Source: {source_dir}")
        log(f"Reports: {reports_dir}")
        log(f"Generated: {generated_dir}")

        # Import parsers and generators
        from engines.code_analysis.parsers.comprehensive_parser import run_comprehensive_parse
        from engines.code_analysis.parsers.cobol_parse_export import export_cobol_parse_artifacts
        from engines.code_analysis.parsers.cobol_data_parser import parse_data_division
        from engines.code_analysis.parsers.cobol_data_extractor import extract_data_items
        from engines.code_analysis.parsers.cobol_procedure_parser import parse_procedure_division
        from engines.code_analysis.parsers.cobol_file_parser import parse_file_section
        from engines.code_analysis.utils.file_analyzer import find_cobol_files

        # Step 1-2: Find COBOL files
        log("[1/11] Scanning COBOL files...")
        extensions = ['.cbl', '.CBL', '.cob', '.COB']
        cobol_files = find_cobol_files(source_dir, extensions)
        log(f"  Found {len(cobol_files)} COBOL files")

        if not cobol_files:
            raise ValueError("No COBOL files found")

        # Detect main program
        main_prog_path, base_name = _detect_main_program(cobol_files, main_program)
        class_name = main_prog_path.stem
        log(f"  Main program: {main_prog_path.name}")

        # Step 3: Comprehensive parse
        log("[3/11] Running comprehensive parse (all programs + copybooks)...")
        try:
            comp_results = run_comprehensive_parse(source_dir, reports_dir)
            summary = comp_results['summary']
            log(f"  Programs: {summary['program_count']}, Copybooks: {summary['copybook_count']}")

            # Save comprehensive parse results to MongoDB (app-wide artifacts)
            save_to_mongo("_application", "comprehensive_parse_results", comp_results, job_id)
            save_to_mongo("_application", "unified_data_model", comp_results.get('unified_data_model', {}), job_id)
            save_to_mongo("_application", "cross_reference", comp_results.get('cross_reference', {}), job_id)
        except Exception as e:
            log(f"  WARNING: Comprehensive parse failed: {e}")
            comp_results = None

        # Step 4: Tree-sitter line inventory
        log(f"[4/11] Parsing {main_prog_path.name} with tree-sitter...")
        parse_result = export_cobol_parse_artifacts(main_prog_path, reports_dir, base_name)

        if not parse_result.get("found"):
            raise ValueError(f"Tree-sitter parsing failed: {parse_result.get('error')}")

        line_inventory_path = Path(parse_result['line_inventory_path'])
        line_stats = parse_result.get('line_inventory_stats', {})
        log(f"  Lines: {line_stats.get('source_lines', 0)} (zero-loss: {line_stats.get('zero_loss', False)})")

        # Save line inventory to MongoDB
        with open(line_inventory_path) as f:
            line_inventory_data = json.load(f)
        save_to_mongo(base_name.upper(), "line_inventory", line_inventory_data, job_id)

        # Step 5: Data Division model
        log("[5/11] Building DATA DIVISION semantic model...")
        data_model_path = reports_dir / f"{base_name}_data_model.json"
        data_result = parse_data_division(line_inventory_path, data_model_path)
        log(f"  Data items: {data_result['summary']['total_data_items']}")

        # Save data model to MongoDB
        with open(data_model_path) as f:
            data_model_data = json.load(f)
        save_to_mongo(base_name.upper(), "data_model", data_model_data, job_id)

        # Step 6: Complete data model (IBM ODM)
        log("[6/11] Building COMPLETE data model (IBM ODM mapping)...")
        complete_data_model_path = reports_dir / f"{base_name}_complete_data_model.json"
        complete_result = extract_data_items(line_inventory_path)
        with open(complete_data_model_path, 'w') as f:
            json.dump(complete_result, f, indent=2)
        log(f"  Groups: {len(complete_result['groups'])}, Fields: {len(complete_result['fields'])}")

        # Save complete data model to MongoDB
        save_to_mongo(base_name.upper(), "complete_data_model", complete_result, job_id)

        # Step 7: Procedure Division model
        log("[7/11] Building PROCEDURE DIVISION semantic model...")
        procedure_model_path = reports_dir / f"{base_name}_procedure_model.json"
        proc_result = parse_procedure_division(line_inventory_path, procedure_model_path)
        log(f"  Paragraphs: {proc_result['summary']['paragraph_count']}")

        # Step 7b: Expand copybook paragraphs into procedure model
        # COBOL COPY statements insert copybook content - we need to merge copybook paragraphs
        if comp_results:
            copybook_paragraphs_added = _merge_copybook_paragraphs(
                procedure_model_path, comp_results, log
            )
            if copybook_paragraphs_added > 0:
                log(f"  + {copybook_paragraphs_added} paragraphs merged from copybooks")
                # Update proc_result count
                proc_result['summary']['paragraph_count'] += copybook_paragraphs_added

        # Save procedure model to MongoDB
        with open(procedure_model_path) as f:
            procedure_model_data = json.load(f)
        save_to_mongo(base_name.upper(), "procedure_model", procedure_model_data, job_id)

        # Step 8: File Section model
        log("[8/11] Building FILE SECTION semantic model...")
        file_model_path = reports_dir / f"{base_name}_file_model.json"
        file_result = parse_file_section(line_inventory_path, file_model_path)
        log(f"  Files: {file_result['summary']['select_count']}")

        # Save file model to MongoDB
        with open(file_model_path) as f:
            file_model_data = json.load(f)
        save_to_mongo(base_name.upper(), "file_model", file_model_data, job_id)

        # Load line inventory for generators
        with open(line_inventory_path) as f:
            line_inventory = json.load(f)['lines']

        # Step 9: Hybrid Java (alternate output)
        log("[9/11] Generating HYBRID Java (libcobj - alternate output)...")
        try:
            from engines.code_analysis.generators.java_generator_clean import load_models as load_hybrid_models
            # Skip hybrid for now - it's alternate output
            log("  Skipped (alternate output - use clean generator)")
        except Exception as e:
            log(f"  WARNING: Hybrid generator skipped: {e}")

        # Step 10: Maven project with clean Java
        java_lines = 0
        if generate_java:
            log(f"[10/11] Generating COMPLETE Maven project for {class_name}...")
            try:
                from engines.code_analysis.generators.java_generator_clean import (
                    CleanJavaGenerator,
                    load_models as load_clean_models
                )
                from engines.code_analysis.generators.project_template_generator import generate_project_from_java

                data_model, procedure_model = load_clean_models(reports_dir, base_name)
                clean_generator = CleanJavaGenerator(data_model, procedure_model, class_name)
                clean_output = clean_generator.generate()
                java_content = '\n'.join(clean_output)
                java_lines = len(clean_output)

                stats = {
                    'cobol_lines': len(line_inventory),
                    'java_lines': java_lines,
                    'paragraph_count': len(procedure_model.get('paragraphs', [])),
                    'field_count': len(data_model.get('fields', []))
                }

                project_result = generate_project_from_java(
                    output_dir=generated_dir,
                    java_content=java_content,
                    cobol_program=main_prog_path.name,
                    stats=stats
                )
                log(f"  Project: {project_result['project_dir']}")
                log(f"  Java lines: {java_lines}")
            except Exception as e:
                log(f"  WARNING: Java generation failed: {e}")
                import traceback
                traceback.print_exc()
        else:
            log("[10/11] Skipped Java generation (disabled)")

        # Step 11: Graphs (parallel generation)
        graphs_generated = []
        if generate_graphs:
            log("[11/11] Generating dependency graphs (parallel)...")
            try:
                from engines.code_analysis.generators.graph_generator import (
                    generate_high_level_graph,
                    generate_summary_graph,
                    generate_detailed_graph,
                    render_dot_to_png
                )

                graphs_dir = reports_dir / "graphs"
                graphs_dir.mkdir(parents=True, exist_ok=True)

                # Define graph generation tasks
                graph_tasks = [
                    ("high_level", generate_high_level_graph, graphs_dir / f"{base_name}_high_level", None),
                    ("summary", generate_summary_graph, graphs_dir / f"{base_name}_summary", None),
                    ("detailed", generate_detailed_graph, graphs_dir / f"{base_name}_detailed", 'sfdp'),
                ]

                def generate_graph(task):
                    """Generate a single graph."""
                    name, gen_fn, output_path, engine = task
                    dot_file = gen_fn(reports_dir, output_path, base_name)
                    png_file = render_dot_to_png(dot_file, engine=engine) if engine else render_dot_to_png(dot_file)
                    return name, png_file

                # Generate graphs in parallel
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {executor.submit(generate_graph, task): task[0] for task in graph_tasks}

                    for future in as_completed(futures):
                        graph_name = futures[future]
                        try:
                            name, png_file = future.result()
                            if png_file:
                                graphs_generated.append(png_file.name)
                                log(f"  Graph '{name}' generated: {png_file.name}")
                        except Exception as e:
                            log(f"  WARNING: Graph '{graph_name}' failed: {e}")

                log(f"  Generated {len(graphs_generated)} graphs total")
            except Exception as e:
                log(f"  WARNING: Graph generation failed: {e}")
        else:
            log("[11/11] Skipped graph generation (disabled)")

        # Build result
        duration_ms = int((time.time() - start_time) * 1000)

        # Collect JSON artifacts
        json_artifacts = []
        for f in reports_dir.glob("*.json"):
            json_artifacts.append(f.name)

        result = CodeAnalysisResult(
            success=True,
            job_id=job_id,
            status="completed",
            artifacts_path=str(output_path),
            main_program=main_prog_path.name,
            base_name=base_name,
            logs=logs,
            duration_ms=duration_ms,
            summary={
                "source_lines": line_stats.get('source_lines', 0),
                "data_items": data_result['summary']['total_data_items'],
                "paragraphs": proc_result['summary']['paragraph_count'],
                "files_analyzed": len(cobol_files),
                "java_lines": java_lines,
                "zero_loss": line_stats.get('zero_loss', False),
            },
            artifacts={
                "json": sorted(json_artifacts),
                "graphs": graphs_generated,
                "java_project": f"generated/{base_name}_cbl/" if generate_java else None,
            }
        )

        log(f"Analysis complete in {duration_ms}ms")
        return result

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

        return CodeAnalysisResult(
            success=False,
            job_id=job_id,
            status="failed",
            artifacts_path=str(output_dir),
            error=str(e),
            logs=logs,
            duration_ms=duration_ms,
        )


def _detect_main_program(
    cobol_files: List[Path],
    main_program: Optional[str] = None
) -> tuple:
    """
    Detect or validate the main COBOL program.

    Args:
        cobol_files: List of COBOL file paths
        main_program: Optional specific program name

    Returns:
        Tuple of (program_path, base_name)
    """
    if main_program:
        # Find specified program
        for f in cobol_files:
            if f.name.lower() == main_program.lower():
                return f, f.stem.lower()
        raise ValueError(f"Specified main program not found: {main_program}")

    # Auto-detect: filter to main programs (not copybooks)
    program_extensions = {'.cbl', '.CBL', '.cob', '.COB'}
    copybook_patterns = {'CPY', 'COPY', 'cpy', 'copy'}

    programs = []
    for f in cobol_files:
        if any(pat in f.name for pat in copybook_patterns):
            continue
        if f.suffix in program_extensions:
            programs.append(f)

    if not programs:
        programs = cobol_files

    if not programs:
        raise ValueError("No COBOL program files found")

    # Choose largest file as main program
    main_prog = max(programs, key=lambda f: f.stat().st_size)
    return main_prog, main_prog.stem.lower()


def _merge_copybook_paragraphs(
    procedure_model_path: Path,
    comp_results: Dict[str, Any],
    log: Callable
) -> int:
    """
    Merge copybook paragraphs into the procedure model.

    COBOL COPY statements insert copybook content at that location.
    Copybooks can contain PROCEDURE DIVISION paragraphs that need to be
    included in the main program's procedure model.

    This function:
    1. Finds copybooks that contain paragraphs (procedure division code)
    2. Parses those paragraphs using the same parser as the main program
    3. Merges them into the procedure model

    NO HARDCODING - dynamically discovers copybook paragraphs from uploaded files.

    Args:
        procedure_model_path: Path to the procedure_model.json file
        comp_results: Results from comprehensive_parser
        log: Logging function

    Returns:
        Number of paragraphs added from copybooks
    """
    # Load the procedure model
    with open(procedure_model_path) as f:
        procedure_model = json.load(f)

    # Get copybooks from comprehensive parse results
    copybooks = comp_results.get('copybooks', {})
    if not copybooks:
        return 0

    paragraphs_added = 0
    existing_para_names = {
        p.get('name', '').upper()
        for p in procedure_model.get('paragraphs', [])
    }

    # Also track in control_flow
    if 'control_flow' not in procedure_model:
        procedure_model['control_flow'] = {}
    if 'perform_targets' not in procedure_model['control_flow']:
        procedure_model['control_flow']['perform_targets'] = {}
    if 'goto_targets' not in procedure_model['control_flow']:
        procedure_model['control_flow']['goto_targets'] = {}

    perform_targets = procedure_model['control_flow']['perform_targets']
    goto_targets = procedure_model['control_flow']['goto_targets']

    # Find copybooks that have procedure division paragraphs
    for copybook_name, copybook_data in copybooks.items():
        copybook_paragraphs = copybook_data.get('paragraphs', [])

        if not copybook_paragraphs:
            continue

        # This copybook has paragraphs - it contains procedure division code
        log(f"    Copybook {copybook_name}: {len(copybook_paragraphs)} paragraphs")

        # Read the copybook file and parse its procedure division content
        copybook_path = copybook_data.get('file_path')
        if not copybook_path or not Path(copybook_path).exists():
            log(f"    WARNING: Copybook file not found: {copybook_path}")
            continue

        # Parse the copybook's procedure division content
        try:
            parsed_paragraphs = _parse_copybook_procedure(
                Path(copybook_path),
                copybook_name,
                log
            )

            for para in parsed_paragraphs:
                para_name = para.get('name', '').upper()

                # Skip if already exists in main program
                if para_name in existing_para_names:
                    continue

                # Skip EXIT paragraphs - they're just markers
                if 'EXIT' in para_name and para.get('is_exit', False):
                    continue

                # Add to procedure model
                procedure_model['paragraphs'].append(para)
                existing_para_names.add(para_name)
                paragraphs_added += 1

                # Update control flow - these paragraphs are now available
                if para_name in perform_targets:
                    perform_targets[para_name]['from_copybook'] = copybook_name
                if para_name in goto_targets:
                    goto_targets[para_name]['from_copybook'] = copybook_name

        except Exception as e:
            log(f"    WARNING: Failed to parse copybook {copybook_name}: {e}")
            continue

    # Save updated procedure model
    if paragraphs_added > 0:
        with open(procedure_model_path, 'w') as f:
            json.dump(procedure_model, f, indent=2)

    return paragraphs_added


def _parse_copybook_procedure(
    copybook_path: Path,
    copybook_name: str,
    log: Callable
) -> List[Dict]:
    """
    Parse procedure division content from a copybook.

    Args:
        copybook_path: Path to the copybook file
        copybook_name: Name of the copybook for logging
        log: Logging function

    Returns:
        List of paragraph dictionaries with statements
    """
    import re

    # Read copybook content
    content = copybook_path.read_text(encoding='latin-1', errors='replace')
    lines = content.splitlines()

    paragraphs = []
    current_para = None

    for i, line in enumerate(lines, 1):
        # Skip comment lines
        if len(line) > 6 and line[6] == '*':
            continue

        # Skip lines that are too short
        if len(line) < 8:
            continue

        # Get content area (columns 8-72)
        content_area = line[7:72] if len(line) > 7 else ''
        content_stripped = content_area.strip()

        if not content_stripped:
            continue

        # Check for paragraph header (name ending with period at start of content area)
        # Paragraph: starts in column 8, name followed by period
        para_match = re.match(r'^([A-Z0-9][-A-Z0-9]*)\s*\.\s*$', content_stripped, re.IGNORECASE)

        if para_match:
            para_name = para_match.group(1).upper()

            # Check if this is an EXIT paragraph
            is_exit = 'EXIT' in para_name

            # Save current paragraph if exists
            if current_para:
                paragraphs.append(current_para)

            # Start new paragraph
            current_para = {
                'name': para_name,
                'line_num': i,
                'is_exit': is_exit,
                'statements': [],
                'from_copybook': copybook_name
            }
            continue

        # If we're in a paragraph, collect statements
        if current_para:
            # Parse statement semantics (simplified for copybook content)
            statement = _parse_copybook_statement(content_stripped, i)
            if statement:
                current_para['statements'].append(statement)

    # Don't forget last paragraph
    if current_para:
        paragraphs.append(current_para)

    return paragraphs


def _parse_copybook_statement(content: str, line_num: int) -> Optional[Dict]:
    """
    Parse a single COBOL statement from copybook content.

    Args:
        content: The statement content (stripped)
        line_num: Line number in copybook

    Returns:
        Statement dictionary or None if not a meaningful statement
    """
    import re

    content_upper = content.upper()

    # Skip pure comments
    if content.startswith('*'):
        return None

    # Determine statement type and extract semantics
    statement = {
        'line_num': line_num,
        'raw_text': content,
        'classification': 'CODE',
        'semantic': None
    }

    # MOVE statement
    if content_upper.startswith('MOVE '):
        match = re.match(r'MOVE\s+(.+?)\s+TO\s+(.+?)\.?\s*$', content, re.IGNORECASE)
        if match:
            statement['classification'] = 'MOVE'
            statement['semantic'] = {
                'type': 'MOVE',
                'source': match.group(1).strip(),
                'target': match.group(2).strip()
            }

    # PERFORM statement
    elif content_upper.startswith('PERFORM '):
        match = re.match(r'PERFORM\s+([A-Z0-9][-A-Z0-9]*)', content, re.IGNORECASE)
        if match:
            statement['classification'] = 'PERFORM'
            statement['semantic'] = {
                'type': 'PERFORM',
                'target': match.group(1).upper()
            }

    # GO TO statement
    elif 'GO TO ' in content_upper or content_upper.startswith('GO '):
        match = re.search(r'GO\s+TO\s+([A-Z0-9][-A-Z0-9]*)', content, re.IGNORECASE)
        if match:
            statement['classification'] = 'GOTO'
            statement['semantic'] = {
                'type': 'GOTO',
                'target': match.group(1).upper()
            }

    # IF statement
    elif content_upper.startswith('IF '):
        statement['classification'] = 'IF'
        statement['semantic'] = {'type': 'IF', 'condition': content[3:].strip()}

    # INITIALIZE statement
    elif content_upper.startswith('INITIALIZE '):
        match = re.match(r'INITIALIZE\s+([A-Z0-9][-A-Z0-9]*)', content, re.IGNORECASE)
        if match:
            statement['classification'] = 'INITIALIZE'
            statement['semantic'] = {
                'type': 'INITIALIZE',
                'target': match.group(1).upper()
            }

    # ADD statement
    elif content_upper.startswith('ADD '):
        statement['classification'] = 'ARITHMETIC'
        statement['semantic'] = {'type': 'ADD', 'expression': content}

    # READ statement
    elif content_upper.startswith('READ '):
        match = re.match(r'READ\s+([A-Z0-9][-A-Z0-9]*)', content, re.IGNORECASE)
        if match:
            statement['classification'] = 'IO'
            statement['semantic'] = {
                'type': 'READ',
                'file': match.group(1).upper()
            }

    # START statement
    elif content_upper.startswith('START '):
        match = re.match(r'START\s+([A-Z0-9][-A-Z0-9]*)', content, re.IGNORECASE)
        if match:
            statement['classification'] = 'IO'
            statement['semantic'] = {
                'type': 'START',
                'file': match.group(1).upper()
            }

    return statement
