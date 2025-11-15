"""
Version 1: OpenAI API를 사용한 기본 구현

Claude Code의 핵심 아키텍처:
1. 사용자 입력 → LLM 요청
2. stop_reason 처리:
   - tool_calls: 도구 실행 후 루프 계속
   - stop: 사용자에게 응답 표시
3. messages는 append-only (삭제/수정 금지)
4. 스트리밍으로 실시간 응답 표시
5. Task 도구는 subagent.py로 특별 처리
"""

import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .subagent import execute_subagent
from .system_prompt import get_system_prompt
from .tools import TOOLS, execute_tool
from .types import TaskInput, ToolResult

# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화 (AsyncOpenAI!)
# Supports Anthropic API via base_url
client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")  # For Anthropic: https://api.anthropic.com/v1/
)

# Rich console
console = Console()

# Prompt session (async 지원)
prompt_session = PromptSession(history=InMemoryHistory())


def display_message(role: str, content: str):
    """메시지를 Rich 포맷으로 표시"""
    if role == "assistant":
        console.print(Panel(Markdown(content), title="[bold blue]Assistant[/bold blue]", border_style="blue"))
    elif role == "user":
        console.print(Panel(content, title="[bold green]You[/bold green]", border_style="green"))
    elif role == "system":
        console.print(Panel(content, title="[bold yellow]System[/bold yellow]", border_style="yellow"))
    elif role == "tool":
        console.print(
            Panel(
                content[:500] + "..." if len(content) > 500 else content,
                title="[bold cyan]Tool Result[/bold cyan]",
                border_style="cyan",
            )
        )


def display_tool_use(tool_name: str, tool_input: Dict[str, Any]):
    """도구 사용을 표시"""
    console.print(f"\n[bold cyan]🔧 Using tool:[/bold cyan] {tool_name}")
    # 너무 긴 입력은 생략
    input_str = json.dumps(tool_input, indent=2, ensure_ascii=False)
    if len(input_str) > 300:
        input_str = input_str[:300] + "\n  ...\n}"
    console.print(f"[dim]{input_str}[/dim]")


def display_tool_result(tool_result: ToolResult):
    """도구 결과를 표시"""
    if tool_result.is_error:
        console.print(f"[bold red]❌ Tool failed:[/bold red] {tool_result.tool_name}")
        console.print(f"[red]{tool_result.result}[/red]\n")
    else:
        console.print(f"[bold green]✅ Tool completed:[/bold green] {tool_result.tool_name}")
        # 결과가 너무 길면 첫 500자만 표시
        display_result = tool_result.result[:500] + "..." if len(tool_result.result) > 500 else tool_result.result
        console.print(f"[dim]{display_result}[/dim]\n")


async def stream_assistant_response(
    messages: List[Dict[str, Any]], system_prompt: str, model: str = "claude-haiku-4-5"
) -> Dict[str, Any]:
    """
    스트리밍으로 어시스턴트 응답 처리

    Returns:
        완성된 assistant 메시지 (content + tool_calls)
    """
    console.print("\n[bold blue]Assistant:[/bold blue]", end=" ")

    collected_content = ""
    collected_tool_calls = []
    finish_reason = None

    try:
        # AsyncOpenAI 스트리밍 API (수동 방식 - auto-parsing 방지)
        stream = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, *messages],
            tools=TOOLS,  # TOOLS는 이미 올바른 형식!
            temperature=0.7,
            max_tokens=4096,
            stream=True,
        )

        async for chunk in stream:
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            # Content 스트리밍 (실시간 출력을 위해 Python print 사용)
            if delta.content:
                print(delta.content, end="", flush=True)
                collected_content += delta.content

            # Tool calls 수집
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    # tool_calls 배열 확장
                    while len(collected_tool_calls) <= tc_delta.index:
                        collected_tool_calls.append(
                            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                        )

                    # ID 설정
                    if tc_delta.id:
                        collected_tool_calls[tc_delta.index]["id"] = tc_delta.id

                    # Function 정보 수집
                    if tc_delta.function:
                        if tc_delta.function.name:
                            collected_tool_calls[tc_delta.index]["function"]["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            collected_tool_calls[tc_delta.index]["function"][
                                "arguments"
                            ] += tc_delta.function.arguments

            # finish_reason 저장
            if choice.finish_reason:
                finish_reason = choice.finish_reason

        print()  # 줄바꿈

        # Assistant 메시지 구성
        assistant_message = {"role": "assistant", "content": collected_content or ""}

        if collected_tool_calls:
            assistant_message["tool_calls"] = collected_tool_calls

        assistant_message["_finish_reason"] = finish_reason  # 내부 플래그

        return assistant_message

    except Exception as e:
        console.print(f"\n[red]Streaming error: {e}[/red]")
        return {"role": "assistant", "content": f"Error during streaming: {str(e)}", "_finish_reason": "error"}


# ============================================================================
# Helper Functions (Extracted for Readability)
# ============================================================================


async def get_user_input() -> Optional[str]:
    """Get user input with keyboard interrupt handling.

    Returns:
        User input string, or None if interrupted (exit signal)
    """
    try:
        user_input = await prompt_session.prompt_async("\n> ")
        return user_input
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Goodbye![/yellow]")
        return None


async def handle_command(command: str, messages: List[Dict[str, Any]], system_prompt: str) -> bool:
    """Handle special commands (quit, clear, debug).

    Returns:
        True if should continue processing, False if should skip to next input
    """
    cmd_lower = command.lower()

    if cmd_lower == "quit":
        console.print("[yellow]Goodbye![/yellow]")
        return False

    if cmd_lower == "clear":
        messages.clear()
        console.print("[yellow]History cleared![/yellow]")
        return False

    if cmd_lower == "debug":
        console.print(f"[yellow]Messages: {len(messages)}[/yellow]")
        console.print(f"[yellow]System prompt length: {len(system_prompt)} chars[/yellow]")
        return False

    if not command.strip():
        return False

    return True


async def execute_single_tool_call(tool_call: Dict[str, Any], system_prompt: str) -> Dict[str, Any]:
    """Execute a single tool call (Task or regular tool).

    Returns:
        Tool result message dict with role='tool'
    """
    tool_name = tool_call["function"]["name"]

    # Parse tool input
    try:
        tool_input = json.loads(tool_call["function"]["arguments"])
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON decode error: {e}[/red]")
        tool_input = {}

    display_tool_use(tool_name, tool_input)

    # Task tool: Launch subagent
    if tool_name == "Task":
        try:
            task_input = TaskInput(**tool_input)

            console.print(f"[bold magenta]🚀 Launching subagent:[/bold magenta] {task_input.subagent_type.value}")
            console.print(f"[dim]{task_input.description}[/dim]\n")

            # Execute subagent
            with console.status("[bold magenta]Subagent working...[/bold magenta]", spinner="dots"):
                subagent_report = await execute_subagent(
                    client=client, task_input=task_input, system_prompt=system_prompt, current_depth=0, max_depth=5
                )

            console.print(f"[bold green]📋 Subagent report:[/bold green]")
            console.print(
                Panel(
                    Markdown(subagent_report[:1000] + "..." if len(subagent_report) > 1000 else subagent_report),
                    border_style="green",
                )
            )

            return {"role": "tool", "tool_call_id": tool_call["id"], "content": subagent_report}

        except Exception as e:
            error_msg = f"Subagent failed: {type(e).__name__}: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            return {"role": "tool", "tool_call_id": tool_call["id"], "content": error_msg}

    # Regular tool execution
    else:
        try:
            tool_result = await execute_tool(tool_name, tool_input)
            display_tool_result(tool_result)

            return {"role": "tool", "tool_call_id": tool_call["id"], "content": tool_result.result}

        except Exception as e:
            error_msg = f"Error: {type(e).__name__}: {str(e)}"
            console.print(f"[red]{error_msg}[/red]")
            return {"role": "tool", "tool_call_id": tool_call["id"], "content": error_msg}


async def process_turn_loop(messages: List[Dict[str, Any]], system_prompt: str, max_turns: int = 50) -> None:
    """Process tool usage loop until stop.

    Claude Code's core: Continues calling LLM until finish_reason is 'stop'
    """
    turn_count = 0

    while turn_count < max_turns:
        turn_count += 1

        try:
            # Stream assistant response
            assistant_message = await stream_assistant_response(
                messages=messages, system_prompt=system_prompt, model="claude-haiku-4-5"
            )

            finish_reason = assistant_message.pop("_finish_reason", "stop")
            messages.append(assistant_message)

            # Handle finish_reason
            if finish_reason == "stop":
                break

            elif finish_reason == "tool_calls":
                tool_calls = assistant_message.get("tool_calls", [])
                if not tool_calls:
                    console.print("[yellow]Warning: tool_calls finish_reason but no tool_calls found[/yellow]")
                    break

                # Execute all tool calls
                tool_results = [await execute_single_tool_call(tool_call, system_prompt) for tool_call in tool_calls]

                messages.extend(tool_results)
                continue

            elif finish_reason == "length":
                console.print("[red]⚠ Response truncated (max tokens exceeded)[/red]")
                break

            elif finish_reason == "error":
                console.print("[red]⚠ Error during API call[/red]")
                break

            else:
                console.print(f"[yellow]Unknown finish_reason: {finish_reason}[/yellow]")
                break

        except Exception as e:
            console.print(f"[red]Error in conversation loop: {type(e).__name__}: {str(e)}[/red]")
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            break

    if turn_count >= max_turns:
        console.print(f"[yellow]⚠ Max turns ({max_turns}) exceeded[/yellow]")


async def run_conversation_loop():
    """Main conversation loop (refactored for readability)."""
    messages: List[Dict[str, Any]] = []
    system_prompt = get_system_prompt(os.getcwd())

    # Welcome message
    console.print(
        Panel(
            "[bold]Custom Claude Code - Version 1: OpenAI API[/bold]\n\n"
            "✨ Features:\n"
            "  - 16 tools (Read, Write, Edit, Bash, Glob, Grep, etc.)\n"
            "  - Subagent system (Task tool with recursive execution)\n"
            "  - Streaming responses\n"
            "  - Claude Code original system prompt\n\n"
            "Commands:\n"
            "  - Type 'quit' to exit\n"
            "  - Type 'clear' to clear history\n"
            "  - Type 'debug' to show message count",
            title="Welcome",
            border_style="magenta",
        )
    )

    # Main loop
    while True:
        # Get user input
        user_input = await get_user_input()
        if user_input is None:  # Interrupted (quit)
            break

        # Handle commands
        if not await handle_command(user_input, messages, system_prompt):
            if user_input.lower() == "quit":
                break
            continue

        # Add user message
        messages.append({"role": "user", "content": user_input})

        # Process turn loop (tool usage)
        await process_turn_loop(messages, system_prompt)


async def main():
    """메인 함수"""
    await run_conversation_loop()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
