# v2 멀티 모델 지원

v2는 Anthropic, OpenAI, Gemini를 모두 지원합니다.

## 빠른 시작

### 1. 환경 변수 설정 (.env)

```bash
# 기본 provider 선택
V2_PROVIDER=anthropic  # 또는 openai, gemini

# 특정 모델 지정 (선택사항)
V2_MODEL=claude-sonnet-4-5-20250929

# API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

# 기타 설정
V2_TEMPERATURE=1.0
V2_THINKING_BUDGET=2048
```

### 2. 실행

```bash
# .env 설정대로 실행
uv run python -m custom_claude_code.v2_langgraph.main

# 또는 환경 변수로 오버라이드
V2_PROVIDER=openai V2_MODEL=gpt-4o uv run python -m custom_claude_code.v2_langgraph.main
```

## 지원 모델

### Anthropic (Extended Thinking ✅)

```bash
V2_PROVIDER=anthropic
V2_MODEL=claude-haiku-4-5        # 기본값, 빠르고 저렴
V2_MODEL=claude-sonnet-4-5-20250929  # 균형잡힌 성능
V2_MODEL=claude-opus-4-20250514  # 최고 성능
```

**별칭**:
- `haiku` → claude-haiku-4-5
- `sonnet` → claude-sonnet-4-5-20250929
- `opus` → claude-opus-4-20250514

### OpenAI (Extended Thinking ❌)

```bash
V2_PROVIDER=openai
V2_MODEL=gpt-4o           # 기본값
V2_MODEL=gpt-4o-mini      # 저렴한 옵션
V2_MODEL=gpt-4-turbo
```

**별칭**:
- `gpt4o` → gpt-4o
- `gpt4o-mini` → gpt-4o-mini

**참고**: OpenAI를 Anthropic API로 사용하려면:
```bash
V2_PROVIDER=openai
OPENAI_BASE_URL=https://api.anthropic.com/v1/
OPENAI_API_KEY=sk-ant-...  # Anthropic 키 사용
```

### Gemini (Extended Thinking ✅ - 2.0+)

```bash
V2_PROVIDER=gemini
V2_MODEL=gemini-2.0-flash-exp  # 기본값, 빠름
V2_MODEL=gemini-1.5-pro        # 더 강력
V2_MODEL=gemini-1.5-flash
```

**별칭**:
- `gemini` → gemini-2.0-flash-exp
- `gemini-pro` → gemini-1.5-pro

## 코드에서 직접 사용

### 기본 사용법

```python
from custom_claude_code.v2_langgraph.models import get_model

# Anthropic
model = get_model(provider="anthropic", model_name="claude-haiku-4-5")

# OpenAI
model = get_model(provider="openai", model_name="gpt-4o")

# Gemini
model = get_model(provider="gemini", model_name="gemini-2.0-flash-exp")
```

### 별칭 사용

```python
from custom_claude_code.v2_langgraph.models import get_model_by_alias

model = get_model_by_alias("haiku")    # Claude Haiku
model = get_model_by_alias("gpt4o")    # GPT-4o
model = get_model_by_alias("gemini")   # Gemini Flash
```

### 설정 확인

```python
from custom_claude_code.v2_langgraph.config import V2Config

# 현재 설정 출력
print(V2Config.summary())
```

## 전체 설정 옵션

| 환경 변수 | 기본값 | 설명 |
|-----------|--------|------|
| `V2_PROVIDER` | `anthropic` | 모델 제공자 |
| `V2_MODEL` | (provider 기본값) | 사용할 모델 이름 |
| `V2_TEMPERATURE` | `1.0` | 생성 온도 (0.0 ~ 2.0) |
| `V2_THINKING_BUDGET` | `2048` | Extended Thinking 토큰 수 |
| `V2_RECURSION_LIMIT` | `50` | 그래프 재귀 제한 |
| `V2_MAX_SUBAGENT_DEPTH` | `5` | Subagent 중첩 깊이 |
| `V2_AUTO_COMPACT` | `true` | 자동 메시지 압축 |
| `V2_COMPACT_THRESHOLD` | `100000` | 압축 임계값 (토큰) |
| `V2_SHOW_THINKING` | `true` | Thinking 블록 표시 |
| `V2_SHOW_TOOL_RESULTS` | `true` | 도구 결과 표시 |

## 모델별 특징

| 특징 | Anthropic | OpenAI | Gemini |
|------|-----------|--------|--------|
| Extended Thinking | ✅ | ❌ | ✅ (2.0+) |
| Tool Use | ✅ | ✅ | ✅ |
| Streaming | ✅ | ✅ | ✅ |
| Vision | ✅ | ✅ | ✅ |
| 한국어 성능 | 🌟🌟🌟 | 🌟🌟 | 🌟🌟🌟 |

## 예시: OpenAI로 전환

```bash
# .env 파일 수정
V2_PROVIDER=openai
V2_MODEL=gpt-4o
OPENAI_API_KEY=sk-proj-...

# 실행
uv run python -m custom_claude_code.v2_langgraph.main
```

첫 번째 응답에서 설정 정보가 표시됩니다:
```
v2 LangGraph 설정:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[모델]
  Provider: openai
  Model: gpt-4o
  Temperature: 1.0
  Thinking Budget: 2048
...
```

## 문제 해결

### "API Key not found" 에러

해당 provider의 API 키가 `.env`에 설정되어 있는지 확인:
- Anthropic: `ANTHROPIC_API_KEY`
- OpenAI: `OPENAI_API_KEY`
- Gemini: `GOOGLE_API_KEY`

### "Unsupported provider" 에러

`V2_PROVIDER`가 `anthropic`, `openai`, `gemini` 중 하나인지 확인

### Thinking이 표시되지 않음

- Anthropic: 모든 모델 지원 ✅
- OpenAI: 지원 안함 ❌
- Gemini: 2.0 모델만 지원 (실험적)
