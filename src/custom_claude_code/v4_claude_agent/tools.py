"""
v4: Claude Agent SDK - Custom Tools

Custom tools defined using @tool decorator:
- Background process management (v2.1 feature)
- Web access tools (v2.1 feature)
"""

import os
import subprocess
import uuid
import re
from typing import Any, Dict
from claude_agent_sdk import tool

# Background process management (v2.1 feature)
BACKGROUND_PROCESSES: Dict[str, subprocess.Popen] = {}


# ============================================================================
# Background Execution Tools (v2.1 feature)
# ============================================================================


@tool("bash_background", "Run a bash command in the background", {"command": str, "description": str})
async def bash_background(args: dict[str, Any]) -> dict[str, Any]:
    """
    Run a bash command in the background.

    Args:
        command: Bash command to execute
        description: Short description of what this command does
    """
    command = args["command"]
    description = args.get("description", "")
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
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"✓ Started background process{desc_text}\nShell ID: {shell_id}\nUse bash_output('{shell_id}') to check output",
                }
            ]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"[ERROR] Failed to start: {type(e).__name__}: {str(e)}"}],
            "is_error": True,
        }


@tool("bash_output", "Get output from a background shell", {"shell_id": str, "filter": str})
async def bash_output(args: dict[str, Any]) -> dict[str, Any]:
    """
    Get output from a background shell.

    Args:
        shell_id: Background shell ID
        filter: Optional regex filter
    """
    shell_id = args["shell_id"]
    filter_pattern = args.get("filter")

    proc = BACKGROUND_PROCESSES.get(shell_id)

    if not proc:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"[ERROR] Shell not found: {shell_id}\nAvailable: {list(BACKGROUND_PROCESSES.keys())}",
                }
            ],
            "is_error": True,
        }

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
        if filter_pattern and output_lines:
            regex = re.compile(filter_pattern)
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

        return {"content": [{"type": "text", "text": result}]}

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"[ERROR] Failed to read: {type(e).__name__}: {str(e)}"}],
            "is_error": True,
        }


@tool("kill_shell", "Kill a background shell", {"shell_id": str})
async def kill_shell(args: dict[str, Any]) -> dict[str, Any]:
    """
    Kill a background shell.

    Args:
        shell_id: Shell ID to kill
    """
    shell_id = args["shell_id"]
    proc = BACKGROUND_PROCESSES.get(shell_id)

    if not proc:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"[ERROR] Shell not found: {shell_id}\nAvailable: {list(BACKGROUND_PROCESSES.keys())}",
                }
            ],
            "is_error": True,
        }

    try:
        proc.kill()
        proc.wait(timeout=5)
        del BACKGROUND_PROCESSES[shell_id]
        return {"content": [{"type": "text", "text": f"✓ Killed shell: {shell_id}"}]}

    except subprocess.TimeoutExpired:
        proc.kill()
        del BACKGROUND_PROCESSES[shell_id]
        return {"content": [{"type": "text", "text": f"✓ Force killed shell: {shell_id}"}]}

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"[ERROR] Failed to kill: {type(e).__name__}: {str(e)}"}],
            "is_error": True,
        }


# ============================================================================
# Web Access Tools (v2.1 feature)
# ============================================================================


@tool("web_search", "Search the web using DuckDuckGo", {"query": str, "max_results": int})
async def web_search(args: dict[str, Any]) -> dict[str, Any]:
    """
    Search the web using DuckDuckGo.

    Args:
        query: Search query
        max_results: Maximum results (default: 5)
    """
    query = args["query"]
    max_results = args.get("max_results", 5)

    try:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"**[{r['title']}]({r['href']})**\n{r['body']}\n")

        if not results:
            return {"content": [{"type": "text", "text": f"No results found for: {query}"}]}

        return {"content": [{"type": "text", "text": f"Search results for '{query}':\n\n" + "\n---\n\n".join(results)}]}

    except ImportError:
        return {
            "content": [{"type": "text", "text": "[ERROR] ddgs not installed. Run: uv add ddgs"}],
            "is_error": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"[ERROR] Search failed: {type(e).__name__}: {str(e)}"}],
            "is_error": True,
        }


@tool("web_fetch", "Fetch and analyze content from a URL", {"url": str, "prompt": str})
async def web_fetch(args: dict[str, Any]) -> dict[str, Any]:
    """
    Fetch and analyze content from a URL.

    Args:
        url: URL to fetch
        prompt: What to extract from the page
    """
    url = args["url"]
    prompt = args.get("prompt", "Summarize the main content")

    try:
        import httpx
        from bs4 import BeautifulSoup

        # Fetch (sync version for v4)
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

        return {"content": [{"type": "text", "text": result}]}

    except ImportError:
        return {
            "content": [
                {"type": "text", "text": "[ERROR] httpx or beautifulsoup4 not installed. Run: uv add httpx beautifulsoup4"}
            ],
            "is_error": True,
        }
    except httpx.HTTPStatusError as e:
        return {
            "content": [{"type": "text", "text": f"[ERROR] HTTP {e.response.status_code}: {url}"}],
            "is_error": True,
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"[ERROR] Failed to fetch: {type(e).__name__}: {str(e)}"}],
            "is_error": True,
        }


# ============================================================================
# Tool List
# ============================================================================

CUSTOM_TOOLS = [
    bash_background,
    bash_output,
    kill_shell,
    web_search,
    web_fetch,
]
