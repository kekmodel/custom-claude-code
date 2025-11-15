# 🎮 Interactive Examples

Tool과 Subagent를 활용하는 실전 멀티턴 대화 예시

---

## 📋 목차

1. [프로젝트 분석 및 문서 생성](#1-프로젝트-분석-및-문서-생성)
2. [버그 찾기 및 수정](#2-버그-찾기-및-수정)
3. [새 기능 추가 (계획 → 구현)](#3-새-기능-추가-계획--구현)
4. [코드베이스 탐색 및 리팩토링](#4-코드베이스-탐색-및-리팩토링)
5. [테스트 작성 및 실행](#5-테스트-작성-및-실행)

---

## 1. 프로젝트 분석 및 문서 생성

### 시나리오
프로젝트의 구조를 파악하고 요약 문서를 만들기

### 대화 예시

```
👤 You:
I need to understand this project structure.
Use the Explore agent to find all Python files and summarize the project structure.

🤖 Claude:
I'll use the Explore agent to analyze the codebase.

🔧 Using tool: Task
   subagent_type: Explore
   description: Find all Python files and analyze project structure

📋 Subagent report:
Found the following structure:
- src/custom_claude_code/
  - v1_openai/ (6 files, ~1,891 lines)
  - v2_langgraph/ (6 files, ~450 lines)
  - v3_openai_agents/ (6 files, ~280 lines)
  - v4_claude_agent/ (3 files, ~302 lines)

The project contains 4 different implementations of Claude Code...

---

👤 You:
Good! Now read the main README.md to understand what this project is about.

🤖 Claude:
🔧 Using tool: Read
   file_path: README.md

The project is a comprehensive analysis and implementation of Claude Code's
internal architecture. It provides 4 different versions...

---

👤 You:
Create a summary document called PROJECT_SUMMARY.md with:
1. What this project does
2. The 4 versions and their key differences
3. How to get started

🤖 Claude:
I'll create the summary document.

🔧 Using tool: Write
   file_path: PROJECT_SUMMARY.md

✅ Document created successfully!
```

### 사용된 Tool/Subagent
- ✅ **Task (Explore)** - 프로젝트 구조 분석
- ✅ **Read** - README 읽기
- ✅ **Write** - 새 문서 작성

---

## 2. 버그 찾기 및 수정

### 시나리오
에러를 찾아서 수정하기

### 대화 예시

```
👤 You:
I'm getting an error: "Optional is not defined".
Find where this error is coming from and fix it.

🤖 Claude:
Let me search for where "Optional" is used without being imported.

🔧 Using tool: Grep
   pattern: Optional\[
   path: src/custom_claude_code

Found in:
- v1_openai/main.py:183 - def get_user_input() -> Optional[str]:

Let me check the imports in that file.

---

🔧 Using tool: Read
   file_path: src/custom_claude_code/v1_openai/main.py
   offset: 1
   limit: 30

I can see the imports section. The issue is that "Optional" is not imported
from typing. Let me fix it.

---

🔧 Using tool: Edit
   file_path: src/custom_claude_code/v1_openai/main.py
   old_string: from typing import List, Dict, Any
   new_string: from typing import List, Dict, Any, Optional

✅ Fixed! The import has been added.

---

👤 You:
Great! Run a quick test to make sure the import works.

🤖 Claude:
🔧 Using tool: Bash
   command: cd /Users/jd/Documents/workspace/custom-claude-code &&
            python -c "from custom_claude_code.v1_openai.main import get_user_input;
            print('✅ Import successful')"

Output: ✅ Import successful

The fix is working!
```

### 사용된 Tool/Subagent
- ✅ **Grep** - 에러 위치 검색
- ✅ **Read** - 파일 내용 확인
- ✅ **Edit** - 코드 수정
- ✅ **Bash** - 테스트 실행

---

## 3. 새 기능 추가 (계획 → 구현)

### 시나리오
새로운 기능을 계획하고 구현하기

### 대화 예시

```
👤 You:
I want to add a "cost tracking" feature to v1 that shows the total API cost
after each response. Use the Plan agent to break this down into steps.

🤖 Claude:
I'll use the Plan agent to create an implementation plan.

🔧 Using tool: Task
   subagent_type: Plan
   description: Plan cost tracking feature for v1
   prompt: |
     Analyze the v1 codebase and create a plan to add cost tracking that:
     1. Tracks tokens used in each API call
     2. Calculates cost based on Claude Haiku pricing
     3. Displays total cost after each response

📋 Subagent report:

## Implementation Plan: Cost Tracking for v1

### Step 1: Add cost calculation function
- Create `calculate_cost()` function
- Use Claude Haiku pricing: $0.25/1M input, $1.25/1M output

### Step 2: Modify stream_assistant_response()
- Capture usage data from API response
- Calculate cost and add to return value

### Step 3: Update process_turn_loop()
- Track cumulative cost
- Display after each turn

### Step 4: Add 'cost' command
- Show total session cost on demand

---

👤 You:
Perfect! Let's start with Step 1. Add the calculate_cost function to main.py.

🤖 Claude:
🔧 Using tool: Read
   file_path: src/custom_claude_code/v1_openai/main.py
   offset: 40
   limit: 50

I'll add the cost calculation function after the console initialization.

---

🔧 Using tool: Edit
   file_path: src/custom_claude_code/v1_openai/main.py
   old_string: # Prompt session (async 지원)
prompt_session = PromptSession(history=InMemoryHistory())
   new_string: # Prompt session (async 지원)
prompt_session = PromptSession(history=InMemoryHistory())


# ============================================================================
# Cost Calculation
# ============================================================================

def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """
    Calculate API cost for Claude Haiku

    Pricing:
    - Input: $0.25 per 1M tokens
    - Output: $1.25 per 1M tokens
    """
    input_cost = (input_tokens / 1_000_000) * 0.25
    output_cost = (output_tokens / 1_000_000) * 1.25
    return input_cost + output_cost

✅ Function added!

---

👤 You:
Now modify stream_assistant_response to capture and return usage data.

🤖 Claude:
🔧 Using tool: Read
   file_path: src/custom_claude_code/v1_openai/main.py
   offset: 88
   limit: 100

[Continues with implementation...]
```

### 사용된 Tool/Subagent
- ✅ **Task (Plan)** - 구현 계획 수립
- ✅ **Read** - 코드 분석
- ✅ **Edit** - 기능 구현
- ✅ **Bash** - 테스트

---

## 4. 코드베이스 탐색 및 리팩토링

### 시나리오
중복 코드를 찾아서 공통 함수로 추출하기

### 대화 예시

```
👤 You:
Use the Explore agent to find all files that have similar tool implementations.
I want to refactor and eliminate duplication.

🤖 Claude:
🔧 Using tool: Task
   subagent_type: Explore
   description: Find duplicated tool implementations across versions
   prompt: |
     Search for files containing tool implementations (read_file, write_file, etc.)
     and identify duplicated code patterns.

📋 Subagent report:

Found tool implementations in:
1. v1_openai/tools.py - 16 tools (~740 lines)
2. v2_langgraph/tools.py - 6 tools (~350 lines)
3. v3_openai_agents/tools.py - 5 tools (~280 lines)

Common tools with ~80% code duplication:
- read_file
- write_file
- edit_file
- glob_files
- grep_code

Recommendation: Create common/tools_core.py with shared implementations.

---

👤 You:
Good analysis! Let's create the common/tools_core.py with the shared read_file implementation.

🤖 Claude:
🔧 Using tool: Bash
   command: mkdir -p src/custom_claude_code/common

🔧 Using tool: Read
   file_path: src/custom_claude_code/v1_openai/tools.py
   offset: 100
   limit: 50

I'll extract the core read_file logic.

---

🔧 Using tool: Write
   file_path: src/custom_claude_code/common/tools_core.py

[Implementation continues...]
```

### 사용된 Tool/Subagent
- ✅ **Task (Explore)** - 중복 코드 탐색
- ✅ **Bash** - 디렉토리 생성
- ✅ **Read** - 코드 분석
- ✅ **Write** - 공통 모듈 생성

---

## 5. 테스트 작성 및 실행

### 시나리오
새 기능에 대한 테스트 작성 및 실행

### 대화 예시

```
👤 You:
I just added a calculate_cost function. Create a test file for it and run the tests.

🤖 Claude:
I'll create a comprehensive test file.

🔧 Using tool: Write
   file_path: tests/test_cost_calculation.py
   content: |
     """Test cost calculation function"""
     import pytest
     from custom_claude_code.v1_openai.main import calculate_cost

     def test_calculate_cost_basic():
         # 1000 input tokens, 500 output tokens
         cost = calculate_cost(1000, 500)
         expected = (1000/1_000_000 * 0.25) + (500/1_000_000 * 1.25)
         assert abs(cost - expected) < 0.0001

     def test_calculate_cost_large():
         # 100K input, 50K output
         cost = calculate_cost(100_000, 50_000)
         expected = (100_000/1_000_000 * 0.25) + (50_000/1_000_000 * 1.25)
         assert abs(cost - expected) < 0.001

✅ Test file created!

---

👤 You:
Run the tests now.

🤖 Claude:
🔧 Using tool: Bash
   command: cd /Users/jd/Documents/workspace/custom-claude-code &&
            pytest tests/test_cost_calculation.py -v

Output:
============================= test session starts ==============================
collected 2 items

tests/test_cost_calculation.py::test_calculate_cost_basic PASSED        [ 50%]
tests/test_cost_calculation.py::test_calculate_cost_large PASSED        [100%]

============================== 2 passed in 0.03s ===============================

✅ All tests passed!

---

👤 You:
Great! Also run a quick integration test to make sure it works in the actual conversation loop.

🤖 Claude:
I'll create a simple integration test.

🔧 Using tool: Write
   file_path: tests/test_cost_integration.py

[Creates integration test...]

---

🔧 Using tool: Bash
   command: cd /Users/jd/Documents/workspace/custom-claude-code &&
            pytest tests/test_cost_integration.py -v

[Runs integration test...]
```

### 사용된 Tool/Subagent
- ✅ **Write** - 테스트 파일 작성
- ✅ **Bash** - pytest 실행
- ✅ **Read** - 테스트 결과 확인

---

## 🎯 복합 시나리오: 전체 워크플로우

### 대화 예시: 새 프로젝트 기능 추가 (모든 것 활용)

```
👤 You:
I want to add a new feature to this project: a "comparison mode" that lets users
run the same prompt on all 4 versions and compare the responses.

Use the Plan agent to create a detailed implementation plan, then we'll implement it together.

🤖 Claude:
I'll use the Plan agent to analyze the project and create a comprehensive plan.

🔧 Using tool: Task
   subagent_type: Plan
   description: Plan comparison mode feature
   prompt: |
     Analyze the project structure and create a detailed plan for a "comparison mode"
     that runs the same prompt on all 4 versions and shows a side-by-side comparison.

     Consider:
     1. How to run all versions with the same input
     2. How to capture and format outputs
     3. UI/UX for displaying comparisons
     4. Error handling for version-specific issues

📋 Plan agent report:

## Comparison Mode Implementation Plan

### Phase 1: Research & Design (Use Explore agent)
- Analyze current launcher.py structure
- Identify shared conversation loop patterns
- Design comparison output format

### Phase 2: Core Implementation
1. Create comparison_mode.py
   - Function to run prompt on single version
   - Function to run on all versions in parallel
   - Response formatter

2. Update launcher.py
   - Add new menu option: "5 → Comparison Mode"
   - Integrate comparison_mode functionality

3. Create comparison output template
   - Side-by-side table format
   - Response time tracking
   - Token usage comparison

### Phase 3: Testing
- Test with simple prompts
- Test with tool-using prompts
- Test error handling

Would you like to proceed with Phase 1?

---

👤 You:
Yes! Start with Phase 1. Use the Explore agent to analyze the launcher structure.

🤖 Claude:
🔧 Using tool: Task
   subagent_type: Explore
   description: Analyze launcher.py structure for comparison mode integration

[Continues with full implementation...]
```

### 이 시나리오에서 사용:
- ✅ **Task (Plan)** - 전체 계획 수립
- ✅ **Task (Explore)** - 코드베이스 분석
- ✅ **Read** - 기존 코드 읽기
- ✅ **Write** - 새 파일 생성
- ✅ **Edit** - 기존 파일 수정
- ✅ **Bash** - 테스트 실행
- ✅ **Task (General)** - 복잡한 멀티스텝 작업

---

## 📝 사용 팁

### 1. Subagent 활용 시점

| Subagent | 사용 시점 | 예시 |
|----------|----------|------|
| **Explore** | 파일 찾기, 코드 검색 | "Find all files that use asyncio" |
| **Plan** | 복잡한 기능 구현 전 | "Plan how to add authentication" |
| **General** | 자동화된 멀티스텝 작업 | "Refactor all similar code patterns" |

### 2. Tool 조합 패턴

**패턴 1: 분석 → 수정 → 테스트**
```
Grep → Read → Edit → Bash
```

**패턴 2: 탐색 → 계획 → 구현**
```
Task(Explore) → Task(Plan) → Write/Edit → Bash
```

**패턴 3: 반복적 개선**
```
Read → Edit → Bash → (피드백 기반 반복)
```

### 3. 효율적인 프롬프트

❌ **나쁜 예:**
```
"Fix the code"
```

✅ **좋은 예:**
```
"Use Grep to find all TODO comments, then use the Explore agent
to analyze which ones are most important based on the codebase
structure, and create a prioritized list"
```

---

## 🚀 실전 연습 과제

### 초급
1. README.md 읽고 요약하기
2. 모든 Python 파일 찾기
3. 특정 함수 찾아서 읽기

### 중급
4. 중복 코드 찾아서 리팩토링하기
5. 새 테스트 파일 작성하고 실행하기
6. Explore agent로 프로젝트 분석 후 문서 생성

### 고급
7. Plan agent로 새 기능 계획 후 구현
8. 모든 버전에 동일한 기능 추가
9. 복잡한 멀티스텝 리팩토링 수행

---

## 💡 다음 단계

이 예시들을 launcher.py에서 직접 시도해보세요:

```bash
uv run python launcher.py
```

각 버전에서 동일한 태스크를 수행하고 차이점을 경험해보세요!

---

**Happy Coding! 🎉**
