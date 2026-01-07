# Assemble final document in the target schema
import time, re

def make_document(source_path: str, text: str, units, symbols, deps, cfg, du, smells):
    loc = len(text.splitlines())
    # Rough nesting estimate
    max_nesting = text.upper().count("IF") // 2
    program_id = _program_id(text)

    return {
        "schema_version": "2.0",
        "program_id": program_id,
        "source_path": source_path,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "structure": {
            "divisions": units.get("divisions", []),
            "paragraphs": [{"name": p["name"], "range": p["range"]} for p in units.get("paragraphs", [])],
            "copybooks": deps.get("copybooks", [])
        },
        "symbols": symbols,
        "io": {
            "files": [{"select": f} for f in deps.get("files", [])],
            "sql": deps.get("sql_count", 0)
        },
        "graphs": {
            "cfg": cfg,
            "calls": [{"from": program_id or "?", "to": c, "type":"CALL"} for c in deps.get("calls", [])]
        },
        "data_flow": du,
        "metrics": {
            "loc": loc,
            "cyclomatic": cfg.get("cyclomatic", 1),
            "max_nesting": max_nesting
        },
        "smells": smells,
        "recommendations": _recommendations(smells)
    }

def _program_id(text: str):
    m = re.search(r"\bPROGRAM-ID\.\s*([A-Z0-9_-]+)", text, re.IGNORECASE)
    return m.group(1) if m else None

def _recommendations(smells):
    recs = []
    for s in smells:
        if s["type"] == "MissingFileStatus":
            recs.append({"category":"I/O","action":"Add FILE STATUS checks for all SELECT/FD files"})
        if s["type"] == "MagicNumbers":
            recs.append({"category":"Refactor","action":"Replace magic numbers with named constants"})
    return recs
