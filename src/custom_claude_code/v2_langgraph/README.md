# Version 2: LangGraph를 활용한 구현 ✅ **COMPLETE**

LangGraph의 상태 머신을 활용하여 Claude Code를 구현한 버전입니다.

## LangGraph란?

LangGraph는 LangChain 팀이 만든 **상태 머신 기반 agent 프레임워크**입니다.

### 핵심 개념

1. **State**: 대화의 현재 상태
   ```python
   class AgentState(TypedDict):
       messages: List[Message]
       current_tool: Optional[str]
   ```

2. **Graph**: 노드와 엣지로 구성된 플로우
   ```python
   graph = StateGraph(AgentState)
   graph.add_node("llm", call_llm)
   graph.add_node("tools", execute_tools)
   graph.add_edge("llm", "tools")
   graph.add_conditional_edges("tools", should_continue)
   ```

3. **Checkpointer**: 대화 히스토리 자동 저장
   ```python
   checkpointer = MemorySaver()
   app = graph.compile(checkpointer=checkpointer)
   ```

## v1 (OpenAI 직접)과의 차이점

### v1: 수동 루프

```python
while True:
    response = openai.chat.completions.create(...)

    if finish_reason == "stop":
        break
    elif finish_reason == "tool_calls":
        results = execute_tools(...)
        messages.extend(results)
        continue  # 수동으로 루프
```

### v2: LangGraph 자동 루프

```python
graph = StateGraph(AgentState)
graph.add_node("llm", call_llm)
graph.add_node("tools", execute_tools)
graph.add_conditional_edges(
    "tools",
    lambda state: "llm" if has_tool_calls(state) else END
)

# 그래프가 알아서 루프!
app = graph.compile()
result = app.invoke({"messages": [user_message]})
```

**장점**:
- 루프 로직을 그래프가 자동 처리
- 조건부 분기가 명확 (conditional_edges)
- Checkpointer로 히스토리 자동 관리
- 시각화 가능 (graph.get_graph().draw_mermaid())

**단점**:
- 추가 추상화 레이어 (학습 곡선)
- LangGraph 의존성

## 구현 현황

- ✅ **types.py** - AgentState 정의 (MessagesState 패턴)
- ✅ **tools.py** - 7개 도구 (6개 핵심 + **task_tool**)
- ✅ **nodes.py** - call_agent, should_continue, **execute_subagent**
- ✅ **graph.py** - StateGraph 구성 + **커스텀 도구 노드 (Subagent 지원!)**
- ✅ **main.py** - graph.stream() 실행 루프
- ✅ **README.md** - 완전한 문서

**총 코드**: ~866줄 (Subagent 지원 포함!)

## ⭐ Subagent 시스템 (Claude Code의 핵심!)

v2는 **Task tool + Subagent 실행**을 완전히 지원합니다!

### 작동 원리

1. **task_tool** - LLM이 복잡한 작업을 Subagent에 위임
   ```python
   @tool
   def task_tool(subagent_type: str, description: str, prompt: str, model: str = "sonnet") -> str:
       """Launch a subagent to handle complex tasks."""
   ```

2. **execute_subagent()** - 독립적인 StateGraph로 Subagent 실행
   ```python
   async def execute_subagent(
       subagent_type: str,
       prompt: str,
       system_prompt: str,
       current_depth: int = 0,
       max_depth: int = 5,
       model_name: str = "claude-haiku-4-5"
   ) -> str:
       # 새로운 StateGraph 생성!
       builder = StateGraph(AgentState)
       builder.add_node("agent", subagent_call_agent)
       builder.add_node("tools", ToolNode(allowed_tools))
       # ... 엣지 구성 ...

       subagent_graph = builder.compile()
       final_state = await subagent_graph.ainvoke(initial_state)
       return final_state["messages"][-1].content
   ```

3. **커스텀 도구 노드** - task_tool을 감지하고 execute_subagent() 호출
   ```python
   async def execute_tools(state: AgentState) -> dict:
       for tool_call in last_message.tool_calls:
           if tool_call["name"] == "task_tool":
               # Subagent 실행!
               result = await execute_subagent(...)
           else:
               # 일반 도구 실행
               result = tool.invoke(tool_args)
   ```

### Subagent 타입

- **general-purpose** - 모든 도구 접근, 복잡한 작업 처리
- **Explore** - 코드베이스 탐색 (glob, grep, read)
- **Plan** - 계획 수립 (탐색 + 분석)
- **statusline-setup** - 설정 파일 편집 (read, edit만 허용)

### 중첩 제한

- **max_depth=5** - 최대 5단계 중첩까지 허용
- 무한 재귀 방지

### LangGraph의 Subagent 패턴

LangGraph에서 Subagent는 **독립적인 StateGraph**로 구현됩니다:
- 각 Subagent가 자체 StateGraph를 가짐
- 도구 필터링으로 권한 제어
- 완전히 독립적인 실행 컨텍스트

## 파일 구조

```
v2_langgraph/
├── types.py         # AgentState 타입 정의
├── tools.py         # 6개 도구 (@tool 데코레이터)
├── nodes.py         # Agent 노드 + 조건부 엣지
├── graph.py         # StateGraph 구성
├── main.py          # 메인 실행 루프
└── README.md        # 이 문서
```

## 사용법

```bash
cd /Users/jd/Documents/workspace/custom-claude-code
uv run python -m custom_claude_code.v2_langgraph.main
```

## LangGraph의 장점

1. **상태 관리 자동화**: messages, 도구 결과 등을 state로 관리
2. **분기 로직 명확화**: conditional_edges로 "도구 사용" vs "완료" 분기
3. **히스토리 관리**: Checkpointer로 대화 자동 저장/복원
4. **시각화**: 그래프 구조를 Mermaid로 시각화 가능
5. **확장성**: 복잡한 multi-agent 플로우도 그래프로 표현

## 언제 사용하나?

- **복잡한 Agent 플로우**: 여러 Agent 간 handoff, 조건부 분기
- **상태 관리가 중요할 때**: 대화 히스토리, 컨텍스트 유지
- **시각화가 필요할 때**: 플로우를 그래프로 보고 싶을 때
- **LangChain 생태계 활용**: LangChain의 다른 기능과 통합

## v1 vs v2 비교

| 특징 | v1: OpenAI 직접 | v2: LangGraph |
|------|-----------------|---------------|
| 루프 관리 | 수동 (while) | 자동 (graph) |
| 분기 로직 | if-elif | conditional_edges |
| 히스토리 | 직접 관리 | Checkpointer |
| 시각화 | 없음 | Mermaid |
| 복잡도 | 단순 | 중간 |
| 학습 곡선 | 낮음 | 중간 |
| 유연성 | 높음 | 높음 |

## 참고 자료

- [LangGraph 공식 문서](https://langchain-ai.github.io/langgraph/)
- [LangGraph Tutorials](https://langchain-ai.github.io/langgraph/tutorials/)
