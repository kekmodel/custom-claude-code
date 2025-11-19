# Custom Claude Code

> Claude Code 내부 아키텍처 분석 및 4가지 구현 방법 비교

## 개요

Claude Code의 내부 동작 원리를 분석하고, 동일한 기능을 4가지 방식으로 구현한 교육/연구 프로젝트입니다.

- 시스템 프롬프트 (약 3,000 토큰) + 도구 스키마 (약 14,000 토큰) = 총 약 17,000 토큰
- 16개 기본 도구 + 2개 MCP 도구 = 18개
- DAG 기반 워크플로우, 4가지 Subagent 타입
- 실제 API 요청/응답 캡처 및 시뮬레이션

---

## 빠른 시작

```bash
# 설치
uv sync

# 환경 변수 설정 (.env 파일 참고)
cp .env.example .env

# 실행
uv run python launcher.py                              # 대화형 런처
uv run python -m custom_claude_code.v1_openai.main     # v1
uv run python -m custom_claude_code.v2_langgraph.main  # v2
uv run python -m custom_claude_code.v3_openai_agents.main  # v3
uv run python -m custom_claude_code.v4_claude_agent.main   # v4
```

---

## 프로젝트 구조

```
custom-claude-code/
├── src/custom_claude_code/
│   ├── v1_openai/          # OpenAI API 직접 (1,966 lines)
│   ├── v2_langgraph/       # LangGraph StateGraph (2,376 lines)
│   ├── v3_openai_agents/   # OpenAI Agents SDK (516 lines)
│   ├── v4_claude_agent/    # Claude Agent SDK (311 lines)
│   └── common/
├── docs/                   # 아키텍처 문서 (한글)
│   ├── 01-architecture/
│   ├── 02-components/
│   ├── 03-interactions/
│   ├── 04-implementation/
│   └── 05-improvements/
├── reference/              # 실제 캡처 데이터
├── tests/                  # 테스트
├── launcher.py
└── CLAUDE.md
```

---

## 4가지 구현 비교

| 특징 | v1 | v2 | v3 | v4 |
|------|----|----|----|----|
| **LLM 지원** | OpenAI/Claude | OpenAI/Claude/Gemini | OpenAI | Claude |
| **핵심 패턴** | 수동 대화 루프 | StateGraph | Agent + Runner | ClaudeSDKClient |
| **Subagent** | 재귀 실행 | 독립 StateGraph | Agent.as_tool() | agents 파라미터 |
| **프롬프트** | 수동 | 수동 | 수동 | Preset |
| **MCP** | 수동 구현 | 수동 구현 | 미지원 | 네이티브 |

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

### DAG 구조

```
Main Agent
  → [Optional] Task(Explore)
  → [Optional] Task(Plan)
  → Action (Write/Edit)
  → Verify (Bash)
     ↓ 실패? → Fix → Re-verify
     ↓ 성공 → 완료
```

- 한 방향 흐름 (순환 없음)
- 조건부 재시도 (같은 단계만)
- 자동 Re-plan 없음

### Subagent 4가지 타입

| Agent | 용도 | 도구 |
|-------|------|------|
| general-purpose | 복잡한 멀티스텝 작업 | ALL 16 tools |
| Explore | 코드베이스 탐색 | Glob, Grep, Read |
| Plan | 구현 계획 수립 | Read, Grep, Glob, Bash |
| statusline-setup | 설정 파일 편집 | Read, Edit |

### 16개 도구

- **파일**: Read, Write, Edit, NotebookEdit
- **탐색**: Glob, Grep
- **실행**: Bash, BashOutput, KillShell
- **에이전트**: Task
- **관리**: TodoWrite, AskUserQuestion
- **외부**: WebSearch, WebFetch
- **기타**: ExitPlanMode, SlashCommand

---

## 환경 설정

`.env`:

```bash
# v1, v2: Anthropic API를 OpenAI SDK로 호출
OPENAI_API_KEY=sk-ant-api03-...
OPENAI_BASE_URL=https://api.anthropic.com/v1/

# v3: 실제 OpenAI API
OPENAI_API_KEY_V3=sk-proj-...

# v4: Claude Agent SDK
ANTHROPIC_API_KEY=sk-ant-api03-...
```

---

## 문서

- [시스템 개요](docs/01-architecture/system-overview.md)
- [기본 플로우](docs/03-interactions/basic-flow.md)
- [시스템 프롬프트](docs/02-components/system-prompt.md)
- [도구](docs/02-components/tools.md)
- [Subagent](docs/02-components/agents.md)

---

## 테스트

```bash
pytest tests/test_version_imports.py
pytest tests/test_v1_conversation.py
pytest tests/v2_improvements/
```

---

## 라이선스

교육 및 연구 목적. Claude Code는 Anthropic의 공식 제품이며, 이 문서는 비공식 분석입니다.

---

**생성**: 2025-11-15 | **업데이트**: 2025-11-19 | **분석 대상**: Claude Code (claude.ai/code)
