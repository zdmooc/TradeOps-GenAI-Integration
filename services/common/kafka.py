import asyncio
import json
import time
from typing import Any, Dict, Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from opentelemetry.trace import SpanKind, Status, StatusCode

from .config import settings
from .logging import setup_logging
from .observability_metrics import KAFKA_HANDLER_DURATION, KAFKA_MESSAGES
from .otel import correlation_scope, inject_kafka_headers, kafka_carrier, start_span

log = setup_logging("common.kafka")


async def get_producer() -> AIOKafkaProducer:
    producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP)
    await producer.start()
    return producer


async def publish(topic: str, message: Dict[str, Any], key: Optional[str] = None) -> None:
    producer = await get_producer()
    try:
        payload = json.dumps(message).encode("utf-8")
        with start_span(
            f"kafka.publish {topic}",
            kind=SpanKind.PRODUCER,
            attributes={"messaging.system": "kafka", "messaging.destination.name": topic},
        ) as span:
            try:
                await producer.send_and_wait(
                    topic,
                    payload,
                    key=(key.encode("utf-8") if key else None),
                    headers=inject_kafka_headers(),
                )
                KAFKA_MESSAGES.labels(direction="produce", topic=topic, status="ok").inc()
            except Exception as exc:
                KAFKA_MESSAGES.labels(direction="produce", topic=topic, status="error").inc()
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
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
            carrier = kafka_carrier(msg.headers)
            started = time.perf_counter()
            with correlation_scope(carrier.get("X-Correlation-ID")):
                with start_span(
                    f"kafka.consume {msg.topic}",
                    carrier=carrier,
                    kind=SpanKind.CONSUMER,
                    attributes={
                        "messaging.system": "kafka",
                        "messaging.destination.name": msg.topic,
                        "messaging.kafka.partition": msg.partition,
                        "messaging.kafka.offset": msg.offset,
                    },
                ) as span:
                    try:
                        data = json.loads(msg.value.decode("utf-8"))
                        await handler(msg.topic, data)
                        KAFKA_MESSAGES.labels(
                            direction="consume", topic=msg.topic, status="ok"
                        ).inc()
                    except Exception as exc:
                        KAFKA_MESSAGES.labels(
                            direction="consume", topic=msg.topic, status="error"
                        ).inc()
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR, str(exc)))
                        log.exception("handler error topic=%s err=%s", msg.topic, exc)
                        await asyncio.sleep(0.25)
                    finally:
                        KAFKA_HANDLER_DURATION.labels(topic=msg.topic).observe(
                            time.perf_counter() - started
                        )
    finally:
        await cons.stop()
