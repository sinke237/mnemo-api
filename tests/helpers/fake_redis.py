from typing import Any


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    async def incr(self, key: str) -> int:
        self.store.setdefault(key, 0)
        self.store[key] += 1
        return int(self.store[key])

    async def expire(self, key: str, ttl: int) -> bool:
        # no-op for tests
        return True

    async def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> int:
        # Emulate the atomic INCR+EXPIRE Lua script used by RateLimitMiddleware.
        # keys_and_args[0] is the key, keys_and_args[1] is the ttl (ignored here).
        key = keys_and_args[0]
        return int(await self.incr(key))

    async def ping(self) -> bool:
        return True

    async def rpush(self, key: str, *values: Any) -> int:
        self.store.setdefault(key, [])
        self.store[key].extend(values)
        return len(self.store[key])

    async def blpop(self, keys: str | list[str], timeout: int = 0) -> tuple[str, Any] | None:
        # keys may be single key or list/tuple
        if isinstance(keys, list | tuple):
            for key in keys:
                lst = self.store.get(key)
                if lst:
                    value = lst.pop(0)
                    return (key, value)
            return None
        else:
            lst = self.store.get(keys)
            if lst:
                value = lst.pop(0)
                return (keys, value)
            return None

    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0

    async def aclose(self) -> None:
        return None
