from typing import Dict, Any, Optional, Callable
from .api import YetterImageClient
from .client import YetterStream, yetter
from .types import (
    CancelRequest,
    CancelResponse,
    ClientOptions,
    GenerateImageResponse,
    GetResponseRequest,
    GetResultOptions,
    GetResultResponse,
    GetStatusRequest,
    GetStatusResponse,
    GetUploadUrlRequest,
    GetUploadUrlResponse,
    StatusOptions,
    StatusResponse,
    UploadCompleteRequest,
    UploadCompleteResponse,
)

# Create the default instance
_yetter_instance = yetter()

def configure(api_key: str = None, api_endpoint: str = None):
    global _yetter_instance
    _yetter_instance.configure(api_key=api_key, endpoint=api_endpoint)

async def run(model: str, args: Dict[str, Any]) -> Dict[str, Any]:
    global _yetter_instance
    if not _yetter_instance._api_key:
        raise RuntimeError("You must call yetter.configure() before using yetter.run()")
    stream = await _yetter_instance.stream(model, args)
    return await stream.done()  # Wait for stream completion and return the final result

async def subscribe(model: str, args: Dict[str, Any], on_queue_update: Optional[Callable[[GetStatusResponse], None]] = None) -> Dict[str, Any]:
    global _yetter_instance
    if not _yetter_instance._api_key:
        raise RuntimeError("You must call yetter.configure() before using yetter.subscribe()")
    return await _yetter_instance.subscribe(model, args, on_queue_update)

async def stream(model: str, args: Dict[str, Any]) -> YetterStream:
    global _yetter_instance
    if not _yetter_instance._api_key:
        raise RuntimeError("You must call yetter.configure() before using yetter.stream()")
    return await _yetter_instance.stream(model, args)


async def upload_file(
    file_path: str,
    on_progress: Optional[Callable[[int], None]] = None,
) -> UploadCompleteResponse:
    """
    Upload a file using presigned URLs.

    Supports automatic single-part upload for small files and multipart
    upload for large files. The mode is determined by the server response.

    Args:
        file_path: Path to the file to upload
        on_progress: Optional callback function that receives progress (0-100)

    Returns:
        UploadCompleteResponse containing the public URL and metadata

    Raises:
        FileNotFoundError: If the file does not exist
        RuntimeError: If upload fails or API key is not configured

    Example:
        ```python
        import yetter
        yetter.configure(api_key="your_api_key")
        result = await yetter.upload_file(
            "./image.jpg",
            on_progress=lambda pct: print(f"Upload: {pct}%")
        )
        print(f"Uploaded: {result.url}")
        ```
    """
    global _yetter_instance
    if not _yetter_instance._api_key:
        raise RuntimeError("You must call yetter.configure() before using yetter.upload_file()")
    return await yetter.upload_file(file_path, on_progress)


# Export everything needed for the public API
__all__ = [
    "configure",
    "run",
    "subscribe",
    "stream",
    "upload_file",
    "YetterImageClient",
    "YetterStream",
    "ClientOptions",
    "GenerateImageResponse",
    "GetStatusRequest",
    "GetStatusResponse",
    "CancelRequest",
    "CancelResponse",
    "GetResponseRequest",
    "LogEntry",
    "GetResultOptions",
    "GetResultResponse",
    "StatusOptions",
    "StatusResponse",
    # Upload-related exports
    "GetUploadUrlRequest",
    "GetUploadUrlResponse",
    "UploadCompleteRequest",
    "UploadCompleteResponse",
]
