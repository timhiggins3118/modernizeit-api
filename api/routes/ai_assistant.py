"""
AI Assistant API Routes

Provides a conversational AI interface that is context-aware.
Knows about the project, can read generated code, and answer questions.

Uses the same BedrockAgent pattern as all other AI features in the codebase.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config.settings import settings
from services.storage import storage_service
from engines.ai.bedrock_agent import BedrockAgent

router = APIRouter(prefix="/ai", tags=["ai-assistant"])


class AssistantRequest(BaseModel):
    message: str
    scout_account_id: str
    application_name: str
    context: Optional[Dict[str, Any]] = None


class AssistantResponse(BaseModel):
    response: str
    files_referenced: List[str] = []


def _find_java_files(account: str, app: str) -> List[Dict[str, str]]:
    """
    Find generated Java files for the project.
    Looks in: {account}/{app}/code_analysis/generated/{project}/
    Searches recursively to find Java files in src/main/java/...
    """
    generated_path = f"{account}/{app}/code_analysis/generated"
    print(f"[ai_assistant] Looking for Java files in: {generated_path}")

    if not storage_service.directory_exists(generated_path):
        print(f"[ai_assistant] Generated path does not exist")
        return []

    # Find project directories
    project_dirs = storage_service.list_directories(generated_path)
    print(f"[ai_assistant] Found project dirs: {project_dirs}")

    if not project_dirs:
        return []

    # Use the first project directory
    project_path = f"{generated_path}/{project_dirs[0]}"

    # List Java files recursively (they're in src/main/java/...)
    java_files = storage_service.list_files(project_path, pattern="*.java", recursive=True)
    print(f"[ai_assistant] Found Java files: {java_files}")

    # Read content of each file (limit to first 3 to avoid token limits)
    files = []
    max_content_chars = 15000  # Limit content per file to avoid exceeding model context

    for filepath in java_files[:3]:
        # filepath is already relative to project_path
        full_path = f"{project_path}/{filepath}"
        filename = filepath.split("/")[-1]  # Get just the filename
        try:
            content = storage_service.read_file(full_path)
            # Truncate if too long
            if len(content) > max_content_chars:
                content = content[:max_content_chars] + f"\n\n... [truncated - {len(content)} total chars]"
            files.append({
                "name": filename,
                "path": full_path,
                "content": content
            })
        except Exception as e:
            print(f"[ai_assistant] Error reading {filepath}: {e}")

    return files


def _find_cobol_files(account: str, app: str) -> List[Dict[str, str]]:
    """
    Find source COBOL files for the project.
    """
    # Find the source hash from latest.json
    latest_path = f"{account}/{app}/shared/uploads/latest.json"

    source_hash = None
    try:
        import json
        content = storage_service.read_file(latest_path)
        data = json.loads(content)
        source_hash = data.get("source_hash")
    except Exception:
        # Try to find any hash folder
        uploads_path = f"{account}/{app}/shared/uploads"
        if storage_service.directory_exists(uploads_path):
            dirs = storage_service.list_directories(uploads_path)
            for d in dirs:
                if len(d) == 64:  # SHA256 hash
                    source_hash = d
                    break

    if not source_hash:
        return []

    cobol_path = f"{account}/{app}/shared/uploads/{source_hash}/extracted/COBOLSource/Cobol"

    if not storage_service.directory_exists(cobol_path):
        return []

    cobol_files = storage_service.list_files(cobol_path, pattern="*.CBL", recursive=False)

    files = []
    for filename in cobol_files[:3]:  # Limit to 3 files
        file_path = f"{cobol_path}/{filename}"
        try:
            content = storage_service.read_file(file_path)
            files.append({
                "name": filename,
                "path": file_path,
                "content": content[:10000]  # Truncate large files
            })
        except Exception as e:
            print(f"[ai_assistant] Error reading COBOL {filename}: {e}")

    return files


@router.post("/assistant", response_model=AssistantResponse)
async def chat_with_assistant(request: AssistantRequest) -> AssistantResponse:
    """
    Chat with the AI assistant. The assistant is context-aware and knows about:
    - The current project (account/app)
    - Generated Java code (from code analysis)
    - Source COBOL code
    - Execution results from workflow nodes
    """
    print(f"[ai_assistant] Request: {request.message[:100]}...")
    print(f"[ai_assistant] Project: {request.scout_account_id}/{request.application_name}")

    # Load code context
    java_files = _find_java_files(request.scout_account_id, request.application_name)
    cobol_files = _find_cobol_files(request.scout_account_id, request.application_name)

    files_referenced = [f["name"] for f in java_files] + [f["name"] for f in cobol_files]
    print(f"[ai_assistant] Found files: {files_referenced}")

    # Build context prompt
    context_parts = []

    if java_files:
        context_parts.append("## Generated Java Code\n")
        for f in java_files:
            context_parts.append(f"### {f['name']}\n```java\n{f['content']}\n```\n")

    if cobol_files:
        context_parts.append("\n## Source COBOL Code\n")
        for f in cobol_files:
            context_parts.append(f"### {f['name']}\n```cobol\n{f['content']}\n```\n")

    # Add execution context if provided
    if request.context and request.context.get("completed_nodes"):
        context_parts.append("\n## Workflow Context\n")
        nodes = request.context["completed_nodes"]
        context_parts.append(f"Completed workflow nodes: {', '.join(n.get('type', 'unknown') for n in nodes)}\n")

    context_prompt = "".join(context_parts) if context_parts else "No code files found for this project."

    # Build the full prompt
    system_prompt = """You are an AI assistant helping developers understand and work with legacy code modernization.
You have access to the project's source code (COBOL) and generated code (Java).

Be helpful, concise, and specific. When discussing code:
- Reference specific files, methods, or line numbers when relevant
- Explain the business logic, not just the syntax
- Highlight any potential issues or improvements

If no code is available, let the user know they need to run Code Analysis first."""

    user_prompt = f"""Project: {request.scout_account_id}/{request.application_name}

{context_prompt}

User Question: {request.message}"""

    # Call AI using BedrockAgent (same pattern as code editor and other AI features)
    try:
        agent = BedrockAgent.create(
            purpose="ai_assistant",
            max_tokens=2048,
            temperature=0.7
        )

        response = agent.invoke(
            prompt=user_prompt,
            system=system_prompt
        )

        print(f"[ai_assistant] Response length: {len(response)} chars")

        return AssistantResponse(
            response=response,
            files_referenced=files_referenced
        )

    except Exception as e:
        print(f"[ai_assistant] Error calling AI: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"AI error: {str(e)}")
