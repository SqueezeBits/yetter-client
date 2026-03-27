import pytest

from yetter.client import YetterStream
from yetter.types import GenerateImageResponse


class FakeApiClient:
    api_key = "Key test-key"

    def get_api_endpoint(self):
        return "https://api.example.test"

    async def get_response(self, request):
        return {"request_url": request.url}


def build_stream(initial_status="IN_PROGRESS"):
    return YetterStream(
        api_client=FakeApiClient(),
        model="demo/model",
        initial_response=GenerateImageResponse(
            status=initial_status,
            request_id="req-123",
            response_url="https://api.example.test/requests/req-123",
            status_url="https://api.example.test/requests/req-123/status",
            cancel_url="https://api.example.test/requests/req-123/cancel",
            queue_position=1,
        ),
        args={"prompt": "hello"},
    )


def test_process_event_data_parses_valid_json(run_async):
    async def scenario():
        stream = build_stream()
        return await stream._process_event_data(
            '{"status":"IN_PROGRESS","request_id":"req-123","queue_position":1}'
        )

    status = run_async(scenario())

    assert status.status == "IN_PROGRESS"
    assert status.request_id == "req-123"


def test_process_event_data_rejects_invalid_json(run_async):
    async def scenario():
        stream = build_stream()
        await stream._process_event_data("not-json")

    with pytest.raises(ValueError, match="Error parsing SSE data"):
        run_async(scenario())


def test_done_uses_background_consumer_when_stream_not_started(monkeypatch, run_async):
    async def scenario():
        stream = build_stream()

        async def fake_consume():
            if not stream._done_future.done():
                stream._done_future.set_result(
                    {"images": ["https://cdn.example.test/final.png"]}
                )

        monkeypatch.setattr(stream, "_consume_stream", fake_consume)
        result = await stream.done()
        return result, stream._stream_consumed

    result, stream_consumed = run_async(scenario())

    assert result == {"images": ["https://cdn.example.test/final.png"]}
    assert stream_consumed is False


def test_iterating_completed_stream_yields_initial_terminal_status(run_async):
    async def collect():
        stream = build_stream(initial_status="COMPLETED")
        stream._stream_ended = True
        items = []
        async for item in stream:
            items.append(item)
        return items

    statuses = run_async(collect())

    assert [item.status for item in statuses] == ["COMPLETED"]
    assert statuses[0].request_id == "req-123"
