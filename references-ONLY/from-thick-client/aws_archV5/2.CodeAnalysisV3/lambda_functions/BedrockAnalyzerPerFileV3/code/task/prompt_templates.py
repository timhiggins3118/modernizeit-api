"""
Prompt Templates Module

Purpose: AI analysis prompts for COBOL business logic extraction
Date: November 3, 2025
Version: V3.0
"""

import json


def build_program_level_prompt(file_analysis, user_context=None):
    """
    Build lightweight program-level analysis prompt

    Args:
        file_analysis: File analysis dictionary
        user_context: Optional user-provided context (from .md file)

    Returns:
        Prompt string
    """
    file_name = file_analysis.get('file_name', 'UNKNOWN')
    paragraph_count = file_analysis.get('paragraph_count', 0)
    total_lines = file_analysis.get('total_lines', 0)
    divisions = file_analysis.get('divisions', [])
    sections = file_analysis.get('sections', [])
    data_dict = file_analysis.get('data_dictionary', [])
    paragraphs = file_analysis.get('paragraphs', [])

    # Get top 20 data items
    top_data = data_dict[:20] if data_dict else []

    # Get first 50 paragraph names
    para_names = [p.get('name', 'UNKNOWN') for p in paragraphs[:50]]

    # Build user context section if provided
    context_section = ""
    if user_context:
        context_section = f"""
📋 USER-PROVIDED CONTEXT:
The user has provided the following context to assist with this analysis:

{user_context}

Use this context to better understand the business purpose, requirements, and modernization goals.
---
"""

    prompt = f"""You are a COBOL Business Logic Analyst specializing in extracting insights for Java modernization.
{context_section}
Analyze this COBOL program at a HIGH LEVEL:

**File:** {file_name}
**Total Paragraphs:** {paragraph_count}
**Total Lines:** {total_lines}

**Divisions:**
{json.dumps(divisions, indent=2)}

**Sections:**
{json.dumps(sections, indent=2)}

**Top 20 Data Items:**
{json.dumps(top_data, indent=2)}

**Paragraph Names (first 50):**
{json.dumps(para_names, indent=2)}

Provide a concise analysis (under 2000 tokens):

1. **Business Purpose:** What does this program do? What business problem does it solve?
2. **Main Data Flows:** What data does it read, write, or transform? What are the key data structures?
3. **Key Business Rules:** What are the core business rules implemented in this code?
4. **External Dependencies:** What files, databases, or external systems does it interact with?
5. **Modernization Complexity:** Assess the complexity for Java conversion (HIGH/MEDIUM/LOW) and explain why.

Return your analysis as JSON with this exact structure:

{{
  "business_purpose": "Detailed description...",
  "data_flows": "Description of data inputs/outputs/transformations...",
  "business_rules": ["Rule 1...", "Rule 2...", "Rule 3..."],
  "dependencies": ["FILE-INPUT", "DATABASE-TABLE", "EXTERNAL-SYSTEM"],
  "complexity": "HIGH|MEDIUM|LOW",
  "complexity_reasoning": "Explanation of complexity assessment...",
  "recommendations": "High-level modernization recommendations..."
}}

Return ONLY the JSON, no other text."""

    return prompt


def build_full_file_prompt(file_analysis, program_summary, user_context=None):
    """
    Build detailed full-file analysis prompt (for small files)

    Args:
        file_analysis: File analysis dictionary
        program_summary: Program-level summary from first analysis
        user_context: Optional user-provided context (from .md file)

    Returns:
        Prompt string
    """
    file_name = file_analysis.get('file_name', 'UNKNOWN')
    paragraph_count = file_analysis.get('paragraph_count', 0)
    paragraphs = file_analysis.get('paragraphs', [])

    # Build user context section if provided
    context_section = ""
    if user_context:
        context_section = f"""
📋 USER-PROVIDED CONTEXT:
{user_context}
---
"""

    prompt = f"""You are a COBOL Business Logic Analyst specializing in extracting insights for Java modernization.
{context_section}
PROGRAM CONTEXT (from previous high-level analysis):
{json.dumps(program_summary, indent=2)}

Now analyze ALL {paragraph_count} paragraphs in detail:

**File:** {file_name}

**Paragraphs:**
{json.dumps(paragraphs, indent=2)}

For EACH paragraph, provide:
1. **Business Logic:** What does this paragraph do? What business logic does it implement?
2. **Data Flow:** What data does it read/write/transform?
3. **Dependencies:** Which other paragraphs does it call (PERFORM statements)?
4. **Java Recommendations:** Specific recommendations for converting this paragraph to Java

⚠️ CRITICAL: Analyze EVERY paragraph. Do NOT truncate your output.

Return your analysis as JSON with this exact structure:

{{
  "paragraphs": [
    {{
      "name": "00000-MAIN-CONTROL",
      "business_logic": "Orchestrates main program flow...",
      "data_flow": "Reads INPUT-FILE, writes OUTPUT-FILE...",
      "dependencies": ["10000-INITIALIZE", "20000-PROCESS"],
      "java_recommendations": "Convert to main() method with dependency injection..."
    }}
  ]
}}

Return ONLY the JSON, no other text."""

    return prompt


def build_batch_prompt(batch_paragraphs, batch_num, total_batches, program_summary, user_context=None):
    """
    Build batch analysis prompt (for large files)

    Args:
        batch_paragraphs: List of paragraphs in this batch
        batch_num: Current batch number (1-indexed)
        total_batches: Total number of batches
        program_summary: Program-level summary
        user_context: Optional user-provided context (from .md file)

    Returns:
        Prompt string
    """
    # Build user context section if provided
    context_section = ""
    if user_context:
        context_section = f"""
📋 USER-PROVIDED CONTEXT:
{user_context}
---
"""

    prompt = f"""You are a COBOL Business Logic Analyst specializing in extracting insights for Java modernization.
{context_section}
PROGRAM CONTEXT (from previous high-level analysis):
{json.dumps(program_summary, indent=2)}

This is BATCH {batch_num} of {total_batches}.

Analyze these {len(batch_paragraphs)} paragraphs in detail:

**Paragraphs:**
{json.dumps(batch_paragraphs, indent=2)}

For EACH paragraph, provide:
1. **Business Logic:** What does this paragraph do? What business logic does it implement?
2. **Data Flow:** What data does it read/write/transform?
3. **Dependencies:** Which other paragraphs does it call (PERFORM statements)?
4. **Java Recommendations:** Specific recommendations for converting this paragraph to Java

Return your analysis as JSON with this exact structure:

{{
  "paragraphs": [
    {{
      "name": "PARAGRAPH-NAME",
      "business_logic": "...",
      "data_flow": "...",
      "dependencies": ["OTHER-PARAGRAPH"],
      "java_recommendations": "..."
    }}
  ]
}}

Return ONLY the JSON, no other text."""

    return prompt


def build_jcl_program_level_prompt(file_analysis, user_context=None):
    """
    Build lightweight JCL program-level analysis prompt

    Args:
        file_analysis: File analysis dictionary (from TreeSitter)
        user_context: Optional user-provided context (from .md file)

    Returns:
        Prompt string for JCL analysis
    """
    file_name = file_analysis.get('file_name', 'UNKNOWN')
    total_lines = file_analysis.get('total_lines', 0)
    raw_content = file_analysis.get('raw_content', '')

    # Build user context section if provided
    context_section = ""
    if user_context:
        context_section = f"""
📋 USER-PROVIDED CONTEXT:
The user has provided the following context to assist with this analysis:

{user_context}

Use this context to better understand the business purpose, requirements, and modernization goals.
---
"""

    # Build JCL content section
    jcl_content_section = ""
    if raw_content:
        jcl_content_section = f"""

**JCL CODE:**
```jcl
{raw_content}
```
"""
    else:
        jcl_content_section = "\n⚠️ WARNING: No JCL content provided - analysis will be limited.\n"

    prompt = f"""You are a JCL (Job Control Language) Business Logic Analyst specializing in extracting insights for modernization.
{context_section}
Analyze this JCL file at a HIGH LEVEL:

**File:** {file_name}
**Total Lines:** {total_lines}
{jcl_content_section}

JCL files orchestrate batch job execution on mainframe systems. They define:
- Job definitions (//JOBNAME JOB ...)
- Execution steps (//STEPNAME EXEC PGM=...)
- Data definitions (//DDNAME DD ...)
- Conditional logic (IF/THEN/ELSE, COND parameters)
- Procedure calls (EXEC PROC=...)

Provide a concise analysis (under 2000 tokens):

1. **Business Purpose:** What does this JCL job do? What business process does it orchestrate?
2. **Execution Flow:** What programs/procedures are executed and in what order?
3. **Data Flow:** What datasets/files are read, written, or transformed? Document all DD statements.
4. **Conditional Logic:** What conditional execution logic exists (IF/THEN/ELSE, COND codes)?
5. **Error Handling:** What error handling mechanisms are in place (ABEND handling, return code checking)?
6. **External Dependencies:** What external programs, datasets, or systems does it depend on?
7. **Modernization Complexity:** Assess the complexity for modernization (HIGH/MEDIUM/LOW) and explain why.

Return your analysis as JSON with this exact structure:

{{
  "business_purpose": "Detailed description of what this JCL job accomplishes...",
  "execution_flow": [
    {{"step_name": "STEP01", "program": "PGMNAME", "purpose": "What this step does..."}},
    {{"step_name": "STEP02", "proc": "PROCNAME", "purpose": "What this procedure does..."}}
  ],
  "data_flow": [
    {{"ddname": "INPUT01", "dataset": "DSN.NAME", "purpose": "Input data description..."}},
    {{"ddname": "OUTPUT01", "dataset": "DSN.OUTPUT", "purpose": "Output data description..."}}
  ],
  "conditional_logic": ["Description of IF/THEN/ELSE logic...", "COND parameter explanations..."],
  "error_handling": ["ABEND handling approach...", "Return code checking..."],
  "dependencies": ["Program: PGMNAME", "Dataset: DSN.NAME", "External System: XYZ"],
  "complexity": "HIGH|MEDIUM|LOW",
  "complexity_reasoning": "Explanation of complexity assessment...",
  "recommendations": "High-level modernization recommendations (e.g., convert to Apache Airflow, AWS Step Functions, etc.)..."
}}

Return ONLY the JSON, no other text."""

    return prompt


def build_generic_file_prompt(file_analysis, user_context=None):
    """
    Build generic analysis prompt for non-COBOL, non-JCL files (COPYBOOK, DCLGEN, etc.)

    Args:
        file_analysis: File analysis dictionary
        user_context: Optional user-provided context

    Returns:
        Prompt string
    """
    file_name = file_analysis.get('file_name', 'UNKNOWN')
    file_type = file_analysis.get('file_type', 'UNKNOWN')
    total_lines = file_analysis.get('total_lines', 0)
    raw_content = file_analysis.get('raw_content', '')

    # Build user context section if provided
    context_section = ""
    if user_context:
        context_section = f"""
📋 USER-PROVIDED CONTEXT:
{user_context}
---
"""

    # Build content section
    content_section = ""
    if raw_content:
        content_section = f"""

**FILE CONTENT:**
```
{raw_content}
```
"""
    else:
        content_section = "\n⚠️ WARNING: No file content provided - analysis will be limited.\n"

    prompt = f"""You are a Legacy Code Analyst specializing in extracting insights for modernization.
{context_section}
Analyze this file:

**File:** {file_name}
**File Type:** {file_type}
**Total Lines:** {total_lines}
{content_section}

Provide a concise analysis (under 2000 tokens):

1. **Purpose:** What is the purpose of this file? What role does it play in the application?
2. **Content:** What does this file contain? (e.g., data structures, database schemas, reusable code, etc.)
3. **Usage:** How is this file typically used? (e.g., included by programs, referenced by jobs, etc.)
4. **Dependencies:** What other files or systems does it depend on or reference?
5. **Modernization Approach:** How should this be handled during modernization?

Return your analysis as JSON with this exact structure:

{{
  "purpose": "Description of file purpose...",
  "content": "Description of what the file contains...",
  "usage": "How this file is used...",
  "dependencies": ["Referenced file 1", "Referenced file 2"],
  "modernization_approach": "Recommendations for handling this file during modernization...",
  "complexity": "HIGH|MEDIUM|LOW",
  "complexity_reasoning": "Explanation..."
}}

Return ONLY the JSON, no other text."""

    return prompt
