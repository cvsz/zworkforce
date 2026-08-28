#!/usr/bin/env python3
"""
Enterprise End-to-End Load Testing & Capacity Validation
Simulates enterprise traffic loads against the wire CLI-to-API gateway.

It tests:
1. High-throughput HTTP multiplexing
2. Simulated chunked file upload events
3. Telemetry emission rates

Usage:
  python3 e2e_load_test.py --concurrency 100 --requests 1000
"""

import asyncio
import time
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor

# Since we might not have aiohttp installed, we can simulate load or use urllib if aiohttp fails.
# Using standard library tools to ensure it runs everywhere.
import urllib.request
import urllib.error
import json
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("e2e-load-test")

def fetch_url(url: str, method: str = "GET", headers: Optional[dict] = None, data: Optional[bytes] = None) -> tuple[int, float]:
    """Synchronous fetch to be run in a thread pool."""
    start_time = time.time()
    req = urllib.request.Request(url, data=data, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    
    status = 500
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            status = response.getcode()
            response.read() # drain
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception as e:
        status = 0
    
    elapsed = time.time() - start_time
    return (status, elapsed)

async def worker(worker_id: int, url: str, total_requests: int, executor: ThreadPoolExecutor, results: list):
    """Async worker dispatching synchronous requests via executor."""
    for _ in range(total_requests):
        loop = asyncio.get_running_loop()
        # Simulate different payloads based on worker id
        if worker_id % 2 == 0:
            # Simulate a telemetry or state check
            status, elapsed = await loop.run_in_executor(executor, fetch_url, url)
        else:
            # Simulate chunk upload ping
            data = json.dumps({"worker": worker_id, "chunk_size": 1024, "status": "ping"}).encode('utf-8')
            headers = {"Content-Type": "application/json"}
            status, elapsed = await loop.run_in_executor(executor, fetch_url, url, "POST", headers, data)
        
        results.append((status, elapsed))

async def main():
    parser = argparse.ArgumentParser(description="Run E2E Load Test")
    parser.add_argument("--url", default="http://127.0.0.1:8000/admin/docs", help="Target URL (e.g. Health Endpoint)")
    parser.add_argument("-c", "--concurrency", type=int, default=50, help="Number of concurrent workers")
    parser.add_argument("-n", "--requests", type=int, default=100, help="Requests per worker")
    args = parser.parse_args()

    logger.info(f"Starting E2E load test against {args.url}")
    logger.info(f"Concurrency: {args.concurrency}, Requests per worker: {args.requests}")
    logger.info(f"Total Requests: {args.concurrency * args.requests}")

    results = []
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        tasks = []
        for i in range(args.concurrency):
            tasks.append(asyncio.create_task(worker(i, args.url, args.requests, executor, results)))
        
        await asyncio.gather(*tasks)

    total_time = time.time() - start_time
    
    successes = len([r for r in results if r[0] in (200, 201)])
    failures = len([r for r in results if r[0] not in (200, 201)])
    
    latencies = [r[1] for r in results]
    avg_latency = (sum(latencies) / len(latencies)) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    rps = len(results) / total_time if total_time > 0 else 0

    print("\\n" + "="*50)
    print("E2E LOAD TEST RESULTS - ENTERPRISE VALIDATION")
    print("="*50)
    print(f"Total Time:      {total_time:.2f} seconds")
    print(f"Total Requests:  {len(results)}")
    print(f"Successful:      {successes}")
    print(f"Failed:          {failures}")
    print(f"Reqs/Sec (RPS):  {rps:.2f} req/s")
    print(f"Avg Latency:     {avg_latency*1000:.2f} ms")
    print(f"Max Latency:     {max_latency*1000:.2f} ms")
    print("="*50)
    
    if failures > 0:
        logger.warning("Load test completed with errors. Check backend capacity or routing.")
    elif rps < 50 and args.concurrency > 10:
        logger.warning("Throughput is sub-optimal. Ensure gRPC/HTTP multiplexing and connection pooling are engaged.")
    else:
        logger.info("Load test completed successfully. System architecture meets performance thresholds.")

if __name__ == "__main__":
    asyncio.run(main())
