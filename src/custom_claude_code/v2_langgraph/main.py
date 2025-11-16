"""
v2: LangGraph 메인 실행 루프

graph.astream_events()로 토큰 단위 스트리밍 처리
v1 대비: 그래프가 도구 루프 자동 처리, 코드 ~50% 감소
"""

import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from .graph import graph

load_dotenv()
console = Console()
prompt_session = PromptSession(history=InMemoryHistory())


def display_message(message):
    """메시지 타입별 Rich 포맷 출력 (HumanMessage/AIMessage/ToolMessage)"""
    if isinstance(message, HumanMessage):
        console.print(Panel(message.content, title="[bold green]You[/bold green]", border_style="green"))

    elif isinstance(message, AIMessage):
        if hasattr(message, "content_blocks"):
            reasoning_blocks = [block for block in message.content_blocks if block.get("type") == "reasoning"]
            if reasoning_blocks:
                for block in reasoning_blocks:
                    reasoning_text = block.get("reasoning", "")
                    if reasoning_text:
                        console.print(
                            Panel(
                                Markdown(f"**💭 Reasoning:**\n\n{reasoning_text}"),
                                title="[bold yellow]Thinking[/bold yellow]",
                                border_style="yellow",
                            )
                        )

        if message.content:
            if isinstance(message.content, list):
                text_blocks = [
                    block.get("text", "") for block in message.content_blocks if block.get("type") == "text"
                ]
                content_text = "\n\n".join(text_blocks)
            else:
                content_text = message.content

            if content_text:
                console.print(
                    Panel(Markdown(content_text), title="[bold blue]Assistant[/bold blue]", border_style="blue")
                )

        if message.tool_calls:
            for tc in message.tool_calls:
                console.print(f"[cyan]🔧 Calling tool:[/cyan] {tc['name']}")

    elif isinstance(message, ToolMessage):
        result = message.content[:500] + "..." if len(message.content) > 500 else message.content
        console.print(f"[dim]  → Result: {result}[/dim]\n")


def display_todos(todos):
    """Todo 목록을 체크박스(☐/☒) 형식으로 표시"""
    if not todos:
        return

    lines = []
    completed_count = 0

    for todo in todos:
        status = todo["status"]
        if status == "completed":
            lines.append(f"☒ {todo['content']}")
            completed_count += 1
        elif status == "in_progress":
            lines.append(f"☐ {todo['activeForm']}")
        else:
            lines.append(f"☐ {todo['content']}")

    todo_text = "\n".join(lines)
    console.print(
        Panel(
            todo_text,
            title=f"[bold magenta]Todos ({completed_count}/{len(todos)})[/bold magenta]",
            border_style="magenta",
        )
    )


async def run_conversation_loop():
    """
    메인 대화 루프 - graph.astream_events()로 토큰 단위 스트리밍 처리

    흐름: 사용자 입력 → graph.astream_events() → 이벤트 처리 → 응답 표시
    """
    console.print(
        Panel(
            "[bold]Custom Claude Code - Version 2: LangGraph[/bold]\n\n"
            "Commands: quit, clear, graph",
            title="Welcome",
            border_style="magenta",
        )
    )

    messages = []
    working_dir = os.getcwd()

    while True:
        try:
            user_input = await prompt_session.prompt_async("\n> ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye![/yellow]")
            break
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
                img = graph.get_graph().draw_mermaid_png()
                console.print("[green]Graph saved to graph.png[/green]")
                with open("graph.png", "wb") as f:
                    f.write(img)
            except Exception as e:
                console.print(f"[yellow]Graph visualization requires additional dependencies: {e}[/yellow]")
            continue

        if not user_input.strip():
            continue

        user_message = HumanMessage(content=user_input)
        messages.append(user_message)

        try:
            config = {"recursion_limit": 50}
            current_thinking = ""
            current_content = ""
            thinking_live = None
            content_live = None
            collected_messages = []

            # astream_events: LangGraph 실행을 이벤트 스트림으로 받기
            # version="v2": 이벤트 스키마 버전 (v2가 최신)
            async for event in graph.astream_events(
                {"messages": messages, "working_dir": working_dir, "depth": 0, "todos": None},
                config=config,
                version="v2",
            ):
                # 이벤트 종류: on_chain_start (노드 시작), on_chat_model_stream (토큰),
                # on_chat_model_end (LLM 완료), on_chain_end (노드 완료)
                kind = event.get("event")
                name = event.get("name")
                data = event.get("data", {})

                if kind == "on_chain_start":
                    tags = event.get("tags", [])
                    if "agent" in tags or name == "agent":
                        console.print(f"[dim](agent)[/dim]")
                    elif "tools" in tags or name == "tools":
                        console.print(f"[dim](tools)[/dim]")

                elif kind == "on_chat_model_stream":
                    chunk = data.get("chunk")
                    if chunk and hasattr(chunk, "content"):
                        if hasattr(chunk, "content_blocks"):
                            for block in chunk.content_blocks:
                                block_type = block.get("type")

                                if block_type == "reasoning":
                                    reasoning = block.get("reasoning", "")
                                    if reasoning:
                                        current_thinking += reasoning
                                        if thinking_live is None:
                                            thinking_live = Live(
                                                Panel(
                                                    Markdown(current_thinking),
                                                    title="[bold yellow]Thinking[/bold yellow]",
                                                    border_style="yellow",
                                                ),
                                                console=console,
                                                refresh_per_second=10,
                                            )
                                            thinking_live.start()
                                        else:
                                            thinking_live.update(
                                                Panel(
                                                    Markdown(current_thinking),
                                                    title="[bold yellow]Thinking[/bold yellow]",
                                                    border_style="yellow",
                                                )
                                            )

                                elif block_type == "text":
                                    if thinking_live is not None:
                                        thinking_live.stop()
                                        thinking_live = None

                                    text = block.get("text", "")
                                    if text:
                                        current_content += text
                                        if content_live is None:
                                            content_live = Live(
                                                Panel(
                                                    Markdown(current_content),
                                                    title="[bold blue]Assistant[/bold blue]",
                                                    border_style="blue",
                                                ),
                                                console=console,
                                                refresh_per_second=10,
                                            )
                                            content_live.start()
                                        else:
                                            content_live.update(
                                                Panel(
                                                    Markdown(current_content),
                                                    title="[bold blue]Assistant[/bold blue]",
                                                    border_style="blue",
                                                )
                                            )

                elif kind == "on_chat_model_end":
                    if thinking_live is not None:
                        thinking_live.stop()
                        thinking_live = None
                    if content_live is not None:
                        content_live.stop()
                        content_live = None

                    output = data.get("output")
                    if output and isinstance(output, AIMessage):
                        collected_messages.append(output)

                        if output.tool_calls:
                            for tc in output.tool_calls:
                                if tc["name"] == "exit_plan_mode":
                                    plan = tc["args"].get("plan", "")
                                    if plan:
                                        console.print(
                                            Panel(
                                                Markdown(plan),
                                                title="[bold cyan]📋 Implementation Plan[/bold cyan]",
                                                border_style="cyan",
                                            )
                                        )
                                        console.print(
                                            "[dim]Awaiting your approval to proceed with implementation...[/dim]\n"
                                        )
                                else:
                                    console.print(f"[cyan]🔧 Calling tool:[/cyan] {tc['name']}")

                    current_thinking = ""
                    current_content = ""

                elif kind == "on_chain_end":
                    tags = event.get("tags", [])
                    output = data.get("output")

                    if ("tools" in tags or name == "tools") and output:
                        if "messages" in output:
                            for msg in output["messages"]:
                                if isinstance(msg, ToolMessage):
                                    result = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
                                    console.print(f"[dim]  → Result: {result}[/dim]\n")
                                    collected_messages.append(msg)

                        if "todos" in output and output["todos"]:
                            display_todos(output["todos"])

            messages.extend(collected_messages)

        except Exception as e:
            console.print(f"[red]Error: {type(e).__name__}: {str(e)}[/red]")
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")


async def main():
    await run_conversation_loop()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
