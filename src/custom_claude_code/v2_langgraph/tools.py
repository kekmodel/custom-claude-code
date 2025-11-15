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

import json
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
    """
    📖 파일을 읽고 라인 번호와 함께 반환합니다.

    이 도구는 LLM이 코드를 분석하거나 파일 내용을 확인할 때 사용합니다.

    Args:
        file_path: 읽을 파일의 절대 경로 (필수)
        offset: 시작 라인 번호 (1부터 시작, 선택)
        limit: 읽을 라인 수 (선택)

    Returns:
        라인 번호가 포함된 파일 내용 (cat -n 스타일)

    Example:
        read_file("/path/to/file.py", offset=10, limit=20)
        → 10번째 줄부터 20줄 읽기

    📌 확장 팁:
    다른 파일 타입 지원을 추가할 수 있습니다:
    - PDF 읽기: PyPDF2
    - Excel 읽기: pandas
    - 이미지 OCR: pytesseract
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
    """
    Write content to a file (creates new file or overwrites existing).

    Args:
        file_path: Absolute path to the file to write
        content: Content to write

    Returns:
        Success message
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
    """
    Edit a file by replacing exact string matches.

    Args:
        file_path: Absolute path to the file to edit
        old_string: Exact string to replace
        new_string: Replacement string
        replace_all: Replace all occurrences (default: False, requires unique match)

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
    """
    Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.ts", "src/**/*.py")
        path: Directory to search in (default: current working directory)

    Returns:
        List of matching file paths
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
    """
    Search for code using regex pattern.

    Args:
        pattern: Regex pattern to search for
        path: File or directory to search in
        glob: Glob pattern to filter files (e.g., "*.py")
        case_insensitive: Case insensitive search

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
                if glob and not python_glob(file, glob):
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
    """
    Execute a bash command.

    Args:
        command: Bash command to execute
        timeout: Timeout in seconds

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
# 도구 목록
# ============================================================================

# ============================================================================
# Task Tool (Subagent 실행) - 이것이 핵심!
# ============================================================================


@tool
def task_tool(subagent_type: str, description: str, prompt: str, model: str = "sonnet") -> str:
    """
    Launch a subagent to handle complex tasks.

    Args:
        subagent_type: Type of agent (general-purpose, Explore, Plan, statusline-setup)
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
    task_tool,  # Subagent 실행!
]


# 도구 이름으로 매핑
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
