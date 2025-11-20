# Translation Rules (번역 규칙)

System prompt 영어 원문을 한국어로 번역할 때 적용하는 규칙입니다.

## 1. 기본 원칙

- 영어 원문을 한국어로 번역
- 존댓말 사용 (~하세요, ~합니다)
- 기술 문서 스타일 유지
- 명확하고 정확한 번역

## 2. 유지되는 부분

- **XML 태그**: `<example>`, `<system-reminder>`, `<env>`, `<policy_spec>` 등 모든 태그
- **코드 블록**: 백틱으로 감싼 코드 및 명령어
- **URL**: 모든 링크 주소
- **파일 경로**: 절대/상대 경로
- **마크다운 포맷팅**: `**`, `-`, `#`, 백틱 등
- **영어 키워드**: `user:`, `assistant:`, `IMPORTANT:`, `CRITICAL:` 등

## 3. 기술 용어 처리

### 그대로 유지
- CLI, API, URL, SDK, JSON, XML
- CTF, DoS, XSS, SQL injection, OWASP
- Git, Bash, Python, npm 등 명령어/언어명
- Model ID: `claude-sonnet-4-5-20250929`

### 영어 유지 (기술 용어)
- tool, hook, agent
- task, todo
- file, code, codebase
- read-only, command, prefix
- input, output, prompt
- message, content, context

### 한글화 (일반 용어)
- user → 사용자
- error → 오류
- example → 예제 (문맥에 따라)
- note → 참고 (문맥에 따라)

### 맥락에 따라
- "exploration" → "탐색" 또는 exploration
- "search" → "검색" 또는 search
- "security" → "보안" 또는 security

## 4. 번역 예시

### 기본 문장
- "You are Claude Code" → "당신은 Claude Code입니다"
- "You are a Claude agent, built on Anthropic's Claude Agent SDK" → "당신은 Anthropic의 Claude Agent SDK로 구축된 Claude 에이전트입니다"
- "interactive CLI tool" → "대화형 CLI 도구"
- "software engineering tasks" → "소프트웨어 엔지니어링 작업"

### 지시문
- "Use this tool" → "이 도구를 사용하세요"
- "You must follow" → "~을 따라야 합니다"
- "Do not create files" → "파일을 생성하지 마세요"
- "NEVER use" → "**절대** 사용하지 마세요"

### 강조 표현
- "IMPORTANT:" → "IMPORTANT:" (유지)
- "CRITICAL:" → "CRITICAL:" (유지)
- "VERY frequently" → "**매우** 자주"
- "EXTREMELY helpful" → "**극도로** 유용합니다"
- "NEVER" → "**절대**"
- "MUST NOT" → "~해서는 **절대** 안 됩니다"
- "under any circumstances" → "어떤 상황에서도"

## 5. 예제 (example) 태그 처리

- `<example>` 태그 자체는 유지
- `user:` → `user:` (유지)
- `assistant:` → `assistant:` (유지)
- 대화 내용은 번역하되, 코드는 유지

```xml
<example>
user: Run the build and fix any type errors
assistant: I'm going to use the TodoWrite tool...
</example>
```

→ 예제 설명 부분만 번역, user/assistant 레이블과 코드는 유지

## 6. 환경 정보 처리

```xml
<env>
Working directory: /Users/jd/Documents/workspace/...
Is directory a git repo: Yes
Platform: darwin
OS Version: Darwin 25.1.0
Today's date: 2025-11-20
</env>
```

→ 태그와 내용 모두 그대로 유지 (번역하지 않음)

## 7. 특수 케이스

### Git Status
```
Status:
M package.json
 M src/index.ts
?? captured_request.json
```
→ 그대로 유지

### 코드 스니펫 내 주석
영어 주석도 일반적으로 유지하지만, 예제 설명이 한국어로 되어 있으면 자연스럽게 조정

### URL 및 경로
- `https://github.com/...` → 유지
- `/Users/jd/...` → 유지
- `src/services/process.ts:712` → 유지

## 8. 문체 가이드

### 존댓말 형태
- "~하세요" (지시)
- "~합니다" (설명)
- "~해야 합니다" (의무)
- "~할 수 있습니다" (가능)

### 부정 표현
- "don't" → "~하지 마세요"
- "must not" → "~해서는 안 됩니다"
- "never" → "절대 ~하지 마세요"
- "avoid" → "~을 피하세요"

### 긍정 표현
- "should" → "~해야 합니다"
- "must" → "반드시 ~해야 합니다"
- "ensure" → "~을 보장하세요" / "~을 확인하세요"
- "make sure" → "~을 확인하세요"

## 9. 품질 체크리스트

번역 완료 후 확인사항:
- [ ] 모든 XML 태그가 그대로 유지되었는가?
- [ ] 코드 블록과 명령어가 변경되지 않았는가?
- [ ] URL과 파일 경로가 그대로인가?
- [ ] 기술 용어가 일관되게 처리되었는가?
- [ ] 존댓말 형태가 일관되는가?
- [ ] 강조 표현(**굵게**)이 적절히 사용되었는가?
- [ ] 마크다운 포맷팅이 깨지지 않았는가?

## 10. 예외 사항

다음의 경우 번역하지 않음:
- 모델 ID 및 기술 식별자
- Git 명령어 및 출력
- 환경 변수명
- 함수명 및 변수명
- 에러 메시지 (원문 유지)
- 로그 출력
