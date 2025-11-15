"""
🎯 Simple Live Demo
v1으로 실제 대화를 시뮬레이션
"""

import asyncio
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load environment
load_dotenv()

console = Console()


async def main():
    """Simple conversation demo"""
    console.print("\n" + "="*80, style="bold cyan")
    console.print("🎬 LIVE DEMO: v1 + Anthropic Claude Haiku 4.5", style="bold cyan")
    console.print("="*80 + "\n", style="bold cyan")

    from custom_claude_code.v1_openai.main import run_conversation_loop

    # Run the actual conversation loop!
    await run_conversation_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo ended![/yellow]")
