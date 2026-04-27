import io
from datetime import datetime

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import get_db
from .models import ScanEvent, UrlMapping
from .schemas import CreateRequest, CreateResponse, QRInfoResponse, UpdateRequest
from .token_gen import generate_token
from .url_validator import validate_url

router = APIRouter()

# In-memory cache (simulates Redis for prototype)
redirect_cache: dict[str, str] = {}

BASE_URL = "http://localhost:8000"


@router.post("/api/qr/create", response_model=CreateResponse)
def create_qr(req: CreateRequest, db: Session = Depends(get_db)):
    normalized_url = validate_url(req.url)
    token = generate_token(normalized_url, db)

    mapping = UrlMapping(
        token=token,
        original_url=normalized_url,
        expires_at=req.expires_at,
    )
    db.add(mapping)
    db.commit()

    short_url = f"{BASE_URL}/r/{token}"

    # Warm cache
    redirect_cache[token] = normalized_url

    return CreateResponse(
        token=token,
        short_url=short_url,
        qr_code_url=f"{BASE_URL}/api/qr/{token}/image",
        original_url=normalized_url,
    )


@router.get("/r/{token}")
def redirect(token: str, request: Request, db: Session = Depends(get_db)):
    """Redirect fallback flow: Cache -> DB -> 404/410 (from slides mermaid diagram)"""
    # TODO: Implement this function
    #
    # Design decision: the redirect path is the hottest path in the system, so
    # we use a cache-first strategy (Cache -> DB -> 404/410) to minimize DB load
    # while still handling soft-deleted and expired links.
    #
    # Hints:
    # 1. Check redirect_cache first — on hit, call _record_scan() and return
    #    RedirectResponse(status_code=302).
    # 2. On miss, query the DB: raise 404 if not found, 410 if is_deleted or
    #    past expires_at; otherwise warm the cache, _record_scan(), and 302.
    raise NotImplementedError("redirect() is not yet implemented")


@router.get("/api/qr/{token}", response_model=QRInfoResponse)
def get_qr_info(token: str, db: Session = Depends(get_db)):
    mapping = _get_mapping_or_404(token, db)
    return mapping


@router.patch("/api/qr/{token}", response_model=QRInfoResponse)
def update_qr(token: str, req: UpdateRequest, db: Session = Depends(get_db)):
    mapping = _get_mapping_or_404(token, db)

    if req.url is not None:
        mapping.original_url = validate_url(req.url)
        # Invalidate cache
        redirect_cache.pop(token, None)

    if req.expires_at is not None:
        mapping.expires_at = req.expires_at

    db.commit()
    db.refresh(mapping)
    return mapping


@router.delete("/api/qr/{token}")
def delete_qr(token: str, db: Session = Depends(get_db)):
    mapping = _get_mapping_or_404(token, db)
    mapping.is_deleted = True
    db.commit()
    # Invalidate cache
    redirect_cache.pop(token, None)
    return {"detail": "Deleted"}


@router.get("/api/qr/{token}/image")
def get_qr_image(token: str, db: Session = Depends(get_db)):
    _get_mapping_or_404(token, db)
    short_url = f"{BASE_URL}/r/{token}"

    img = qrcode.make(short_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@router.get("/api/qr/{token}/analytics")
def get_analytics(token: str, db: Session = Depends(get_db)):
    _get_mapping_or_404(token, db)

    total = db.query(func.count(ScanEvent.id)).filter(ScanEvent.token == token).scalar()

    daily = (
        db.query(
            func.date(ScanEvent.scanned_at).label("date"),
            func.count(ScanEvent.id).label("count"),
        )
        .filter(ScanEvent.token == token)
        .group_by(func.date(ScanEvent.scanned_at))
        .all()
    )

    return {
        "token": token,
        "total_scans": total,
        "scans_by_day": [{"date": str(row.date), "count": row.count} for row in daily],
    }


def _get_mapping_or_404(token: str, db: Session) -> UrlMapping:
    mapping = db.query(UrlMapping).filter(UrlMapping.token == token).first()
    if mapping is None or mapping.is_deleted:
        raise HTTPException(status_code=404, detail="Not Found")
    return mapping


def _record_scan(token: str, request: Request, db: Session):
    event = ScanEvent(
        token=token,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    db.add(event)
    db.commit()
