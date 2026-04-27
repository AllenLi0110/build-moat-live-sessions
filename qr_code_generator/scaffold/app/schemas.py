from datetime import datetime

from pydantic import BaseModel


class CreateRequest(BaseModel):
    url: str
    expires_at: datetime | None = None


class CreateResponse(BaseModel):
    token: str
    short_url: str
    qr_code_url: str
    original_url: str


class QRInfoResponse(BaseModel):
    token: str
    original_url: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    is_deleted: bool


class UpdateRequest(BaseModel):
    url: str | None = None
    expires_at: datetime | None = None
