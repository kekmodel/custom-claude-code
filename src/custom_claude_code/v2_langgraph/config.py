"""
v2: 중앙 설정 관리

환경 변수 또는 코드로 설정 변경 가능
"""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class V2Config:
    """v2 LangGraph 설정"""

    # 모델 설정
    DEFAULT_PROVIDER: str = os.getenv("V2_PROVIDER", "anthropic")
    DEFAULT_MODEL: Optional[str] = os.getenv("V2_MODEL")  # None이면 provider 기본값
    DEFAULT_TEMPERATURE: float = float(os.getenv("V2_TEMPERATURE", "1.0"))
    DEFAULT_THINKING_BUDGET: int = int(os.getenv("V2_THINKING_BUDGET", "2048"))

    # 그래프 설정
    RECURSION_LIMIT: int = int(os.getenv("V2_RECURSION_LIMIT", "50"))
    MAX_SUBAGENT_DEPTH: int = int(os.getenv("V2_MAX_SUBAGENT_DEPTH", "5"))

    # 메시지 압축 설정
    AUTO_COMPACT_ENABLED: bool = os.getenv("V2_AUTO_COMPACT", "true").lower() == "true"
    AUTO_COMPACT_THRESHOLD: int = int(os.getenv("V2_COMPACT_THRESHOLD", "100000"))  # 100k tokens

    # 표시 설정
    SHOW_THINKING: bool = os.getenv("V2_SHOW_THINKING", "true").lower() == "true"
    SHOW_TOOL_RESULTS: bool = os.getenv("V2_SHOW_TOOL_RESULTS", "true").lower() == "true"
    TOOL_RESULT_MAX_LENGTH: int = int(os.getenv("V2_TOOL_RESULT_MAX", "500"))

    @classmethod
    def get_model_config(cls) -> dict:
        """모델 설정 딕셔너리 반환"""
        return {
            "provider": cls.DEFAULT_PROVIDER,
            "model_name": cls.DEFAULT_MODEL,
            "temperature": cls.DEFAULT_TEMPERATURE,
            "thinking_budget": cls.DEFAULT_THINKING_BUDGET,
        }

    @classmethod
    def get_graph_config(cls) -> dict:
        """그래프 실행 설정 딕셔너리 반환"""
        return {
            "recursion_limit": cls.RECURSION_LIMIT,
        }

    @classmethod
    def summary(cls) -> str:
        """현재 설정 요약"""
        return f"""
v2 LangGraph 설정:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[모델]
  Provider: {cls.DEFAULT_PROVIDER}
  Model: {cls.DEFAULT_MODEL or 'default'}
  Temperature: {cls.DEFAULT_TEMPERATURE}
  Thinking Budget: {cls.DEFAULT_THINKING_BUDGET}

[그래프]
  Recursion Limit: {cls.RECURSION_LIMIT}
  Max Subagent Depth: {cls.MAX_SUBAGENT_DEPTH}

[압축]
  Auto Compact: {cls.AUTO_COMPACT_ENABLED}
  Threshold: {cls.AUTO_COMPACT_THRESHOLD:,} tokens

[표시]
  Show Thinking: {cls.SHOW_THINKING}
  Show Tool Results: {cls.SHOW_TOOL_RESULTS}
  Tool Result Max Length: {cls.TOOL_RESULT_MAX_LENGTH}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        """.strip()


# 편의를 위한 인스턴스
config = V2Config()
