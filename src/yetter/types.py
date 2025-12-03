from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ClientOptions(BaseModel):
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    backend: Optional[str] = None  # For upload coordination


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


# ============= Upload-Related Types =============


class GetUploadUrlRequest(BaseModel):
    """Request to get presigned upload URL(s)"""
    file_name: str
    content_type: Optional[str] = None
    size: int


class GetUploadUrlResponse(BaseModel):
    """Response containing presigned URL(s) for upload"""
    mode: str  # "single" or "multipart"
    key: str  # S3 object key for tracking
    put_url: Optional[str] = None  # Presigned PUT URL (single mode only)
    part_size: Optional[int] = None  # Size of each part in bytes (multipart mode only)
    part_urls: Optional[List[Dict[str, Any]]] = None  # Array of part URLs with part numbers


class UploadCompleteRequest(BaseModel):
    """Request to notify upload completion"""
    key: str  # S3 object key from GetUploadUrlResponse


class UploadCompleteResponse(BaseModel):
    """Response after successful upload completion"""
    url: str  # Public URL to access the uploaded file
    key: str  # S3 object key
    metadata: Optional[Dict[str, Any]] = None  # Optional metadata (size, content_type, uploaded_at)
