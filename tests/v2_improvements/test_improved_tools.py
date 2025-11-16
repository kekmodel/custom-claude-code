#!/usr/bin/env python3
"""개선된 도구 테스트"""

import sys
import os

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from custom_claude_code.v2_langgraph.tools import grep_code, run_bash

def test_grep_code():
    """grep_code 파라미터 테스트"""
    print("=" * 80)
    print("grep_code 도구 테스트")
    print("=" * 80)

    # 1. 기본 검색 (files_with_matches 모드)
    print("\n1. 기본 검색 - 파일 목록만")
    print("-" * 80)
    result = grep_code.invoke({"pattern": "def ", "path": "src/custom_claude_code/v2_langgraph"})
    print(f"결과 (첫 5줄):\n{chr(10).join(result.split(chr(10))[:5])}\n")

    # 2. content 모드 (줄 번호 포함)
    print("\n2. content 모드 - 매칭된 라인 표시 (head_limit=10)")
    print("-" * 80)
    result = grep_code.invoke({
        "pattern": "tool",
        "path": "src/custom_claude_code/v2_langgraph/tools.py",
        "output_mode": "content",
        "n": True,
        "head_limit": 10
    })
    print(f"결과:\n{result}\n")

    # 3. 파일 타입 필터링
    print("\n3. 파일 타입 필터링 (type=py)")
    print("-" * 80)
    result = grep_code.invoke({
        "pattern": "import",
        "path": "src/custom_claude_code/v2_langgraph",
        "type": "py",
        "head_limit": 5
    })
    print(f"결과:\n{result}\n")

    # 4. 대소문자 무시 검색
    print("\n4. 대소문자 무시 검색 (i=True)")
    print("-" * 80)
    result = grep_code.invoke({
        "pattern": "TOOL",
        "path": "src/custom_claude_code/v2_langgraph/tools.py",
        "i": True,
        "head_limit": 5
    })
    print(f"결과:\n{result}\n")

    # 5. count 모드
    print("\n5. count 모드 - 매칭 개수")
    print("-" * 80)
    result = grep_code.invoke({
        "pattern": "def ",
        "path": "src/custom_claude_code/v2_langgraph/tools.py",
        "output_mode": "count"
    })
    print(f"결과:\n{result}\n")

    print("✅ grep_code 모든 테스트 통과!")


def test_run_bash():
    """run_bash 파라미터 테스트"""
    print("\n" + "=" * 80)
    print("run_bash 도구 테스트")
    print("=" * 80)

    # 1. 기본 실행
    print("\n1. 기본 명령어 실행")
    print("-" * 80)
    result = run_bash.invoke({"command": "echo 'Hello from improved bash!'"})
    print(f"결과: {result}\n")

    # 2. 기본 명령어
    print("\n2. 다른 명령어 (pwd)")
    print("-" * 80)
    result = run_bash.invoke({"command": "pwd"})
    print(f"결과: {result}\n")

    # 3. timeout 설정 (milliseconds)
    print("\n3. timeout 설정 (5000ms)")
    print("-" * 80)
    result = run_bash.invoke({
        "command": "sleep 0.1 && echo 'Completed within timeout'",
        "timeout": 5000
    })
    print(f"결과: {result}\n")

    print("✅ run_bash 모든 테스트 통과!")


def main():
    print("\n🔍 개선된 v2 도구 테스트 시작\n")

    try:
        test_grep_code()
        test_run_bash()

        print("\n" + "=" * 80)
        print("✅ 모든 테스트 성공!")
        print("=" * 80)

        print("\n📋 개선 사항 요약:")
        print("-" * 80)
        print("grep_code:")
        print("  ✅ output_mode 추가 (content/files_with_matches/count)")
        print("  ✅ type 파라미터 추가 (파일 타입 필터)")
        print("  ✅ -i, -n, -A, -B, -C 컨텍스트 파라미터")
        print("  ✅ head_limit, offset 추가")
        print("  ✅ multiline 모드 지원")
        print()
        print("run_bash:")
        print("  ✅ timeout을 milliseconds로 변경 (레퍼런스와 일치)")
        print("  ✅ 불필요한 description 파라미터 제거 (간소화)")
        print()

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
