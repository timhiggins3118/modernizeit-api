import re

def compute_smells(units, symbols, deps, cfg, du, text: str):
    smells = []

    # Magic numbers (rough)
    magic_count = len(re.findall(r"\b\d+\b", text))
    if magic_count > 0:
        smells.append({"type":"MagicNumbers","severity":"MEDIUM","count":magic_count})

    # Missing FILE STATUS if SELECT/FD present
    if (deps.get("files") and "FILE STATUS" not in text.upper()):
        smells.append({"type":"MissingFileStatus","severity":"HIGH","files":deps["files"]})

    # Unused paragraphs (defined but never target of edge, rough)
    para_names = {p["name"] for p in units.get("paragraphs", [])}
    targets = {e["to"] for e in cfg.get("edges", []) if e["edge"] in ("PERFORM","GOTO")}
    unused = sorted(list(para_names - targets))
    if unused:
        smells.append({"type":"UnusedParagraphs","severity":"LOW","count":len(unused),"paragraphs":unused[:20]})

    # Deep nesting (naive): count THEN/IF indentation depth via occurrences
    if_depth = text.upper().count("IF")
    if if_depth >= 10:
        smells.append({"type":"DeepNesting","severity":"MEDIUM","score":if_depth})

    # GO TO usage
    if re.search(r"\bGO\s+TO\b", text, re.IGNORECASE):
        smells.append({"type":"GotoUsage","severity":"LOW"})

    return smells
