# Captured Claude Code Request Data

이 폴더는 **실제 Claude Code Router가 가로챈 요청 데이터**를 담고 있습니다.

## 📁 파일 구조

### 1. `request-*.json` - 요청 요약
전체 요청의 메타데이터와 통계 정보:

```json
{
  "timestamp": "2025-11-14T17:30:36.831Z",
  "model": "claude-sonnet-4",
  "hasThinking": true,
  "messagesCount": 1,
  "systemPromptBlocks": 2,
  "toolsCount": 3,
  "toolNames": ["Read", "Write", "Bash"],
  "metadata": {
    "user_id": "user_test123_session_xyz789"
  },
  "lastMessage": {
    "role": "user",
    "contentPreview": "이 프로젝트의 구조를 설명해줘"
  },
  "systemPromptLength": [1077, 547],
  "fullRequest": { ... }
}
```

**주요 정보**:
- 요청 시간
- 요청된 모델
- Thinking 모드 여부
- 메시지 개수
- 시스템 프롬프트 블록 수
- 도구 개수 및 이름
- 세션 정보

### 2. `system-prompt-*.txt` - 시스템 프롬프트
Claude Code가 사용하는 시스템 프롬프트 전문:

```
================================================================================
CLAUDE CODE SYSTEM PROMPT
================================================================================

================================================================================
Block 1
Type: text
Cache Control: {"type":"ephemeral"}
Length: 1077 characters
================================================================================

You are Claude Code, Anthropic's official CLI for Claude.
...

================================================================================
Block 2
Type: text
Cache Control: {"type":"ephemeral"}
Length: 547 characters
================================================================================

<env>
Working directory: /Users/jd/Documents/workspace/claude-code-router
...
</env>
```

**주요 내용**:
- Block 1: 핵심 정체성, 역할, 정책, 지침
- Block 2: 환경 정보, 모델 정보, 출력 스타일

**실제 Claude Code는 훨씬 더 긴 프롬프트 사용**:
- 약 50,000+ 토큰
- 16개 도구에 대한 상세 지침
- Task Management 시스템 설명
- Git 프로토콜
- PR 생성 프로토콜
- 등등...

### 3. `tools-*.json` - 도구 정의
사용 가능한 도구들의 JSON 스키마:

```json
{
  "count": 3,
  "tools": [
    {
      "name": "Read",
      "description": "Reads a file from the local filesystem...",
      "input_schema": {
        "type": "object",
        "properties": {
          "file_path": {
            "type": "string",
            "description": "The absolute path to the file to read"
          }
        },
        "required": ["file_path"]
      }
    },
    ...
  ]
}
```

**테스트에서는 3개**만 포함했지만, **실제 Claude Code는 16개**:
1. Task - 서브에이전트 실행
2. Read - 파일 읽기
3. Write - 파일 쓰기
4. Edit - 파일 편집
5. Bash - 셸 명령
6. Glob - 파일 검색
7. Grep - 코드 검색
8. TodoWrite - 작업 관리
9. AskUserQuestion - 질문
10. WebSearch - 웹 검색
11. WebFetch - URL 가져오기
12. NotebookEdit - Jupyter 편집
13. ExitPlanMode - Plan 모드 종료
14. SlashCommand - 커스텀 명령
15. Skill - 스킬 실행
16. BashOutput/KillShell - 셸 관리

### 4. `messages-*.json` - 메시지 히스토리
대화 내역:

```json
{
  "count": 1,
  "messages": [
    {
      "role": "user",
      "content": "이 프로젝트의 구조를 설명해줘"
    }
  ]
}
```

**실제 Claude Code에서는**:
- 이전 대화 히스토리 포함
- 도구 사용 (`tool_use`) 포함
- 도구 결과 (`tool_result`) 포함
- 복잡한 대화 흐름

## 🔍 데이터 분석

### 요청 구조

```
┌─────────────────────────────────────────────┐
│           Claude Code Request               │
├─────────────────────────────────────────────┤
│ model: "claude-sonnet-4"                    │
│ max_tokens: 8192                            │
│ thinking: { type: "enabled", budget: 10000 }│
├─────────────────────────────────────────────┤
│ messages: [                                 │
│   { role: "user", content: "..." }          │
│   { role: "assistant", content: [...] }     │
│   { role: "user", content: [tool_result] }  │
│ ]                                           │
├─────────────────────────────────────────────┤
│ system: [                                   │
│   Block 1: 핵심 지침 (cache_control)        │
│   Block 2: 환경 정보 (cache_control)        │
│ ]                                           │
├─────────────────────────────────────────────┤
│ tools: [                                    │
│   { name: "Read", ... },                    │
│   { name: "Write", ... },                   │
│   ...                                       │
│ ]                                           │
├─────────────────────────────────────────────┤
│ metadata: {                                 │
│   user_id: "user_xxx_session_yyy"          │
│ }                                           │
└─────────────────────────────────────────────┘
```

### 토큰 분포 (실제 Claude Code)

```
시스템 프롬프트:  ~50,000 토큰 (캐시됨)
도구 정의:        ~15,000 토큰 (캐시됨)
메시지 히스토리:   가변
───────────────────────────────────────
총 입력:          ~65,000+ 토큰

* Prompt Caching으로 75-90% 비용 절감
```

### Prompt Caching

시스템 프롬프트와 도구 정의에 `cache_control: {type: "ephemeral"}`이 적용되어 있습니다:

- **첫 요청**: 전체 비용 지불
- **이후 요청**: 캐시된 부분 75-90% 할인
- **효과**: Claude Code가 경제적으로 실행 가능

## 🎯 주요 발견사항

### 1. 매우 긴 시스템 프롬프트
- 약 50,000+ 토큰
- 각 도구마다 상세한 사용 지침
- 보안 정책, Git 프로토콜, PR 생성 등

### 2. 계층적 에이전트 시스템
- Task tool로 서브에이전트 실행
- Explore, Plan, general-purpose 등
- 각각 독립적인 대화 컨텍스트

### 3. Thinking Mode
- `thinking: {type: "enabled", budget_tokens: 10000}`
- 추론 과정을 노출
- Plan 모드 등에서 활용

### 4. 작업 관리 시스템
- TodoWrite tool로 진행 상황 추적
- pending/in_progress/completed 상태
- 한 번에 하나의 작업만 in_progress

### 5. 출력 스타일
- Explanatory: 교육적 인사이트 포함
- Concise: 간결한 응답
- Detailed: 상세한 설명

## 📊 실제 vs 테스트

| 항목 | 테스트 | 실제 Claude Code |
|------|--------|-----------------|
| 시스템 프롬프트 길이 | ~1,600자 | ~50,000+ 토큰 |
| 도구 개수 | 3개 | 16개 |
| 도구 지침 상세도 | 간단 | 매우 상세 (각 도구당 수백 줄) |
| Prompt Caching | O | O |
| Thinking Mode | O | O |
| Session Tracking | O | O |

## 🚀 라우터의 역할

라우터는 이 모든 정보를 **그대로 유지**하면서:

1. ✅ `model` 필드만 변경 (라우팅)
2. ✅ `messages`, `system`, `tools` 그대로 전달
3. ✅ Prompt Caching 효과 유지
4. ✅ 다른 LLM Provider API로 변환
5. ✅ 응답을 Anthropic 형식으로 재변환

### 투명한 프록시

```
Claude Code
    ↓
    ↓ 요청 (Anthropic 형식)
    ↓
[Router] ← model 필드만 변경
    ↓
    ↓ 변환 (Provider 형식)
    ↓
DeepSeek/Gemini/etc
    ↓
    ↓ 응답 (Provider 형식)
    ↓
[Router] ← Anthropic 형식으로 변환
    ↓
    ↓ 응답 (Anthropic 형식)
    ↓
Claude Code
```

## 📝 데이터 캡처 방법

이 데이터는 다음 코드로 자동 캡처되었습니다:

```typescript
// src/utils/router.ts에 추가된 디버깅 코드
const debugDir = path.join(os.homedir(), ".claude-code-router", "captured-requests");

// 4개 파일 자동 생성:
// 1. request-{timestamp}.json  - 요청 요약
// 2. system-prompt-{timestamp}.txt  - 시스템 프롬프트
// 3. tools-{timestamp}.json  - 도구 정의
// 4. messages-{timestamp}.json  - 메시지 히스토리
```

## 🔧 재현 방법

```bash
# 1. 프로젝트 빌드
npm run build

# 2. 라우터 시작
node dist/cli.js start

# 3. 테스트 요청 보내기
curl -X POST http://localhost:3456/v1/messages \
  -H "Content-Type: application/json" \
  -d @test-request.json

# 4. 캡처된 데이터 확인
ls -la ~/.claude-code-router/captured-requests/
```

## 🎓 학습 포인트

1. **프롬프트 엔지니어링**: 50,000+ 토큰의 초상세 지침
2. **경제성**: Prompt Caching 없이는 불가능한 구조
3. **아키텍처**: 계층적 에이전트 시스템
4. **도구 통합**: 16개 도구의 정교한 오케스트레이션
5. **프록시 패턴**: 투명한 중간 계층

---

**생성 시간**: 2025-11-14T17:30:36.830Z
**생성 방법**: Claude Code Router의 디버깅 기능
**목적**: Claude Code의 내부 구조 이해 및 분석
