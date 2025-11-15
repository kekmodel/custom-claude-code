# Version 3: OpenAI Agents SDK를 활용한 구현 ✅ **COMPLETE**

OpenAI Agents SDK의 고수준 추상화를 활용하여 Claude Code를 구현한 버전입니다.

## OpenAI Agents SDK란?

2025년 3월 OpenAI가 공개한 **production-ready agent 프레임워크**입니다.
이전의 실험적 프로젝트 Swarm을 프로덕션 수준으로 업그레이드한 버전입니다.

### 핵심 개념

1. **Agent**: LLM + instructions + tools
   ```python
   agent = Agent(
       name="coding_assistant",
       instructions="You are an AI coding assistant",
       tools=[read_file, write_file, edit_file, run_bash]
   )
   ```

2. **Handoffs**: Agent 간 작업 위임
   ```python
   explore_agent = Agent(name="explorer", tools=[glob, grep])
   main_agent = Agent(
       name="main",
       tools=[read, write, Handoff(target=explore_agent)]
   )
   ```

3. **Sessions**: 대화 히스토리 자동 관리
   ```python
   with Session() as session:
       response = session.run(agent, "Fix the bug")
       # 히스토리 자동 저장!
   ```

4. **Guardrails**: 입출력 검증
   ```python
   agent = Agent(
       tools=[...],
       guardrails=[validate_paths, block_dangerous_commands]
   )
   ```

## v1, v2와의 차이점

### v1: 수동 구현

```python
while True:
    response = openai.chat.completions.create(...)
    if finish_reason == "tool_calls":
        # 도구 실행 로직 직접 구현
        results = []
        for tool_call in response.tool_calls:
            result = execute_tool(tool_call.name, tool_call.args)
            results.append(result)
```

### v2: LangGraph 상태 머신

```python
graph = StateGraph(...)
graph.add_node("llm", call_llm)
graph.add_node("tools", execute_tools)
# 그래프로 플로우 정의
```

### v3: OpenAI Agents SDK (최고 수준 추상화)

```python
agent = Agent(
    name="assistant",
    instructions="...",
    tools=[read_file, write_file, edit_file, bash]
)

# 단 3줄로 완료!
with Session() as session:
    for chunk in session.run_stream(agent, user_input):
        print(chunk)
```

**장점**:
- 가장 간결한 코드
- 도구 실행 로직 완전 자동화
- Pydantic 기반 도구 검증
- 내장 tracing (Logfire, AgentOps 등)
- Streaming 기본 지원

**단점**:
- OpenAI Agents SDK에 강하게 결합
- 커스터마이징 제한적 (SDK 내부 로직 변경 어려움)
- 2025년 3월 출시로 아직 안정화 단계

## 구현 현황

- ✅ **tools.py** - 6개 핵심 도구 (@function_tool 데코레이터)
- ✅ **main.py** - Agent + Runner.run() + **4개 Subagent (Agent.as_tool()!)**
- ✅ **SQLiteSession** - 자동 히스토리 관리
- ✅ **README.md** - 완전한 문서

**총 코드**: ~280줄 (Subagent 지원 포함!)

## ⭐ Subagent 시스템 (Claude Code의 핵심!)

v3는 **Agent.as_tool()** 패턴으로 Subagent를 구현합니다!

### OpenAI Agents SDK의 Subagent 패턴

OpenAI Agents SDK는 **Agent를 도구로 변환**하는 기능을 제공합니다:

```python
# 1. Subagent 정의
explore_agent = Agent(
    name="Explore Agent",
    instructions="You are a specialized agent for exploring codebases...",
    tools=[glob_files, grep_code, read_file],
)

# 2. Agent를 도구로 변환!
explore_tool = explore_agent.as_tool(
    tool_name="task_explore",
    description="Launch an Explore agent to search and analyze the codebase..."
)

# 3. Main Agent에 추가
main_agent = Agent(
    name="Coding Assistant",
    instructions="...",
    tools=TOOLS + [explore_tool, plan_tool, general_purpose_tool, statusline_setup_tool],
)
```

### 4개 Subagent

1. **Explore Agent** (`task_explore`)
   - 코드베이스 탐색 전문
   - 도구: `glob_files`, `grep_code`, `read_file`
   - 용도: 파일 찾기, 코드 검색, 구조 분석

2. **Plan Agent** (`task_plan`)
   - 계획 수립 전문
   - 도구: `glob_files`, `grep_code`, `read_file`
   - 용도: 작업 분해, 구현 방법 제안

3. **General Purpose Agent** (`task_general`)
   - 일반 작업 처리
   - 도구: 모든 도구
   - 용도: 복잡한 다단계 작업 자율 실행

4. **Statusline Setup Agent** (`task_statusline_setup`)
   - 설정 파일 편집 전문
   - 도구: `read_file`, `edit_file`만
   - 용도: Claude Code 상태 표시줄 설정

### v2 (LangGraph) vs v3 (OpenAI Agents SDK) Subagent 비교

| 특징 | v2: LangGraph | v3: OpenAI Agents SDK |
|------|---------------|----------------------|
| 구현 방법 | 독립 StateGraph 생성 | Agent.as_tool() |
| 코드 복잡도 | 중간 (execute_subagent 함수) | 낮음 (한 줄로 변환!) |
| 도구 필터링 | 수동 (if 문으로 분기) | 자동 (Agent 정의 시 설정) |
| 중첩 제한 | 수동 (max_depth 체크) | SDK가 자동 관리 |
| 가독성 | 명시적 | 매우 직관적 |

### Agent.as_tool()의 장점

- **극도로 간결**: 한 줄로 Agent를 도구로 변환
- **자동 실행**: SDK가 Subagent 생애주기 자동 관리
- **타입 안전**: Pydantic 기반 자동 검증
- **네이티브 지원**: OpenAI의 공식 패턴

## 파일 구조

```
v3_openai_agents/
├── tools.py         # 6개 도구 (@function_tool)
├── main.py          # Agent + Runner (한 줄로 실행!)
└── README.md        # 이 문서
```

## 사용법

```bash
cd /Users/jd/Documents/workspace/custom-claude-code
uv run python -m custom_claude_code.v3_openai_agents.main
```

## OpenAI Agents SDK의 특징

### 1. Function Tools with Pydantic

```python
from pydantic import BaseModel

class ReadFileInput(BaseModel):
    file_path: str
    offset: int | None = None
    limit: int | None = None

@agent.tool
def read_file(input: ReadFileInput) -> str:
    # Pydantic이 자동 검증!
    with open(input.file_path) as f:
        return f.read()
```

### 2. Built-in Tracing

```python
import logfire

# Logfire로 자동 트레이싱
agent = Agent(
    name="assistant",
    tools=[...],
    logfire=True  # 자동으로 로그 전송!
)
```

### 3. Guardrails

```python
def validate_file_paths(state):
    """파일 경로 검증"""
    for message in state.messages:
        if hasattr(message, 'tool_calls'):
            for tc in message.tool_calls:
                if tc.name in ["Read", "Write", "Edit"]:
                    path = tc.args.get('file_path')
                    if not os.path.isabs(path):
                        raise ValueError("Must use absolute path")

agent = Agent(
    tools=[...],
    guardrails=[validate_file_paths]  # 자동 검증!
)
```

## 언제 사용하나?

- **빠른 프로토타이핑**: 최소 코드로 agent 구축
- **OpenAI 생태계 활용**: OpenAI 모델과 완벽 통합
- **Tracing 필요**: Logfire, AgentOps 등 내장 지원
- **프로덕션 배포**: OpenAI의 공식 프레임워크

## v1 vs v2 vs v3 비교

| 특징 | v1: OpenAI 직접 | v2: LangGraph | v3: OpenAI Agents |
|------|-----------------|---------------|-------------------|
| 코드 길이 | 중간 | 중간 | 짧음 |
| 추상화 수준 | 낮음 | 중간 | 높음 |
| 커스터마이징 | 완전 자유 | 높음 | 제한적 |
| 학습 곡선 | 낮음 | 중간 | 낮음 |
| Tracing | 수동 구현 | 수동 구현 | 내장 |
| Pydantic 검증 | 수동 | 수동 | 자동 |
| 의존성 | openai | langgraph | openai-agents |

## 참고 자료

- [OpenAI Agents SDK 공식 문서](https://openai.github.io/openai-agents-python/)
- [GitHub Repository](https://github.com/openai/openai-agents-python)
- [Tutorial: Building AI Systems That Take Action](https://www.datacamp.com/tutorial/openai-agents-sdk-tutorial)
