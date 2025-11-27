import asyncio
import json
import logging
import mimetypes
import os
from typing import Any, AsyncIterable, Callable, Dict, Optional

import httpx
import requests

from .api import YetterImageClient
from .types import (
    CancelRequest,
    ClientOptions,
    GenerateImageResponse,
    GetResponseRequest,
    GetResultOptions,
    GetResultResponse,
    GetSchemeRequest,
    GetStatusRequest,
    GetStatusResponse,
    GetUploadUrlRequest,
    StatusOptions,
    StatusResponse,
    UploadCompleteRequest,
)

class YetterStream:
    def __init__(
        self,
        api_client: YetterImageClient,
        model: str,
        initial_response: GenerateImageResponse,
        args: Dict[str, Any],
    ):
        self._api_client = api_client
        self._model = model
        self._initial_response = initial_response
        self._request_id = initial_response.request_id
        self._response_url = initial_response.response_url
        self._cancel_url = initial_response.cancel_url
        self._sse_stream_url = f"{self._api_client.get_api_endpoint()}/{self._model}/requests/{self._request_id}/status/stream"
        self._event_source: Optional[httpx.AsyncClient] = None
        self._stream_ended = False
        self._done_future = asyncio.Future()
        self._final_response: Optional[Dict[str, Any]] = None
        self._stream_task: Optional[asyncio.Task] = None
        self._stream_consumed = False

    def get_request_id(self) -> str:
        return self._request_id

    async def cancel(self) -> None:
        if not self._stream_ended:
            try:
                await self._api_client.cancel(CancelRequest(url=self._cancel_url))
                logging.debug(
                    f"Stream for {self._request_id} - underlying request cancelled."
                )
            except Exception as e:
                print(
                    f"Error cancelling underlying request for stream {self._request_id}: {e}"
                )

    async def _consume_stream(self):
        """Internal method to consume the stream in the background"""
        if self._stream_consumed:
            return

        try:
            async for _ in self:
                pass
        except Exception as e:
            if not self._done_future.done():
                self._done_future.set_exception(e)

    async def done(self) -> Dict[str, Any]:
        """
        Returns the final response when the stream is completed.
        """
        if not self._stream_consumed and not self._stream_task:
            self._stream_task = asyncio.create_task(self._consume_stream())

        try:
            return await self._done_future
        finally:
            if self._stream_task:
                self._stream_task.cancel()
                try:
                    await self._stream_task
                except asyncio.CancelledError:
                    pass

    async def _process_event_data(self, event_data: str) -> GetStatusResponse:
        try:
            data = json.loads(event_data)
            return GetStatusResponse(**data)
        except json.JSONDecodeError as e:
            logging.debug(f"Error parsing SSE event data: {e}, raw: {event_data}")
            raise ValueError(f"Error parsing SSE data: {e}")

    async def __aiter__(self) -> AsyncIterable[GetStatusResponse]:
        if self._stream_consumed:
            return

        self._stream_consumed = True
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
            self._stream_task = None

        if self._stream_ended:
            if self._initial_response.status in ["COMPLETED", "ERROR", "CANCELLED"]:
                status_like_initial = GetStatusResponse(
                    status=self._initial_response.status,
                    request_id=self._initial_response.request_id,
                    response_url=self._initial_response.response_url,
                    status_url=self._initial_response.status_url,
                    cancel_url=self._initial_response.cancel_url,
                    queue_position=self._initial_response.queue_position,
                    logs=None,
                )
                yield status_like_initial
                return
            elif self._initial_response.status in ["IN_QUEUE", "IN_PROGRESS"]:
                self._stream_ended = False

        self._event_source = httpx.AsyncClient()
        try:
            headers = {
                "Authorization": f"{self._api_client.api_key}",
                "Accept": "text/event-stream",
            }
            logging.debug(f"Connecting to SSE: {self._sse_stream_url}")

            # Replace the connect_sse usage with direct httpx streaming
            async with self._event_source.stream(
                "GET", self._sse_stream_url, headers=headers, timeout=30 * 60.0
            ) as response:
                async for line in response.aiter_lines():
                    if self._stream_ended:
                        break

                    if not line.strip():
                        continue

                    if line.startswith("data: "):
                        data = line[6:].strip()
                        logging.debug(f"SSE event: data, data: {data}")
                        status_update = await self._process_event_data(data)
                        yield status_update

                    elif line.startswith("event: "):
                        event_type = line[6:].strip()
                        if event_type == "data":
                            continue
                        elif event_type == "done":
                            self._stream_ended = True
                            try:
                                final_data = await self._api_client.get_response(
                                    GetResponseRequest(url=self._response_url)
                                )
                                self._final_response = final_data
                                if not self._done_future.done():
                                    self._done_future.set_result(final_data)
                            except Exception as e:
                                if not self._done_future.done():
                                    self._done_future.set_exception(e)
                            break
                        elif status_update.status == "FAILED":
                            self._stream_ended = True
                            err_msg = f"Stream reported FAILED for {self._request_id}"
                            if status_update.logs:
                                err_msg = "\n".join(
                                    [log.message for log in status_update.logs]
                                )
                            if not self._done_future.done():
                                try:
                                    logging.debug(
                                        f"SSE 'done' event, checking final status for {self._request_id}"
                                    )

                                    # TODO: js-package updates lateset status by variable that is updated every stream event
                                    # => python package get latest status from status-API
                                    # => which method is more better?
                                    current_status = await self._api_client.get_status(
                                        GetStatusRequest(
                                            url=self._initial_response.status_url
                                        )
                                    )
                                    if current_status.status == "COMPLETED":
                                        final_data = await self._api_client.get_response(
                                            GetResponseRequest(url=self._response_url)
                                        )
                                        self._done_future.set_result(final_data)
                                    elif current_status.status == "CANCELLED":
                                        self._done_future.set_result("Stream was cancelled by user.")
                                    elif current_status.status == "ERROR" | "IN_PROGRESS" | "IN_QUEUE":
                                        self._done_future.set_exception(
                                            RuntimeError(f"Stream ended: 'done' event, wrong final status {current_status.status}.")
                                        )
                                    else:
                                        self._done_future.set_exception(
                                            RuntimeError(f"Stream ended: 'done' event, unexpected final status {current_status.status}.")
                                        )
                                except Exception as e:
                                    if not self._done_future.done():
                                        self._done_future.set_exception(
                                            RuntimeError(
                                                f"Stream ended: 'done' event, error on final status check: {e}"
                                            )
                                        )
                            break
                        elif event_type == "error":
                            self._stream_ended = True
                            if not self._done_future.done():
                                self._done_future.set_exception(
                                    RuntimeError("Stream ended: 'error' event")
                                )
                            break
                        else:
                            self._stream_ended = True
                            if not self._done_future.done():
                                self._done_future.set_exception(
                                    RuntimeError(f"Stream ended: 'done' event, unknown event type: {event_type}")
                                )
                            break
        except httpx.RequestError as e:
            logging.debug(f"SSE connection error for {self._request_id}: {e}")
            if not self._done_future.done():
                self._done_future.set_exception(e)
        except ValueError as e:
            if not self._done_future.done():
                self._done_future.set_exception(e)
        except Exception as e:
            logging.debug(f"Unexpected error in SSE stream for {self._request_id}: {e}")
            if not self._done_future.done():
                self._done_future.set_exception(e)
        finally:
            self._stream_ended = True
            if self._event_source:
                await self._event_source.aclose()
            if not self._done_future.done():
                self._done_future.set_exception(
                    RuntimeError("Stream closed unexpectedly or prematurely.")
                )


class yetter:
    _api_key = None
    _endpoint = "https://api.yetter.ai"

    def __init__(self):
        api_key = os.environ.get("YTR_API_KEY", "")
        if "Bearer" in api_key or "Key" in api_key:
            raise ValueError("API key must not contain 'Bearer' or 'Key'")
        self._api_key = "Key " + api_key

    @staticmethod
    def configure(
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        is_bearer: Optional[bool] = False,
    ) -> None:
        if api_key:
            if "Bearer" in api_key or "Key" in api_key:
                raise ValueError("API key must not contain 'Bearer' or 'Key'")
            if is_bearer:
                yetter._api_key = "Bearer " + api_key
            else:
                yetter._api_key = "Key " + api_key
        if endpoint:
            yetter._endpoint = endpoint

    @staticmethod
    def _get_client() -> YetterImageClient:
        if not yetter._api_key:
            raise ValueError(
                "API key not configured. Call yetter.configure() or set YTR_API_KEY."
            )
        return YetterImageClient(
            ClientOptions(api_key=yetter._api_key, endpoint=yetter._endpoint)
        )

    @staticmethod
    async def subscribe(
        model: str,
        args: Dict[str, Any],
        on_queue_update: Optional[Callable[[GetStatusResponse], None]] = None,
    ) -> Dict[str, Any]:
        client = yetter._get_client()
        payload = {
            "model": model,
            **args,
        }
        generate_response = await client.generate_image(payload)
        status = generate_response.status
        last_status_response: Optional[GetStatusResponse] = None
        start_time = asyncio.get_event_loop().time()
        timeout_seconds = 30 * 60

        while status not in ["COMPLETED", "ERROR", "CANCELLED"]:
            if (asyncio.get_event_loop().time() - start_time) > timeout_seconds:
                logging.debug(
                    f"Subscription timed out for {generate_response.request_id}. Attempting cancel."
                )
                try:
                    await client.cancel(CancelRequest(url=generate_response.cancel_url))
                except Exception as cancel_error:
                    print(
                        f"Failed to cancel timed out request {generate_response.request_id}: {cancel_error}"
                    )
                raise TimeoutError(
                    f"Subscription timed out for {generate_response.request_id}."
                )

            await asyncio.sleep(0.1)  # Polling interval
            try:
                last_status_response = await client.get_status(
                    GetStatusRequest(
                        url=generate_response.status_url, logs=args.get("logs", None)
                    )
                )
                status = last_status_response.status
                if on_queue_update and last_status_response:
                    if asyncio.iscoroutinefunction(on_queue_update):
                        asyncio.create_task(on_queue_update(last_status_response))
                    else:
                        on_queue_update(last_status_response)
            except httpx.HTTPStatusError as e:
                logging.debug(f"Polling error for {generate_response.request_id}: {e}")
                raise
            except Exception as e:
                logging.debug(
                    f"Unexpected polling error for {generate_response.request_id}: {e}"
                )
                raise

        if status == "ERROR":
            err_msg = "Image generation failed."
            if last_status_response and last_status_response.logs:
                err_msg = "\n".join([log.message for log in last_status_response.logs])
            raise RuntimeError(err_msg)

        return await client.get_response(
            GetResponseRequest(url=generate_response.response_url)
        )

    class queue:
        @staticmethod
        async def submit(model: str, args: Dict[str, Any]) -> GenerateImageResponse:
            client = yetter._get_client()
            payload = {
                "model": model,
                **args,
            }
            return await client.generate_image(payload)

        @staticmethod
        async def status(model: str, options: StatusOptions) -> StatusResponse:
            client = yetter._get_client()
            status_url = f"{client.get_api_endpoint()}/{model}/requests/{options.request_id}/status"
            status_data = await client.get_status(GetStatusRequest(url=status_url))
            return StatusResponse(data=status_data, request_id=options.request_id)

        @staticmethod
        async def result(model: str, options: GetResultOptions) -> GetResultResponse:
            client = yetter._get_client()
            response_url = (
                f"{client.get_api_endpoint()}/{model}/requests/{options.request_id}"
            )
            response_data = await client.get_response(
                GetResponseRequest(url=response_url)
            )
            return GetResultResponse(data=response_data, request_id=options.request_id)

    @staticmethod
    async def stream(model: str, args: Dict[str, Any]) -> YetterStream:
        client = yetter._get_client()
        payload = {
            "model": model,
            **args,
        }
        initial_api_response = await client.generate_image(payload)
        stream_wrapper = YetterStream(client, model, initial_api_response, args)

        if initial_api_response.status in ["COMPLETED", "ERROR", "CANCELLED"]:
            stream_wrapper._stream_ended = True
            if initial_api_response.status == "COMPLETED":
                if not stream_wrapper._done_future.done():
                    try:
                        final_data = await client.get_response(
                            GetResponseRequest(url=initial_api_response.response_url)
                        )
                        stream_wrapper._done_future.set_result(final_data)
                    except Exception as e:
                        if not stream_wrapper._done_future.done():
                            stream_wrapper._done_future.set_exception(e)
            elif initial_api_response.status == "ERROR":
                err_msg = f"Stream creation failed: {initial_api_response.request_id} reported FAILED initially."
                if not stream_wrapper._done_future.done():
                    stream_wrapper._done_future.set_exception(RuntimeError(err_msg))
            elif initial_api_response.status == "CANCELLED":
                err_msg = f"Stream creation failed: {initial_api_response.request_id} reported CANCELLED initially."
                if not stream_wrapper._done_future.done():
                    stream_wrapper._done_future.set_exception(RuntimeError(err_msg))
        else:
            stream_wrapper._stream_task = asyncio.create_task(
                stream_wrapper._consume_stream()
            )

        return stream_wrapper

    @staticmethod
    async def get_scheme(app_id: str) -> Dict[str, Any]:
        client = yetter._get_client()
        return await client.get_scheme(GetSchemeRequest(app_id=app_id))

    @staticmethod
    async def upload_file(file_name: str) -> Dict[str, Any]:
        client = yetter._get_client()
        file_size = os.path.getsize(file_name)
        file_type = mimetypes.guess_type(file_name)[0]
        file_size = 12 * 1024 * 1024
        upload_url_response = await client.get_upload_url(
            GetUploadUrlRequest(
                file_name=file_name, content_type=file_type, size=file_size
            )
        )
        if upload_url_response["mode"] == "single":
            # Singlepart upload
            with open(file_name, "rb") as file:
                requests.put(
                    upload_url_response["put_url"],
                    data=file,
                    headers={"Content-Type": file_type},
                )
        else:
            # Multipart upload
            part_size: int = int(upload_url_response.get("part_size", 0))
            part_urls = upload_url_response.get("part_urls", [])
            if not part_size or not part_urls:
                raise ValueError("Invalid multipart upload response: missing part_size or part_urls")

            # Ensure parts are uploaded in order of part_number
            sorted_parts = sorted(part_urls, key=lambda p: int(p.get("part_number", 0)))

            with open(file_name, "rb") as f:
                for part in sorted_parts:
                    url = part.get("url")
                    part_number = int(part.get("part_number"))
                    if not url or not part_number:
                        raise ValueError("Invalid multipart part entry: missing url or part_number")

                    # Read the next chunk
                    chunk = f.read(part_size)
                    if chunk is None or len(chunk) == 0:
                        break

                    resp = requests.put(
                        url,
                        data=chunk,
                        headers={
                            # S3 part upload typically requires Content-Length; avoid Content-Type here
                            "Content-Length": str(len(chunk)),
                        },
                    )
                    if not (200 <= resp.status_code < 300):
                        raise RuntimeError(f"Multipart upload failed at part {part_number}: {resp.status_code} {resp.text}")
        upload_done_response = await client.upload_complete(
            UploadCompleteRequest(key=upload_url_response["key"])
        )

        return upload_done_response
