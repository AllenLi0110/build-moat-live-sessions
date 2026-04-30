Build a QR Code Generator prototype based on the following spec.

**Goal:** Users submit a long URL and receive a short URL token plus a QR code image. The QR code encodes the short URL, which redirects (302) to the original URL via the server. Users can update the target URL, delete the link (soft delete), and optionally set an expiration timestamp.

**Tech stack:** Python 3.11 + FastAPI + SQLAlchemy (SQLite) for the backend. React 18 + TypeScript + Vite for the frontend. No external UI library — plain inline styles or CSS modules only.

**Backend file structure** under `scaffold/app/`: `main.py`, `database.py`, `models.py`, `schemas.py`, `routes.py`, `token_gen.py`, `url_validator.py` are already scaffolded — implement the `TODO` sections in-place. Frontend lives in `scaffold/frontend/`.

**Database models:** `UrlMapping` with fields: id, token (unique, 7 chars), original_url, is_deleted (bool, default false), expires_at (nullable datetime), created_at, updated_at. `ScanEvent` with fields: id, token, scanned_at, user_agent, ip_address.

**Token generation** (`token_gen.py`): SHA-256 hash of `url + nonce + nanosecond timestamp`, Base62-encode the digest, truncate to 7 characters. Retry up to 10 times with DB uniqueness check on each attempt.

**URL validation** (`url_validator.py`): reject URLs longer than 2048 chars, reject non-http/https schemes, reject blocked domains (`evil.com`, `malware.example.com`, `phishing.example.com`). Normalize: upgrade to https, lowercase the hostname, strip trailing slash from path.

**API endpoints:**
- `POST /api/qr/create` — validate and normalize URL, generate token, store mapping, return token + short_url + qr_code_url + original_url
- `GET /r/{token}` — check in-memory dict cache first; if miss, query DB; return 302 redirect if active, 410 if deleted or expired, 404 if never existed; always record a ScanEvent on successful redirect
- `GET /api/qr/{token}` — return mapping info; 404 if deleted or not found
- `PATCH /api/qr/{token}` — update url and/or expires_at; invalidate cache entry
- `DELETE /api/qr/{token}` — soft delete (set is_deleted=true); invalidate cache entry; return 200
- `GET /api/qr/{token}/image` — generate QR code PNG with the `qrcode` library encoding the short URL; return as StreamingResponse image/png
- `GET /api/qr/{token}/analytics` — return total scan count and scans grouped by date

**404 vs 410 rule:** The redirect endpoint (`/r/{token}`) returns 410 for deleted or expired tokens, 404 for tokens that never existed. All other endpoints (`/api/qr/{token}`) return 404 for both deleted and non-existent tokens.

**main.py:** Add CORSMiddleware allowing all origins. Mount `frontend/dist` as StaticFiles at `/` with `html=True` so the React build is served by FastAPI. Call `Base.metadata.create_all` on startup.

**requirements.txt:** Already exists at `scaffold/requirements.txt` — do not create a new one.

**Frontend** (single-page, one `App.tsx` file): URL input field + Generate button that calls `POST /api/qr/create`. Before any QR code is generated, display a feature-list panel below the input that lists the five key capabilities (short token + QR code, 302 redirect, analytics, expiry + soft delete, in-memory cache). This panel disappears as soon as a QR code is successfully generated and is replaced by the result panel. On success, display: the QR code image (via `/api/qr/{token}/image`), the token, the short URL, the original URL target. Show an info panel with created_at, updated_at, expires_at, is_deleted. Show a live countdown timer if expires_at is set, turning red under 10 seconds. Show an Update section (new URL input + PATCH button that resets expiry to +1 minute). Show a Load Analytics button that calls `/api/qr/{token}/analytics` and displays total scans and a per-day breakdown. Show a Delete button that calls `DELETE /api/qr/{token}` and updates UI to show "Deleted — redirect returns 410". Show a Test Redirect button that fetches `/r/{token}` with `redirect: 'manual'` and displays the HTTP status code badge. Status indicator in the header showing Active / Expired / Deleted with color coding.

**Frontend Layout:** All content must be visible on a single screen without vertical scrolling. Use a structured grid layout:
- Row 1 — Header: app title on the left, status badge (Active / Expired / Deleted) on the right.
- Row 2 — Input bar: full-width URL input + Generate button.
- Row 3 — Main panel (2 columns): left column = QR code image (200×200); right column = token/short URL/target info on top, metadata row (created, updated, expires, is_deleted, countdown) below.
- Row 4 — Update bar: new URL input + PATCH button, full width.
- Row 5 — Action bar: Load Analytics, Test Redirect, Delete buttons on the left; HTTP status badge on the right.
- Row 6 — Analytics panel: appears inline when loaded (total scans + compact per-day table).
Use compact font sizes (13–14px) and tight spacing so the full interface fits within a typical laptop viewport (~900px tall).

**Frontend Visual Style — Dark Mode Terminal:**
- Background: `#0d1117` (GitHub Dark base), card/panel surfaces: `#161b22`
- Borders: `#30363d` (subtle, single-pixel)
- Primary accent: `#39d353` (terminal green) for buttons, highlights, active status
- Secondary accent: `#58a6ff` (blue) for links and short URLs
- Danger: `#f85149` (red) for delete, expired, 410 status
- Warning: `#d29922` (amber) for expired status
- Text: `#e6edf3` (primary), `#8b949e` (secondary/labels)
- Font: `'JetBrains Mono', 'Fira Code', monospace` for tokens and URLs; `system-ui, sans-serif` for body copy
- **Minimum font size: 16px.** Labels (uppercase) may use 14px at the smallest. Never go below 14px anywhere in the UI.
- Buttons: flat, no box-shadow, `border: 1px solid` matching accent color, background transparent or dark — no filled solid color blocks
- Status badges: small, pill-shaped, colored dot prefix (●)
- QR code panel: white background island (invert filter not needed — QR must stay readable)
- Do NOT use gradients, drop shadows, rounded corners larger than 6px, or bright saturated fills

**vite.config.ts:** Proxy `/api` and `/r` to `http://localhost:8000` for local dev. Use `changeOrigin: false` so the original `Host` header is forwarded to FastAPI — this lets `request.base_url` correctly reflect the address the browser actually used (localhost or LAN IP), which is then embedded in the generated short URL and QR code.

After completing all TODOs and creating the frontend, run:

```bash
cd scaffold
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment

**No `BASE_URL` configuration required.** The backend derives the base URL dynamically from the incoming HTTP request (`request.base_url`), so the generated short URL and QR code always reflect the address the client actually used — localhost, LAN IP, or any reverse proxy — without any env-var changes.

**To allow phone scanning on a LAN (e.g. laptop hotspot):**

1. Start the backend with `--host 0.0.0.0`: `uvicorn app.main:app --reload --port 8000 --host 0.0.0.0`
2. Start the frontend with `--host`: `npm run dev -- --host`
3. Open `http://<your-lan-ip>:5173` from your phone's browser — the generated QR code will automatically encode that LAN address.

Then verify all curl tests from the spec pass: create, redirect (302), get info, update, redirect to new URL, delete, redirect after delete (410), non-existent token (404), QR image (200 image/png), analytics.

---

## Testing

**Framework:** pytest (already in `requirements.txt`). Test file: `scaffold/tests/test_api.py`. Run from the `scaffold/` directory with the virtual environment active:

```bash
pytest tests/ -v
```

**Required test coverage per endpoint:**

| Endpoint | Cases to cover |
|---|---|
| `POST /api/qr/create` | valid URL → 200 with token/short_url/qr_code_url; URL > 2048 chars → 422; non-http/https scheme → 422; blocked domain → 422 |
| `GET /r/{token}` | active token → 302 with correct `Location`; soft-deleted token → 410; expired token → 410; token that never existed → 404; redirect records a `ScanEvent` row |
| `GET /api/qr/{token}` | active token → 200 with correct fields; soft-deleted token → 404; non-existent token → 404 |
| `PATCH /api/qr/{token}` | update `original_url` → 200, redirect now resolves to new URL; set `expires_at` in the past → subsequent redirect returns 410; non-existent token → 404 |
| `DELETE /api/qr/{token}` | active token → 200, subsequent redirect returns 410; non-existent token → 404 |
| `GET /api/qr/{token}/image` | active token → 200 `image/png`; non-existent or deleted token → 404 |
| `GET /api/qr/{token}/analytics` | returns `total_scans` int and `by_date` list; non-existent token → 404 |

**Edge cases that must have explicit tests:**

- **Expired token** — insert a `UrlMapping` with `expires_at` set one second in the past; assert `GET /r/{token}` returns 410.
- **Deleted token** — create via API then `DELETE`; assert `GET /r/{token}` returns 410 and `GET /api/qr/{token}` returns 404.
- **Non-existent token** — use a 7-char string that was never inserted; assert `GET /r/{token}` returns 404 and `GET /api/qr/{token}` returns 404.
- **Cache invalidation** — patch or delete a token that was previously fetched (cache populated); assert the next redirect reflects the updated state, not the stale cache entry.

---

## Feedback Loop

The agent must follow this loop strictly — no step may be skipped:

```
1. Implement (or fix) the code.
2. Run: pytest tests/ -v
3. If any test fails:
   a. Read the full pytest output.
   b. Identify the root cause — do not guess.
   c. Fix only the failing code path.
   d. Go to step 2.
4. If all tests pass → proceed to Definition of Done check.
```

**Rules:**

- Never mark a task complete while any test is red.
- Never silence a test (skip/xfail) to make the suite green — fix the code.
- If a fix causes a previously passing test to fail, treat the regression as a new failure and loop again.
- Do not move to the next endpoint until the current endpoint's tests are fully green.

---

## Definition of Done

The implementation is complete only when **all** of the following are true simultaneously:

- [ ] `pytest tests/ -v` exits 0 with no skipped or xfailed tests.
- [ ] Every endpoint listed in the spec exists and returns the documented HTTP status codes.
- [ ] Redirect behavior exactly matches the 302/404/410 rule: `GET /r/{token}` returns 302 for active, 410 for deleted or expired, 404 for never-existed — with no exceptions.
- [ ] `GET /api/qr/{token}` returns 404 for both deleted and non-existent tokens (not 410).
- [ ] The in-memory cache is invalidated on every `PATCH` and `DELETE` so stale redirects are impossible.
- [ ] A `ScanEvent` row is written for every successful 302 redirect.
- [ ] The frontend build (`npm run build`) completes without errors and is served correctly by FastAPI at `/`.

---

## Non-Goals

The following must **not** be added, even if they seem like natural improvements:

| Item | Reason excluded |
|---|---|
| Authentication / API keys | Out of scope for a prototype; adds complexity with no spec requirement |
| Rate limiting | No abuse-prevention requirement exists in the spec |
| Distributed caching (Redis, Memcached) | SQLite + in-memory dict is the specified stack |
| Message queues or async workers | Synchronous request handling is sufficient for the prototype |
| Multi-database support or migrations tooling (Alembic) | `Base.metadata.create_all` on startup is the specified approach |
| User accounts or ownership model | Tokens are anonymous by design |
| Custom short-URL slugs | Token generation algorithm is fixed in the spec |
| HTTPS termination or TLS config | Handled outside the app (reverse proxy / hosting layer) |
