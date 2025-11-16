"""
시스템 프롬프트의 도구 설명 vs 실제 @tool docstring 일치 확인
"""

import sys
sys.path.insert(0, '/Users/jd/Documents/workspace/custom-claude-code/src')

from custom_claude_code.v2_langgraph.tools import TOOLS

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 시스템 프롬프트에 있는 설명 (nodes.py 86-97번 줄)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SYSTEM_PROMPT_DESCRIPTIONS = {
    "read_file": "줄 번호와 함께 파일 읽기",
    "write_file": "파일 생성 또는 덮어쓰기",
    "edit_file": "정확한 문자열 치환으로 파일 편집",
    "glob_files": "glob 패턴으로 파일 찾기 (예: \"**/*.ts\")",
    "grep_code": "정규식으로 코드 검색",
    "run_bash": "bash 명령어 실행",
    "todo_write": "진행 상황 추적을 위한 작업 목록 생성 및 관리",
    "exit_plan_mode": "구현 계획 제시 및 계획 단계 종료",
    "task_tool": "복잡한 작업을 위한 전문 subagent 실행",
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 비교
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("=" * 80)
print("🔍 시스템 프롬프트 vs 실제 @tool Docstring 비교")
print("=" * 80)

mismatches = []

for tool in TOOLS:
    tool_name = tool.name

    # 실제 docstring (첫 문장만)
    actual_desc = tool.description.split('\n')[0].strip()

    # 시스템 프롬프트 설명
    system_desc = SYSTEM_PROMPT_DESCRIPTIONS.get(tool_name, "❌ 없음")

    # 비교
    match = "✅" if tool_name in SYSTEM_PROMPT_DESCRIPTIONS else "❌"

    print(f"\n{'=' * 80}")
    print(f"📦 {tool_name}")
    print(f"{'=' * 80}")
    print(f"\n시스템 프롬프트 ({match}):")
    print(f"  {system_desc}")
    print(f"\n실제 @tool Docstring:")
    print(f"  {actual_desc}")

    # 차이점 분석
    if match == "✅":
        if system_desc.lower() in actual_desc.lower() or actual_desc.lower() in system_desc.lower():
            print(f"\n💡 일치도: 부분 일치 (acceptable)")
        else:
            print(f"\n⚠️  일치도: 의미는 유사하지만 표현 다름")
            mismatches.append({
                "tool": tool_name,
                "system": system_desc,
                "actual": actual_desc
            })
    else:
        print(f"\n❌ 시스템 프롬프트에 없음!")
        mismatches.append({
            "tool": tool_name,
            "system": "❌ 없음",
            "actual": actual_desc
        })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 요약
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n\n" + "=" * 80)
print("📊 요약")
print("=" * 80)

if mismatches:
    print(f"\n⚠️  {len(mismatches)}개 도구에서 불일치 발견:")
    for m in mismatches:
        print(f"\n  • {m['tool']}:")
        print(f"    시스템: {m['system']}")
        print(f"    실제:   {m['actual']}")
else:
    print("\n✅ 모든 도구 설명이 일치합니다!")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 권장사항
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n\n" + "=" * 80)
print("💡 권장사항")
print("=" * 80)

print("""
🎯 질문: 시스템 프롬프트에 도구 설명을 넣어야 하나?

앞서 분석한 내용을 다시 상기하면:

1. @tool의 JSON Schema = WHAT (기술적 정보)
   - 파라미터 타입, 설명 등

2. 시스템 프롬프트 = WHEN & HOW (사용 정책)
   - 언제 사용하는가
   - 어떻게 사용하는가
   - 다른 도구와의 관계

📌 현재 문제:

시스템 프롬프트의 도구 설명이:
  - 너무 간략함 (1줄 요약)
  - 실제 docstring과 표현이 다름
  - 중복된 정보 (JSON Schema에 이미 있음)

📌 두 가지 접근법:

┌─────────────────────────────────────────────────────────────────┐
│ 접근법 A: 시스템 프롬프트에서 도구 목록 제거                    │
├─────────────────────────────────────────────────────────────────┤
│ ✅ 장점:                                                         │
│   - 중복 제거                                                   │
│   - 유지보수 간편 (한 곳만 수정)                                │
│   - @tool docstring이 single source of truth                    │
│                                                                 │
│ ❌ 단점:                                                         │
│   - LLM이 도구 목록을 한눈에 파악하기 어려움                    │
│   - 사용 정책을 도구별로 설명하기 어려움                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 접근법 B: 시스템 프롬프트에서 사용 정책만 강조 (권장!)         │
├─────────────────────────────────────────────────────────────────┤
│ ✅ 장점:                                                         │
│   - 도구 목록으로 빠른 참조 가능                                │
│   - 사용 정책과 패턴 명확히 전달                                │
│   - Best practices 명시 가능                                    │
│                                                                 │
│ 📝 형식:                                                        │
│   간단한 1줄 요약 + 사용 정책 추가                              │
│                                                                 │
│ 예시:                                                           │
│   # Tools                                                       │
│                                                                 │
│   Available tools:                                              │
│   - read_file, write_file, edit_file: 파일 작업               │
│   - glob_files, grep_code: 파일 검색                           │
│   - run_bash: 시스템 명령 실행                                  │
│   - todo_write: 작업 관리                                       │
│   - task_tool: Subagent 실행                                    │
│                                                                 │
│   Tool usage policy:                                            │
│   - ⚠️ ALWAYS use dedicated tools, NEVER use bash for files    │
│     ❌ run_bash("cat file.txt")                                 │
│     ✅ read_file("file.txt")                                    │
│                                                                 │
│   - 🔍 For exploration, use task_tool with Explore agent       │
│   - 📋 Use todo_write for multi-step tasks                     │
│   - 🚀 Parallelize independent tool calls                      │
└─────────────────────────────────────────────────────────────────┘

🎯 최종 권장: 접근법 B

이유:
1. 도구 목록 유지 (빠른 참조)
2. 하지만 간략하게 (그룹화)
3. 사용 정책에 집중 (실제 가치)
4. 중복 최소화 (상세한 건 @tool에 맡김)
""")

print("\n" + "=" * 80)
print("📝 개선된 # Tools 섹션 예시")
print("=" * 80)

print("""
# Tools

Available tools (도구 상세 설명은 각 도구 호출 시 자동으로 제공됩니다):

📁 File Operations:
  - read_file, write_file, edit_file

🔍 Search & Discovery:
  - glob_files (파일명 패턴), grep_code (코드 검색)

⚙️ Execution:
  - run_bash (시스템 명령)

📋 Task Management:
  - todo_write (작업 추적), exit_plan_mode (계획 모드 종료)

🤖 Agents:
  - task_tool (Explore/Plan/General subagent 실행)

## Tool Usage Policy

⚠️ IMPORTANT: 항상 전문 도구를 사용하세요. bash로 파일 작업 금지!

❌ 잘못된 사용:
  run_bash("cat file.txt")       # read_file 사용!
  run_bash("find . -name *.py")  # glob_files 사용!
  run_bash("grep pattern file")  # grep_code 사용!

✅ 올바른 사용:
  read_file("file.txt")
  glob_files("**/*.py")
  grep_code("pattern", path="file")

🔍 탐색 작업은 Task 도구 사용:
  - 코드베이스 이해: task_tool(subagent_type="Explore", ...)
  - 구현 계획: task_tool(subagent_type="Plan", ...)

🚀 독립적인 도구는 병렬 실행:
  read_file("a.py"), read_file("b.py")  # 동시 실행!

📋 복잡한 작업은 todo_write로 추적:
  - 3단계 이상 작업
  - 사용자에게 진행 상황 가시화
""")
