"""
실험: 시스템 프롬프트에 도구 정의가 필요한가?

비교:
1. JSON Schema만 사용 (tool.args_schema)
2. 시스템 프롬프트 가이드라인 추가
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. @tool이 자동 생성하는 것 (JSON Schema)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

JSON_SCHEMA_ONLY = """
{
  "name": "grep_code",
  "description": "A powerful search tool built on ripgrep. Supports full regex syntax...",
  "parameters": {
    "properties": {
      "pattern": {
        "type": "string",
        "description": "The regular expression pattern to search for"
      },
      "path": {
        "type": "string",
        "description": "File or directory to search in"
      }
    }
  }
}
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 실제 Claude Code가 시스템 프롬프트에 추가하는 것
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SYSTEM_PROMPT_GUIDANCE = """
## Grep
A powerful search tool built on ripgrep

  Usage:
  - ALWAYS use Grep for search tasks. NEVER invoke `grep` or `rg` as a Bash command.  👈 정책!
  - Supports full regex syntax (e.g., "log.*Error", "function\\s+\\w+")
  - Filter files with glob parameter (e.g., "*.js", "**/*.tsx")
  - Output modes: "content" shows matching lines, "files_with_matches" shows only file paths
  - Use Task tool for open-ended searches requiring multiple rounds  👈 조합 패턴!
  - Pattern syntax: Uses ripgrep (not grep) - literal braces need escaping  👈 주의사항!
  - Multiline matching: By default patterns match within single lines only  👈 제약사항!
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 비교 분석
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("=" * 80)
print("🔍 @tool JSON Schema vs 시스템 프롬프트 가이드라인 비교")
print("=" * 80)

print("\n1️⃣ @tool이 자동 생성하는 것 (JSON Schema):")
print("=" * 80)
print(JSON_SCHEMA_ONLY)

print("\n\n2️⃣ 시스템 프롬프트에 추가하는 것 (사용 가이드라인):")
print("=" * 80)
print(SYSTEM_PROMPT_GUIDANCE)

print("\n\n3️⃣ 차이점 분석:")
print("=" * 80)

print("""
┌─────────────────────────┬───────────────────┬────────────────────────┐
│ 정보 유형                │ JSON Schema       │ 시스템 프롬프트        │
├─────────────────────────┼───────────────────┼────────────────────────┤
│ 도구 이름                │ ✅ 있음           │ ✅ 있음                │
│ 도구 설명                │ ✅ 있음           │ ✅ 있음                │
│ 파라미터 타입            │ ✅ 있음           │ ❌ 없음                │
│ 파라미터 설명            │ ✅ 있음 (parse)   │ ❌ 없음                │
├─────────────────────────┼───────────────────┼────────────────────────┤
│ 사용 시기 (when)         │ ❌ 없음           │ ✅ "ALWAYS use..."     │
│ 사용 금지 (when NOT)     │ ❌ 없음           │ ✅ "NEVER invoke..."   │
│ Best Practices           │ ❌ 없음           │ ✅ 여러 개             │
│ 다른 도구와 조합         │ ❌ 없음           │ ✅ "Use Task tool..."  │
│ 주의사항                 │ ❌ 없음           │ ✅ "literal braces..." │
│ 제약사항                 │ ❌ 없음           │ ✅ "single lines only" │
│ 예시                     │ ❌ 없음           │ ✅ 여러 개             │
└─────────────────────────┴───────────────────┴────────────────────────┘
""")

print("\n4️⃣ 결론:")
print("=" * 80)
print("""
🎯 질문: 시스템 프롬프트에 도구 정의가 필요한가?

📌 이론적 답변: NO
   - @tool이 생성한 JSON Schema만으로 LLM은 도구를 **호출할 수 있습니다**
   - 파라미터 타입, 설명 등 모든 기술적 정보가 포함됨

📌 실무적 답변: YES (강력 권장!)
   - JSON Schema는 **WHAT** (무엇을 할 수 있는가)
   - 시스템 프롬프트는 **WHEN & HOW** (언제, 어떻게 사용해야 하는가)

📊 시스템 프롬프트가 제공하는 추가 가치:

1. **사용 정책 (Policy)**
   - "ALWAYS use Grep" → LLM이 우선순위 이해
   - "NEVER invoke grep as Bash" → 잘못된 사용 방지

2. **조합 패턴 (Patterns)**
   - "Use Task tool for open-ended searches" → 도구 간 협력

3. **주의사항 (Gotchas)**
   - "literal braces need escaping" → 흔한 실수 방지
   - "single lines only by default" → 제약사항 이해

4. **컨텍스트 (Context)**
   - "Uses ripgrep (not grep)" → 기대치 설정
   - Output modes 설명 → 옵션 이해

🚀 권장사항:

✅ @tool(parse_docstring=True) 사용:
   - 파라미터별 설명 자동 생성
   - JSON Schema 품질 향상

✅ 시스템 프롬프트에 사용 가이드라인 추가:
   - ALWAYS/NEVER 정책
   - Best practices
   - 조합 패턴
   - 주의사항

❌ 중복 제거:
   - 파라미터 타입/설명은 @tool에 맡김
   - 시스템 프롬프트는 정책과 패턴에 집중

💡 이상적인 구조:

@tool(parse_docstring=True)         # 기술적 정보 (WHAT)
+
시스템 프롬프트 가이드라인           # 사용 정책 (WHEN & HOW)
=
최고의 tool calling 정확도! 🎯
""")

print("\n5️⃣ 실제 예시 - Claude Code의 Bash 도구:")
print("=" * 80)
print("""
@tool에서 자동 생성된 Schema:
{
  "name": "Bash",
  "parameters": {
    "command": {"type": "string", "description": "The command to execute"},
    "timeout": {"type": "number", "description": "Optional timeout in ms"}
  }
}

시스템 프롬프트에 추가된 가이드라인:
- IMPORTANT: This tool is for terminal operations like git, npm, docker
- DO NOT use it for file operations - use specialized tools instead
- Always quote file paths that contain spaces
- When multiple commands: use && for sequential, parallel for independent
- NEVER run destructive commands without user confirmation
- Examples: ✅ git status, ❌ cat file.txt (use Read instead)

👆 이 가이드라인이 없으면 LLM은 자주 실수합니다!
   - cat으로 파일 읽기 (Read 대신)
   - find로 파일 찾기 (Glob 대신)
   - 경로에 공백 있을 때 따옴표 누락
""")
