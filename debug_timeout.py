#!/usr/bin/env python3
"""
Debug script to help identify 504 timeout issues in LightRAG queries.
This script will help you pinpoint exactly where the timeout occurs.
"""

import asyncio
import time
import logging
import httpx
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_query_with_timeout(url: str, query: str, timeout: int = 350):
    """
    Test a query with detailed timeout monitoring
    """
    logger.info(f"Testing query with {timeout}s timeout")
    logger.info(f"Query: {query[:100]}...")

    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                json={"query": query, "mode": "hybrid"},
                headers={"Content-Type": "application/json"}
            )

            end_time = time.time()
            duration = end_time - start_time

            logger.info(f"Request completed in {duration:.2f}s")
            logger.info(f"Status code: {response.status_code}")

            if response.status_code == 200:
                logger.info("✅ Request successful!")
                response_data = response.json()
                logger.info(f"Response length: {len(str(response_data))}")
            elif response.status_code == 504:
                logger.error("❌ 504 Gateway Timeout - Server timeout")
            else:
                logger.error(
                    f"❌ Unexpected status code: {response.status_code}")
                logger.error(f"Response: {response.text}")

    except httpx.TimeoutException:
        end_time = time.time()
        duration = end_time - start_time
        logger.error(f"❌ Client timeout after {duration:.2f}s")
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        logger.error(f"❌ Error after {duration:.2f}s: {str(e)}")


async def main():
    """
    Run timeout tests with different configurations
    """
    # Update these values for your setup
    BASE_URL = "http://localhost:9621"  # Update if different
    QUERY_URL = f"{BASE_URL}/query"

    # Test queries of different complexities
    test_queries = [
        "What is e-invoicing?",  # Simple query
        "Recommend e-invoicing software for small business with budget under $5K",  # Complex query
    ]

    # Test different timeout values
    timeout_values = [60, 120, 300, 350]

    for query in test_queries:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing query: {query}")
        logger.info(f"{'='*60}")

        for timeout in timeout_values:
            logger.info(f"\n--- Testing with {timeout}s timeout ---")
            await test_query_with_timeout(QUERY_URL, query, timeout)
            await asyncio.sleep(2)  # Brief pause between tests

if __name__ == "__main__":
    print("LightRAG Timeout Debug Script")
    print("=" * 50)
    print("This script will help identify where 504 timeouts occur.")
    print("Make sure your LightRAG server is running on localhost:9621")
    print("=" * 50)

    asyncio.run(main())
