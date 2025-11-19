"""
도구 정의 및 실행 (10개 도구)

OpenAI 최신 패턴:
- Pydantic 기반 검증
- Async/await
- 타입 힌팅 강화
"""

import os
import subprocess
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from glob import glob as python_glob
import re

from .types import (
    ReadInput, WriteInput, EditInput, BashInput,
    GlobInput, GrepInput, TodoWriteInput, TaskInput,
    ExitPlanModeInput, AskUserQuestionInput,
    NotebookEditInput, BashBackgroundInput, BashOutputInput, KillShellInput,
    WebSearchInput, WebFetchInput, SlashCommandInput,
    ToolResult
)


# ============================================================================
# 백그라운드 프로세스 관리 (v2.1 feature)
# ============================================================================

BACKGROUND_PROCESSES: Dict[str, subprocess.Popen] = {}


# ============================================================================
# 도구 스키마 정의 (OpenAI function calling format)
# ============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "Read",
            "description": "Read a file from the filesystem. Returns file contents with line numbers (cat -n style).",
            "parameters": ReadInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Write",
            "description": "Write content to a file (creates or overwrites). Creates parent directories if needed.",
            "parameters": WriteInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Edit",
            "description": "Edit a file by replacing old_string with new_string. old_string must be exact match.",
            "parameters": EditInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Bash",
            "description": "Execute a bash command. Dangerous commands are blocked for safety.",
            "parameters": BashInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Glob",
            "description": "Find files matching a glob pattern (e.g., '**/*.ts'). Fast file pattern matching.",
            "parameters": GlobInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Grep",
            "description": "Search for regex pattern in files. Supports filtering by glob pattern.",
            "parameters": GrepInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "TodoWrite",
            "description": "Update the todo list to track task progress. IMPORTANT: Use frequently!",
            "parameters": TodoWriteInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Task",
            "description": "Launch a subagent to handle complex, multi-step tasks autonomously. Types: general-purpose, Explore, Plan, statusline-setup.",
            "parameters": TaskInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ExitPlanMode",
            "description": "Exit plan mode with a finalized implementation plan. Only use in Plan agent.",
            "parameters": ExitPlanModeInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "AskUserQuestion",
            "description": "Ask the user questions during execution. Gather preferences, clarify ambiguity, get decisions.",
            "parameters": AskUserQuestionInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "NotebookEdit",
            "description": "Edit a Jupyter notebook (.ipynb file) cell. Supports replace, insert, delete modes.",
            "parameters": NotebookEditInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "BashBackground",
            "description": "Run a bash command in the background and return a shell ID for monitoring. Use for long-running commands like servers or watchers.",
            "parameters": BashBackgroundInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "BashOutput",
            "description": "Retrieve output from a running background bash shell. Returns new output since last check.",
            "parameters": BashOutputInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "KillShell",
            "description": "Kill a running background bash shell by its ID.",
            "parameters": KillShellInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "WebSearch",
            "description": "Search the web for up-to-date information. Returns search results.",
            "parameters": WebSearchInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "WebFetch",
            "description": "Fetch and process content from a URL. Converts HTML to markdown and extracts information.",
            "parameters": WebFetchInput.model_json_schema(),
        }
    },
    {
        "type": "function",
        "function": {
            "name": "SlashCommand",
            "description": "Execute a custom slash command (e.g., /help, /review-pr).",
            "parameters": SlashCommandInput.model_json_schema(),
        }
    },
]


# ============================================================================
# 도구 실행 함수들
# ============================================================================

async def tool_read(input_data: ReadInput) -> str:
    """
    파일 읽기

    Args:
        input_data: Pydantic validated input

    Returns:
        File contents with line numbers
    """
    # 절대 경로 검증
    if not os.path.isabs(input_data.file_path):
        raise ValueError(
            f"File path must be absolute. Got: {input_data.file_path}\n"
            f"Example: /Users/user/project/file.txt"
        )

    # 파일 존재 확인
    if not os.path.exists(input_data.file_path):
        raise FileNotFoundError(
            f"File not found: {input_data.file_path}\n\n"
            f"Suggestions:\n"
            f"- Check if the path is correct\n"
            f"- Use Glob tool to find the file first\n"
            f"- Use Bash tool to list directory contents"
        )

    # 파일 읽기
    try:
        with open(input_data.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # Binary file
        return f"Error: {input_data.file_path} is a binary file. Cannot read as text."

    # offset/limit 처리
    if input_data.offset is not None:
        offset = max(0, input_data.offset - 1)  # 1-indexed to 0-indexed
        lines = lines[offset:]
    else:
        offset = 0

    if input_data.limit is not None:
        lines = lines[:input_data.limit]

    # 줄 번호 추가 (cat -n 스타일)
    numbered_lines = [
        f"{i+offset+1:6d}\t{line.rstrip()}"
        for i, line in enumerate(lines)
    ]

    return "\n".join(numbered_lines)


async def tool_write(input_data: WriteInput) -> str:
    """파일 쓰기"""
    # 절대 경로 검증
    if not os.path.isabs(input_data.file_path):
        raise ValueError(f"File path must be absolute. Got: {input_data.file_path}")

    # 부모 디렉토리 생성
    parent_dir = os.path.dirname(input_data.file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # 파일 쓰기
    with open(input_data.file_path, 'w', encoding='utf-8') as f:
        f.write(input_data.content)

    return f"File written successfully: {input_data.file_path} ({len(input_data.content)} bytes)"


async def tool_edit(input_data: EditInput) -> str:
    """파일 편집 (문자열 교체)"""
    # 절대 경로 검증
    if not os.path.isabs(input_data.file_path):
        raise ValueError(f"File path must be absolute. Got: {input_data.file_path}")

    # 파일 존재 확인
    if not os.path.exists(input_data.file_path):
        raise FileNotFoundError(f"File not found: {input_data.file_path}")

    # 파일 읽기
    with open(input_data.file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # old_string 존재 확인
    if input_data.old_string not in content:
        raise ValueError(
            f"old_string not found in file.\n\n"
            f"Looking for:\n{input_data.old_string[:200]}...\n\n"
            f"Suggestion: Use Read tool to check file contents first"
        )

    # 고유성 검증
    count = content.count(input_data.old_string)
    if not input_data.replace_all and count > 1:
        raise ValueError(
            f"old_string appears {count} times in file.\n\n"
            f"Either:\n"
            f"1. Provide more context to make it unique\n"
            f"2. Use replace_all=true to replace all occurrences"
        )

    # 교체
    if input_data.replace_all:
        new_content = content.replace(input_data.old_string, input_data.new_string)
    else:
        new_content = content.replace(input_data.old_string, input_data.new_string, 1)

    # 파일 쓰기
    with open(input_data.file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return f"File edited successfully. Replaced {count if input_data.replace_all else 1} occurrence(s)."


async def tool_bash(input_data: BashInput) -> str:
    """Bash 명령 실행"""
    # 위험한 명령어 차단
    dangerous_commands = [
        "rm -rf /",
        "sudo rm",
        "mkfs",
        "> /dev/sda",
        "dd if=",
        ":(){ :|:& };:",  # fork bomb
    ]

    for dangerous in dangerous_commands:
        if dangerous in input_data.command:
            raise ValueError(
                f"Dangerous command blocked: {input_data.command}\n\n"
                f"This command could cause system damage."
            )

    try:
        # 명령 실행
        result = subprocess.run(
            input_data.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=input_data.timeout,
            cwd=os.getcwd()
        )

        # 출력 조합
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\n[stderr]\n{result.stderr}"

        # 종료 코드 추가
        if result.returncode != 0:
            output += f"\n\nExit code: {result.returncode}"

        return output or "(No output)"

    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"Command timed out after {input_data.timeout} seconds.\n\n"
            f"Command: {input_data.command}\n\n"
            f"Suggestion: Increase timeout or simplify command"
        )
    except Exception as e:
        raise RuntimeError(f"Command failed: {str(e)}")


async def tool_glob(input_data: GlobInput) -> str:
    """
    파일 패턴 검색 (glob)

    Examples:
        - "**/*.ts" - All TypeScript files recursively
        - "src/**/*.py" - All Python files in src/
        - "*.json" - All JSON files in current dir
    """
    search_path = input_data.path or os.getcwd()

    # 패턴 조합
    full_pattern = os.path.join(search_path, input_data.pattern)

    # Glob 실행
    matches = python_glob(full_pattern, recursive=True)

    if not matches:
        return f"No files matching pattern: {input_data.pattern}"

    # 결과 포맷팅
    matches.sort()
    result = f"Found {len(matches)} file(s):\n\n"
    for match in matches:
        # 상대 경로로 표시 (더 읽기 쉬움)
        rel_path = os.path.relpath(match, search_path)
        result += f"  {rel_path}\n"

    return result.rstrip()


async def tool_grep(input_data: GrepInput) -> str:
    """
    코드 검색 (grep with regex)

    Uses ripgrep-like pattern matching
    """
    # 검색 경로 설정
    search_path = input_data.path or os.getcwd()

    # ripgrep 스타일 명령 구성
    cmd_parts = ["grep", "-r", "-n"]  # recursive, line numbers

    if input_data.case_insensitive:
        cmd_parts.append("-i")

    # 패턴 추가
    cmd_parts.append(input_data.pattern)

    # 경로 추가
    cmd_parts.append(search_path)

    # Glob 필터 추가
    if input_data.glob:
        cmd_parts.extend(["--include", input_data.glob])

    try:
        result = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            return f"Found {len(lines)} match(es):\n\n{result.stdout}"
        elif result.returncode == 1:
            return f"No matches found for pattern: {input_data.pattern}"
        else:
            return f"Error: {result.stderr}"

    except FileNotFoundError:
        # grep not available, use Python implementation
        return await _python_grep(input_data, search_path)


async def _python_grep(input_data: GrepInput, search_path: str) -> str:
    """Python fallback for grep"""
    pattern = re.compile(
        input_data.pattern,
        re.IGNORECASE if input_data.case_insensitive else 0
    )

    matches = []

    # 파일 목록 가져오기
    if input_data.glob:
        files = python_glob(
            os.path.join(search_path, input_data.glob),
            recursive=True
        )
    else:
        files = []
        for root, _, filenames in os.walk(search_path):
            for filename in filenames:
                files.append(os.path.join(root, filename))

    # 각 파일 검색
    for filepath in files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if pattern.search(line):
                        rel_path = os.path.relpath(filepath, search_path)
                        matches.append(f"{rel_path}:{line_num}:{line.rstrip()}")
        except (UnicodeDecodeError, PermissionError):
            continue

    if not matches:
        return f"No matches found for pattern: {input_data.pattern}"

    return f"Found {len(matches)} match(es):\n\n" + "\n".join(matches[:100])


async def tool_todowrite(input_data: TodoWriteInput) -> str:
    """
    Todo 리스트 업데이트

    중요: 자주 사용해서 진행 상황 추적!
    """
    # Todo 리스트를 JSON으로 저장 (실제로는 메모리 또는 파일 시스템)
    todos_json = json.dumps(
        [todo.model_dump() for todo in input_data.todos],
        indent=2,
        ensure_ascii=False
    )

    # 현재 진행 중인 작업 확인
    in_progress_count = sum(1 for todo in input_data.todos if todo.status == "in_progress")

    if in_progress_count == 0:
        return "Warning: No task is in_progress! Mark one task as in_progress."
    elif in_progress_count > 1:
        return f"Warning: {in_progress_count} tasks are in_progress! Only one should be in_progress at a time."

    return f"Todo list updated successfully. {len(input_data.todos)} tasks total."


async def tool_task(input_data: TaskInput) -> str:
    """
    Subagent 실행

    NOTE: 실제 구현은 subagent.py에서 처리
    이 함수는 플레이스홀더 (메인 루프에서 특별 처리)
    """
    # 이 함수는 실제로는 호출되지 않음
    # execute_tool()에서 "Task"를 특별하게 처리
    raise NotImplementedError(
        "Task tool should be handled by main loop (see subagent.py)"
    )


async def tool_exitplanmode(input_data: ExitPlanModeInput) -> str:
    """
    Plan 모드 종료

    Plan Agent만 사용 가능
    """
    # Plan을 반환하고 Agent 종료 신호
    return f"[PLAN_COMPLETE]\n\n{input_data.plan}"


async def tool_askuserquestion(input_data: AskUserQuestionInput) -> str:
    """
    사용자에게 질문

    NOTE: 실제 구현은 메인 루프에서 처리 (대화형)
    """
    # 실제로는 메인 루프에서 사용자 입력을 받아야 함
    # 여기서는 플레이스홀더
    raise NotImplementedError(
        "AskUserQuestion should be handled by main loop (interactive)"
    )


async def tool_notebookedit(input_data: NotebookEditInput) -> str:
    """
    Jupyter notebook 편집

    NOTE: 간단한 구현 (실제 Claude Code는 더 복잡)
    """
    import json

    # Notebook 파일 읽기
    if not os.path.exists(input_data.notebook_path):
        raise FileNotFoundError(f"Notebook not found: {input_data.notebook_path}")

    with open(input_data.notebook_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)

    # Edit mode 처리
    if input_data.edit_mode == "insert":
        # 새 셀 삽입
        new_cell = {
            "cell_type": input_data.cell_type or "code",
            "source": input_data.new_source.split('\n'),
            "metadata": {},
            "outputs": [] if input_data.cell_type == "code" else None
        }
        # cell_id로 찾거나 마지막에 추가
        notebook["cells"].append(new_cell)

    elif input_data.edit_mode == "delete":
        # cell_id로 찾아서 삭제
        if input_data.cell_id:
            notebook["cells"] = [
                c for c in notebook["cells"]
                if c.get("id") != input_data.cell_id
            ]
    else:  # replace
        # cell_id로 찾아서 교체
        if input_data.cell_id:
            for cell in notebook["cells"]:
                if cell.get("id") == input_data.cell_id:
                    cell["source"] = input_data.new_source.split('\n')
                    if input_data.cell_type:
                        cell["cell_type"] = input_data.cell_type
                    break

    # Notebook 저장
    with open(input_data.notebook_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2)

    return f"Notebook edited successfully: {input_data.notebook_path}"


async def tool_bashbackground(input_data: BashBackgroundInput) -> str:
    """
    백그라운드에서 bash 명령 실행

    v2.1 feature: 백그라운드 프로세스 실행 및 shell_id 반환
    """
    shell_id = str(uuid.uuid4())[:8]

    try:
        proc = subprocess.Popen(
            input_data.command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.getcwd(),
            bufsize=1,
        )
        BACKGROUND_PROCESSES[shell_id] = proc

        desc_text = f" ({input_data.description})" if input_data.description else ""
        return f"✓ Started background process{desc_text}\nShell ID: {shell_id}\nUse BashOutput('{shell_id}') to check output"

    except Exception as e:
        return f"[ERROR] Failed to start background process: {type(e).__name__}: {str(e)}"


async def tool_bashoutput(input_data: BashOutputInput) -> str:
    """
    백그라운드 bash 출력 읽기

    v2.1 feature: shell_id로 프로세스 출력 확인
    """
    proc = BACKGROUND_PROCESSES.get(input_data.bash_id)

    if not proc:
        return f"[ERROR] Shell not found: {input_data.bash_id}\nAvailable shells: {list(BACKGROUND_PROCESSES.keys())}"

    try:
        poll_result = proc.poll()
        output_lines = []

        # stdout 읽기
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
                pass

        # Filter 적용
        if input_data.filter and output_lines:
            regex = re.compile(input_data.filter)
            output_lines = [line for line in output_lines if regex.search(line)]

        # 상태 정보
        if poll_result is None:
            status = "Running"
        else:
            status = f"Exited (code: {poll_result})"
            del BACKGROUND_PROCESSES[input_data.bash_id]

        result = f"Shell {input_data.bash_id} - {status}\n"
        if output_lines:
            result += "\n".join(output_lines)
        else:
            result += "(no new output)"

        return result

    except Exception as e:
        return f"[ERROR] Failed to read output: {type(e).__name__}: {str(e)}"


async def tool_killshell(input_data: KillShellInput) -> str:
    """
    백그라운드 bash 종료

    v2.1 feature: shell_id로 프로세스 종료
    """
    proc = BACKGROUND_PROCESSES.get(input_data.shell_id)

    if not proc:
        return f"[ERROR] Shell not found: {input_data.shell_id}\nAvailable shells: {list(BACKGROUND_PROCESSES.keys())}"

    try:
        proc.kill()
        proc.wait(timeout=5)
        del BACKGROUND_PROCESSES[input_data.shell_id]
        return f"✓ Killed shell: {input_data.shell_id}"

    except subprocess.TimeoutExpired:
        proc.kill()
        del BACKGROUND_PROCESSES[input_data.shell_id]
        return f"✓ Force killed shell: {input_data.shell_id}"

    except Exception as e:
        return f"[ERROR] Failed to kill shell: {type(e).__name__}: {str(e)}"


async def tool_websearch(input_data: WebSearchInput) -> str:
    """
    웹 검색 (DuckDuckGo)

    v2.1 feature: DuckDuckGo를 사용한 실제 웹 검색
    """
    try:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(input_data.query, max_results=5):
                results.append(f"**[{r['title']}]({r['href']})**\n{r['body']}\n")

        if not results:
            return f"No results found for: {input_data.query}"

        return f"Search results for '{input_data.query}':\n\n" + "\n---\n\n".join(results)

    except ImportError:
        return "[ERROR] ddgs package not installed. Run: uv add ddgs"
    except Exception as e:
        return f"[ERROR] Search failed: {type(e).__name__}: {str(e)}"


async def tool_webfetch(input_data: WebFetchInput) -> str:
    """
    URL 가져오기 (BeautifulSoup)

    v2.1 feature: 스마트 콘텐츠 추출 및 구조 보존
    """
    try:
        import httpx
        from bs4 import BeautifulSoup

        # Fetch content
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            response = await client.get(input_data.url)
            response.raise_for_status()

        # Parse HTML
        soup = BeautifulSoup(response.text, "html.parser")

        # Remove unwanted elements
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

        # Extract text with structure
        def extract_structured_text(element):
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
                    elif child.name in ["li"]:
                        li_text = child.get_text(strip=True)
                        if li_text:
                            lines.append(f"- {li_text}")
                    elif child.name not in ["script", "style"]:
                        lines.extend(extract_structured_text(child))

            return lines

        content_lines = extract_structured_text(main_content)
        clean_text = "\n".join(content_lines)
        clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()

        # Smart truncation
        max_length = 15000
        if len(clean_text) > max_length:
            truncate_point = clean_text.rfind('\n\n', 0, max_length)
            if truncate_point > max_length * 0.8:
                clean_text = clean_text[:truncate_point]
            else:
                truncate_point = clean_text.rfind('. ', 0, max_length)
                if truncate_point > max_length * 0.8:
                    clean_text = clean_text[:truncate_point + 1]
                else:
                    clean_text = clean_text[:max_length]

            clean_text += "\n\n[Content truncated. Use prompt parameter to request specific information.]"

        title = soup.title.string if soup.title else "No title"
        result = f"**URL**: {input_data.url}\n**Title**: {title}\n**Task**: {input_data.prompt}\n\n**Content**:\n\n{clean_text}"

        if len(result) > 20000:
            result = result[:20000] + "\n\n[Note: Content is extensive. Refine your prompt for specific information.]"

        return result

    except ImportError:
        return "[ERROR] Required packages not installed. Run: uv add httpx beautifulsoup4"
    except httpx.HTTPStatusError as e:
        return f"[ERROR] HTTP {e.response.status_code}: {input_data.url}"
    except Exception as e:
        return f"[ERROR] Failed to fetch URL: {type(e).__name__}: {str(e)}"


async def tool_slashcommand(input_data: SlashCommandInput) -> str:
    """
    슬래시 커맨드 실행

    NOTE: 실제 구현은 커맨드 파일 시스템 필요
    """
    # 간단한 구현
    if input_data.command == "/help":
        return """Available commands:
- /help - Show this help
- /clear - Clear conversation history
- /quit - Exit the program

For custom commands, create .claude/commands/ files."""
    else:
        return f"[PLACEHOLDER] SlashCommand '{input_data.command}' not implemented.\n\nCreate custom commands in .claude/commands/ directory."


# ============================================================================
# 도구 실행 디스패처
# ============================================================================

# ============================================================================
# Tool Registry Pattern (Simple and Extensible!)
# ============================================================================

# Mapping of tool names to (InputClass, tool_function) pairs
TOOL_REGISTRY = {
    "Read": (ReadInput, tool_read),
    "Write": (WriteInput, tool_write),
    "Edit": (EditInput, tool_edit),
    "Bash": (BashInput, tool_bash),
    "Glob": (GlobInput, tool_glob),
    "Grep": (GrepInput, tool_grep),
    "TodoWrite": (TodoWriteInput, tool_todowrite),
    "ExitPlanMode": (ExitPlanModeInput, tool_exitplanmode),
    "NotebookEdit": (NotebookEditInput, tool_notebookedit),
    "BashBackground": (BashBackgroundInput, tool_bashbackground),
    "BashOutput": (BashOutputInput, tool_bashoutput),
    "KillShell": (KillShellInput, tool_killshell),
    "WebSearch": (WebSearchInput, tool_websearch),
    "WebFetch": (WebFetchInput, tool_webfetch),
    "SlashCommand": (SlashCommandInput, tool_slashcommand),
}

# Tools that need special handling in the main loop
SPECIAL_TOOLS = {"Task", "AskUserQuestion"}


async def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> ToolResult:
    """
    Execute a tool using the registry pattern.

    96 lines of if-elif reduced to 30 lines with registry pattern!

    Args:
        tool_name: Tool name
        tool_input: Tool input (will be validated by Pydantic)

    Returns:
        ToolResult with result or error
    """
    # Special tools handled by main loop
    if tool_name in SPECIAL_TOOLS:
        raise NotImplementedError(f"{tool_name} handled by main loop")

    # Unknown tool
    if tool_name not in TOOL_REGISTRY:
        return ToolResult(
            tool_name=tool_name,
            result=f"Unknown tool: {tool_name}",
            is_error=True
        )

    # Execute tool via registry
    try:
        input_class, tool_func = TOOL_REGISTRY[tool_name]
        input_obj = input_class(**tool_input)
        result = await tool_func(input_obj)
        return ToolResult(tool_name=tool_name, result=result)

    except Exception as e:
        error_msg = f"Error: {type(e).__name__}: {str(e)}"
        return ToolResult(tool_name=tool_name, result=error_msg, is_error=True)
