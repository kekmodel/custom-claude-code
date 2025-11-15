# Version 1: OpenAI API 직접 사용 ✅ **COMPLETE**

Claude Code의 핵심 아키텍처를 OpenAI API로 완전 구현한 버전입니다.

## 구현 현황

- ✅ **16개 도구** - 모든 Claude Code 도구 구현 (Read, Write, Edit, Bash, Glob, Grep, TodoWrite, Task, ExitPlanMode, AskUserQuestion, NotebookEdit, BashOutput, KillShell, WebSearch, WebFetch, SlashCommand)
- ✅ **Subagent 시스템** - Task 도구를 통한 재귀적 에이전트 실행
- ✅ **스트리밍** - 실시간 응답 표시 (AsyncOpenAI)
- ✅ **클로드 코드 원본 프롬프트** - 동일한 구조의 시스템 프롬프트
- ✅ **Pydantic 타입 안전성** - 모든 도구 입력 검증
- ✅ **Rich UI** - 아름다운 터미널 인터페이스

## 핵심 개념

### 1. 대화 루프 (Conversation Loop) + 함수 분해 ⭐

**리팩토링됨!** 188줄 단일 함수 → 5개 독립 함수

**Before**: 188줄, 5단계 중첩
```python
async def run_conversation_loop():
    messages = []
    system_prompt = get_system_prompt(os.getcwd())

    while True:  # 1단계
        try:  # 2단계
            user_input = await prompt_session.prompt_async("\n> ")
            if user_input.lower() == "quit":
                ...

            while turn_count < max_turns:  # 3단계
                try:  # 4단계
                    ...
                    for tool_call in tool_calls:  # 5단계
                        # 도구 실행 로직 (70줄)
```

**After**: 5개 함수, 최대 2-3단계 중첩
```python
async def get_user_input() -> Optional[str]:
    """사용자 입력 + KeyboardInterrupt 처리 (19줄)"""
    try:
        return await prompt_session.prompt_async("\n> ")
    except (KeyboardInterrupt, EOFError):
        return None

async def handle_command(cmd: str, messages: List, system_prompt: str) -> bool:
    """명령어 처리: quit/clear/debug (26줄)"""
    if cmd == "quit": return False
    if cmd == "clear": messages.clear()
    ...

async def execute_single_tool_call(tool_call: Dict, system_prompt: str) -> Dict:
    """단일 도구 실행 - Task vs 일반 도구 (79줄)"""
    if tool_name == "Task":
        return await execute_subagent(...)  # 재귀!
    else:
        return await execute_tool(...)

async def process_turn_loop(messages: List, system_prompt: str, max_turns: int = 50):
    """도구 사용 내부 루프 (64줄)"""
    while turn_count < max_turns:
        assistant_message = await stream_assistant_response(...)
        if finish_reason == "tool_calls":
            tool_results = [await execute_single_tool_call(tc, sp) for tc in tool_calls]
            messages.extend(tool_results)
        elif finish_reason == "stop":
            break

async def run_conversation_loop():
    """메인 루프 - 극도로 간결! (38줄)"""
    messages = []
    system_prompt = get_system_prompt(os.getcwd())

    while True:
        user_input = await get_user_input()
        if user_input is None: break
        if not await handle_command(user_input, messages, system_prompt): continue
        messages.append({"role": "user", "content": user_input})
        await process_turn_loop(messages, system_prompt)
```

**개선 효과**:
- ✅ 중첩 깊이: 5단계 → 2-3단계 (-40%~-60%)
- ✅ 단일 책임: 각 함수가 하나의 역할만
- ✅ 가독성: 함수명이 곧 문서 (self-documenting)
- ✅ 재사용성: 독립 함수로 다른 컨텍스트에서도 사용 가능
- ✅ 테스트 가능: 개별 함수 단위 테스트 가능

### 2. finish_reason 처리

OpenAI API의 `finish_reason`은 Claude의 `stop_reason`과 동일한 역할:

- **`stop`**: 완료 - 사용자에게 응답 표시
- **`tool_calls`**: 도구 실행 필요 - 루프 계속
- **`length`**: 토큰 한계 초과 - 에러

### 3. Messages 구조 (append-only)

```python
messages = [
    {"role": "user", "content": "Fix bug in app.ts"},
    {"role": "assistant", "content": "I'll read the file first", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "file contents..."},
    {"role": "assistant", "content": "I found the issue. Editing now.", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "File edited successfully"},
    {"role": "assistant", "content": "Bug fixed! The issue was..."}
]
```

**중요**: messages는 절대 삭제하거나 수정하지 않음 (append-only)

### 4. 도구 시스템 (16개 도구) + 레지스트리 패턴 ⭐

#### 레지스트리 패턴 (리팩토링됨!)

**Before**: 96줄 if-elif 체인
```python
async def execute_tool(tool_name: str, tool_input: Dict) -> ToolResult:
    if tool_name == "Read":
        input_obj = ReadInput(**tool_input)
        result = await tool_read(input_obj)
        return ToolResult(...)
    elif tool_name == "Write":
        ...  # 14개 도구 반복
```

**After**: 30줄 레지스트리 패턴 (-69%)
```python
TOOL_REGISTRY = {
    "Read": (ReadInput, tool_read),
    "Write": (WriteInput, tool_write),
    "Edit": (EditInput, tool_edit),
    # ... 모든 도구
}

async def execute_tool(tool_name: str, tool_input: Dict) -> ToolResult:
    input_class, tool_func = TOOL_REGISTRY[tool_name]
    input_obj = input_class(**tool_input)
    result = await tool_func(input_obj)
    return ToolResult(tool_name=tool_name, result=result)
```

**효과**: 코드 중복 제거, 가독성 향상, 새 도구 추가 용이

#### 파일 조작 (4)
1. **Read**: 파일 읽기 (줄 번호 포함, offset/limit 지원)
2. **Write**: 파일 쓰기 (새 파일 생성 또는 덮어쓰기)
3. **Edit**: 파일 편집 (정확한 문자열 매칭, 고유성 검증)
4. **NotebookEdit**: Jupyter 노트북 셀 편집

#### 검색 (2)
5. **Glob**: 파일 패턴 검색 (`**/*.ts`, `src/**/*.py`)
6. **Grep**: 코드 검색 (regex, ripgrep 스타일)

#### 실행 (3)
7. **Bash**: 셸 명령 실행 (위험 명령어 차단, 타임아웃)
8. **BashOutput**: 백그라운드 셸 출력 조회
9. **KillShell**: 백그라운드 셸 종료

#### 에이전트 (1)
10. **Task**: Subagent 실행 (재귀적 에이전트, 4가지 타입)

#### 관리 (2)
11. **TodoWrite**: 작업 목록 관리 (pending/in_progress/completed)
12. **AskUserQuestion**: 사용자에게 질문 (다중 선택)

#### 외부 (2)
13. **WebSearch**: 웹 검색 (placeholder - OpenAI 미지원)
14. **WebFetch**: URL 콘텐츠 가져오기 (html2text)

#### 기타 (2)
15. **ExitPlanMode**: Plan 에이전트 종료
16. **SlashCommand**: 커스텀 명령어 실행

### 5. Subagent 시스템 (Task 도구)

Task 도구를 사용하면 독립적인 에이전트를 실행할 수 있습니다:

```python
# Main Agent
await execute_tool("Task", {
    "subagent_type": "Explore",
    "description": "Find all TypeScript files",
    "prompt": "Search the codebase for all *.ts files and summarize their purposes"
})

# → Subagent가 실행됨:
#    - 독립적인 messages 컨텍스트
#    - 같은 시스템 프롬프트 (캐싱!)
#    - 모든 도구 사용 가능
#    - Subagent도 Task 도구 사용 가능 (재귀!)
#    - 최종 리포트를 Main Agent에 반환
```

**4가지 Subagent 타입**:
- **general-purpose**: 복잡한 다단계 작업 (모든 도구 사용)
- **Explore**: 코드베이스 탐색 (빠른 검색, 파일 찾기)
- **Plan**: 구현 계획 수립 (ExitPlanMode로 종료)
- **statusline-setup**: 상태줄 설정 (Read, Edit만 허용)

**재귀 깊이 제한**: max_depth=5 (무한 루프 방지)

### 6. 시스템 프롬프트

OpenAI에게 도구 사용 방법을 가르치는 프롬프트 (~17KB, 410줄):

- **Environment** - 작업 디렉토리, git 상태, 플랫폼 정보
- **16개 도구 설명** - 각 도구의 사용 시점, 파라미터, 제약사항
- **Task Management** - TodoWrite 사용 패턴
- **Tool Usage Policy** - 도구 선택 기준 (Task vs Glob vs Grep)
- **Code References** - `file_path:line_number` 형식
- **Output Style** - "★ Insight" 교육 포맷
- **Workflow Patterns** - Bug Fix, Feature Implementation, Error Recovery
- **Safety Rules** - 파일 삭제 금지, 절대 경로 사용, Read before Edit
- **Git Protocol** - 커밋 메시지 형식, 안전 규칙

## 파일 구조

```
v1_openai/
├── types.py           # Pydantic 타입 모델 (150줄)
│   ├── ReadInput, WriteInput, EditInput, BashInput
│   ├── GlobInput, GrepInput, TaskInput
│   ├── TodoWriteInput, AskUserQuestionInput
│   ├── NotebookEditInput, WebSearchInput, WebFetchInput
│   ├── SubagentType, ModelType, TodoStatus
│   └── Message, ToolResult
│
├── tools.py           # 16개 도구 구현 (674줄) ⭐ 리팩토링됨!
│   ├── TOOLS - OpenAI function calling schema
│   ├── TOOL_REGISTRY - 레지스트리 패턴 (30줄, -69%)
│   ├── tool_read(), tool_write(), tool_edit()
│   ├── tool_bash(), tool_glob(), tool_grep()
│   ├── tool_todowrite(), tool_askuserquestion()
│   ├── tool_notebookedit(), tool_webfetch()
│   └── execute_tool() - 도구 디스패처 (레지스트리 기반)
│
├── subagent.py        # Subagent 실행 엔진 (230줄)
│   ├── execute_subagent() - 재귀적 에이전트 실행
│   ├── _filter_tools_by_agent_type() - 도구 필터링
│   └── get_subagent_info() - Subagent 정보
│
├── system_prompt.py   # 시스템 프롬프트 (410줄)
│   ├── get_system_prompt(working_dir) - 동적 프롬프트 생성
│   └── SYSTEM_PROMPT - 기본 프롬프트
│
├── main.py            # 메인 대화 루프 (427줄) ⭐ 리팩토링됨!
│   ├── stream_assistant_response() - 스트리밍 응답
│   ├── get_user_input() - 사용자 입력 처리 (19줄)
│   ├── handle_command() - 명령어 처리 (26줄)
│   ├── execute_single_tool_call() - 단일 도구 실행 (79줄)
│   ├── process_turn_loop() - 도구 사용 루프 (64줄)
│   ├── run_conversation_loop() - 메인 루프 (38줄, -80% 중첩)
│   └── main() - 진입점
│
└── README.md          # 이 문서
```

**총 코드**: ~1,891줄 (주석 제외)
**핵심 개선**: 레지스트리 패턴 (-66줄), 함수 분해 (중첩 -60%)

## 사용법

### 1. 환경 변수 설정

`.env` 파일 생성:

```bash
OPENAI_API_KEY=sk-...
```

### 2. 실행

```bash
cd /Users/jd/Documents/workspace/custom-claude-code
uv run python -m custom_claude_code.v1_openai.main
```

### 3. 예시 대화

```
Custom Claude Code - Version 1: OpenAI API

✨ Features:
  - 16 tools (Read, Write, Edit, Bash, Glob, Grep, etc.)
  - Subagent system (Task tool with recursive execution)
  - Streaming responses
  - Claude Code original system prompt

Commands:
  - Type 'quit' to exit
  - Type 'clear' to clear history
  - Type 'debug' to show message count

> Read the file src/app.ts