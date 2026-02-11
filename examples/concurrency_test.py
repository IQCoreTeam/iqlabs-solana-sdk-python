"""
Test the concurrency utilities without network calls.
This is useful to verify the SDK logic works correctly.
"""
import asyncio
from iqlabs.sdk.utils.concurrency import run_with_concurrency
from iqlabs.sdk.utils.rate_limiter import create_rate_limiter
from iqlabs.sdk.utils.seed import derive_seed_bytes, derive_dm_seed, sort_pubkeys


async def test_concurrency():
    print("Testing concurrency...")
    results = []

    async def worker(item: int, index: int):
        await asyncio.sleep(0.01)  # Simulate async work
        results.append(item * 2)

    items = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    await run_with_concurrency(items, limit=3, worker=worker)

    assert len(results) == 10
    assert sorted(results) == [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
    print(f"  Concurrency test passed! Results: {sorted(results)}")


async def test_rate_limiter():
    print("Testing rate limiter...")
    limiter = create_rate_limiter(100)  # 100 RPS

    start = asyncio.get_event_loop().time()
    for _ in range(5):
        await limiter.wait()
    elapsed = asyncio.get_event_loop().time() - start

    # At 100 RPS, 5 requests should take ~40ms minimum
    assert elapsed >= 0.03  # Allow some tolerance
    print(f"  Rate limiter test passed! 5 requests took {elapsed:.3f}s")


def test_seed_utils():
    print("Testing seed utilities...")

    # Test hex passthrough
    hex_str = "0123456789abcdef" * 4
    result = derive_seed_bytes(hex_str)
    assert result.hex() == hex_str
    print(f"  Hex passthrough: {hex_str[:16]}... -> {result.hex()[:16]}...")

    # Test keccak hashing
    text_result = derive_seed_bytes("hello")
    assert len(text_result) == 32
    print(f"  Keccak hash of 'hello': {text_result.hex()[:32]}...")

    # Test DM seed
    dm_seed = derive_dm_seed("user-a", "user-b")
    dm_seed_reversed = derive_dm_seed("user-b", "user-a")
    assert dm_seed == dm_seed_reversed  # Order shouldn't matter
    print(f"  DM seed (user-a, user-b): {dm_seed.hex()[:32]}...")

    # Test sort
    a, b = sort_pubkeys("zzz", "aaa")
    assert a == "aaa" and b == "zzz"
    print("  Sort pubkeys test passed!")


async def main():
    print("=" * 50)
    print("IQLabs SDK Unit Tests (No Network)")
    print("=" * 50)

    test_seed_utils()
    await test_rate_limiter()
    await test_concurrency()

    print("=" * 50)
    print("All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
