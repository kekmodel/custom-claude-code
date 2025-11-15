# 4가지 구현 - 동등 비교

## 핵심: 모두 동일한 기능

| 항목 | v1 | v2 | v3 | v4 |
|------|----|----|----|----|
| **모델** | Haiku 4.5 | Haiku 4.5 | Haiku 4.5 | Haiku 4.5 |
| **도구** | 6개 | 6개 | 6개 | 6개 |
| **한국어** | ✅ | ✅ | ✅ | ✅ |
| **비용 추적** | ✅ | ✅ | ✅ | ✅ |
| **대화형 UI** | ✅ | ✅ | ✅ | ✅ |

**차이점은 오직 구현 방식뿐!**

## 구현 방식 비교

### v1: OpenAI API 직접 사용
```python
# 수동 루프
while True:
    response = await client.chat.completions.create(model="claude-haiku-4-5", ...)
    # 도구 처리 직접 구현
    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = execute_tool(tool_call)
```

**장점:** 완전한 제어
**단점:** 코드량 많음 (~1,891줄)
**특징:** 모든 세부사항 확인 가능

### v2: LangGraph
```python
# StateGraph 자동 루프
graph = StateGraph(AgentState)
graph.add_node("agent", call_model)
graph.add_node("tools", execute_tools)
graph.stream(initial_state)
```

**장점:** 워크플로우 명확
**단점:** LangGraph 학습 필요
**특징:** 상태 관리 우수 (~450줄)

### v3: OpenAI Agents SDK
```python
# Agent.as_tool() 패턴
subagent = Agent(name="explore", functions=[...])
main_agent = Agent(
    functions=[tool1, tool2, subagent.as_tool()]
)
runner.run(main_agent, messages)
```

**장점:** 에이전트 체인 쉬움
**단점:** OpenAI SDK 전용
**특징:** 서브에이전트 간단 (~280줄)

### v4: Claude Agent SDK
```python
# 선언적 설정
options = ClaudeAgentOptions(
    model="haiku",
    agents=SUBAGENTS,
    system_prompt={"type": "preset", "preset": "claude_code"}
)
async with ClaudeSDKClient(options=options) as client:
    await client.query(text)
```

**장점:** 가장 간단
**단점:** Claude 전용
**특징:** 설정 기반 (~190줄)

## 서브에이전트 비교

### v1: 없음
- 모든 작업을 메인 루프에서 처리

### v2: SubGraph로 구현
```python
# 서브그래프 생성
explore_graph = StateGraph(...)
# 메인 그래프에 추가
main_graph.add_node("explore", explore_graph)
```

### v3: Agent.as_tool()
```python
explore_agent = Agent(name="explore", ...)
main_agent = Agent(
    functions=[explore_agent.as_tool()]
)
```

### v4: agents 파라미터
```python
SUBAGENTS = {
    "explore": AgentDefinition(...),
    "plan": AgentDefinition(...),
}
options = ClaudeAgentOptions(agents=SUBAGENTS)
```

## 코드 길이

- v1: ~1,891줄 (모든 것을 수동)
- v2: ~450줄 (그래프 자동화)
- v3: ~280줄 (SDK 활용)
- v4: ~190줄 (선언적)

**코드가 짧을수록 유지보수 쉬움!**

## 선택 가이드

**학습 목적:**
→ v1 (모든 동작 이해)

**복잡한 워크플로우:**
→ v2 (StateGraph 시각화)

**OpenAI 사용자:**
→ v3 (익숙한 패턴)

**빠른 프로토타입:**
→ v4 (가장 간단)

## 결론

**기능은 동등, 구현만 다름:**
- 같은 모델 (Haiku 4.5)
- 같은 도구 (6개)
- 같은 결과

**차이는 추상화 수준:**
- v1: 로우 레벨 (수동)
- v2: 미드 레벨 (그래프)
- v3: 하이 레벨 (SDK)
- v4: 최상위 레벨 (선언적)

더 추상화될수록 코드는 짧고, 유지보수는 쉬워집니다! 🎯
