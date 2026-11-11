from functools import lru_cache
import redis
from sensor_hub.config import get_settings

@lru_cache                                  
def get_cache() -> redis.Redis:
    return redis.Redis.from_url(
        get_settings().redis_url.get_secret_value(),
        decode_responses=True,                
        socket_connect_timeout=0.5,
        socket_timeout=0.5,
    )