"""Run the decision engine standalone, with no Redis/DB/backend running.

Usage:
    python scripts/demo_cli.py --intersection <uuid> \\
        --lane north car=8 bus=1 bike=3 \\
        --lane south car=2 truck=1 \\
        --lane east car=1 ambulance=1

Each --lane takes a lane name followed by vehicle_type=count pairs. Prints
the resulting signal decision as JSON, in exactly the shape signal-service
publishes on vectra.signal.decision.
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.decision_engine import decide_signal  # noqa: E402
from vectra_contracts.models import LaneObservation  # noqa: E402


def parse_lane(tokens: list[str]) -> LaneObservation:
    lane_group, *counts = tokens
    vehicle_counts = {}
    for token in counts:
        vehicle_type, _, count = token.partition("=")
        vehicle_counts[vehicle_type] = int(count)
    return LaneObservation(lane_group=lane_group, vehicle_counts=vehicle_counts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intersection", default=str(uuid.uuid4()))
    parser.add_argument(
        "--lane",
        action="append",
        nargs="+",
        required=True,
        metavar="LANE_GROUP VEHICLE=COUNT ...",
        help="repeatable, e.g. --lane north car=8 bus=1",
    )
    args = parser.parse_args()

    lanes = [parse_lane(tokens) for tokens in args.lane]
    decision = decide_signal(intersection_id=args.intersection, lanes=lanes)
    print(json.dumps(decision.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
