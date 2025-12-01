"""
v2.3: DeepAgents 기반 메인 실행 루프

특징:
- create_deep_agent로 에이전트 생성
- astream_events()로 토큰 단위 스트리밍
- 내장 Middleware 활용 (TodoList, Filesystem, SubAgent, Summarization)
- 커스텀 Middleware로 bash, grep, web 도구 추가
- MemorySaver checkpointer로 대화 스레드 체크포인팅
- Ctrl+C로 실행 중단 후 새 지시 가능
"""

import asyncio
import time
import uuid
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from .config import create_model, config
from .prompts import get_system_prompt
from .middleware import get_custom_middleware, ALL_CUSTOM_TOOLS
from .ui import console, StreamingUI, display_welcome, display_help, display_error, display_todos

load_dotenv()
prompt_session = PromptSession(history=InMemoryHistory())

# 세션 ID 생성 (프로그램 실행당 하나)
SESSION_ID = str(uuid.uuid4())[:8]


class StreamInterrupted(Exception):
    """스트리밍 중단 예외 (Ctrl+C)"""
    pass


def get_subagents():
    """Subagent 목록 반환

    Note: general-purpose는 DeepAgents가 자동으로 추가함
    """
    return [
        {
            "name": "Explore",
            "description": "코드베이스 탐색 전문. 파일 패턴 검색, 키워드 검색, 아키텍처 분석. 읽기 전용.",
            "system_prompt": "당신은 코드베이스 탐색 전문 Explore agent입니다. 파일 탐색과 분석만 수행합니다.",
            "tools": [],  # 기본 filesystem 도구만 사용
        },
        {
            "name": "Plan",
            "description": "구현 계획 수립 전문. 기능 구현, 버그 수정, 리팩토링 계획. 읽기 전용.",
            "system_prompt": "당신은 구현 계획 수립 전문 Plan agent입니다. 계획 수립만 수행합니다.",
            "tools": [],
        },
    ]


def create_agent():
    """DeepAgents 에이전트 생성"""
    try:
        from deepagents import create_deep_agent
        from deepagents.backends import FilesystemBackend
        from langgraph.checkpoint.memory import MemorySaver
        import os

        working_dir = os.getcwd()

        # Backend 설정: 실제 파일 시스템 접근
        backend = FilesystemBackend(root_dir=working_dir)

        # MemorySaver: 대화 스레드 체크포인팅 (대화 지속성)
        checkpointer = MemorySaver()

        # TODO: Long-term memory (CompositeBackend + StoreBackend)
        # DeepAgents 라이브러리 버전과 문서 API가 불일치하여 비활성화
        # config.enable_long_term_memory 옵션은 유지

        return create_deep_agent(
            model=create_model(),
            system_prompt=get_system_prompt(),
            tools=ALL_CUSTOM_TOOLS,
            middleware=get_custom_middleware(),
            subagents=get_subagents(),
            backend=backend,
            checkpointer=checkpointer,
        )
    except ImportError as e:
        console.print(f"[red]DeepAgents import error: {e}[/red]")
        console.print("[yellow]Run: uv add deepagents[/yellow]")
        return None


async def process_stream(agent, messages: list):
    """스트리밍 이벤트 처리"""
    ui = StreamingUI()
    ui.start()

    final_messages = messages.copy()
    in_text_block = False
    in_thinking_block = False
    displayed_tool_ids = set()  # 이미 표시한 도구 호출 ID

    run_config = {
        "recursion_limit": config.recursion_limit,
        "configurable": {"thread_id": SESSION_ID},
    }

    try:
        async for event in agent.astream_events({"messages": messages}, config=run_config, version="v2"):
            kind = event.get("event")
            tags = event.get("tags", [])

            # Main graph 이벤트만 처리 (subagent 필터링)
            is_main_graph = any(tag in ["seq:step:1", "graph:step:1"] for tag in tags)

            # 채팅 모델 스트리밍
            if kind == "on_chat_model_stream" and is_main_graph:
                chunk = event.get("data", {}).get("chunk")
                if not chunk:
                    continue

                content = getattr(chunk, "content", None)
                if not content:
                    continue

                # Extended Thinking: content가 list인 경우
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            block_type = block.get("type")

                            # Thinking 블록
                            if block_type == "thinking":
                                if not in_thinking_block:
                                    in_thinking_block = True
                                    ui.start_thinking()
                                thinking_delta = block.get("thinking", "")
                                if thinking_delta:
                                    ui.append_thinking(thinking_delta)

                            # Text 블록
                            elif block_type == "text":
                                if in_thinking_block:
                                    in_thinking_block = False
                                    ui.end_thinking()
                                if not in_text_block:
                                    in_text_block = True
                                    ui.start_text()
                                text_delta = block.get("text", "")
                                if text_delta:
                                    ui.append_text(text_delta)

                # 일반 문자열
                elif isinstance(content, str) and content:
                    if in_thinking_block:
                        in_thinking_block = False
                        ui.end_thinking()
                    if not in_text_block:
                        in_text_block = True
                        ui.start_text()
                    ui.append_text(content)

            # 채팅 모델 완료 - 도구 호출 확인
            elif kind == "on_chat_model_end" and is_main_graph:
                # 현재 스트리밍 종료
                if in_thinking_block:
                    in_thinking_block = False
                    ui.end_thinking()
                if in_text_block:
                    in_text_block = False
                    ui.end_text()

                # 도구 호출 표시 (중복 방지)
                output = event.get("data", {}).get("output")
                if output and hasattr(output, "tool_calls") and output.tool_calls:
                    for tc in output.tool_calls:
                        tool_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)
                        if tool_id and tool_id in displayed_tool_ids:
                            continue
                        if tool_id:
                            displayed_tool_ids.add(tool_id)
                        tool_name = tc.get("name", "unknown") if isinstance(tc, dict) else getattr(tc, "name", "unknown")
                        console.print(f"[cyan]Tool:[/cyan] {tool_name}")

            # 체인 종료 - 최종 메시지 및 todos 수집
            elif kind == "on_chain_end":
                output = event.get("data", {}).get("output", {})
                if isinstance(output, dict):
                    if "messages" in output:
                        final_messages = output["messages"]
                    # Todo 업데이트 표시
                    if "todos" in output and output["todos"]:
                        display_todos(output["todos"])

    except (KeyboardInterrupt, asyncio.CancelledError):
        # Ctrl+C로 중단됨 - UI 정리 후 예외 발생
        raise StreamInterrupted()

    finally:
        if in_thinking_block:
            ui.end_thinking()
        if in_text_block:
            ui.end_text()
        ui.stop()

    return final_messages


async def run_conversation_loop():
    """메인 대화 루프

    Ctrl+C 동작:
    - 스트리밍 중: 중단 후 새 지시 입력 가능
    - 프롬프트에서: 종료
    - 2초 내 연속 Ctrl+C: 즉시 종료
    """
    display_welcome()

    agent = create_agent()
    if agent is None:
        console.print("[red]Failed to create agent. Exiting.[/red]")
        return

    messages = []
    last_interrupt_time = 0.0

    while True:
        try:
            user_input = await prompt_session.prompt_async("\n> ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye![/yellow]")
            break

        if not user_input.strip():
            continue

        cmd = user_input.lower()
        if cmd == "quit":
            console.print("[yellow]Goodbye![/yellow]")
            break
        elif cmd == "clear":
            messages = []
            console.print("[yellow]History cleared![/yellow]")
            continue
        elif cmd == "help":
            display_help()
            continue

        messages.append(HumanMessage(content=user_input))

        try:
            result_messages = await process_stream(agent, messages)

            # 메시지 히스토리 업데이트 (원본 메시지 객체 유지)
            if result_messages:
                messages = list(result_messages)

        except (StreamInterrupted, KeyboardInterrupt, asyncio.CancelledError):
            # Ctrl+C로 스트리밍 중단됨
            current_time = time.time()

            # 2초 내 연속 Ctrl+C면 종료
            if current_time - last_interrupt_time < 2.0:
                console.print("\n[yellow]Goodbye![/yellow]")
                break

            last_interrupt_time = current_time
            console.print("\n[yellow]중단됨. 새 지시를 입력하세요. (2초 내 Ctrl+C: 종료)[/yellow]")
            # 마지막 사용자 메시지 제거 (재입력 받을 것이므로)
            if messages and isinstance(messages[-1], HumanMessage):
                messages.pop()

        except Exception as e:
            display_error(e)


async def main():
    """메인 엔트리포인트"""
    await run_conversation_loop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
