from urllib.parse import urlparse, urlunparse

MAX_URL_LENGTH = 2048

BLOCKED_DOMAINS = {
    "evil.com",
    "malware.example.com",
    "phishing.example.com",
}


def is_blocked_domain(hostname: str | None) -> bool:
    if hostname is None:
        return True
    return hostname.lower() in BLOCKED_DOMAINS


def validate_url(url: str) -> str:
    if len(url) > MAX_URL_LENGTH:
        raise ValueError("URL exceeds maximum length of 2048 characters")

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL must use http or https scheme")

    if is_blocked_domain(parsed.hostname):
        raise ValueError(f"Domain '{parsed.hostname}' is blocked")

    # Normalize: upgrade to https, lowercase netloc, strip trailing slash
    path = parsed.path.rstrip("/")
    normalized = urlunparse((
        "https",
        parsed.netloc.lower(),
        path,
        parsed.params,
        parsed.query,
        parsed.fragment,
    ))
    return normalized
