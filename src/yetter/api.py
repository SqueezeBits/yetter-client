from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx

from .types import (
    CancelRequest,
    CancelResponse,
    ClientOptions,
    GenerateImageResponse,
    GetResponseRequest,
    GetSchemeRequest,
    GetStatusRequest,
    GetStatusResponse,
    GetUploadUrlRequest,
    UploadCompleteRequest,
)


class YetterImageClient:
    def __init__(self, options: ClientOptions):
        if not options.api_key:
            raise ValueError("`api_key` is required")
        self.api_key = options.api_key
        self.endpoint = options.endpoint or "https://api.yetter.ai"
        self.backend = options.backend or "https://app.yetter.ai"

    def get_api_endpoint(self) -> str:
        return self.endpoint

    def get_backend(self) -> str:
        return self.backend

    def configure(self, options: ClientOptions) -> None:
        if options.api_key:
            if "Bearer" in options.api_key or "Key" in options.api_key:
                raise ValueError("API key must not contain 'Bearer' or 'Key'")
            self.api_key = "Key " + options.api_key
        if options.endpoint:
            self.endpoint = options.endpoint

    async def _request(
        self,
        method: str,
        url: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> httpx.Response:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"{self.api_key}",
        }
        async with httpx.AsyncClient() as client:
            res = await client.request(
                method, url, json=json_data, headers=headers, params=params
            )

        if not res.is_success:
            try:
                error_text = res.text
            except Exception:
                error_text = "Unknown error (unable to decode response)"
            raise httpx.HTTPStatusError(
                f"API error ({res.status_code}): {error_text}",
                request=res.request,
                response=res,
            )
        return res

    async def generate_image(self, body: Dict[str, Any]) -> GenerateImageResponse:
        payload = body
        model = payload.get("model")
        if not isinstance(model, str) or not model:
            raise ValueError(
                "GenerateImageRequest must include a non-empty 'model' key"
            )
        url = f"{self.endpoint}/{model}"
        res = await self._request(
            "POST", url, json_data=body
        )
        return GenerateImageResponse(**res.json())

    async def get_status(self, body: GetStatusRequest) -> GetStatusResponse:
        parsed_url = urlparse(body.url)
        query_params = parse_qs(parsed_url.query)
        if body.logs:
            query_params["logs"] = ["1"]
        new_query_string = urlencode(query_params, doseq=True)
        url_to_fetch = urlunparse(parsed_url._replace(query=new_query_string))

        res = await self._request("GET", url_to_fetch)
        return GetStatusResponse(**res.json())

    async def cancel(self, body: CancelRequest) -> CancelResponse:
        res = await self._request("PUT", body.url)
        return CancelResponse(**res.json())

    async def get_response(self, body: GetResponseRequest) -> Dict[str, Any]:
        res = await self._request("GET", body.url)
        return res.json()

    async def get_scheme(self, body: GetSchemeRequest) -> Dict[str, Any]:
        res = await self._request("GET", f"{self.backend}/model/{body.app_id}")
        return res.json()

    async def get_upload_url(self, body: GetUploadUrlRequest) -> Dict[str, Any]:
        res = await self._request("POST", f"{self.endpoint}/uploads", json_data=body.model_dump())
        return res.json()

    async def upload_complete(self, body: UploadCompleteRequest) -> Dict[str, Any]:
        res = await self._request("POST", f"{self.endpoint}/uploads/complete", json_data=body.model_dump())
        return res.json()
