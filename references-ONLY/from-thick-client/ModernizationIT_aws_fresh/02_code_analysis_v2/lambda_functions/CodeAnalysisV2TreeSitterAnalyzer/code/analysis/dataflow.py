# Basic Def-Use via MOVE/COMPUTE within paragraphs
import re

MOVE_RE = re.compile(r"\bMOVE\s+(.+?)\s+TO\s+([A-Z0-9-]+)\b", re.IGNORECASE)
COMP_RE = re.compile(r"\bCOMPUTE\s+([A-Z0-9-]+)\s*=\s*(.+?)\.", re.IGNORECASE)

def compute_def_use(units, text: str):
    defs = {}
    uses = {}

    paras = units.get("paragraphs", [])
    # Build paragraph ranges to scope scans (optional, we use full text heuristics for now)
    for p in paras:
        name = p["name"]
        defs[name] = set()
        uses[name] = set()

    # Scan moves
    for m in MOVE_RE.finditer(text):
        src, dst = m.group(1), m.group(2)
        para = _enclosing_para(text, m.start())
        if para and para in defs:
            defs[para].add(dst)
            for tok in _vars_in_expr(src):
                uses[para].add(tok)

    for m in COMP_RE.finditer(text):
        dst, expr = m.group(1), m.group(2)
        para = _enclosing_para(text, m.start())
        if para and para in defs:
            defs[para].add(dst)
            for tok in _vars_in_expr(expr):
                uses[para].add(tok)

    # Flatten
    return {
        "by_paragraph": [
            {"paragraph": k, "defs": sorted(v), "uses": sorted(uses.get(k, set()))} for k, v in defs.items()
        ]
    }

def _vars_in_expr(expr: str):
    # Pull out variable-like tokens
    return re.findall(r"\b([A-Z][A-Z0-9-]+)\b", expr.upper())

def _enclosing_para(text: str, pos: int):
    import re as _re
    pre = text[:pos].splitlines()
    for line in reversed(pre):
        m = _re.match(r"\s*([A-Z0-9-]+)\.\s*$", line, _re.IGNORECASE)
        if m:
            return m.group(1)
    return None
