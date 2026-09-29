import redis as _redis
from flask import current_app

_pool: _redis.ConnectionPool | None = None

def get_redis() -> _redis.Redis:
    global _pool
    if _pool is None:
        url  = current_app.config["REDIS_URL"]
        _pool = _redis.ConnectionPool.from_url(
            url,
            decode_responses=True,
            max_connections=20,
        )
    return _redis.Redis(connection_pool=_pool)

def redis_set(key: str, value: str, ex: int | None = None) -> None:
    get_redis().set(key, value, ex=ex)

def redis_get(key: str) -> str | None:
    return get_redis().get(key)

def redis_delete(*keys: str) -> None:
    if keys:
        get_redis().delete(*keys)

def redis_incr(key: str, ex: int | None = None) -> int:
    r   = get_redis()
    val = r.incr(key)
    if ex and val == 1:
        r.expire(key, ex)
    return val

def redis_ttl(key: str) -> int:
    return get_redis().ttl(key)