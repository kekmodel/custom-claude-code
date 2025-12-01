"""
v2.3: UI 표시 함수

Rich 기반 콘솔 출력 및 스트리밍 처리.
"""

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

console = Console()


class StreamingUI:
    """스트리밍 응답 처리를 위한 UI 클래스"""

    def __init__(self):
        self.current_text = ""
        self.thinking_text = ""
        self.in_thinking = False
        self.live = None
        self.spinner = None

    def start(self):
        """스트리밍 시작"""
        self.current_text = ""
        self.thinking_text = ""
        self.in_thinking = False
        self.spinner = Live(
            Spinner("dots", text="Thinking..."),
            console=console,
            refresh_per_second=10,
        )
        self.spinner.start()

    def stop(self):
        """스트리밍 종료"""
        if self.spinner:
            self.spinner.stop()
            self.spinner = None
        if self.live:
            self.live.stop()
            self.live = None

    def start_thinking(self):
        """Thinking 블록 시작"""
        self.in_thinking = True
        self.thinking_text = ""
        if self.spinner:
            self.spinner.stop()
            self.spinner = None
        self.live = Live(
            Panel(Text("..."), title="[bold yellow]Thinking[/bold yellow]", border_style="yellow"),
            console=console,
            refresh_per_second=4,
        )
        self.live.start()

    def append_thinking(self, text: str):
        """Thinking 텍스트 추가"""
        self.thinking_text += text
        if self.live:
            # 너무 길면 마지막 부분만 표시
            display_text = self.thinking_text
            if len(display_text) > 2000:
                display_text = "..." + display_text[-2000:]
            self.live.update(
                Panel(
                    Text(display_text),
                    title="[bold yellow]Thinking[/bold yellow]",
                    border_style="yellow",
                )
            )

    def end_thinking(self):
        """Thinking 블록 종료"""
        self.in_thinking = False
        if self.live:
            # 최종 상태로 업데이트 후 종료
            if self.thinking_text:
                self.live.update(
                    Panel(
                        Markdown(f"**Reasoning:**\n\n{self.thinking_text}"),
                        title="[bold yellow]Thinking[/bold yellow]",
                        border_style="yellow",
                    )
                )
            self.live.stop()
            self.live = None

    def start_text(self):
        """텍스트 응답 시작"""
        self.current_text = ""
        if self.spinner:
            self.spinner.stop()
            self.spinner = None
        self.live = Live(
            Panel(Text(""), title="[bold blue]Assistant[/bold blue]", border_style="blue"),
            console=console,
            refresh_per_second=10,
        )
        self.live.start()

    def append_text(self, text: str):
        """텍스트 추가"""
        self.current_text += text
        if self.live:
            self.live.update(
                Panel(
                    Markdown(self.current_text),
                    title="[bold blue]Assistant[/bold blue]",
                    border_style="blue",
                )
            )

    def end_text(self):
        """텍스트 응답 종료"""
        if self.live:
            self.live.stop()
            self.live = None

    def show_tool_call(self, tool_name: str):
        """도구 호출 표시"""
        if self.spinner:
            self.spinner.stop()
            self.spinner = None
        console.print(f"[cyan]Tool:[/cyan] {tool_name}")
        # 다시 스피너 시작
        self.spinner = Live(
            Spinner("dots", text="Running..."),
            console=console,
            refresh_per_second=10,
        )
        self.spinner.start()


def display_response(result: dict):
    """AI 응답 표시 (비스트리밍 - 호환성 유지)"""
    if not result or "messages" not in result:
        return

    messages = result["messages"]
    if not messages:
        return

    last_message = messages[-1]
    content = getattr(last_message, "content", None)

    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "thinking":
                    thinking_text = block.get("thinking", "")
                    if thinking_text:
                        console.print(
                            Panel(
                                Markdown(f"**Reasoning:**\n\n{thinking_text}"),
                                title="[bold yellow]Thinking[/bold yellow]",
                                border_style="yellow",
                            )
                        )
                elif block_type == "text":
                    text = block.get("text", "")
                    if text:
                        console.print(
                            Panel(
                                Markdown(text),
                                title="[bold blue]Assistant[/bold blue]",
                                border_style="blue",
                            )
                        )
    elif content:
        console.print(
            Panel(
                Markdown(str(content)),
                title="[bold blue]Assistant[/bold blue]",
                border_style="blue",
            )
        )

    tool_calls = getattr(last_message, "tool_calls", [])
    for tc in tool_calls:
        if isinstance(tc, dict):
            console.print(f"[cyan]Used tool:[/cyan] {tc.get('name', 'unknown')}")


def display_welcome():
    """환영 메시지 표시"""
    console.print(
        Panel(
            "[bold]Custom Claude Code - Version 2.3: DeepAgents[/bold]\n\n"
            "Built on LangChain DeepAgents framework\n"
            "Features: Middleware, SubAgents, Checkpointing\n\n"
            "Commands: quit, clear, help",
            title="Welcome",
            border_style="magenta",
        )
    )


def display_help():
    """도움말 표시"""
    console.print(
        Panel(
            """**Commands:**
- quit: Exit the program
- clear: Clear conversation history
- help: Show this help

**DeepAgents Built-in Tools:**
- write_todos: Task planning and tracking
- ls, read_file, write_file, edit_file: File operations
- spawn_agent: Delegate to sub-agents

**Custom Tools:**
- run_bash, bash_background, bash_output, kill_shell: Bash execution
- grep_code: Code search with ripgrep
- web_search, web_fetch: Web access""",
            title="[bold green]Help[/bold green]",
            border_style="green",
        )
    )


def display_error(e: Exception):
    """에러 표시"""
    import traceback
    console.print(f"[red]Error: {type(e).__name__}: {str(e)}[/red]")
    console.print(f"[dim]{traceback.format_exc()}[/dim]")


def display_todos(todos: list):
    """Todo 목록을 체크박스(☐/☒) 형식으로 표시"""
    if not todos:
        return

    lines = []
    completed_count = 0

    for todo in todos:
        status = todo.get("status", "pending")
        content = todo.get("content", "")
        active_form = todo.get("activeForm", content)

        if status == "completed":
            lines.append(f"[green]☒[/green] [dim]{content}[/dim]")
            completed_count += 1
        elif status == "in_progress":
            lines.append(f"[yellow]☐[/yellow] [bold]{active_form}[/bold]")
        else:
            lines.append(f"☐ {content}")

    todo_text = "\n".join(lines)
    console.print(
        Panel(
            todo_text,
            title=f"[bold magenta]Todos ({completed_count}/{len(todos)})[/bold magenta]",
            border_style="magenta",
        )
    )
