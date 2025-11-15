# Tests - 자동화된 테스트

이 폴더에는 Custom Claude Code의 기능을 검증하는 자동화된 테스트들이 있습니다.

## 파일 목록

### test_version_imports.py
**목적:** 모든 버전 import 확인
**기능:** v1, v2, v3, v4 모듈이 정상적으로 import되는지 테스트

**실행:**
```bash
uv run python tests/test_version_imports.py
```

---

### test_v1_api_client.py
**목적:** v1 API 클라이언트 테스트
**기능:** OpenAI API 클라이언트 초기화 및 간단한 완성도 테스트

**실행:**
```bash
uv run python tests/test_v1_api_client.py
```

---

### test_v1_conversation.py
**목적:** v1 전체 대화 테스트
**기능:** 3가지 실제 대화 시나리오 테스트
- 인사
- 파일 찾기
- 파일 읽기

**실행:**
```bash
uv run python tests/test_v1_conversation.py
```

---

### test_quality.py
**목적:** 코드 품질 테스트
**기능:**
- v1 Read 도구 품질 검증
- v4 import 테스트

**실행:**
```bash
uv run python tests/test_quality.py
```

---

## 테스트 실행 방법

### 전체 테스트 실행
```bash
uv run python -m pytest tests/
```

### 개별 테스트 실행
```bash
uv run python tests/test_version_imports.py
```

---

## 용도

- **CI/CD**: 자동화된 빌드 파이프라인에서 사용
- **회귀 테스트**: 코드 변경 후 기존 기능 확인
- **품질 보증**: 릴리스 전 검증
