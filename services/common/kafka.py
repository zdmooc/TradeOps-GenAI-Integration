import json
import asyncio
from typing import Any, Dict, Optional
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from .config import settings
from .logging import setup_logging

log = setup_logging("common.kafka")

async def get_producer() -> AIOKafkaProducer:
    producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP)
    await producer.start()
    return producer

async def publish(topic: str, message: Dict[str, Any], key: Optional[str] = None) -> None:
    producer = await get_producer()
    try:
        payload = json.dumps(message).encode("utf-8")
        await producer.send_and_wait(topic, payload, key=(key.encode("utf-8") if key else None))
    finally:
        await producer.stop()

def consumer(topics: list[str], group_id: str) -> AIOKafkaConsumer:
    return AIOKafkaConsumer(
        *topics,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP,
        group_id=group_id,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )

async def consume_forever(cons: AIOKafkaConsumer, handler):
    await cons.start()
    try:
        async for msg in cons:
            try:
                data = json.loads(msg.value.decode("utf-8"))
                await handler(msg.topic, data)
            except Exception as e:
                log.exception("handler error topic=%s err=%s", msg.topic, e)
                await asyncio.sleep(0.25)
    finally:
        await cons.stop()
