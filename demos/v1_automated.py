"""
🎬 Automated Live Demo
실제 사용자가 입력하는 것처럼 자동으로 대화를 시연
"""

import asyncio
import os
import json
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# Load environment
load_dotenv()

console = Console()


async def demo_v1():
    """v1 자동 데모"""
    console.print("\n" + "="*80, style="bold magenta")
    console.print("🎬 AUTOMATED DEMO: v1 + Anthropic Claude Haiku 4.5", style="bold magenta")
    console.print("="*80 + "\n", style="bold magenta")

    from custom_claude_code.v1_openai.main import (
        stream_assistant_response,
        get_system_prompt,
        execute_single_tool_call,
    )

    messages = []

    # Demo 1: Simple conversation
    console.print(Panel("👤 사용자: 안녕! 어떤 도구들을 사용할 수 있어?", border_style="green", title="데모 1: 소개"))
    await asyncio.sleep(0.5)

    messages.append({
        "role": "user",
        "content": "안녕! 어떤 도구들을 사용할 수 있어? 주요 도구 3-4개만 간단히 알려줘."
    })

    console.print("\n[dim]🤖 Assistant is thinking...[/dim]\n")
    await asyncio.sleep(0.3)

    result = await stream_assistant_response(
        messages=messages,
        system_prompt=get_system_prompt(),
        model="claude-haiku-4-5"
    )

    console.print()
    console.print(Panel(
        Markdown(result["content"]),
        title="[bold blue]✅ Response[/bold blue]",
        border_style="blue"
    ))

    messages.append({
        "role": "assistant",
        "content": result["content"]
    })

    # Demo 2: Using Glob tool
    await asyncio.sleep(2)
    console.print("\n" + "-"*80 + "\n", style="dim")
    console.print(Panel("👤 사용자: Glob 도구를 사용해서 현재 디렉토리의 모든 .md 파일을 찾아줘", border_style="green", title="데모 2: 도구 사용 (Glob)"))
    await asyncio.sleep(0.5)

    messages.append({
        "role": "user",
        "content": "Glob 도구를 사용해서 현재 디렉토리의 모든 .md 파일을 찾아줘"
    })

    console.print("\n[dim]🤖 Assistant is thinking...[/dim]\n")
    await asyncio.sleep(0.3)

    # First response (will have tool calls)
    result = await stream_assistant_response(
        messages=messages,
        system_prompt=get_system_prompt(),
        model="claude-haiku-4-5"
    )

    # Handle tool calls
    if result.get("tool_calls"):
        console.print("\n[cyan]🔧 Using tools:[/cyan]")
        for tool_call in result["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            console.print(f"  → [yellow]{tool_name}[/yellow]")

        messages.append({
            "role": "assistant",
            "content": result.get("content", ""),
            "tool_calls": result["tool_calls"]
        })

        # Execute tools
        for tool_call in result["tool_calls"]:
            tool_message = await execute_single_tool_call(tool_call, get_system_prompt())
            messages.append(tool_message)

        # Get final response
        console.print("\n[dim]🤖 Processing results...[/dim]\n")
        await asyncio.sleep(0.3)

        result = await stream_assistant_response(
            messages=messages,
            system_prompt=get_system_prompt(),
            model="claude-haiku-4-5"
        )

    console.print()
    console.print(Panel(
        Markdown(result["content"]),
        title="[bold blue]✅ Final Response[/bold blue]",
        border_style="blue"
    ))

    messages.append({
        "role": "assistant",
        "content": result["content"]
    })

    # Demo 3: Read file
    await asyncio.sleep(2)
    console.print("\n" + "-"*80 + "\n", style="dim")
    console.print(Panel("👤 사용자: launcher.py 파일을 읽고 한 문장으로 설명해줘", border_style="green", title="데모 3: 파일 읽기"))
    await asyncio.sleep(0.5)

    messages.append({
        "role": "user",
        "content": "launcher.py 파일을 읽고 한 문장으로 설명해줘"
    })

    console.print("\n[dim]🤖 Assistant is thinking...[/dim]\n")
    await asyncio.sleep(0.3)

    # First response
    result = await stream_assistant_response(
        messages=messages,
        system_prompt=get_system_prompt(),
        model="claude-haiku-4-5"
    )

    # Handle tool calls
    if result.get("tool_calls"):
        console.print("\n[cyan]🔧 Using tools:[/cyan]")
        for tool_call in result["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            console.print(f"  → [yellow]{tool_name}[/yellow]")

        messages.append({
            "role": "assistant",
            "content": result.get("content", ""),
            "tool_calls": result["tool_calls"]
        })

        # Execute tools
        for tool_call in result["tool_calls"]:
            tool_message = await execute_single_tool_call(tool_call, get_system_prompt())
            messages.append(tool_message)

        # Get final response
        console.print("\n[dim]🤖 Processing file contents...[/dim]\n")
        await asyncio.sleep(0.3)

        result = await stream_assistant_response(
            messages=messages,
            system_prompt=get_system_prompt(),
            model="claude-haiku-4-5"
        )

    console.print()
    console.print(Panel(
        Markdown(result["content"]),
        title="[bold blue]✅ Final Response[/bold blue]",
        border_style="blue"
    ))

    # Summary
    console.print("\n" + "="*80, style="bold green")
    console.print("✅ DEMO COMPLETE!", style="bold green")
    console.print(f"   Total messages: {len(messages)}", style="green")
    console.print(f"   Model: claude-haiku-4-5 (Anthropic API)", style="green")
    console.print(f"   Status: All interactions working perfectly! 🎉", style="green")
    console.print("="*80 + "\n", style="bold green")


async def main():
    """Run demo"""
    await demo_v1()


if __name__ == "__main__":
    asyncio.run(main())
