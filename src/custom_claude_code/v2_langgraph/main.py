"""
v2: LangGraph 메인 실행 루프

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 이 파일의 역할: LangGraph 실행 및 사용자 인터페이스
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

이 파일에서 배울 것:
    ✅ LangGraph 그래프 실행 방법 (graph.astream)
    ✅ 스트리밍 이벤트 처리 (노드별 업데이트)
    ✅ 대화 이력 관리
    ✅ 사용자 인터페이스 패턴
    ✅ 에러 처리 및 리커전 제한

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 v1 vs v2 비교: 코드가 얼마나 간단해졌는지!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

v1 (OpenAI API 직접 사용):
    - run_conversation_loop(): ~200줄
    - 내부 while 루프로 도구 호출 처리
    - finish_reason 체크
    - 수동 메시지 관리

v2 (LangGraph):
    - run_conversation_loop(): ~95줄
    - 그래프가 자동으로 도구 루프 처리!
    - graph.astream()만 호출
    - 상태는 그래프가 자동 관리

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 환경 설정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# .env 파일에서 환경 변수 로드 (ANTHROPIC_API_KEY, OPENAI_API_KEY 등)
load_dotenv()

# Rich console: 터미널 출력 포맷팅 (색상, 패널, 마크다운 렌더링 등)
console = Console()

# prompt_toolkit: 터미널 입력 처리 (히스토리, 자동완성 등 지원)
prompt_session = PromptSession(history=InMemoryHistory())


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메시지 출력 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def display_message(message):
    """
    📺 메시지를 Rich 포맷으로 표시

    LangChain 메시지 타입에 따라 다른 스타일로 출력:
        - HumanMessage: 사용자 입력 (녹색 패널)
        - AIMessage: LLM 응답 (파란색 패널, 마크다운 렌더링)
        - ToolMessage: 도구 실행 결과 (회색 텍스트)

    Args:
        message: LangChain BaseMessage (HumanMessage, AIMessage, ToolMessage 등)

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    📌 확장 팁: 커스텀 UI 추가

    **예시 1: 토큰 사용량 표시**
    ```python
    elif isinstance(message, AIMessage):
        if hasattr(message, "usage_metadata"):
            console.print(f"[dim]Tokens: {message.usage_metadata}[/dim]")
    ```

    **예시 2: 다중 모달 출력 (이미지)**
    ```python
    if hasattr(message, "image_url"):
        from rich.image import Image
        console.print(Image.from_url(message.image_url))
    ```

    **예시 3: 도구 실행 시간 측정**
    ```python
    elif isinstance(message, ToolMessage):
        if hasattr(message, "execution_time"):
            console.print(f"[dim]Executed in {message.execution_time}s[/dim]")
    ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 사용자 메시지: 녹색 패널
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if isinstance(message, HumanMessage):
        console.print(Panel(message.content, title="[bold green]You[/bold green]", border_style="green"))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # AI 응답: 파란색 패널 + 마크다운 렌더링
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    elif isinstance(message, AIMessage):
        # content가 있으면 표시 (빈 content는 스킵 - tool_calls만 있는 경우)
        if message.content:
            console.print(
                Panel(Markdown(message.content), title="[bold blue]Assistant[/bold blue]", border_style="blue")
            )

        # tool_calls가 있으면 도구 이름 표시
        if message.tool_calls:
            for tc in message.tool_calls:
                console.print(f"[cyan]🔧 Calling tool:[/cyan] {tc['name']}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 도구 실행 결과: 간략히 표시 (500자 제한)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    elif isinstance(message, ToolMessage):
        # 너무 긴 결과는 잘라서 표시
        result = message.content[:500] + "..." if len(message.content) > 500 else message.content
        console.print(f"[dim]  → Result: {result}[/dim]\n")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 대화 루프
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def run_conversation_loop():
    """
    🔄 메인 대화 루프 (LangGraph 버전)

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    🎯 LangGraph의 장점: 내부 도구 루프가 없다!

    v1 (OpenAI 직접 사용):
        ```python
        while True:  # 외부 대화 루프
            user_input = input()
            messages.append(user_input)

            while True:  # 내부 도구 루프
                response = client.chat.completions.create(...)
                if response.finish_reason == "stop":
                    break
                # 도구 실행...
        ```

    v2 (LangGraph):
        ```python
        while True:  # 외부 대화 루프만!
            user_input = input()
            messages.append(user_input)

            async for event in graph.astream(...):
                # 그래프가 자동으로 도구 루프 처리!
                display_message(event)
        ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    🔄 실행 흐름:

    1. 사용자 입력 받기 (prompt_toolkit)
    2. 명령어 처리 (quit, clear, graph)
    3. HumanMessage로 변환하여 messages에 추가
    4. graph.astream() 호출:
       ┌─────────────────────────────────────────┐
       │ graph.astream() 내부:                   │
       ├─────────────────────────────────────────┤
       │ START → agent → should_continue         │
       │   ↓              ↓                      │
       │ tools ←────── "tools"                   │
       │   ↓                                     │
       │ agent (결과 처리) → END                 │
       └─────────────────────────────────────────┘
    5. 각 노드의 업데이트를 이벤트로 수신 (스트리밍!)
    6. 새 메시지 표시 및 히스토리 업데이트
    7. 그래프 종료 시 다음 사용자 입력 대기

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    💡 graph.astream() 이해하기

    **stream_mode 옵션:**

    - "values" (기본값):
        각 노드 실행 후 전체 상태 반환
        ```python
        {"messages": [...전체 메시지 목록...], "working_dir": "..."}
        ```

    - "updates":
        각 노드가 반환한 업데이트만 반환 (우리가 사용!)
        ```python
        {"agent": {"messages": [AIMessage(...)]}}
        {"tools": {"messages": [ToolMessage(...)]}}
        ```

    - "debug":
        디버깅 정보 포함 (노드 이름, 실행 시간 등)

    **config 옵션:**

    - recursion_limit: 최대 노드 실행 횟수 (무한 루프 방지)
    - configurable: checkpointer 사용 시 thread_id 등 설정

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    📌 확장 패턴: 다양한 실행 방식

    **패턴 1: 배치 실행 (invoke)**
    ```python
    result = await graph.ainvoke(
        {"messages": messages, "working_dir": working_dir, "depth": 0}
    )
    # 결과가 한 번에 반환됨 (스트리밍 없음)
    ```

    **패턴 2: 멀티턴 대화 (checkpointer)**
    ```python
    from .graph import graph_with_memory
    config = {"configurable": {"thread_id": "user123"}}

    # 첫 번째 턴
    await graph_with_memory.ainvoke(state1, config=config)

    # 두 번째 턴 (이전 대화 이력 유지!)
    await graph_with_memory.ainvoke(state2, config=config)
    ```

    **패턴 3: 이벤트 필터링**
    ```python
    async for event in graph.astream(..., stream_mode="updates"):
        for node_name, node_output in event.items():
            if node_name == "agent":  # agent 노드만 처리
                process_agent_output(node_output)
    ```

    **패턴 4: 중단 가능 실행**
    ```python
    task = asyncio.create_task(graph.astream(...))
    try:
        async for event in task:
            if user_cancelled():
                task.cancel()
                break
    except asyncio.CancelledError:
        console.print("Execution cancelled")
    ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 환영 메시지
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 대화 상태 초기화
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    messages = []  # 대화 히스토리 (LangChain 메시지 목록)
    working_dir = os.getcwd()  # 현재 작업 디렉토리

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 메인 대화 루프
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    while True:
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 1️⃣ 사용자 입력 받기
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        try:
            user_input = await prompt_session.prompt_async("\n> ")
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C 또는 Ctrl+D
            console.print("\n[yellow]Goodbye![/yellow]")
            break

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 2️⃣ 명령어 처리
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        if user_input.lower() == "quit":
            console.print("[yellow]Goodbye![/yellow]")
            break

        if user_input.lower() == "clear":
            messages.clear()
            console.print("[yellow]History cleared![/yellow]")
            continue

        if user_input.lower() == "graph":
            # 그래프 시각화 (Mermaid 다이어그램)
            console.print("[yellow]Graph visualization:[/yellow]")
            try:
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

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 3️⃣ 사용자 메시지 추가 및 표시
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        user_message = HumanMessage(content=user_input)
        messages.append(user_message)
        display_message(user_message)

        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # 4️⃣ LangGraph 실행 (스트리밍!)
        # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        try:
            # recursion_limit: 무한 루프 방지 (최대 50번 노드 실행)
            config = {"recursion_limit": 50}

            # graph.astream()으로 실시간 업데이트 수신
            # - stream_mode="updates": 각 노드의 업데이트만 반환
            # - 각 노드 실행 후 이벤트 발생 (agent → tools → agent → ...)
            async for event in graph.astream(
                {"messages": messages, "working_dir": working_dir, "depth": 0},
                config=config,
                stream_mode="updates",  # 노드별 업데이트만 (전체 상태 아님)
            ):
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # 5️⃣ 각 노드의 업데이트 처리
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                # event 구조:
                # {
                #     "agent": {"messages": [AIMessage(...)]},
                #     "tools": {"messages": [ToolMessage(...)]},
                # }
                for node_name, node_output in event.items():
                    # 노드 이름 표시 (디버깅용)
                    console.print(f"[dim]({node_name})[/dim]")

                    # 새 메시지가 있으면 표시 및 히스토리 업데이트
                    if "messages" in node_output:
                        for msg in node_output["messages"]:
                            display_message(msg)  # Rich 포맷으로 표시
                            messages.append(msg)  # 히스토리에 추가

                # 노드 실행이 끝나면 다음 이벤트 대기
                # (graph가 자동으로 다음 노드 실행!)

        except Exception as e:
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 에러 처리
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            console.print(f"[red]Error: {type(e).__name__}: {str(e)}[/red]")
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 메인 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    """
    📌 프로그램 진입점

    asyncio.run(main())으로 실행됨 (비동기 이벤트 루프 시작)
    """
    await run_conversation_loop()


if __name__ == "__main__":
    import asyncio

    # 비동기 이벤트 루프 시작
    asyncio.run(main())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📌 다른 도메인으로 확장하기: UI 커스터마이징 예시
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
**예시 1: 웹 UI 통합 (FastAPI + WebSocket)**

```python
from fastapi import FastAPI, WebSocket
from .graph import graph

app = FastAPI()

@app.websocket("/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    messages = []

    while True:
        # 사용자 메시지 수신
        user_input = await websocket.receive_text()
        messages.append(HumanMessage(content=user_input))

        # LangGraph 실행 및 스트리밍
        async for event in graph.astream({"messages": messages, ...}):
            for node_name, node_output in event.items():
                if "messages" in node_output:
                    for msg in node_output["messages"]:
                        # WebSocket으로 실시간 전송!
                        await websocket.send_json({
                            "type": msg.__class__.__name__,
                            "content": msg.content
                        })
```

**예시 2: Slack Bot 통합**

```python
from slack_bolt.async_app import AsyncApp
from .graph import graph_with_memory

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])

@app.message()
async def handle_message(message, say):
    user_id = message["user"]
    config = {"configurable": {"thread_id": user_id}}  # 사용자별 대화 이력

    messages = [HumanMessage(content=message["text"])]

    async for event in graph_with_memory.astream(
        {"messages": messages, ...},
        config=config
    ):
        for node_name, node_output in event.items():
            if "messages" in node_output:
                for msg in node_output["messages"]:
                    if isinstance(msg, AIMessage):
                        await say(msg.content)  # Slack에 응답
```

**예시 3: Discord Bot**

```python
import discord
from .graph import graph_with_memory

client = discord.Client(intents=discord.Intents.default())

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    config = {"configurable": {"thread_id": str(message.channel.id)}}
    messages = [HumanMessage(content=message.content)]

    async for event in graph_with_memory.astream(
        {"messages": messages, ...},
        config=config
    ):
        for node_name, node_output in event.items():
            if "messages" in node_output:
                for msg in node_output["messages"]:
                    if isinstance(msg, AIMessage) and msg.content:
                        await message.channel.send(msg.content)
```

**예시 4: GUI (Gradio)**

```python
import gradio as gr
from .graph import graph

async def chat(message, history):
    messages = []
    for h in history:
        messages.append(HumanMessage(content=h[0]))
        messages.append(AIMessage(content=h[1]))
    messages.append(HumanMessage(content=message))

    response = ""
    async for event in graph.astream({"messages": messages, ...}):
        for node_name, node_output in event.items():
            if "messages" in node_output:
                for msg in node_output["messages"]:
                    if isinstance(msg, AIMessage):
                        response += msg.content

    return response

demo = gr.ChatInterface(chat)
demo.launch()
```
"""
