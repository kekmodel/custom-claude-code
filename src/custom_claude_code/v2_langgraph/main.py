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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Live 패널 관리
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class LivePanelManager:
    """Live 패널 생성/업데이트 통합 관리"""

    def __init__(self):
        self.thinking_live = None
        self.content_live = None
        self.current_thinking = ""
        self.current_content = ""

    def update_thinking(self, text: str):
        """Thinking 패널 업데이트"""
        self.current_thinking += text
        panel = Panel(
            Markdown(f"**💭 Reasoning:**\n\n{self.current_thinking}"),
            title="[bold yellow]Thinking[/bold yellow]",
            border_style="yellow",
        )

        if self.thinking_live is None:
            self.thinking_live = Live(panel, console=console, refresh_per_second=10)
            self.thinking_live.start()
        else:
            self.thinking_live.update(panel)

    def update_content(self, text: str):
        """Content 패널 업데이트"""
        # Thinking 패널이 있으면 닫기
        if self.thinking_live is not None:
            self.thinking_live.stop()
            self.thinking_live = None

        self.current_content += text
        panel = Panel(
            Markdown(self.current_content), title="[bold blue]Assistant[/bold blue]", border_style="blue"
        )

        if self.content_live is None:
            self.content_live = Live(panel, console=console, refresh_per_second=10)
            self.content_live.start()
        else:
            self.content_live.update(panel)

    def close_all(self):
        """모든 Live 패널 닫기"""
        if self.thinking_live is not None:
            self.thinking_live.stop()
            self.thinking_live = None
        if self.content_live is not None:
            self.content_live.stop()
            self.content_live = None

    def reset(self):
        """상태 초기화"""
        self.current_thinking = ""
        self.current_content = ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 이벤트 핸들러
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class EventHandler:
    """LangGraph astream_events 이벤트 처리"""

    def __init__(self):
        self.panel_manager = LivePanelManager()
        self.collected_messages = []

    def handle_chain_start(self, event: dict):
        """노드 시작 이벤트"""
        tags = event.get("tags", [])
        name = event.get("name")

        if "agent" in tags or name == "agent":
            console.print(f"[dim](agent)[/dim]")
        elif "tools" in tags or name == "tools":
            console.print(f"[dim](tools)[/dim]")

    def handle_chat_model_stream(self, event: dict):
        """LLM 스트리밍 이벤트 (토큰 단위)"""
        data = event.get("data", {})
        chunk = data.get("chunk")

        if not chunk or not hasattr(chunk, "content"):
            return

        if not hasattr(chunk, "content_blocks"):
            return

        for block in chunk.content_blocks:
            block_type = block.get("type")

            if block_type == "reasoning":
                reasoning = block.get("reasoning", "")
                if reasoning:
                    self.panel_manager.update_thinking(reasoning)

            elif block_type == "text":
                text = block.get("text", "")
                if text:
                    self.panel_manager.update_content(text)

    def handle_chat_model_end(self, event: dict):
        """LLM 응답 완료 이벤트"""
        self.panel_manager.close_all()

        data = event.get("data", {})
        output = data.get("output")

        if output and isinstance(output, AIMessage):
            self.collected_messages.append(output)
            self._display_tool_calls(output.tool_calls)

        self.panel_manager.reset()

    def handle_chain_end(self, event: dict):
        """노드 완료 이벤트"""
        tags = event.get("tags", [])
        name = event.get("name")
        data = event.get("data", {})
        output = data.get("output")

        # Tools 노드의 결과 처리
        if ("tools" in tags or name == "tools") and output:
            if "messages" in output:
                for msg in output["messages"]:
                    if isinstance(msg, ToolMessage):
                        self._display_tool_result(msg)
                        self.collected_messages.append(msg)

            if "todos" in output and output["todos"]:
                display_todos(output["todos"])

    def _display_tool_calls(self, tool_calls):
        """도구 호출 표시"""
        if not tool_calls:
            return

        for tc in tool_calls:
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
                    console.print("[dim]Awaiting your approval to proceed with implementation...[/dim]\n")
            else:
                console.print(f"[cyan]🔧 Calling tool:[/cyan] {tc['name']}")

    def _display_tool_result(self, msg: ToolMessage):
        """도구 실행 결과 표시"""
        result = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
        console.print(f"[dim]  → Result: {result}[/dim]\n")

    def get_collected_messages(self):
        """수집된 메시지 반환"""
        return self.collected_messages

    def reset_collected_messages(self):
        """수집된 메시지 초기화"""
        self.collected_messages = []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 헬퍼 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def display_message(message):
    """메시지 타입별 Rich 포맷 출력 (사용 안함 - EventHandler가 처리)"""
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


def visualize_graph():
    """그래프 시각화 (Mermaid 다이어그램)"""
    console.print("[yellow]Graph visualization:[/yellow]")
    try:
        img = graph.get_graph().draw_mermaid_png()
        with open("graph.png", "wb") as f:
            f.write(img)
        console.print("[green]Graph saved to graph.png[/green]")
    except Exception as e:
        console.print(f"[yellow]Graph visualization requires additional dependencies: {e}[/yellow]")


async def handle_command(user_input: str, messages: list) -> bool:
    """
    명령어 처리

    Returns:
        True: 대화 루프 계속
        False: 프로그램 종료
    """
    cmd = user_input.lower()

    if cmd == "quit":
        console.print("[yellow]Goodbye![/yellow]")
        return False

    elif cmd == "clear":
        messages.clear()
        console.print("[yellow]History cleared![/yellow]")
        return True

    elif cmd == "graph":
        visualize_graph()
        return True

    return True  # 일반 입력


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 그래프 스트리밍 처리
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def process_graph_stream(messages: list, working_dir: str):
    """
    LangGraph 실행 및 이벤트 스트림 처리

    Args:
        messages: 대화 메시지 목록
        working_dir: 현재 작업 디렉토리
    """
    handler = EventHandler()
    config = {"recursion_limit": 50}

    try:
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

            if kind == "on_chain_start":
                handler.handle_chain_start(event)
            elif kind == "on_chat_model_stream":
                handler.handle_chat_model_stream(event)
            elif kind == "on_chat_model_end":
                handler.handle_chat_model_end(event)
            elif kind == "on_chain_end":
                handler.handle_chain_end(event)

        # 수집된 메시지를 히스토리에 추가
        messages.extend(handler.get_collected_messages())

    except Exception as e:
        console.print(f"[red]Error: {type(e).__name__}: {str(e)}[/red]")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 대화 루프
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def run_conversation_loop():
    """
    메인 대화 루프

    흐름: 사용자 입력 → 명령어 처리 → 그래프 실행 → 응답 표시
    """
    console.print(
        Panel(
            "[bold]Custom Claude Code - Version 2: LangGraph[/bold]\n\n" "Commands: quit, clear, graph",
            title="Welcome",
            border_style="magenta",
        )
    )

    messages = []
    working_dir = os.getcwd()

    while True:
        # 사용자 입력
        try:
            user_input = await prompt_session.prompt_async("\n> ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye![/yellow]")
            break

        if not user_input.strip():
            continue

        # 명령어 처리
        if user_input.lower() in ["quit", "clear", "graph"]:
            should_continue = await handle_command(user_input, messages)
            if not should_continue:
                break
            continue

        # 일반 메시지 처리
        messages.append(HumanMessage(content=user_input))
        await process_graph_stream(messages, working_dir)


async def main():
    await run_conversation_loop()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
