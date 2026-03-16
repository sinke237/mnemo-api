"""Shared service utilities."""

from math import ceil


def pagination_meta(page: int, per_page: int, total: int) -> dict[str, int]:
    if per_page <= 0:
        raise ValueError("per_page must be greater than 0.")
    if page < 1:
        raise ValueError("page must be greater than or equal to 1.")
    if total < 0:
        raise ValueError("total must be greater than or equal to 0.")

    total_pages = 0 if total == 0 else ceil(total / per_page)
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }
