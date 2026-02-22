import asyncio
import httpx

async def main():
    payload = {"symbol":"AAPL","side":"BUY","qty":250,"reason":"Breakout sur résistance, contrôle risque requis."}
    async with httpx.AsyncClient() as client:
        r = await client.post("http://workflow-api:8012/trade-requests", json=payload)
        r.raise_for_status()
        out = r.json()
        print("workflow created:", out)
        # Persist id for next scripts
        with open("/work/.demo_workflow_id","w",encoding="utf-8") as f:
            f.write(out["workflow_id"])

if __name__ == "__main__":
    asyncio.run(main())
