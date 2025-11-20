"""
v2.2: LangGraph Tools

v2.1 도구 세트 유지 (13개 도구):
- 파일: read_file, write_file, edit_file (3)
- 검색: glob_files, grep_code (2)
- 실행: run_bash, bash_background, bash_output, kill_shell (4)
- 웹: web_search, web_fetch (2)
- 관리: todo_write, task_tool (2)

Hook System 통합 가능:
- PreToolUse Hook으로 도구 실행 전 검증 (Validation Agent)
- PostToolUse Hook으로 도구 결과 후처리 (File Extraction Agent)

🎯 핵심 개념:
LangGraph에서 도구는 @tool 데코레이터로 매우 간단하게 정의됩니다.
LangChain이 자동으로 OpenAI function calling 스키마를 생성합니다.
"""

import asyncio
import fnmatch
import os
import subprocess
import uuid
from glob import glob as python_glob
from typing import Dict, Optional

from langchain_core.tools import tool

# 백그라운드 프로세스 관리
BACKGROUND_PROCESSES: Dict[str, subprocess.Popen] = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 파일 조작 도구
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(parse_docstring=True)
def read_file(file_path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> str:
    """Reads a file from the local filesystem. You can access any file directly by using this tool.

    IMPORTANT: This tool can only read FILES, not directories. If you need to list directory contents,
    use glob_files() or run_bash with 'ls' command instead.

    Usage:
    - The file_path parameter must be an absolute path, not a relative path
    - The path must point to a file, not a directory
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

    if os.path.isdir(file_path):
        raise IsADirectoryError(
            f"Cannot read directory as file: {file_path}\n"
            f"Hint: Use glob_files() to list directory contents, or specify a file inside the directory."
        )

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


@tool(parse_docstring=True)
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


@tool(parse_docstring=True)
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


@tool(parse_docstring=True)
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


@tool(parse_docstring=True)
def grep_code(
    pattern: str,
    path: Optional[str] = None,
    glob: Optional[str] = None,
    output_mode: str = "files_with_matches",
    type: Optional[str] = None,
    i: bool = False,
    n: bool = True,
    A: Optional[int] = None,
    B: Optional[int] = None,
    C: Optional[int] = None,
    head_limit: Optional[int] = None,
    offset: int = 0,
    multiline: bool = False,
) -> str:
    """A powerful search tool built on ripgrep.

    Usage:
    - ALWAYS use grep_code for search tasks. NEVER invoke `grep` or `rg` as a Bash command.
    - Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+")
    - Filter files with glob parameter (e.g., "*.js", "**/*.tsx") or type parameter (e.g., "js", "py", "rust")
    - Output modes: "content" shows matching lines, "files_with_matches" shows only file paths, "count" shows match counts
    - Pattern syntax: Uses ripgrep (not grep) - literal braces need escaping
    - Multiline matching: By default patterns match within single lines only. For cross-line patterns, use multiline=True

    Args:
        pattern: The regular expression pattern to search for in file contents
        path: File or directory to search in (defaults to current working directory)
        glob: Glob pattern to filter files (e.g., "*.py", "*.{ts,tsx}")
        output_mode: Output mode - "content" shows lines, "files_with_matches" shows paths (default), "count" shows counts
        type: File type to search (e.g., "js", "py", "rust", "go", "java")
        i: Case insensitive search (rg -i)
        n: Show line numbers in output (rg -n). Defaults to true. Only applies to "content" mode.
        A: Number of lines to show after each match (rg -A). Only applies to "content" mode.
        B: Number of lines to show before each match (rg -B). Only applies to "content" mode.
        C: Number of lines to show before and after each match (rg -C). Only applies to "content" mode.
        head_limit: Limit output to first N lines/entries
        offset: Skip first N lines/entries before applying head_limit
        multiline: Enable multiline mode where . matches newlines (rg -U --multiline-dotall)

    Returns:
        Search results based on output_mode
    """
    search_path = path or os.getcwd()

    # Use ripgrep if available
    try:
        cmd = ["rg"]

        # Output mode
        if output_mode == "files_with_matches":
            cmd.append("--files-with-matches")
        elif output_mode == "count":
            cmd.append("--count")
        # content mode는 기본 동작

        # Case insensitive
        if i:
            cmd.append("-i")

        # Line numbers (only for content mode)
        if output_mode == "content" and n:
            cmd.append("-n")

        # Context lines (only for content mode)
        if output_mode == "content":
            if C is not None:
                cmd.extend(["-C", str(C)])
            else:
                if A is not None:
                    cmd.extend(["-A", str(A)])
                if B is not None:
                    cmd.extend(["-B", str(B)])

        # File type
        if type:
            cmd.extend(["--type", type])

        # Glob pattern
        if glob:
            cmd.extend(["--glob", glob])

        # Multiline mode
        if multiline:
            cmd.extend(["-U", "--multiline-dotall"])

        # Pattern and path
        cmd.append(pattern)
        cmd.append(search_path)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout if result.stdout else "No matches found"

        # Apply offset and head_limit
        if output != "No matches found" and (offset > 0 or head_limit is not None):
            lines = output.splitlines()
            start = offset
            end = (start + head_limit) if head_limit else len(lines)
            output = "\n".join(lines[start:end])

        return output

    except FileNotFoundError:
        # Fallback to basic Python implementation (simplified - only supports basic features)
        import re

        flags = re.IGNORECASE if i else 0
        if multiline:
            flags |= re.DOTALL
        regex = re.compile(pattern, flags)

        matches = []
        for root, _, files in os.walk(search_path):
            for file in files:
                if glob and not fnmatch.fnmatch(file, glob):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if regex.search(content):
                            if output_mode == "files_with_matches":
                                matches.append(file_path)
                            elif output_mode == "content":
                                for line_num, line in enumerate(content.splitlines(), 1):
                                    if regex.search(line):
                                        if n:
                                            matches.append(f"{file_path}:{line_num}:{line}")
                                        else:
                                            matches.append(f"{file_path}:{line}")
                            elif output_mode == "count":
                                count = len(regex.findall(content))
                                matches.append(f"{file_path}:{count}")
                except Exception:
                    continue

        if not matches:
            return "No matches found"

        # Apply offset and head_limit
        if offset > 0 or head_limit is not None:
            start = offset
            end = (start + head_limit) if head_limit else len(matches)
            matches = matches[start:end]

        return "\n".join(matches)

    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Search timed out after 30s")


# ============================================================================
# 실행 도구
# ============================================================================


@tool(parse_docstring=True)
def run_bash(command: str, timeout: Optional[int] = None) -> str:
    """Executes a given bash command in a persistent shell session with optional timeout.

    IMPORTANT: This tool is for terminal operations like git, npm, docker, etc. DO NOT use it for file operations (reading, writing, editing, searching, finding files) - use the specialized tools for this instead.

    Before executing the command:
    - If the command will create new directories or files, first use `ls` to verify the parent directory exists
    - Always quote file paths that contain spaces with double quotes (e.g., cd "path with spaces/file.txt")

    Usage notes:
    - The command argument is required
    - You can specify an optional timeout in milliseconds (up to 600000ms / 10 minutes). If not specified, commands will timeout after 120000ms (2 minutes)
    - Avoid using Bash with the `find`, `grep`, `cat`, `head`, `tail`, `sed`, `awk`, or `echo` commands. Instead, always prefer using the dedicated tools:
      - File search: Use glob_files (NOT find or ls)
      - Content search: Use grep_code (NOT grep or rg)
      - Read files: Use read_file (NOT cat/head/tail)
      - Edit files: Use edit_file (NOT sed/awk)
      - Write files: Use write_file (NOT echo >/cat <<EOF)
      - Communication: Output text directly (NOT echo/printf)

    When issuing multiple commands:
    - If the commands are independent and can run in parallel, make multiple run_bash tool calls in a single response
    - If the commands depend on each other and must run sequentially, use a single Bash call with '&&' to chain them together (e.g., `git add . && git commit -m "message" && git push`)
    - Use ';' only when you need to run commands sequentially but don't care if earlier commands fail
    - DO NOT use newlines to separate commands (newlines are ok in quoted strings)

    Try to maintain your current working directory throughout the session by using absolute paths and avoiding usage of `cd`.

    Args:
        command: The command to execute
        timeout: Optional timeout in milliseconds (max 600000). Defaults to 120000ms (2 minutes)

    Returns:
        Command output (stdout + stderr)
    """
    # Convert milliseconds to seconds, with defaults
    timeout_seconds = (timeout / 1000) if timeout else 120

    # Safety check
    dangerous_commands = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };:"]
    if any(danger in command for danger in dangerous_commands):
        raise ValueError(f"Dangerous command blocked: {command}")

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout_seconds, cwd=os.getcwd()
        )

        output = []
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(f"[stderr]\n{result.stderr}")
        if result.returncode != 0:
            output.append(f"[exit code: {result.returncode}]")

        return "\n".join(output) if output else "(no output)"

    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out after {timeout_seconds}s: {command}")


# ============================================================================
# 작업 관리 도구
# ============================================================================


@tool(parse_docstring=True)
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
# Task Tool (Subagent 실행) - 이것이 핵심!
# ============================================================================


@tool(parse_docstring=True)
def task_tool(
    description: str,
    prompt: str,
    subagent_type: str,
    model: Optional[str] = None,
) -> str:
    """Launch a new agent to handle complex, multi-step tasks autonomously.

    The Task tool launches specialized agents (subprocesses) that autonomously handle complex tasks.
    Each agent type has specific capabilities and tools available to it.

    Available agent types and the tools they have access to:
    - general-purpose: General-purpose agent for researching complex questions, searching for code,
      and executing multi-step tasks. When you are searching for a keyword or file and are not
      confident that you will find the right match in the first few tries use this agent to
      perform the search for you. (Tools: *)
    - Explore: Fast agent specialized for exploring codebases. Use this when you need to quickly
      find files by patterns, search code for keywords, or answer questions about the codebase.
      When calling this agent, specify the desired thoroughness level: "quick" for basic searches,
      "medium" for moderate exploration, or "very thorough" for comprehensive analysis. (Tools: All tools)
    - Plan: Fast agent specialized for planning implementation steps. Use this when you need to
      create a structured plan for implementing features, fixing bugs, or refactoring code.
      When calling this agent, specify the desired thoroughness level: "quick" for basic plans,
      "medium" for detailed analysis, or "very thorough" for comprehensive planning. (Tools: All tools)

    Usage notes:
    - Launch multiple agents concurrently whenever possible, to maximize performance
    - When the agent is done, it will return a single message back to you
    - Each agent invocation is stateless. You will not be able to send additional messages to the agent
    - The agent's outputs should generally be trusted
    - Clearly tell the agent whether you expect it to write code or just to do research

    Args:
        description: A short (3-5 word) description of the task
        prompt: The task for the agent to perform
        subagent_type: The type of specialized agent to use (general-purpose, Explore, Plan)
        model: Optional model to use for this agent (sonnet, opus, haiku). If not specified, inherits from parent. Prefer haiku for quick, straightforward tasks to minimize cost and latency.

    Returns:
        Subagent report
    """
    # NOTE: 실제 구현은 graph.py에서 처리
    # 이 tool은 schema만 제공, 실제 실행은 노드에서 처리
    return f"Task tool called: {subagent_type} - {description}"


# ============================================================================
# 백그라운드 실행 도구 (NEW in v2.1)
# ============================================================================


@tool(parse_docstring=True)
def bash_background(command: str, description: str = "") -> str:
    """Run a bash command in the background and return a shell ID for monitoring.

    This tool is useful for long-running commands like servers, watchers, or build processes.
    Use bash_output() to check the output and kill_shell() to stop the process.

    IMPORTANT: This tool is for terminal operations that run in the background. Use run_bash for normal commands.

    Args:
        command: The bash command to execute in background
        description: Short description of what this command does (5-10 words)

    Returns:
        Shell ID for monitoring and controlling the process
    """
    shell_id = str(uuid.uuid4())[:8]

    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.getcwd(),
            bufsize=1,  # Line buffered
        )
        BACKGROUND_PROCESSES[shell_id] = proc

        desc_text = f" ({description})" if description else ""
        return f"✓ Started background process{desc_text}\nShell ID: {shell_id}\nUse bash_output('{shell_id}') to check output"

    except Exception as e:
        return f"[ERROR] Failed to start background process: {type(e).__name__}: {str(e)}"


@tool(parse_docstring=True)
def bash_output(shell_id: str, filter: Optional[str] = None) -> str:
    """Retrieve output from a background bash shell.

    Takes a shell_id parameter identifying the shell. Always returns only new output since the last check.

    Args:
        shell_id: The ID of the background shell to retrieve output from
        filter: Optional regular expression to filter the output lines. Only lines matching this regex will be included.

    Returns:
        stdout and stderr output along with shell status
    """
    proc = BACKGROUND_PROCESSES.get(shell_id)

    if not proc:
        return f"[ERROR] Shell not found: {shell_id}\nAvailable shells: {list(BACKGROUND_PROCESSES.keys())}"

    try:
        # 비블로킹 읽기 (poll로 확인)
        poll_result = proc.poll()

        output_lines = []

        # stdout 읽기 (non-blocking)
        if proc.stdout:
            try:
                # 사용 가능한 데이터만 읽기
                import select

                if select.select([proc.stdout], [], [], 0)[0]:
                    line = proc.stdout.readline()
                    while line:
                        output_lines.append(line.rstrip())
                        if not select.select([proc.stdout], [], [], 0)[0]:
                            break
                        line = proc.stdout.readline()
            except (IOError, OSError, ValueError):
                # I/O 오류 무시 (프로세스가 종료되었을 수 있음)
                pass

        # stderr 읽기
        if proc.stderr:
            try:
                import select

                if select.select([proc.stderr], [], [], 0)[0]:
                    line = proc.stderr.readline()
                    while line:
                        output_lines.append(f"[stderr] {line.rstrip()}")
                        if not select.select([proc.stderr], [], [], 0)[0]:
                            break
                        line = proc.stderr.readline()
            except (IOError, OSError, ValueError):
                # I/O 오류 무시 (프로세스가 종료되었을 수 있음)
                pass

        # Filter 적용
        if filter and output_lines:
            import re

            regex = re.compile(filter)
            output_lines = [line for line in output_lines if regex.search(line)]

        # 상태 정보
        if poll_result is None:
            status = "Running"
        else:
            status = f"Exited (code: {poll_result})"
            # 프로세스 종료 시 제거
            del BACKGROUND_PROCESSES[shell_id]

        result = f"Shell {shell_id} - {status}\n"
        if output_lines:
            result += "\n".join(output_lines)
        else:
            result += "(no new output)"

        return result

    except Exception as e:
        return f"[ERROR] Failed to read output: {type(e).__name__}: {str(e)}"


@tool(parse_docstring=True)
def kill_shell(shell_id: str) -> str:
    """Kill a running background bash shell by its ID.

    Args:
        shell_id: The ID of the background shell to kill

    Returns:
        Success or failure status
    """
    proc = BACKGROUND_PROCESSES.get(shell_id)

    if not proc:
        return f"[ERROR] Shell not found: {shell_id}\nAvailable shells: {list(BACKGROUND_PROCESSES.keys())}"

    try:
        proc.kill()
        proc.wait(timeout=5)  # 종료 대기
        del BACKGROUND_PROCESSES[shell_id]
        return f"✓ Killed shell: {shell_id}"

    except subprocess.TimeoutExpired:
        proc.kill()  # Force kill
        del BACKGROUND_PROCESSES[shell_id]
        return f"✓ Force killed shell: {shell_id}"

    except Exception as e:
        return f"[ERROR] Failed to kill shell: {type(e).__name__}: {str(e)}"


# ============================================================================
# 웹 접근 도구 (NEW in v2.1)
# ============================================================================


@tool(parse_docstring=True)
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return up-to-date information.

    Uses DuckDuckGo to search the web without requiring API keys.
    Use this tool for accessing information beyond the AI's knowledge cutoff.

    Args:
        query: The search query
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Search results formatted as markdown
    """
    try:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"**[{r['title']}]({r['href']})**\n{r['body']}\n")

        if not results:
            return f"No results found for: {query}"

        return f"Search results for '{query}':\n\n" + "\n---\n\n".join(results)

    except ImportError:
        return "[ERROR] ddgs package not installed. Run: uv add ddgs"
    except Exception as e:
        return f"[ERROR] Search failed: {type(e).__name__}: {str(e)}"


@tool(parse_docstring=True)
async def web_fetch(url: str, prompt: str = "Summarize the main content") -> str:
    """Fetch and analyze content from a URL.

    Retrieves HTML content, intelligently extracts main content, and processes it based on the prompt.
    Use this tool when you need to access specific web pages or documentation.

    Args:
        url: The URL to fetch content from (must be a valid HTTP/HTTPS URL)
        prompt: What information to extract from the page (e.g., "Summarize", "Extract code examples", "Find pricing info")

    Returns:
        Processed page content based on the prompt
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
        import re

        # Fetch content
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
            element.decompose()

        # Try to find main content (smart extraction)
        main_content = None

        # Priority 1: Look for semantic HTML5 elements
        for tag in ["article", "main", "[role='main']"]:
            main_content = soup.select_one(tag)
            if main_content:
                break

        # Priority 2: Look for common content classes/ids
        if not main_content:
            for selector in ["#content", "#main-content", ".content", ".main-content", ".post-content", ".article-content"]:
                main_content = soup.select_one(selector)
                if main_content:
                    break

        # Fallback: use body
        if not main_content:
            main_content = soup.body if soup.body else soup

        # Extract text with structure preservation
        def extract_structured_text(element, depth=0):
            """Extract text while preserving some structure (headings, lists, code)"""
            if not element:
                return []

            lines = []
            for child in element.children:
                if isinstance(child, str):
                    text = child.strip()
                    if text:
                        lines.append(text)
                elif child.name:
                    # Preserve code blocks
                    if child.name in ["pre", "code"]:
                        code_text = child.get_text(strip=True)
                        if code_text:
                            lines.append(f"\n```\n{code_text}\n```\n")
                    # Preserve headings
                    elif child.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                        heading_text = child.get_text(strip=True)
                        if heading_text:
                            level = int(child.name[1])
                            lines.append(f"\n{'#' * level} {heading_text}\n")
                    # Preserve lists
                    elif child.name in ["li"]:
                        li_text = child.get_text(strip=True)
                        if li_text:
                            lines.append(f"- {li_text}")
                    # Recurse for other elements
                    elif child.name not in ["script", "style"]:
                        lines.extend(extract_structured_text(child, depth + 1))

            return lines

        # Extract structured content
        content_lines = extract_structured_text(main_content)
        clean_text = "\n".join(content_lines)

        # Clean up excessive whitespace
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text)  # Max 2 consecutive newlines
        clean_text = clean_text.strip()

        # Smart truncation based on content length
        max_length = 15000  # Increased from 10000
        if len(clean_text) > max_length:
            # Try to truncate at a paragraph boundary
            truncate_point = clean_text.rfind('\n\n', 0, max_length)
            if truncate_point > max_length * 0.8:  # If we found a good break point
                clean_text = clean_text[:truncate_point]
            else:
                # Truncate at sentence boundary
                truncate_point = clean_text.rfind('. ', 0, max_length)
                if truncate_point > max_length * 0.8:
                    clean_text = clean_text[:truncate_point + 1]
                else:
                    # Last resort: hard truncate
                    clean_text = clean_text[:max_length]

            clean_text += "\n\n[Content truncated. Use prompt parameter to request specific information.]"

        # Add metadata
        title = soup.title.string if soup.title else "No title"
        result = f"**URL**: {url}\n**Title**: {title}\n**Task**: {prompt}\n\n**Content**:\n\n{clean_text}"

        # If content is still too long, provide a note about using the prompt
        if len(result) > 20000:
            result = result[:20000] + f"\n\n[Note: Content is extensive. Refine your prompt for specific information.]"

        return result

    except ImportError:
        return "[ERROR] Required packages not installed. Run: pip install httpx beautifulsoup4"
    except httpx.HTTPStatusError as e:
        return f"[ERROR] HTTP {e.response.status_code}: {url}"
    except Exception as e:
        return f"[ERROR] Failed to fetch URL: {type(e).__name__}: {str(e)}"


# ============================================================================
# 도구 목록
# ============================================================================

# LangGraph에서 사용할 도구 목록 (v2.1: 13개 도구)
TOOLS = [
    # 파일 조작 (3)
    read_file,
    write_file,
    edit_file,
    # 검색 (2)
    glob_files,
    grep_code,
    # 실행 (4) - 백그라운드 실행 추가!
    run_bash,
    bash_background,
    bash_output,
    kill_shell,
    # 웹 접근 (2) - NEW!
    web_search,
    web_fetch,
    # 관리 (2)
    todo_write,
    task_tool,
]


# 도구 이름으로 매핑
TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}
