# Custom Claude Code - 완전 가이드

> Claude Code의 내부 동작을 완전히 이해하고 커스텀 구현을 위한 기술 문서

---

## 📋 목차

- [개요](#개요)
- [프로젝트 구조](#프로젝트-구조)
- [핵심 개념](#핵심-개념)
- [빠른 시작](#빠른-시작)
- [문서 가이드](#문서-가이드)

---

## 개요

이 프로젝트는 **Claude Code의 내부 동작 원리**를 완전히 분석하고 문서화한 것입니다.

### 🎯 목적

1. **Claude Code 이해**: 50,000+ 토큰 시스템 프롬프트, 16개 도구, 멀티 에이전트 구조 완전 분석
2. **커스텀 구현**: 자체 AI 코딩 어시스턴트 구축을 위한 레퍼런스
3. **아키텍처 학습**: DAG 기반 워크플로우, 프롬프트 캐싱, 도구 중심 설계 패턴

### 📊 분석 범위

- ✅ 전체 시스템 프롬프트 구조 (50,000+ 토큰)
- ✅ 16개 도구의 스키마와 사용 패턴
- ✅ 4개 Subagent의 발동 조건과 동작 방식
- ✅ 단순/복잡/멀티에이전트 인터랙션 플로우
- ✅ 검증 및 에러 복구 메커니즘
- ✅ 사용자 피드백 루프와 목표 확장 패턴
- ✅ DAG 구조와 조건부 재시도 설계

### 🔬 분석 방법

1. **Claude Code Router 활용**: localhost:3456에서 실제 요청 가로채기
2. **실제 데이터 캡처**: System prompt, Tools, Messages 완전 저장
3. **시뮬레이션 생성**: 3가지 복잡도의 실제 인터랙션 시뮬레이션
4. **패턴 추출**: 반복되는 워크플로우와 설계 패턴 문서화

---

## 프로젝트 구조

```
custom-claude-code/
├── README.md                    # 메인 문서
├── CLAUDE.md                    # AI 개발 지침
├── QUICKSTART.md                # 빠른 시작 가이드
├── launcher.py                  # 대화형 런처 (권장) ⭐
│
├── src/custom_claude_code/      # 소스 코드
│   ├── v1_openai/              # v1: OpenAI API 직접 (~1,966줄)
│   ├── v2_langgraph/           # v2: LangGraph (~866줄)
│   ├── v3_openai_agents/       # v3: OpenAI Agents SDK (~515줄)
│   └── v4_claude_agent/        # v4: Claude Agent SDK (~311줄)
│
├── docs/                        # 아키텍처 및 분석 문서
│   ├── 01-architecture/         # 시스템 아키텍처
│   │   ├── system-overview.md
│   │   ├── graph-structure.md
│   │   └── data-flow.md
│   ├── 02-components/           # 컴포넌트 상세
│   │   ├── system-prompt.md
│   │   ├── tools.md
│   │   ├── agents.md
│   │   └── verification.md
│   ├── 03-interactions/         # 상호작용 패턴
│   │   ├── basic-flow.md
│   │   ├── multi-agent.md
│   │   ├── user-feedback.md
│   │   └── error-recovery.md
│   ├── 04-implementation/       # 구현 가이드
│   │   ├── getting-started.md
│   │   ├── custom-agents.md
│   │   └── best-practices.md
│   ├── EQUAL_COMPARISON.md      # 4가지 버전 비교
│   └── INTERACTIVE_EXAMPLES.md  # 실전 사용 예시
│
├── demos/                       # 자동 데모 스크립트
│   ├── v1_automated.py
│   ├── v1_and_v3_conversation.py
│   └── v4_api_test.py
│
├── tests/                       # 테스트 스위트
│   ├── test_version_imports.py
│   ├── test_v1_api_client.py
│   ├── test_v1_conversation.py
│   └── test_quality.py
│
├── quick_start/                 # 빠른 시작 스크립트
│   └── simple_v1.py
│
├── examples/                    # 시뮬레이션 예시
│   ├── interaction-simulations/
│   │   ├── 1-simple-file-read.json
│   │   ├── 2-multi-tool-loop.json
│   │   └── 3-multi-agent-task.json
│   └── EXAMPLE_PROMPTS.txt
│
├── references/                  # 실제 캡처 데이터
│   └── captured-data/
│       ├── request-*.json
│       ├── system-prompt-*.txt
│       ├── tools-*.json
│       └── messages-*.json
│
└── data/                        # 데이터베이스 (gitignore)
    └── v3_conversations.db
```

---

## 핵심 개념

### 1. 시스템 프롬프트 (50,000+ 토큰)

```
Block 1: 정체성 및 기본 지침 (1,000 토큰)
Block 2: 환경 정보 (<env>) (500 토큰)
Block 3-18: 16개 도구 사용 지침 (각 1,000-3,000 토큰)
Block 19: TodoWrite 시스템 (2,000 토큰)
Block 20: Git 프로토콜 (1,500 토큰)
Block 21: PR 프로토콜 (1,500 토큰)
Block 22-25: 기타 지침 (5,000 토큰)
```

**핵심**: Prompt Caching으로 매 요청마다 90% 비용 절감 (ephemeral cache)

### 2. DAG 구조 (Directed Acyclic Graph)

```
Main Agent
    ├→ [Optional] Task(Explore) ← Research
    ├→ [Optional] Task(Plan) ← Planning
    ├→ Action (Write/Edit)
    └→ Verify (Bash)
         ↓
      실패? → Fix → Re-verify (조건부 루프)
         ↓
      성공 → 완료
```

**특징**:
- ✅ 순환 없음 (뒤로 못 감)
- ✅ 조건부 재시도 (같은 단계만 반복)
- ❌ 자동 Re-plan 없음 (사용자 제어)

### 3. 4개 Subagent

| Agent | 용도 | 도구 | 발동 조건 |
|-------|------|------|----------|
| **general-purpose** | 복잡한 멀티스텝 작업 | ALL 16 tools | 불확실한 검색, 자동화 |
| **Explore** | 코드베이스 탐색 | ALL 16 tools | 파일 찾기, 패턴 검색 |
| **Plan** | 구현 계획 수립 | ALL 16 tools | 복잡한 기능 구현 전 |
| **statusline-setup** | 상태표시줄 설정 | Read, Edit만 | 상태표시줄 설정 시 |

**모두 같은 50k+ 토큰 시스템 프롬프트 사용!**

### 4. 16개 도구

**파일 작업**:
- Read, Write, Edit, NotebookEdit

**코드 탐색**:
- Glob, Grep

**실행**:
- Bash, BashOutput, KillShell

**에이전트**:
- Task (Subagent 생성)

**관리**:
- TodoWrite, AskUserQuestion

**외부**:
- WebSearch, WebFetch

**기타**:
- ExitPlanMode, SlashCommand, Skill

### 5. 검증 시스템

```
검증 전용 Agent 없음! ❌

Main이 직접:
  Edit → Bash(build) → 실패?
         → Read(error) → Edit(fix) → Bash(build)
                                      → 성공! ✅
```

**특징**:
- 즉각적 피드백
- Plan 없이 바로 수정
- 최대 3번 재시도

---

## 빠른 시작

### 1. Claude Code 이해하기

```bash
# 1. 아키텍처 개요 읽기
cat docs/01-architecture/system-overview.md

# 2. 기본 플로우 이해
cat docs/03-interactions/basic-flow.md

# 3. 시뮬레이션 확인
cat examples/interaction-simulations/1-simple-file-read.json
```

### 2. 실제 데이터 확인

```bash
# 캡처된 실제 요청 확인
cat references/captured-data/request-*.json

# 시스템 프롬프트 전체 보기
cat references/captured-data/system-prompt-*.txt

# 도구 정의 확인
cat references/captured-data/tools-*.json
```

### 3. 커스텀 구현 시작

```bash
# 구현 가이드 읽기
cat docs/04-implementation/getting-started.md

# 커스텀 Agent 만들기
cat docs/04-implementation/custom-agents.md

# 베스트 프랙티스
cat docs/04-implementation/best-practices.md
```

---

## 4가지 구현 버전

이 프로젝트는 Claude Code의 핵심 아키텍처를 **4가지 다른 방식**으로 구현합니다.

### 버전 비교

| 특징 | v1: OpenAI | v2: LangGraph | v3: OpenAI Agents | v4: Claude Agent |
|------|-----------|---------------|-------------------|------------------|
| **상태** | ✅ **REFACTORED** | ✅ COMPLETE | ✅ COMPLETE | ✅ **REFACTORED** |
| **LLM** | OpenAI | Any (OpenAI/Claude/etc) | OpenAI | **Claude** |
| **코드 길이** | 중간 (~1,891줄) ⭐ | 짧음 (~450줄) | 간결 (~280줄) | **간결 (~302줄)** ⭐ |
| **핵심 로직** | ~334줄 ⭐ (-66줄) | ~200줄 | ~130줄 | **~50줄!** |
| **Subagent** | ✅ 재귀 실행 | ✅ StateGraph | ✅ Agent.as_tool() | ✅ **agents 파라미터** |
| **추상화 수준** | 낮음 (직접 구현) | 중간 (그래프) | 높음 (SDK) | **최고 (설정)** |
| **커스터마이징** | 완전 자유 | 높음 | 제한적 | 중간 |
| **가독성** | ✅ **개선됨!** ⭐ | 중간 | 높음 | **최고** |
| **Streaming** | ✅ 구현됨 | ✅ 구현됨 | 내장 | **내장** |
| **MCP 지원** | 수동 구현 | 가능 | ✗ | **네이티브 ✓** |
| **System Prompt** | 수동 | 수동 | 수동 | **Preset ✓** |
| **Hook 시스템** | 수동 | 가능 | ✗ | **내장 ✓** |
| **Claude Code 호환** | ✗ | ✗ | ✗ | ✓ **(공식!)** |
| **의존성** | `openai`, `rich` | `langgraph`, `langchain` | `openai-agents` | `claude-agent-sdk` |

**리팩토링 완료** (2025-01):
- ⭐ **v1**: 레지스트리 패턴 (-66줄), 함수 분해 (중첩 -60%)
- ⭐ **v4**: 설정 분리 (config.py로 72줄 이동)

### Version 1: OpenAI API 직접 사용 ✅ **COMPLETE**

**학습 목적**: Claude Code의 핵심 패턴 완전 이해

```python
# 핵심 패턴 1: 스트리밍 + finish_reason 루프
async with client.chat.completions.stream(...) as stream:
    async for chunk in stream:
        if chunk.delta.content:
            print(chunk.delta.content, end="")  # 실시간!
        if chunk.delta.tool_calls:
            collect_tool_calls(chunk)

if finish_reason == "tool_calls":
    for tool_call in tool_calls:
        if tool_call.name == "Task":
            # Subagent 재귀 실행!
            result = await execute_subagent(...)
        else:
            result = await execute_tool(...)
```

**구현 완료**:
- ✅ **16개 도구** - Read, Write, Edit, Bash, Glob, Grep, TodoWrite, Task, ExitPlanMode, AskUserQuestion, NotebookEdit, BashOutput, KillShell, WebSearch, WebFetch, SlashCommand
- ✅ **Subagent 시스템** - 재귀적 Task 실행 (4가지 타입: general-purpose, Explore, Plan, statusline-setup)
- ✅ **스트리밍** - AsyncOpenAI로 실시간 응답 표시
- ✅ **클로드 코드 원본 프롬프트** - 동일 구조 (~17KB, 410줄)
- ✅ **Pydantic 타입 안전성** - 모든 도구 입력 검증
- ✅ **Rich UI** - 터미널 인터페이스 (패널, 마크다운, 스피너)

**특징**:
- ✅ 모든 로직 직접 구현 → 이해 쉬움
- ✅ 완전한 제어 → 커스터마이징 자유
- ✅ 교육용으로 최적 → 핵심 패턴 명확
- ✅ 프로덕션 레디 → 실제 사용 가능
- ⚠️ 코드량 많음 (~1,915줄)

**언제 사용**: 내부 동작을 완전히 이해하고 싶을 때, 최대한 커스터마이징이 필요할 때, OpenAI 모델 사용 시

📖 [상세 가이드](src/custom_claude_code/v1_openai/README.md)

### Version 2: LangGraph를 활용한 구현 ✅ **COMPLETE**

**학습 목적**: 상태 머신 기반 agent 설계 + 워크플로우 자동화

```python
# 핵심 패턴: StateGraph로 루프 자동화!
builder = StateGraph(AgentState)
builder.add_node("agent", call_agent)
builder.add_node("tools", ToolNode(TOOLS))

builder.add_edge(START, "agent")
builder.add_conditional_edges(
    "agent",
    should_continue,  # tool_calls 체크
    {"tools": "tools", END: END}
)
builder.add_edge("tools", "agent")  # 루프!

graph = builder.compile()

# 사용: v1의 while 루프 필요 없음!
async for event in graph.astream({"messages": [user_msg]}):
    # 자동으로 agent → tools → agent → ... → END
    print(event)
```

**구현 완료**:
- ✅ **7개 도구** - Read, Write, Edit, Glob, Grep, Bash + **Task** (@tool 데코레이터)
- ✅ **Subagent 시스템** - 독립 StateGraph로 중첩 실행 (4가지 타입)
- ✅ **StateGraph** - 자동 루프 (agent → tools → agent)
- ✅ **커스텀 도구 노드** - task_tool 감지 및 execute_subagent() 호출
- ✅ **Streaming** - graph.astream()으로 실시간 업데이트
- ✅ **Memory 옵션** - MemorySaver로 히스토리 관리
- ✅ **그래프 시각화** - Mermaid 다이어그램 생성

**특징**:
- ✅ 루프 로직 자동화 → v1 대비 76% 코드 감소 (~450줄, Subagent 포함)
- ✅ Subagent as StateGraph → 각 Subagent가 독립 그래프
- ✅ 조건부 분기 명확 → should_continue 함수
- ✅ 히스토리 자동 관리 → Checkpointer
- ✅ 그래프 시각화 → draw_mermaid_png()
- ✅ Any LLM 지원 → OpenAI, Claude, Gemini 등
- ⚠️ LangGraph 학습 필요 (중간 난이도)

**언제 사용**: 복잡한 multi-agent 플로우, 상태 관리가 중요할 때, 코드 간결성 중요 시

📖 [상세 가이드](src/custom_claude_code/v2_langgraph/README.md)

### Version 3: OpenAI Agents SDK를 활용한 구현 ✅ **COMPLETE**

**학습 목적**: 최고 수준 추상화 + 극도로 간단한 코드

```python
# 핵심 패턴: Agent + Runner.run() (이게 전부!)
from agents import Agent, Runner, function_tool, SQLiteSession

@function_tool
def read_file(file_path: str) -> str:
    """Read a file."""
    with open(file_path) as f:
        return f.read()

agent = Agent(
    name="Coding Assistant",
    instructions="You are a helpful coding assistant.",
    tools=[read_file, write_file, edit_file, glob_files, grep_code, run_bash]
)

# 실행 - 한 줄로 끝!
session = SQLiteSession("conversation_v3")
result = await Runner.run(agent, input=user_input, session=session)
print(result.final_output)  # 완료!
```

**구현 완료**:
- ✅ **6개 핵심 도구** - Read, Write, Edit, Glob, Grep, Bash (@function_tool)
- ✅ **4개 Subagent** - Explore, Plan, General-purpose, Statusline-setup (Agent.as_tool()!)
- ✅ **Agent + Runner** - 극도로 간단한 실행 (한 줄!)
- ✅ **SQLiteSession** - 자동 히스토리 관리
- ✅ **총 코드 ~280줄** - Subagent 포함, v1 대비 85% 감소!

**특징**:
- ✅ 가장 간결한 코드 - 핵심 로직 ~130줄 (Subagent 포함 ~280줄)
- ✅ Subagent as Tool - Agent.as_tool()로 한 줄에 변환!
- ✅ 도구 실행 완전 자동화 - while 루프 필요 없음
- ✅ Pydantic 검증 자동 - @function_tool이 처리
- ✅ Session 자동 관리 - SQLiteSession으로 히스토리 자동 저장
- ✅ 내장 Tracing - Logfire, AgentOps 지원
- ⚠️ OpenAI Agents SDK 의존 - 커스터마이징 제한적

**언제 사용**: 빠른 프로토타이핑, 최소 코드로 agent 구축, OpenAI 생태계 활용

📖 [상세 가이드](src/custom_claude_code/v3_openai_agents/README.md)

### Version 4: Claude Agent SDK를 활용한 구현 ✅ **COMPLETE**

**학습 목적**: 최고 수준 추상화 + Subagent를 설정으로!

```python
# 핵심 패턴: ClaudeSDKClient + agents 파라미터 (혁명!)
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    system_prompt={"type": "preset", "preset": "claude_code"},
    agents={  # Subagent가 설정으로!
        "explore": {
            "description": "Explore the codebase",
            "prompt": "You are an Explore agent...",
            "tools": ["Glob", "Grep", "Read"],
            "model": "sonnet"
        }
    }
)

async with ClaudeSDKClient(options=options) as client:
    await client.query(user_input)
    async for msg in client.receive_response():
        print(msg)
```

**구현 완료**:
- ✅ **ClaudeSDKClient** - Interactive 대화형 클라이언트
- ✅ **4개 Subagent** - explore, plan, general, statusline (**agents 파라미터로!**)
- ✅ **System Prompt Preset** - claude_code preset 사용
- ✅ **6개 내장 도구** - Read, Write, Edit, Bash, Glob, Grep
- ✅ **Rich UI** - Panel, Markdown으로 예쁜 터미널
- ✅ **비용 자동 추적** - ResultMessage에 포함
- ✅ **총 코드 ~280줄** - 핵심 로직 **~50줄!**

**특징**:
- ✅ **Subagent = 설정** - 코드 불필요, agents 파라미터로 정의!
- ✅ **System Prompt Preset** - claude_code preset 사용
- ✅ **MCP 네이티브** - In-process MCP servers
- ✅ **Hook 시스템** - PreToolUse, PostToolUse
- ✅ **Anthropic 공식** - Claude Code와 동일한 SDK
- ⚠️ **Claude만 지원** - OpenAI, Gemini 불가

**언제 사용**: Claude 모델 사용 시, MCP 활용, 설정 기반 agent, 공식 SDK

📖 [상세 가이드](src/custom_claude_code/v4_claude_agent/README.md)

### 어떤 버전을 선택할까?

```
┌─────────────────────────────────────────┐
│ 목적에 따른 버전 선택 가이드              │
├─────────────────────────────────────────┤
│                                         │
│  학습/이해가 목표                        │
│  → v1 (OpenAI 직접 사용)                │
│                                         │
│  복잡한 multi-agent 플로우               │
│  → v2 (LangGraph)                       │
│                                         │
│  빠른 프로토타이핑 + OpenAI 사용          │
│  → v3 (OpenAI Agents SDK)               │
│                                         │
│  Claude Code 스타일 + Claude 사용 ⭐     │
│  → v4 (Claude Agent SDK)                │
│                                         │
└─────────────────────────────────────────┘
```

### 프로젝트 구조 (구현)

```
src/custom_claude_code/
├── v1_openai/               # Version 1: OpenAI 직접
│   ├── __init__.py
│   ├── main.py              # 메인 대화 루프
│   ├── tools.py             # 4개 도구 (Read, Write, Edit, Bash)
│   ├── system_prompt.py     # 시스템 프롬프트
│   └── README.md
│
├── v2_langgraph/            # Version 2: LangGraph
│   ├── __init__.py
│   ├── main.py              # 메인 실행
│   ├── graph.py             # StateGraph 정의
│   ├── tools.py             # 도구 (v1과 동일)
│   └── README.md
│
├── v3_openai_agents/        # Version 3: OpenAI Agents SDK
│   ├── __init__.py
│   ├── main.py              # 메인 실행
│   ├── agents.py            # Agent 정의
│   └── README.md
│
└── v4_claude_agent/         # Version 4: Claude Agent SDK
    ├── __init__.py
    ├── main.py              # 메인 실행
    ├── agents.py            # ClaudeAgent 정의
    └── README.md
```

---

## 문서 가이드

### 📖 읽는 순서 (초보자)

1. **[시스템 개요](docs/01-architecture/system-overview.md)** - 전체 그림 이해
2. **[기본 플로우](docs/03-interactions/basic-flow.md)** - 단순한 동작 방식
3. **[시스템 프롬프트](docs/02-components/system-prompt.md)** - 50k+ 토큰 구조
4. **[도구들](docs/02-components/tools.md)** - 16개 도구 상세
5. **[멀티 에이전트](docs/03-interactions/multi-agent.md)** - 복잡한 동작
6. **[구현 시작](docs/04-implementation/getting-started.md)** - 직접 만들기

### 🚀 읽는 순서 (숙련자)

1. **[그래프 구조](docs/01-architecture/graph-structure.md)** - DAG 상세
2. **[Subagent 분석](docs/02-components/agents.md)** - 4개 Agent 완전 분석
3. **[사용자 피드백](docs/03-interactions/user-feedback.md)** - 루프 메커니즘
4. **[에러 복구](docs/03-interactions/error-recovery.md)** - 재시도 로직
5. **[커스텀 Agent](docs/04-implementation/custom-agents.md)** - 고급 구현

### 📚 주제별 가이드

**아키텍처 이해**:
- [시스템 개요](docs/01-architecture/system-overview.md)
- [그래프 구조](docs/01-architecture/graph-structure.md)
- [데이터 흐름](docs/01-architecture/data-flow.md)

**컴포넌트 상세**:
- [시스템 프롬프트](docs/02-components/system-prompt.md)
- [도구들](docs/02-components/tools.md)
- [Subagent](docs/02-components/agents.md)
- [검증 시스템](docs/02-components/verification.md)

**상호작용 패턴**:
- [기본 플로우](docs/03-interactions/basic-flow.md)
- [멀티 에이전트](docs/03-interactions/multi-agent.md)
- [사용자 피드백](docs/03-interactions/user-feedback.md)
- [에러 복구](docs/03-interactions/error-recovery.md)

**구현하기**:
- [시작 가이드](docs/04-implementation/getting-started.md)
- [커스텀 Agent](docs/04-implementation/custom-agents.md)
- [베스트 프랙티스](docs/04-implementation/best-practices.md)

---

## 핵심 인사이트

### 💡 설계 철학

1. **도구 중심 아키텍처**
   - 모든 작업은 도구 조합으로 표현
   - 시스템 프롬프트가 "사용 설명서"
   - LLM이 적절한 도구 선택

2. **경제적 설계**
   - Prompt Caching 필수 (90% 절감)
   - 50k+ 토큰을 매번 보낼 수 없음
   - 5분 TTL로 세션 유지

3. **사용자 제어**
   - 자동 루프 없음
   - 항상 사용자 입력 대기
   - 예측 가능한 비용

4. **계층적 에이전트**
   - Task tool로 subprocess 생성
   - 독립적 대화 컨텍스트
   - 무한 중첩 가능 (DAG 제약)

### 🎯 주요 패턴

**1. Read → Analyze → Edit → Verify**
```
가장 기본적인 패턴
Main이 모든 단계 직접 수행
```

**2. Explore → Plan → Execute**
```
복잡한 작업 패턴
각 단계를 Subagent로 분리
```

**3. Verify → Fix → Re-verify**
```
에러 복구 패턴
Plan 없이 즉시 수정
```

**4. User Request → Claude Response → User Feedback → ...**
```
대화 확장 패턴
루프가 아닌 선형 추가
```

### ⚠️ 흔한 오해

| 오해 | 실제 |
|------|------|
| "Plan → Do → Check → Act 사이클" | 한 방향 DAG + 조건부 재시도 |
| "검증 전용 Agent 있음" | Main이 Bash로 직접 검증 |
| "Subagent마다 다른 시스템 프롬프트" | 모두 같은 50k+ 프롬프트 |
| "Fix 시 자동 Re-plan" | Plan 없이 바로 수정 |
| "사용자 피드백으로 루프" | 대화 확장 (append-only) |

---

## 기여

이 문서는 실제 Claude Code 분석을 기반으로 작성되었습니다.

**분석 방법**:
1. Claude Code Router로 localhost:3456에서 요청 가로채기
2. System prompt, Tools, Messages 전체 캡처
3. 3가지 복잡도의 시뮬레이션 생성
4. 패턴 추출 및 문서화

**업데이트**:
- Claude Code가 업데이트되면 이 문서도 업데이트 필요
- 시스템 프롬프트 변경 추적
- 새로운 도구 추가 확인

---

## 라이선스

이 문서는 교육 및 연구 목적으로 작성되었습니다.

**참고**:
- Claude Code는 Anthropic의 공식 제품입니다
- 이 문서는 비공식 분석입니다
- 커스텀 구현 시 Anthropic의 서비스 약관을 준수하세요

---

## 다음 단계

### 학습 경로

1. ✅ **이해 단계**: 문서 읽기 (1-2일)
2. ✅ **분석 단계**: 시뮬레이션 확인 (1일)
3. ✅ **실험 단계**: Router로 실제 데이터 캡처 (1일)
4. 🚧 **구현 단계**: 커스텀 도구/Agent 만들기 (1주)
5. 🚧 **최적화 단계**: 프롬프트 튜닝, 비용 최적화 (ongoing)

### 커스텀 구현 체크리스트

- [ ] 시스템 프롬프트 설계 (최소 20k+ 토큰)
- [ ] 핵심 도구 구현 (Read, Write, Edit, Bash 최소)
- [ ] Prompt Caching 적용 (필수!)
- [ ] 기본 Agent 구현 (Main)
- [ ] Subagent 시스템 (Task tool)
- [ ] 도구 사용 루프 (stop_reason 처리)
- [ ] 에러 복구 메커니즘
- [ ] TodoWrite 시스템 (선택)
- [ ] 비용 추적 시스템

---

**생성 날짜**: 2025-11-15
**분석 대상**: Claude Code (claude.ai/code)
**목적**: 커스텀 AI 코딩 어시스턴트 구현을 위한 완전한 레퍼런스

**시작하기**: [docs/01-architecture/system-overview.md](docs/01-architecture/system-overview.md)
