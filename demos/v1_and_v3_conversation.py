"""
🎯 Live Conversation Test
실시간으로 대화를 보여주는 테스트
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


async def test_v1():
    """v1 버전으로 실제 대화 테스트"""
    console.print("\n" + "="*80, style="bold cyan")
    console.print("🚀 Testing v1: OpenAI API Version", style="bold cyan")
    console.print("="*80 + "\n", style="bold cyan")

    from custom_claude_code.v1_openai.main import (
        stream_assistant_response,
        get_system_prompt,
        execute_tool,
    )

    # 대화 히스토리
    messages = []

    # Test 1: Simple greeting
    console.print(Panel("👤 User: Hello! Can you introduce yourself?", border_style="green"))

    messages.append({
        "role": "user",
        "content": "Hello! Can you introduce yourself?"
    })

    result = await stream_assistant_response(
        messages=messages,
        system_prompt=get_system_prompt(),
        model="claude-haiku-4-5"
    )

    console.print(Panel(
        Markdown(result["content"]),
        title="🤖 Assistant",
        border_style="blue"
    ))

    messages.append({
        "role": "assistant",
        "content": result["content"]
    })

    # Test 2: Tool usage - Read file
    console.print("\n" + "-"*80 + "\n", style="dim")
    console.print(Panel("👤 User: Read the README.md file and tell me what this project is about", border_style="green"))

    messages.append({
        "role": "user",
        "content": "Read the README.md file and tell me what this project is about"
    })

    # Stream 응답 처리
    console.print("\n[dim]🤖 Assistant is thinking...[/dim]\n")

    result = await stream_assistant_response(
        messages=messages,
        system_prompt=get_system_prompt(),
        model="claude-haiku-4-5"
    )

    # Tool calls가 있으면 실행
    if result.get("tool_calls"):
        console.print("[cyan]🔧 Using tools:[/cyan]")
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
            tool_result = await execute_tool(tool_call)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": tool_result
            })

        # 도구 실행 후 다시 응답
        console.print("\n[dim]🤖 Processing results...[/dim]\n")
        result = await stream_assistant_response(
            messages=messages,
            system_prompt=get_system_prompt(),
            model="claude-haiku-4-5"
        )

    console.print(Panel(
        Markdown(result["content"]),
        title="🤖 Assistant",
        border_style="blue"
    ))

    messages.append({
        "role": "assistant",
        "content": result["content"]
    })

    # Test 3: Complex task - Use Explore subagent
    console.print("\n" + "-"*80 + "\n", style="dim")
    console.print(Panel(
        "👤 User: Use the Explore agent to find all Python files in the src directory and tell me which version has the most code",
        border_style="green"
    ))

    messages.append({
        "role": "user",
        "content": "Use the Explore agent to find all Python files in the src directory and tell me which version has the most code"
    })

    console.print("\n[dim]🤖 Assistant is thinking...[/dim]\n")

    result = await stream_assistant_response(
        messages=messages,
        system_prompt=get_system_prompt(),
        model="claude-haiku-4-5"
    )

    # Tool calls 처리 (Subagent 포함)
    if result.get("tool_calls"):
        console.print("[cyan]🔧 Using tools:[/cyan]")
        for tool_call in result["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            console.print(f"  → [yellow]{tool_name}[/yellow]")
            if tool_name == "task":
                import json
                args = json.loads(tool_call["function"]["arguments"])
                console.print(f"    📋 Subagent type: [magenta]{args.get('subagent_type')}[/magenta]")

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
        console.print("\n[dim]🤖 Processing results...[/dim]\n")
        result = await stream_assistant_response(
            messages=messages,
            system_prompt=get_system_prompt(),
            model="claude-haiku-4-5"
        )

    console.print(Panel(
        Markdown(result["content"]),
        title="🤖 Assistant",
        border_style="blue"
    ))

    console.print("\n" + "="*80, style="bold green")
    console.print("✅ v1 Conversation Test Complete!", style="bold green")
    console.print("="*80 + "\n", style="bold green")


async def test_v3():
    """v3 버전으로 실제 대화 테스트"""
    console.print("\n" + "="*80, style="bold yellow")
    console.print("🚀 Testing v3: OpenAI Agents SDK Version", style="bold yellow")
    console.print("="*80 + "\n", style="bold yellow")

    from agents import Runner, SQLiteSession
    from custom_claude_code.v3_openai_agents.main import agent

    # Session
    session = SQLiteSession("test_session", "test_v3.db")
    await session.clear_session()

    # Test 1: Simple greeting
    console.print(Panel("👤 User: Hello! What can you do?", border_style="green"))

    console.print("\n[dim]🤖 Assistant is thinking...[/dim]\n")

    result = await Runner.run(agent, input="Hello! What can you do?", session=session)

    console.print(Panel(
        Markdown(result.final_output),
        title="🤖 Assistant",
        border_style="blue"
    ))

    # Test 2: Tool usage
    console.print("\n" + "-"*80 + "\n", style="dim")
    console.print(Panel("👤 User: Find all Python files in the current directory", border_style="green"))

    console.print("\n[dim]🤖 Assistant is thinking...[/dim]\n")

    result = await Runner.run(agent, input="Find all Python files in the current directory", session=session)

    console.print(Panel(
        Markdown(result.final_output),
        title="🤖 Assistant",
        border_style="blue"
    ))

    if hasattr(result, 'turns'):
        console.print(f"\n[dim]📊 Turns used: {len(result.turns)}[/dim]")

    # Test 3: Subagent
    console.print("\n" + "-"*80 + "\n", style="dim")
    console.print(Panel(
        "👤 User: Use the Explore agent to find all configuration files in this project",
        border_style="green"
    ))

    console.print("\n[dim]🤖 Assistant is thinking...[/dim]\n")
    console.print("[cyan]🔧 Launching Explore subagent...[/cyan]\n")

    result = await Runner.run(
        agent,
        input="Use the Explore agent to find all configuration files in this project",
        session=session
    )

    console.print(Panel(
        Markdown(result.final_output),
        title="🤖 Assistant",
        border_style="blue"
    ))

    if hasattr(result, 'turns'):
        console.print(f"\n[dim]📊 Turns used: {len(result.turns)}[/dim]")

    console.print("\n" + "="*80, style="bold green")
    console.print("✅ v3 Conversation Test Complete!", style="bold green")
    console.print("="*80 + "\n", style="bold green")


async def main():
    """메인 테스트 실행"""
    console.print("\n")
    console.print("╔" + "="*78 + "╗", style="bold magenta")
    console.print("║" + " "*20 + "🎯 LIVE CONVERSATION TEST" + " "*32 + "║", style="bold magenta")
    console.print("║" + " "*78 + "║", style="bold magenta")
    console.print("║" + " "*15 + "실시간으로 AI와 대화하는 모습을 보여드립니다!" + " "*17 + "║", style="bold magenta")
    console.print("╚" + "="*78 + "╝", style="bold magenta")
    console.print("\n")

    # Test v1
    await test_v1()

    # Wait a bit
    await asyncio.sleep(2)

    # Test v3
    await test_v3()

    console.print("\n" + "="*80, style="bold magenta")
    console.print("🎉 All Tests Complete!", style="bold magenta")
    console.print("="*80 + "\n", style="bold magenta")


if __name__ == "__main__":
    asyncio.run(main())
