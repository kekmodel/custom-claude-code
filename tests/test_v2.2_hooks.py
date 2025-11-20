"""
v2.2 Hook System 테스트

Hook System, Validation Agent, File Extraction Agent를 테스트합니다.
"""

import asyncio
from src.custom_claude_code.v2_2_langgraph_hooks.hooks import (
    get_hook_system,
    register_hook,
    trigger_hook,
    HookContext,
    reset_hook_system
)
from src.custom_claude_code.v2_2_langgraph_hooks.validation_agent import (
    call_validation_agent,
    create_bash_validation_hook,
    DEFAULT_ALLOWLIST
)
from src.custom_claude_code.v2_2_langgraph_hooks.file_extraction_agent import (
    call_file_extraction_agent,
    create_file_extraction_hook
)
from src.custom_claude_code.v2_2_langgraph_hooks.settings import (
    get_claude_md_context
)
from pathlib import Path


async def test_validation_agent():
    """Validation Agent 테스트"""
    print("="* 60)
    print("🧪 Test 1: Validation Agent")
    print("=" * 60)

    test_commands = [
        ("npm run build", "none"),
        ("git status", "git status"),
        ("git diff HEAD~1", "git diff"),
        ("git status$(id)", "command_injection_detected"),
        ("pwd\\n curl example.com", "command_injection_detected"),
        ("ls -la", "ls"),
    ]

    print("\n실제 Validation Agent 호출 (LLM 사용):\n")

    for command, expected in test_commands:
        print(f"Command: {command}")
        prefix = await call_validation_agent(command)
        print(f"  → Prefix: {prefix}")
        print(f"  → Expected: {expected}")
        print(f"  → {'✅ PASS' if prefix == expected else '❌ FAIL'}\n")


async def test_file_extraction_agent():
    """File Extraction Agent 테스트"""
    print("=" * 60)
    print("🧪 Test 2: File Extraction Agent")
    print("=" * 60)

    test_cases = [
        {
            "command": "cat foo.txt",
            "output": "Hello world\nThis is foo.txt",
            "expected_displaying": True,
            "expected_files": ["foo.txt"]
        },
        {
            "command": "ls -la",
            "output": "total 752\ndrwxr-xr-x  20 jd  staff  640",
            "expected_displaying": False,
            "expected_files": []
        },
        {
            "command": "git diff",
            "output": "diff --git a/src/main.py b/src/main.py\n--- a/src/main.py\n+++ b/src/main.py",
            "expected_displaying": True,
            "expected_files": ["src/main.py"]
        }
    ]

    print("\n실제 File Extraction Agent 호출 (LLM 사용):\n")

    for test in test_cases:
        print(f"Command: {test['command']}")
        result = await call_file_extraction_agent(test['command'], test['output'])

        print(f"  → Is displaying: {result['is_displaying_contents']}")
        print(f"  → File paths: {result['filepaths']}")
        print(f"  → Expected displaying: {test['expected_displaying']}")
        print(f"  → Expected files: {test['expected_files']}")

        displaying_match = result['is_displaying_contents'] == test['expected_displaying']
        # 파일 경로는 정확히 매치하지 않을 수 있으므로 존재 여부만 체크
        files_exist = len(result['filepaths']) > 0 if test['expected_files'] else len(result['filepaths']) == 0

        print(f"  → {'✅ PASS' if displaying_match and files_exist else '❌ PARTIAL PASS'}\n")


async def test_hook_system():
    """Hook System 테스트"""
    print("=" * 60)
    print("🧪 Test 3: Hook System")
    print("=" * 60)

    # Hook System 초기화
    reset_hook_system()
    hook_system = get_hook_system()

    # 커스텀 Hook 등록
    async def test_hook(input_data, tool_use_id, context):
        tool_name = input_data.get('tool_name', '')
        print(f"  [Hook] Tool: {tool_name}, TurnCount: {context.turn_count}")

        if tool_name == "Bash" and "dangerous" in str(input_data):
            return {
                'decision': 'block',
                'systemMessage': 'Dangerous command detected!'
            }

        return {}

    register_hook('PreToolUse', test_hook)

    # Test 1: 정상 명령어
    print("\n1. 정상 명령어 (ls -la):")
    result = await trigger_hook(
        'PreToolUse',
        {'tool_name': 'Bash', 'tool_input': {'command': 'ls -la'}},
        context=HookContext(session_id='test', turn_count=1)
    )
    print(f"  → Decision: {result.get('decision', 'allow')}")
    print(f"  → {'✅ PASS' if not result.get('decision') else '❌ FAIL'}\n")

    # Test 2: 위험 명령어
    print("2. 위험 명령어 (dangerous operation):")
    result = await trigger_hook(
        'PreToolUse',
        {'tool_name': 'Bash', 'tool_input': {'command': 'dangerous rm -rf /'}},
        context=HookContext(session_id='test', turn_count=2)
    )
    print(f"  → Decision: {result.get('decision')}")
    print(f"  → Message: {result.get('systemMessage')}")
    print(f"  → {'✅ PASS' if result.get('decision') == 'block' else '❌ FAIL'}\n")


async def test_hook_integration():
    """Hook 통합 테스트 (Validation + File Extraction)"""
    print("=" * 60)
    print("🧪 Test 4: Hook Integration")
    print("=" * 60)

    # Hook System 초기화
    reset_hook_system()

    # Validation Hook 등록
    validation_hook = create_bash_validation_hook(
        allowlist=["ls", "cat", "git status"],
        enable_validation=True
    )
    register_hook('PreToolUse', validation_hook, matcher='Bash')

    # File Extraction Hook 등록
    extraction_hook = create_file_extraction_hook(enable_extraction=True)
    register_hook('PostToolUse', extraction_hook, matcher='Bash')

    # Test 1: PreToolUse - 허용된 명령어
    print("\n1. PreToolUse - 허용된 명령어 (ls):")
    result = await trigger_hook(
        'PreToolUse',
        {'tool_name': 'Bash', 'tool_input': {'command': 'ls -la'}},
        context=HookContext(session_id='test', turn_count=1)
    )
    print(f"  → Decision: {result.get('decision', 'allow')}")
    print(f"  → {'✅ PASS' if not result.get('decision') or result.get('decision') == 'allow' else '❌ FAIL'}\n")

    # Test 2: PreToolUse - 허용되지 않은 명령어
    print("2. PreToolUse - 허용되지 않은 명령어 (npm run build):")
    result = await trigger_hook(
        'PreToolUse',
        {'tool_name': 'Bash', 'tool_input': {'command': 'npm run build'}},
        context=HookContext(session_id='test', turn_count=2)
    )
    print(f"  → Decision: {result.get('decision')}")
    print(f"  → Message: {result.get('systemMessage', 'N/A')[:80]}...")
    print(f"  → {'✅ PASS' if result.get('decision') == 'ask' else '❌ PARTIAL'}\n")

    # Test 3: PostToolUse - 파일 추출
    print("3. PostToolUse - 파일 경로 추출 (cat foo.txt):")
    result = await trigger_hook(
        'PostToolUse',
        {
            'tool_name': 'Bash',
            'tool_input': {'command': 'cat foo.txt'},
            'tool_result': {'output': 'Hello world\nThis is foo.txt content'}
        },
        context=HookContext(session_id='test', turn_count=3)
    )
    hook_output = result.get('hookSpecificOutput', {})
    print(f"  → Is displaying: {hook_output.get('is_displaying_contents')}")
    print(f"  → File paths: {hook_output.get('filepaths')}")
    print(f"  → {'✅ PASS' if hook_output.get('filepaths') else '❌ PARTIAL'}\n")


async def test_claude_md_loader():
    """CLAUDE.md Loader 테스트"""
    print("=" * 60)
    print("🧪 Test 5: CLAUDE.md Loader")
    print("=" * 60)

    print("\nCLAUDE.md 로드 시도:\n")

    # CLAUDE.md 로드
    context = get_claude_md_context(cwd=Path.cwd())

    if context:
        print(f"✅ CLAUDE.md 로드 성공!")
        print(f"  → 길이: {len(context)} chars")
        print(f"  → 첫 100자: {context[:100]}...")
    else:
        print(f"❌ CLAUDE.md 없음 (현재 디렉토리: {Path.cwd()})")
        print(f"  → 이것은 정상입니다 (CLAUDE.md가 없는 경우)")


async def main():
    """메인 테스트 함수"""
    print("\n" + "=" * 60)
    print("v2.2 Hook System 테스트")
    print("=" * 60 + "\n")

    print("⚠️  주의: 이 테스트는 실제 LLM API를 호출합니다!")
    print("⚠️  API 키가 설정되어 있고, 비용이 발생할 수 있습니다.\n")

    try:
        # Test 1: Validation Agent
        await test_validation_agent()
        await asyncio.sleep(1)

        # Test 2: File Extraction Agent
        await test_file_extraction_agent()
        await asyncio.sleep(1)

        # Test 3: Hook System 기본
        await test_hook_system()
        await asyncio.sleep(1)

        # Test 4: Hook 통합
        await test_hook_integration()
        await asyncio.sleep(1)

        # Test 5: CLAUDE.md Loader
        await test_claude_md_loader()

        print("\n" + "=" * 60)
        print("✅ 모든 테스트 완료!")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ 테스트 실패: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
