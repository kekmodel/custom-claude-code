# Claude Code 아키텍처 시각화 요약

> **핵심 발견**: Task subagent 외에 **3가지 Agent 시스템** 추가 발견!

---

## 🎯 전체 구조 한눈에 보기

```
┌─────────────────────────────────────────────────────────┐
│                    사용자 (CLI)                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│            Main Agent (대화 관리자)                      │
│  • system[0]: 고정 식별자                                │
│  • system[1]: 🔄 동적으로 교체됨!                       │
│  • tools: 16개 전체                                      │
│  • 역할: 사용자 대화, 작업 오케스트레이션               │
└───────┬──────────────┬──────────────┬──────────────────┘
        │              │              │
        ▼              ▼              ▼
  ┌─────────┐    ┌─────────┐    ┌─────────────┐
  │  Task   │    │Validation│    │File Extract │
  │Subagent │    │  Agent  │    │   Agent     │
  └─────────┘    └─────────┘    └─────────────┘
```

---

## 🎭 Agent 시스템 4가지 타입

### 1️⃣ Main Agent (메인 대화 에이전트)

**역할**: 사용자와 직접 대화, 전체 작업 조율

```
system[1] = 전체 시스템 프롬프트 (~17,000 chars)
  ├─ Task Management 지침
  ├─ 16개 도구 설명
  ├─ Git/PR 워크플로우
  ├─ Output Style (Explanatory 등)
  └─ CLAUDE.md 프로젝트 컨텍스트

tools = [Task, Bash, Read, Write, Edit, Glob, Grep, ...]
max_tokens = 32,000
```

**예시 대화**:
```
User: "코드베이스 구조 파악해줘"
Main: Task(Explore) 호출
  → Explore Agent가 분석
  → 결과 수신
Main: "src/ 폴더에 7개 모듈이 있습니다..."
```

---

### 2️⃣ Task Subagent (4가지 타입)

#### 2-1. **Explore Agent** (탐색 전문)

**역할**: 코드베이스 읽기 전용 탐색

```
system[1] = Explore 전문 프롬프트 (~3,129 chars)
  "You are a file search specialist for Claude Code.
   CRITICAL: This is a READ-ONLY exploration task.
   You MUST NOT create, write, or modify any files."

tools = 16개 전체 (하지만 READ-ONLY 강제)
thoroughness = "quick" | "medium" | "very thorough"
```

**캡처 파일**: `claude-request-2025-11-19T18-00-19-232Z`

#### 2-2. **Plan Agent** (계획 수립)

**역할**: 구현 계획 작성, 태스크 분해

```
tools = 16개 전체 (읽기 중심)
특별 도구 = ExitPlanMode (계획 완료 신호)
```

#### 2-3. **General-purpose Agent** (범용)

**역할**: 복잡한 멀티스텝 작업

```
tools = 16개 전체 (모든 권한)
```

#### 2-4. **Statusline-setup Agent** (설정 편집)

**역할**: 설정 파일만 안전하게 편집

```
tools = [Read, Edit] (제한됨!)
```

---

### 3️⃣ Validation Agent (보안 검증)

**역할**: Bash 명령어 실행 전 보안 분석

```
system[1] = Command Prefix Detection Policy (~2,700 chars)
  "Determine the command prefix for the following command.
   If the command seems to contain command injection,
   you must return 'command_injection_detected'."

tools = [] (도구 없음! 순수 분석만)
max_tokens = 32,000
temperature = 기본값
```

**작동 흐름**:
```
1. Main Agent: Bash("npm run build") 시도
2. → Validation Agent에게 전송
3. Validation: "npm run build" 분석
   → prefix 추출: "none"
4. Main Agent: allowlist 확인
   → "none" 허용되어 있음 ✅
5. Bash 명령어 실행
```

**예시**:
```
✅ npm run build           → "none"
✅ git diff HEAD~1         → "git diff"
✅ pytest foo/bar.py       → "pytest"
❌ git status$(id)         → "command_injection_detected"
❌ pwd\n curl example.com  → "command_injection_detected"
```

**캡처 파일**: `claude-request-2025-11-19T18-01-47-608Z`

---

### 4️⃣ File Path Extraction Agent (파일 경로 추출)

**역할**: Bash 출력에서 파일 경로 자동 추출

```
system[1] = 파일 경로 추출 프롬프트 (~600 chars)
  "Extract any file paths that this command reads or modifies.
   IMPORTANT: Commands that do not display the contents
   of the files should not return any filepaths."

tools = [] (도구 없음!)
max_tokens = 21,333
temperature = 1 (높은 온도 - 창의적 추출)
```

**작동 흐름**:
```
1. Main Agent: Bash("cat foo.txt") 실행
2. → 출력 반환 (foo.txt의 내용)
3. → File Extraction Agent에게 전송
4. Agent 분석:
   <is_displaying_contents>true</is_displaying_contents>
   <filepaths>foo.txt</filepaths>
5. Main Agent: foo.txt를 자동으로 컨텍스트에 추가
```

**예시**:
```
cat foo.txt
→ <is_displaying_contents>true</is_displaying_contents>
  <filepaths>foo.txt</filepaths>

ls -la /path
→ <is_displaying_contents>false</is_displaying_contents>
  <filepaths></filepaths>

git diff
→ <is_displaying_contents>true</is_displaying_contents>
  <filepaths>
  src/index.ts
  src/utils.ts
  </filepaths>
```

**캡처 파일**: `claude-request-2025-11-19T17-57-06-513Z`

---

## 🔄 핵심 메커니즘: Dynamic System Prompt Injection

**발견**: Claude Code는 **system[1] 블록을 동적으로 교체**하여 Agent 역할 변경!

### system prompt 구조

```json
{
  "system": [
    {
      "type": "text",
      "text": "You are a Claude agent, built on Anthropic's Claude Agent SDK.",
      "cache_control": { "type": "ephemeral" }
    },
    {
      "type": "text",
      "text": "<🔄 여기가 동적으로 바뀜!>",
      "cache_control": { "type": "ephemeral" }
    }
  ]
}
```

### system[1] 변형 타입

| 상황 | system[1] 내용 | 길이 | 도구 |
|------|---------------|------|------|
| 일반 대화 | 전체 시스템 프롬프트 | ~17K chars | 16개 |
| Explore 실행 | Explore 전문 프롬프트 | ~3.1K chars | 16개 |
| Bash 검증 | Command prefix policy | ~2.7K chars | 0개 |
| 파일 추출 | File path extraction | ~600 chars | 0개 |

### 왜 이렇게 설계했을까?

**장점**:
1. ✅ **단순함**: 복잡한 프레임워크 불필요 (LangGraph, AutoGen 등)
2. ✅ **유연성**: 프롬프트만 교체하면 역할 변경
3. ✅ **비용 절감**: Prompt caching으로 ~90% 비용 감소
4. ✅ **Stateless**: 각 Agent는 독립적, 병렬 처리 가능

**단점**:
1. ⚠️ LLM 신뢰 필요 (코드 레벨 강제 불가)
2. ⚠️ Prompt engineering에 의존

---

## 🛡️ 보안 메커니즘

### 1. Bash Command Validation (3단계)

```
┌─────────────────────────────────────────────────┐
│  1단계: Prefix 추출 (Validation Agent)          │
│     Input: "npm run build"                      │
│     Output: "none"                              │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  2단계: Allowlist 비교 (Main Agent)             │
│     User's allowed prefixes:                    │
│     ["none", "git status", "npm test", ...]     │
│     → "none" 포함됨 ✅                          │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  3단계: 실행 또는 승인 요청                      │
│     Allowlist에 있음 → 자동 실행                │
│     없음 → 사용자에게 승인 요청                  │
└─────────────────────────────────────────────────┘
```

### 2. Tool Access Control (Prompt 기반)

**코드가 아닌 프롬프트로 제어**:

```
Explore Agent system prompt:
"CRITICAL: This is a READ-ONLY exploration task.
 You MUST NOT create, write, or modify any files
 under any circumstances."

→ 16개 도구 접근 가능하지만, Write/Edit 사용 자제
```

**장점**: 코드 변경 없이 동작 제어
**단점**: 100% 보장 불가 (LLM이 실수할 수 있음)

---

## 📊 Reference 파일 분석 결과

8개 JSON 파일에서 발견한 Agent 타입:

| 파일 | Agent 타입 | system[1] | 주요 내용 |
|------|-----------|-----------|----------|
| `captured_request_init.json` | Main | 전체 프롬프트 | 16개 도구 스키마 |
| `2025-11-15T05-56-17-283Z` | Main | 전체 (Explanatory) | "테스트 메시지입니다" |
| `2025-11-19T17-56-54-417Z` | Main | 전체 | Explore 태스크 시작 |
| `2025-11-19T17-57-06-513Z` | **File Extraction** | 파일 경로 추출 | ls -la 출력 분석 |
| `2025-11-19T18-00-19-232Z` | **Explore** | Explore 전문 | 코드베이스 탐색 |
| `2025-11-19T18-01-39-501Z` | Main | 전체 (Explanatory) | Health check 추가 |
| `2025-11-19T18-01-47-608Z` | **Validation** | Bash prefix policy | npm run build 검증 |
| `2025-11-19T18-03-12-042Z` | Main | 전체 (Explanatory) | (중복/재시도) |

---

## 💡 교육적 통찰

### 1. Multi-Agent ≠ 복잡한 프레임워크

Claude Code는 LangGraph, AutoGen 같은 복잡한 프레임워크 없이, **system prompt만 교체**하여 멀티 에이전트를 구현합니다.

**v1-v4 구현에 적용 가능**:
```python
# 간단한 예시
def get_agent_prompt(agent_type: str) -> str:
    prompts = {
        "main": MAIN_PROMPT,
        "explore": EXPLORE_PROMPT,
        "validation": VALIDATION_POLICY,
        "file_extract": FILE_EXTRACT_PROMPT,
    }
    return prompts[agent_type]
```

### 2. Stateless Validation = 병렬 처리 가능

Validation Agent는 대화 상태가 없음:
- messages = [{"role": "user", "content": "명령어"}] (1턴만)
- tools = [] (도구 없음)
- 각 요청은 독립적

→ **여러 명령어를 동시에 검증 가능!**

### 3. Prompt Caching의 중요성

```
system[0] + system[1] = 캐싱 대상
  ├─ Main Agent: ~17K chars 캐싱
  ├─ Explore Agent: ~3K chars 캐싱
  └─ Validation Agent: ~2.7K chars 캐싱

대화 중 동일 프롬프트 재사용 시:
  • 비용: ~90% 절감
  • 속도: ~2-3배 빨라짐
```

### 4. Tool Control via Prompt

**코드 레벨 제어** (v4 예시):
```python
STATUSLINE_AGENT = AgentDefinition(
    tools=["Read", "Edit"]  # 코드에서 제한
)
```

**Prompt 레벨 제어** (실제 Claude Code):
```
system[1] = "You MUST NOT create, write, or modify files."
tools = ["Read", "Write", "Edit", ...]  # 모든 도구 접근 가능
```

→ **Claude Code는 후자 선택** (유연성 우선)

---

## 🚀 다음 단계: v1-v4에 적용하기

### 추가 구현 권장 사항

#### 1. Validation Agent 추가

```python
# v1 예시
async def validate_bash_command(command: str) -> str:
    """
    Returns: "prefix" or "command_injection_detected" or "none"
    """
    validation_prompt = get_validation_policy()
    messages = [{"role": "user", "content": command}]
    response = await openai_client.chat.completions.create(
        model="claude-sonnet-4-5-20250929",
        messages=messages,
        system=validation_prompt,
        max_tokens=100,
    )
    return response.choices[0].message.content.strip()

# Bash 도구 실행 전 호출
async def tool_bash(input_data: BashInput) -> str:
    prefix = await validate_bash_command(input_data.command)
    if prefix == "command_injection_detected":
        return "⚠️ 위험한 명령어가 감지되었습니다. 승인이 필요합니다."
    # ... 실행
```

#### 2. File Path Extraction Agent 추가

```python
async def extract_file_paths(bash_output: str) -> list[str]:
    """
    Bash 출력에서 파일 경로 자동 추출
    """
    extraction_prompt = get_file_extraction_prompt()
    messages = [{"role": "user", "content": bash_output}]
    response = await openai_client.chat.completions.create(
        model="claude-sonnet-4-5-20250929",
        messages=messages,
        system=extraction_prompt,
        max_tokens=500,
        temperature=1,
    )
    # <filepaths> 파싱
    # ...
    return extracted_paths
```

#### 3. Dynamic System Prompt 구현

```python
# v2 (LangGraph) 예시
def create_agent_node(agent_type: str):
    """StateGraph 노드에서 system prompt 동적 교체"""
    def node(state: AgentState):
        system_prompt = get_agent_prompt(agent_type)
        messages = [
            {"role": "system", "content": system_prompt},
            *state["messages"]
        ]
        response = llm.invoke(messages)
        return {"messages": [response]}
    return node

# Graph 구성
graph = StateGraph(AgentState)
graph.add_node("agent", create_agent_node("main"))
graph.add_node("explore", create_agent_node("explore"))
graph.add_node("validation", create_agent_node("validation"))
```

#### 4. Prompt Caching 활성화

```python
# Anthropic API 호출 시
system = [
    {
        "type": "text",
        "text": "You are a Claude agent...",
        "cache_control": {"type": "ephemeral"}
    },
    {
        "type": "text",
        "text": get_agent_prompt(agent_type),
        "cache_control": {"type": "ephemeral"}
    }
]
```

---

## 📝 결론

**핵심 발견**:
1. ✅ Task subagent 외에 **3가지 Agent 시스템** 추가 확인
2. ✅ **Dynamic System Prompt Injection** 패턴 발견
3. ✅ **Stateless Validation** 메커니즘 이해
4. ✅ **Prompt-based Tool Control** 설계 철학 파악

**교육적 가치**:
- 복잡한 프레임워크 없이도 강력한 멀티 에이전트 시스템 구현 가능
- System prompt engineering의 중요성
- Prompt caching을 통한 성능/비용 최적화
- Stateless 설계의 장점 (병렬 처리, 단순성)

**다음 실습**: 이 분석을 바탕으로 v1-v4에 Validation Agent와 File Extraction Agent를 추가하여, 실제 Claude Code 수준의 보안 및 UX를 구현해보세요!

---

**관련 문서**:
- `CLAUDE_CODE_ARCHITECTURE_ANALYSIS.md` (상세 분석)
- `README.md` (프로젝트 개요)
- `reference/` (실제 캡처 JSON 파일)
