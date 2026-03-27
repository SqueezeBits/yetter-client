from yetter.client import yetter as YetterBackend
from yetter.types import GenerateImageResponse


class FakeCompletedClient:
    def __init__(self):
        self.generate_payload = None
        self.response_request = None

    def get_api_endpoint(self):
        return "https://api.example.test"

    async def generate_image(self, body):
        self.generate_payload = body
        return GenerateImageResponse(
            status="COMPLETED",
            request_id="req-123",
            response_url="https://api.example.test/requests/req-123",
            status_url="https://api.example.test/requests/req-123/status",
            cancel_url="https://api.example.test/requests/req-123/cancel",
            queue_position=0,
        )

    async def get_response(self, request):
        self.response_request = request
        return {"images": ["https://cdn.example.test/final.png"]}


def test_stream_returns_final_payload_for_completed_requests(monkeypatch, run_async):
    YetterBackend.configure(api_key="test-key")
    fake_client = FakeCompletedClient()
    monkeypatch.setattr(YetterBackend, "_get_client", lambda: fake_client)

    stream = run_async(YetterBackend.stream("demo/model", {"prompt": "hello"}))
    result = run_async(stream.done())

    assert result == {"images": ["https://cdn.example.test/final.png"]}
    assert fake_client.generate_payload == {"model": "demo/model", "prompt": "hello"}
    assert fake_client.response_request.url == "https://api.example.test/requests/req-123"
