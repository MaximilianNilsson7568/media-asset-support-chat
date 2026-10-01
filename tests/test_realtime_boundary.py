import httpx

from support_service import InfraiRealtime


def test_publish_uses_the_documented_envelope_and_idempotency_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/realtime/publish"
        assert request.headers["Idempotency-Key"] == "decision:asset-42:processing"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json={"ok": True, "data": {"published": True}})

    realtime = InfraiRealtime("test-key", transport=httpx.MockTransport(handler))
    result = realtime.publish_decision(
        "creator-support-maya",
        "maya",
        {"asset_id": "asset-42", "queue": "processing"},
    )

    assert result == {"published": True}
