import asyncio
import httpx
from pathlib import Path

async def main():
    wf = Path("/work/.demo_workflow_id").read_text(encoding="utf-8").strip()
    payload = {"approver":"risk-user","comment":"OK en paper. Règles respectées."}
    async with httpx.AsyncClient() as client:
        r = await client.post(f"http://workflow-api:8012/trade-requests/{wf}/approve", json=payload)
        r.raise_for_status()
        print("approved:", r.json())

if __name__ == "__main__":
    asyncio.run(main())
