"""
🎯 Test v1 Only - Real Conversation
v1 버전만 테스트 (실시간 대화)
"""

import asyncio
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Load environment
load_dotenv()

console = Console()


async def main():
    """v1 버전 실제 대화 테스트"""
    console.print("\n" + "="*80, style="bold cyan")
    console.print("🚀 Testing v1: OpenAI API + Anthropic Claude Haiku 4.5", style="bold cyan")
    console.print("="*80 + "\n", style="bold cyan")

    from custom_claude_code.v1_openai.main import (
        stream_assistant_response,
        get_system_prompt,
        execute_tool,
    )

    # 대화 히스토리
    messages = []

    # ==================================================
    # Test 1: Simple greeting
    # ==================================================
    console.print(Panel("👤 User: Hello! Can you introduce yourself briefly?", border_style="green", title="Test 1"))

    messages.append({
        "role": "user",
        "content": "Hello! Can you introduce yourself briefly in 2-3 sentences?"
    })

    console.print("\n[dim]🤖 Thinking...[/dim]")

    result = await stream_assistant_response(
        messages=messages,
        system_prompt=get_system_prompt(),
        model="claude-haiku-4-5"
    )

    console.print()  # New line after streaming
    console.print(Panel(
        Markdown(result["content"]),
        title="[bold blue]✅ Assistant Response[/bold blue]",
        border_style="blue"
    ))

    messages.append({
        "role": "assistant",
        "content": result["content"]
    })

    # ==================================================
    # Test 2: Tool usage - Glob files
    # ==================================================
    await asyncio.sleep(1)
    console.print("\n" + "-"*80 + "\n", style="dim")
    console.print(Panel("👤 User: Find all Python files in the src directory", border_style="green", title="Test 2: Tool Usage"))

    messages.append({
        "role": "user",
        "content": "Find all Python files in the src directory using the Glob tool"
    })

    console.print("\n[dim]🤖 Thinking...[/dim]")

    result = await stream_assistant_response(
        messages=messages,
        system_prompt=get_system_prompt(),
        model="claude-haiku-4-5"
    )

    # Tool calls가 있으면 실행
    turn_count = 1
    max_turns = 5  # 무한 루프 방지

    while result.get("tool_calls") and turn_count < max_turns:
        console.print()  # New line
        console.print(f"[cyan]🔧 Turn {turn_count}: Using tools:[/cyan]")

        for tool_call in result["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            console.print(f"  → [yellow]{tool_name}[/yellow]")

        messages.append({
            "role": "assistant",
            "content": result.get("content", ""),
            "tool_calls": result["tool_calls"]
        })

        # 도구 실행
        for tool_call in result["tool_calls"]:
            console.print(f"\n[dim]⚙️  Executing {tool_call['function']['name']}...[/dim]")
            tool_result = await execute_tool(tool_call)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": tool_result
            })
            # 결과 미리보기 (짧게)
            preview = tool_result[:200] + "..." if len(tool_result) > 200 else tool_result
            console.print(f"[dim]   Result: {preview}[/dim]")

        # 도구 실행 후 다시 응답
        console.print("\n[dim]🤖 Processing results...[/dim]")
        result = await stream_assistant_response(
            messages=messages,
            system_prompt=get_system_prompt(),
            model="claude-haiku-4-5"
        )

        turn_count += 1

    console.print()  # New line
    console.print(Panel(
        Markdown(result["content"]),
        title="[bold blue]✅ Final Response[/bold blue]",
        border_style="blue"
    ))

    messages.append({
        "role": "assistant",
        "content": result["content"]
    })

    # ==================================================
    # Test 3: Complex task - Read a file
    # ==================================================
    await asyncio.sleep(1)
    console.print("\n" + "-"*80 + "\n", style="dim")
    console.print(Panel(
        "👤 User: Read the launcher.py file and tell me how many versions it supports",
        border_style="green",
        title="Test 3: File Reading"
    ))

    messages.append({
        "role": "user",
        "content": "Read the launcher.py file and tell me how many versions of Claude Code it supports"
    })

    console.print("\n[dim]🤖 Thinking...[/dim]")

    result = await stream_assistant_response(
        messages=messages,
        system_prompt=get_system_prompt(),
        model="claude-haiku-4-5"
    )

    # Tool calls 처리
    turn_count = 1
    while result.get("tool_calls") and turn_count < max_turns:
        console.print()
        console.print(f"[cyan]🔧 Turn {turn_count}: Using tools:[/cyan]")

        for tool_call in result["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            console.print(f"  → [yellow]{tool_name}[/yellow]")

        messages.append({
            "role": "assistant",
            "content": result.get("content", ""),
            "tool_calls": result["tool_calls"]
        })

        # 도구 실행
        for tool_call in result["tool_calls"]:
            console.print(f"\n[dim]⚙️  Executing {tool_call['function']['name']}...[/dim]")
            tool_result = await execute_tool(tool_call)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": tool_result
            })

        # 도구 실행 후 다시 응답
        console.print("\n[dim]🤖 Processing results...[/dim]")
        result = await stream_assistant_response(
            messages=messages,
            system_prompt=get_system_prompt(),
            model="claude-haiku-4-5"
        )

        turn_count += 1

    console.print()
    console.print(Panel(
        Markdown(result["content"]),
        title="[bold blue]✅ Final Response[/bold blue]",
        border_style="blue"
    ))

    # ==================================================
    # Summary
    # ==================================================
    console.print("\n" + "="*80, style="bold green")
    console.print("✅ v1 Conversation Test Complete!", style="bold green")
    console.print(f"   Total messages: {len(messages)}", style="green")
    console.print(f"   Model: claude-haiku-4-5 via Anthropic API", style="green")
    console.print("="*80 + "\n", style="bold green")


if __name__ == "__main__":
    asyncio.run(main())
