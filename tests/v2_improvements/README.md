# v2 개선 사항 테스트

v2 LangGraph 구현의 개선 사항을 검증하는 테스트 모음입니다.

## 🧪 테스트 파일

### 1. verify_tools_implementation.py
**목적**: 레퍼런스 JSON schema와 현재 구현 비교

**검증 항목**:
- 전체 도구 개수 (9/16개 구현)
- 각 도구의 파라미터 완전성
- 누락/추가된 도구 목록

**실행**:
```bash
uv run python tests/v2_improvements/verify_tools_implementation.py
```

**출력 예시**:
```
✅ 구현 완료: 9/16 도구
❌ 미구현:     7/16 도구

⚠️  grep_code (레퍼런스: Grep)
   누락된 파라미터: (없음)

✅ run_bash: 핵심 파라미터 일치
```

---

### 2. test_improved_tools.py
**목적**: grep_code와 run_bash의 개선된 기능 테스트

**테스트 케이스**:

**grep_code (5가지)**:
1. 기본 검색 (files_with_matches 모드)
2. content 모드 (매칭된 라인 표시 + head_limit)
3. 파일 타입 필터링 (type=py)
4. 대소문자 무시 (i=True)
5. count 모드 (매칭 개수)

**run_bash (3가지)**:
1. 기본 명령어 실행
2. pwd 명령어
3. timeout 설정 (milliseconds)

**실행**:
```bash
uv run python tests/v2_improvements/test_improved_tools.py
```

**출력 예시**:
```
✅ grep_code 모든 테스트 통과!
✅ run_bash 모든 테스트 통과!

📋 개선 사항 요약:
grep_code:
  ✅ output_mode 추가 (content/files_with_matches/count)
  ✅ type 파라미터 추가 (파일 타입 필터)
  ...
```

---

### 3. test_task_tool.py
**목적**: task_tool 레퍼런스 일치 및 subagent_type 필터링 검증

**테스트 케이스**:

**Schema 검증**:
- Required 파라미터: description, prompt, subagent_type
- Optional 파라미터: model, resume
- 파라미터 순서 확인

**Subagent 필터링**:
- general-purpose: 6개 도구 (쓰기 가능)
- Explore: 4개 도구 (읽기 전용)
- Plan: 4개 도구 (읽기 전용)

**도구 호출**:
- 각 타입별 task_tool 호출 성공 여부

**실행**:
```bash
uv run python tests/v2_improvements/test_task_tool.py
```

**출력 예시**:
```
✅ 파라미터 완전 일치!
✅ Required 파라미터 일치!
✅ Explore 도구 필터링 정확!
✅ Plan 도구 필터링 정확!
✅ general-purpose 도구 필터링 정확!
```

---

## 🚀 전체 테스트 실행

```bash
# 모든 테스트 순차 실행
cd /Users/jd/Documents/workspace/custom-claude-code
uv run python tests/v2_improvements/verify_tools_implementation.py
uv run python tests/v2_improvements/test_improved_tools.py
uv run python tests/v2_improvements/test_task_tool.py
```

**또는 간단하게**:
```bash
for test in tests/v2_improvements/*.py; do
    echo "Running $test..."
    uv run python "$test"
    echo ""
done
```

---

## ✅ 기대 결과

모든 테스트가 통과해야 합니다:

```
verify_tools_implementation.py  ✅
test_improved_tools.py          ✅
test_task_tool.py               ✅
```

---

## 🐛 테스트 실패 시

### 1. ImportError
```bash
uv sync  # 의존성 재설치
```

### 2. 파일 경로 오류
- 프로젝트 루트에서 실행했는지 확인
- `sys.path` 설정 확인

### 3. 기능 테스트 실패
- 최신 코드로 업데이트: `git pull`
- 변경사항 확인: `git diff src/custom_claude_code/v2_langgraph/`

---

## 📊 테스트 커버리지

| 컴포넌트 | 테스트 항목 | 상태 |
|----------|------------|------|
| grep_code | output_mode 3가지 | ✅ |
| grep_code | 파일 타입 필터 | ✅ |
| grep_code | 대소문자 무시 | ✅ |
| grep_code | head_limit | ✅ |
| run_bash | timeout ms | ✅ |
| task_tool | 파라미터 순서 | ✅ |
| task_tool | resume 파라미터 | ✅ |
| Subagent | Explore 필터링 | ✅ |
| Subagent | Plan 필터링 | ✅ |
| Subagent | general 필터링 | ✅ |

**총 커버리지**: 10/10 항목 (100%)

---

## 🔧 테스트 추가하기

새로운 기능을 추가했다면 테스트도 추가하세요:

```python
# tests/v2_improvements/test_new_feature.py

def test_new_feature():
    """새 기능 테스트"""
    result = new_tool.invoke({"param": "value"})
    assert result == "expected"
    print("✅ 새 기능 테스트 통과!")

if __name__ == "__main__":
    test_new_feature()
```

---

## 📚 관련 문서

- **개선 문서**: `docs/05-improvements/README.md`
- **종합 요약**: `docs/05-improvements/TOOLS_IMPROVEMENT_SUMMARY.md`
- **레퍼런스 비교**: `docs/05-improvements/tool_implementation_analysis.md`
