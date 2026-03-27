from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import yetter as yetter_sdk
from yetter.client import yetter as YetterBackend


def test_configure_updates_global_client_state():
    yetter_sdk.configure(
        api_key="test-key",
        api_endpoint="https://api.example.test",
    )

    assert YetterBackend._api_key == "Key test-key"
    assert YetterBackend._endpoint == "https://api.example.test"


def test_run_requires_configuration(run_async):
    with pytest.raises(RuntimeError, match="configure"):
        run_async(yetter_sdk.run("demo/model", {"prompt": "hello"}))


def test_run_waits_for_stream_completion(monkeypatch, run_async):
    yetter_sdk.configure(api_key="test-key")

    payload = {"images": ["https://cdn.example.test/image.png"]}
    fake_stream = SimpleNamespace(done=AsyncMock(return_value=payload))
    stream_mock = AsyncMock(return_value=fake_stream)
    monkeypatch.setattr(yetter_sdk._yetter_instance, "stream", stream_mock)

    result = run_async(yetter_sdk.run("demo/model", {"prompt": "hello"}))

    assert result == payload
    stream_mock.assert_awaited_once_with("demo/model", {"prompt": "hello"})
    fake_stream.done.assert_awaited_once_with()


def test_subscribe_delegates_to_shared_instance(monkeypatch, run_async):
    yetter_sdk.configure(api_key="test-key")

    payload = {"status": "ok"}
    callback = object()
    subscribe_mock = AsyncMock(return_value=payload)
    monkeypatch.setattr(yetter_sdk._yetter_instance, "subscribe", subscribe_mock)

    result = run_async(
        yetter_sdk.subscribe(
            "demo/model",
            {"prompt": "hello"},
            on_queue_update=callback,
        )
    )

    assert result == payload
    subscribe_mock.assert_awaited_once_with(
        "demo/model",
        {"prompt": "hello"},
        callback,
    )
