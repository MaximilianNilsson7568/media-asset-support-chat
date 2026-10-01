from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal


class AssetStage(str, Enum):
    INGESTING = "ingesting"
    PROCESSING = "processing"
    READY = "ready"


@dataclass(frozen=True)
class SupportDecision:
    queue: Literal["ingestion", "processing", "creator-delivery"]
    priority: Literal["normal", "high"]
    reply: str


def route_asset_question(stage: AssetStage, minutes_waiting: int) -> SupportDecision:
    """Choose the owning queue and the reply shown to the creator."""
    if stage is AssetStage.INGESTING:
        return SupportDecision(
            queue="ingestion",
            priority="high" if minutes_waiting >= 15 else "normal",
            reply="Your upload is being ingested; the media team can inspect its progress.",
        )
    if stage is AssetStage.PROCESSING:
        return SupportDecision(
            queue="processing",
            priority="high" if minutes_waiting >= 30 else "normal",
            reply="Your asset is processing; the media team can inspect the active job.",
        )
    return SupportDecision(
        queue="creator-delivery",
        priority="normal",
        reply="Your asset is ready for creator delivery.",
    )


def decision_event(asset_id: str, decision: SupportDecision) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "queue": decision.queue,
        "priority": decision.priority,
        "reply": decision.reply,
    }
