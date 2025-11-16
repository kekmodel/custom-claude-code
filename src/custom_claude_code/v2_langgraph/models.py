"""
v2: 멀티 모델 지원 (Anthropic, OpenAI, Gemini)

중앙에서 모델 설정을 관리하여 쉽게 전환 가능
"""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def get_model(
    provider: str = "anthropic",
    model_name: Optional[str] = None,
    temperature: float = 1.0,
    thinking_budget: int = 2048,
    **kwargs,
):
    """
    모델 팩토리 함수

    Args:
        provider: "anthropic", "openai", "gemini"
        model_name: 모델 이름 (None이면 기본값)
        temperature: 온도 (0.0 ~ 2.0)
        thinking_budget: Extended Thinking 토큰 수
        **kwargs: 추가 모델 파라미터

    Returns:
        LangChain ChatModel 인스턴스
    """
    provider = provider.lower()

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        default_model = "claude-haiku-4-5"
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        return ChatAnthropic(
            model=model_name or default_model,
            temperature=temperature,
            api_key=api_key,
            thinking={"type": "enabled", "budget_tokens": thinking_budget},
            **kwargs,
        )

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        default_model = "gpt-4o"
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")  # Anthropic API 사용 시

        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")

        # OpenAI는 Extended Thinking을 직접 지원하지 않음
        return ChatOpenAI(
            model=model_name or default_model,
            temperature=temperature,
            api_key=api_key,
            base_url=base_url,  # None이면 기본 OpenAI API
            **kwargs,
        )

    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        default_model = "gemini-2.0-flash-exp"
        api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment")

        # Gemini는 Extended Thinking을 thinking_config로 설정
        return ChatGoogleGenerativeAI(
            model=model_name or default_model,
            temperature=temperature,
            google_api_key=api_key,
            # Gemini 2.0 thinking mode (실험적 기능)
            # thinking_config={"mode": "THINKING_MODE_ENABLED"} if thinking_budget else None,
            **kwargs,
        )

    else:
        raise ValueError(f"Unsupported provider: {provider}. Choose from: anthropic, openai, gemini")


def get_available_providers() -> dict:
    """
    사용 가능한 프로바이더와 기본 모델 반환

    Returns:
        {provider: {model, requires_key, supports_thinking}}
    """
    return {
        "anthropic": {
            "default_model": "claude-haiku-4-5",
            "models": ["claude-haiku-4-5", "claude-sonnet-4-5-20250929", "claude-opus-4-20250514"],
            "requires_key": "ANTHROPIC_API_KEY",
            "supports_thinking": True,
        },
        "openai": {
            "default_model": "gpt-4o",
            "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            "requires_key": "OPENAI_API_KEY",
            "supports_thinking": False,
        },
        "gemini": {
            "default_model": "gemini-2.0-flash-exp",
            "models": ["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"],
            "requires_key": "GOOGLE_API_KEY",
            "supports_thinking": True,  # Gemini 2.0+
        },
    }


# 모델 별칭 (짧은 이름으로 접근)
MODEL_ALIASES = {
    # Anthropic
    "haiku": ("anthropic", "claude-haiku-4-5"),
    "sonnet": ("anthropic", "claude-sonnet-4-5-20250929"),
    "opus": ("anthropic", "claude-opus-4-20250514"),
    # OpenAI
    "gpt4o": ("openai", "gpt-4o"),
    "gpt4o-mini": ("openai", "gpt-4o-mini"),
    # Gemini
    "gemini": ("gemini", "gemini-2.0-flash-exp"),
    "gemini-pro": ("gemini", "gemini-1.5-pro"),
}


def get_model_by_alias(alias: str, **kwargs):
    """
    별칭으로 모델 가져오기

    Example:
        model = get_model_by_alias("haiku")
        model = get_model_by_alias("gpt4o")
    """
    if alias not in MODEL_ALIASES:
        raise ValueError(f"Unknown alias: {alias}. Available: {list(MODEL_ALIASES.keys())}")

    provider, model_name = MODEL_ALIASES[alias]
    return get_model(provider=provider, model_name=model_name, **kwargs)
