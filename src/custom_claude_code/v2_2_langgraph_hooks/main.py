"""
v2.2: LangGraph with Hook System

v2.1 기반 + Hook System 완전 통합:
- Hook System: 4개 Hook Events 완전히 작동
  * PreToolUse: 도구 실행 전 검증/차단 (graph.py)
  * PostToolUse: 도구 실행 후 후처리/중단 (graph.py)
  * UserPromptSubmit: 사용자 입력 시 컨텍스트 주입 (main.py)
  * SubagentStop: Subagent 완료 시 결과 후처리 (nodes.py)
- Validation Agent: Bash 명령어 보안 검증 (PreToolUse hook 예시)
- File Extraction Agent: 파일 경로 자동 추출 (PostToolUse hook 예시)
- Permission System: can_use_tool API (고수준 추상화)
- Settings Loader: CLAUDE.md 자동 로드

graph.astream_events()로 토큰 단위 스트리밍 처리
v2.1 대비: Hook System으로 확장성 및 보안 강화
"""

import os
import time
import traceback

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from .graph import graph
from .hooks import trigger_hook, HookContext

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
        self.spinner_live = None
        self.current_thinking = ""
        self.current_content = ""

        # 스트리밍 최적화: 청크 배칭
        self.pending_content = ""  # 대기 중인 콘텐츠 버퍼
        self.last_update_time = 0  # 마지막 업데이트 시간
        self.min_update_interval = 0.15  # 최소 업데이트 간격 (150ms) - Markdown용
        self.batch_size = 100  # 배치 크기 (문자 수) - 더 큰 배치

    def update_thinking(self, text: str):
        """Thinking 패널 업데이트"""
        # Spinner 숨기기 (Thinking과 Spinner 동시 표시 방지)
        if self.spinner_live is not None:
            self.spinner_live.stop()
            self.spinner_live = None

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

    def update_content(self, text: str, force: bool = False):
        """Content 패널 업데이트 (배칭 최적화)

        Args:
            text: 추가할 텍스트
            force: True면 즉시 업데이트 (스트림 종료 시)
        """
        # Spinner 숨기기 (Content 표시 시작)
        if self.spinner_live is not None:
            self.spinner_live.stop()
            self.spinner_live = None

        # Thinking 패널이 있으면 닫기
        if self.thinking_live is not None:
            self.thinking_live.stop()
            self.thinking_live = None

        # 버퍼에 텍스트 추가
        self.pending_content += text

        current_time = time.time()
        time_elapsed = current_time - self.last_update_time

        # 업데이트 조건: force OR 충분한 시간 경과 OR 충분한 텍스트 누적
        should_update = (
            force or time_elapsed >= self.min_update_interval or len(self.pending_content) >= self.batch_size
        )

        if should_update:
            # 누적된 콘텐츠를 실제 콘텐츠에 추가
            self.current_content += self.pending_content

            self.pending_content = ""
            self.last_update_time = current_time

            # 패널 업데이트 - Markdown (대용량 배칭으로 최적화)
            panel = Panel(
                Markdown(self.current_content), title="[bold blue]Assistant[/bold blue]", border_style="blue"
            )

            if self.content_live is None:
                self.content_live = Live(panel, console=console, refresh_per_second=10)
                self.content_live.start()
            else:
                self.content_live.update(panel)

    def show_spinner(self, message: str, subagent_type: str = "general"):
        """
        Spinner 표시 (subagent 작업 중)

        Spinner는 main agent가 응답 시작할 때 자동으로 종료됨
        (update_thinking 또는 update_content에서 close_all 호출)
        """
        # 기존 패널들 닫기
        self.close_all()

        # 타입별 이모지
        emoji_map = {
            "Agent": "🤔",
            "Explore": "🔍",
            "Plan": "📋",
            "general-purpose": "⚙️",
            "statusline-setup": "⚙️",
        }
        emoji = emoji_map.get(subagent_type, "⚙️")

        spinner = Spinner("dots", text=Text(f"{emoji} {message}", style="cyan"))

        # 패널 타이틀
        if subagent_type == "Agent":
            title = f"[bold cyan]{subagent_type}[/bold cyan]"
        else:
            title = f"[bold cyan]{subagent_type} Agent[/bold cyan]"

        panel = Panel(spinner, title=title, border_style="cyan")

        if self.spinner_live is None:
            self.spinner_live = Live(panel, console=console, refresh_per_second=10)
            self.spinner_live.start()
        else:
            self.spinner_live.update(panel)

    def hide_spinner(self):
        """Spinner 숨기기"""
        if self.spinner_live is not None:
            self.spinner_live.stop()
            self.spinner_live = None

    def close_all(self):
        """모든 Live 패널 닫기"""
        # 남은 콘텐츠 플러시
        if self.pending_content:
            self.update_content("", force=True)

        if self.thinking_live is not None:
            self.thinking_live.stop()
            self.thinking_live = None
        if self.content_live is not None:
            self.content_live.stop()
            self.content_live = None
        if self.spinner_live is not None:
            self.spinner_live.stop()
            self.spinner_live = None

    def reset(self):
        """상태 초기화"""
        self.current_thinking = ""
        self.current_content = ""
        self.pending_content = ""
        self.last_update_time = 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 이벤트 핸들러
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class EventHandler:
    """
    LangGraph astream_events 이벤트 처리

    Subagent 필터링: tag 검사 + depth 추적으로 중복 AIMessage 방지
    """

    def __init__(self, initial_messages: list):
        self.panel_manager = LivePanelManager()
        self.messages = list(initial_messages)  # 초기 메시지로 시작
        self.todos = None
        self.active_subagent = None  # 현재 실행 중인 subagent 타입 (spinner 표시용)
        self.task_tool_depth = 0  # task_tool 호출 깊이 (subagent 감지용)

    def handle_chain_start(self, event: dict):
        """노드 시작 이벤트"""
        tags = event.get("tags", [])
        name = event.get("name")

        # 노드 시작 로그
        if "agent" in tags or name == "agent":
            console.print(f"[dim](agent)[/dim]")
        elif "tools" in tags or name == "tools":
            console.print(f"[dim](tools)[/dim]")

    def handle_chat_model_stream(self, event: dict):
        """
        LLM 스트리밍 이벤트 (토큰 단위)

        Subagent 필터링: graph:step:1 태그로 main graph만 식별
        """
        # Subagent 이벤트 무시 (정확한 tag 필터링)
        tags = event.get("tags", [])
        # Main graph는 seq:step:1 또는 graph:step:1을 가짐
        # Subagent는 seq:step:2, graph:step:2 등을 가짐
        if not any(tag in ["seq:step:1", "graph:step:1"] for tag in tags):
            return
        data = event.get("data", {})
        chunk = data.get("chunk")

        if not chunk or not hasattr(chunk, "content"):
            return

        # Extended Thinking 지원 (content_blocks 있을 때)
        if hasattr(chunk, "content_blocks") and chunk.content_blocks:
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

        # 일반 content 스트리밍 (content_blocks가 없거나 비어있을 때)
        # elif가 아니라 별도 체크로 변경!
        if chunk.content and not (hasattr(chunk, "content_blocks") and chunk.content_blocks):
            if isinstance(chunk.content, str):
                self.panel_manager.update_content(chunk.content)
            elif isinstance(chunk.content, list):
                for block in chunk.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        if text:
                            self.panel_manager.update_content(text)

    def handle_chat_model_end(self, event: dict):
        """
        LLM 응답 완료 이벤트

        Subagent 필터링: tag + depth 검사로 main graph AIMessage만 수집
        """
        # 패널 정리 (v2와 동일: 필터링 전에 close_all)
        self.panel_manager.close_all()

        # 🔍 Subagent 이벤트 무시
        tags = event.get("tags", [])
        if not any(tag in ["seq:step:1", "graph:step:1"] for tag in tags):
            self.panel_manager.reset()
            return

        data = event.get("data", {})
        output = data.get("output")

        # AIMessage 추가 및 도구 호출 표시
        if output and isinstance(output, AIMessage):
            # 🔧 FIX: depth > 0이면 subagent 내부 메시지 → 무시
            if self.task_tool_depth > 0:
                self.panel_manager.reset()
                return

            self.messages.append(output)
            self._display_tool_calls(output.tool_calls)

            # task_tool 호출 감지 → depth 증가 + spinner 표시
            if output.tool_calls:
                for tc in output.tool_calls:
                    if tc.get("name") == "task_tool":
                        self.task_tool_depth += 1  # Subagent 진입

                        # Spinner 표시
                        args = tc.get("args", {})
                        subagent_type = args.get("subagent_type", "general-purpose")
                        description = args.get("description", "Processing task...")
                        self.active_subagent = subagent_type
                        self.panel_manager.show_spinner(description, subagent_type)

                        break

        self.panel_manager.reset()

    def handle_chain_end(self, event: dict):
        """
        노드 완료 이벤트

        Subagent 필터링: tag 검사 + depth 감소 (task_tool 완료 시)
        """
        tags = event.get("tags", [])
        name = event.get("name")
        data = event.get("data", {})
        output = data.get("output")

        # Tools 노드의 결과 처리
        if ("tools" in tags or name == "tools") and output:
            if "messages" in output:
                for msg in output["messages"]:
                    if isinstance(msg, ToolMessage):
                        tool_name = getattr(msg, "name", "unknown")

                        # task_tool 완료 → depth 감소
                        if tool_name == "task_tool":
                            if self.task_tool_depth > 0:
                                self.task_tool_depth -= 1  # Subagent 종료
                            self.active_subagent = None

                        # 🔧 FIX: task_tool ToolMessage는 항상 추가 (main graph 호출이므로)
                        # depth > 0인 다른 ToolMessage는 subagent 내부 → 무시
                        if tool_name == "task_tool" or self.task_tool_depth == 0:
                            self.messages.append(msg)
                            self._display_tool_result(msg)
            if "todos" in output and output["todos"]:
                self.todos = output["todos"]
                display_todos(output["todos"], panel_manager=self.panel_manager)

    def _display_tool_calls(self, tool_calls):
        """도구 호출 표시"""
        if not tool_calls:
            return

        for tc in tool_calls:
            console.print(f"[cyan]🔧 Calling tool:[/cyan] {tc['name']}")

    def _display_tool_result(self, msg: ToolMessage):
        """도구 실행 결과 표시"""
        result = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
        console.print(f"[dim]  → Result:\n{result}[/dim]\n")

    def get_final_messages(self):
        """누적된 최종 메시지 반환"""
        return self.messages


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
        console.print(f"[dim]  → Result:\n{result}[/dim]\n")


def display_todos(todos, panel_manager=None):
    """Todo 목록을 체크박스(☐/☒) 형식으로 표시

    Args:
        todos: Todo 목록
        panel_manager: LivePanelManager (제공 시 Live 패널 먼저 닫음)
    """
    if not todos:
        return

    # Live 패널이 활성화되어 있으면 먼저 닫기 (위치 고정)
    if panel_manager is not None:
        panel_manager.close_all()

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
        # TODO: Stop Hook 구현 위치 (정상 종료)
        # await trigger_hook(
        #     event="Stop",
        #     input_data={"reason": "user_command", "message_count": len(messages)},
        #     tool_use_id=None,
        #     context=HookContext(session_id="main", turn_count=len(messages))
        # )
        # Hook에서 정리 작업 수행 가능 (세션 저장, 통계 기록 등)
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
    LangGraph 실행 및 스트림 처리 (astream_events - 1회 실행, thinking 표시)

    Args:
        messages: 대화 메시지 목록
        working_dir: 현재 작업 디렉토리
    """
    handler = EventHandler(initial_messages=messages)
    config = {"recursion_limit": 50}
    initial_state = {"messages": messages, "working_dir": working_dir, "depth": 0, "todos": None}

    try:
        # astream_events: 토큰 단위 스트리밍 + 메시지 누적 (1회 실행)
        async for event in graph.astream_events(initial_state, config=config, version="v2"):
            kind = event.get("event")

            if kind == "on_chain_start":
                handler.handle_chain_start(event)
            elif kind == "on_chat_model_stream":
                handler.handle_chat_model_stream(event)
            elif kind == "on_chat_model_end":
                handler.handle_chat_model_end(event)
            elif kind == "on_chain_end":
                handler.handle_chain_end(event)

        # EventHandler에서 누적한 최종 메시지로 업데이트
        final_messages = handler.get_final_messages()
        messages.clear()
        messages.extend(final_messages)

    except Exception as e:
        error_name = type(e).__name__
        error_msg = str(e)

        # 네트워크 오류 감지
        if "RemoteProtocolError" in error_name or "connection" in error_msg.lower():
            console.print(f"[red]Network Error: {error_name}[/red]")
            console.print("[yellow]⚠️  연결이 끊겼습니다. 다시 시도해주세요.[/yellow]")
            console.print(f"[dim]Details: {error_msg}[/dim]")
        else:
            console.print(f"[red]Error: {error_name}: {error_msg}[/red]")
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
            "[bold]Custom Claude Code - Version 2.2: LangGraph Hooks[/bold]\n\n" "Commands: quit, clear, graph",
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
            # TODO: Stop Hook 구현 위치 (사용자 중단)
            # await trigger_hook(
            #     event="Stop",
            #     input_data={"reason": "user_interrupt", "message_count": len(messages)},
            #     tool_use_id=None,
            #     context=HookContext(session_id="main", turn_count=len(messages))
            # )
            # Hook에서 정리 작업 수행 가능 (로그 저장, 리소스 해제 등)
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

        # UserPromptSubmit Hook 트리거
        context = HookContext(
            session_id="main",
            turn_count=len(messages),
        )

        hook_result = await trigger_hook(
            event="UserPromptSubmit",
            input_data={"user_input": user_input},
            tool_use_id=None,
            context=context
        )

        # additionalContext를 user_input에 추가
        final_input = user_input
        hook_output = hook_result.get("hookSpecificOutput", {})
        if hook_output.get("additionalContext"):
            additional = hook_output["additionalContext"]
            final_input = f"{user_input}\n\n<system-reminder>\n{additional}\n</system-reminder>"

        # TODO: PreCompact Hook 구현 위치
        # 메시지 수/토큰 수가 임계값을 초과하면:
        # 1. PreCompact Hook 트리거
        #    hook_result = await trigger_hook(
        #        event="PreCompact",
        #        input_data={"messages": messages, "threshold": 100000},
        #        tool_use_id=None,
        #        context=HookContext(session_id="main", turn_count=len(messages))
        #    )
        # 2. Hook에서 보존할 메시지 마킹 가능
        # 3. 메시지 압축 수행 (RemoveMessage 사용)
        # 4. 압축된 메시지로 교체

        # 일반 메시지 처리
        messages.append(HumanMessage(content=final_input))
        await process_graph_stream(messages, working_dir)


async def main():
    await run_conversation_loop()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
