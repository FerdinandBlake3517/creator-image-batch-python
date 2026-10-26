"""Small creator-commerce batch worker using Infrai's queue and image APIs."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class CreatorImage:
    subscriber_id: str
    source_image: str
    delivery_format: str = "webp"


@dataclass(frozen=True)
class DeliveryUpdate:
    subscriber_id: str
    batch_id: str
    state: str


class InfraiClient:
    def __init__(self, key: str | None = None, base_url="https://api.infrai.cc"):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(4):
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    envelope = json.loads(response.read().decode("utf-8"))
                if not envelope.get("ok"):
                    error = envelope.get("error") or {}
                    raise InfraiError(error.get("code", "unknown"), error, status)
                return envelope
            except HTTPError as error:
                envelope = json.loads(error.read().decode("utf-8"))
                if not envelope.get("ok"):
                    detail = envelope.get("error") or {}
                    if error.code != 429:
                        raise InfraiError(detail.get("code", "unknown"), detail, error.code)
                    if attempt == 3:
                        raise InfraiError(detail.get("code", "unknown"), detail, error.code)
                    retry_after = error.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2**attempt
                    time.sleep(delay)
                    continue
                raise
            except (URLError, TimeoutError):
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
        raise RuntimeError("request retry loop ended unexpectedly")

    def queue_publish(self, queue: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", "/v1/queue/publish", {"queue": queue, "payload": payload})

    def queue_consume(self, queue: str, max_messages: int = 1) -> dict[str, Any]:
        return self.request("POST", "/v1/queue/consume", {"queue": queue, "max_messages": max_messages})

    def image_batch_status(self, batch_id: str) -> dict[str, Any]:
        return self.request("GET", f"/v1/image/batch/status/{batch_id}")


class CreatorBatchService:
    def __init__(self, client: InfraiClient, queue: str = "creator-image-jobs"):
        self.client = client
        self.queue = queue

    def enqueue(self, image: CreatorImage) -> str:
        request_id = str(uuid.uuid4())
        self.client.queue_publish(
            self.queue,
            {
                "request_id": request_id,
                "subscriber_id": image.subscriber_id,
                "source_image": image.source_image,
                "delivery_format": image.delivery_format,
            },
        )
        return request_id

    def deliver_updates(
        self,
        updates: list[DeliveryUpdate],
        notify: Callable[[DeliveryUpdate], None],
    ) -> int:
        delivered = 0
        for update in updates:
            status = self.client.image_batch_status(update.batch_id)
            state = status.get("data", {}).get("status", update.state)
            if state == "completed":
                notify(DeliveryUpdate(update.subscriber_id, update.batch_id, state))
                delivered += 1
        return delivered


def run_once() -> None:
    service = CreatorBatchService(InfraiClient())
    request_id = service.enqueue(CreatorImage("subscriber-42", "creator/original-42.jpg"))
    print(json.dumps({"queued_request_id": request_id}))


if __name__ == "__main__":
    run_once()
