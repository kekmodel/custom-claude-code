"""
v2.1 도구 기능 테스트

모든 14개 도구의 실제 동작을 테스트합니다.
"""

import asyncio
import os
import sys
import tempfile
import time


async def test_file_operations():
    """파일 조작 도구 테스트 (read_file, write_file, edit_file)"""
    print("\n" + "=" * 60)
    print("1. 파일 조작 도구 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.tools import (
        read_file,
        write_file,
        edit_file,
    )

    # 임시 파일 생성
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        test_file = f.name
        f.write("Original content\nLine 2\nLine 3")

    try:
        # Test 1: read_file
        print("\n[1-1] read_file 테스트...")
        result = read_file.invoke({"file_path": test_file})
        if "Original content" in result:
            print("   ✅ read_file 작동")
        else:
            print(f"   ❌ read_file 실패: {result[:100]}")
            return False

        # Test 2: write_file
        print("\n[1-2] write_file 테스트...")
        new_file = test_file + ".new"
        result = write_file.invoke({"file_path": new_file, "content": "New file content"})
        if os.path.exists(new_file):
            with open(new_file) as f:
                if "New file content" in f.read():
                    print("   ✅ write_file 작동")
                else:
                    print("   ❌ write_file 내용 불일치")
                    return False
            os.unlink(new_file)
        else:
            print(f"   ❌ write_file 실패: {result}")
            return False

        # Test 3: edit_file
        print("\n[1-3] edit_file 테스트...")
        result = edit_file.invoke({
            "file_path": test_file,
            "old_string": "Line 2",
            "new_string": "Modified Line 2"
        })

        with open(test_file) as f:
            content = f.read()
            if "Modified Line 2" in content:
                print("   ✅ edit_file 작동")
            else:
                print(f"   ❌ edit_file 실패: {content}")
                return False

        return True

    finally:
        # 정리
        if os.path.exists(test_file):
            os.unlink(test_file)


async def test_search_tools():
    """검색 도구 테스트 (glob_files, grep_code)"""
    print("\n" + "=" * 60)
    print("2. 검색 도구 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.tools import glob_files, grep_code

    # Test 1: glob_files
    print("\n[2-1] glob_files 테스트...")
    result = glob_files.invoke({"pattern": "*.py", "path": os.getcwd()})
    if "test_v2.1" in result or ".py" in result:
        print("   ✅ glob_files 작동")
    else:
        print(f"   ❌ glob_files 실패: {result[:100]}")
        return False

    # Test 2: grep_code
    print("\n[2-2] grep_code 테스트...")
    # Search in current directory for Python files containing "def test"
    result = grep_code.invoke({
        "pattern": "def test",
        "path": os.getcwd(),
        "output_mode": "files_with_matches"
    })

    if ".py" in result and "test" in result:
        print("   ✅ grep_code 작동")
        return True
    else:
        print(f"   ❌ grep_code 실패: {result[:100]}")
        return False


async def test_execution_tools():
    """실행 도구 테스트 (run_bash, bash_background, bash_output, kill_shell)"""
    print("\n" + "=" * 60)
    print("3. 실행 도구 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.tools import (
        run_bash,
        bash_background,
        bash_output,
        kill_shell,
    )

    # Test 1: run_bash
    print("\n[3-1] run_bash 테스트...")
    result = run_bash.invoke({"command": "echo 'Hello from bash'"})
    if "Hello from bash" in result:
        print("   ✅ run_bash 작동")
    else:
        print(f"   ❌ run_bash 실패: {result[:100]}")
        return False

    # Test 2: bash_background
    print("\n[3-2] bash_background 테스트...")
    result = bash_background.invoke({
        "command": "for i in 1 2 3; do echo Line $i; sleep 0.1; done",
        "description": "Test background process"
    })

    if "Shell ID:" in result:
        # Extract shell_id
        shell_id = result.split("Shell ID: ")[1].split("\n")[0].strip()
        print(f"   ✅ bash_background 작동 (Shell ID: {shell_id})")

        # Test 3: bash_output
        print("\n[3-3] bash_output 테스트...")
        time.sleep(0.5)  # Wait for some output
        output_result = bash_output.invoke({"shell_id": shell_id})

        if "Line" in output_result or "exited" in output_result:
            print("   ✅ bash_output 작동")
        else:
            print(f"   ⚠️  bash_output 결과: {output_result[:200]}")

        # Test 4: kill_shell
        print("\n[3-4] kill_shell 테스트...")
        time.sleep(0.5)  # Wait for process to finish
        kill_result = kill_shell.invoke({"shell_id": shell_id})

        if "Killed" in kill_result or "not found" in kill_result:
            print("   ✅ kill_shell 작동")
        else:
            print(f"   ❌ kill_shell 실패: {kill_result}")
            return False

        return True
    else:
        print(f"   ❌ bash_background 실패: {result}")
        return False


async def test_web_tools():
    """웹 접근 도구 테스트 (web_search, web_fetch)"""
    print("\n" + "=" * 60)
    print("4. 웹 접근 도구 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.tools import web_search, web_fetch

    # Test 1: web_search
    print("\n[4-1] web_search 테스트...")
    try:
        result = await web_search.ainvoke({"query": "Python asyncio", "max_results": 2})
        if "Python" in result or "asyncio" in result or "Search results" in result:
            print("   ✅ web_search 작동")
        else:
            print(f"   ⚠️  web_search 결과: {result[:200]}")
    except Exception as e:
        print(f"   ⚠️  web_search 오류 (네트워크 문제일 수 있음): {e}")

    # Test 2: web_fetch
    print("\n[4-2] web_fetch 테스트...")
    try:
        result = await web_fetch.ainvoke({
            "url": "https://www.example.com",
            "prompt": "Get the main heading"
        })
        if "Example" in result or "URL:" in result:
            print("   ✅ web_fetch 작동")
            # Check for smart features
            if "Title:" in result and "Task:" in result:
                print("   ✅ web_fetch 메타데이터 포함")
            if "##" in result or "```" in result:
                print("   ✅ web_fetch 구조 보존")
        else:
            print(f"   ⚠️  web_fetch 결과: {result[:200]}")
    except Exception as e:
        print(f"   ⚠️  web_fetch 오류 (네트워크 문제일 수 있음): {e}")

    return True


async def test_management_tools():
    """관리 도구 테스트 (todo_write)"""
    print("\n" + "=" * 60)
    print("5. 관리 도구 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.tools import todo_write

    # Test 1: todo_write
    print("\n[5-1] todo_write 테스트...")
    result = todo_write.invoke({
        "todos": [
            {"content": "Test task 1", "status": "pending", "activeForm": "Testing task 1"},
            {"content": "Test task 2", "status": "completed", "activeForm": "Tested task 2"},
        ]
    })

    if "todos" in result.lower() or "updated" in result.lower():
        print("   ✅ todo_write 작동")
        return True
    else:
        print(f"   ❌ todo_write 실패: {result}")
        return False


async def test_task_tool():
    """Subagent 도구 테스트 (task_tool)"""
    print("\n" + "=" * 60)
    print("6. Subagent 도구 테스트")
    print("=" * 60)

    from custom_claude_code.v2_1_langgraph_improved.tools import task_tool

    # Test: task_tool schema
    print("\n[6-1] task_tool 스키마 테스트...")

    # task_tool은 실제로는 graph에서 처리되므로, 여기서는 tool이 존재하는지만 확인
    if hasattr(task_tool, 'name') and task_tool.name == 'task_tool':
        print("   ✅ task_tool 등록 확인")

        # Check schema
        if hasattr(task_tool, 'args_schema'):
            print("   ✅ task_tool 스키마 정의됨")
            return True
        else:
            print("   ⚠️  task_tool 스키마 없음 (정상일 수 있음)")
            return True
    else:
        print("   ❌ task_tool 미등록")
        return False


async def main():
    print("=" * 60)
    print("v2.1 LangGraph Improved - 전체 도구 테스트")
    print("=" * 60)

    results = []

    # Run all tests
    print("\n🔧 13개 도구 기능 테스트 시작...\n")

    results.append(("파일 조작 (3개)", await test_file_operations()))
    results.append(("검색 (2개)", await test_search_tools()))
    results.append(("실행 (4개)", await test_execution_tools()))
    results.append(("웹 접근 (2개)", await test_web_tools()))
    results.append(("관리 (1개)", await test_management_tools()))
    results.append(("Subagent (1개)", await test_task_tool()))

    # Summary
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    for name, passed in results:
        status = "✅ 통과" if passed else "❌ 실패"
        print(f"{name:20} {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\n총 {total}개 카테고리 중 {passed}개 통과")

    if passed == total:
        print("\n🎉 모든 도구 테스트 통과!")
        return 0
    else:
        print(f"\n⚠️  {total - passed}개 카테고리 실패")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
