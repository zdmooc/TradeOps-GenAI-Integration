from services.common.logging import setup_logging
from services.common.kafka import consumer, consume_forever

log = setup_logging("notifier")

async def handler(topic: str, msg: dict):
    if topic in ("workflow.requested", "workflow.approved", "orders.filled", "genai.review.created", "risk.breach", "audit.logged"):
        log.info("NOTIFY topic=%s payload=%s", topic, msg.get("payload"))

async def main():
    cons = consumer(
        ["workflow.requested","genai.review.created","workflow.approved","orders.filled","risk.breach","audit.logged"],
        group_id="notifier"
    )
    await consume_forever(cons, handler)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
