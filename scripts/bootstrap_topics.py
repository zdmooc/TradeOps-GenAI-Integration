import asyncio
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
from services.common.config import settings

TOPICS = [
    "market.prices",
    "signals.generated",
    "risk.breach",
    "workflow.requested",
    "genai.review.created",
    "workflow.approved",
    "orders.filled",
    "audit.logged",
]

async def main():
    admin = AIOKafkaAdminClient(bootstrap_servers=settings.KAFKA_BOOTSTRAP)
    await admin.start()
    try:
        existing = set(await admin.list_topics())
        to_create = [NewTopic(name=t, num_partitions=1, replication_factor=1) for t in TOPICS if t not in existing]
        if to_create:
            await admin.create_topics(to_create)
            print("created topics:", [t.name for t in to_create])
        else:
            print("topics already exist")
    finally:
        await admin.close()

if __name__ == "__main__":
    asyncio.run(main())
