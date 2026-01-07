# Tree-Sitter Grammar Build Guide

**Last Updated:** January 7, 2026

## Overview

The ModernizeIT API uses tree-sitter for COBOL code parsing in the code analysis engine. The tree-sitter grammar must be compiled **on the target platform** because binary formats differ between operating systems:

- **macOS**: Mach-O binary format (.dylib or .so)
- **Linux**: ELF binary format (.so)
- **Windows**: PE format (.dll)

**CRITICAL:** You cannot copy a `.so` file compiled on macOS to Linux and expect it to work. You'll get "invalid ELF header" errors.

---

## Quick Start

When deploying to a new environment (EC2, Docker, different server), run:

```bash
cd /path/to/modernizeit-api
python3 build_tree_sitter_grammar.py
```

This will:
1. Find the tree-sitter-cobol source in `vendor/tree-sitter-cobol/`
2. Compile it using gcc
3. Output `engines/code_analysis/grammar/cobol.so`
4. Test that the grammar loads

---

## Prerequisites

### Required Files
- `vendor/tree-sitter-cobol/` - Source grammar (grammar.js, src/parser.c, src/scanner.c)
- `build_tree_sitter_grammar.py` - Build script

### Required Tools
- **gcc** - C compiler
- **Python 3.8+**
- **tree-sitter** Python package (in requirements.txt)

### Installing gcc

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install build-essential
```

**Amazon Linux/CentOS:**
```bash
sudo yum groupinstall "Development Tools"
```

**macOS:**
```bash
xcode-select --install
```

---

## Deployment Steps

### 1. Initial Deployment (New Environment)

```bash
# SSH into the server
ssh -i your-key.pem user@server-ip

# Navigate to project
cd /var/modernizeit/modernizeit-api

# Ensure source files exist
ls vendor/tree-sitter-cobol/src/parser.c  # Should exist
ls vendor/tree-sitter-cobol/src/scanner.c # Should exist

# Build the grammar
python3 build_tree_sitter_grammar.py

# Expected output:
# ============================================================
# BUILDING TREE-SITTER COBOL GRAMMAR
# ============================================================
#
# ✓ Found tree-sitter-cobol source: .../vendor/tree-sitter-cobol
# ✓ Output directory: .../engines/code_analysis/grammar
#
# 🔨 Building COBOL grammar with gcc...
#    Running: gcc -shared -fPIC -I.../src -o .../cobol.so .../parser.c .../scanner.c
#
# ✅ SUCCESS! Grammar built: .../cobol.so
#    File size: 13,411,984 bytes

# Verify the file exists
ls -lh engines/code_analysis/grammar/cobol.so

# Restart the API
sudo systemctl restart modernizeit-api
```

### 2. Code Updates (No Grammar Rebuild Needed)

If you're just updating Python code (not the grammar source), you don't need to rebuild:

```bash
rsync -avz --exclude='.venv' --exclude='__pycache__' \
  -e "ssh -i your-key.pem" \
  ./api ./engines ./config \
  user@server:/var/modernizeit/modernizeit-api/

ssh -i your-key.pem user@server \
  "sudo systemctl restart modernizeit-api"
```

### 3. Grammar Source Updates

If the tree-sitter-cobol source is updated (grammar.js changes):

```bash
# Upload new source
rsync -avz --exclude='.git' \
  -e "ssh -i your-key.pem" \
  ./vendor/tree-sitter-cobol \
  user@server:/var/modernizeit/modernizeit-api/vendor/

# Rebuild on server
ssh -i your-key.pem user@server \
  "cd /var/modernizeit/modernizeit-api && python3 build_tree_sitter_grammar.py"

# Restart API
ssh -i your-key.pem user@server \
  "sudo systemctl restart modernizeit-api"
```

---

## Troubleshooting

### Error: "invalid ELF header"

**Cause:** You copied a macOS-compiled `.so` file to Linux.

**Solution:** Rebuild on the target platform:
```bash
cd /var/modernizeit/modernizeit-api
rm engines/code_analysis/grammar/cobol.so  # Remove old macOS version
python3 build_tree_sitter_grammar.py        # Build Linux version
sudo systemctl restart modernizeit-api
```

### Error: "gcc: command not found"

**Cause:** C compiler not installed.

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# Amazon Linux/CentOS
sudo yum groupinstall "Development Tools"
```

### Error: "tree_sitter/parser.h: No such file or directory"

**Cause:** Missing source files or incorrect include path.

**Solution:** Verify source files exist:
```bash
ls vendor/tree-sitter-cobol/src/parser.c
ls vendor/tree-sitter-cobol/src/scanner.c
ls vendor/tree-sitter-cobol/src/tree_sitter/parser.h
```

If missing, re-upload the vendor directory.

### Error: "Failed to load COBOL grammar"

**Cause:** Grammar file corrupted or wrong architecture.

**Solution:** Rebuild the grammar and verify:
```bash
python3 build_tree_sitter_grammar.py
file engines/code_analysis/grammar/cobol.so
# Should show: ELF 64-bit LSB shared object, x86-64
```

---

## Docker Deployment

### Dockerfile Example

```dockerfile
FROM python:3.13-slim

# Install gcc for building tree-sitter grammar
RUN apt-get update && \
    apt-get install -y build-essential && \
    rm -rf /var/lib/apt/lists/*

# Copy application
COPY . /app
WORKDIR /app

# Install Python dependencies
RUN pip install -r requirements.txt

# Build tree-sitter grammar for this container
RUN python3 build_tree_sitter_grammar.py

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Multi-Stage Build (Recommended)

```dockerfile
# Stage 1: Build
FROM python:3.13-slim as builder
RUN apt-get update && apt-get install -y build-essential
COPY vendor /app/vendor
COPY build_tree_sitter_grammar.py /app/
WORKDIR /app
RUN python3 build_tree_sitter_grammar.py

# Stage 2: Runtime
FROM python:3.13-slim
COPY --from=builder /app/engines/code_analysis/grammar/cobol.so /app/engines/code_analysis/grammar/
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build and Deploy API

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install gcc
        run: sudo apt-get install -y build-essential

      - name: Build tree-sitter grammar
        run: python3 build_tree_sitter_grammar.py

      - name: Verify grammar
        run: |
          test -f engines/code_analysis/grammar/cobol.so
          file engines/code_analysis/grammar/cobol.so

      - name: Deploy to EC2
        run: |
          rsync -avz -e "ssh -i ${{ secrets.EC2_KEY }}" \
            --exclude='.git' --exclude='.venv' \
            . user@${{ secrets.EC2_HOST }}:/var/modernizeit/modernizeit-api/
```

---

## Architecture Notes

### Why Platform-Specific?

Tree-sitter grammars are compiled to **native machine code** as shared libraries:

- **Binary Format:** OS-specific (ELF vs Mach-O vs PE)
- **CPU Architecture:** x86_64, ARM64, etc.
- **ABI:** Calling conventions differ between platforms
- **System Libraries:** Linked against platform libc

### What Gets Compiled?

The tree-sitter-cobol grammar consists of:

1. **grammar.js** - Grammar definition (platform-independent)
2. **src/parser.c** - Generated parser code (~600KB)
3. **src/scanner.c** - Hand-written scanner code
4. **src/tree_sitter/parser.h** - Header file

The build process compiles `parser.c` and `scanner.c` into a single `.so` shared library.

### File Sizes

| Platform | File | Size |
|----------|------|------|
| macOS (Mach-O) | cobol.so | ~14.0 MB |
| Linux (ELF) | cobol.so | ~13.4 MB |
| Windows (PE) | cobol.dll | ~14.5 MB |

---

## Testing

### Verify Grammar Loads

```python
# Test script: test_grammar.py
from tree_sitter import Language
from pathlib import Path

grammar_path = Path("engines/code_analysis/grammar/cobol.so")
if not grammar_path.exists():
    print(f"❌ Grammar not found: {grammar_path}")
    exit(1)

try:
    lang = Language(str(grammar_path), 'cobol')
    print(f"✅ COBOL grammar loaded successfully")
    print(f"   Path: {grammar_path}")
    print(f"   Size: {grammar_path.stat().st_size:,} bytes")
except Exception as e:
    print(f"❌ Failed to load grammar: {e}")
    exit(1)
```

Run test:
```bash
python3 test_grammar.py
```

### Test Code Analysis API

```bash
# Trigger a code analysis job
curl -X POST http://localhost:8000/codeanalysis \
  -H "Content-Type: application/json" \
  -d '{
    "scout_account_id": "test",
    "application_name": "test-app",
    "source_hash": "test-hash",
    "automate_flow": false
  }'

# Check logs for tree-sitter usage
tail -f /var/log/modernizeit/api.log | grep -i "tree-sitter\|parsing"
```

---

## Reference

### Build Script Location
`build_tree_sitter_grammar.py`

### Grammar Source Location
`vendor/tree-sitter-cobol/`

### Compiled Output Location
`engines/code_analysis/grammar/cobol.so`

### Related Documentation
- `deployment_scripts/EC2_DEPLOYMENT.md` - Full EC2 deployment guide
- `engines/code_analysis/README.md` - Code analysis architecture
- Tree-sitter documentation: https://tree-sitter.github.io/

---

## Checklist for New Environment

- [ ] Install gcc/build tools
- [ ] Upload vendor/tree-sitter-cobol source
- [ ] Upload build_tree_sitter_grammar.py
- [ ] Run build script
- [ ] Verify cobol.so exists and is correct size (~13-14 MB)
- [ ] Test grammar loads with test script
- [ ] Start API and test code analysis endpoint
- [ ] Check logs for "Tree-sitter parsing" success

---

**Created:** January 7, 2026
**Author:** Claude (via deployment session)
**Last Build:** EC2 t3.medium, Ubuntu 24.04 LTS, gcc 11.4.0
