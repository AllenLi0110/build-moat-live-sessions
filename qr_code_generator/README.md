# QR Code Generator — Exercise

## How to Use

1. Read `PROMPT.md`
2. Answer the Design Questions (write your answers directly in `PROMPT.md`)
3. Build the prototype:
   - **Challenge Track:** Build from scratch using `PROMPT.md` as your spec
   - **Guided Track:** Go to `scaffold/`, fill in the TODOs
4. Verify with the curl tests at the bottom of `PROMPT.md`
5. Bring your Design Questions answers to live session for discussion

## Choose Your Track

**Challenge Track** — You decide the architecture, file structure, and implementation. Any language/framework is OK (Python + FastAPI recommended). Read `PROMPT.md` to get started.

**Guided Track** — File structure and boilerplate are provided. Fill in the core logic marked with `TODO`. Go to `scaffold/` and follow the instructions below.

## Guided Track Setup

```bash
cd scaffold
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Files to Fill In

| File | TODO | Design Decision |
|------|------|-----------------|
| `app/token_gen.py` | `generate_token()` | How to generate unique, URL-safe short tokens |
| `app/url_validator.py` | `validate_url()` | URL normalization and malicious URL blocking |
| `app/routes.py` | `redirect()` | Cache → DB lookup → 410/404 fallback flow |

### Run and Verify

```bash
uvicorn app.main:app --reload
```

Then run the verification tests from `PROMPT.md`.

## Bonus Challenges

- Build a simple frontend (input URL → display QR code image)
- Add rate limiting to the create endpoint
- Add expiration support with automatic 410 responses
