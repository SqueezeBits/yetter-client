from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from yetter.api import YetterImageClient
from yetter.types import ClientOptions, GetStatusRequest


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_generate_image_requires_model(run_async):
    client = YetterImageClient(ClientOptions(api_key="Key test-key"))

    with pytest.raises(ValueError, match="model"):
        run_async(client.generate_image({"prompt": "hello"}))


def test_client_configure_rejects_prefixed_api_keys():
    client = YetterImageClient(ClientOptions(api_key="Key test-key"))

    with pytest.raises(ValueError, match="must not contain"):
        client.configure(ClientOptions(api_key="Key test-key"))


def test_generate_image_posts_to_model_endpoint(monkeypatch, run_async):
    client = YetterImageClient(
        ClientOptions(api_key="Key test-key", endpoint="https://api.example.test")
    )
    captured = {}

    async def fake_request(method, url, json_data=None, params=None):
        captured["method"] = method
        captured["url"] = url
        captured["json_data"] = json_data
        return DummyResponse(
            {
                "status": "IN_QUEUE",
                "request_id": "req-123",
                "response_url": "https://api.example.test/requests/req-123",
                "status_url": "https://api.example.test/requests/req-123/status",
                "cancel_url": "https://api.example.test/requests/req-123/cancel",
                "queue_position": 3,
            }
        )

    monkeypatch.setattr(client, "_request", fake_request)

    response = run_async(
        client.generate_image({"model": "demo/model", "prompt": "hello"})
    )

    assert captured == {
        "method": "POST",
        "url": "https://api.example.test/demo/model",
        "json_data": {"model": "demo/model", "prompt": "hello"},
    }
    assert response.request_id == "req-123"
    assert response.queue_position == 3


def test_get_status_appends_logs_query_flag(monkeypatch, run_async):
    client = YetterImageClient(ClientOptions(api_key="Key test-key"))
    captured = {}

    async def fake_request(method, url, json_data=None, params=None):
        captured["method"] = method
        captured["url"] = url
        return DummyResponse(
            {
                "status": "IN_PROGRESS",
                "request_id": "req-123",
                "response_url": "https://api.example.test/requests/req-123",
                "status_url": "https://api.example.test/requests/req-123/status",
                "cancel_url": "https://api.example.test/requests/req-123/cancel",
                "queue_position": 1,
                "logs": [{"message": "queued"}],
            }
        )

    monkeypatch.setattr(client, "_request", fake_request)

    response = run_async(
        client.get_status(
            GetStatusRequest(
                url="https://api.example.test/status?request_id=req-123",
                logs=True,
            )
        )
    )

    query = parse_qs(urlparse(captured["url"]).query)

    assert captured["method"] == "GET"
    assert query["request_id"] == ["req-123"]
    assert query["logs"] == ["1"]
    assert response.logs[0].message == "queued"


def test_get_http_client_refreshes_and_closes_stale_client_when_loop_changes(
    monkeypatch,
    run_async,
):
    client = YetterImageClient(ClientOptions(api_key="Key test-key"))
    first_loop = object()
    second_loop = object()
    created_clients = []

    def fake_async_client(*, timeout):
        async def aclose():
            instance.is_closed = True

        instance = SimpleNamespace(timeout=timeout, is_closed=False, aclose=aclose)
        created_clients.append(instance)
        return instance

    monkeypatch.setattr("yetter.api.httpx.AsyncClient", fake_async_client)
    
    async def scenario():
        monkeypatch.setattr("yetter.api.asyncio.get_running_loop", lambda: first_loop)
        first_client = await client._get_http_client()

        monkeypatch.setattr("yetter.api.asyncio.get_running_loop", lambda: second_loop)
        second_client = await client._get_http_client()
        return first_client, second_client

    first_client, second_client = run_async(scenario())

    assert len(created_clients) == 2
    assert first_client is created_clients[0]
    assert second_client is created_clients[1]
    assert first_client.is_closed is True
    assert second_client.is_closed is False
    assert client._http_client_loop is second_loop
