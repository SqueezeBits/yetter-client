import asyncio
from unittest.mock import AsyncMock

import pytest

from yetter.client import yetter as YetterBackend
from yetter.types import GenerateImageResponse, GetStatusResponse, LogEntry


class FakeSubscribeClient:
    def __init__(self, statuses, final_response):
        self.statuses = list(statuses)
        self.final_response = final_response
        self.cancel = AsyncMock()
        self.generate_payload = None
        self.status_requests = []
        self.response_request = None

    async def generate_image(self, payload):
        self.generate_payload = payload
        return GenerateImageResponse(
            status="IN_QUEUE",
            request_id="req-123",
            response_url="https://api.example.test/requests/req-123",
            status_url="https://api.example.test/requests/req-123/status",
            cancel_url="https://api.example.test/requests/req-123/cancel",
            queue_position=2,
        )

    async def get_status(self, request):
        self.status_requests.append(request)
        return self.statuses.pop(0)

    async def get_response(self, request):
        self.response_request = request
        return self.final_response


def test_subscribe_returns_response_and_calls_sync_callback(
    monkeypatch,
    run_async,
):
    YetterBackend.configure(api_key="test-key")
    updates = []
    fake_client = FakeSubscribeClient(
        statuses=[
            GetStatusResponse(status="IN_PROGRESS", queue_position=1),
            GetStatusResponse(status="COMPLETED", queue_position=0),
        ],
        final_response={"images": ["https://cdn.example.test/final.png"]},
    )

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(YetterBackend, "_get_client", lambda: fake_client)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    result = run_async(
        YetterBackend.subscribe(
            "demo/model",
            {"prompt": "hello", "logs": True},
            on_queue_update=lambda status: updates.append(status.status),
        )
    )

    assert result == {"images": ["https://cdn.example.test/final.png"]}
    assert fake_client.generate_payload == {"model": "demo/model", "prompt": "hello", "logs": True}
    assert [request.logs for request in fake_client.status_requests] == [True, True]
    assert updates == ["IN_PROGRESS", "COMPLETED"]
    assert fake_client.cancel.await_count == 0


def test_subscribe_raises_runtime_error_with_log_messages(monkeypatch, run_async):
    YetterBackend.configure(api_key="test-key")
    fake_client = FakeSubscribeClient(
        statuses=[
            GetStatusResponse(
                status="ERROR",
                logs=[LogEntry(message="first failure"), LogEntry(message="second failure")],
            )
        ],
        final_response={},
    )

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(YetterBackend, "_get_client", lambda: fake_client)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    with pytest.raises(RuntimeError, match="first failure\nsecond failure"):
        run_async(YetterBackend.subscribe("demo/model", {"prompt": "hello"}))


def test_subscribe_cancels_request_after_timeout(monkeypatch, run_async):
    YetterBackend.configure(api_key="test-key")
    fake_client = FakeSubscribeClient(
        statuses=[],
        final_response={},
    )

    class FakeLoop:
        def __init__(self):
            self._times = iter([0.0, 1801.0])

        def time(self):
            return next(self._times)

    loop = FakeLoop()
    monkeypatch.setattr(YetterBackend, "_get_client", lambda: fake_client)
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: loop)

    with pytest.raises(TimeoutError, match="timed out"):
        run_async(YetterBackend.subscribe("demo/model", {"prompt": "hello"}))

    fake_client.cancel.assert_awaited_once()
