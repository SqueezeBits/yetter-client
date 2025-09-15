from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ClientOptions(BaseModel):
    api_key: Optional[str] = None
    endpoint: Optional[str] = None


class GenerateImageResponse(BaseModel):
    status: str
    request_id: str = Field(..., alias="request_id")
    response_url: str = Field(..., alias="response_url")
    status_url: str = Field(..., alias="status_url")
    cancel_url: str = Field(..., alias="cancel_url")
    queue_position: Optional[int] = Field(None, alias="queue_position")


class LogEntry(BaseModel):
    message: str


class GetStatusRequest(BaseModel):
    url: str
    logs: Optional[bool] = None


class GetStatusResponse(BaseModel):
    status: str
    request_id: Optional[str] = Field(None, alias="request_id")
    response_url: Optional[str] = Field(None, alias="response_url")
    status_url: Optional[str] = Field(None, alias="status_url")
    cancel_url: Optional[str] = Field(None, alias="cancel_url")
    queue_position: Optional[int] = Field(None, alias="queue_position")
    logs: Optional[List[LogEntry]] = None


class CancelRequest(BaseModel):
    url: str


class CancelResponse(BaseModel):
    status: str
    request_id: Optional[str] = Field(None, alias="request_id")
    response_url: Optional[str] = Field(None, alias="response_url")
    status_url: Optional[str] = Field(None, alias="status_url")
    cancel_url: Optional[str] = Field(None, alias="cancel_url")
    queue_position: Optional[int] = Field(None, alias="queue_position")
    logs: Optional[List[str]] = None


class GetResponseRequest(BaseModel):
    url: str


class GetResultOptions(BaseModel):
    request_id: str = Field(..., alias="requestId")


class GetResultResponse(BaseModel):
    data: Dict[str, Any]
    request_id: str = Field(..., alias="requestId")


class StatusOptions(BaseModel):
    request_id: str = Field(..., alias="requestId")


class StatusResponse(BaseModel):
    data: GetStatusResponse
    request_id: str = Field(..., alias="requestId")
