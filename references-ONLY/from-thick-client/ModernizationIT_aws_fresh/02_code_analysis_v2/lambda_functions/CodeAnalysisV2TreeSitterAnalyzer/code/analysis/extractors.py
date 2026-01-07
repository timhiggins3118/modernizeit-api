# AST walkers and text slices to extract structure & symbols
import re

def _slice(text: str, start_byte: int, end_byte: int) -> str:
    # Tree-sitter byte indexes map to bytes; we assume utf-8 without multi-byte COBOL keywords.
    return text.encode('utf-8')[start_byte:end_byte].decode('utf-8', 'replace')

def extract_program_units(tree, text: str):
    # We don't rely on exact node names (grammar may vary). Instead, we map by keywords in text slices.
    root = tree.root_node
    ranges = []
    def walk(n):
        for c in n.children:
            walk(c)
            # Heuristic paragraph label: LINE with word + dot at eol
            # We also try to spot DIVISION headers
            start, end = c.start_byte, c.end_byte
            frag = _slice(text, start, min(end, start+200))
            if re.match(r"\s*[A-Z0-9-]+\.\s*$", frag.splitlines()[0] if frag.strip() else "", re.IGNORECASE):
                name = frag.splitlines()[0].strip().rstrip(".")
                ranges.append({"kind":"paragraph","name":name,"range":[start,end]})
            if re.search(r"\bIDENTIFICATION\s+DIVISION\b", frag, re.IGNORECASE):
                ranges.append({"kind":"division","name":"IDENTIFICATION","range":[start,end]})
            if re.search(r"\bENVIRONMENT\s+DIVISION\b", frag, re.IGNORECASE):
                ranges.append({"kind":"division","name":"ENVIRONMENT","range":[start,end]})
            if re.search(r"\bDATA\s+DIVISION\b", frag, re.IGNORECASE):
                ranges.append({"kind":"division","name":"DATA","range":[start,end]})
            if re.search(r"\bPROCEDURE\s+DIVISION\b", frag, re.IGNORECASE):
                ranges.append({"kind":"division","name":"PROCEDURE","range":[start,end]})
    walk(root)

    # Simple derived lists
    divisions = sorted({r["name"] for r in ranges if r["kind"] == "division"})
    paragraphs = [r for r in ranges if r["kind"] == "paragraph"]
    return {"divisions": divisions, "paragraphs": paragraphs}

def extract_symbols_and_segments(tree, text: str):
    # Slice DATA DIVISION and parse level items lines (01/02/77/88)
    # This is text-driven but scoped by AST-found DATA division ranges when possible.
    levels = []
    data_div_re = re.compile(r"\bDATA\s+DIVISION\b", re.IGNORECASE)
    # Find a rough DATA segment
    m = data_div_re.search(text)
    data_text = text[m.start():] if m else text
    # Level item pattern (simplified)
    pat = re.compile(r"^\s*(0[12578]|88)\s+([A-Z0-9-]+)(?:\s+REDEFINES\s+([A-Z0-9-]+))?\s+(?:PIC|PICTURE)\s+([A-Z0-9\(\)V\.\-]+)(?:\s+USAGE\s+([A-Z0-9-]+))?(?:\s+OCCURS\s+(\d+))?", re.IGNORECASE | re.MULTILINE)
    for m in pat.finditer(data_text):
        level, name, redefs, pic, usage, occurs = m.groups()
        levels.append({
            "level": int(level),
            "name": name,
            "pic": pic,
            "usage": usage,
            "redefines": redefs,
            "occurs": int(occurs) if occurs else None
        })
    return {"data_items": levels}

def extract_dependencies(tree, text: str):
    copybooks = re.findall(r"\bCOPY\s+([A-Z0-9-]+)(?:\s+OF\s+([A-Z0-9-]+))?", text, re.IGNORECASE)
    files = re.findall(r"\bSELECT\s+([A-Z0-9-]+)\b", text, re.IGNORECASE)
    calls = re.findall(r"\bCALL\s+['\"]([A-Z0-9_$-]+)['\"]", text, re.IGNORECASE)
    sqls  = re.findall(r"\bEXEC\s+SQL\b.*?\bEND-EXEC\b", text, re.IGNORECASE | re.DOTALL)
    return {
        "copybooks": [{"name": a, "of": b or None} for (a,b) in copybooks],
        "files": sorted(set(files)),
        "calls": sorted(set(calls)),
        "sql_count": len(sqls)
    }
