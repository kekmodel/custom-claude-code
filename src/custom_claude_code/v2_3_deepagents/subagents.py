"""
v2.3: Subagent 정의

DeepAgents의 subagent 설정.
general-purpose는 DeepAgents가 자동으로 추가함.
"""


def get_subagents() -> list[dict]:
    """Subagent 목록 반환"""
    return [
        {
            "name": "Explore",
            "description": "코드베이스 탐색 전문. 파일 패턴 검색, 키워드 검색, 아키텍처 분석. 읽기 전용.",
            "system_prompt": "당신은 코드베이스 탐색 전문 Explore agent입니다. 파일 탐색과 분석만 수행합니다.",
            "tools": [],  # 기본 filesystem 도구만 사용
        },
        {
            "name": "Plan",
            "description": "구현 계획 수립 전문. 기능 구현, 버그 수정, 리팩토링 계획. 읽기 전용.",
            "system_prompt": "당신은 구현 계획 수립 전문 Plan agent입니다. 계획 수립만 수행합니다.",
            "tools": [],
        },
    ]
