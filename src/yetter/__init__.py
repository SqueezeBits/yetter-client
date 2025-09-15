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
    StatusOptions,
    StatusResponse,
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

# Export everything needed for the public API
__all__ = [
    "configure",
    "run",
    "subscribe",
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
]
