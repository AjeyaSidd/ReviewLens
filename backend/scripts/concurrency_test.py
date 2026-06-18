import asyncio
import httpx
import time

# Target environment configuration
RENDER_URL = "https://app-review-intelligence.onrender.com"  # Replace with http://localhost:8000 for local testing
ENDPOINT = "/catalog"
NUM_REQUESTS = 80

async def send_request(client, i):
    start = time.time()
    response = await client.get(f"{RENDER_URL}{ENDPOINT}")
    elapsed = time.time() - start
    print(f"Request {i}: status={response.status_code}, time={elapsed:.2f}s")
    return elapsed

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        tasks = [send_request(client, i) for i in range(NUM_REQUESTS)]
        times = await asyncio.gather(*tasks)
    print(f"\nTotal time: {max(times):.2f}s | Avg: {sum(times)/len(times):.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
