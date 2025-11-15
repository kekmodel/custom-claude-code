"""
v4: Claude Agent SDK - Ultimate Simplicity

Using Anthropic's official Claude Agent SDK:
- Subagents: Defined via agents parameter (no code needed!)
- System Prompt: claude_code preset
- Tools: All built into SDK
- Total code: ~280 lines (with UI), Core logic: ~50 lines!
"""

import asyncio
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from .config import SUBAGENTS

# Load environment variables
load_dotenv()

# Rich console
console = Console()

# Prompt session
prompt_session = PromptSession(history=InMemoryHistory())


# ============================================================================
# Main Conversation Loop
# ============================================================================


async def run_conversation_loop():
    """
    Claude Agent SDK conversation loop

    Key differences from other versions:
    - v1: Manual while loop + tool execution
    - v2: StateGraph automatic loop
    - v3: Agent + Runner.run()
    - v4: ClaudeSDKClient + agents parameter (simplest!)
    """
    console.print(
        Panel(
            "[bold]Custom Claude Code - Version 4: Claude Agent SDK[/bold]\n\n"
            "Features:\n"
            "  - Anthropic official SDK\n"
            "  - Subagents: agents parameter (4 types)\n"
            "  - System prompt: claude_code preset\n"
            "  - All tools: Read, Write, Edit, Bash, Glob, Grep\n"
            "  - Native MCP support (extensible)\n\n"
            "Commands:\n"
            "  - Type 'quit' to exit\n"
            "  - Type 'cost' to see total cost",
            title="Welcome",
            border_style="magenta",
        )
    )

    # Claude Agent SDK options
    options = ClaudeAgentOptions(
        # Tool configuration
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
            "Bash",
            "Glob",
            "Grep",
            # Subagent tools are automatically added!
        ],
        # Permission mode
        permission_mode="default",  # Ask user for confirmation
        # System prompt - Use Claude Code preset!
        system_prompt={
            "type": "preset",
            "preset": "claude_code",  # Claude Code's official prompt!
        },
        # Working directory
        cwd=Path.cwd(),
        # Subagents definition (The key!)
        agents=SUBAGENTS,
        # Model
        model="haiku",  # Haiku 4.5 (claude-haiku-4-5-20251001)
        # Limits
        max_turns=50,
        max_thinking_tokens=10000,
        # Streaming
        include_partial_messages=True,
    )

    # Cost tracking
    total_cost = 0.0

    # Start Claude SDK Client
    async with ClaudeSDKClient(options=options) as client:
        while True:
            # User input
            try:
                user_input = await prompt_session.prompt_async("\n> ")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]Goodbye![/yellow]")
                break

            # Handle commands
            if user_input.lower() == "quit":
                console.print("[yellow]Goodbye![/yellow]")
                break

            if user_input.lower() == "cost":
                console.print(f"[cyan]Total cost so far: ${total_cost:.4f}[/cyan]")
                continue

            if not user_input.strip():
                continue

            # Query Claude
            try:
                console.print("\n[dim]Thinking...[/dim]\n")

                await client.query(user_input)

                # Receive and display response
                async for message in client.receive_response():
                    # Assistant messages
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                # Text output
                                console.print(
                                    Panel(
                                        Markdown(block.text),
                                        title="[bold blue]Assistant[/bold blue]",
                                        border_style="blue",
                                    )
                                )

                            elif isinstance(block, ThinkingBlock):
                                # Thinking process (optional display)
                                console.print(f"[dim italic]Thinking: {block.thinking[:100]}...[/dim italic]")

                            elif isinstance(block, ToolUseBlock):
                                # Tool use
                                console.print(f"[cyan]Using tool: {block.name}[/cyan]")

                    # User messages (includes tool results)
                    elif isinstance(message, UserMessage):
                        for block in message.content:
                            if isinstance(block, ToolResultBlock):
                                # Don't display tool results if too long
                                console.print(f"[dim]Tool {block.tool_use_id[:8]}... completed[/dim]")

                    # Result message (cost, token usage)
                    elif isinstance(message, ResultMessage):
                        total_cost += message.total_cost_usd
                        # Handle both object and dict usage formats
                        try:
                            if hasattr(message.usage, 'input_tokens'):
                                input_tokens = message.usage.input_tokens
                                output_tokens = message.usage.output_tokens
                            else:
                                # Usage might be a dict
                                input_tokens = message.usage.get('input_tokens', 0)
                                output_tokens = message.usage.get('output_tokens', 0)

                            console.print(
                                f"\n[dim]Cost: ${message.total_cost_usd:.4f} | "
                                f"Tokens: {input_tokens} in, {output_tokens} out[/dim]"
                            )
                        except Exception:
                            console.print(f"\n[dim]Cost: ${message.total_cost_usd:.4f}[/dim]")

            except Exception as e:
                error_msg = f"Error: {type(e).__name__}: {str(e)}"
                # Escape Rich markup characters
                error_msg = error_msg.replace("[", "\\[").replace("]", "\\]")
                console.print(f"[red]{error_msg}[/red]")

                import traceback
                tb = traceback.format_exc()
                # Escape Rich markup in traceback
                tb = tb.replace("[", "\\[").replace("]", "\\]")
                console.print(f"[dim]{tb}[/dim]")


async def main():
    """Main function"""
    await run_conversation_loop()


if __name__ == "__main__":
    asyncio.run(main())
