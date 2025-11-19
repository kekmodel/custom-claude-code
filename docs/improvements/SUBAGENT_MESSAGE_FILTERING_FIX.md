# Subagent 메시지 필터링 수정 (v2.1)

## 문제 상황

### 오류 메시지
```
Error code: 400 - messages.3: `tool_use` ids were found without `tool_result` blocks immediately after:
toolu_0156uYBmJUt91rJrdG2RzoPQ. Each `tool_use` block must have a corresponding `tool_result` block in the next message.
```

### 발생 시나리오
1. Main agent가 `task_tool`을 호출하여 subagent 실행
2. Subagent가 자체 tool calls 수행 (예: Explore agent가 `glob_files` 호출)
3. Subagent의 **AIMessage(tool_calls)**가 main graph의 messages에 섞임
4. API 요청 시 tool_use without tool_result 오류 발생

### 근본 원인

**astream_events의 이벤트 전파**:
- `graph.astream_events()`는 **모든 nested graph의 이벤트**를 캡처
- Subagent의 `RunnableConfig(callbacks=[])`는 callback 전파만 막음
- `astream_events`는 callback과 무관하게 모든 이벤트를 볼 수 있음

**EventHandler의 무분별한 수집**:
```python
# v2.1 초기 구현 (문제)
def handle_chat_model_end(self, event: dict):
    output = data.get("output")
    if output and isinstance(output, AIMessage):
        self.messages.append(output)  # Subagent AIMessage도 추가됨!
```

---

## 해결 방법

### 1. Tag 기반 필터링

LangGraph의 이벤트에는 `tags` 필드가 포함되며, main graph와 subagent를 구분할 수 있습니다:

```python
# Main graph 이벤트: ["agent", "seq:step:1", "graph:step:1", ...]
# Subagent 이벤트: ["seq:step:2", "graph:step:2", ...]  (agent 태그 없음)

tags = event.get("tags", [])
if not any(tag in ["agent", "seq:step:1", "graph:step:1"] for tag in tags):
    return  # Subagent 이벤트 무시
```

### 2. Depth 추적

`task_tool` 호출/완료를 추적하여 subagent 실행 여부를 판단:

```python
# EventHandler.__init__
self.task_tool_depth = 0  # 0: main graph, >0: subagent 내부

# handle_chat_model_end (task_tool 호출 시)
if tc.get('name') == 'task_tool':
    self.task_tool_depth += 1  # Subagent 진입

# handle_chain_end (task_tool 완료 시)
if tool_name == 'task_tool':
    if self.task_tool_depth > 0:
        self.task_tool_depth -= 1  # Subagent 종료
```

### 3. 이중 필터링 적용

**Tag 필터링** + **Depth 필터링**을 모두 적용:

```python
def handle_chat_model_end(self, event: dict):
    # 1차 필터: Tag 검사
    tags = event.get("tags", [])
    if not any(tag in ["agent", "seq:step:1", "graph:step:1"] for tag in tags):
        return

    # 2차 필터: Depth 검사
    if self.task_tool_depth > 0:
        return  # Subagent 내부 메시지 무시

    # Main graph AIMessage만 추가
    if output and isinstance(output, AIMessage):
        self.messages.append(output)
```

---

## 수정된 코드

### main.py EventHandler (v2.1)

```python
class EventHandler:
    """
    LangGraph astream_events 이벤트 처리

    Subagent 필터링: tag 검사 + depth 추적으로 중복 AIMessage 방지
    """

    def __init__(self, initial_messages: list):
        self.panel_manager = LivePanelManager()
        self.messages = list(initial_messages)
        self.todos = None
        self.active_subagent = None
        self.task_tool_depth = 0  # ← NEW: Depth 추적

    def handle_chat_model_stream(self, event: dict):
        """LLM 스트리밍 이벤트"""
        # ← NEW: Tag 필터링
        tags = event.get("tags", [])
        if not any(tag in ["agent", "seq:step:1", "graph:step:1"] for tag in tags):
            return

        # ... 스트리밍 처리

    def handle_chat_model_end(self, event: dict):
        """LLM 응답 완료 이벤트"""
        self.panel_manager.close_all()

        # ← NEW: Tag 필터링
        tags = event.get("tags", [])
        if not any(tag in ["agent", "seq:step:1", "graph:step:1"] for tag in tags):
            self.panel_manager.reset()
            return

        data = event.get("data", {})
        output = data.get("output")

        if output and isinstance(output, AIMessage):
            # ← NEW: Depth 필터링
            if self.task_tool_depth > 0:
                self.panel_manager.reset()
                return

            self.messages.append(output)
            self._display_tool_calls(output.tool_calls)

            # ← NEW: Depth 증가
            if output.tool_calls:
                for tc in output.tool_calls:
                    if tc.get('name') == 'task_tool':
                        self.task_tool_depth += 1
                        # ... spinner 표시

        self.panel_manager.reset()

    def handle_chain_end(self, event: dict):
        """노드 완료 이벤트"""
        # ...
        if ("tools" in tags or name == "tools") and output:
            if "messages" in output:
                for msg in output["messages"]:
                    if isinstance(msg, ToolMessage):
                        tool_name = getattr(msg, 'name', 'unknown')

                        # ← NEW: Depth 필터링
                        if self.task_tool_depth == 0:
                            self.messages.append(msg)
                            self._display_tool_result(msg)

                        # ← NEW: Depth 감소
                        if tool_name == 'task_tool':
                            if self.task_tool_depth > 0:
                                self.task_tool_depth -= 1
                            self.active_subagent = None
```

---

## 검증

### 테스트 케이스

**test_subagent_message_fix.py**:
```python
# 시나리오: Main agent → task_tool(Explore) → Explore가 glob_files 사용

initial_state = {
    "messages": [HumanMessage(content="Use Explore agent to find test files")],
    ...
}

final_state = await graph.ainvoke(initial_state, config=config)
messages = final_state["messages"]

# 예상 메시지 구조:
# [0] HumanMessage
# [1] AIMessage (task_tool 호출)
# [2] ToolMessage (task_tool 결과)
# [3] AIMessage (최종 응답)

# Subagent의 AIMessage(glob_files 호출)는 messages에 없어야 함!
```

### 실행 결과
```
✅ 테스트 통과: 모든 tool_calls에 대한 결과가 존재합니다!
   Subagent 필터링이 올바르게 작동합니다.
```

---

## 메시지 구조 비교

### Before (문제 발생)

```
messages = [
    HumanMessage("Use Explore to find files"),
    AIMessage(tool_calls=[task_tool]),      # Main
    AIMessage(tool_calls=[glob_files]),     # ← Subagent 메시지 (잘못 추가됨!)
    ToolMessage(glob_files 결과),           # Subagent 내부 결과
    ToolMessage(task_tool 결과),            # Main
    AIMessage("Here are the files..."),     # Main
]
```

**문제**: messages[2]의 `tool_calls=[glob_files]`에 대한 결과가 API 관점에서 보이지 않음
→ `tool_use without tool_result` 오류

### After (수정 후)

```
messages = [
    HumanMessage("Use Explore to find files"),
    AIMessage(tool_calls=[task_tool]),      # Main
    ToolMessage(task_tool 결과),            # Main (Subagent의 최종 응답)
    AIMessage("Here are the files..."),     # Main
]
```

**해결**: Subagent 내부 메시지는 완전히 필터링됨
→ 메시지 구조가 깨끗하고 Anthropic API 요구사항 충족

---

## 학습 포인트

### 1. astream_events의 동작 방식

- **전역 이벤트 스트림**: 모든 nested graph 이벤트를 캡처
- **callbacks=[]의 한계**: Callback 전파만 막음, 이벤트 가시성은 유지
- **필터링 필수**: Tag/Depth 기반 명시적 필터링 필요

### 2. LangGraph 이벤트 태그

```python
# Main graph 실행
event["tags"] = ["agent", "seq:step:1", "graph:step:1", ...]

# Nested graph (subagent) 실행
event["tags"] = ["seq:step:2", "graph:step:2", ...]  # "agent" 없음!
```

**활용**: `"agent" in tags` 또는 `"seq:step:1" in tags`로 main graph 식별

### 3. 상태 추적의 중요성

- **Depth 추적**: Task nesting level 파악
- **Tag 필터링**: 이벤트 소스 식별
- **이중 검증**: Tag + Depth 모두 확인하여 안정성 보장

---

## v2와의 차이점

### v2 구현

- Tag 필터링 + Depth 추적을 이미 구현
- DEBUG 코드로 상세한 로깅 제공
- `task_tool_depth` 추적 포함

### v2.1 초기 구현

- **단순화 과정에서 필터링 로직 제거**
- 주석에 "callbacks=[] 덕분에 자동 필터링"이라고 잘못 기재
- 실제로는 필터링이 작동하지 않음 → 오류 발생

### v2.1 수정 후

- v2의 필터링 로직 복원
- DEBUG 코드는 제거한 채로 핵심 로직만 유지
- 간결하면서도 안정적인 구현

---

## 참고 문서

- **LangGraph Event Streaming**: https://python.langchain.com/docs/langgraph/how-tos/stream-events
- **Anthropic Messages API**: https://docs.anthropic.com/claude/reference/messages_post
- **v2 구현**: `src/custom_claude_code/v2_langgraph/main.py:258-279`

---

## 요약

**문제**: Subagent의 AIMessage가 main graph messages에 섞여서 API 오류 발생

**원인**: `astream_events`가 모든 nested 이벤트를 캡처, EventHandler가 무분별하게 수집

**해결**:
1. Tag 필터링으로 main graph 이벤트 식별
2. Depth 추적으로 subagent 실행 여부 판단
3. 이중 검증으로 안정성 보장

**결과**: 깨끗한 메시지 구조 + Anthropic API 요구사항 충족 ✅
