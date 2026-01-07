import pathlib, os, json, time
from .ts_loader import get_cobol_language, Parser
from .extractors import extract_program_units, extract_symbols_and_segments, extract_dependencies
from .copybooks import expand_copybooks
from .cfg import build_cfg
from .dataflow import compute_def_use
from .smells import compute_smells
from .schema import make_document

COBOL_EXTS = (".cbl",".cob",".cobol")

def _read(p: pathlib.Path):
    try:
        return p.read_text(errors="replace")
    except Exception:
        return None

def analyze_path(path: pathlib.Path, copybooks_dir: str | None = None):
    lang = get_cobol_language()
    parser = Parser(); parser.set_language(lang)

    paths = [path] if path.is_file() else sorted([p for p in path.rglob("*") if p.suffix.lower() in COBOL_EXTS])
    files_out = []
    for p in paths:
        text = _read(p)
        if text is None:
            continue
        tree = parser.parse(text.encode("utf-8"))
        units = extract_program_units(tree, text)            # divisions, sections, paragraphs, ranges
        symbols = extract_symbols_and_segments(tree, text)   # working-storage items, pic/usage, etc.
        deps = extract_dependencies(tree, text)              # copybooks, files, calls, exec sql

        # Optional copybook expansion
        expanded = expand_copybooks(text, copybooks_dir) if copybooks_dir else None

        cfg = build_cfg(units, text)                         # paragraph graph from PERFORM/GO TO
        du = compute_def_use(units, text)                    # simple def/use from MOVE/COMPUTE
        smells = compute_smells(units, symbols, deps, cfg, du, text)

        files_out.append(make_document(
            source_path=str(p),
            text=text,
            units=units,
            symbols=symbols,
            deps=deps,
            cfg=cfg,
            du=du,
            smells=smells
        ))

    # Single-file = return document; multi-file wrap
    if len(files_out) == 1:
        return files_out[0]

    return {
        "schema_version": "2.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "files": files_out
    }
