"""Shared service utilities."""

from math import ceil


def pagination_meta(page: int, per_page: int, total: int) -> dict[str, int]:
    total_pages = ceil(total / per_page) if per_page else 0
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }
