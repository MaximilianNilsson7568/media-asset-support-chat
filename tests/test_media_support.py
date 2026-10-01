from media_support import AssetStage, route_asset_question


def test_long_processing_job_is_routed_to_high_priority_processing() -> None:
    decision = route_asset_question(AssetStage.PROCESSING, minutes_waiting=34)

    assert decision.queue == "processing"
    assert decision.priority == "high"
    assert "active job" in decision.reply
