# Version 2: LangGraph를 활용한 구현 ✅

LangGraph의 상태 머신을 활용하여 Claude Code를 구현한 버전입니다.

## LangGraph란?

LangGraph는 LangChain 팀이 만든 **상태 머신 기반 agent 프레임워크**입니다.

### 핵심 개념

1. **State**: 대화의 현재 상태
   ```python
   class AgentState(TypedDict):
       messages: List[Message]
       depth: int
       todos: Optional[list[dict]]
   ```

2. **Graph**: 노드와 엣지로 구성된 플로우
   ```python
   graph = StateGraph(AgentState)
   graph.add_node("agent", call_agent)
   graph.add_node("tools", execute_tools)
   graph.add_conditional_edges("agent", should_continue)
   ```

3. **Checkpointer**: 대화 히스토리 자동 저장
   ```python
   checkpointer = MemorySaver()
   app = graph.compile(checkpointer=checkpointer)
   ```

## v1 vs v2 비교

| 특징 | v1 (OpenAI 직접) | v2 (LangGraph) |
|------|-----------------|----------------|
| 루프 관리 | 수동 while 루프 | 자동 graph 루프 |
| 분기 로직 | if-elif 체인 | conditional_edges |
| 히스토리 | 직접 관리 | Checkpointer 자동 |
| 시각화 | 없음 | Mermaid 다이어그램 |
| 학습 곡선 | 낮음 | 중간 |
| 확장성 | 높음 | 매우 높음 |

**v2의 핵심 장점**: 복잡한 multi-agent 플로우를 선언적으로 표현

## 구현 현황

**파일 구조**:
- **types.py** (158줄) - AgentState 정의
- **tools.py** (451줄) - 9개 도구 (read_file, write_file, edit_file, glob_files, grep_code, run_bash, todo_write, exit_plan_mode, task_tool)
- **nodes.py** (661줄) - call_agent, should_continue, execute_subagent
- **graph.py** (462줄) - StateGraph 구성 + 커스텀 도구 노드
- **main.py** (732줄) - 토큰 단위 스트리밍 UI

**총 코드**: ~2,473줄 (상세 주석 포함)

## ⭐ Subagent 시스템

v2는 **재귀적 StateGraph**를 통한 Subagent 실행을 완전히 지원합니다.

### 작동 원리

```python
# 1. task_tool로 Subagent 요청
@tool
def task_tool(subagent_type: str, prompt: str, model: str = "sonnet"):
    """Launch a specialized subagent"""

# 2. execute_subagent()가 독립적인 StateGraph 생성 및 실행
async def execute_subagent(...) -> str:
    builder = StateGraph(AgentState)
    builder.add_node("agent", subagent_call_agent)
    builder.add_node("tools", ToolNode(allowed_tools))
    subagent_graph = builder.compile()
    return await subagent_graph.ainvoke(initial_state)

# 3. 커스텀 도구 노드에서 task_tool 감지 및 처리
if tool_name == "task_tool":
    result = await execute_subagent(...)
```

### Subagent 타입

1. **general-purpose** - 복잡한 리서치, 코드 검색, 멀티스텝 실행
2. **Explore** - 코드베이스 탐색 (파일 찾기, 키워드 검색, 질문 답변)
3. **Plan** - 구현 계획 수립

**제한사항**:
- 모든 Subagent는 `task_tool`, `todo_write`, `exit_plan_mode` 사용 불가
- 최대 중첩 깊이: 5단계 (무한 재귀 방지)

### LangGraph의 Subagent 패턴

- 각 Subagent는 독립적인 StateGraph
- 도구 필터링으로 권한 제어
- 완전히 독립적인 실행 컨텍스트

## 사용법

```bash
uv run python -m custom_claude_code.v2_langgraph.main
```

## 언제 LangGraph를 사용할까?

✅ **추천**:
- 복잡한 multi-agent 워크플로우
- 조건부 분기가 많은 경우
- 대화 히스토리 관리가 중요할 때
- 플로우 시각화가 필요할 때

❌ **비추천**:
- 단순한 단일 agent 구현
- LangGraph 의존성을 피하고 싶을 때

## System Prompt 번역 규칙

이 프로젝트는 교육용으로 system prompt를 한국어로 번역합니다.

**규칙**:
- 섹션 제목, XML 태그, Examples 레이블 → 영어 유지
- 내용, 설명 → 한국어 번역
- 기술 용어 (read_file, subagent_type 등) → 영어 유지
- 강조 (VERY, NEVER, ALWAYS) → 한국어 볼드 (**매우**, **절대**, **항상**)

**예시**:
```
# Task Management (영어 유지)

todo_write 도구를 **매우** 자주 사용하세요. (내용 번역 + 강조 볼드)
```

## 참고 자료

- [LangGraph 공식 문서](https://langchain-ai.github.io/langgraph/)
- [LangGraph Tutorials](https://langchain-ai.github.io/langgraph/tutorials/)
