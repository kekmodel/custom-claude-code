#!/usr/bin/env python3
"""
레퍼런스 JSON schema와 v2 구현 비교 검증
"""

import json
import sys

# 레퍼런스에서 기대되는 16개 도구
REFERENCE_TOOLS = {
    "Task": {
        "params": ["description", "prompt", "subagent_type", "model", "resume"],
        "required": ["description", "prompt", "subagent_type"],
    },
    "Bash": {
        "params": ["command", "timeout", "description", "run_in_background", "dangerouslyDisableSandbox"],
        "required": ["command"],
    },
    "Glob": {
        "params": ["pattern", "path"],
        "required": ["pattern"],
    },
    "Grep": {
        "params": ["pattern", "path", "glob", "output_mode", "-B", "-A", "-C", "-n", "-i", "type", "head_limit", "offset", "multiline"],
        "required": ["pattern"],
    },
    "ExitPlanMode": {
        "params": ["plan"],
        "required": ["plan"],
    },
    "Read": {
        "params": ["file_path", "offset", "limit"],
        "required": ["file_path"],
    },
    "Edit": {
        "params": ["file_path", "old_string", "new_string", "replace_all"],
        "required": ["file_path", "old_string", "new_string"],
    },
    "Write": {
        "params": ["file_path", "content"],
        "required": ["file_path", "content"],
    },
    "NotebookEdit": {
        "params": ["notebook_path", "cell_id", "new_source", "cell_type", "edit_mode"],
        "required": ["notebook_path", "new_source"],
    },
    "WebFetch": {
        "params": ["url", "prompt"],
        "required": ["url", "prompt"],
    },
    "TodoWrite": {
        "params": ["todos"],
        "required": ["todos"],
    },
    "WebSearch": {
        "params": ["query", "allowed_domains", "blocked_domains"],
        "required": ["query"],
    },
    "BashOutput": {
        "params": ["bash_id", "filter"],
        "required": ["bash_id"],
    },
    "KillShell": {
        "params": ["shell_id"],
        "required": ["shell_id"],
    },
    "Skill": {
        "params": ["skill"],
        "required": ["skill"],
    },
    "SlashCommand": {
        "params": ["command"],
        "required": ["command"],
    },
}

# v2 구현에서 실제로 구현된 도구 (tools.py의 TOOLS 리스트 기준)
IMPLEMENTED_TOOLS = {
    "read_file": {
        "reference_name": "Read",
        "params": ["file_path", "offset", "limit"],
    },
    "write_file": {
        "reference_name": "Write",
        "params": ["file_path", "content"],
    },
    "edit_file": {
        "reference_name": "Edit",
        "params": ["file_path", "old_string", "new_string", "replace_all"],
    },
    "glob_files": {
        "reference_name": "Glob",
        "params": ["pattern", "path"],
    },
    "grep_code": {
        "reference_name": "Grep",
        "params": ["pattern", "path", "glob", "case_insensitive"],  # 실제 구현된 파라미터만
    },
    "run_bash": {
        "reference_name": "Bash",
        "params": ["command", "timeout"],  # description, run_in_background, dangerouslyDisableSandbox 없음
    },
    "todo_write": {
        "reference_name": "TodoWrite",
        "params": ["todos"],
    },
    "exit_plan_mode": {
        "reference_name": "ExitPlanMode",
        "params": ["plan"],
    },
    "task_tool": {
        "reference_name": "Task",
        "params": ["subagent_type", "description", "prompt", "model"],  # resume 없음
    },
}


def main():
    print("=" * 80)
    print("v2 LangGraph Tools 검증 리포트")
    print("=" * 80)
    print()

    # 1. 도구 개수 비교
    print("📊 도구 개수 비교")
    print("-" * 80)
    print(f"레퍼런스 (Claude Code): {len(REFERENCE_TOOLS)}개 도구")
    print(f"v2 구현:                {len(IMPLEMENTED_TOOLS)}개 도구")
    print()

    # 2. 누락된 도구 확인
    implemented_refs = {info["reference_name"] for info in IMPLEMENTED_TOOLS.values()}
    missing_tools = set(REFERENCE_TOOLS.keys()) - implemented_refs

    if missing_tools:
        print("❌ 누락된 도구:")
        print("-" * 80)
        for tool in sorted(missing_tools):
            print(f"  - {tool}")
            print(f"    파라미터: {', '.join(REFERENCE_TOOLS[tool]['params'])}")
        print()
    else:
        print("✅ 모든 도구가 구현되었습니다!")
        print()

    # 3. 구현된 도구의 파라미터 검증
    print("🔍 파라미터 완전성 검증")
    print("-" * 80)

    issues_found = False
    for impl_name, impl_info in IMPLEMENTED_TOOLS.items():
        ref_name = impl_info["reference_name"]
        ref_params = set(REFERENCE_TOOLS[ref_name]["params"])
        impl_params = set(impl_info["params"])

        missing_params = ref_params - impl_params
        extra_params = impl_params - ref_params

        if missing_params or extra_params:
            issues_found = True
            print(f"\n⚠️  {impl_name} (레퍼런스: {ref_name})")

            if missing_params:
                print(f"   누락된 파라미터: {', '.join(sorted(missing_params))}")

            if extra_params:
                print(f"   추가된 파라미터: {', '.join(sorted(extra_params))}")
        else:
            print(f"✅ {impl_name}: 파라미터 일치")

    if not issues_found:
        print("\n✅ 모든 구현된 도구의 파라미터가 레퍼런스와 일치합니다!")

    print()
    print("=" * 80)
    print("검증 완료")
    print("=" * 80)
    print()

    # 요약
    print("📋 요약")
    print("-" * 80)
    print(f"✅ 구현 완료: {len(IMPLEMENTED_TOOLS)}/{len(REFERENCE_TOOLS)} 도구")
    print(f"❌ 미구현:     {len(missing_tools)}/{len(REFERENCE_TOOLS)} 도구")

    if missing_tools:
        print()
        print("💡 권장사항:")
        print("   교육/연구 목적이라면 핵심 9개 도구만으로 충분합니다.")
        print("   프로덕션 용도라면 다음 도구 추가를 고려하세요:")
        print("   - WebFetch, WebSearch (웹 검색/페치 기능)")
        print("   - BashOutput, KillShell (백그라운드 프로세스 관리)")
        print("   - NotebookEdit (Jupyter 노트북 지원)")


if __name__ == "__main__":
    main()
