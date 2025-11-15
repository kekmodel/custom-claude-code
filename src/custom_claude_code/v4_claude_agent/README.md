# Version 4: Claude Agent SDK를 활용한 구현 ✅ **COMPLETE**

Anthropic의 공식 **Claude Agent SDK**를 활용하여 Claude Code를 구현한 버전입니다.

## Claude Agent SDK란?

Anthropic이 **2025년 공개한 공식 Agent 프레임워크**입니다.
Claude Code의 빌딩 블록을 Python/TypeScript SDK로 제공합니다.

### 핵심 개념

1. **query() - One-shot 쿼리**
   ```python
   from claude_agent_sdk import query, ClaudeAgentOptions

   async for message in query(prompt="What is 2+2?"):
       print(message)
   ```

2. **ClaudeSDKClient - Interactive 대화**
   ```python
   from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

   async with ClaudeSDKClient(options=options) as client:
       await client.query("What's the capital of France?")
       async for msg in client.receive_response():
           print(msg)
   ```

3. **ClaudeAgentOptions - 설정**
   ```python
   options = ClaudeAgentOptions(
       allowed_tools=["Read", "Write", "Bash", "Edit", "Glob", "Grep"],
       permission_mode="acceptEdits",
       system_prompt={"type": "preset", "preset": "claude_code"},
       agents={  # Subagent 정의!
           "reviewer": {
               "description": "Code reviewer",
               "prompt": "Review code for issues",
               "tools": ["Read", "Grep"],
               "model": "sonnet"
           }
       }
   )
   ```

4. **Custom Tools with @tool**
   ```python
   from claude_agent_sdk import tool, create_sdk_mcp_server

   @tool("greet", "Greet a user", {"name": str})
   async def greet_user(args):
       return {"content": [{"type": "text", "text": f"Hello, {args['name']}!"}]}

   server = create_sdk_mcp_server(name="my-tools", tools=[greet_user])
   options = ClaudeAgentOptions(
       mcp_servers={"tools": server},
       allowed_tools=["mcp__tools__greet"]
   )
   ```

5. **Hooks - 검증 및 피드백**
   ```python
   async def check_bash(input_data, tool_use_id, context):
       if "rm -rf" in input_data["tool_input"].get("command", ""):
           return {
               "hookSpecificOutput": {
                   "permissionDecision": "deny",
                   "permissionDecisionReason": "Dangerous command blocked"
               }
           }
       return {}

   options = ClaudeAgentOptions(
       hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[check_bash])]}
   )
   ```

## v1, v2, v3과의 차이점

### v1: OpenAI API 직접 사용
```python
while True:
    response = openai.chat.completions.create(...)
    if finish_reason == "tool_calls":
        # 도구 실행 로직 직접 구현
```

### v2: LangGraph 상태 머신
```python
graph = StateGraph(...)
graph.add_node("agent", call_agent)
graph.add_node("tools", execute_tools)
app = graph.compile()
```

### v3: OpenAI Agents SDK
```python
agent = Agent(name="assistant", tools=[read, write])
result = await Runner.run(agent, input=user_input)
```

### v4: Claude Agent SDK (최고 수준 추상화!)
```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    system_prompt={"type": "preset", "preset": "claude_code"},
    agents={  # Subagent가 파라미터로!
        "explore": {"description": "...", "prompt": "...", "tools": ["Glob", "Grep"]}
    }
)

async with ClaudeSDKClient(options=options) as client:
    await client.query(user_input)
    async for msg in client.receive_response():
        print(msg)
```

**v4의 장점**:
- ✅ **Subagent = 파라미터**: 코드 불필요, `agents` 파라미터로 정의!
- ✅ **System Prompt Preset**: `{"type": "preset", "preset": "claude_code"}`
- ✅ **내장 도구**: Read, Write, Edit, Bash, Glob, Grep 모두 SDK에!
- ✅ **MCP 네이티브 지원**: In-process MCP servers
- ✅ **Hook 시스템**: PreToolUse, PostToolUse로 검증/피드백
- ✅ **비용 추적**: ResultMessage에 자동 포함
- ✅ **Anthropic 공식**: Claude Code와 동일한 SDK

**v4의 단점**:
- ⚠️ **Claude만 지원**: OpenAI, Gemini 등 불가
- ⚠️ **최신 SDK**: 2025년 출시, 아직 안정화 진행 중

## 구현 현황

- ✅ **main.py** - ClaudeSDKClient + agents 파라미터 (208줄, 극도로 간결!)
- ✅ **config.py** - Subagent 설정 분리 (94줄) ⭐ 리팩토링됨!
- ✅ **4개 Subagent** - explore, plan, general, statusline (agents 파라미터로!)
- ✅ **System Prompt** - claude_code preset 사용
- ✅ **6개 도구** - Read, Write, Edit, Bash, Glob, Grep (모두 내장!)
- ✅ **Rich UI** - Panel, Markdown으로 예쁜 터미널 인터페이스
- ✅ **비용 추적** - ResultMessage로 자동 추적
- ✅ **README.md** - 완전한 문서

**총 코드**: ~302줄 (설정 분리), **핵심 로직 ~50줄!**

## ⭐ Subagent 시스템 (v4의 핵심!)

v4는 **`agents` 파라미터**로 Subagent를 정의합니다!

### 작동 원리 ⭐ 리팩토링됨!

**Before**: main.py에 72줄 inline 설정
```python
# main.py (Before)
SUBAGENTS = {
    "explore": {
        "description": "Explore the codebase",
        "prompt": "You are an Explore agent...",
        "tools": ["Glob", "Grep", "Read"],
        "model": "sonnet"
    },
    # ... 3개 더 (72줄)
}

options = ClaudeAgentOptions(agents=SUBAGENTS, ...)
```

**After**: config.py로 분리 (-72줄)
```python
# config.py (After)
EXPLORE_AGENT = {
    "description": "Explore the codebase",
    "prompt": "You are an Explore agent...",
    "tools": ["Glob", "Grep", "Read"],
    "model": "sonnet"
}
# ... PLAN_AGENT, GENERAL_AGENT, STATUSLINE_AGENT ...

SUBAGENTS: Dict[str, Any] = {
    "explore": EXPLORE_AGENT,
    "plan": PLAN_AGENT,
    "general": GENERAL_AGENT,
    "statusline": STATUSLINE_AGENT,
}

# main.py (After)
from .config import SUBAGENTS  # 깔끔!

options = ClaudeAgentOptions(
    agents=SUBAGENTS,  # 이게 전부!
    # ...
)
```

**SDK가 자동으로**:
1. 각 Subagent를 도구로 변환
2. Main agent가 필요 시 Subagent 호출
3. Subagent 실행 관리 (깊이 제한, 권한 등)

### 4개 Subagent

1. **explore** - 코드베이스 탐색
   - 도구: Glob, Grep, Read
   - 용도: 파일 찾기, 코드 검색, 구조 분석

2. **plan** - 계획 수립
   - 도구: Glob, Grep, Read
   - 용도: 작업 분해, 구현 방법 제안

3. **general** - 일반 작업
   - 도구: 모든 도구
   - 용도: 복잡한 다단계 작업 자율 실행

4. **statusline** - 설정 파일 편집
   - 도구: Read, Edit만
   - 용도: Claude Code 상태 표시줄 설정

### v1/v2/v3 vs v4 Subagent 비교

| 특징 | v1 | v2 | v3 | v4 |
|------|----|----|----|----|
| 구현 방법 | 재귀 함수 | 독립 StateGraph | Agent.as_tool() | **agents 파라미터** |
| 코드 복잡도 | 높음 | 중간 | 낮음 | **최저 (설정만!)** |
| 도구 필터링 | 수동 | 수동 | 자동 | **자동** |
| 중첩 제한 | 수동 | 수동 | SDK 관리 | **SDK 관리** |
| 코드량 | ~230줄 | ~100줄 | ~150줄 | **~50줄 (설정!)** |

**v4의 혁명**: Subagent가 **코드가 아니라 설정**입니다!

## 파일 구조 ⭐ 리팩토링됨!

```
v4_claude_agent/
├── __init__.py          # 패키지 초기화
├── config.py            # Subagent 설정 (94줄) - 분리됨!
│   ├── EXPLORE_AGENT - 코드베이스 탐색
│   ├── PLAN_AGENT - 계획 수립
│   ├── GENERAL_AGENT - 일반 작업
│   ├── STATUSLINE_AGENT - 설정 편집
│   └── SUBAGENTS - 통합 딕셔너리
│
├── main.py              # 메인 실행 (208줄) - 간소화됨!
│   └── ClaudeSDKClient + agents parameter
│
└── README.md            # 이 문서
```

**개선 효과**:
- ✅ 관심사 분리: 설정 vs 로직
- ✅ 가독성 향상: main.py가 더 간결함
- ✅ 유지보수 용이: SUBAGENTS 수정이 쉬움

## 사용법

```bash
cd /Users/jd/Documents/workspace/custom-claude-code
uv run python -m custom_claude_code.v4_claude_agent.main
```

## Claude Agent SDK의 고급 기능

### 1. System Prompt Preset

```python
# Claude Code의 공식 프롬프트 사용!
options = ClaudeAgentOptions(
    system_prompt={"type": "preset", "preset": "claude_code"}
)

# 또는 추가 지침
options = ClaudeAgentOptions(
    system_prompt={
        "type": "preset",
        "preset": "claude_code",
        "append": "You are a Python expert."
    }
)
```

### 2. MCP 서버 통합

```python
# In-process SDK MCP server
calculator = create_sdk_mcp_server(
    name="calc",
    tools=[add_numbers, multiply_numbers]
)

# External stdio MCP server
options = ClaudeAgentOptions(
    mcp_servers={
        "calc": calculator,  # In-process
        "external": {  # External
            "type": "stdio",
            "command": "python",
            "args": ["-m", "external_server"]
        }
    }
)
```

### 3. Hook 시스템

```python
# PreToolUse: 도구 실행 전 검증
async def validate_bash(input_data, tool_use_id, context):
    command = input_data["tool_input"].get("command", "")
    if "rm -rf" in command:
        return {
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": "Dangerous command"
            }
        }
    return {}

# PostToolUse: 도구 실행 후 피드백
async def review_output(input_data, tool_use_id, context):
    if "error" in str(input_data.get("tool_response", "")).lower():
        return {
            "systemMessage": "⚠️ The command produced an error",
            "additionalContext": "Consider a different approach."
        }
    return {}

options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [HookMatcher(matcher="Bash", hooks=[validate_bash])],
        "PostToolUse": [HookMatcher(matcher=None, hooks=[review_output])]
    }
)
```

### 4. 권한 콜백

```python
async def can_use_tool(tool_name: str, tool_input: dict, context):
    # 중요 파일 쓰기 차단
    if tool_name == "Write":
        if "config" in tool_input.get("file_path", "").lower():
            return PermissionResultDeny(
                behavior="deny",
                message="Cannot write to config files"
            )

    # Bash 명령 수정
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if command.startswith("rm"):
            modified_input = {**tool_input, "command": f"{command} -i"}
            return PermissionResultAllow(
                behavior="allow",
                updated_input=modified_input
            )

    return PermissionResultAllow(behavior="allow")

options = ClaudeAgentOptions(can_use_tool=can_use_tool)
```

## 언제 사용하나?

- **Claude 모델 사용**: Claude Sonnet 4.5, Opus 등
- **MCP 활용**: Custom MCP 서버 또는 In-process MCP 도구
- **최소 코드**: 설정 기반으로 agent 구축
- **공식 SDK**: Anthropic의 공식 프레임워크

## v1 vs v2 vs v3 vs v4 완전 비교

| 특징 | v1: OpenAI | v2: LangGraph | v3: OpenAI Agents | v4: Claude Agent |
|------|-----------|---------------|-------------------|------------------|
| LLM | OpenAI | Any | OpenAI | **Claude** |
| 코드 길이 | ~1,915줄 | ~450줄 | ~280줄 | **~280줄** |
| 핵심 로직 | ~400줄 | ~200줄 | ~130줄 | **~50줄** |
| Subagent | 재귀 함수 | StateGraph | Agent.as_tool() | **agents 파라미터** |
| 추상화 수준 | 낮음 | 중간 | 높음 | **최고** |
| 커스터마이징 | 완전 자유 | 높음 | 제한적 | 중간 |
| MCP 지원 | 수동 구현 | 가능 | ✗ | **네이티브 ✓** |
| System Prompt | 수동 | 수동 | 수동 | **Preset!** |
| Hook 시스템 | 수동 | 가능 | ✗ | **내장 ✓** |
| 비용 추적 | 수동 | 수동 | 수동 | **자동 ✓** |
| Claude Code 호환 | ✗ | ✗ | ✗ | **✓ (공식!)** |

## 참고 자료

- [Claude Agent SDK Python - GitHub](https://github.com/anthropics/claude-agent-sdk-python)
- [Claude Agent SDK - Official Docs](https://docs.claude.com/en/docs/agent-sdk/overview)
- [Building AI Systems That Take Action - Tutorial](https://www.datacamp.com/tutorial/openai-agents-sdk-tutorial)
