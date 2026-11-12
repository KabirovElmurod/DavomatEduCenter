"""
Markaz public URL helper'lari.

Har markazning o'z subdomain'i bo'lishi mumkin: {subdomain}.{BASE_DOMAIN}.
Subdomain yo'q yoki BASE_DOMAIN sozlanmagan bo'lsa PUBLIC_URL ishlatiladi.
"""
import re
from urllib.parse import urlparse

from app.core.config import settings

SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,48}[a-z0-9])?$")


def normalize_subdomain(value: str | None) -> str | None:
    """Subdomain ni normalizatsiya qilish (lowercase, slug tekshiruvi)"""
    if not value:
        return None
    slug = value.strip().lower()
    if not SLUG_RE.match(slug):
        return None
    return slug


def center_url(subdomain: str | None) -> str:
    """
    Markazning public URL'i.

    subdomain + BASE_DOMAIN bo'lsa: {scheme}://{sub}.{BASE_DOMAIN}[:port]
    (scheme/port PUBLIC_URL'dan meros olinadi — lokal test uchun).
    Aks holda PUBLIC_URL.
    """
    base = settings.PUBLIC_URL.strip().rstrip("/")
    if subdomain and settings.BASE_DOMAIN:
        p = urlparse(base)
        scheme = p.scheme or "https"
        port = f":{p.port}" if p.port else ""
        return f"{scheme}://{subdomain}.{settings.BASE_DOMAIN}{port}"
    return base
