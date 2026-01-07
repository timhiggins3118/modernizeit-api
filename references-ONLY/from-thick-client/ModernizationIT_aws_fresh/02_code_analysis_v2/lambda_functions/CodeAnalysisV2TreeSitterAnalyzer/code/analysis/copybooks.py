# Minimal copybook expander: looks for COPY lines and tries to inline from a directory
import re, pathlib

COPY_RE = re.compile(r"^\s*COPY\s+([A-Z0-9-]+)(?:\s+OF\s+([A-Z0-9-]+))?\s*\.\s*$", re.IGNORECASE | re.MULTILINE)

def expand_copybooks(text: str, copybooks_dir: str | None):
    if not copybooks_dir:
        return None
    base = pathlib.Path(copybooks_dir)
    # naive expansion: replace "COPY NAME." with file contents if found
    def replace(m):
        name, of = m.group(1), m.group(2)
        candidates = [
            base / f"{name}.cpy",
            base / f"{name}.CPY",
            base / name
        ]
        for c in candidates:
            if c.exists():
                try:
                    return c.read_text(errors="replace")
                except Exception:
                    continue
        return m.group(0)  # leave as-is if missing
    expanded = COPY_RE.sub(replace, text)
    changed = (expanded != text)
    return {"expanded": changed, "text": expanded}
