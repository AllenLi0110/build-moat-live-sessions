# QR Code Generator

A dynamic QR code system built with Python + FastAPI (backend) and React + TypeScript (frontend).

## Demo

### Image
![QR Code Generator Screenshot](images/qr-code-generator-demo.png)

### GIF
![QR Code Generator Demo GIF](images/qr-code-generator-demo.gif)

---

## Features

- Submit a long URL → receive a short URL token + QR code image
- QR code encodes the short URL which 302-redirects to the original URL
- Update the target URL after creation
- Soft delete (returns 410 on redirect)
- Optional expiration timestamp with live countdown
- In-memory cache (cache-first redirect strategy)
- Scan analytics (total count + per-day breakdown)
- URL validation: length check, scheme check, blocklist, normalization

---

## Tech Stack

| Layer    | Technology                        |
|----------|-----------------------------------|
| Backend  | Python 3.10+, FastAPI, SQLAlchemy |
| Database | SQLite                            |
| Frontend | React 18, TypeScript, Vite        |
| QR       | qrcode[pil]                       |

---

## Project Structure

```
scaffold/
├── app/
│   ├── main.py          # FastAPI app, CORS, static file serving
│   ├── database.py      # SQLAlchemy engine + session
│   ├── models.py        # UrlMapping, ScanEvent
│   ├── schemas.py       # Pydantic request/response types
│   ├── routes.py        # All API endpoints
│   ├── token_gen.py     # SHA-256 + Base62 token generation
│   └── url_validator.py # URL validation + normalization
├── frontend/
│   └── src/
│       └── App.tsx      # Single-page React UI
└── requirements.txt
```

---

## Getting Started

**Prerequisites:** Python 3.10+, Node.js 18+

No environment variables or `.env` configuration required. The backend detects the correct base URL from each incoming request automatically.

**1. Install dependencies**

```bash
cd scaffold
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

**2. Start the backend**

```bash
# from scaffold/
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**3. Start the frontend dev server**

```bash
# from scaffold/frontend/
npm run dev -- --host
```

**4. Open the app**

| Goal | URL to open |
|------|-------------|
| Desktop only | `http://localhost:5173` |
| QR scannable from phone | `http://<your-lan-ip>:5173` |

To find your LAN IP:
```bash
ipconfig getifaddr en0   # Wi-Fi
ipconfig getifaddr en1   # Ethernet
```

> Open the app from the LAN IP when you want QR codes to be scannable from a phone. The short URL embedded in the QR code mirrors whatever address your browser used to open the app — no configuration needed.

---

## API Reference

| Method   | Path                        | Description                              |
|----------|-----------------------------|------------------------------------------|
| `POST`   | `/api/qr/create`            | Create QR code, returns token + URLs     |
| `GET`    | `/r/{token}`                | 302 redirect (410 if deleted/expired)    |
| `GET`    | `/api/qr/{token}`           | Get mapping info                         |
| `PATCH`  | `/api/qr/{token}`           | Update target URL and/or expiry          |
| `DELETE` | `/api/qr/{token}`           | Soft delete                              |
| `GET`    | `/api/qr/{token}/image`     | QR code PNG image                        |
| `GET`    | `/api/qr/{token}/analytics` | Total scans + per-day breakdown          |
| `GET`    | `/api/qr/{token}/check`     | Check redirect status without recording scan |

**404 vs 410:** `/r/{token}` returns 410 for deleted or expired tokens, 404 for tokens that never existed.

---

## Exercise Track

This project was built as a guided coding exercise. The original scaffold contained three TODOs:

| File              | TODO                | Concept                              |
|-------------------|---------------------|--------------------------------------|
| `token_gen.py`    | `generate_token()`  | SHA-256 + Base62 + collision retry   |
| `url_validator.py`| `validate_url()`    | Normalization + blocklist            |
| `routes.py`       | `redirect()`        | Cache → DB → 302 / 410 / 404         |

Design questions and answers are in `PROMPT.md`.
