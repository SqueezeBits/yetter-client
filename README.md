## Yetter Python Client

A lightweight async Python client for the Yetter image generation API. It supports simple one-shot runs, subscription-style polling, and server-sent events (SSE) streaming.

### Installation

```bash
pip install yetter
```

If the package is not yet published to PyPI, install from the repository:

```bash
pip install "yetter @ git+https://github.com/SqueezeBits/yetter-client"
```

### Authentication & Configuration

Provide your API key in one of the following ways:

- Environment variable (preferred):

```bash
export YTR_API_KEY="YOUR_API_KEY"
```

- Programmatically via `configure`:

```python
import asyncio
import yetter

async def main():
    yetter.configure(api_key="YOUR_API_KEY")
    # Optionally override endpoint:
    # yetter.configure(api_key="YOUR_API_KEY", api_endpoint="https://api.yetter.ai")

asyncio.run(main())
```


### Quick start: one-shot run

Use `yetter.run()` for a convenient "submit + wait for completion" flow powered by streaming under the hood.

```python
import asyncio
import yetter

async def main():
    yetter.configure(api_key="YOUR_API_KEY")
    result = await yetter.run(
        "ytr-ai/qwen/image/t2i",
        args={"prompt": "A beautiful landscape with a river and mountains"},
    )
    # result is dict('images':..., 'prompt':...)
    print(result)

asyncio.run(main())
```

### Subscribe: polling with optional queue updates

`yetter.subscribe()` submits a request and polls status until completion. You can pass a callback to receive queue/status updates.

```python
import asyncio
import yetter
from yetter.types import GetStatusResponse

async def on_update(status: GetStatusResponse):
    print("status:", status.status)

async def main():
    yetter.configure(api_key="YOUR_API_KEY")
    result = await yetter.subscribe(
        "ytr-ai/qwen/image/t2i",
        args={
            "prompt": "A beautiful landscape with a river and mountains",
            "num_images": 2,
        },
        on_queue_update=on_update,
    )
    print("final images:", result.images)

asyncio.run(main())
```

### Examples

See the `examples/` directory:
- `examples/run.py`: minimal one-shot run
- `examples/subscribe.py`: subscription with updates

