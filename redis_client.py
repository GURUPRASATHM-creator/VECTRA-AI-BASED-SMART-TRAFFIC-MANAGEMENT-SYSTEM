import json

import redis.asyncio as redis

from .config import settings

redis_client: redis.Redis = redis.from_url(settings.redis_url, decode_responses=True)


def signal_key(intersection_id: str) -> str:
    return f"signal:{intersection_id}"


async def get_previous_signals(intersection_id: str) -> dict[str, str] | None:
    """Returns {lane_group: color} from the last published decision, so the
    engine can insert a YELLOW transition for lanes losing GREEN.
    """
    raw = await redis_client.get(signal_key(intersection_id))
    if not raw:
        return None
    decision = json.loads(raw)
    return {ls["lane_group"]: ls["color"] for ls in decision.get("lane_signals", [])}


async def cache_and_publish_decision(channel: str, decision: dict) -> None:
    payload = json.dumps(decision, default=str)
    await redis_client.set(signal_key(str(decision["intersection_id"])), payload)
    await redis_client.publish(channel, payload)
