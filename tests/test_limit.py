import asyncio

import pytest

from muffin_rest import limits


class FakeTime:
    def __init__(self, start=0.0):
        self._t = float(start)

    def time(self):
        return self._t

    def advance(self, dt):
        self._t += float(dt)


async def _run_concurrent_checks(limiter, key: str, n: int, start_evt: asyncio.Event):
    await start_evt.wait()
    return await limiter.check(key)


async def test_limit_memory_allows_until_limit(monkeypatch):

    ft = FakeTime(start=100.0)
    monkeypatch.setattr(limits, "time", ft.time)

    limiter = limits.MemoryRateLimiter(limit=2, period=10)

    assert await limiter.check("k1") is True
    assert await limiter.check("k1") is True
    assert await limiter.check("k1") is False


async def test_limit_memory_resets_after_period(monkeypatch):

    ft = FakeTime(start=0.0)
    monkeypatch.setattr(limits, "time", ft.time)

    limiter = limits.MemoryRateLimiter(limit=2, period=5)

    assert await limiter.check("user") is True
    assert await limiter.check("user") is True
    assert await limiter.check("user") is False  # упёрлись в лимит

    ft.advance(5.0)
    assert await limiter.check("user") is False  # всё ещё то же окно

    ft.advance(0.0001)
    assert await limiter.check("user") is True
    assert await limiter.check("user") is True
    assert await limiter.check("user") is False


async def test_limit_memory_isolated_keys(monkeypatch):

    ft = FakeTime(start=10.0)
    monkeypatch.setattr(limits, "time", ft.time)

    limiter = limits.MemoryRateLimiter(limit=1, period=60)

    # ключи считаются независимо
    assert await limiter.check("A") is True
    assert await limiter.check("A") is False

    assert await limiter.check("B") is True
    assert await limiter.check("B") is False


async def test_limit_memory_first_hit_initializes(monkeypatch):

    ft = FakeTime(start=1.0)
    monkeypatch.setattr(limits, "time", ft.time)

    limiter = limits.MemoryRateLimiter(limit=3, period=10)
    assert await limiter.check("new") is True
    assert await limiter.check("new") is True
    assert await limiter.check("new") is True
    assert await limiter.check("new") is False


@pytest.mark.parametrize("aiolib", ["asyncio"])
async def test_memory_limiter_concurrent_requests_respect_limit(monkeypatch):
    ft = FakeTime(start=123.0)
    monkeypatch.setattr(limits, "time", ft.time)

    limit = 5
    limiter = limits.MemoryRateLimiter(limit=limit, period=60)

    start_evt = asyncio.Event()
    tasks = [
        asyncio.create_task(_run_concurrent_checks(limiter, "same-key", 1, start_evt))
        for _ in range(25)
    ]

    start_evt.set()
    results = await asyncio.gather(*tasks)

    assert sum(1 for r in results if r) == limit
    assert sum(1 for r in results if not r) == len(results) - limit

    assert await limiter.check("same-key") is False

    ft.advance(60.001)
    start_evt2 = asyncio.Event()
    tasks2 = [
        asyncio.create_task(_run_concurrent_checks(limiter, "same-key", 1, start_evt2))
        for _ in range(10)
    ]
    start_evt2.set()
    results2 = await asyncio.gather(*tasks2)
    assert sum(1 for r in results2 if r) == limit
    assert sum(1 for r in results2 if not r) == len(results2) - limit


class FakeRedis:
    def __init__(self, time_fn):
        self._store = {}
        self._time = time_fn

    async def incr(self, key):
        v = self._store.get(key)
        now = self._time()
        if v is None:
            self._store[key] = (1, None)
            return 1
        value, expires_at = v
        if expires_at is not None and now >= expires_at:
            self._store[key] = (1, None)
            return 1
        new_val = int(value) + 1
        self._store[key] = (new_val, expires_at)
        return new_val

    async def expire(self, key, seconds):
        v = self._store.get(key)
        if v is None:
            return False
        value, _ = v
        expires_at = self._time() + seconds
        self._store[key] = (value, expires_at)
        return True


async def test_limit_redis_basic(monkeypatch):

    ft = FakeTime(start=1000.0)
    monkeypatch.setattr(limits, "time", ft.time)

    redis = FakeRedis(ft.time)
    limiter = limits.RedisRateLimiter(limit=2, period=10, redis=redis)

    assert await limiter.check("ip:1") is True
    assert await limiter.check("ip:1") is True
    assert await limiter.check("ip:1") is False

    ft.advance(10.0001)
    assert await limiter.check("ip:1") is True
    assert await limiter.check("ip:1") is True
    assert await limiter.check("ip:1") is False


async def test_limit_redis_separate_keys(monkeypatch):

    ft = FakeTime(start=0.0)
    redis = FakeRedis(ft.time)
    limiter = limits.RedisRateLimiter(limit=1, period=60, redis=redis)

    assert await limiter.check("u1") is True
    assert await limiter.check("u1") is False

    assert await limiter.check("u2") is True
    assert await limiter.check("u2") is False


@pytest.mark.parametrize("aiolib", ["asyncio"])
async def test_redis_limiter_concurrent_requests_respect_limit(monkeypatch):
    from muffin_rest import limits

    ft = FakeTime(start=999.0)
    monkeypatch.setattr(limits, "time", ft.time)

    limit = 3
    redis = FakeRedis(ft.time)
    limiter = limits.RedisRateLimiter(limit=limit, period=120, redis=redis)

    start_evt = asyncio.Event()
    tasks = [
        asyncio.create_task(_run_concurrent_checks(limiter, "ip:42", 1, start_evt))
        for _ in range(20)
    ]
    start_evt.set()
    results = await asyncio.gather(*tasks)

    assert sum(1 for r in results if r) == limit
    assert sum(1 for r in results if not r) == len(results) - limit

    assert await limiter.check("ip:42") is False

    ft.advance(120.01)
    assert await limiter.check("ip:42") is True
    start_evt2 = asyncio.Event()
    tasks2 = [
        asyncio.create_task(_run_concurrent_checks(limiter, "ip:42", 1, start_evt2))
        for _ in range(5)
    ]
    start_evt2.set()
    results2 = await asyncio.gather(*tasks2)
    total_success = 1 + sum(1 for r in results2 if r)
    assert total_success == limit
