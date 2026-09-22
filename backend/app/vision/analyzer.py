from collections import defaultdict

from app.models import ApproachState, Direction


VEHICLE_WEIGHTS = {
    "motorcycle": 0.5,
    "car": 1.0,
    "bus": 2.0,
    "truck": 2.0,
}


def direction_from_center(x: float, y: float, width: int, height: int) -> Direction:
    """Assign a detection to its closest incoming edge of an overhead frame."""
    dx = x - width / 2
    dy = y - height / 2
    if abs(dx) > abs(dy):
        return Direction.E if dx > 0 else Direction.W
    return Direction.S if dy > 0 else Direction.N


def aggregate_detections(
    detections: list[dict], width: int, height: int
) -> dict[Direction, ApproachState]:
    totals = defaultdict(lambda: {"vehicles": 0, "weighted": 0.0, "queue": 0})
    for detection in detections:
        name = detection["class"]
        if name not in VEHICLE_WEIGHTS:
            continue
        x1, y1, x2, y2 = detection["box"]
        direction = direction_from_center((x1 + x2) / 2, (y1 + y2) / 2, width, height)
        totals[direction]["vehicles"] += 1
        totals[direction]["weighted"] += VEHICLE_WEIGHTS[name]
        # Initial queue proxy: detections inside the central 65% of the frame.
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        if width * 0.175 < cx < width * 0.825 and height * 0.175 < cy < height * 0.825:
            totals[direction]["queue"] += 1

    return {
        direction: ApproachState(
            vehicles=totals[direction]["vehicles"],
            queue=totals[direction]["queue"],
            weighted_vehicles=round(totals[direction]["weighted"], 1),
        )
        for direction in Direction
    }

