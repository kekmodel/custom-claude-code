"""
캐시 모듈 - Redis 기반 캐싱 시스템

이 모듈은 API 응답 및 계산 결과를 캐시하기 위한 Redis 기반 캐싱 시스템을 제공합니다.
"""

from .redis_cache import RedisCache, cache_result

__all__ = ["RedisCache", "cache_result"]
