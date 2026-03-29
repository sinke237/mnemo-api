"""One-off script to remove expired password reset tokens.

Run with: `python -m scripts.cleanup_password_reset_tokens` from the project root.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from mnemo.db.database import engine, get_db
from mnemo.services import password_reset as pr_service


async def main() -> None:
    async with engine.connect() as conn:
        async with AsyncSession(bind=conn) as session:
            deleted = await pr_service.delete_expired_tokens(session)
            print(f"Deleted {deleted} expired password reset tokens")


if __name__ == "__main__":
    asyncio.run(main())
