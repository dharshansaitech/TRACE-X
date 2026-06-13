# backend/services/pubsub_service.py
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Awaitable

import structlog
from google.api_core.exceptions import AlreadyExists
from google.cloud import pubsub_v1

from api.config import Settings

logger = structlog.get_logger(__name__)

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class PubSubService:
    """
    Google Cloud Pub/Sub publisher and subscriber with async message handlers.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.project_id = settings.gcp_project_id
        self._publisher: pubsub_v1.PublisherClient | None = None
        self._subscriber: pubsub_v1.SubscriberClient | None = None
        self._handlers: dict[str, list[MessageHandler]] = {}
        self._background_tasks: list[asyncio.Task] = []
        self._running = False

    @property
    def publisher(self) -> pubsub_v1.PublisherClient:
        if self._publisher is None:
            self._publisher = pubsub_v1.PublisherClient()
        return self._publisher

    @property
    def subscriber(self) -> pubsub_v1.SubscriberClient:
        if self._subscriber is None:
            self._subscriber = pubsub_v1.SubscriberClient()
        return self._subscriber

    def topic_path(self, topic_name: str) -> str:
        return self.publisher.topic_path(self.project_id, topic_name)

    def subscription_path(self, subscription_name: str) -> str:
        return self.subscriber.subscription_path(self.project_id, subscription_name)

    async def ensure_topic(self, topic_name: str) -> str:
        """Create topic if it doesn't exist."""
        path = self.topic_path(topic_name)
        loop = asyncio.get_event_loop()

        def _create():
            try:
                self.publisher.create_topic(name=path)
                logger.info("pubsub_topic_created", topic=path)
            except AlreadyExists:
                pass
            except Exception as exc:
                logger.warning("pubsub_topic_creation_failed", topic=path, error=str(exc))
            return path

        return await loop.run_in_executor(None, _create)

    async def ensure_subscription(
        self, topic_name: str, subscription_name: str
    ) -> str:
        """Create subscription if it doesn't exist."""
        topic = self.topic_path(topic_name)
        sub_path = self.subscription_path(subscription_name)
        loop = asyncio.get_event_loop()

        def _create():
            try:
                self.subscriber.create_subscription(name=sub_path, topic=topic)
                logger.info("pubsub_subscription_created", subscription=sub_path)
            except AlreadyExists:
                pass
            except Exception as exc:
                logger.warning(
                    "pubsub_subscription_creation_failed",
                    subscription=sub_path,
                    error=str(exc),
                )
            return sub_path

        return await loop.run_in_executor(None, _create)

    async def publish(self, topic_name: str, data: dict[str, Any], **attributes: str) -> str | None:
        """Publish a message to a Pub/Sub topic."""
        loop = asyncio.get_event_loop()
        topic_path = self.topic_path(topic_name)
        message_data = json.dumps(data, default=str).encode("utf-8")

        def _publish():
            try:
                future = self.publisher.publish(
                    topic_path,
                    data=message_data,
                    **attributes,
                )
                message_id = future.result(timeout=10)
                return message_id
            except Exception as exc:
                logger.error("pubsub_publish_failed", topic=topic_name, error=str(exc))
                return None

        return await loop.run_in_executor(None, _publish)

    async def publish_trace(self, trace_data: dict[str, Any]) -> str | None:
        """Publish a trace message."""
        return await self.publish(
            self.settings.pubsub_traces_topic,
            trace_data,
            message_type="trace",
            agent_id=str(trace_data.get("agent_id", "")),
        )

    async def publish_event(self, event_data: dict[str, Any]) -> str | None:
        """Publish an event message."""
        return await self.publish(
            self.settings.pubsub_events_topic,
            event_data,
            message_type="event",
        )

    async def publish_repair(self, repair_data: dict[str, Any]) -> str | None:
        """Publish a repair message."""
        return await self.publish(
            self.settings.pubsub_repairs_topic,
            repair_data,
            message_type="repair",
        )

    def register_handler(self, topic_name: str, handler: MessageHandler) -> None:
        """Register an async message handler for a topic."""
        if topic_name not in self._handlers:
            self._handlers[topic_name] = []
        self._handlers[topic_name].append(handler)

    async def start_background_subscriber(self) -> None:
        """Start background polling for messages on registered subscriptions."""
        self._running = True

        # Ensure infrastructure exists
        try:
            await self.ensure_topic(self.settings.pubsub_traces_topic)
            await self.ensure_topic(self.settings.pubsub_events_topic)
            await self.ensure_subscription(
                self.settings.pubsub_traces_topic,
                self.settings.pubsub_subscription_traces,
            )
            await self.ensure_subscription(
                self.settings.pubsub_events_topic,
                self.settings.pubsub_subscription_events,
            )
        except Exception as exc:
            logger.warning("pubsub_setup_skipped", error=str(exc))
            return

        # Start polling task
        task = asyncio.create_task(
            self._poll_subscription(
                self.settings.pubsub_subscription_traces,
                self.settings.pubsub_traces_topic,
            )
        )
        self._background_tasks.append(task)

        task2 = asyncio.create_task(
            self._poll_subscription(
                self.settings.pubsub_subscription_events,
                self.settings.pubsub_events_topic,
            )
        )
        self._background_tasks.append(task2)

    async def _poll_subscription(
        self, subscription_name: str, topic_name: str
    ) -> None:
        """Poll a subscription for messages."""
        sub_path = self.subscription_path(subscription_name)
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                def _pull():
                    return self.subscriber.pull(
                        request={
                            "subscription": sub_path,
                            "max_messages": 10,
                        },
                        timeout=5,
                    )

                response = await loop.run_in_executor(None, _pull)

                if not response.received_messages:
                    await asyncio.sleep(1)
                    continue

                ack_ids = []
                for received in response.received_messages:
                    try:
                        data = json.loads(received.message.data.decode("utf-8"))
                        handlers = self._handlers.get(topic_name, [])
                        for handler in handlers:
                            await handler(data)
                        ack_ids.append(received.ack_id)
                    except Exception as exc:
                        logger.error("message_processing_failed", error=str(exc))

                if ack_ids:
                    def _ack():
                        self.subscriber.acknowledge(
                            request={"subscription": sub_path, "ack_ids": ack_ids}
                        )
                    await loop.run_in_executor(None, _ack)

            except Exception as exc:
                if self._running:
                    logger.warning("subscriber_poll_error", error=str(exc))
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop all background subscriber tasks."""
        self._running = False
        for task in self._background_tasks:
            task.cancel()
        self._background_tasks.clear()
        logger.info("pubsub_service_stopped")
