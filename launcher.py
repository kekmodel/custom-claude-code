"""
🚀 Custom Claude Code - Interactive Launcher

4가지 버전을 선택해서 직접 테스트할 수 있는 UI
"""

import asyncio
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

# Load environment
load_dotenv()

console = Console()


def show_welcome():
    """환영 화면"""
    console.clear()
    console.print()
    console.print("╔" + "=" * 78 + "╗", style="bold magenta")
    console.print("║" + " " * 20 + "🚀 CUSTOM CLAUDE CODE LAUNCHER" + " " * 28 + "║", style="bold magenta")
    console.print("║" + " " * 78 + "║", style="bold magenta")
    console.print("║" + " " * 15 + "4가지 버전으로 구현된 Claude Code를 테스트하세요!" + " " * 15 + "║", style="bold magenta")
    console.print("╚" + "=" * 78 + "╝", style="bold magenta")
    console.print()


def show_version_comparison():
    """버전 비교 테이블"""
    table = Table(title="📊 버전 비교", show_header=True, header_style="bold cyan")

    table.add_column("버전", style="bold", width=18)
    table.add_column("프레임워크", width=20)
    table.add_column("코드", width=12)
    table.add_column("특징", width=28)

    table.add_row(
        "v1: OpenAI",
        "OpenAI API 직접",
        "~1,891줄",
        "✅ 완전 제어, 리팩토링됨",
        style="green"
    )
    table.add_row(
        "v2: LangGraph",
        "LangGraph StateGraph",
        "~450줄",
        "✅ 자동 워크플로우",
        style="blue"
    )
    table.add_row(
        "v3: Agents SDK",
        "OpenAI Agents SDK",
        "~280줄",
        "✅ Agent.as_tool() 패턴",
        style="yellow"
    )
    table.add_row(
        "v4: Claude SDK",
        "Claude Agent SDK",
        "~190줄",
        "✅ Haiku 4.5 + 서브에이전트",
        style="magenta"
    )

    console.print(table)
    console.print()


def show_menu():
    """메인 메뉴"""
    console.print(Panel(
        "[bold cyan]버전을 선택하세요:[/bold cyan]\n\n"
        "  [bold green]1[/bold green] → v1: OpenAI API (직접 구현, 완전 제어)\n"
        "  [bold blue]2[/bold blue] → v2: LangGraph (StateGraph, 자동 워크플로우)\n"
        "  [bold yellow]3[/bold yellow] → v3: OpenAI Agents SDK (Agent.as_tool())\n"
        "  [bold magenta]4[/bold magenta] → v4: Claude Agent SDK (Haiku 4.5 + 서브에이전트)\n\n"
        "  [bold red]q[/bold red] → 종료\n"
        "  [bold dim]c[/bold dim] → 버전 비교 보기",
        title="🎯 메뉴",
        border_style="cyan"
    ))


async def run_v1():
    """v1 실행"""
    console.print("\n[bold green]🚀 Starting v1: OpenAI API...[/bold green]\n")
    try:
        from custom_claude_code.v1_openai.main import run_conversation_loop
        await run_conversation_loop()
    except KeyboardInterrupt:
        console.print("\n[yellow]v1 종료됨[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


async def run_v2():
    """v2 실행"""
    console.print("\n[bold blue]🚀 Starting v2: LangGraph...[/bold blue]\n")
    try:
        from custom_claude_code.v2_langgraph.main import run_conversation_loop
        await run_conversation_loop()
    except KeyboardInterrupt:
        console.print("\n[yellow]v2 종료됨[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


async def run_v3():
    """v3 실행"""
    console.print("\n[bold yellow]🚀 Starting v3: OpenAI Agents SDK...[/bold yellow]\n")
    try:
        # v3은 OpenAI API를 사용하므로 환경 변수 임시 변경 필요 없음
        # v3 main.py에서 하드코딩된 OpenAI API 키 사용
        from custom_claude_code.v3_openai_agents.main import run_conversation_loop
        await run_conversation_loop()
    except KeyboardInterrupt:
        console.print("\n[yellow]v3 종료됨[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")


async def run_v4():
    """v4 실행"""
    console.print("\n[bold magenta]🚀 Starting v4: Claude Agent SDK...[/bold magenta]\n")
    try:
        from custom_claude_code.v4_claude_agent.main import run_conversation_loop
        await run_conversation_loop()
    except KeyboardInterrupt:
        console.print("\n[yellow]v4 종료됨[/yellow]")
    except Exception as e:
        error_msg = str(e).replace("[", "\\[").replace("]", "\\]")
        console.print(f"[red]Error: {error_msg}[/red]")
        import traceback
        tb = traceback.format_exc().replace("[", "\\[").replace("]", "\\]")
        console.print(f"[dim]{tb}[/dim]")


async def main():
    """메인 루프"""
    show_welcome()

    while True:
        show_menu()

        choice = Prompt.ask(
            "\n[bold cyan]선택[/bold cyan]",
            choices=["1", "2", "3", "4", "c", "q"],
            default="1"
        )

        if choice == "q":
            console.print("\n[bold green]👋 Goodbye![/bold green]\n")
            break

        elif choice == "c":
            console.clear()
            show_welcome()
            show_version_comparison()
            console.print("\n[dim]Press Enter to continue...[/dim]")
            input()
            console.clear()
            show_welcome()
            continue

        elif choice == "1":
            await run_v1()

        elif choice == "2":
            await run_v2()

        elif choice == "3":
            await run_v3()

        elif choice == "4":
            await run_v4()

        # 버전 종료 후 메인 메뉴로
        console.print("\n[dim]Returning to main menu...[/dim]\n")
        await asyncio.sleep(1)
        console.clear()
        show_welcome()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n\n[bold green]👋 Goodbye![/bold green]\n")
        sys.exit(0)
