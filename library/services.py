"""Streaming services we can import from (Netflix now, others later)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Service:
    slug: str
    name: str
    supported: bool


SERVICES = [
    Service("netflix", "Netflix", True),
    Service("prime-video", "Prime Video", False),
    Service("disney-plus", "Disney+", False),
    Service("max", "Max", False),
    Service("hulu", "Hulu", False),
    Service("apple-tv", "Apple TV+", False),
]

SERVICES_BY_SLUG = {service.slug: service for service in SERVICES}
