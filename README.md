# Custom Claude Code

> Claude Code 분석 및 교육용 재구현 프로젝트

---

## 📖 Claude Code 분석

Anthropic의 공식 AI 코딩 어시스턴트인 **Claude Code**의 내부 동작 원리를 분석한 내용입니다.

### 분석 결과 요약

**시스템 프롬프트 구조** (~3,000 토큰):
- 역할 정의 및 행동 지침
- 도구 사용 패턴 및 제약사항
- 코드 스타일 가이드
- Git/PR 작성 워크플로우

**도구 스키마** (~14,000 토큰):
- 16개 기본 도구 정의 (파일, 검색, 실행, 웹, 에이전트 등)
- 각 도구의 파라미터 및 설명
- MCP(Model Context Protocol)로 확장 가능

**16개 기본 도구**:

1. **파일 조작 (4개)**
   - `Read`: 파일 읽기 (라인 번호 포함, offset/limit 지원)
   - `Write`: 파일 쓰기 (기존 파일 덮어쓰기)
   - `Edit`: 파일 편집 (문자열 치환 방식)
   - `NotebookEdit`: Jupyter 노트북 셀 편집

2. **코드 검색 (2개)**
   - `Glob`: 파일 패턴 매칭 (예: `**/*.ts`)
   - `Grep`: 정규식 기반 코드 검색 (ripgrep 사용)

3. **명령 실행 (3개)**
   - `Bash`: 동기 bash 명령 실행
   - `BashOutput`: 백그라운드 프로세스 출력 읽기
   - `KillShell`: 백그라운드 프로세스 종료

4. **웹 접근 (2개)**
   - `WebSearch`: 웹 검색 (도메인 필터링 지원)
   - `WebFetch`: URL 컨텐츠 가져오기 및 분석

5. **에이전트 (1개)**
   - `Task`: 서브에이전트 실행 (복잡한 멀티스텝 작업 위임)
     - `general-purpose`: 범용 에이전트 (모든 도구 사용)
     - `Explore`: 코드베이스 탐색 전문 (파일 찾기, 검색)
     - `Plan`: 구현 계획 수립 전문 (읽기 전용)
     - `statusline-setup`: 설정 파일 편집 전문 (Read, Edit만)

6. **관리/UI (4개)**
   - `TodoWrite`: 작업 목록 관리
   - `ExitPlanMode`: 계획 모드 종료
   - `Skill`: 스킬 실행 (확장 기능)
   - `SlashCommand`: 커스텀 슬래시 명령 실행

**MCP 확장**:
- MCP(Model Context Protocol)를 통해 외부 도구 추가 가능
- 예: context7 (라이브러리 문서 검색), filesystem, database 등

**핵심 동작 패턴** - 대화 루프:

```
사용자 입력
  ↓
LLM 판단 (다음 행동 결정)
  ↓
  ├─→ [선택지] Task 호출 - 복잡한 멀티스텝 작업
  ├─→ [선택지] 도구 직접 사용 - 단순 작업
  └─→ [선택지] 사용자에게 응답 - 완료 시
  ↓
도구 실행 (가능하면 병렬)
  ↓
LLM이 tool_result 분석
  ↓
  ├─→ 성공? 다음 단계 또는 완료
  └─→ 실패? Read → Edit → 재실행 (LLM 판단)
  ↓
LLM이 완료 판단할 때까지 반복
```

**핵심 특징**:
- ✅ LLM이 상황에 맞게 도구 자유롭게 선택
- ✅ 실패 시 자동 복구 시도 (LLM 판단)
- ✅ 미리 정해진 워크플로우 없음 - 유연한 대화 기반

**참조 자료** (reference/ 폴더):
- 실제 API 요청/응답 캡처
- 시스템 프롬프트 원본
- 도구 스키마 원본

### 심층 아키텍처 분석 🆕

**Task subagent 외에 3가지 Agent 시스템 추가 발견!**

reference/ 폴더의 8개 캡처 파일을 분석한 결과, Claude Code는 다음과 같은 멀티 에이전트 시스템을 사용합니다:

1. **Main Agent**: 사용자 대화 및 작업 오케스트레이션
2. **Task Subagent (4타입)**: general-purpose, Explore, Plan, statusline-setup
3. **Validation Agent** 🆕: Bash 명령어 보안 검증 (command injection 탐지)
4. **File Path Extraction Agent** 🆕: Bash 출력에서 파일 경로 자동 추출

**핵심 메커니즘**:
- **Dynamic System Prompt Injection**: system[1] 블록을 동적으로 교체하여 Agent 역할 변경
- **Stateless Validation**: 검증 Agent는 대화 상태 없이 독립 실행 (병렬 처리 가능)
- **Prompt-based Tool Control**: 코드가 아닌 system prompt로 도구 접근 제어
- **Prompt Caching**: system[0] + system[1] 캐싱으로 ~90% 비용 절감

**Hook System 발견** 🆕:
- Python Agent SDK 분석 결과, Claude Code는 **Hook System**을 확장 메커니즘으로 사용
- **6개 Hook Events**: PreToolUse, PostToolUse, UserPromptSubmit, PreCompact, Stop, SubagentStop
- **Validation Agent = PreToolUse Hook** (Bash 명령어 보안 검증)
- **File Extraction Agent = PostToolUse Hook** (파일 경로 자동 추출)
- **can_use_tool API**: Hook System의 고수준 추상화 (권한 제어)

**상세 문서**:
- 📄 [CLAUDE_CODE_ARCHITECTURE_ANALYSIS.md](docs/CLAUDE_CODE_ARCHITECTURE_ANALYSIS.md) - 전체 분석 리포트 (영문)
- 📄 [ARCHITECTURE_VISUAL_SUMMARY.md](docs/ARCHITECTURE_VISUAL_SUMMARY.md) - 시각화 요약 (한글)
- 📄 [HOOK_SYSTEM_ANALYSIS.md](docs/HOOK_SYSTEM_ANALYSIS.md) - Hook System 분석 (한글)
- 📄 [HOOK_SYSTEM_FLOW_DIAGRAM.md](docs/HOOK_SYSTEM_FLOW_DIAGRAM.md) - Hook 제어 흐름도 (한글)

---

## 🎓 이 프로젝트 (교육용 구현)

위 분석을 바탕으로 **4가지 프레임워크**로 동일한 기능을 구현한 교육/연구 프로젝트입니다.

### 구현 내용

- **4가지 프레임워크**: OpenAI API, LangGraph (v2/v2.1/v2.2), OpenAI Agents SDK, Claude SDK
- **6개 구현 버전**: v1, v2, v2.1, v2.2 🆕, v3, v4
- **최대 16개 도구 지원** (v1 기준, 다른 버전은 11-13개):
  - **파일**: Read, Write, Edit, NotebookEdit (4)
  - **검색**: Glob, Grep (2)
  - **실행**: Bash, BashBackground, BashOutput, KillShell (4)
  - **웹**: WebSearch, WebFetch (2)
  - **에이전트**: Task (1)
  - **관리**: TodoWrite, ExitPlanMode, Skill, SlashCommand (4)
- **4가지 Subagent 타입**: general-purpose, Explore, Plan, statusline-setup
- **Hook System** 🆕 (v2.2): PreToolUse, PostToolUse, UserPromptSubmit, PreCompact, Stop, SubagentStop
- **Stateless Agents** 🆕 (v2.2): Validation Agent (보안), File Extraction Agent (파일 경로)
- **대화 루프 패턴**: LLM 판단 → 도구 실행 → 결과 분석 → 반복

---

## 빠른 시작

```bash
# 설치
uv sync

# 환경 변수 설정 (.env 파일 참고)
cp .env.example .env

# 실행
uv run python launcher.py                                          # 대화형 런처
uv run python -m custom_claude_code.v1_openai.main                 # v1: OpenAI API
uv run python -m custom_claude_code.v2_langgraph.main              # v2: LangGraph
uv run python -m custom_claude_code.v2_1_langgraph_improved.main   # v2.1: 개선 ⭐ 권장
uv run python -m custom_claude_code.v2_2_langgraph_hooks.main      # v2.2: Hook 실험
uv run python -m custom_claude_code.v3_openai_agents.main          # v3: OpenAI Agents SDK
uv run python -m custom_claude_code.v4_claude_agent.main           # v4: Claude SDK
```

---

## 프로젝트 구조

```
custom-claude-code/
├── src/custom_claude_code/          # 메인 패키지
│   ├── __init__.py
│   ├── v1_openai/                   # v1: OpenAI API 직접 사용
│   ├── v2_langgraph/                # v2: LangGraph StateGraph
│   ├── v2_1_langgraph_improved/     # v2.1: 개선된 버전 ⭐ 권장
│   ├── v2_2_langgraph_hooks/        # v2.2: Hook 시스템 (실험)
│   ├── v3_openai_agents/            # v3: OpenAI Agents SDK
│   ├── v4_claude_agent/             # v4: Claude Agent SDK
│   └── common/                       # 공통 유틸리티/설정
│
├── docs/                             # 문서
│   ├── CLAUDE_CODE_ARCHITECTURE_ANALYSIS.md   # 분석 리포트
│   ├── ARCHITECTURE_VISUAL_SUMMARY.md         # 시각화
│   ├── HOOK_SYSTEM_ANALYSIS.md
│   ├── HOOK_SYSTEM_FLOW_DIAGRAM.md
│   └── improvements/                 # 개선사항 기록
│
├── tests/                            # 테스트 코드
│   ├── v2_improvements/
│   └── README.md
│
├── reference/                        # 참조 데이터 (실제 API 캡처)
│   └── examples/
│
├── data/                             # 프로젝트 데이터
│
├── .env.example                      # 환경 변수 템플릿
├── pyproject.toml                    # 패키지 설정
├── launcher.py                       # 대화형 런처
├── CLAUDE.md                         # Claude Code 지침
└── README.md                         # 이 파일
```

---

## 6가지 구현 비교

| 특징 | v1 | v2 | v2.1 ⭐ | v2.2 🔬 | v3 | v4 |
|------|----|----|---------|---------|----|----|
| **코드량** | ~1,966줄 | ~2,376줄 | ~585줄 | ~1,400줄 | ~516줄 | ~311줄 |
| **LLM 지원** | OpenAI/Claude | OpenAI/Claude/Gemini | OpenAI/Claude/Gemini | OpenAI/Claude/Gemini | OpenAI | Claude |
| **핵심 패턴** | 수동 대화 루프 | StateGraph + 압축 | StateGraph 단순화 | Hook System | Agent + Runner | ClaudeSDKClient |
| **도구 개수** | 16개 | 9개 | 13개 | 13개 | 11개 | 11개 (6+5) |
| **Subagent** | 재귀 실행 | 독립 StateGraph | Tag 필터링 | Tag 필터링 | Agent.as_tool() | agents 파라미터 |
| **Hook Events** | ❌ | ❌ | ❌ | ✅ 6개 | ❌ | ✅ (SDK) |
| **Stateless Agents** | ❌ | ❌ | ❌ | ✅ 2개 | ❌ | ✅ (SDK) |
| **보안 검증** | ❌ | ❌ | ❌ | ✅ Validation | ❌ | ✅ (can_use_tool) |
| **메시지 압축** | 없음 | 100k 토큰 자동 | 없음 (단순화) | 없음 | 없음 | 없음 |
| **웹 접근** | ✅ | ❌ | ✅ (신규) | ✅ | ✅ (신규) | ✅ (신규) |
| **용도** | 학습 | 프로덕션 | 권장 | 연구 | 프로토타입 | 공식 SDK |

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
- **v2.2**: Hook System 구현 (PreToolUse/PostToolUse, Validation/File Extraction Agents)

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

### v2.2: LangGraph with Hook System (NEW - 2025-11-20)

**파일**:
- main.py, graph.py, nodes.py, tools.py, prompts.py, models.py, config.py
- hooks.py (342줄), validation_agent.py (245줄), file_extraction_agent.py (195줄)
- permission.py (119줄), settings.py (107줄)
- README.md (650+줄 상세 문서), test_v2.2_hooks.py (250+줄 테스트)

**주요 특징 - Hook System 구현**:

1. **6가지 Hook Events**:
   - `PreToolUse`: 도구 실행 전 검증/수정 (Validation Agent)
   - `PostToolUse`: 도구 실행 후 처리 (File Extraction Agent)
   - `UserPromptSubmit`: 사용자 입력 전처리
   - `PreCompact`: 메시지 압축 전처리
   - `Stop`: 대화 종료 시
   - `SubagentStop`: Subagent 종료 시

2. **Stateless Agents 구현**:
   - **Validation Agent**: Bash 명령어 보안 검증 (command injection 탐지)
     - 별도 LLM 호출로 명령어 prefix 추출
     - Allowlist 기반 허용/차단/승인 요청
   - **File Extraction Agent**: Bash 출력에서 파일 경로 자동 추출
     - 별도 LLM 호출로 파일 경로 파싱
     - `is_displaying_contents`, `filepaths` 반환

3. **Permission System (can_use_tool API)**:
   - Hook System의 고수준 추상화
   - deny/ask/allow 동작 지원
   - 입력 수정 (updatedInput) 기능

4. **Settings Loader**:
   - CLAUDE.md 자동 로드 (프로젝트 지침)
   - Setting Sources: user/project/local
   - system-reminder 형태로 컨텍스트 주입

5. **Hook Matcher**:
   - 정규식 기반 도구 필터링
   - 다중 Hook 체인 실행
   - Decision Chain: block → ask → allow

**v2.1과의 차이**:
- v2.1: 단순한 대화 루프 (압축 제거, 13개 도구)
- v2.2: Hook System 추가 (보안 검증, 파일 추출, 권한 제어)

**상태**: 🔬 연구/교육용 (Claude Code의 Hook System 재구현)

**실행**:
```bash
uv run python -m custom_claude_code.v2_2_langgraph_hooks.main
uv run python test_v2.2_hooks.py  # Hook System 테스트
```

**문서**:
- [Hook System README](src/custom_claude_code/v2_2_langgraph_hooks/README.md)
- [Hook System Flow Diagram](docs/HOOK_SYSTEM_FLOW_DIAGRAM.md)
- [Hook System Analysis](docs/HOOK_SYSTEM_ANALYSIS.md)

### v3: OpenAI Agents SDK

**파일**:
- main.py (286줄), tools.py (500줄)

**특징**:
- Agent.as_tool()로 Subagent 변환
- SQLiteSession 자동 히스토리
- @function_tool 데코레이터
- 11개 도구 (v2.1과 동일한 기능)

### v4: Claude Agent SDK

**파일**:
- main.py (228줄), config.py (120줄), tools.py (360줄)

**특징**:
- Subagent = 설정 (agents 파라미터)
- System Prompt Preset (claude_code)
- MCP 네이티브, Hook 시스템
- Anthropic 공식 SDK
- 11개 도구 (6 SDK 기본 + 5 커스텀 MCP 도구)

---

## 구현 상세

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
