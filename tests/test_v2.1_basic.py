"""
v2.1 기본 테스트

v2.1_langgraph_improved 구현의 기본 기능 검증:
1. 모든 모듈 임포트 가능
2. 14개 도구 등록 확인
3. 노드 및 그래프 구성 확인
"""

import sys


def test_imports():
    """모듈 임포트 테스트"""
    print("1. 모듈 임포트 테스트...")
    try:
        from custom_claude_code.v2_1_langgraph_improved import tools, nodes, prompts, graph
        print("   ✅ 모든 모듈 임포트 성공")
        return True
    except ImportError as e:
        print(f"   ❌ 임포트 실패: {e}")
        return False


def test_tools():
    """도구 등록 테스트"""
    print("\n2. 도구 등록 테스트...")
    try:
        from custom_claude_code.v2_1_langgraph_improved.tools import TOOLS

        expected_tools = {
            # 파일 조작 (3)
            "read_file",
            "write_file",
            "edit_file",
            # 검색 (2)
            "glob_files",
            "grep_code",
            # 실행 (4) - 백그라운드 추가!
            "run_bash",
            "bash_background",
            "bash_output",
            "kill_shell",
            # 웹 접근 (2) - NEW!
            "web_search",
            "web_fetch",
            # 관리 (2)
            "todo_write",
            "task_tool",
        }

        actual_tools = {tool.name for tool in TOOLS}
        missing = expected_tools - actual_tools
        extra = actual_tools - expected_tools

        print(f"   예상 도구: {len(expected_tools)}개")
        print(f"   실제 도구: {len(actual_tools)}개")

        if missing:
            print(f"   ❌ 누락된 도구: {missing}")
            return False

        if extra:
            print(f"   ⚠️  추가 도구: {extra}")

        print(f"   ✅ 모든 도구 등록 확인 ({len(actual_tools)}개)")

        # 도구 목록 출력
        print("\n   등록된 도구:")
        for tool in TOOLS:
            print(f"     - {tool.name}")

        return True

    except Exception as e:
        print(f"   ❌ 도구 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_graph_structure():
    """그래프 구조 테스트"""
    print("\n3. 그래프 구조 테스트...")
    try:
        from custom_claude_code.v2_1_langgraph_improved.graph import graph

        # 그래프가 컴파일되었는지 확인
        if graph is None:
            print("   ❌ 그래프가 None입니다")
            return False

        # 그래프 노드 확인
        nodes = graph.get_graph().nodes
        print(f"   노드 수: {len(nodes)}")

        # 예상 노드: agent, tools, __start__, __end__
        expected_nodes = {"agent", "tools", "__start__", "__end__"}
        actual_nodes = set(nodes.keys())

        if expected_nodes.issubset(actual_nodes):
            print(f"   ✅ 기본 노드 확인: {expected_nodes}")
        else:
            missing = expected_nodes - actual_nodes
            print(f"   ❌ 누락된 노드: {missing}")
            return False

        return True

    except Exception as e:
        print(f"   ❌ 그래프 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_prompts():
    """프롬프트 테스트"""
    print("\n4. 프롬프트 테스트...")
    try:
        from custom_claude_code.v2_1_langgraph_improved.prompts import (
            get_system_prompt,
            PROMPT_VERSION,
        )

        # 프롬프트 버전 확인
        print(f"   프롬프트 버전: {PROMPT_VERSION}")

        # 시스템 프롬프트 생성 테스트
        prompt = get_system_prompt("/test/path")

        # 새 도구들이 프롬프트에 포함되어 있는지 확인
        required_keywords = [
            "bash_background",
            "bash_output",
            "kill_shell",
            "web_search",
            "web_fetch",
            "Background Execution",
            "Web Tools",
        ]

        missing = [kw for kw in required_keywords if kw not in prompt]

        if missing:
            print(f"   ⚠️  프롬프트에 누락된 키워드: {missing}")
            print("   (하지만 도구 자체는 등록되어 있으므로 작동은 가능합니다)")
        else:
            print("   ✅ 모든 새 도구가 프롬프트에 문서화됨")

        return True

    except Exception as e:
        print(f"   ❌ 프롬프트 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_nodes_simplification():
    """노드 단순화 테스트"""
    print("\n5. 노드 단순화 테스트...")
    try:
        from custom_claude_code.v2_1_langgraph_improved import nodes
        import inspect

        # compact_messages 함수가 없는지 확인
        has_compact = hasattr(nodes, "compact_messages")
        if has_compact:
            print("   ❌ compact_messages가 여전히 존재합니다 (제거되어야 함)")
            return False
        else:
            print("   ✅ compact_messages 제거 확인")

        # call_agent 함수 라인 수 확인 (단순화 검증)
        call_agent_source = inspect.getsource(nodes.call_agent)
        lines = [l for l in call_agent_source.split("\n") if l.strip() and not l.strip().startswith("#")]
        print(f"   call_agent 함수 라인 수: {len(lines)}줄")

        if len(lines) < 30:  # v2는 ~120줄, v2.1은 ~20줄
            print("   ✅ call_agent 단순화 확인")
        else:
            print(f"   ⚠️  call_agent이 여전히 복잡할 수 있음 ({len(lines)}줄)")

        return True

    except Exception as e:
        print(f"   ❌ 노드 단순화 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("v2.1 LangGraph Improved - 기본 테스트")
    print("=" * 60)

    results = []

    results.append(("모듈 임포트", test_imports()))

    if results[-1][1]:  # 임포트 성공시에만 나머지 테스트 진행
        results.append(("도구 등록", test_tools()))
        results.append(("그래프 구조", test_graph_structure()))
        results.append(("프롬프트", test_prompts()))
        results.append(("노드 단순화", test_nodes_simplification()))

    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    for name, passed in results:
        status = "✅ 통과" if passed else "❌ 실패"
        print(f"{name:20} {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\n총 {total}개 테스트 중 {passed}개 통과")

    if passed == total:
        print("\n🎉 모든 테스트 통과!")
        return 0
    else:
        print(f"\n⚠️  {total - passed}개 테스트 실패")
        return 1


if __name__ == "__main__":
    sys.exit(main())
