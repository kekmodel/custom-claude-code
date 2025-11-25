# Technical Documentation Korean Translation Rules

기술 문서의 한국어 번역 시 적용하는 규칙입니다.

## 번역하지 않는 항목

### 1. 코드 및 마크업 요소
- XML/HTML 태그: `<example>`, `<env>`, `<system-reminder>`
- 코드 블록 내용 (```로 감싸진 부분)
- 마크다운 서식: `#`, `**`, `-`, `>`

### 2. 참조 경로
- URL: `https://github.com/...`
- 파일 경로: `/Users/username/project/src/index.ts`
- 패키지명: `npm install`, `pip install`

### 3. 헤드라인 키워드 (독립된 대문자 강조)
```
IMPORTANT:
CRITICAL:
REMEMBER:
VERY IMPORTANT:
Notes:
Usage notes:
Important notes:
```

### 4. 섹션 제목
```
# Task Management
## When to Use This Tool
### Examples
```

### 5. 기술 용어
- 도구명: Bash, Glob, Grep, Read, Write, Edit
- 프로그래밍 용어: regex, git, API, CLI, JSON
- 모델명: Claude, Opus, Sonnet, Haiku

## 대문자 강조 처리 규칙

### 헤드라인 (번역 X)
독립된 줄이나 섹션 제목으로 사용된 경우 영어 유지:

```markdown
=== CRITICAL: READ-ONLY MODE ===
IMPORTANT: Always use...
```

### 본문 내 강조 (번역 O)
문장 안에서 강조 용도로 사용된 경우 한국어 + `**` 강조:

```markdown
English: This is STRICTLY PROHIBITED in all cases.
Korean: 이것은 모든 경우에 **엄격히 금지**됩니다.
```

## 문장 구조 규칙

### 어색한 혼합 피하기
```
❌ You are Claude Code, Anthropic의 공식 CLI입니다.
✅ 당신은 Anthropic의 공식 CLI인 Claude Code입니다.
```

### 자연스러운 어순 유지
영어 문장 구조를 그대로 따르지 않고 한국어 어순에 맞게 재구성합니다.

## 문서 형식 유지

### 구조 보존
- 원본의 마크다운 계층 구조 (`#`, `##`, `###`) 유지
- 목록 형식 (번호, 불릿) 동일하게 유지
- 코드 블록, 테이블, 인용문 형식 그대로 유지
- 줄바꿈과 문단 구분 유지

### 서식 요소 보존
```markdown
원본: - **Step 1**: Do something
번역: - **Step 1**: 무언가를 수행하세요
```

## 톤앤매너 유지

### 지시문 스타일
원본이 명령형이면 번역도 명령형 유지:
```
원본: Use the Read tool first.
번역: 먼저 Read 도구를 사용하세요.
```

### 경고/주의 톤
원본의 강도를 유지:
```
원본: NEVER do this.
번역: **절대** 이렇게 하지 마세요.

원본: Avoid doing this.
번역: 이렇게 하는 것을 피하세요.
```

### 설명문 스타일
원본이 설명조면 번역도 설명조 유지:
```
원본: This tool allows you to...
번역: 이 도구를 사용하면 ...할 수 있습니다.
```

### 일관성
- 동일 용어는 문서 전체에서 동일하게 번역
- 존칭 사용 일관성 유지 (예: "~하세요" 또는 "~합니다")

## 예시

| 원문 | 번역 |
|------|------|
| `IMPORTANT: Do not...` | `IMPORTANT: ...하지 마세요.` |
| `This is CRITICAL for...` | `이것은 ...에 **매우 중요**합니다.` |
| `# Git Safety Protocol` | `# Git Safety Protocol` |
| `Use the Read tool` | `Read 도구를 사용하세요` |
