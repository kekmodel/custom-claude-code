"""
v2 멀티 모델 지원 테스트
"""

import os

from dotenv import load_dotenv

from custom_claude_code.v2_langgraph.config import V2Config
from custom_claude_code.v2_langgraph.models import (
    MODEL_ALIASES,
    get_available_providers,
    get_model,
    get_model_by_alias,
)

load_dotenv()


def test_config():
    """설정 로드 테스트"""
    print("\n" + "=" * 80)
    print("테스트 1: 설정 로드")
    print("=" * 80)

    print(V2Config.summary())

    assert V2Config.DEFAULT_PROVIDER in ["anthropic", "openai", "gemini"]
    print("\n✅ PASS: 설정 로드 성공")


def test_available_providers():
    """사용 가능한 프로바이더 확인"""
    print("\n" + "=" * 80)
    print("테스트 2: 사용 가능한 프로바이더")
    print("=" * 80)

    providers = get_available_providers()
    print(f"\n사용 가능한 프로바이더: {list(providers.keys())}")

    for provider, info in providers.items():
        print(f"\n{provider}:")
        print(f"  기본 모델: {info['default_model']}")
        print(f"  지원 모델: {', '.join(info['models'][:3])}...")
        print(f"  필요 키: {info['requires_key']}")
        print(f"  Thinking: {'✅' if info['supports_thinking'] else '❌'}")

    assert "anthropic" in providers
    assert "openai" in providers
    assert "gemini" in providers

    print("\n✅ PASS: 모든 프로바이더 확인 완료")


def test_model_creation():
    """모델 생성 테스트"""
    print("\n" + "=" * 80)
    print("테스트 3: 모델 생성")
    print("=" * 80)

    # Anthropic 모델만 테스트 (API 키 필요)
    if os.getenv("ANTHROPIC_API_KEY"):
        print("\n[Anthropic]")
        try:
            model = get_model(provider="anthropic", model_name="claude-haiku-4-5")
            print(f"  ✅ 모델 생성 성공: {model.__class__.__name__}")
            print(f"  모델명: {model.model}")
        except Exception as e:
            print(f"  ❌ 실패: {e}")
            raise
    else:
        print("\n  ⏭️  SKIP: ANTHROPIC_API_KEY 없음")

    # OpenAI (선택적)
    if os.getenv("OPENAI_API_KEY"):
        print("\n[OpenAI]")
        try:
            model = get_model(provider="openai", model_name="gpt-4o")
            print(f"  ✅ 모델 생성 성공: {model.__class__.__name__}")
        except Exception as e:
            print(f"  ⚠️  경고: {e}")
    else:
        print("\n  ⏭️  SKIP: OPENAI_API_KEY 없음")

    # Gemini (선택적)
    if os.getenv("GOOGLE_API_KEY"):
        print("\n[Gemini]")
        try:
            model = get_model(provider="gemini", model_name="gemini-2.0-flash-exp")
            print(f"  ✅ 모델 생성 성공: {model.__class__.__name__}")
        except Exception as e:
            print(f"  ⚠️  경고: {e}")
    else:
        print("\n  ⏭️  SKIP: GOOGLE_API_KEY 없음")

    print("\n✅ PASS: 모델 생성 테스트 완료")


def test_model_aliases():
    """모델 별칭 테스트"""
    print("\n" + "=" * 80)
    print("테스트 4: 모델 별칭")
    print("=" * 80)

    print(f"\n사용 가능한 별칭: {list(MODEL_ALIASES.keys())}")

    if os.getenv("ANTHROPIC_API_KEY"):
        print("\n별칭으로 모델 생성:")
        for alias in ["haiku", "sonnet"]:
            try:
                model = get_model_by_alias(alias)
                provider, model_name = MODEL_ALIASES[alias]
                print(f"  ✅ {alias} → {provider}/{model_name}")
            except Exception as e:
                print(f"  ❌ {alias} 실패: {e}")
                raise

    print("\n✅ PASS: 별칭 테스트 완료")


def main():
    """전체 테스트 실행"""
    print("\n" + "=" * 80)
    print("v2 멀티 모델 지원 테스트")
    print("=" * 80)

    try:
        test_config()
        test_available_providers()
        test_model_creation()
        test_model_aliases()

        print("\n" + "=" * 80)
        print("🎉 모든 테스트 통과!")
        print("=" * 80)

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ 테스트 실패: {e}")
        print("=" * 80)
        raise


if __name__ == "__main__":
    main()
