"""
v3: OpenAI Agents SDK Tools

@function_tool 데코레이터로 정의 (v2와 동일)
- SDK가 모든 것을 자동 처리!
"""

import os
import subprocess
from glob import glob as python_glob
from typing import Optional

from agents import function_tool

# ============================================================================
# 파일 조작 도구
# ============================================================================


@function_tool
def read_file(file_path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> str:
    """
    Read a file with line numbers.

    Args:
        file_path: Absolute path to the file
        offset: Line number to start from (1-indexed)
        limit: Number of lines to read
    """
    if not os.path.isabs(file_path):
        raise ValueError(f"File path must be absolute: {file_path}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    start = (offset - 1) if offset else 0
    end = (start + limit) if limit else len(lines)
    selected_lines = lines[start:end]

    result = []
    for i, line in enumerate(selected_lines, start=start + 1):
        line_content = line.rstrip("\n")
        if len(line_content) > 2000:
            line_content = line_content[:2000] + "..."
        result.append(f"{i:5d}→{line_content}")

    return "\n".join(result)


@function_tool
def write_file(file_path: str, content: str) -> str:
    """
    Write content to a file.

    Args:
        file_path: Absolute path to the file
        content: Content to write
    """
    if not os.path.isabs(file_path):
        raise ValueError(f"File path must be absolute: {file_path}")

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return f"File written: {file_path} ({len(content)} bytes)"


@function_tool
def edit_file(file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """
    Edit a file by replacing exact strings.

    Args:
        file_path: Absolute path to the file
        old_string: Exact string to replace
        new_string: Replacement string
        replace_all: Replace all occurrences (default: False)
    """
    if not os.path.isabs(file_path):
        raise ValueError(f"File path must be absolute: {file_path}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    count = content.count(old_string)
    if count == 0:
        raise ValueError("old_string not found in file")
    if count > 1 and not replace_all:
        raise ValueError(f"old_string appears {count} times. " f"Set replace_all=True or provide more context.")

    new_content = content.replace(old_string, new_string)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return f"File edited: {count} replacement(s) made"


# ============================================================================
# 검색 도구
# ============================================================================


@function_tool
def glob_files(pattern: str, path: Optional[str] = None) -> str:
    """
    Find files matching a glob pattern.

    Args:
        pattern: Glob pattern (e.g., "**/*.ts")
        path: Directory to search in (default: cwd)
    """
    search_path = path or os.getcwd()
    full_pattern = os.path.join(search_path, pattern)
    matches = sorted(python_glob(full_pattern, recursive=True))

    if not matches:
        return f"No files found matching: {pattern}"

    return "\n".join(matches)


@function_tool
def grep_code(
    pattern: str, path: Optional[str] = None, glob: Optional[str] = None, case_insensitive: bool = False
) -> str:
    """
    Search code using regex.

    Args:
        pattern: Regex pattern to search for
        path: File or directory to search in
        glob: Glob pattern to filter files
        case_insensitive: Case insensitive search
    """
    search_path = path or os.getcwd()

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


@function_tool
def run_bash(command: str, timeout: int = 30) -> str:
    """
    Execute a bash command.

    Args:
        command: Bash command to execute
        timeout: Timeout in seconds
    """
    dangerous = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };:"]
    if any(danger in command for danger in dangerous):
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

TOOLS = [
    read_file,
    write_file,
    edit_file,
    glob_files,
    grep_code,
    run_bash,
]
