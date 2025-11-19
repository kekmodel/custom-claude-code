"""
v3: OpenAI Agents SDK 메인

극도로 간단!
- Agent() 정의
- Runner.run() 실행
- 끝!
"""

import asyncio
import os
import platform as platform_module
from datetime import datetime

from agents import Agent, Runner, SQLiteSession, set_default_openai_client
from dotenv import load_dotenv
from openai import AsyncOpenAI
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .tools import TOOLS, edit_file, glob_files, grep_code, read_file, write_file

# 환경 변수 로드
load_dotenv()

# Configure OpenAI API for v3 (OpenAI Agents SDK requires actual OpenAI API)
# Note: v3 uses OpenAI API key, not Anthropic
v3_api_key = os.getenv("OPENAI_API_KEY_V3") or os.getenv("OPENAI_API_KEY")
if not v3_api_key:
    raise ValueError(
        "❌ OpenAI API key not found!\n"
        "v3 requires OpenAI API (not Anthropic).\n"
        "Please set OPENAI_API_KEY_V3 or OPENAI_API_KEY in your .env file.\n"
        "Get your key from: https://platform.openai.com/api-keys"
    )

# v3 must use OpenAI's endpoint, not Anthropic's
# Explicitly set base_url to OpenAI (ignore OPENAI_BASE_URL env var)
custom_client = AsyncOpenAI(
    api_key=v3_api_key,
    base_url="https://api.openai.com/v1"  # Force OpenAI endpoint
)
set_default_openai_client(custom_client)

# Rich console
console = Console()

# Prompt session
prompt_session = PromptSession(history=InMemoryHistory())


def get_instructions() -> str:
    """
    간소화된 instructions (OpenAI Agents SDK 스타일)
    """
    working_dir = os.getcwd()
    is_git_repo = os.path.exists(os.path.join(working_dir, ".git"))
    platform_name = platform_module.system().lower()
    os_version = platform_module.platform()
    today = datetime.now().strftime("%Y-%m-%d")

    return f"""You are a coding assistant.

# Environment

Working directory: {working_dir}
Is directory a git repo: {"Yes" if is_git_repo else "No"}
Platform: {platform_name}
OS Version: {os_version}
Today's date: {today}

# Tools

You have access to these tools:
- read_file: Read files with line numbers
- write_file: Create or overwrite files
- edit_file: Edit files by replacing strings
- glob_files: Find files by glob pattern
- grep_code: Search code with regex
- run_bash: Execute bash commands

# Guidelines

1. Read before Edit: Always read_file before edit_file
2. Absolute Paths: Use absolute file paths
3. Safety: Verify dangerous operations
4. Code References: Use `file_path:line_number` format
5. Be concise and helpful

Now, help the user with their request."""


# ============================================================================
# Subagent 정의 (Claude Code의 핵심!)
# ============================================================================

# Explore Agent - 코드베이스 탐색 전문
explore_agent = Agent(
    name="Explore Agent",
    model="gpt-5.1-codex-mini",
    instructions="""You are a specialized agent for exploring codebases.

Your role:
- Find files by patterns (glob)
- Search code for keywords (grep)
- Answer questions about codebase structure
- Provide quick, focused exploration results

You have access to:
- glob_files: Find files by pattern
- grep_code: Search code with regex
- read_file: Read specific files

Be thorough and concise. Return your findings in a clear report.""",
    tools=[glob_files, grep_code, read_file],
)

# Plan Agent - 계획 수립 전문
plan_agent = Agent(
    name="Plan Agent",
    model="gpt-5.1-codex-mini",
    instructions="""You are a specialized agent for planning implementation tasks.

Your role:
- Analyze requirements
- Break down complex tasks into steps
- Suggest implementation approaches
- Identify potential challenges

You have access to:
- glob_files: Find relevant files
- grep_code: Search existing implementations
- read_file: Read files to understand current code

Return a clear, actionable plan.""",
    tools=[glob_files, grep_code, read_file],
)

# General-purpose Agent - 일반 작업
general_purpose_agent = Agent(
    name="General Purpose Agent",
    model="gpt-5.1-codex-mini",
    instructions="""You are a general-purpose coding agent.

Your role:
- Handle complex, multi-step tasks autonomously
- Search for code and files
- Execute various operations
- Provide comprehensive solutions

You have full access to all tools.

Be thorough and complete your assigned tasks.""",
    tools=TOOLS,  # 모든 도구 접근
)

# Statusline-setup Agent - 설정 파일 편집 전문
statusline_setup_agent = Agent(
    name="Statusline Setup Agent",
    model="gpt-5.1-codex-mini",
    instructions="""You are a specialized agent for configuring Claude Code status line settings.

Your role:
- Read configuration files
- Edit settings safely
- Validate changes

You have access to:
- read_file: Read config files
- edit_file: Edit config files

Be careful and precise with configuration changes.""",
    tools=[read_file, edit_file],
)


# ============================================================================
# Main Agent with Subagents (as tools!)
# ============================================================================

# Subagent들을 도구로 변환
explore_tool = explore_agent.as_tool(
    tool_name="task_explore",
    tool_description="Launch an Explore agent to search and analyze the codebase"
)

plan_tool = plan_agent.as_tool(
    tool_name="task_plan",
    tool_description="Launch a Plan agent to break down complex tasks into steps"
)

general_purpose_tool = general_purpose_agent.as_tool(
    tool_name="task_general",
    tool_description="Launch a general-purpose agent for complex multi-step tasks"
)

statusline_setup_tool = statusline_setup_agent.as_tool(
    tool_name="task_statusline_setup",
    tool_description="Launch a specialized agent to configure Claude Code status line settings"
)

# Main Agent (Subagent 도구 포함!)
agent = Agent(
    name="Coding Assistant",
    model="gpt-5.1-codex-mini",
    instructions=get_instructions(),
    tools=TOOLS
    + [
        explore_tool,
        plan_tool,
        general_purpose_tool,
        statusline_setup_tool,
    ],
)


async def run_conversation_loop():
    """
    메인 대화 루프 (OpenAI Agents SDK 버전)

    v1/v2와의 차이:
    - while 루프 없음! (Runner.run()이 자동 처리)
    - StateGraph 없음! (SDK가 자동 처리)
    - 코드가 극도로 간단함!
    """
    console.print(
        Panel(
            "[bold]Custom Claude Code - Version 3: OpenAI Agents SDK[/bold]\n\n"
            "✨ Features:\n"
            "  - Ultra-simple Agent + Runner pattern\n"
            "  - Automatic tool-calling loop\n"
            "  - Session memory support\n"
            "  - 11 tools (file, search, bash, web, background)\n\n"
            "Commands:\n"
            "  - Type 'quit' to exit\n"
            "  - Type 'clear' to clear history",
            title="Welcome",
            border_style="magenta",
        )
    )

    # Session (대화 히스토리 자동 관리!)
    # Create data directory if it doesn't exist
    import os
    os.makedirs("data", exist_ok=True)
    session = SQLiteSession("conversation_v3", "data/v3_conversations.db")

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
            await session.clear_session()
            console.print("[yellow]History cleared![/yellow]")
            continue

        if not user_input.strip():
            continue

        # OpenAI Agents SDK 실행 (한 줄!)
        try:
            console.print("\n[dim]Thinking...[/dim]\n")

            # 이게 전부! Runner.run()이 모든 것을 처리!
            result = await Runner.run(agent, input=user_input, session=session)  # 히스토리 자동 관리!

            # 결과 표시
            console.print(
                Panel(Markdown(result.final_output), title="[bold blue]Assistant[/bold blue]", border_style="blue")
            )

            # 디버그: 사용된 도구 표시
            if hasattr(result, "turns") and result.turns:
                console.print(f"\n[dim]Turns: {len(result.turns)}[/dim]")

        except Exception as e:
            console.print(f"[red]Error: {type(e).__name__}: {str(e)}[/red]")
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")


async def main():
    """메인 함수"""
    await run_conversation_loop()


if __name__ == "__main__":
    asyncio.run(main())
