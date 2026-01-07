# Build a paragraph-level control-flow graph from PROCEDURE DIVISION
import re, itertools

def build_cfg(units, text: str):
    paras = [p["name"] for p in units.get("paragraphs", [])]
    edges = []

    # PERFORM para
    for m in re.finditer(r"\bPERFORM\s+([A-Z0-9-]+)\b", text, re.IGNORECASE):
        tgt = m.group(1)
        # Find current paragraph by nearest preceding label
        cur = _find_enclosing_paragraph(text, m.start())
        if cur and tgt in paras:
            edges.append((cur, tgt, "PERFORM"))

    # GO TO para
    for m in re.finditer(r"\bGO\s+TO\s+([A-Z0-9-]+)\b", text, re.IGNORECASE):
        tgt = m.group(1)
        cur = _find_enclosing_paragraph(text, m.start())
        if cur and tgt in paras:
            edges.append((cur, tgt, "GOTO"))

    # Simple fallthrough: connect paragraph i to i+1 if no explicit transfer detected (heuristic)
    for a, b in itertools.pairwise(paras):
        edges.append((a, b, "FALLTHROUGH"))

    # Compute cyclomatic = E - N + 2 (approx)
    N = len(set(paras))
    E = len(edges)
    cyclomatic = max(1, E - N + 2)

    return {
        "paragraphs": paras,
        "edges": [{"from":a,"to":b,"edge":k} for (a,b,k) in edges],
        "cyclomatic": cyclomatic
    }

def _find_enclosing_paragraph(text: str, pos: int):
    # Walk backwards to find a line that looks like a paragraph label (NAME.)
    pre = text[:pos].splitlines()
    for line in reversed(pre):
        if re.match(r"\s*([A-Z0-9-]+)\.\s*$", line, re.IGNORECASE):
            return re.match(r"\s*([A-Z0-9-]+)\.\s*$", line, re.IGNORECASE).group(1)
    return None
