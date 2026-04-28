import io
import os
from datetime import datetime

import qrcode
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import get_db
from .models import ScanEvent, UrlMapping
from .schemas import CreateRequest, CreateResponse, QRInfoResponse, UpdateRequest
from .token_gen import generate_token
from .url_validator import validate_url

load_dotenv()

router = APIRouter()

# In-memory cache: token -> (original_url, expires_at)
redirect_cache: dict = {}

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")


@router.post("/api/qr/create", response_model=CreateResponse)
def create_qr(req: CreateRequest, db: Session = Depends(get_db)):
    try:
        normalized_url = validate_url(req.url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    token = generate_token(normalized_url, db)

    mapping = UrlMapping(
        token=token,
        original_url=normalized_url,
        expires_at=req.expires_at,
    )
    db.add(mapping)
    db.commit()

    short_url = f"{BASE_URL}/r/{token}"
    redirect_cache[token] = (normalized_url, req.expires_at)

    return CreateResponse(
        token=token,
        short_url=short_url,
        qr_code_url=f"{BASE_URL}/api/qr/{token}/image",
        original_url=normalized_url,
    )


@router.get("/r/{token}")
def redirect(token: str, request: Request, db: Session = Depends(get_db)):
    # Cache-first: cache -> DB -> 302/410/404
    if token in redirect_cache:
        cached_url, cached_expires = redirect_cache[token]
        if cached_expires is not None and cached_expires < datetime.utcnow():
            redirect_cache.pop(token, None)
            raise HTTPException(status_code=410, detail="Gone — link expired")
        _record_scan(token, request, db)
        return RedirectResponse(url=cached_url, status_code=302)

    mapping = db.query(UrlMapping).filter(UrlMapping.token == token).first()

    if mapping is None:
        raise HTTPException(status_code=404, detail="Not Found")

    if mapping.is_deleted:
        raise HTTPException(status_code=410, detail="Gone")

    if mapping.expires_at is not None and mapping.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Gone — link expired")

    redirect_cache[token] = (mapping.original_url, mapping.expires_at)
    _record_scan(token, request, db)
    return RedirectResponse(url=mapping.original_url, status_code=302)


@router.get("/api/qr/{token}", response_model=QRInfoResponse)
def get_qr_info(token: str, db: Session = Depends(get_db)):
    return _get_mapping_or_404(token, db)


@router.patch("/api/qr/{token}", response_model=QRInfoResponse)
def update_qr(token: str, req: UpdateRequest, db: Session = Depends(get_db)):
    mapping = _get_mapping_or_404(token, db)

    if req.url is not None:
        try:
            mapping.original_url = validate_url(req.url)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    if req.expires_at is not None:
        mapping.expires_at = req.expires_at

    # Invalidate so the next redirect re-reads updated url and expires_at
    redirect_cache.pop(token, None)

    db.commit()
    db.refresh(mapping)
    return mapping


@router.delete("/api/qr/{token}")
def delete_qr(token: str, db: Session = Depends(get_db)):
    mapping = _get_mapping_or_404(token, db)
    mapping.is_deleted = True
    db.commit()
    redirect_cache.pop(token, None)
    return {"detail": "Deleted"}


@router.get("/api/qr/{token}/check")
def check_redirect(token: str, db: Session = Depends(get_db)):
    mapping = db.query(UrlMapping).filter(UrlMapping.token == token).first()
    if mapping is None:
        return {"status": 404}
    if mapping.is_deleted:
        return {"status": 410}
    if mapping.expires_at is not None and mapping.expires_at < datetime.utcnow():
        return {"status": 410}
    return {"status": 302}


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


def _record_scan(token: str, request: Request, db: Session) -> None:
    event = ScanEvent(
        token=token,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    db.add(event)
    db.commit()
