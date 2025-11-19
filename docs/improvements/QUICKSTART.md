# 🚀 Quick Start Guide

Custom Claude Code의 4가지 버전을 즉시 테스트해보세요!

## 📋 요구사항

- Python 3.10+
- uv (Python 패키지 관리자)
- Anthropic API key

## ⚡ 빠른 시작

### 1. API Key 설정

`.env` 파일이 이미 설정되어 있습니다:

```bash
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1/

OPENAI_API_KEY=sk-ant-api03-...  # v1-v3에서 사용
OPENAI_BASE_URL=https://api.anthropic.com/v1/
```

### 2. Interactive Launcher 실행

```bash
cd /Users/jd/Documents/workspace/custom-claude-code
uv run python launcher.py
```

### 3. 버전 선택

메뉴에서 원하는 버전을 선택:
- **1**: v1 - OpenAI API (완전 제어, 리팩토링됨)
- **2**: v2 - LangGraph (자동 워크플로우)
- **3**: v3 - OpenAI Agents SDK (Agent.as_tool())
- **4**: v4 - Claude Agent SDK (공식, 가장 간단)
- **c**: 버전 비교 보기
- **q**: 종료

## 🎯 개별 버전 직접 실행

각 버전을 직접 실행하려면:

```bash
# v1 - OpenAI API
uv run python -m custom_claude_code.v1_openai.main

# v2 - LangGraph
uv run python -m custom_claude_code.v2_langgraph.main

# v3 - OpenAI Agents SDK
uv run python -m custom_claude_code.v3_openai_agents.main

# v4 - Claude Agent SDK
uv run python -m custom_claude_code.v4_claude_agent.main
```

## 💡 테스트 예시

각 버전에서 동일한 태스크를 시도해보세요:

```
# 예시 1: 파일 읽기
Read the README.md file and summarize it

# 예시 2: 코드 검색
Find all Python files that import asyncio

# 예시 3: Subagent 사용 (v1, v2, v3, v4 모두 지원)
Use the Explore agent to find all configuration files in this project
```

## 🔧 명령어

모든 버전에서 공통으로 사용 가능:

- `quit` - 종료 (launcher로 돌아감)
- `clear` - 대화 기록 삭제 (v1, v2, v3)
- `debug` - 디버그 정보 표시 (v1)
- `cost` - 비용 정보 표시 (v4)

## 📊 버전별 특징

| 버전 | 프레임워크 | 코드량 | 주요 특징 |
|------|-----------|--------|----------|
| v1 | OpenAI API | ~1,891줄 | 레지스트리 패턴, 함수 분해 |
| v2 | LangGraph | ~450줄 | StateGraph, 자동 워크플로우 |
| v3 | OpenAI Agents | ~280줄 | Agent.as_tool() 패턴 |
| v4 | Claude Agent | ~302줄 | 공식 SDK, 설정 기반 |

## 🎨 UI 기능

Launcher의 주요 기능:

✅ **버전 비교 테이블** - 각 버전의 특징 한눈에 보기
✅ **원클릭 실행** - 숫자만 입력하면 즉시 실행
✅ **자동 복귀** - 종료 시 자동으로 메인 메뉴로
✅ **에러 처리** - 에러 발생 시 메뉴로 복귀
✅ **키보드 인터럽트** - Ctrl+C로 안전하게 종료

## 🚨 문제 해결

### langchain_openai 에러 (v2)

```bash
uv pip install langchain-openai
```

### Import 에러

```bash
cd /Users/jd/Documents/workspace/custom-claude-code
uv sync
```

### API Key 에러

`.env` 파일의 API key가 올바른지 확인:
```bash
cat .env
```

## 📚 더 알아보기

- [메인 README](README.md) - 전체 프로젝트 개요
- [v1 README](src/custom_claude_code/v1_openai/README.md) - OpenAI API 버전
- [v2 README](src/custom_claude_code/v2_langgraph/README.md) - LangGraph 버전
- [v3 README](src/custom_claude_code/v3_openai_agents/README.md) - OpenAI Agents 버전
- [v4 README](src/custom_claude_code/v4_claude_agent/README.md) - Claude Agent 버전

## 🎉 즐기세요!

각 버전은 동일한 Claude Code 기능을 제공하지만, 다른 구현 패턴을 사용합니다.
자유롭게 비교하고 테스트하세요!
