# v2 LangGraph Tools 구현 분석

## 검증 결과 요약

### ✅ 완벽하게 구현된 도구 (6개)

| 도구 | 레퍼런스 | 파라미터 일치 | 상태 |
|------|----------|---------------|------|
| read_file | Read | ✅ | 완벽 |
| write_file | Write | ✅ | 완벽 |
| edit_file | Edit | ✅ | 완벽 |
| glob_files | Glob | ✅ | 완벽 |
| todo_write | TodoWrite | ✅ | 완벽 |
| exit_plan_mode | ExitPlanMode | ✅ | 완벽 |

### ⚠️ 파라미터 불일치 도구 (3개)

#### 1. grep_code (레퍼런스: Grep)

**누락된 파라미터:**
- `-A`, `-B`, `-C`: Context lines (전후 라인 표시)
- `-i`: 대소문자 구분 없음 (구현됨: `case_insensitive`)
- `-n`: 줄 번호 표시
- `output_mode`: "content" | "files_with_matches" | "count"
- `type`: 파일 타입 필터 (js, py, rust 등)
- `head_limit`: 출력 제한
- `offset`: 출력 오프셋
- `multiline`: 멀티라인 매칭

**현재 구현:**
```python
def grep_code(pattern: str, path: Optional[str] = None,
              glob: Optional[str] = None, case_insensitive: bool = False)
```

**레퍼런스 스키마:**
```python
def grep_code(pattern: str, path: Optional[str] = None, glob: Optional[str] = None,
              output_mode: str = "files_with_matches",
              B: Optional[int] = None, A: Optional[int] = None, C: Optional[int] = None,
              n: bool = True, i: bool = False, type: Optional[str] = None,
              head_limit: Optional[int] = None, offset: int = 0, multiline: bool = False)
```

**영향도:** 중간 - 고급 검색 기능이 제한됨

---

#### 2. run_bash (레퍼런스: Bash)

**누락된 파라미터:**
- `description`: 명령어 설명 (5-10 단어)
- `run_in_background`: 백그라운드 실행 여부
- `dangerouslyDisableSandbox`: 샌드박스 비활성화

**현재 구현:**
```python
def run_bash(command: str, timeout: int = 30)
```

**레퍼런스 스키마:**
```python
def run_bash(command: str, timeout: Optional[int] = 120000,  # milliseconds
             description: Optional[str] = None,
             run_in_background: bool = False,
             dangerouslyDisableSandbox: bool = False)
```

**영향도:** 중간 - 백그라운드 실행 기능 없음

---

#### 3. task_tool (레퍼런스: Task)

**누락된 파라미터:**
- `resume`: Agent ID to resume from

**현재 구현:**
```python
def task_tool(subagent_type: str, description: str, prompt: str, model: str = "haiku")
```

**레퍼런스 스키마:**
```python
def task_tool(description: str, prompt: str, subagent_type: str,
              model: Optional[str] = None, resume: Optional[str] = None)
```

**영향도:** 낮음 - Resume 기능은 고급 기능

---

### ❌ 미구현 도구 (7개)

| 도구 | 용도 | 우선순위 |
|------|------|----------|
| **WebFetch** | 웹 페이지 내용 가져오기 | 🔴 높음 |
| **WebSearch** | 웹 검색 | 🔴 높음 |
| **BashOutput** | 백그라운드 Bash 출력 읽기 | 🟡 중간 |
| **KillShell** | 백그라운드 Bash 종료 | 🟡 중간 |
| **NotebookEdit** | Jupyter 노트북 편집 | 🟢 낮음 |
| **Skill** | Skill 실행 | 🟢 낮음 |
| **SlashCommand** | 슬래시 명령어 실행 | 🟢 낮음 |

---

## 개선 권장사항

### 1단계: 핵심 파라미터 추가 (필수)

#### grep_code 개선
```python
@tool(parse_docstring=True)
def grep_code(
    pattern: str,
    path: Optional[str] = None,
    glob: Optional[str] = None,
    output_mode: str = "files_with_matches",  # 추가
    i: bool = False,  # case_insensitive → -i로 변경
    n: bool = True,  # 추가
    type: Optional[str] = None,  # 추가
) -> str:
    """A powerful search tool built on ripgrep.

    Args:
        pattern: The regular expression pattern to search for
        path: File or directory to search in (defaults to current working directory)
        glob: Glob pattern to filter files (e.g., "*.py", "*.{ts,tsx}")
        output_mode: Output mode - "content" shows lines, "files_with_matches" shows paths, "count" shows counts
        i: Case insensitive search (rg -i)
        n: Show line numbers in output (rg -n). Defaults to true.
        type: File type to search (rg --type). Common types: js, py, rust, go, java
    """
```

#### run_bash 개선
```python
@tool(parse_docstring=True)
def run_bash(
    command: str,
    timeout: int = 120,  # seconds
    description: Optional[str] = None,  # 추가
    run_in_background: bool = False,  # 추가
) -> str:
    """Executes a bash command.

    Args:
        command: The command to execute
        timeout: Optional timeout in seconds (default: 120)
        description: Clear, concise description of what this command does in 5-10 words
        run_in_background: Set to true to run this command in the background
    """
```

#### task_tool 개선
```python
@tool(parse_docstring=True)
def task_tool(
    description: str,  # 순서 변경 (required first)
    prompt: str,
    subagent_type: str,
    model: str = "haiku",
    resume: Optional[str] = None,  # 추가
) -> str:
    """Launch a subagent to handle complex tasks.

    Args:
        description: A short (3-5 word) description of the task
        prompt: The task for the agent to perform
        subagent_type: The type of specialized agent to use (general-purpose, Explore, Plan)
        model: Optional model to use (sonnet, opus, haiku). Defaults to haiku.
        resume: Optional agent ID to resume from
    """
```

---

### 2단계: 고급 기능 추가 (선택)

#### WebFetch 추가 (웹 콘텐츠 가져오기)
```python
@tool(parse_docstring=True)
def web_fetch(url: str, prompt: str) -> str:
    """Fetches content from a URL and processes it.

    Args:
        url: The URL to fetch content from
        prompt: The prompt to run on the fetched content

    Returns:
        Processed web content
    """
    import requests
    from bs4 import BeautifulSoup

    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.text, 'html.parser')
    text = soup.get_text()

    # 실제로는 LLM으로 prompt 처리 필요
    return f"Content from {url}:\n{text[:1000]}"
```

#### WebSearch 추가 (웹 검색)
```python
@tool(parse_docstring=True)
def web_search(
    query: str,
    allowed_domains: Optional[list[str]] = None,
    blocked_domains: Optional[list[str]] = None
) -> str:
    """Search the web and return results.

    Args:
        query: The search query
        allowed_domains: Only include results from these domains
        blocked_domains: Never include results from these domains

    Returns:
        Search results
    """
    # 실제로는 검색 API (DuckDuckGo, Tavily 등) 사용 필요
    return f"Search results for: {query}"
```

---

## 결론

### 현재 상태
- ✅ **교육/연구 목적으로 충분함**: 핵심 9개 도구가 잘 구현됨
- ⚠️ **프로덕션 용도**: 파라미터 보완 필요
- ❌ **완전한 Claude Code 재현**: 7개 도구 추가 필요

### 우선순위
1. 🔴 **필수**: grep_code, run_bash, task_tool 파라미터 보완
2. 🟡 **권장**: WebFetch, WebSearch 추가 (웹 기능)
3. 🟢 **선택**: BashOutput, KillShell, NotebookEdit, Skill, SlashCommand

### 다음 단계
이 프로젝트의 목적이 **교육/분석**이라면:
- 현재 상태 유지 ✅
- 문서화에 "간소화된 구현"임을 명시

프로덕션/완전한 구현이 목표라면:
1. 1단계: 파라미터 보완 (1-2시간)
2. 2단계: WebFetch, WebSearch 추가 (2-3시간)
3. 3단계: 나머지 도구 추가 (4-5시간)
