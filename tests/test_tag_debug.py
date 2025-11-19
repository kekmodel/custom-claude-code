"""
이벤트 태그 디버깅

Subagent 이벤트의 실제 태그를 확인
"""

import asyncio
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

load_dotenv()


async def main():
    from custom_claude_code.v2_1_langgraph_improved.graph import graph

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY needed")
        return

    initial_state = {
        "messages": [HumanMessage(content="Use Explore agent to list Python files")],
        "working_dir": os.getcwd(),
        "depth": 0,
        "todos": None,
    }

    config = {"recursion_limit": 50}

    print("이벤트 태그 추적:\n")

    async for event in graph.astream_events(initial_state, config=config, version="v2"):
        kind = event.get("event")

        if kind == "on_chat_model_stream":
            tags = event.get("tags", [])
            name = event.get("name", "")

            # 태그 출력
            step_tags = [t for t in tags if "step:" in t or "graph:" in t]
            if step_tags:
                has_agent = "agent" in tags
                print(f"  Stream event: tags={step_tags}, has_agent={has_agent}, name={name}")

        elif kind == "on_chat_model_end":
            tags = event.get("tags", [])
            name = event.get("name", "")

            step_tags = [t for t in tags if "step:" in t or "graph:" in t]
            if step_tags:
                has_agent = "agent" in tags
                print(f"  End event: tags={step_tags}, has_agent={has_agent}, name={name}")


if __name__ == "__main__":
    asyncio.run(main())
