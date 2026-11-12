"""Text, date and URL helpers. Standard library only."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&apos;": "'",
    "&nbsp;": " ", "&rsquo;": "'", "&lsquo;": "'", "&ldquo;": '"', "&rdquo;": '"',
    "&ndash;": "-", "&mdash;": "-", "&hellip;": "...",
}

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "cmpid", "at_medium",
}


def strip_html(value: str, limit: int = 400) -> str:
    if not value:
        return ""
    text = TAG_RE.sub(" ", value)
    for entity, char in ENTITIES.items():
        text = text.replace(entity, char)
    return WS_RE.sub(" ", text).strip()[:limit].strip()


def to_datetime(value: Optional[str]) -> Optional[str]:
    """RSS or ISO timestamp to `YYYY-MM-DDTHH:MM:SS+00:00`, or None."""
    if not value:
        return None
    raw = str(value).strip()
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    # GDELT: 20261112T093000Z
    compact = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z", raw)
    if compact:
        parsed = datetime(*[int(part) for part in compact.groups()], tzinfo=timezone.utc)
        return parsed.isoformat()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except ValueError:
        return None


def parse_now(value: Optional[str]) -> datetime:
    """`--now` accepts a date or a full timestamp; naive input is read as UTC."""
    if not value:
        return datetime.now(timezone.utc).replace(microsecond=0)
    raw = value.strip()
    try:
        if len(raw) == 10:
            return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError(f"--now must be YYYY-MM-DD or an ISO timestamp, got {value!r}") from error


def hours_between(published: Optional[str], now: datetime) -> Optional[float]:
    if not published:
        return None
    try:
        then = datetime.fromisoformat(published)
    except ValueError:
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return round((now - then).total_seconds() / 3600, 1)


def in_window(published: Optional[str], now: datetime, hours: int) -> bool:
    age = hours_between(published, now)
    return age is not None and -1 <= age <= hours


def human_age(published: Optional[str], now: datetime) -> str:
    age = hours_between(published, now)
    if age is None:
        return "time not stated"
    if age < 1:
        return "under an hour ago"
    if age < 24:
        return f"{int(age)}h ago"
    return f"{int(age // 24)}d ago"


def canonical_url(url: str) -> str:
    """Drop tracking parameters and fragments so the same article has one address."""
    try:
        parts = urlparse(url.strip())
    except ValueError:
        return url
    query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING_PARAMS]
    path = parts.path.rstrip("/") or "/"
    return urlunparse((parts.scheme.lower() or "https", parts.netloc.lower(), path,
                       "", urlencode(query), ""))


def host_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host
