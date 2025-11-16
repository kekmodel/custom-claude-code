"""
v2: LangGraph StateGraph 구성

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 이 파일의 역할: LangGraph StateGraph 구성 및 워크플로우 정의
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LangGraph의 핵심 개념:
    StateGraph = 노드(Node) + 엣지(Edge) + 상태(State)

이 파일에서 배울 것:
    ✅ StateGraph 생성 패턴
    ✅ 노드 추가 방법 (add_node)
    ✅ 엣지 연결 방법 (add_edge, add_conditional_edges)
    ✅ 커스텀 도구 노드 구현 (Subagent 지원)
    ✅ Checkpointer를 활용한 메모리 관리
    ✅ 새로운 노드/엣지 추가 확장 패턴

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Claude Code의 워크플로우 구조 (DAG):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    START
      ↓
    agent (LLM 호출)
      ↓
    conditional_edge (should_continue 판단)
      ↓                    ↓
    tools               END
      ↓
    agent (다시 루프)

핵심 특징:
    - 단방향 흐름 (Directed Acyclic Graph)
    - agent ↔ tools 사이만 루프 가능
    - 사용자가 항상 제어권 유지

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import call_agent, execute_subagent, get_system_prompt, should_continue
from .tools import TOOLS_BY_NAME
from .types import AgentState

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 커스텀 도구 실행 노드 (Subagent 지원)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def execute_tools(state: AgentState) -> dict:
    """
    🔧 커스텀 도구 실행 노드 (LangGraph ToolNode의 커스텀 버전)

    💡 왜 LangGraph의 기본 ToolNode를 안 쓰나요?

    LangGraph는 ToolNode라는 편리한 기본 노드를 제공하지만,
    우리는 특별한 요구사항이 있습니다:

        ❌ 문제: task_tool은 일반 도구가 아니라 **Subagent를 실행**해야 함
        ❌ 문제: todo_write는 state를 업데이트해야 함
        ✅ 해결: 커스텀 노드로 특수 도구를 별도 처리!

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    🔄 실행 흐름:

    1. 마지막 AIMessage에서 tool_calls 추출
    2. 각 tool_call에 대해:
       ┌─────────────────────────────────────────┐
       │ task_tool?                              │
       │   → execute_subagent() 호출             │
       │                                         │
       │ todo_write?                             │
       │   → state의 todos 업데이트              │
       │                                         │
       │ 기타                                    │
       │   → TOOLS_BY_NAME에서 도구 찾아 실행    │
       └─────────────────────────────────────────┘
    3. 결과를 ToolMessage로 변환
    4. {"messages": [...], "todos": [...]} 반환

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Args:
        state: 현재 AgentState (messages, working_dir, depth, todos 포함)

    Returns:
        dict: {"messages": [ToolMessage, ...], "todos": [...]}
              StateGraph가 자동으로 기존 messages에 append하고 todos 업데이트

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    📌 확장 팁: 다른 특수 도구 처리 추가하기

    만약 다른 도구도 특별한 처리가 필요하다면:

    ```python
    if tool_name == "task_tool":
        # Subagent 실행
        result = await execute_subagent(...)
    elif tool_name == "approval_required_tool":
        # 사용자 승인 받기
        result = await ask_user_approval(tool_args)
    elif tool_name == "long_running_tool":
        # 백그라운드 실행
        result = await run_in_background(tool_args)
    else:
        # 일반 도구
        result = tool.invoke(tool_args)
    ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
    messages = state["messages"]
    last_message = messages[-1]

    # 마지막 메시지가 AIMessage이고 tool_calls가 있는지 확인
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_messages = []
    updated_todos = state.get("todos")  # 현재 todos 상태

    # 각 tool_call 처리
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]  # OpenAI function calling ID

        try:
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 특수 처리: task_tool은 Subagent 실행!
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            if tool_name == "task_tool":
                system_prompt = get_system_prompt(state.get("working_dir"))
                current_depth = state.get("depth", 0)

                # execute_subagent는 완전히 독립적인 StateGraph를 생성하여 실행!
                result = await execute_subagent(
                    subagent_type=tool_args.get("subagent_type", "general-purpose"),
                    prompt=tool_args.get("prompt", ""),
                    system_prompt=system_prompt,
                    current_depth=current_depth,
                    max_depth=5,
                    model_name=tool_args.get("model", "claude-haiku-4-5"),
                )

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 특수 처리: todo_write는 state 업데이트!
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            elif tool_name == "todo_write":
                # todo_write 도구 실행 (검증 포함)
                tool = TOOLS_BY_NAME.get(tool_name)
                result = tool.invoke(tool_args)

                # state의 todos 업데이트
                updated_todos = tool_args.get("todos", [])

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 일반 도구: TOOLS_BY_NAME에서 찾아서 실행
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            else:
                tool = TOOLS_BY_NAME.get(tool_name)
                if not tool:
                    result = f"[ERROR] Unknown tool: {tool_name}"
                else:
                    # LangChain tool의 invoke 메서드 호출
                    result = tool.invoke(tool_args)

            # 성공: ToolMessage로 변환
            tool_messages.append(ToolMessage(content=str(result), tool_call_id=tool_call_id))

        except Exception as e:
            # 실패: 에러 메시지를 ToolMessage로 반환 (LLM이 에러 처리!)
            tool_messages.append(
                ToolMessage(content=f"[ERROR] {type(e).__name__}: {str(e)}", tool_call_id=tool_call_id)
            )

    # StateGraph가 자동으로 messages에 append하고 todos 업데이트
    result_dict = {"messages": tool_messages}
    if updated_todos is not None:
        result_dict["todos"] = updated_todos

    return result_dict


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# StateGraph 구성 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def create_graph(use_memory: bool = False):
    """
    🏗️ LangGraph StateGraph 생성 및 구성

    이 함수가 하는 일:
        1. StateGraph 생성 (AgentState 타입 지정)
        2. 노드 추가 (agent, tools)
        3. 엣지 추가 (노드 간 연결)
        4. 조건부 엣지 추가 (동적 라우팅)
        5. 컴파일 (실행 가능한 graph로 변환)

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    📝 StateGraph 구성 5단계:

    1️⃣ **StateGraph 생성**
       ```python
       builder = StateGraph(AgentState)
       ```
       - AgentState: 모든 노드가 공유하는 상태 타입 (types.py 참고)
       - TypedDict로 정의된 구조를 기반으로 자동 검증

    2️⃣ **노드 추가 (add_node)**
       ```python
       builder.add_node("agent", call_agent)
       builder.add_node("tools", execute_tools)
       ```
       - 노드 = 실행 가능한 함수 (AgentState → dict 반환)
       - 각 노드는 독립적으로 실행되며, 반환값이 state에 병합됨

    3️⃣ **기본 엣지 추가 (add_edge)**
       ```python
       builder.add_edge(START, "agent")      # 시작점 → agent
       builder.add_edge("tools", "agent")    # tools → agent (루프)
       ```
       - 단방향 연결 (항상 같은 다음 노드로 이동)
       - START: LangGraph 내장 시작 노드
       - END: LangGraph 내장 종료 노드

    4️⃣ **조건부 엣지 추가 (add_conditional_edges)**
       ```python
       builder.add_conditional_edges(
           "agent",              # 출발 노드
           should_continue,      # 판단 함수 (AgentState → str)
           {
               "tools": "tools", # 반환값이 "tools"면 tools 노드로
               END: END,         # 반환값이 END면 종료
           }
       )
       ```
       - 동적 라우팅: 함수 결과에 따라 다른 노드로 이동
       - should_continue(): "tools" 또는 END 반환

    5️⃣ **컴파일 (compile)**
       ```python
       graph = builder.compile(checkpointer=memory)
       ```
       - 실행 가능한 graph 객체로 변환
       - checkpointer: 상태 저장 (대화 이력 유지)

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    🔄 실행 흐름:

        START (초기 상태)
          ↓
        agent (call_agent 실행)
          │
          ├─ LLM 호출
          ├─ tool_calls 있음? → should_continue가 "tools" 반환
          └─ tool_calls 없음? → should_continue가 END 반환
          ↓
        [조건부 분기]
          ├─ "tools" → execute_tools 실행
          │              ↓
          │           agent로 돌아감 (루프!)
          │
          └─ END → 종료

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    Args:
        use_memory: True면 MemorySaver로 대화 이력 저장

    Returns:
        CompiledGraph: 실행 가능한 graph 객체
                      - graph.invoke(state) 또는
                      - graph.astream(state)로 실행

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    📌 확장 패턴: 새로운 노드/엣지 추가하기

    **예시 1: 코드 검증 노드 추가**

    ```python
    async def verify_code(state: AgentState) -> dict:
        '''테스트 실행 및 검증'''
        # 구현...
        return {"messages": [AIMessage(content="Tests passed!")]}

    # 그래프 구성
    builder.add_node("verify", verify_code)
    builder.add_edge("tools", "verify")  # tools 후 검증
    builder.add_conditional_edges(
        "verify",
        lambda state: "agent" if tests_failed(state) else END,
        {"agent": "agent", END: END}
    )
    ```

    **예시 2: 사용자 승인 노드 추가**

    ```python
    async def ask_approval(state: AgentState) -> dict:
        '''위험한 작업 전 사용자 승인 요청'''
        # 구현...
        return {"messages": [...]}

    builder.add_node("approval", ask_approval)
    builder.add_conditional_edges(
        "tools",
        lambda state: "approval" if is_dangerous(state) else "agent",
        {"approval": "approval", "agent": "agent"}
    )
    ```

    **예시 3: 다중 Subagent 병렬 실행**

    ```python
    async def parallel_research(state: AgentState) -> dict:
        '''여러 Subagent를 병렬로 실행'''
        tasks = [
            execute_subagent("Explore", "Search for API docs"),
            execute_subagent("Explore", "Find test files"),
        ]
        results = await asyncio.gather(*tasks)
        return {"messages": [...]}

    builder.add_node("parallel", parallel_research)
    ```

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    💡 MemorySaver (Checkpointer)란?

    LangGraph의 Checkpointer는 각 노드 실행 후 상태를 저장합니다.

    장점:
        ✅ 대화 이력 유지 (멀티턴 대화)
        ✅ 실패 시 복구 (중간 상태에서 재시작)
        ✅ 디버깅 용이 (각 단계별 상태 확인)

    사용법:
        ```python
        config = {"configurable": {"thread_id": "user123"}}
        graph.invoke(state, config=config)  # thread_id로 대화 이력 관리
        ```

    다른 Checkpointer:
        - MemorySaver: 메모리 (휘발성)
        - SqliteSaver: SQLite DB (영구 저장)
        - PostgresSaver: PostgreSQL (프로덕션용)

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1️⃣ StateGraph 생성
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    builder = StateGraph(AgentState)
    # AgentState: types.py에 정의된 TypedDict
    # - messages: 대화 메시지 목록 (add_messages reducer로 자동 append)
    # - working_dir: 현재 작업 디렉토리
    # - selected_tools: 사용 가능한 도구 목록
    # - depth: Subagent 중첩 깊이

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2️⃣ 노드 추가
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    builder.add_node("agent", call_agent)
    # call_agent: LLM을 호출하여 다음 액션 결정 (nodes.py 참고)
    #   - SystemMessage 추가 (첫 호출 시)
    #   - model_with_tools.invoke(messages)
    #   - AIMessage 반환 (tool_calls 포함 가능)

    builder.add_node("tools", execute_tools)
    # execute_tools: 도구 실행 (위에 정의된 함수)
    #   - task_tool이면 Subagent 실행
    #   - 일반 도구면 TOOLS_BY_NAME에서 찾아 실행
    #   - ToolMessage 반환

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3️⃣ 기본 엣지 추가 (단방향 연결)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    builder.add_edge(START, "agent")
    # START → agent: 그래프 시작 시 agent 노드로 이동

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4️⃣ 조건부 엣지 추가 (동적 라우팅)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    builder.add_conditional_edges(
        "agent",  # agent 노드 실행 후
        should_continue,  # should_continue 함수 호출 (nodes.py 참고)
        {
            "tools": "tools",  # "tools" 반환 → tools 노드로
            END: END,  # END 반환 → 종료
        },
    )
    # should_continue 로직:
    #   - 마지막 AIMessage에 tool_calls가 있으면 "tools"
    #   - 없으면 END

    builder.add_edge("tools", "agent")
    # tools → agent: 도구 실행 후 다시 agent로 돌아가 결과 처리
    # 이것이 Claude Code의 핵심 루프!
    #   agent (도구 선택) → tools (도구 실행) → agent (결과 해석) → ...

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 5️⃣ 컴파일 (실행 가능한 graph로 변환)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    if use_memory:
        memory = MemorySaver()  # 인메모리 checkpointer
        graph = builder.compile(checkpointer=memory)
        # checkpointer가 있으면 각 노드 실행 후 상태 저장
        # → 대화 이력 유지, 멀티턴 대화 가능
    else:
        graph = builder.compile()
        # checkpointer 없으면 단일 실행만 가능 (상태 저장 안 됨)

    return graph


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 기본 그래프 인스턴스
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 메모리 없는 기본 그래프 (단일 턴 실행용)
graph = create_graph(use_memory=False)

# 메모리 사용 그래프 (멀티턴 대화용)
graph_with_memory = create_graph(use_memory=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📌 사용 예시
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
# 단일 실행
initial_state = {
    "messages": [HumanMessage(content="Hello")],
    "working_dir": os.getcwd(),
    "depth": 0,
}
result = await graph.ainvoke(initial_state)

# 멀티턴 대화
config = {"configurable": {"thread_id": "user123"}}
result1 = await graph_with_memory.ainvoke(state1, config=config)
result2 = await graph_with_memory.ainvoke(state2, config=config)  # 이전 대화 이력 유지

# 스트리밍 실행
async for chunk in graph.astream(initial_state):
    print(chunk)
"""
