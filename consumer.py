import asyncio
import json
import logging

from vectra_contracts.models import LaneObservation, TrafficDetectionEvent

from .config import settings
from .decision_engine import decide_signal
from .redis_client import cache_and_publish_decision, get_previous_signals, redis_client

logger = logging.getLogger(__name__)

# In-memory latest-known observation per (intersection, lane_group). Good
# enough for a hackathon single-instance deployment; swap for a Redis hash
# if signal-service ever runs with more than one replica.
_latest_by_intersection: dict[str, dict[str, LaneObservation]] = {}


def _update_buffer(event: TrafficDetectionEvent) -> dict[str, LaneObservation]:
    key = str(event.intersection_id)
    lanes = _latest_by_intersection.setdefault(key, {})
    lanes[event.lane_group] = LaneObservation(
        lane_group=event.lane_group,
        vehicle_counts=event.vehicle_counts,
        avg_speed_kmh=event.avg_speed_kmh,
        queue_length_m=event.queue_length_m,
    )
    return lanes


async def _handle_traffic_detection(raw: str) -> None:
    payload = json.loads(raw)
    event = TrafficDetectionEvent(**payload)

    lanes = _update_buffer(event)
    previous_signals = await get_previous_signals(str(event.intersection_id))

    decision = decide_signal(
        intersection_id=event.intersection_id,
        lanes=list(lanes.values()),
        previous_signals=previous_signals,
        emergency_override=event.traffic_type.value == "EMERGENCY",
    )

    await cache_and_publish_decision(
        settings.signal_channel, decision.model_dump(mode="json")
    )
    logger.info(
        "intersection=%s traffic_type=%s -> %s",
        event.intersection_id,
        decision.traffic_type.value,
        {ls.lane_group: ls.color.value for ls in decision.lane_signals},
    )


async def run_traffic_detection_consumer() -> None:
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(settings.traffic_detection_channel)
    logger.info("Subscribed to %s", settings.traffic_detection_channel)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                await _handle_traffic_detection(message["data"])
            except Exception:  # noqa: BLE001 — keep the consumer alive
                logger.exception("Failed to process traffic-detection message")
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(settings.traffic_detection_channel)
        await pubsub.close()
