# 수동 통합 테스트 가이드

새로 추가된 5개 도구(bash_background, bash_output, kill_shell, web_search, web_fetch)가 실제 AI 대화에서 제대로 작동하는지 확인하는 가이드입니다.

## 준비사항

```bash
# 환경 변수 설정 확인
source .env  # 또는 .env 파일에 API 키가 설정되어 있는지 확인

# 필요한 패키지 설치 (웹 도구용)
uv add ddgs httpx beautifulsoup4
```

## 테스트 1: v1 (OpenAI API)

### 실행
```bash
uv run python -m custom_claude_code.v1_openai.main
```

### 테스트 프롬프트

#### 백그라운드 실행 테스트
```
백그라운드에서 'sleep 3 && echo "작업 완료!"' 명령을 실행하고,
프로세스 ID를 알려줘. 그 다음 출력을 확인하고, 마지막으로 프로세스를 종료해줘.
```

**기대 동작:**
1. ✅ AI가 `BashBackground` 도구를 사용해서 백그라운드 프로세스 시작
2. ✅ Shell ID를 포함한 성공 메시지 출력
3. ✅ `BashOutput` 도구로 프로세스 출력 확인
4. ✅ `KillShell` 도구로 프로세스 종료

#### 웹 검색 테스트
```
DuckDuckGo로 "Python asyncio tutorial"을 검색해서 상위 3개 결과를 요약해줘.
```

**기대 동작:**
1. ✅ AI가 `WebSearch` 도구 사용
2. ✅ 검색 결과 표시 (제목, URL, 설명)
3. ✅ 검색 결과 요약 제공

#### 웹 페이지 가져오기 테스트
```
https://example.com 페이지의 주요 내용을 가져와서 요약해줘.
```

**기대 동작:**
1. ✅ AI가 `WebFetch` 도구 사용
2. ✅ HTML 내용을 파싱해서 주요 텍스트 추출
3. ✅ 내용 요약 제공

---

## 테스트 2: v3 (OpenAI Agents SDK)

### 실행
```bash
# v3는 OpenAI API 키 필요
export OPENAI_API_KEY=your_openai_api_key_here
uv run python -m custom_claude_code.v3_openai_agents.main
```

### 테스트 프롬프트

```
Run 'echo "V3 test" && sleep 2' in the background,
check the output, then kill the process. Keep it brief.
```

**기대 동작:**
1. ✅ AI가 bash_background 도구 사용
2. ✅ bash_output으로 출력 확인
3. ✅ kill_shell로 종료
4. ✅ 간결한 완료 메시지

---

## 테스트 3: v4 (Claude Agent SDK)

### 실행
```bash
uv run python -m custom_claude_code.v4_claude_agent.main
```

### 테스트 프롬프트

```
백그라운드에서 'date && sleep 2' 명령을 실행하고,
출력을 확인한 다음 프로세스를 종료해줘.
```

**기대 동작:**
1. ✅ AI가 `mcp__custom__bash_background` 도구 사용
2. ✅ `mcp__custom__bash_output`으로 현재 날짜 출력 확인
3. ✅ `mcp__custom__kill_shell`로 종료
4. ✅ 각 단계별 상태 보고

---

## 테스트 4: 복합 테스트 (v2.1과 비교)

### v2.1 실행
```bash
uv run python -m custom_claude_code.v2_1_langgraph_improved.main
```

### v1/v3/v4 중 하나 실행

### 같은 프롬프트로 테스트
```
다음 작업을 순서대로 해줘:
1. 백그라운드에서 'ls -la | head -5' 실행
2. 출력 확인
3. 프로세스 종료
4. "LangGraph tutorial"을 웹 검색
```

**비교 사항:**
- ✅ 모든 버전이 동일한 도구를 사용하는지 확인
- ✅ 응답 품질이 유사한지 확인
- ✅ 에러 처리가 올바른지 확인

---

## 검증 체크리스트

### 각 버전별로 확인:

- [ ] 백그라운드 프로세스 실행 (bash_background)
- [ ] 프로세스 출력 읽기 (bash_output)
- [ ] 프로세스 종료 (kill_shell)
- [ ] 웹 검색 (web_search) - ddgs 패키지 필요
- [ ] 웹 페이지 가져오기 (web_fetch) - httpx, bs4 필요

### 에러 케이스 테스트:

```
존재하지 않는 shell ID로 출력을 확인해줘: "invalid-id"
```

**기대 동작:**
- ✅ "[ERROR] Shell not found" 메시지
- ✅ AI가 에러를 인지하고 사용자에게 알림

---

## 성공 기준

1. **도구 사용**: AI가 새로운 5개 도구를 올바르게 호출
2. **에러 처리**: 잘못된 입력에 대해 적절한 에러 메시지
3. **작업 완료**: 요청한 작업을 끝까지 수행
4. **일관성**: v1, v3, v4 모두 동일한 기능 제공

---

## 문제 해결

### ddgs 패키지 에러
```bash
uv add ddgs
```

### httpx/beautifulsoup4 에러
```bash
uv add httpx beautifulsoup4
```

### API 키 에러
```bash
# .env 파일 확인
cat .env | grep API_KEY

# 환경 변수 재로드
source .env
```

---

## 자동화된 기본 테스트

위의 수동 테스트 전에 먼저 실행:

```bash
# 도구 등록 확인
uv run python test_new_tools.py

# 기본 기능 확인
uv run python test_v1_only.py
uv run python test_v2_korean.py
uv run python test_v4_korean.py
```

---

## 결과 기록

테스트 날짜: _______________

| 버전 | bash_bg | bash_out | kill | web_search | web_fetch | 전체 |
|------|---------|----------|------|------------|-----------|------|
| v1   | ☐       | ☐        | ☐    | ☐          | ☐         | ☐    |
| v3   | ☐       | ☐        | ☐    | ☐          | ☐         | ☐    |
| v4   | ☐       | ☐        | ☐    | ☐          | ☐         | ☐    |

테스트 담당자: _______________
