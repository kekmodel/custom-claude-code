"""
v2: LangGraph Tools

🎯 핵심 개념:
LangGraph에서 도구는 @tool 데코레이터로 매우 간단하게 정의됩니다.
LangChain이 자동으로 OpenAI function calling 스키마를 생성합니다.

📌 도구 추가 3단계:
1. @tool 데코레이터를 함수에 추가
2. Docstring 작성 (필수! LLM이 이것을 보고 도구를 선택함)
3. TOOLS 리스트에 추가

✨ 자동 처리:
- 타입 힌트 → JSON Schema 자동 생성
- Docstring → 도구 설명으로 사용
- ToolNode가 자동으로 도구 실행

📌 확장 예시:
```python
@tool
def analyze_sentiment(text: str) -> str:
    '''Analyze sentiment of given text.'''
    # 구현...
    return "positive"

# TOOLS에 추가만 하면 끝!
TOOLS = [..., analyze_sentiment]
```
"""

import fnmatch
import os
import subprocess
from glob import glob as python_glob
from typing import Optional

from langchain_core.tools import tool

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 파일 조작 도구
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool
def read_file(file_path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> str:
    """Reads a file from the local filesystem. You can access any file directly by using this tool.

    Usage:
    - The file_path parameter must be an absolute path, not a relative path
    - By default, it reads up to 2000 lines starting from the beginning of the file
    - You can optionally specify a line offset and limit (especially handy for long files), but it's recommended to read the whole file by not providing these parameters
    - Any lines longer than 2000 characters will be truncated
    - Results are returned using cat -n format, with line numbers starting at 1
    - You can call multiple tools in a single response. It is always better to speculatively read multiple potentially useful files in parallel.

    Args:
        file_path: The absolute path to the file to read
        offset: The line number to start reading from (1-based index). Only provide if the file is too large to read at once
        limit: The number of lines to read. Only provide if the file is too large to read at once

    Returns:
        File content with line numbers (cat -n format)
    """
    if not os.path.isabs(file_path):
        raise ValueError(f"File path must be absolute, got: {file_path}")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    # Apply offset and limit
    start = (offset - 1) if offset else 0
    end = (start + limit) if limit else len(lines)
    selected_lines = lines[start:end]

    # Format with line numbers
    result = []
    for i, line in enumerate(selected_lines, start=start + 1):
        # Truncate long lines
        line_content = line.rstrip("\n")
        if len(line_content) > 2000:
            line_content = line_content[:2000] + "..."
        result.append(f"{i:5d}→{line_content}")

    return "\n".join(result)


@tool
def write_file(file_path: str, content: str) -> str:
    """Writes a file to the local filesystem.

    Usage:
    - This tool will overwrite the existing file if there is one at the provided path.
    - ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
    - The file_path parameter must be an absolute path, not a relative path.

    Args:
        file_path: The absolute path to the file to write (must be absolute, not relative)
        content: The content to write to the file

    Returns:
        Success message with file path and size
    """
    if not os.path.isabs(file_path):
        raise ValueError(f"File path must be absolute, got: {file_path}")

    # Create parent directories if needed
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return f"File written successfully: {file_path} ({len(content)} bytes)"


@tool
def edit_file(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """Performs exact string replacements in files.

    Usage:
    - You must use your `read_file` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file.
    - When editing text from read_file output, ensure you preserve the exact indentation (tabs/spaces) as it appears AFTER the line number prefix. The line number prefix format is: spaces + line number + tab. Everything after that tab is the actual file content to match. Never include any part of the line number prefix in the old_string or new_string.
    - ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
    - The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`.
    - Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance.

    Args:
        file_path: The absolute path to the file to modify
        old_string: The text to replace
        new_string: The text to replace it with (must be different from old_string)
        replace_all: Replace all occurrences of old_string (default false)

    Returns:
        Success message with number of replacements
    """
    if not os.path.isabs(file_path):
        raise ValueError(f"File path must be absolute, got: {file_path}")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Check uniqueness
    count = content.count(old_string)
    if count == 0:
        raise ValueError(f"old_string not found in file")
    if count > 1 and not replace_all:
        raise ValueError(
            f"old_string appears {count} times in file. "
            f"Set replace_all=True to replace all occurrences, "
            f"or provide more context to make the string unique."
        )

    # Replace
    new_content = content.replace(old_string, new_string)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return f"File edited successfully: {count} replacement(s) made"


# ============================================================================
# 검색 도구
# ============================================================================


@tool
def glob_files(pattern: str, path: Optional[str] = None) -> str:
    """Fast file pattern matching tool that works with any codebase size.

    Usage:
    - Supports glob patterns like "**/*.js" or "src/**/*.ts"
    - Returns matching file paths sorted by modification time
    - Use this tool when you need to find files by name patterns
    - You can call multiple tools in a single response. It is always better to speculatively perform multiple searches in parallel if they are potentially useful.

    Args:
        pattern: Glob pattern (e.g., "**/*.ts", "src/**/*.py")
        path: Directory to search in (default: current working directory). IMPORTANT: Omit this field to use the default directory. DO NOT enter "undefined" or "null" - simply omit it for the default behavior.

    Returns:
        List of matching file paths sorted by modification time
    """
    search_path = path or os.getcwd()
    full_pattern = os.path.join(search_path, pattern)

    matches = sorted(python_glob(full_pattern, recursive=True))

    if not matches:
        return f"No files found matching pattern: {pattern}"

    return "\n".join(matches)


@tool
def grep_code(
    pattern: str, path: Optional[str] = None, glob: Optional[str] = None, case_insensitive: bool = False
) -> str:
    """A powerful search tool built on ripgrep.

    Usage:
    - ALWAYS use grep_code for search tasks. NEVER invoke `grep` or `rg` as a Bash command.
    - Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+")
    - Filter files with glob parameter (e.g., "*.js", "**/*.tsx")
    - Returns list of files containing matches by default
    - You can call multiple tools in a single response. It is always better to speculatively perform multiple searches in parallel if they are potentially useful.

    Args:
        pattern: The regular expression pattern to search for in file contents
        path: File or directory to search in (defaults to current working directory)
        glob: Glob pattern to filter files (e.g., "*.py", "*.{ts,tsx}")
        case_insensitive: Case insensitive search (default: False)

    Returns:
        List of files containing the pattern
    """
    search_path = path or os.getcwd()

    # Use ripgrep if available, otherwise Python fallback
    try:
        cmd = ["rg", "--files-with-matches", pattern]
        if case_insensitive:
            cmd.append("-i")
        if glob:
            cmd.extend(["--glob", glob])
        cmd.append(search_path)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout if result.stdout else "No matches found"

    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Fallback to basic Python implementation
        import re

        flags = re.IGNORECASE if case_insensitive else 0
        regex = re.compile(pattern, flags)

        matches = []
        for root, _, files in os.walk(search_path):
            for file in files:
                # glob 패턴이 지정되었으면 파일명 필터링
                # fnmatch: 파일명 패턴 매칭 (예: "*.py", "test_*.js")
                if glob and not fnmatch.fnmatch(file, glob):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        if regex.search(f.read()):
                            matches.append(file_path)
                except Exception:
                    continue

        return "\n".join(matches) if matches else "No matches found"


# ============================================================================
# 실행 도구
# ============================================================================


@tool
def run_bash(command: str, timeout: int = 30) -> str:
    """Executes a given bash command in a persistent shell session with optional timeout.

    IMPORTANT: This tool is for terminal operations like git, npm, docker, etc. DO NOT use it for file operations (reading, writing, editing, searching, finding files) - use the specialized tools for this instead.

    Usage notes:
    - Always quote file paths that contain spaces with double quotes (e.g., cd "path with spaces/file.txt")
    - You can specify an optional timeout in seconds (default: 30s)
    - Avoid using Bash with the `find`, `grep`, `cat`, `head`, `tail`, `sed`, `awk`, or `echo` commands. Instead, always prefer using the dedicated tools:
      - File search: Use glob_files (NOT find or ls)
      - Content search: Use grep_code (NOT grep or rg)
      - Read files: Use read_file (NOT cat/head/tail)
      - Edit files: Use edit_file (NOT sed/awk)
      - Write files: Use write_file (NOT echo >/cat <<EOF)

    When issuing multiple commands:
    - If the commands are independent and can run in parallel, make multiple run_bash tool calls in a single response
    - If the commands depend on each other and must run sequentially, use a single Bash call with '&&' to chain them together (e.g., `git add . && git commit -m "message" && git push`)
    - Use ';' only when you need to run commands sequentially but don't care if earlier commands fail
    - DO NOT use newlines to separate commands (newlines are ok in quoted strings)

    Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`.

    Args:
        command: Bash command to execute
        timeout: Timeout in seconds (default: 30)

    Returns:
        Command output (stdout + stderr)
    """
    # Safety check
    dangerous_commands = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };:"]
    if any(danger in command for danger in dangerous_commands):
        raise ValueError(f"Dangerous command blocked: {command}")

    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=os.getcwd())

        output = []
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(f"[stderr]\n{result.stderr}")
        if result.returncode != 0:
            output.append(f"[exit code: {result.returncode}]")

        return "\n".join(output) if output else "(no output)"

    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out after {timeout}s: {command}")


# ============================================================================
# 작업 관리 도구
# ============================================================================


@tool
def todo_write(todos: list[dict]) -> str:
    """Use this tool to create and manage a structured task list for your current coding session.

    Usage:
    Use this tool proactively in these scenarios:
    1. Complex multi-step tasks - When a task requires 3 or more distinct steps or actions
    2. Non-trivial and complex tasks - Tasks that require careful planning or multiple operations
    3. After receiving new instructions - Immediately capture user requirements as todos
    4. When you start working on a task - Mark it as in_progress BEFORE beginning work
    5. After completing a task - Mark it as completed and add any new follow-up tasks

    When NOT to Use This Tool:
    1. There is only a single, straightforward task
    2. The task is trivial and tracking it provides no organizational benefit
    3. The task can be completed in less than 3 trivial steps

    Task States and Management:
    1. Task States:
       - pending: Task not yet started
       - in_progress: Currently working on (limit to ONE task at a time)
       - completed: Task finished successfully

    2. Task descriptions must have two forms:
       - content: The imperative form (e.g., "Run tests", "Build the project")
       - activeForm: The present continuous form (e.g., "Running tests", "Building the project")

    3. Task Management:
       - Update task status in real-time as you work
       - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
       - Exactly ONE task must be in_progress at any time (not less, not more)
       - Complete current tasks before starting new ones

    Args:
        todos: List of todo items, each with 'content' (str), 'status' (pending/in_progress/completed), 'activeForm' (str)

    Returns:
        Success message with current todo status
    """
    # Validate todo structure
    for todo in todos:
        if not all(k in todo for k in ["content", "status", "activeForm"]):
            raise ValueError("Each todo must have 'content', 'status', and 'activeForm' fields")
        if todo["status"] not in ["pending", "in_progress", "completed"]:
            raise ValueError(f"Invalid status: {todo['status']}")

    # Count statuses
    in_progress = sum(1 for t in todos if t["status"] == "in_progress")
    completed = sum(1 for t in todos if t["status"] == "completed")
    pending = sum(1 for t in todos if t["status"] == "pending")

    # Return formatted status
    result = f"Todo list updated: {len(todos)} total tasks\n"
    result += f"  - {completed} completed\n"
    result += f"  - {in_progress} in progress\n"
    result += f"  - {pending} pending"

    # Note: Actual state update happens in graph node
    return result


# ============================================================================
# 계획 모드 도구
# ============================================================================


@tool
def exit_plan_mode(plan: str) -> str:
    """Use this tool when you are in plan mode and have finished presenting your plan and are ready to code.

    IMPORTANT: Only use this tool when the task requires planning the implementation steps of a task that requires writing code.
    For research tasks where you're gathering information, searching files, reading files or in general trying to understand the codebase - do NOT use this tool.

    Handling Ambiguity in Plans:
    Before using this tool, ensure your plan is clear and unambiguous. If there are multiple valid approaches or unclear requirements:
    1. Clarify with the user
    2. Ask about specific implementation choices (e.g., architectural patterns, which library to use)
    3. Clarify any assumptions that could affect the implementation
    4. Only proceed after resolving ambiguities

    Args:
        plan: The plan you came up with, that you want to run by the user for approval. Supports markdown. The plan should be pretty concise.

    Returns:
        Message indicating plan mode exit
    """
    return f"Plan presented to user. Awaiting approval to proceed with implementation.\n\n{plan}"


# ============================================================================
# Task Tool (Subagent 실행) - 이것이 핵심!
# ============================================================================


@tool
def task_tool(subagent_type: str, description: str, prompt: str, model: str = "sonnet") -> str:
    """
    Launch a subagent to handle complex tasks.

    Args:
        subagent_type: Type of agent (general-purpose, Explore, Plan)
        description: Short 3-5 word description
        prompt: Detailed instructions for the subagent
        model: Model to use (sonnet, opus, haiku)

    Returns:
        Subagent report
    """
    # NOTE: 실제 구현은 graph.py에서 처리
    # 이 tool은 schema만 제공, 실제 실행은 노드에서 처리
    return f"Task tool called: {subagent_type} - {description}"


# LangGraph에서 사용할 도구 목록
TOOLS = [
    read_file,
    write_file,
    edit_file,
    glob_files,
    grep_code,
    run_bash,
    todo_write,  # 작업 추적!
    exit_plan_mode,  # 계획 모드 종료!
    task_tool,  # Subagent 실행!
]


# 도구 이름으로 매핑
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
