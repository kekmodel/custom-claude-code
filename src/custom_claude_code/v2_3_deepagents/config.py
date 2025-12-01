"""
v2.3: DeepAgents 설정

모델 설정 및 Extended Thinking 구성.
"""

import os
from dataclasses import dataclass


@dataclass
class DeepAgentsConfig:
    """DeepAgents 설정"""

    model_name: str = "claude-haiku-4-5-20251001"
    thinking_budget: int = 5000
    summarization_threshold: int = 170_000
    max_depth: int = 5
    recursion_limit: int = 100
    enable_long_term_memory: bool = True  # /memories/ 경로 영구 저장

    @classmethod
    def from_env(cls) -> "DeepAgentsConfig":
        """환경 변수에서 설정 로드"""
        return cls(
            model_name=os.getenv("DEEPAGENTS_MODEL", cls.model_name),
            thinking_budget=int(os.getenv("DEEPAGENTS_THINKING_BUDGET", cls.thinking_budget)),
            summarization_threshold=int(os.getenv("DEEPAGENTS_SUMMARIZATION_THRESHOLD", cls.summarization_threshold)),
            max_depth=int(os.getenv("DEEPAGENTS_MAX_DEPTH", cls.max_depth)),
            recursion_limit=int(os.getenv("DEEPAGENTS_RECURSION_LIMIT", cls.recursion_limit)),
            enable_long_term_memory=os.getenv("DEEPAGENTS_LONG_TERM_MEMORY", "true").lower() == "true",
        )


def create_model():
    """Extended Thinking이 활성화된 ChatAnthropic 모델 생성"""
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=config.model_name,
        thinking={"type": "enabled", "budget_tokens": config.thinking_budget},
    )


config = DeepAgentsConfig.from_env()
