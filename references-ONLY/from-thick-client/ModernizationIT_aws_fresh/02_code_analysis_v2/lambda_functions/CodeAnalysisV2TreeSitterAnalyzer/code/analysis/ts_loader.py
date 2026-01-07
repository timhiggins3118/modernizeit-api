import os, pathlib
from tree_sitter import Language, Parser

ROOT = pathlib.Path(__file__).resolve().parents[2]
LIB = os.environ.get("TS_COBOL_LIB", str(ROOT / "vendor" / "libtree-sitter-cobol.so"))
LANGS = os.environ.get("TS_LANGS", str(ROOT / "vendor" / "ts-langs.so"))

def get_cobol_language():
    if not os.path.exists(LIB):
        raise RuntimeError(f"Missing COBOL grammar shared library: {LIB}\n"
                           "Run: bash scripts/get_treesitter_cobol.sh")
    if not os.path.exists(LANGS):
        Language.build_library(LANGS, [str(ROOT / "vendor" / "tree-sitter-cobol")])
    return Language(LANGS, "COBOL")
