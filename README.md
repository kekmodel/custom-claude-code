# Custom Claude Code

> Claude Code 내부 아키텍처 분석 및 5가지 구현 방법 비교

## 개요

Claude Code의 내부 동작 원리를 분석하고, 동일한 기능을 5가지 방식으로 구현한 교육/연구 프로젝트입니다.

- 시스템 프롬프트 (약 3,000 토큰) + 도구 스키마 (약 14,000 토큰) = 총 약 17,000 토큰
- 16개 도구 (MCP로 확장 가능), 4가지 Subagent 타입, DAG 기반 워크플로우
- 실제 API 요청/응답 캡처 및 시뮬레이션

---

## 빠른 시작

```bash
# 설치
uv sync

# 환경 변수 설정 (.env 파일 참고)
cp .env.example .env

# 실행
uv run python launcher.py                                          # 대화형 런처
uv run python -m custom_claude_code.v1_openai.main                 # v1
uv run python -m custom_claude_code.v2_langgraph.main              # v2
uv run python -m custom_claude_code.v2_1_langgraph_improved.main   # v2.1 ⭐ 최신!
uv run python -m custom_claude_code.v3_openai_agents.main          # v3
uv run python -m custom_claude_code.v4_claude_agent.main           # v4
```

---

## 프로젝트 구조

```
custom-claude-code/
├── src/custom_claude_code/
│   ├── v1_openai/              # OpenAI API 직접 (1,966 lines)
│   ├── v2_langgraph/           # LangGraph StateGraph (2,376 lines)
│   ├── v2_1_langgraph_improved/ # v2 개선 버전 (2025-11-19)
│   ├── v3_openai_agents/       # OpenAI Agents SDK (516 lines)
│   ├── v4_claude_agent/        # Claude Agent SDK (311 lines)
│   └── common/
├── reference/              # 실제 캡처 데이터
├── tests/                  # 테스트
├── launcher.py
└── CLAUDE.md
```

---

## 5가지 구현 비교

| 특징 | v1 | v2 | v2.1 ⭐ | v3 | v4 |
|------|----|----|---------|----|----|
| **코드량** | ~1,891줄 | ~2,376줄 | ~585줄 | ~516줄 | ~311줄 |
| **LLM 지원** | OpenAI/Claude | OpenAI/Claude/Gemini | OpenAI/Claude/Gemini | OpenAI | Claude |
| **핵심 패턴** | 수동 대화 루프 | StateGraph + 압축 | StateGraph 단순화 | Agent + Runner | ClaudeSDKClient |
| **도구 개수** | 16개 | 9개 | 14개 | 9개 | 16개 |
| **Subagent** | 재귀 실행 | 독립 StateGraph | Tag 필터링 | Agent.as_tool() | agents 파라미터 |
| **메시지 압축** | 없음 | 100k 토큰 자동 | 없음 (단순화) | 없음 | 없음 |
| **웹 접근** | ✅ | ❌ | ✅ (신규) | ❌ | ✅ |

### v1: OpenAI API 직접 사용

**파일**:
- main.py (385줄), tools.py (705줄), subagent.py (270줄), system_prompt.py (410줄), types.py (187줄)

**특징**:
- 모든 패턴 명시적 구현 (finish_reason, tool_calls, streaming)
- TOOL_REGISTRY 패턴
- 16개 도구 완전 구현
- 4개 Subagent 타입 (general, explore, plan, statusline)

### v2: LangGraph StateGraph

**파일**:
- main.py (678줄), graph.py (114줄), nodes.py (378줄), tools.py (591줄), prompts.py (329줄), models.py (152줄), config.py (85줄)

**특징**:
- 자동 대화 루프 (agent → tools → agent)
- 조건부 분기 (should_continue)
- 독립 StateGraph per Subagent
- OpenAI/Claude/Gemini 지원

**최근 개선** (2025-01):
- Prompt 중앙화, AIMessage 중복 수정
- 대화 압축 (100k 토큰), 멀티 모델 지원
- 스트리밍 최적화, 도구 개선

### v2.1: LangGraph Improved (NEW - 2025-11-19)

**파일**:
- main.py, graph.py, nodes.py, tools.py, prompts.py, models.py, config.py

**주요 개선 사항**:
1. **코드 단순화**:
   - `compact_messages()` 제거 (273줄 삭제, 불필요한 압축 로직)
   - `call_agent()` 단순화 (~120줄 → ~13줄, 83% 감소)
   - `EventHandler` depth tracking 제거 (callbacks=[] 신뢰)

2. **도구 확장** (9개 → 14개):
   - 백그라운드 실행: `bash_background`, `bash_output`, `kill_shell`
   - 웹 접근: `web_search` (DuckDuckGo), `web_fetch` (URL 파싱)

3. **프롬프트 개선**:
   - 새 도구 사용 가이드 추가
   - 버전 2.1.0으로 업데이트

**실행**:
```bash
uv run python -m custom_claude_code.v2_1_langgraph_improved.main
uv run python test_v2.1_basic.py  # 기본 테스트
```

### v3: OpenAI Agents SDK

**파일**:
- main.py (286줄), tools.py (221줄)

**특징**:
- Agent.as_tool()로 Subagent 변환
- SQLiteSession 자동 히스토리
- @function_tool 데코레이터

### v4: Claude Agent SDK

**파일**:
- main.py (208줄), config.py (94줄)

**특징**:
- Subagent = 설정 (agents 파라미터)
- System Prompt Preset (claude_code)
- MCP 네이티브, Hook 시스템
- Anthropic 공식 SDK

---

## 핵심 개념

### 실제 동작 구조

**기본 루프:**
```
User 요청
  ↓
Main Agent (LLM)
  ↓ 판단
  ┌─────────────────────┐
  │ 복잡도에 따라 선택:   │
  │ - 단순: 직접 처리    │
  │ - 복잡: Task 호출    │
  └─────────────────────┘
  ↓
도구 실행 (병렬 가능)
  ↓
tool_result 분석
  ↓
성공? → 다음 단계
실패? → 오류 분석 → 수정 도구 → 재시도
  ↓
반복 (LLM 판단으로 종료)
```

**피드백 루프 (핵심!):**
```
예: 코드 작성 → 테스트
  Write(code.py)
    ↓
  Bash(pytest)
    ↓ tool_result: "FAILED: 3 errors"
  오류 분석
    ↓
  Read(code.py) ← 오류 부분 확인
    ↓
  Edit(code.py) ← 수정
    ↓
  Bash(pytest)
    ↓ tool_result: "PASSED: 10 tests"
  성공 → 완료
```

**특징:**
- LLM이 tool_result 보고 다음 도구 선택
- 오류 시 자동으로 수정 시도
- 성공할 때까지 반복 (또는 LLM 판단으로 중단)

### Subagent (Task 도구)

**Task 도구는 복잡한 작업 시 선택적으로 사용:**

| Agent | 용도 | 도구 | 언제 사용 |
|-------|------|------|----------|
| general-purpose | 복잡한 멀티스텝 작업 | ALL 16 tools | 불확실한 탐색/자동화 |
| Explore | 코드베이스 탐색 | ALL 16 tools | 전체 구조 파악 필요 시 |
| Plan | 구현 계획 수립 | ALL 16 tools | 복잡한 기능 구현 전 |
| statusline-setup | 설정 파일 편집 | Read, Edit | 특정 설정만 |

**중요:**
- Task는 **선택적** - 단순 작업은 Main이 직접 처리
- Subagent는 **독립 실행** - 별도 컨텍스트, 결과만 Main에게 반환
- **Stateless** - 각 호출은 독립적

### 16개 도구

- **파일**: Read, Write, Edit, NotebookEdit
- **탐색**: Glob, Grep
- **실행**: Bash, BashOutput, KillShell
- **에이전트**: Task
- **관리**: TodoWrite, ExitPlanMode
- **외부**: WebSearch, WebFetch
- **기타**: Skill, SlashCommand

---

## 환경 설정

`.env`:

```bash
# v1, v2, v2.1: Anthropic API를 OpenAI SDK로 호출
OPENAI_API_KEY=sk-ant-api03-...
OPENAI_BASE_URL=https://api.anthropic.com/v1/

# v3: 실제 OpenAI API
OPENAI_API_KEY_V3=sk-proj-...

# v4: Claude Agent SDK
ANTHROPIC_API_KEY=sk-ant-api03-...
```

**권장 버전**: **v2.1** (단순하고 도구가 많음) 또는 **v4** (공식 SDK)

---

## 라이선스

교육 및 연구 목적. Claude Code는 Anthropic의 공식 제품이며, 이 문서는 비공식 분석입니다.
