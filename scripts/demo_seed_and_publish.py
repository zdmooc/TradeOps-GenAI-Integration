import asyncio
import httpx
from scripts.bootstrap_topics import main as bootstrap

async def main():
    await bootstrap()
    symbols = ["AAPL","MSFT","TSLA","NVDA"]
    async with httpx.AsyncClient() as client:
        for s in symbols:
            r = await client.post(f"http://market-data:8011/publish/{s}")
            r.raise_for_status()
            print("published", s, r.json()["event"]["payload"])

if __name__ == "__main__":
    asyncio.run(main())
