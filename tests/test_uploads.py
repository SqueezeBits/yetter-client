from unittest.mock import AsyncMock

import pytest

from yetter.client import yetter as YetterBackend
from yetter.types import GetUploadUrlResponse


class FakeUploadClient:
    def __init__(self, upload_response):
        self.upload_response = upload_response
        self.upload_request = None
        self.complete_request = None

    async def get_upload_url(self, request):
        self.upload_request = request
        return self.upload_response

    async def upload_complete(self, request):
        self.complete_request = request
        return {
            "message": "ok",
            "url": "https://cdn.example.test/files/example.png",
            "metadata": {"size": 4},
        }


def test_upload_file_requires_configured_key(run_async):
    with pytest.raises(ValueError, match="API key not configured"):
        run_async(YetterBackend.upload_file("/tmp/missing.png"))


def test_upload_file_uses_single_part_flow(monkeypatch, run_async, tmp_path):
    YetterBackend.configure(api_key="test-key")
    file_path = tmp_path / "image.png"
    file_path.write_bytes(b"data")

    fake_client = FakeUploadClient(
        GetUploadUrlResponse(
            mode="single",
            key="file-key",
            put_url="https://upload.example.test/single",
        )
    )
    upload_single = AsyncMock()
    progress_updates = []

    monkeypatch.setattr(YetterBackend, "_get_client", lambda: fake_client)
    monkeypatch.setattr(YetterBackend, "_upload_single", upload_single)

    result = run_async(
        YetterBackend.upload_file(str(file_path), on_progress=progress_updates.append)
    )

    assert result.url == "https://cdn.example.test/files/example.png"
    assert fake_client.upload_request.file_name == "image.png"
    assert fake_client.upload_request.content_type == "image/png"
    assert fake_client.upload_request.size == 4
    assert fake_client.complete_request.key == "file-key"
    assert upload_single.await_args.args[:4] == (
        str(file_path),
        "https://upload.example.test/single",
        "image/png",
        4,
    )
    assert progress_updates == [100]


def test_upload_file_uses_multipart_flow(monkeypatch, run_async, tmp_path):
    YetterBackend.configure(api_key="test-key")
    file_path = tmp_path / "archive.bin"
    file_path.write_bytes(b"data")

    upload_response = GetUploadUrlResponse(
        mode="multipart",
        key="file-key",
        part_size=2,
        part_urls=[
            {"part_number": 2, "url": "https://upload.example.test/part-2"},
            {"part_number": 1, "url": "https://upload.example.test/part-1"},
        ],
    )
    fake_client = FakeUploadClient(upload_response)
    upload_multipart = AsyncMock()

    monkeypatch.setattr(YetterBackend, "_get_client", lambda: fake_client)
    monkeypatch.setattr(YetterBackend, "_upload_multipart", upload_multipart)

    result = run_async(YetterBackend.upload_file(str(file_path)))

    assert result.metadata["size"] == 4
    assert fake_client.complete_request.key == "file-key"
    assert upload_multipart.await_args.args == (
        str(file_path),
        upload_response.part_urls,
        2,
        4,
        None,
    )


def test_upload_multipart_rejects_missing_part_metadata(run_async, tmp_path):
    YetterBackend.configure(api_key="test-key")
    file_path = tmp_path / "archive.bin"
    file_path.write_bytes(b"data")

    with pytest.raises(ValueError, match="missing part_size or part_urls"):
        run_async(
            YetterBackend._upload_multipart(
                str(file_path),
                [],
                0,
                4,
                None,
            )
        )
