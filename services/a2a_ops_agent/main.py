from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from typing import Any

from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from a2a.types.a2a_pb2 import TaskState
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from services.agent_controller.mcp_client import (
    get_mq_queue_status,
    get_payment_mq_health,
)

McpHealthProvider = Callable[[], Awaitable[dict[str, Any]]]
McpQueueProvider = Callable[[str], Awaitable[dict[str, Any]]]


class A2APolicyError(PermissionError):
    pass


class OperationsAgentService:
    """Business-neutral A2A facade that re-authorizes its downstream MCP calls."""

    def __init__(
        self,
        *,
        allowed_peers: frozenset[str],
        health_provider: McpHealthProvider = get_payment_mq_health,
        queue_provider: McpQueueProvider = get_mq_queue_status,
    ) -> None:
        self.allowed_peers = allowed_peers
        self.health_provider = health_provider
        self.queue_provider = queue_provider

    def authorize(self, peer_id: str, skill_id: str) -> None:
        if not peer_id or peer_id not in self.allowed_peers:
            raise A2APolicyError("A2A_PEER_DENIED")
        if skill_id not in {"payment_mq_health", "payment_mq_queue_status"}:
            raise A2APolicyError("A2A_SKILL_DENIED")

    async def execute(
        self,
        *,
        peer_id: str,
        skill_id: str,
        query: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.authorize(peer_id, skill_id)
        metadata = metadata or {}

        if skill_id == "payment_mq_health":
            payload = await self.health_provider()
            return {
                "agent_id": "operations-agent",
                "peer_id": peer_id,
                "skill_id": skill_id,
                "source": "native-mcp",
                "result": payload,
            }

        queue = str(metadata.get("queue") or query or "Q.PAYMENT").strip().upper()
        payload = await self.queue_provider(queue)
        return {
            "agent_id": "operations-agent",
            "peer_id": peer_id,
            "skill_id": skill_id,
            "source": "native-mcp",
            "result": payload,
        }


class OperationsAgentExecutor(AgentExecutor):
    def __init__(self, service: OperationsAgentService) -> None:
        self.service = service

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.id,
            context_id=task.context_id,
        )
        await updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message("Payment Operations agent is evaluating the request."),
        )

        metadata = dict(context.metadata or {})
        peer_id = str(metadata.get("mayabank.peer_id", "")).strip()
        skill_id = str(
            metadata.get("mayabank.skill_id", "payment_mq_health")
        ).strip()
        query = get_message_text(context.message) if context.message else ""

        try:
            result = await self.service.execute(
                peer_id=peer_id,
                skill_id=skill_id,
                query=query or "",
                metadata=metadata,
            )
        except A2APolicyError as exc:
            await updater.update_status(
                state=TaskState.TASK_STATE_REJECTED,
                message=new_text_message(str(exc)),
            )
            return
        except Exception:
            await updater.update_status(
                state=TaskState.TASK_STATE_FAILED,
                message=new_text_message("A2A_DOWNSTREAM_FAILURE"),
            )
            return

        await updater.add_artifact(
            parts=[
                new_text_part(
                    text=json.dumps(result, sort_keys=True),
                    media_type="application/json",
                )
            ]
        )
        await updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message("Payment Operations task completed."),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.current_task:
            updater = TaskUpdater(
                event_queue=event_queue,
                task_id=context.current_task.id,
                context_id=context.current_task.context_id,
            )
            await updater.update_status(state=TaskState.TASK_STATE_CANCELED)
            return
        raise NotImplementedError("No active task to cancel")


def _allowed_peers() -> frozenset[str]:
    raw = os.getenv("A2A_ALLOWED_PEERS", "investigation-agent")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def build_agent_card(public_url: str | None = None) -> AgentCard:
    base = (public_url or os.getenv("A2A_PUBLIC_URL", "http://127.0.0.1:8021")).rstrip("/")
    return AgentCard(
        name="MayaBank Payment Operations Agent",
        description=(
            "A governed operations agent that accepts bounded A2A diagnostic work "
            "and re-authorizes downstream calls through native MCP."
        ),
        version="d092-r1",
        default_input_modes=["text/plain"],
        default_output_modes=["application/json", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                url=base,
                protocol_version="1.0",
            )
        ],
        skills=[
            AgentSkill(
                id="payment_mq_health",
                name="Payment MQ health",
                description="Read the deterministic payment MQ health summary via native MCP.",
                input_modes=["text/plain"],
                output_modes=["application/json"],
                tags=["payments", "operations", "mq", "mcp"],
                examples=["Check payment MQ health"],
            ),
            AgentSkill(
                id="payment_mq_queue_status",
                name="Payment MQ queue status",
                description="Read one approved payment queue status via native MCP.",
                input_modes=["text/plain"],
                output_modes=["application/json"],
                tags=["payments", "operations", "mq", "mcp"],
                examples=["Q.PAYMENT"],
            ),
        ],
    )


async def _health(_request):
    return JSONResponse(
        {
            "status": "ok",
            "service": "a2a-ops-agent",
            "protocol_binding": "JSONRPC",
            "wire_protocol_version": "1.0",
            "sdk_baseline": "a2a-sdk==1.2.1",
            "runtime_evidence": "PENDING",
        }
    )


def build_app(
    *,
    service: OperationsAgentService | None = None,
    public_url: str | None = None,
) -> Starlette:
    agent_card = build_agent_card(public_url)
    executor = OperationsAgentExecutor(
        service or OperationsAgentService(allowed_peers=_allowed_peers())
    )
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = [Route("/health", _health)]
    routes.extend(
        create_agent_card_routes(
            agent_card,
            card_url=AGENT_CARD_WELL_KNOWN_PATH,
        )
    )
    routes.extend(create_jsonrpc_routes(handler, rpc_url="/"))
    return Starlette(routes=routes)


app = build_app()
