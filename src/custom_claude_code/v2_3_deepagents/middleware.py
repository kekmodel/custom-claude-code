"""
v2.3: DeepAgents 커스텀 미들웨어

DeepAgents의 AgentMiddleware를 상속받아 커스텀 도구들을 제공합니다.
- ExecutionMiddleware: bash 실행 도구
- SearchMiddleware: grep_code 검색 도구
- WebMiddleware: 웹 검색/페치 도구
"""

import fnmatch
import os
import subprocess
import uuid
from typing import Dict, Optional

from langchain_core.tools import tool
from langchain.agents.middleware import AgentMiddleware

# 백그라운드 프로세스 관리
BACKGROUND_PROCESSES: Dict[str, subprocess.Popen] = {}

# web_fetch 설정
REMOVE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]
CONTENT_SELECTORS = [
    "article", "main", "[role='main']",
    "#content", "#main-content", ".content", ".main-content"
]
MAX_CONTENT_LENGTH = 30000  # ~7,500 tokens

# 위험한 명령어 패턴
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",  # fork bomb
    "> /dev/sda",
    "chmod -R 777 /",
    "chown -R",
    "curl | sh",
    "curl | bash",
    "wget | sh",
    "wget | bash",
]

# ripgrep 타입 → 확장자 매핑 (fallback용)
TYPE_EXTENSIONS: Dict[str, str] = {
    "py": "*.py",
    "js": "*.js",
    "ts": "*.ts",
    "rust": "*.rs",
    "go": "*.go",
    "java": "*.java",
    "c": "*.c",
    "cpp": "*.cpp",
    "h": "*.h",
    "html": "*.html",
    "css": "*.css",
    "json": "*.json",
    "yaml": "*.yaml",
    "yml": "*.yml",
    "md": "*.md",
    "sh": "*.sh",
    "sql": "*.sql",
    "xml": "*.xml",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bash 실행 도구
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(parse_docstring=True)
def run_bash(command: str, timeout: Optional[int] = None) -> str:
    """Executes a given bash command in a persistent shell session with optional timeout.

    IMPORTANT: This tool is for terminal operations like git, npm, docker, etc.
    DO NOT use it for file operations - use DeepAgents built-in filesystem tools instead.

    Usage notes:
    - The command argument is required
    - Timeout in milliseconds (max 600000ms / 10 minutes). Default: 120000ms (2 minutes)
    - Use '&&' to chain dependent commands
    - Use absolute paths to avoid directory issues

    Args:
        command: The command to execute
        timeout: Optional timeout in milliseconds (max 600000). Defaults to 120000ms

    Returns:
        Command output (stdout + stderr)
    """
    timeout_seconds = (timeout / 1000) if timeout else 120

    # Safety check
    if any(danger in command for danger in DANGEROUS_PATTERNS):
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


@tool(parse_docstring=True)
def bash_background(command: str, description: str = "") -> str:
    """Run a bash command in the background and return a shell ID for monitoring.

    Use this for long-running commands like servers, watchers, or build processes.
    Use bash_output() to check the output and kill_shell() to stop the process.

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
            bufsize=1,
        )
        BACKGROUND_PROCESSES[shell_id] = proc

        desc_text = f" ({description})" if description else ""
        return f"✓ Started background process{desc_text}\nShell ID: {shell_id}\nUse bash_output('{shell_id}') to check output"

    except Exception as e:
        return f"[ERROR] Failed to start background process: {type(e).__name__}: {str(e)}"


def _read_stream_nonblocking(stream, prefix: str = "") -> list[str]:
    """Non-blocking으로 스트림에서 라인 읽기"""
    import select

    lines = []
    try:
        while select.select([stream], [], [], 0)[0]:
            line = stream.readline()
            if not line:
                break
            lines.append(f"{prefix}{line.rstrip()}" if prefix else line.rstrip())
    except (IOError, OSError, ValueError):
        pass
    return lines


@tool(parse_docstring=True)
def bash_output(shell_id: str, filter: Optional[str] = None) -> str:
    """Retrieve output from a background bash shell.

    Args:
        shell_id: The ID of the background shell to retrieve output from
        filter: Optional regex to filter output lines

    Returns:
        stdout and stderr output along with shell status
    """
    proc = BACKGROUND_PROCESSES.get(shell_id)

    if not proc:
        return f"[ERROR] Shell not found: {shell_id}\nAvailable: {list(BACKGROUND_PROCESSES.keys())}"

    try:
        poll_result = proc.poll()
        output_lines = []

        # Non-blocking read
        if proc.stdout:
            output_lines.extend(_read_stream_nonblocking(proc.stdout))
        if proc.stderr:
            output_lines.extend(_read_stream_nonblocking(proc.stderr, "[stderr] "))

        # Apply filter
        if filter and output_lines:
            import re
            regex = re.compile(filter)
            output_lines = [line for line in output_lines if regex.search(line)]

        if poll_result is None:
            status = "Running"
        else:
            status = f"Exited (code: {poll_result})"
            del BACKGROUND_PROCESSES[shell_id]

        result = f"Shell {shell_id} - {status}\n"
        result += "\n".join(output_lines) if output_lines else "(no new output)"
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
        return f"[ERROR] Failed to kill shell: {type(e).__name__}: {str(e)}"


class ExecutionMiddleware(AgentMiddleware):
    """Bash 실행 도구를 제공하는 미들웨어"""

    name = "ExecutionMiddleware"
    tools = [run_bash, bash_background, bash_output, kill_shell]
    system_prompt = """## Execution Tools

You have access to bash execution tools:
- run_bash: Execute bash commands (2 min timeout)
- bash_background: Run long-running commands in background
- bash_output: Check background process output
- kill_shell: Kill background processes

Background Workflow:
1. bash_background("npm run dev") → get shell_id
2. bash_output(shell_id) → check output
3. kill_shell(shell_id) → stop process"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 코드 검색 도구
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@tool(parse_docstring=True)
def grep_code(
    pattern: str,
    path: Optional[str] = None,
    glob: Optional[str] = None,
    output_mode: str = "files_with_matches",
    file_type: Optional[str] = None,
    i: bool = False,
    n: bool = True,
    A: Optional[int] = None,
    B: Optional[int] = None,
    C: Optional[int] = None,
    head_limit: Optional[int] = None,
    multiline: bool = False,
) -> str:
    """A powerful search tool built on ripgrep.

    Usage:
    - ALWAYS use grep_code for search tasks
    - Supports full regex syntax
    - Filter files with glob or file_type parameter

    Args:
        pattern: Regex pattern to search for
        path: Directory to search (defaults to cwd)
        glob: Glob pattern to filter files (e.g., "*.py")
        output_mode: "content", "files_with_matches" (default), or "count"
        file_type: File type (e.g., "js", "py", "rust")
        i: Case insensitive search
        n: Show line numbers (default: true)
        A: Lines after match
        B: Lines before match
        C: Lines around match
        head_limit: Limit output entries
        multiline: Enable multiline mode

    Returns:
        Search results
    """
    search_path = path or os.getcwd()

    try:
        cmd = ["rg"]

        if output_mode == "files_with_matches":
            cmd.append("--files-with-matches")
        elif output_mode == "count":
            cmd.append("--count")

        if i:
            cmd.append("-i")

        if output_mode == "content" and n:
            cmd.append("-n")

        if output_mode == "content":
            if C is not None:
                cmd.extend(["-C", str(C)])
            else:
                if A is not None:
                    cmd.extend(["-A", str(A)])
                if B is not None:
                    cmd.extend(["-B", str(B)])

        if file_type:
            cmd.extend(["--type", file_type])

        if glob:
            cmd.extend(["--glob", glob])

        if multiline:
            cmd.extend(["-U", "--multiline-dotall"])

        cmd.append(pattern)
        cmd.append(search_path)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout if result.stdout else "No matches found"

        if output != "No matches found" and head_limit is not None:
            lines = output.splitlines()
            output = "\n".join(lines[:head_limit])

        return output

    except FileNotFoundError:
        # Fallback to Python implementation
        import re

        flags = re.IGNORECASE if i else 0
        if multiline:
            flags |= re.DOTALL
        regex = re.compile(pattern, flags)

        # file_type → glob 변환
        file_glob = glob or TYPE_EXTENSIONS.get(file_type)

        matches = []
        for root, _, files in os.walk(search_path):
            for file in files:
                if file_glob and not fnmatch.fnmatch(file, file_glob):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        if regex.search(content):
                            if output_mode == "files_with_matches":
                                matches.append(file_path)
                            elif output_mode == "content":
                                lines_list = content.splitlines()
                                context_before = B if B is not None else (C if C is not None else 0)
                                context_after = A if A is not None else (C if C is not None else 0)
                                matched_ranges = set()

                                for line_num, line in enumerate(lines_list):
                                    if regex.search(line):
                                        start = max(0, line_num - context_before)
                                        end = min(len(lines_list), line_num + context_after + 1)
                                        for ctx_num in range(start, end):
                                            matched_ranges.add(ctx_num)

                                for line_num in sorted(matched_ranges):
                                    line = lines_list[line_num]
                                    if n:
                                        matches.append(f"{file_path}:{line_num + 1}:{line}")
                                    else:
                                        matches.append(f"{file_path}:{line}")
                            elif output_mode == "count":
                                count = len(regex.findall(content))
                                matches.append(f"{file_path}:{count}")
                except Exception:
                    continue

        if not matches:
            return "No matches found"

        if head_limit is not None:
            matches = matches[:head_limit]

        return "\n".join(matches)

    except subprocess.TimeoutExpired:
        raise TimeoutError("Search timed out after 30s")


class SearchMiddleware(AgentMiddleware):
    """코드 검색 도구를 제공하는 미들웨어"""

    name = "SearchMiddleware"
    tools = [grep_code]
    system_prompt = """## Search Tools

You have access to grep_code for powerful code search:
- Supports regex patterns
- Filter by file type or glob pattern
- Multiple output modes: content, files_with_matches, count

Example: grep_code("TODO", type="py", output_mode="content")"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 웹 접근 도구
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _sync_ddgs_search(query: str, max_results: int) -> list[str]:
    """동기 DuckDuckGo 검색 (to_thread용)"""
    from ddgs import DDGS

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            results.append(f"**[{r['title']}]({r['href']})**\n{r['body']}\n")
    return results


@tool(parse_docstring=True)
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return up-to-date information.

    Uses DuckDuckGo without requiring API keys.

    Args:
        query: The search query
        max_results: Maximum results (default: 5)

    Returns:
        Search results formatted as markdown
    """
    try:
        import asyncio

        results = await asyncio.to_thread(_sync_ddgs_search, query, max_results)

        if not results:
            return f"No results found for: {query}"

        return f"Search results for '{query}':\n\n" + "\n---\n\n".join(results)

    except ImportError:
        return "[ERROR] ddgs package not installed. Run: uv add ddgs"
    except Exception as e:
        return f"[ERROR] Search failed: {type(e).__name__}: {str(e)}"


@tool(parse_docstring=True)
async def web_fetch(url: str) -> str:
    """Fetch content from a URL and return as markdown.

    Retrieves HTML and extracts main content as readable text.

    Args:
        url: The URL to fetch (must be HTTP/HTTPS)

    Returns:
        Page content converted to markdown
    """
    try:
        import httpx
        from bs4 import BeautifulSoup
        import re

        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove unwanted elements
        for element in soup(REMOVE_TAGS):
            element.decompose()

        # Find main content
        main_content = None
        for selector in CONTENT_SELECTORS:
            main_content = soup.select_one(selector)
            if main_content:
                break
        if not main_content:
            main_content = soup.body or soup

        # Extract text
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
                        code_text = child.get_text(strip=True)
                        if code_text:
                            lines.append(f"\n```\n{code_text}\n```\n")
                    elif child.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                        heading_text = child.get_text(strip=True)
                        if heading_text:
                            level = int(child.name[1])
                            lines.append(f"\n{'#' * level} {heading_text}\n")
                    elif child.name == "p":
                        p_text = child.get_text(strip=True)
                        if p_text:
                            lines.append(f"\n{p_text}\n")
                    elif child.name == "li":
                        li_text = child.get_text(strip=True)
                        if li_text:
                            lines.append(f"- {li_text}")
                    elif child.name in ["blockquote"]:
                        quote_text = child.get_text(strip=True)
                        if quote_text:
                            lines.append(f"\n> {quote_text}\n")
                    elif child.name not in ["script", "style"]:
                        lines.extend(extract_text(child))
            return lines

        content_lines = extract_text(main_content)
        clean_text = "\n".join(content_lines)
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()

        # Truncate if needed
        if len(clean_text) > MAX_CONTENT_LENGTH:
            truncate_point = clean_text.rfind('\n\n', 0, MAX_CONTENT_LENGTH)
            if truncate_point > MAX_CONTENT_LENGTH * 0.8:
                clean_text = clean_text[:truncate_point]
            else:
                clean_text = clean_text[:MAX_CONTENT_LENGTH]
            clean_text += "\n\n[Content truncated]"

        title = soup.title.string if soup.title else "No title"
        return f"**URL**: {url}\n**Title**: {title}\n\n{clean_text}"

    except ImportError:
        return "[ERROR] Required packages not installed. Run: uv add httpx beautifulsoup4"
    except Exception as e:
        return f"[ERROR] Failed to fetch URL: {type(e).__name__}: {str(e)}"


class WebMiddleware(AgentMiddleware):
    """웹 접근 도구를 제공하는 미들웨어"""

    name = "WebMiddleware"
    tools = [web_search, web_fetch]
    system_prompt = """## Web Access Tools

You have access to web tools:
- web_search: DuckDuckGo search (no API key needed)
- web_fetch: Fetch and parse URL content

Use web_search for finding documentation, error solutions, best practices.
Use web_fetch for reading specific pages, documentation, README files."""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 통합 미들웨어 목록
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def get_custom_middleware() -> list[AgentMiddleware]:
    """커스텀 미들웨어 목록 반환"""
    return [
        ExecutionMiddleware(),
        SearchMiddleware(),
        WebMiddleware(),
    ]


# 모든 커스텀 도구 목록 (직접 사용 시)
ALL_CUSTOM_TOOLS = [
    run_bash,
    bash_background,
    bash_output,
    kill_shell,
    grep_code,
    web_search,
    web_fetch,
]
