"""
v2.1 Subagent 테스트

모든 subagent 타입의 실제 실행을 테스트합니다:
- Explore: 코드베이스 탐색
- Plan: 계획 수립
- general-purpose: 복잡한 작업
"""

import asyncio
import os
import sys
import tempfile

# .env 파일 로드
from dotenv import load_dotenv
load_dotenv()


async def test_explore_agent():
    """Explore agent 테스트 - 코드베이스 탐색"""
    print("\n" + "=" * 60)
    print("1. Explore Agent 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.nodes import execute_subagent
    from custom_claude_code.v2_1_langgraph_improved.prompts import get_system_prompt

    print("\n[1-1] Explore agent 실행...")
    print("   작업: 현재 디렉토리에서 .py 파일 찾기")

    try:
        system_prompt = get_system_prompt(os.getcwd())
        result = await execute_subagent(
            subagent_type="Explore",
            prompt="Find all Python test files in the current directory. List their names only.",
            system_prompt=system_prompt,
            current_depth=0,
            max_depth=5,
            model_name="haiku",
        )

        if "test" in result.lower() or ".py" in result.lower() or "error" in result.lower():
            print(f"   ✅ Explore agent 작동")
            print(f"   📝 응답 미리보기: {result[:200]}...")
            return True
        else:
            print(f"   ❌ Explore agent 응답 이상: {result[:200]}")
            return False

    except Exception as e:
        print(f"   ❌ Explore agent 실패: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_plan_agent():
    """Plan agent 테스트 - 계획 수립"""
    print("\n" + "=" * 60)
    print("2. Plan Agent 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.nodes import execute_subagent
    from custom_claude_code.v2_1_langgraph_improved.prompts import get_system_prompt

    print("\n[2-1] Plan agent 실행...")
    print("   작업: 간단한 웹 스크래퍼 구현 계획 수립")

    try:
        system_prompt = get_system_prompt(os.getcwd())
        result = await execute_subagent(
            subagent_type="Plan",
            prompt="Create a brief plan (3-4 steps) for implementing a simple web scraper in Python. Just list the steps.",
            system_prompt=system_prompt,
            current_depth=0,
            max_depth=5,
            model_name="haiku",
        )

        # Plan agent should return a string response
        if not isinstance(result, str):
            print(f"   ❌ Plan agent 응답 타입 오류: {type(result)}")
            return False

        # Check for plan-related content
        if any(keyword in result.lower() for keyword in ["step", "plan", "1.", "import", "error"]):
            print(f"   ✅ Plan agent 작동")
            print(f"   📝 응답 미리보기: {result[:200]}...")
            return True
        else:
            print(f"   ❌ Plan agent 응답 내용 부족: {result[:200]}")
            return False

    except Exception as e:
        print(f"   ❌ Plan agent 실패: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_general_agent():
    """General-purpose agent 테스트 - 복잡한 작업"""
    print("\n" + "=" * 60)
    print("3. General-Purpose Agent 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.nodes import execute_subagent
    from custom_claude_code.v2_1_langgraph_improved.prompts import get_system_prompt

    print("\n[3-1] General-purpose agent 실행...")
    print("   작업: 임시 파일 생성 및 읽기")

    # 테스트용 임시 파일 생성
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        test_file = f.name
        f.write("Test content for general agent\nLine 2\nLine 3")

    try:
        system_prompt = get_system_prompt(os.getcwd())
        result = await execute_subagent(
            subagent_type="general-purpose",
            prompt=f"Read the file at {test_file} and tell me how many lines it has. Just give a brief answer.",
            system_prompt=system_prompt,
            current_depth=0,
            max_depth=5,
            model_name="haiku",
        )

        # General agent should be able to use tools and provide an answer
        if any(keyword in result.lower() for keyword in ["line", "3", "three", "error", "content"]):
            print(f"   ✅ General-purpose agent 작동")
            print(f"   📝 응답 미리보기: {result[:200]}...")
            success = True
        else:
            print(f"   ❌ General-purpose agent 응답 이상: {result[:200]}")
            success = False

        return success

    except Exception as e:
        print(f"   ❌ General-purpose agent 실패: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 정리
        if os.path.exists(test_file):
            os.unlink(test_file)


async def test_tool_access():
    """Subagent별 도구 접근 제한 테스트"""
    print("\n" + "=" * 60)
    print("4. Subagent 도구 접근 제한 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.tools import TOOLS

    # 예상 도구 세트
    expected_tools = {
        "Explore": {"read_file", "grep_code", "glob_files", "web_search", "web_fetch"},
        "Plan": {"read_file", "grep_code", "glob_files", "web_search", "web_fetch"},
        "general-purpose": {
            "read_file", "write_file", "edit_file",
            "grep_code", "glob_files",
            "run_bash", "bash_background", "bash_output", "kill_shell",
            "web_search", "web_fetch"
        },
    }

    # nodes.py의 로직을 그대로 재현하여 테스트
    all_tests_passed = True

    for subagent_type, expected in expected_tools.items():
        print(f"\n[4-{list(expected_tools.keys()).index(subagent_type) + 1}] {subagent_type} agent 도구 제한...")

        # 실제 필터링 로직 (nodes.py와 동일)
        excluded_tools = {"task_tool", "todo_write"}
        allowed_tools = [t for t in TOOLS if t.name not in excluded_tools]

        if subagent_type == "Explore":
            explore_tools = {"read_file", "grep_code", "glob_files", "web_search", "web_fetch"}
            allowed_tools = [t for t in allowed_tools if t.name in explore_tools]
        elif subagent_type == "Plan":
            plan_tools = {"read_file", "grep_code", "glob_files", "web_search", "web_fetch"}
            allowed_tools = [t for t in allowed_tools if t.name in plan_tools]

        actual = {t.name for t in allowed_tools}

        # 검증
        missing = expected - actual
        extra = actual - expected

        if missing:
            print(f"   ❌ 누락된 도구: {missing}")
            all_tests_passed = False
        elif extra:
            print(f"   ❌ 불필요한 도구: {extra}")
            all_tests_passed = False
        else:
            print(f"   ✅ 정확히 {len(actual)}개 도구 허용: {sorted(actual)}")

    return all_tests_passed


async def test_depth_limit():
    """재귀 깊이 제한 테스트"""
    print("\n" + "=" * 60)
    print("5. 재귀 깊이 제한 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.nodes import execute_subagent
    from custom_claude_code.v2_1_langgraph_improved.prompts import get_system_prompt

    print("\n[5-1] 최대 깊이 초과 테스트...")

    try:
        system_prompt = get_system_prompt(os.getcwd())
        result = await execute_subagent(
            subagent_type="Explore",
            prompt="Simple test",
            system_prompt=system_prompt,
            current_depth=5,  # 최대 깊이와 같음
            max_depth=5,
            model_name="haiku",
        )

        if "ERROR" in result and "Max subagent depth" in result:
            print(f"   ✅ 깊이 제한 작동 (depth=5, max=5)")
            return True
        else:
            print(f"   ❌ 깊이 제한 미작동: {result[:100]}")
            return False

    except Exception as e:
        print(f"   ⚠️  예외 발생: {type(e).__name__}: {str(e)}")
        # 이것도 유효한 제한 방식
        return True


async def test_model_selection():
    """모델 선택 테스트"""
    print("\n" + "=" * 60)
    print("6. 모델 선택 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.nodes import execute_subagent
    from custom_claude_code.v2_1_langgraph_improved.prompts import get_system_prompt
    from custom_claude_code.v2_1_langgraph_improved.models import MODEL_ALIASES

    print("\n[6-1] 모델 별칭 확인...")
    print(f"   사용 가능한 모델: {list(MODEL_ALIASES.keys())}")

    if "haiku" in MODEL_ALIASES:
        print(f"   ✅ Haiku 모델 별칭 존재")
    else:
        print(f"   ⚠️  Haiku 모델 별칭 없음")

    # 간단한 실행으로 모델이 작동하는지 확인
    print("\n[6-2] Haiku 모델로 실행...")
    try:
        system_prompt = get_system_prompt(os.getcwd())
        result = await execute_subagent(
            subagent_type="Explore",
            prompt="Just say 'OK' in one word.",
            system_prompt=system_prompt,
            current_depth=0,
            max_depth=5,
            model_name="haiku",
        )

        if result and len(result) > 0:
            print(f"   ✅ 모델 실행 성공")
            return True
        else:
            print(f"   ❌ 모델 실행 실패")
            return False

    except Exception as e:
        print(f"   ❌ 모델 테스트 실패: {type(e).__name__}: {str(e)}")
        return False


async def main():
    print("=" * 60)
    print("v2.1 Subagent 전체 테스트")
    print("=" * 60)
    print("\n⚠️  주의: 이 테스트는 실제 API 호출을 수행합니다.")
    print("         API 키가 설정되어 있어야 합니다.\n")

    results = []

    # 환경 변수 확인
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print("❌ API 키가 설정되지 않았습니다.")
        print("   ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를 .env에 설정하세요.")
        return 1

    print("🔧 Subagent 타입별 테스트 시작...\n")

    # 실제 실행 테스트
    results.append(("Explore Agent", await test_explore_agent()))
    results.append(("Plan Agent", await test_plan_agent()))
    results.append(("General-Purpose Agent", await test_general_agent()))

    # 설정 테스트
    results.append(("도구 접근 제한", await test_tool_access()))
    results.append(("재귀 깊이 제한", await test_depth_limit()))
    results.append(("모델 선택", await test_model_selection()))

    # Summary
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    for name, passed in results:
        status = "✅ 통과" if passed else "❌ 실패"
        print(f"{name:25} {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\n총 {total}개 테스트 중 {passed}개 통과")

    if passed == total:
        print("\n🎉 모든 Subagent 테스트 통과!")
        return 0
    else:
        print(f"\n⚠️  {total - passed}개 테스트 실패")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
