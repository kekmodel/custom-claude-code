# Demos - 자동 데모 스크립트

이 폴더에는 Custom Claude Code의 기능을 자동으로 시연하는 데모 스크립트들이 있습니다.

## 파일 목록

### v1_automated.py
**목적:** v1 (OpenAI API 직접 구현) 자동 데모
**기능:** 3가지 시나리오를 자동으로 실행
- 프로젝트 소개
- Glob 도구 사용 (파일 찾기)
- 파일 읽기

**실행:**
```bash
uv run python demos/v1_automated.py
```

---

### v1_and_v3_conversation.py
**목적:** v1과 v3 비교 데모
**기능:** 3가지 테스트 시나리오 실행
- 인사
- 파일 읽기
- 서브에이전트 호출

**실행:**
```bash
uv run python demos/v1_and_v3_conversation.py
```

---

### v4_api_test.py
**목적:** v4 (Claude Agent SDK) API 테스트
**기능:** ClaudeSDKClient로 2개 쿼리 테스트

**실행:**
```bash
uv run python demos/v4_api_test.py
```

---

## 용도

- **프로젝트 소개**: 새로운 사용자에게 기능 시연
- **기능 검증**: CI/CD 파이프라인에서 자동 검증
- **개발 테스트**: 기능 변경 후 빠른 확인
