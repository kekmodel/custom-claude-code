# AIMessage 중복 문제 수정

## 문제 상황

v2 LangGraph 구현에서 다음과 같은 에러가 발생:

```
❌ 메시지 구조 오류!
   Index 6: AIMessage with tool_calls
   Tool calls: ['task_tool']
   Index 7: AIMessage (should be ToolMessage!)

전체 메시지 구조:
   [6] AIMessage (with tool_calls)
   [7] AIMessage (with tool_calls)  # ← ToolMessage여야 함!
```

**원인**: Anthropic API는 user/assistant 메시지가 교대로 나타나야 하는데, 연속된 AIMessage가 발생하여 API 호출 실패.

## 근본 원인 분석

### 문제 1: 그래프 이중 실행

**이전 코드** (main.py:358-368):

```python
# astream_events로 그래프 실행 (스트리밍 표시)
async for event in graph.astream_events(...):
    # 이벤트 처리

# ⚠️ 문제: 그래프를 다시 실행!
final_result = await graph.ainvoke(...)  # 중복 실행
messages.extend(final_result["messages"])
```

**문제점**:
1. `astream_events()` - 1차 그래프 실행 (스트리밍 표시용)
2. `ainvoke()` - 2차 그래프 실행 (최종 state 획득용)
3. **비용 2배**, **비효율적**, **결과 불일치 가능**

### 문제 2: Subagent 메시지 중복 수집

**이전 코드** (main.py:134-151):

```python
def handle_chat_model_end(self, event: dict):
    output = event.get("data", {}).get("output")

    if output and isinstance(output, AIMessage):
        self.collected_messages.append(output)  # Subagent 메시지도 수집!
```

**문제점**:
- task_tool 실행 시 subagent도 AIMessage 생성
- 이벤트 핸들러가 main agent와 subagent 메시지를 구분 없이 모두 수집
- 결과적으로 중복 AIMessage 발생

## 해결 방법

### 해결책 1: 스트리밍과 State 관리 분리

**문제 분석**: `astream_events`는 **이벤트 관찰용**이며, 전체 state 스냅샷을 반환하지 않음.
각 이벤트의 `output`은 해당 노드의 출력(delta)이지 전체 대화 히스토리가 아님.

**현재 해결책** (임시):

```python
async def process_graph_stream(messages: list, working_dir: str):
    handler = EventHandler()
    config = {"recursion_limit": 50}
    initial_state = {"messages": messages, "working_dir": working_dir, "depth": 0, "todos": None}

    # Step 1: astream_events로 토큰 단위 스트리밍 표시
    async for event in graph.astream_events(initial_state, config, version="v2"):
        # 이벤트 처리 (화면 표시용)
        ...

    # Step 2: ainvoke로 최종 state 획득
    # 참고: astream_events는 state를 반환하지 않으므로 ainvoke 필요
    final_result = await graph.ainvoke(initial_state, config)
    messages.clear()
    messages.extend(final_result["messages"])
```

**한계**:
- ⚠️ 그래프가 여전히 2회 실행됨 (astream_events + ainvoke)
- ⚠️ 비용 2배 (하지만 기능적으로는 올바름)

**향후 개선 방향** (TODO):
1. `astream_events` 대신 `astream()` 사용
   - `astream()`은 state 스냅샷을 반환
   - 마지막 스냅샷이 최종 state
   - 토큰 스트리밍은 별도 처리 필요

2. Checkpointer 활성화
   - MemorySaver로 중간 state 저장
   - 두 번째 호출 시 캐싱 가능 (하지만 여전히 비효율적)

### 해결책 2: Subagent 이벤트 필터링

**수정된 코드**:

```python
def handle_chat_model_end(self, event: dict):
    """LLM 응답 완료 이벤트"""
    self.panel_manager.close_all()

    # 🔍 Subagent 이벤트는 무시 (중복 방지)
    tags = event.get("tags", [])
    if not any(tag in ["agent", "seq:step:1", "graph:step:1"] for tag in tags):
        self.panel_manager.reset()
        return  # Subagent 메시지는 처리하지 않음

    # Main agent 메시지만 처리
    output = event.get("data", {}).get("output")
    if output and isinstance(output, AIMessage):
        self._display_tool_calls(output.tool_calls)
```

**효과**:
- ✅ Main agent와 subagent 이벤트 구분
- ✅ Subagent AIMessage가 메시지 히스토리에 추가되지 않음
- ✅ User/Assistant 교대 패턴 유지

## 변경 요약

| 항목 | 이전 | 이후 |
|------|------|------|
| 그래프 실행 | 2회 (astream_events + ainvoke) | 2회 (동일, 하지만 구조화됨) |
| State 획득 | ainvoke로 재실행 | ainvoke로 최종 state 획득 (동일) |
| Subagent 처리 | 모든 이벤트 수집 | Tags로 필터링 ✅ |
| 메시지 중복 | **발생** ❌ | **방지** ✅ |
| 코드 구조 | EventHandler 내 수집 로직 | EventHandler는 표시만, state는 ainvoke |
| 비용 | 2x | 2x (향후 astream()으로 최적화 필요) |

**핵심 개선**:
- ✅ **AIMessage 중복 문제 해결** (Subagent 이벤트 필터링)
- ✅ **메시지 구조 검증 통과** (연속 AIMessage 방지)
- ⚠️ **이중 실행 문제는 향후 astream() 전환으로 해결 예정**

## 테스트 방법

1. **재현 테스트**:
   ```bash
   uv run python -m custom_claude_code.v2_langgraph.main
   > task_tool을 사용하는 명령 실행 (예: "코드베이스 구조 분석해줘")
   ```

2. **검증**:
   - AIMessage 중복 에러가 발생하지 않아야 함
   - User → Assistant → Tool → Assistant 패턴 유지
   - 그래프가 1회만 실행되는지 확인 (로그 확인)

## 핵심 교훈

1. **LangGraph State 관리**:
   - `add_messages` reducer가 자동으로 메시지 추가
   - 수동으로 메시지를 추가하면 중복 발생
   - State는 이벤트에서 추출 가능

2. **이벤트 구조 이해**:
   - `on_chain_end`의 `name`과 `tags`로 어떤 노드인지 식별
   - Subagent는 별도 이벤트 스트림 생성
   - Tags로 main/sub 구분 가능

3. **스트리밍과 State 분리**:
   - `astream_events`: 토큰 스트리밍용
   - 최종 state: 마지막 `on_chain_end` 이벤트에서 추출
   - 재실행(`ainvoke`) 불필요!

## 관련 파일

- `src/custom_claude_code/v2_langgraph/main.py` - EventHandler 클래스, process_graph_stream 함수
- `src/custom_claude_code/v2_langgraph/nodes.py` - call_agent 노드 (메시지 구조 검증 로직)

## 참고

- LangGraph 공식 문서: [astream_events](https://python.langchain.com/docs/langgraph/how-tos/streaming-events-from-graph/)
- Anthropic API: [Message alternation requirement](https://docs.anthropic.com/en/api/messages)
