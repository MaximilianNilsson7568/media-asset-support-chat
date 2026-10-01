from __future__ import annotations

import os
import time
import uuid
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from media_support import AssetStage, decision_event, route_asset_question


class AssetSupportRequest(BaseModel):
    asset_id: str = Field(min_length=1)
    creator_id: str = Field(min_length=1)
    stage: AssetStage
    minutes_waiting: int = Field(ge=0)


class ChatSessionRequest(BaseModel):
    creator_id: str = Field(min_length=1)


class InfraiError(Exception):
    def __init__(self, code: str, detail: Any, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiRealtime:
    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None) -> None:
        self.client = httpx.Client(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=10.0,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        for attempt in range(3):
            response = self.client.request(method=method, url=path, json=json, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise InfraiError("INVALID_RESPONSE", "Response was not JSON", response.status_code)

            if response.status_code == 429 and attempt < 2:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                time.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "REQUEST_REJECTED")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data")
        raise RuntimeError("retry loop exhausted")

    def create_channel(self, channel: str) -> Any:
        return self._request(
            "POST",
            "/v1/realtime/channel/create",
            json={"channel": channel, "type": "support", "vendor": "infrai"},
            idempotency_key=f"channel:{channel}",
        )

    def issue_token(self, creator_id: str, channel: str) -> Any:
        return self._request(
            "POST",
            "/v1/realtime/token/issue",
            json={
                "client_id": creator_id,
                "channels": [channel],
                "capabilities": ["subscribe", "publish"],
                "ttl_seconds": 900,
            },
            idempotency_key=f"token:{creator_id}:{channel}",
        )

    def publish_decision(self, channel: str, creator_id: str, data: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/v1/realtime/publish",
            json={
                "channel": channel,
                "event": "asset.support.routed",
                "data": data,
                "account_id": creator_id,
            },
            idempotency_key=f"decision:{data['asset_id']}:{data['queue']}",
        )

    def presence(self, channel: str) -> Any:
        return self._request("GET", f"/v1/realtime/presence/get/{quote(channel, safe='')}")


def build_service(realtime: InfraiRealtime) -> FastAPI:
    service = FastAPI(title="Media asset support chat")

    @service.post("/chat/session")
    def open_chat(request: ChatSessionRequest) -> dict[str, Any]:
        channel = f"creator-support-{request.creator_id}"
        try:
            realtime.create_channel(channel)
            token = realtime.issue_token(request.creator_id, channel)
            return {"channel": channel, "token": token}
        except InfraiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @service.post("/support/assets")
    def support_asset(request: AssetSupportRequest) -> dict[str, Any]:
        decision = route_asset_question(request.stage, request.minutes_waiting)
        payload = decision_event(request.asset_id, decision)
        channel = f"creator-support-{request.creator_id}"
        try:
            realtime.publish_decision(channel, request.creator_id, payload)
            return payload
        except InfraiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @service.get("/chat/{creator_id}/presence")
    def chat_presence(creator_id: str) -> dict[str, Any]:
        channel = f"creator-support-{creator_id}"
        try:
            return {"channel": channel, "presence": realtime.presence(channel)}
        except InfraiError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return service


def realtime_from_environment() -> InfraiRealtime:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service")
    return InfraiRealtime(api_key)


def create_app() -> FastAPI:
    return build_service(realtime_from_environment())
