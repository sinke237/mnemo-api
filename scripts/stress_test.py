"""Simple stress tester using asyncio + aiohttp.

Usage:
    python scripts/stress_test.py --url http://localhost:8000/v1/health --concurrency 500

This will fire `concurrency` concurrent GET requests and report basic timing.
"""
import argparse
import asyncio
import time

import aiohttp
import logging


logger = logging.getLogger(__name__)


async def worker(session, url, sem, results):
    async with sem:
        start = time.perf_counter()
        try:
            async with session.get(url, timeout=30) as resp:
                await resp.text()
                elapsed = time.perf_counter() - start
                results.append((resp.status, elapsed))
        except Exception as e:
            elapsed = time.perf_counter() - start
            # Log exception with traceback for diagnostics and preserve
            # the exception type/message in results for later inspection.
            logger.exception("Request failed")
            err_str = f"{type(e).__name__}: {e}"
            results.append((err_str, elapsed))


async def run(url, concurrency):
    sem = asyncio.Semaphore(concurrency)
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = [asyncio.create_task(worker(session, url, sem, results)) for _ in range(concurrency)]
        await asyncio.gather(*tasks)

    successes = sum(1 for s, _ in results if s and 200 <= s < 300)
    failures = len(results) - successes
    avg = sum(t for _, t in results) / len(results) if results else 0
    print(f"Requests: {len(results)}, Successes: {successes}, Failures: {failures}, Avg time: {avg:.3f}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/v1/health")
    parser.add_argument("--concurrency", type=int, default=500)
    args = parser.parse_args()
    asyncio.run(run(args.url, args.concurrency))


if __name__ == "__main__":
    main()
