import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from vectra_contracts.models import SignalDecisionRequest, SignalDecisionResponse

from .consumer import run_traffic_detection_consumer
from .decision_engine import decide_signal
from .redis_client import get_previous_signals

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer_task = asyncio.create_task(run_traffic_detection_consumer())
    logger.info("Vectra signal service started")
    yield
    consumer_task.cancel()
    await asyncio.gather(consumer_task, return_exceptions=True)
    logger.info("Vectra signal service stopped")


app = FastAPI(title="Vectra Signal Service API", version="0.1.0", lifespan=lifespan)


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/api/v1/infer/signal-decision", response_model=SignalDecisionResponse)
async def infer_signal_decision(body: SignalDecisionRequest) -> SignalDecisionResponse:
    """Synchronous test endpoint — the one to hit from a single laptop while
    prototyping, before the two services are wired together over Redis.
    """
    previous_signals = await get_previous_signals(str(body.intersection_id))
    return decide_signal(
        intersection_id=body.intersection_id,
        lanes=body.lanes,
        previous_signals=previous_signals,
        emergency_override=body.emergency_override,
        decided_at=body.captured_at,
    )
