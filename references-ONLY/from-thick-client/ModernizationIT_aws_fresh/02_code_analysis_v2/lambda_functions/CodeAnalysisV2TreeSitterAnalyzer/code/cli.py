#!/usr/bin/env python3
import argparse, json, pathlib, sys
from analysis.run import analyze_path

def main():
    p = argparse.ArgumentParser(description="COBOL Tree‑Sitter Analyzer")
    p.add_argument("--source", required=True, help="COBOL file or directory")
    p.add_argument("--out", default="static_analysis.json", help="Output JSON path")
    p.add_argument("--copybooks", default=None, help="Optional copybook directory (for expansion)")
    args = p.parse_args()

    src = pathlib.Path(args.source)
    if not src.exists():
        print(f"Source not found: {src}", file=sys.stderr)
        sys.exit(2)

    result = analyze_path(src, copybooks_dir=args.copybooks)
    pathlib.Path(args.out).write_text(json.dumps(result, indent=2))
    print(f"✅ Wrote {args.out}")

if __name__ == "__main__":
    main()
