"""
Graph Generator for COBOL Analysis

Generates two views:
1. High-Level: Program → Copybooks → Files
2. Detailed: Paragraph call graph (PERFORM relationships)

Uses Graphviz DOT format for rendering.

Date: December 2025
"""

import json
from pathlib import Path


def generate_high_level_graph(reports_dir: Path, output_path: Path, base_name: str = None):
    """
    Generate high-level dependency graph.

    Shows: Program → Copybooks → Files

    Args:
        reports_dir: Directory containing JSON artifacts
        output_path: Output path for DOT/PNG files
        base_name: Base name of the program (e.g., 'ifpr321', 'cmcmcl00')
    """
    # Auto-detect base_name from file_model if not provided
    if not base_name:
        file_models = list(reports_dir.glob("*_file_model.json"))
        if file_models:
            base_name = file_models[0].stem.replace("_file_model", "")
        else:
            base_name = "program"

    program_name = base_name.upper()

    # Load cross reference
    cross_ref_path = reports_dir / "cross_reference.json"
    file_model_path = reports_dir / f"{base_name}_file_model.json"

    with open(cross_ref_path) as f:
        cross_ref = json.load(f)

    with open(file_model_path) as f:
        file_model = json.load(f)

    # Build DOT graph
    dot_lines = [
        'digraph HighLevelDependencies {',
        '    // Graph settings',
        '    rankdir=LR;',
        '    bgcolor="#1e1e1e";',
        '    pad=0.5;',
        '    nodesep=0.8;',
        '    ranksep=1.5;',
        '',
        '    // Node defaults',
        '    node [fontname="Arial", fontsize=11, style=filled];',
        '    edge [fontname="Arial", fontsize=9];',
        '',
        '    // Program node (center)',
        f'    {program_name} [label="{program_name}\\n(Main Program)", shape=box, fillcolor="#4a90d9", fontcolor=white, penwidth=2];',
        '',
        '    // Copybook nodes (left cluster)',
        '    subgraph cluster_copybooks {',
        '        label="Copybooks";',
        '        fontcolor=white;',
        '        color="#555555";',
        '        style=dashed;',
    ]

    # Add copybook nodes - get from copybook_usage (keys are copybook names)
    copybook_usage = cross_ref.get("copybook_usage", {})
    copybooks = list(copybook_usage.keys())[:15]  # Limit to 15 for readability
    for cb in copybooks:
        cb_name = cb.replace(".CBL", "").replace(".cbl", "")
        # Sanitize for DOT (replace hyphens)
        node_id = cb_name.replace("-", "_")
        dot_lines.append(f'        {node_id} [label="{cb_name}", shape=note, fillcolor="#6b8e23", fontcolor=white];')

    dot_lines.append('    }')
    dot_lines.append('')

    # File nodes (right cluster)
    dot_lines.append('    // File nodes (right cluster)')
    dot_lines.append('    subgraph cluster_files {')
    dot_lines.append('        label="Files / Tables";')
    dot_lines.append('        fontcolor=white;')
    dot_lines.append('        color="#555555";')
    dot_lines.append('        style=dashed;')

    # Add file nodes from SELECT statements
    select_stmts = file_model.get("select_statements", [])
    for stmt in select_stmts:
        file_name = stmt.get("file_name", "UNKNOWN")
        file_node_id = file_name.replace("-", "_")  # Sanitize for DOT
        dot_lines.append(f'        {file_node_id} [label="{file_name}", shape=cylinder, fillcolor="#d4a574", fontcolor=black];')

    dot_lines.append('    }')
    dot_lines.append('')

    # Edges: Program → Copybooks (dashed)
    dot_lines.append('    // COPY dependencies (dashed)')
    for cb in copybooks:
        cb_name = cb.replace(".CBL", "").replace(".cbl", "")
        node_id = cb_name.replace("-", "_")
        dot_lines.append(f'    {program_name} -> {node_id} [style=dashed, color="#6b8e23", label="COPY"];')

    dot_lines.append('')

    # Edges: Program → Files (solid)
    dot_lines.append('    // FILE access (solid)')
    for stmt in select_stmts:
        file_name = stmt.get("file_name", "UNKNOWN")
        file_node_id = file_name.replace("-", "_")  # Sanitize for DOT
        access = stmt.get("access_mode", "")
        dot_lines.append(f'    {program_name} -> {file_node_id} [color="#d4a574", label="{access}", penwidth=1.5];')

    dot_lines.append('}')

    # Write DOT file
    dot_content = '\n'.join(dot_lines)
    dot_path = output_path.with_suffix('.dot')
    with open(dot_path, 'w') as f:
        f.write(dot_content)

    print(f"High-level graph DOT: {dot_path}")
    return dot_path


def generate_detailed_graph(reports_dir: Path, output_path: Path, base_name: str = None, max_paragraphs: int = 50):
    """
    Generate detailed paragraph call graph.

    Shows: Only paragraphs involved in PERFORM relationships (callers + callees)

    Args:
        reports_dir: Directory containing JSON artifacts
        output_path: Output path for DOT/PNG files
        base_name: Base name of the program (e.g., 'ifpr321', 'cmcmcl00')
        max_paragraphs: Maximum paragraphs to include
    """
    # Auto-detect base_name from procedure_model if not provided
    if not base_name:
        proc_models = list(reports_dir.glob("*_procedure_model.json"))
        if proc_models:
            base_name = proc_models[0].stem.replace("_procedure_model", "")
        else:
            base_name = "program"

    # Load procedure model
    proc_model_path = reports_dir / f"{base_name}_procedure_model.json"

    with open(proc_model_path) as f:
        proc_model = json.load(f)

    paragraphs = proc_model.get("paragraphs", [])

    # Build paragraph lookup
    para_by_name = {p["name"]: p for p in paragraphs}
    para_names = set(para_by_name.keys())

    # Collect PERFORM relationships
    perform_edges = []
    callers = set()
    callees = set()

    for para in paragraphs:
        para_name = para["name"]
        for stmt in para.get("statements", []):
            if stmt.get("classification") == "PERFORM":
                semantic = stmt.get("semantic", {})
                target = semantic.get("target")
                if target and target in para_names:
                    perform_edges.append((para_name, target))
                    callers.add(para_name)
                    callees.add(target)

    # Only include paragraphs that are in call relationships
    relevant_paras = callers | callees
    print(f"   Found {len(relevant_paras)} paragraphs in call graph (from {len(paragraphs)} total)")

    # Build DOT graph - use hierarchical layout
    dot_lines = [
        'digraph ParagraphCallGraph {',
        '    // Graph settings - hierarchical',
        '    rankdir=TB;',
        '    bgcolor="#1e1e1e";',
        '    pad=0.5;',
        '    nodesep=0.5;',
        '    ranksep=0.8;',
        '    splines=true;',
        '',
        '    // Node defaults',
        '    node [fontname="Arial", fontsize=9, style=filled, shape=box];',
        '    edge [fontname="Arial", fontsize=8, color="#888888", arrowsize=0.7];',
        '',
    ]

    # Color map for different sections
    colors = {
        "0": "#e74c3c",  # Red - Main (000)
        "1": "#3498db",  # Blue - Init/Verify (100)
        "2": "#2ecc71",  # Green - Processing (200)
        "3": "#9b59b6",  # Purple - Calculations (300)
        "4": "#f39c12",  # Orange - Output (400)
        "5": "#1abc9c",  # Teal - Utilities (500)
    }

    # Add only relevant paragraph nodes
    for name in sorted(relevant_paras):
        para = para_by_name.get(name)
        if not para:
            continue

        # Get section color
        parts = name.split("-")
        prefix = parts[0][0] if parts and parts[0].isdigit() else "9"
        color = colors.get(prefix, "#95a5a6")

        # Sanitize name for DOT
        node_id = name.replace("-", "_")
        # Shorter display name
        display_name = name[:22] if len(name) > 22 else name

        # Make callers slightly larger
        if name in callers and name in callees:
            style = 'style="filled,bold"'
        elif name in callers:
            style = 'style=filled'
        else:
            style = 'style="filled,rounded"'

        dot_lines.append(f'    {node_id} [label="{display_name}", fillcolor="{color}", fontcolor=white, {style}];')

    dot_lines.append('')

    # Add PERFORM edges
    dot_lines.append('    // PERFORM relationships')
    added_edges = set()
    for src, tgt in perform_edges:
        src_id = src.replace("-", "_")
        tgt_id = tgt.replace("-", "_")
        edge_key = f"{src_id}_{tgt_id}"
        if edge_key not in added_edges:
            dot_lines.append(f'    {src_id} -> {tgt_id};')
            added_edges.add(edge_key)

    dot_lines.append('}')

    # Write DOT file
    dot_content = '\n'.join(dot_lines)
    dot_path = output_path.with_suffix('.dot')
    with open(dot_path, 'w') as f:
        f.write(dot_content)

    print(f"Detailed graph DOT: {dot_path}")
    return dot_path


def generate_summary_graph(reports_dir: Path, output_path: Path, base_name: str = None):
    """
    Generate summary call graph - top-level sections only.

    Shows: Main entry points and their direct calls (1 level deep)

    Args:
        reports_dir: Directory containing JSON artifacts
        output_path: Output path for DOT/PNG files
        base_name: Base name of the program (e.g., 'ifpr321', 'cmcmcl00')
    """
    # Auto-detect base_name from procedure_model if not provided
    if not base_name:
        proc_models = list(reports_dir.glob("*_procedure_model.json"))
        if proc_models:
            base_name = proc_models[0].stem.replace("_procedure_model", "")
        else:
            base_name = "program"

    proc_model_path = reports_dir / f"{base_name}_procedure_model.json"

    with open(proc_model_path) as f:
        proc_model = json.load(f)

    paragraphs = proc_model.get("paragraphs", [])
    para_by_name = {p["name"]: p for p in paragraphs}
    para_names = set(para_by_name.keys())

    # Find top-level paragraphs (000-xxx, 010-xxx, etc.)
    top_level = []
    for para in paragraphs:
        name = para["name"]
        parts = name.split("-")
        if parts and parts[0].isdigit():
            num = int(parts[0])
            if num < 100:  # 000-099 are top level
                top_level.append(name)

    # Collect direct calls from top-level paragraphs
    direct_calls = {}
    for name in top_level:
        para = para_by_name.get(name)
        if not para:
            continue
        calls = set()
        for stmt in para.get("statements", []):
            if stmt.get("classification") == "PERFORM":
                target = stmt.get("semantic", {}).get("target")
                if target and target in para_names:
                    calls.add(target)
        if calls:
            direct_calls[name] = calls

    # Build DOT
    dot_lines = [
        'digraph SummaryCallGraph {',
        '    rankdir=TB;',
        '    bgcolor="#1e1e1e";',
        '    pad=0.5;',
        '    nodesep=0.6;',
        '    ranksep=1.0;',
        '    splines=true;',
        '',
        '    node [fontname="Arial", fontsize=10, style=filled, shape=box];',
        '    edge [fontname="Arial", fontsize=8, color="#888888"];',
        '',
        '    // Top-level entry points',
    ]

    colors = {
        "0": "#e74c3c",  # Red
        "1": "#3498db",  # Blue
        "2": "#2ecc71",  # Green
        "3": "#9b59b6",  # Purple
        "4": "#f39c12",  # Orange
        "5": "#1abc9c",  # Teal
    }

    # Add top-level nodes
    for name in top_level:
        node_id = name.replace("-", "_")
        prefix = name.split("-")[0][0]
        color = colors.get(prefix, "#e74c3c")
        dot_lines.append(f'    {node_id} [label="{name}", fillcolor="{color}", fontcolor=white, penwidth=2];')

    dot_lines.append('')
    dot_lines.append('    // Called paragraphs (grouped by section)')

    # Collect all called paragraphs grouped by section
    all_called = set()
    for calls in direct_calls.values():
        all_called.update(calls)

    section_groups = {}
    for name in all_called:
        parts = name.split("-")
        if parts and parts[0].isdigit():
            section = parts[0][0] + "00"
        else:
            section = "OTHER"
        if section not in section_groups:
            section_groups[section] = []
        section_groups[section].append(name)

    # Add subgraphs for each section
    for section in sorted(section_groups.keys()):
        names = section_groups[section]
        prefix = section[0]
        color = colors.get(prefix, "#95a5a6")

        dot_lines.append(f'    subgraph cluster_{section} {{')
        dot_lines.append(f'        label="{section} Section";')
        dot_lines.append(f'        fontcolor=white;')
        dot_lines.append(f'        color="{color}";')
        dot_lines.append(f'        style=rounded;')

        for name in sorted(names)[:15]:  # Limit per section
            node_id = name.replace("-", "_")
            short_name = name[:18] if len(name) > 18 else name
            dot_lines.append(f'        {node_id} [label="{short_name}", fillcolor="{color}", fontcolor=white];')

        dot_lines.append('    }')
        dot_lines.append('')

    # Add edges
    dot_lines.append('    // PERFORM edges')
    for src, targets in direct_calls.items():
        src_id = src.replace("-", "_")
        for tgt in targets:
            tgt_id = tgt.replace("-", "_")
            dot_lines.append(f'    {src_id} -> {tgt_id};')

    dot_lines.append('}')

    dot_path = output_path.with_suffix('.dot')
    with open(dot_path, 'w') as f:
        f.write('\n'.join(dot_lines))

    print(f"Summary graph DOT: {dot_path}")
    return dot_path


def render_dot_to_png(dot_path: Path, engine: str = 'dot'):
    """Render DOT file to PNG using Graphviz."""
    import subprocess

    png_path = dot_path.with_suffix('.png')
    try:
        result = subprocess.run(
            [engine, '-Tpng', str(dot_path), '-o', str(png_path)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"Rendered PNG: {png_path}")
            return png_path
        else:
            print(f"Graphviz error: {result.stderr}")
            return None
    except FileNotFoundError:
        print(f"ERROR: Graphviz '{engine}' command not found. Install with: brew install graphviz")
        return None


if __name__ == "__main__":
    reports_dir = Path("reports")
    output_dir = Path("reports/graphs")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("COBOL Dependency Graph Generator")
    print("=" * 60)

    # Generate high-level graph (Program → Copybooks → Files)
    print("\n1. Generating High-Level Dependency Graph...")
    high_level_dot = generate_high_level_graph(
        reports_dir,
        output_dir / "ifpr321_high_level"
    )
    high_level_png = render_dot_to_png(high_level_dot)

    # Generate summary call graph (top-level → sections)
    print("\n2. Generating Summary Call Graph...")
    summary_dot = generate_summary_graph(
        reports_dir,
        output_dir / "ifpr321_summary"
    )
    summary_png = render_dot_to_png(summary_dot)

    # Generate detailed graph (all paragraphs in call relationships)
    print("\n3. Generating Detailed Paragraph Call Graph...")
    detailed_dot = generate_detailed_graph(
        reports_dir,
        output_dir / "ifpr321_detailed",
        max_paragraphs=300
    )
    # Use sfdp for large graphs - handles many nodes better
    detailed_png = render_dot_to_png(detailed_dot, engine='sfdp')

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    print(f"\n1. High-Level: {high_level_png or high_level_dot}")
    print(f"2. Summary:    {summary_png or summary_dot}")
    print(f"3. Detailed:   {detailed_png or detailed_dot}")
