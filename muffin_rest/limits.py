import abc
from asyncio import Lock
from time import time
from typing import Any


class RateLimiter(abc.ABC):
    """Rate limiter."""

    def __init__(self, limit: int, *, period: int = 60, **opts):
        """Initialize the rate limiter.

        Args:
            limit (int): The limit of requests.
            period (int): The period of time in seconds.
        """
        self.lock = Lock()
        self.limit = limit
        self.period = period

    async def check(self, key: str) -> bool:
        """Check the request."""
        async with self.lock:
            return await self._check(key)

    @abc.abstractmethod
    async def _check(self, key: str) -> bool:
        """Check the request."""
        raise NotImplementedError("Subclasses must implement this method.")


class MemoryRateLimiter(RateLimiter):
    """Memory rate limiter. Do not use in production."""

    def __init__(self, limit: int, **opts):
        super().__init__(limit, **opts)
        self.storage: dict[Any, tuple[float, int]] = {}

    async def _check(self, key: str) -> bool:
        """Check the request."""
        now = time()
        storage = self.storage

        if key not in storage:
            storage[key] = (now, 1)
            return True

        last, count = storage[key]
        if now - last > self.period:
            storage[key] = (now, 1)
            return True

        if count < self.limit:
            storage[key] = (last, count + 1)
            return True

        return False


class RedisRateLimiter(RateLimiter):
    """Redis rate limiter."""

    def __init__(self, limit: int, *, redis, **opts):
        """Initialize the rate limiter.

        Args:
            limit (int): The limit of requests.
            period (int): The period of time in seconds.
            redis (aioredis.Redis): The Redis connection.
        """
        super().__init__(limit, **opts)
        self.redis = redis

    async def _check(self, key: str) -> bool:
        """Check the request."""
        value = await self.redis.get(key)
        if value is None:
            await self.redis.setex(key, self.period, 1)
            return True

        await self.redis.incr(key)
        return int(value) < self.limit
