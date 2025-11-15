"""
Redis 기반 캐싱 시스템

Redis를 사용하여 API 응답 및 계산 결과를 캐시합니다.
메모리 부족 시 대체 메모리 캐시도 지원합니다.
"""

import json
import hashlib
from functools import wraps
from typing import Any, Callable, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis 기반 캐시 시스템"""

    def __init__(self, redis_url: Optional[str] = None, default_ttl: int = 3600):
        """
        Redis 캐시 초기화

        Args:
            redis_url: Redis 연결 URL (기본값: None, 메모리 캐시 사용)
            default_ttl: 기본 TTL (초 단위, 기본값: 3600초 = 1시간)
        """
        self.default_ttl = default_ttl
        self.redis_client = None
        self.memory_cache = {}  # 폴백 메모리 캐시

        if redis_url:
            try:
                import redis

                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()
                logger.info("Redis 연결 성공")
            except Exception as e:
                logger.warning(
                    f"Redis 연결 실패, 메모리 캐시로 전환: {e}"
                )
                self.redis_client = None

    @staticmethod
    def _generate_key(prefix: str, *args, **kwargs) -> str:
        """
        캐시 키 생성 (일관된 네이밍 규칙: api:endpoint:params)

        Args:
            prefix: 키 접두사 (예: 'api', 'compute')
            *args: 위치 인수
            **kwargs: 키워드 인수

        Returns:
            생성된 캐시 키
        """
        key_parts = [prefix]

        # args를 키에 추가
        for arg in args:
            key_parts.append(str(arg))

        # kwargs를 정렬하여 일관성 있게 추가
        for k in sorted(kwargs.keys()):
            key_parts.append(f"{k}={kwargs[k]}")

        # 긴 경우 해시로 축약
        key_str = ":".join(key_parts)
        if len(key_str) > 200:
            hash_suffix = hashlib.md5(key_str.encode()).hexdigest()[:8]
            key_str = f"{prefix}:{hash_suffix}"

        return key_str

    def get(self, key: str) -> Optional[Any]:
        """
        캐시에서 값 조회

        Args:
            key: 캐시 키

        Returns:
            캐시된 값 또는 None
        """
        try:
            if self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    logger.debug(f"Redis 캐시 히트: {key}")
                    return json.loads(value)
            else:
                if key in self.memory_cache:
                    cache_entry = self.memory_cache[key]
                    if cache_entry["expires_at"] > datetime.now():
                        logger.debug(f"메모리 캐시 히트: {key}")
                        return cache_entry["value"]
                    else:
                        del self.memory_cache[key]
        except Exception as e:
            logger.error(f"캐시 조회 실패: {e}")

        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        캐시에 값 저장

        Args:
            key: 캐시 키
            value: 저장할 값
            ttl: TTL (초 단위, 기본값: default_ttl)

        Returns:
            성공 여부
        """
        ttl = ttl or self.default_ttl
        try:
            if self.redis_client:
                self.redis_client.setex(key, ttl, json.dumps(value))
                logger.debug(f"Redis 캐시 저장: {key} (TTL: {ttl}s)")
            else:
                self.memory_cache[key] = {
                    "value": value,
                    "expires_at": datetime.now() + timedelta(seconds=ttl),
                }
                logger.debug(f"메모리 캐시 저장: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"캐시 저장 실패: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        캐시에서 값 삭제

        Args:
            key: 캐시 키

        Returns:
            성공 여부
        """
        try:
            if self.redis_client:
                self.redis_client.delete(key)
                logger.debug(f"Redis 캐시 삭제: {key}")
            else:
                if key in self.memory_cache:
                    del self.memory_cache[key]
                    logger.debug(f"메모리 캐시 삭제: {key}")
            return True
        except Exception as e:
            logger.error(f"캐시 삭제 실패: {e}")
            return False

    def clear(self) -> bool:
        """모든 캐시 삭제"""
        try:
            if self.redis_client:
                self.redis_client.flushdb()
                logger.info("Redis 캐시 전체 삭제")
            else:
                self.memory_cache.clear()
                logger.info("메모리 캐시 전체 삭제")
            return True
        except Exception as e:
            logger.error(f"캐시 전체 삭제 실패: {e}")
            return False


# 전역 캐시 인스턴스
_cache_instance: Optional[RedisCache] = None


def get_cache(redis_url: Optional[str] = None) -> RedisCache:
    """전역 캐시 인스턴스 획득"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = RedisCache(redis_url=redis_url)
    return _cache_instance


def cache_result(ttl: Optional[int] = None, key_prefix: str = "api"):
    """
    함수 결과를 캐시하는 데코레이터

    사용 예:
        @cache_result(ttl=600, key_prefix="compute")
        def expensive_computation(x, y):
            return x + y

    Args:
        ttl: TTL (초 단위, 기본값: 캐시 기본값)
        key_prefix: 캐시 키 접두사 (기본값: "api")

    Returns:
        데코레이터 함수
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            cache_key = RedisCache._generate_key(key_prefix, func.__name__, *args, **kwargs)

            # 캐시 확인
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.info(f"캐시된 결과 반환: {func.__name__}")
                return cached_value

            # 실행 및 저장
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result

        return wrapper

    return decorator
