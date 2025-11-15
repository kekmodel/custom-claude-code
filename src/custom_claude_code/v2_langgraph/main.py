"""
v2: LangGraph 메인 루프

LangGraph의 자동 루프를 활용:
- graph.stream() for 실시간 업데이트
- v1보다 훨씬 간단! (루프 로직이 그래프에 있음)
"""

import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .graph import graph

# 환경 변수 로드
load_dotenv()

# Rich console
console = Console()

# Prompt session
prompt_session = PromptSession(history=InMemoryHistory())


def display_message(message):
    """메시지를 Rich 포맷으로 표시"""
    if isinstance(message, HumanMessage):
        console.print(Panel(message.content, title="[bold green]You[/bold green]", border_style="green"))
    elif isinstance(message, AIMessage):
        if message.content:  # 빈 content는 스킵 (tool_calls만 있는 경우)
            console.print(
                Panel(Markdown(message.content), title="[bold blue]Assistant[/bold blue]", border_style="blue")
            )
        if message.tool_calls:
            for tc in message.tool_calls:
                console.print(f"[cyan]🔧 Calling tool:[/cyan] {tc['name']}")
    elif isinstance(message, ToolMessage):
        # 도구 결과는 간략히 표시
        result = message.content[:500] + "..." if len(message.content) > 500 else message.content
        console.print(f"[dim]  → Result: {result}[/dim]\n")


async def run_conversation_loop():
    """
    메인 대화 루프 (LangGraph 버전)

    v1과의 차이:
    - 내부 도구 루프 없음! (그래프가 자동 처리)
    - graph.stream()으로 실시간 업데이트
    - 코드가 훨씬 간단함!
    """
    console.print(
        Panel(
            "[bold]Custom Claude Code - Version 2: LangGraph[/bold]\n\n"
            "✨ Features:\n"
            "  - StateGraph workflow automation\n"
            "  - Automatic tool-calling loop\n"
            "  - Streaming updates\n"
            "  - Memory support (optional)\n\n"
            "Commands:\n"
            "  - Type 'quit' to exit\n"
            "  - Type 'clear' to clear history\n"
            "  - Type 'graph' to visualize the graph",
            title="Welcome",
            border_style="magenta",
        )
    )

    # 대화 상태
    messages = []
    working_dir = os.getcwd()

    while True:
        # 사용자 입력
        try:
            user_input = await prompt_session.prompt_async("\n> ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye![/yellow]")
            break

        # 명령어 처리
        if user_input.lower() == "quit":
            console.print("[yellow]Goodbye![/yellow]")
            break

        if user_input.lower() == "clear":
            messages.clear()
            console.print("[yellow]History cleared![/yellow]")
            continue

        if user_input.lower() == "graph":
            console.print("[yellow]Graph visualization:[/yellow]")
            try:
                # Mermaid 다이어그램 출력
                from IPython.display import Image

                img = graph.get_graph().draw_mermaid_png()
                console.print("[green]Graph saved to graph.png[/green]")
                with open("graph.png", "wb") as f:
                    f.write(img)
            except Exception as e:
                console.print(f"[yellow]Graph visualization requires additional dependencies: {e}[/yellow]")
            continue

        if not user_input.strip():
            continue

        # 사용자 메시지 추가
        user_message = HumanMessage(content=user_input)
        messages.append(user_message)
        display_message(user_message)

        # LangGraph 실행 (스트리밍!)
        try:
            config = {"recursion_limit": 50}  # 무한 루프 방지

            # stream()으로 실시간 업데이트
            async for event in graph.astream(
                {"messages": messages, "working_dir": working_dir, "depth": 0},
                config=config,
                stream_mode="updates",  # 노드별 업데이트
            ):
                # 각 노드의 업데이트 처리
                for node_name, node_output in event.items():
                    console.print(f"[dim]({node_name})[/dim]")

                    # 새 메시지 표시
                    if "messages" in node_output:
                        for msg in node_output["messages"]:
                            display_message(msg)
                            messages.append(msg)  # 히스토리 업데이트

        except Exception as e:
            console.print(f"[red]Error: {type(e).__name__}: {str(e)}[/red]")
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")


async def main():
    """메인 함수"""
    await run_conversation_loop()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
