"""
v3: OpenAI Agents SDK Tools

@function_tool 데코레이터로 정의 (v2와 동일)
- SDK가 모든 것을 자동 처리!
"""

import os
import subprocess
import uuid
import re
from glob import glob as python_glob
from typing import Optional, Dict

from agents import function_tool

# 백그라운드 프로세스 관리 (v2.1 feature)
BACKGROUND_PROCESSES: Dict[str, subprocess.Popen] = {}

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
# 백그라운드 실행 도구 (v2.1 feature)
# ============================================================================


@function_tool
def bash_background(command: str, description: str = "") -> str:
    """
    Run a bash command in the background.

    Args:
        command: Bash command to execute
        description: Short description of the command
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
            bufsize=1,
        )
        BACKGROUND_PROCESSES[shell_id] = proc

        desc_text = f" ({description})" if description else ""
        return f"✓ Started background process{desc_text}\nShell ID: {shell_id}\nUse bash_output('{shell_id}') to check output"

    except Exception as e:
        return f"[ERROR] Failed to start: {type(e).__name__}: {str(e)}"


@function_tool
def bash_output(shell_id: str, filter: Optional[str] = None) -> str:
    """
    Get output from a background shell.

    Args:
        shell_id: Background shell ID
        filter: Optional regex filter
    """
    proc = BACKGROUND_PROCESSES.get(shell_id)

    if not proc:
        return f"[ERROR] Shell not found: {shell_id}\nAvailable: {list(BACKGROUND_PROCESSES.keys())}"

    try:
        poll_result = proc.poll()
        output_lines = []

        # Read stdout
        if proc.stdout:
            try:
                import select

                if select.select([proc.stdout], [], [], 0)[0]:
                    line = proc.stdout.readline()
                    while line:
                        output_lines.append(line.rstrip())
                        if not select.select([proc.stdout], [], [], 0)[0]:
                            break
                        line = proc.stdout.readline()
            except (IOError, OSError, ValueError):
                pass

        # Read stderr
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
                pass

        # Apply filter
        if filter and output_lines:
            regex = re.compile(filter)
            output_lines = [line for line in output_lines if regex.search(line)]

        # Status
        if poll_result is None:
            status = "Running"
        else:
            status = f"Exited (code: {poll_result})"
            del BACKGROUND_PROCESSES[shell_id]

        result = f"Shell {shell_id} - {status}\n"
        if output_lines:
            result += "\n".join(output_lines)
        else:
            result += "(no new output)"

        return result

    except Exception as e:
        return f"[ERROR] Failed to read: {type(e).__name__}: {str(e)}"


@function_tool
def kill_shell(shell_id: str) -> str:
    """
    Kill a background shell.

    Args:
        shell_id: Shell ID to kill
    """
    proc = BACKGROUND_PROCESSES.get(shell_id)

    if not proc:
        return f"[ERROR] Shell not found: {shell_id}\nAvailable: {list(BACKGROUND_PROCESSES.keys())}"

    try:
        proc.kill()
        proc.wait(timeout=5)
        del BACKGROUND_PROCESSES[shell_id]
        return f"✓ Killed shell: {shell_id}"

    except subprocess.TimeoutExpired:
        proc.kill()
        del BACKGROUND_PROCESSES[shell_id]
        return f"✓ Force killed shell: {shell_id}"

    except Exception as e:
        return f"[ERROR] Failed to kill: {type(e).__name__}: {str(e)}"


# ============================================================================
# 웹 접근 도구 (v2.1 feature)
# ============================================================================


@function_tool
def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum results (default: 5)
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
        return "[ERROR] ddgs not installed. Run: uv add ddgs"
    except Exception as e:
        return f"[ERROR] Search failed: {type(e).__name__}: {str(e)}"


@function_tool
def web_fetch(url: str, prompt: str = "Summarize the main content") -> str:
    """
    Fetch and analyze content from a URL.

    Args:
        url: URL to fetch
        prompt: What to extract from the page
    """
    try:
        import httpx
        from bs4 import BeautifulSoup

        # Fetch (sync version)
        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()

        # Parse
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove unwanted
        for element in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
            element.decompose()

        # Find main content
        main_content = None
        for tag in ["article", "main", "[role='main']"]:
            main_content = soup.select_one(tag)
            if main_content:
                break

        if not main_content:
            for selector in ["#content", "#main-content", ".content", ".main-content"]:
                main_content = soup.select_one(selector)
                if main_content:
                    break

        if not main_content:
            main_content = soup.body if soup.body else soup

        # Extract structured text
        def extract_text(element):
            if not element:
                return []

            lines = []
            for child in element.children:
                if isinstance(child, str):
                    text = child.strip()
                    if text:
                        lines.append(text)
                elif child.name:
                    if child.name in ["pre", "code"]:
                        lines.append(f"\n```\n{child.get_text(strip=True)}\n```\n")
                    elif child.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                        level = int(child.name[1])
                        lines.append(f"\n{'#' * level} {child.get_text(strip=True)}\n")
                    elif child.name in ["li"]:
                        lines.append(f"- {child.get_text(strip=True)}")
                    elif child.name not in ["script", "style"]:
                        lines.extend(extract_text(child))

            return lines

        content_lines = extract_text(main_content)
        clean_text = "\n".join(content_lines)
        clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()

        # Truncate
        max_length = 15000
        if len(clean_text) > max_length:
            truncate_point = clean_text.rfind("\n\n", 0, max_length)
            if truncate_point > max_length * 0.8:
                clean_text = clean_text[:truncate_point]
            else:
                truncate_point = clean_text.rfind(". ", 0, max_length)
                if truncate_point > max_length * 0.8:
                    clean_text = clean_text[: truncate_point + 1]
                else:
                    clean_text = clean_text[:max_length]

            clean_text += "\n\n[Content truncated]"

        title = soup.title.string if soup.title else "No title"
        result = f"**URL**: {url}\n**Title**: {title}\n**Task**: {prompt}\n\n**Content**:\n\n{clean_text}"

        if len(result) > 20000:
            result = result[:20000] + "\n\n[Note: Content extensive]"

        return result

    except ImportError:
        return "[ERROR] httpx or beautifulsoup4 not installed. Run: uv add httpx beautifulsoup4"
    except httpx.HTTPStatusError as e:
        return f"[ERROR] HTTP {e.response.status_code}: {url}"
    except Exception as e:
        return f"[ERROR] Failed to fetch: {type(e).__name__}: {str(e)}"


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
    bash_background,
    bash_output,
    kill_shell,
    web_search,
    web_fetch,
]
