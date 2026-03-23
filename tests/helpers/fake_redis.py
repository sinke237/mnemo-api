class FakeRedis:
    def __init__(self):
        self.store = {}

    async def incr(self, key):
        self.store.setdefault(key, 0)
        self.store[key] += 1
        return self.store[key]

    async def expire(self, key, ttl):
        # no-op for tests
        return True

    async def ping(self):
        return True

    async def exists(self, key):
        return 1 if key in self.store else 0

    async def aclose(self):
        return None
