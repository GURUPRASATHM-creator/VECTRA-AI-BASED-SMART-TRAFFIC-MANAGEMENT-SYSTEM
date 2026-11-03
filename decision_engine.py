"""Rule-based traffic-signal decision engine.

This is a plain, side-effect-free function so it can be unit tested and
called identically from:
  - the synchronous /infer/signal-decision HTTP endpoint (single-shot testing
    on a laptop, no Redis/DB needed), and
  - the async Redis consumer (consumer.py) in the real pipeline.

The rules mirror the design prompt used for prototyping this same behaviour
with an LLM (see contracts/README.md / prior discussion):
  1. Never GREEN more than one lane group at a time.
  2. Higher weighted vehicle load -> longer GREEN, but every lane gets at
     least MIN_GREEN_SECONDS.
  3. An ambulance/emergency vehicle in any lane forces immediate GREEN there
     and RED everywhere else.
  4. A lane going from GREEN to RED passes through YELLOW_SECONDS of YELLOW.
  5. Overall traffic_type is classified from the average weighted load.
"""

from datetime import datetime, timezone

from vectra_contracts.enums import SignalColor, TrafficType
from vectra_contracts.models import LaneObservation, LaneSignal, SignalDecisionResponse

from .config import settings

VEHICLE_WEIGHTS = {"car": 1.0, "bus": 2.0, "truck": 2.0, "bike": 0.5}

MIN_GREEN_SECONDS = 10
MAX_GREEN_SECONDS = 60
YELLOW_SECONDS = 3
EMERGENCY_GREEN_SECONDS = 20

# thresholds on average weighted load per lane -> overall traffic_type
TRAFFIC_TYPE_THRESHOLDS = (
    (5.0, TrafficType.LIGHT),
    (15.0, TrafficType.MODERATE),
    (30.0, TrafficType.HEAVY),
)


def weighted_score(vehicle_counts: dict[str, int]) -> float:
    return sum(
        count * VEHICLE_WEIGHTS.get(vehicle_type, 1.0)
        for vehicle_type, count in vehicle_counts.items()
        if vehicle_type != "ambulance"
    )


def classify_traffic_type(avg_score: float) -> TrafficType:
    for threshold, label in TRAFFIC_TYPE_THRESHOLDS:
        if avg_score < threshold:
            return label
    return TrafficType.CONGESTED


def _emergency_lane(lanes: list[LaneObservation]) -> str | None:
    ambulance_lanes = [
        (lane.vehicle_counts.get("ambulance", 0), lane.lane_group) for lane in lanes
    ]
    ambulance_lanes = [al for al in ambulance_lanes if al[0] > 0]
    if not ambulance_lanes:
        return None
    ambulance_lanes.sort(reverse=True)  # highest ambulance count first
    return ambulance_lanes[0][1]


def decide_signal(
    intersection_id,
    lanes: list[LaneObservation],
    previous_signals: dict[str, str] | None = None,
    emergency_override: bool = False,
    decided_at: datetime | None = None,
) -> SignalDecisionResponse:
    if not lanes:
        raise ValueError("At least one lane observation is required")

    decided_at = decided_at or datetime.now(timezone.utc)
    previous_signals = previous_signals or {}

    emergency_lane = _emergency_lane(lanes)
    scores = {lane.lane_group: weighted_score(lane.vehicle_counts) for lane in lanes}

    if emergency_override or emergency_lane is not None:
        chosen_lane = emergency_lane or lanes[0].lane_group
        lane_signals = [
            LaneSignal(
                lane_group=lane.lane_group,
                color=SignalColor.GREEN if lane.lane_group == chosen_lane else SignalColor.RED,
                duration_seconds=EMERGENCY_GREEN_SECONDS,
            )
            for lane in lanes
        ]
        return SignalDecisionResponse(
            intersection_id=intersection_id,
            decided_at=decided_at,
            traffic_type=TrafficType.EMERGENCY,
            lane_signals=lane_signals,
            confidence=0.95,
            reasoning=f"Emergency vehicle detected in lane '{chosen_lane}'; overriding normal cycle.",
            model_version=settings.model_version,
        )

    # Normal cycle — pick the highest-load lane for GREEN.
    chosen_lane = max(scores, key=scores.get)
    chosen_score = scores[chosen_lane]
    green_duration = max(
        MIN_GREEN_SECONDS, min(MAX_GREEN_SECONDS, round(MIN_GREEN_SECONDS + chosen_score * 2))
    )

    lane_signals: list[LaneSignal] = []
    for lane in lanes:
        if lane.lane_group == chosen_lane:
            color = SignalColor.GREEN
            duration = green_duration
        elif previous_signals.get(lane.lane_group) == SignalColor.GREEN.value:
            # was GREEN last cycle, now losing it — pass through YELLOW first
            color = SignalColor.YELLOW
            duration = YELLOW_SECONDS
        else:
            color = SignalColor.RED
            duration = green_duration
        lane_signals.append(
            LaneSignal(lane_group=lane.lane_group, color=color, duration_seconds=duration)
        )

    avg_score = sum(scores.values()) / len(scores)
    has_rich_data = any(
        lane.avg_speed_kmh is not None or lane.queue_length_m is not None for lane in lanes
    )

    return SignalDecisionResponse(
        intersection_id=intersection_id,
        decided_at=decided_at,
        traffic_type=classify_traffic_type(avg_score),
        lane_signals=lane_signals,
        confidence=0.9 if has_rich_data else 0.75,
        reasoning=(
            f"Lane '{chosen_lane}' has the highest weighted load "
            f"({chosen_score:.1f}); given GREEN for {green_duration}s."
        ),
        model_version=settings.model_version,
    )
