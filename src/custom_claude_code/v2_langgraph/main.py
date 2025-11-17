"""
v2: LangGraph 메인 실행 루프

graph.astream_events()로 토큰 단위 스트리밍 처리
v1 대비: 그래프가 도구 루프 자동 처리, 코드 ~50% 감소
"""

import os
import time

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

from .config import V2Config
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

            if V2Config.DEBUG and self.pending_content:
                print(
                    f"\n[DEBUG] 📝 Flushing {len(self.pending_content)} chars "
                    f"(elapsed: {time_elapsed:.3f}s, force: {force})"
                )

            self.pending_content = ""
            self.last_update_time = current_time

            # 패널 업데이트 시간 측정
            update_start = time.time()

            # 패널 업데이트 - Markdown (대용량 배칭으로 최적화)
            panel = Panel(
                Markdown(self.current_content), title="[bold blue]Assistant[/bold blue]", border_style="blue"
            )

            if self.content_live is None:
                self.content_live = Live(panel, console=console, refresh_per_second=10)
                self.content_live.start()
            else:
                self.content_live.update(panel)

            update_elapsed = time.time() - update_start
            if V2Config.DEBUG:
                print(
                    f"[DEBUG] 🎨 Panel update took {update_elapsed*1000:.1f}ms "
                    f"(total content: {len(self.current_content)} chars)"
                )

    def show_spinner(self, message: str, subagent_type: str = "general"):
        """Spinner 표시 (agent 작업 중)"""
        # 기존 패널들 닫기
        self.close_all()

        # 타입별 이모지
        emoji_map = {
            "Agent": "🤔",  # Main agent thinking
            "Explore": "🔍",
            "Plan": "📋",
            "general-purpose": "⚙️",
            "statusline-setup": "⚙️",
        }
        emoji = emoji_map.get(subagent_type, "⚙️")

        spinner = Spinner("dots", text=Text(f"{emoji} {message}", style="cyan"))

        # 패널 타이틀 결정
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
    """LangGraph astream_events 이벤트 처리"""

    def __init__(self, initial_messages: list):
        self.panel_manager = LivePanelManager()
        self.messages = list(initial_messages)  # 초기 메시지로 시작
        self.todos = None
        self.task_tool_depth = 0  # task_tool 중첩 깊이 추적

    def handle_chain_start(self, event: dict):
        """노드 시작 이벤트"""
        tags = event.get("tags", [])
        name = event.get("name")

        # Main agent 시작 - thinking 스피너 제거 (reasoning이 바로 스트리밍됨)
        if ("agent" in tags or name == "agent") and self.task_tool_depth == 0:
            console.print(f"[dim](agent)[/dim]")
        elif "tools" in tags or name == "tools":
            console.print(f"[dim](tools)[/dim]")

    def handle_chat_model_stream(self, event: dict):
        """LLM 스트리밍 이벤트 (토큰 단위)"""
        data = event.get("data", {})
        chunk = data.get("chunk")

        if not chunk or not hasattr(chunk, "content"):
            return

        # 🔧 FIX: Subagent 내부의 스트리밍은 무시 (스피너 유지)
        if self.task_tool_depth > 0:
            if V2Config.DEBUG:
                print(f"\n[DEBUG] ⏭️  Skipping stream (inside subagent, depth={self.task_tool_depth})")
            return

        # Extended Thinking 지원 (content_blocks 있을 때)
        if hasattr(chunk, "content_blocks") and chunk.content_blocks:
            for block in chunk.content_blocks:
                block_type = block.get("type")

                if block_type == "reasoning":
                    reasoning = block.get("reasoning", "")
                    if reasoning:
                        if V2Config.DEBUG:
                            print(f"\n[DEBUG] 🧠 Reasoning chunk: {len(reasoning)} chars")
                        self.panel_manager.update_thinking(reasoning)

                elif block_type == "text":
                    text = block.get("text", "")
                    if text:
                        if V2Config.DEBUG:
                            print(f"\n[DEBUG] 💬 Text chunk (content_blocks): {len(text)} chars")
                        self.panel_manager.update_content(text)

        # 일반 content 스트리밍 (content_blocks가 없거나 비어있을 때)
        # elif가 아니라 별도 체크로 변경!
        if chunk.content and not (hasattr(chunk, "content_blocks") and chunk.content_blocks):
            if isinstance(chunk.content, str):
                if V2Config.DEBUG:
                    print(f"\n[DEBUG] 💬 Text chunk (str): {len(chunk.content)} chars")
                self.panel_manager.update_content(chunk.content)
            elif isinstance(chunk.content, list):
                for block in chunk.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        if text:
                            if V2Config.DEBUG:
                                print(f"\n[DEBUG] 💬 Text chunk (list): {len(text)} chars")
                            self.panel_manager.update_content(text)

    def handle_chat_model_end(self, event: dict):
        """LLM 응답 완료 이벤트"""
        self.panel_manager.close_all()

        # 🔍 subagent 이벤트는 무시 (중복 방지)
        tags = event.get("tags", [])
        if not any(tag in ["agent", "seq:step:1", "graph:step:1"] for tag in tags):
            self.panel_manager.reset()
            return

        data = event.get("data", {})
        output = data.get("output")

        # AIMessage 추가 및 도구 호출 표시
        if output and isinstance(output, AIMessage):
            # 🔧 FIX: depth > 0이면 subagent 내부 메시지 → 무시
            if self.task_tool_depth > 0:
                if V2Config.DEBUG:
                    print(f"\n[DEBUG] ⏭️  Skipping AIMessage (inside subagent, depth={self.task_tool_depth})")
                self.panel_manager.reset()
                return

            if V2Config.DEBUG:
                # 디버깅: 메시지 추가 로그
                msg_id = getattr(output, 'id', 'N/A')
                tool_calls = [tc.get('name') for tc in output.tool_calls] if output.tool_calls else []

                # content 추출 (list일 수도 있음)
                content_preview = ""
                if output.content:
                    if isinstance(output.content, list):
                        text_blocks = [b.get('text', '') for b in output.content if b.get('type') == 'text']
                        content_preview = ' '.join(text_blocks)[:100]
                    else:
                        content_preview = str(output.content)[:100]

                print(f"\n[DEBUG] EventHandler.handle_chat_model_end:")
                print(f"  현재 메시지 수: {len(self.messages)}")
                print(f"  추가할 AIMessage id: {msg_id}")
                print(f"  tool_calls: {tool_calls}")
                print(f"  content: {content_preview}...")

            self.messages.append(output)
            self._display_tool_calls(output.tool_calls)

            # 🔧 FIX: task_tool 호출 감지 → depth 증가 + spinner 표시
            if output.tool_calls:
                for tc in output.tool_calls:
                    if tc.get('name') == 'task_tool':
                        self.task_tool_depth += 1
                        if V2Config.DEBUG:
                            print(f"[DEBUG] 🔽 task_tool detected, depth: {self.task_tool_depth}")

                        # Spinner 표시
                        args = tc.get('args', {})
                        subagent_type = args.get('subagent_type', 'general-purpose')
                        description = args.get('description', 'Processing task...')
                        self.panel_manager.show_spinner(description, subagent_type)
                        break

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
                        tool_name = getattr(msg, 'name', 'unknown')
                        is_task_tool = (tool_name == 'task_tool')

                        # 🔧 FIX: task_tool 완료 → depth 감소 후 메시지 추가
                        # Spinner는 main agent가 응답 시작할 때 자동으로 종료됨
                        if is_task_tool and self.task_tool_depth > 0:
                            self.task_tool_depth -= 1

                            if V2Config.DEBUG:
                                print(f"\n[DEBUG] 🔼 task_tool completed, depth: {self.task_tool_depth}")
                                msg_id = getattr(msg, 'id', 'N/A')
                                content_preview = str(msg.content)[:100] if msg.content else ""
                                print(f"[DEBUG] EventHandler.handle_chain_end:")
                                print(f"  현재 메시지 수: {len(self.messages)}")
                                print(f"  추가할 ToolMessage id: {msg_id}")
                                print(f"  tool_name: {tool_name}")
                                print(f"  content: {content_preview}...")

                            self.messages.append(msg)
                            self._display_tool_result(msg)

                        # 🔧 FIX: subagent 내부의 ToolMessage → 무시
                        elif self.task_tool_depth > 0:
                            if V2Config.DEBUG:
                                print(f"\n[DEBUG] ⏭️  Skipping ToolMessage '{tool_name}' (inside subagent, depth={self.task_tool_depth})")
                            continue

                        # 일반 ToolMessage → 추가
                        else:
                            if V2Config.DEBUG:
                                msg_id = getattr(msg, 'id', 'N/A')
                                content_preview = str(msg.content)[:100] if msg.content else ""
                                print(f"\n[DEBUG] EventHandler.handle_chain_end:")
                                print(f"  현재 메시지 수: {len(self.messages)}")
                                print(f"  추가할 ToolMessage id: {msg_id}")
                                print(f"  tool_name: {tool_name}")
                                print(f"  content: {content_preview}...")

                            self.messages.append(msg)
                            self._display_tool_result(msg)

            if "todos" in output and output["todos"]:
                self.todos = output["todos"]
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
        console.print(f"[dim]  → Result:\n{result}[/dim]\n")

    def get_final_messages(self):
        """누적된 최종 메시지 반환"""
        if V2Config.DEBUG:
            # 디버깅: 최종 메시지 구조 출력
            print(f"\n{'='*80}")
            print(f"[DEBUG] EventHandler.get_final_messages:")
            print(f"  총 메시지 수: {len(self.messages)}")
            print(f"{'='*80}")

            for i, msg in enumerate(self.messages):
                msg_type = type(msg).__name__
                msg_id = getattr(msg, 'id', 'N/A')[:20] if hasattr(msg, 'id') else 'N/A'

                # content 추출
                content_preview = ""
                if hasattr(msg, 'content') and msg.content:
                    if isinstance(msg.content, list):
                        text_blocks = [b.get('text', '') for b in msg.content if b.get('type') == 'text']
                        content_preview = ' '.join(text_blocks)[:80]
                    else:
                        content_preview = str(msg.content)[:80]

                if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                    tool_calls = [tc.get('name') for tc in msg.tool_calls]
                    print(f"  [{i}] {msg_type:15} id=...{msg_id}")
                    print(f"      tool_calls: {tool_calls}")
                    print(f"      content: {content_preview}...")
                elif isinstance(msg, ToolMessage):
                    tool_name = getattr(msg, 'name', 'unknown')
                    print(f"  [{i}] {msg_type:15} id=...{msg_id} name={tool_name}")
                    print(f"      content: {content_preview}...")
                else:
                    print(f"  [{i}] {msg_type:15} id=...{msg_id}")
                    if content_preview:
                        print(f"      content: {content_preview}...")

            # 연속 AIMessage 감지
            print(f"\n🔍 연속 AIMessage 체크:")
            consecutive_found = False
            for i in range(len(self.messages) - 1):
                if isinstance(self.messages[i], AIMessage) and isinstance(self.messages[i + 1], AIMessage):
                    consecutive_found = True
                    msg1_id = getattr(self.messages[i], 'id', 'N/A')
                    msg2_id = getattr(self.messages[i + 1], 'id', 'N/A')

                    # content 비교
                    content1 = self.messages[i].content
                    content2 = self.messages[i + 1].content
                    same_content = (str(content1) == str(content2))

                    tool_calls1 = [tc.get('name') for tc in self.messages[i].tool_calls] if self.messages[i].tool_calls else []
                    tool_calls2 = [tc.get('name') for tc in self.messages[i + 1].tool_calls] if self.messages[i + 1].tool_calls else []

                    print(f"  ⚠️  [{i}]-[{i+1}] 연속 AIMessage 발견!")
                    print(f"      [{i}] id={msg1_id}, tool_calls={tool_calls1}")
                    print(f"      [{i+1}] id={msg2_id}, tool_calls={tool_calls2}")
                    print(f"      같은 ID: {msg1_id == msg2_id}")
                    print(f"      같은 content: {same_content}")

            if not consecutive_found:
                print(f"  ✅ 연속 AIMessage 없음")

            print(f"{'='*80}\n")

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
